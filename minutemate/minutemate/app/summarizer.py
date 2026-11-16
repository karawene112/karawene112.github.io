"""Uses Claude to turn the transcript into structured meeting notes."""
import json
import re

import httpx

from .config import settings

SYSTEM = """You are an expert executive assistant who writes meeting minutes for companies.
You receive a meeting transcript with timestamps and speaker names.
Extract only what was actually said. Never invent facts, names, owners or dates.
If something is unclear, leave it out or put it under open questions.
Return ONLY valid JSON, no markdown, matching this schema:
{
  "title": "short meeting title",
  "summary": "3-6 sentence executive summary",
  "key_points": ["important point", ...],
  "decisions": ["decision that was agreed", ...],
  "action_items": [{"task": "...", "owner": "person or 'Unassigned'", "due": "date/timeframe or ''"}],
  "open_questions": ["unresolved question or risk", ...],
  "topics": [{"topic": "...", "notes": ["...", "..."]}],
  "next_meeting": "date/time if mentioned, else ''"
}"""

LANG_NAMES = {"en": "English", "fr": "French", "ar": "Arabic"}


class SummaryError(Exception):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise SummaryError("Claude did not return JSON.")
        return json.loads(m.group(0))


def _normalize(d: dict) -> dict:
    out = {
        "title": str(d.get("title") or "Meeting notes"),
        "summary": str(d.get("summary") or ""),
        "key_points": [str(x) for x in d.get("key_points") or []],
        "decisions": [str(x) for x in d.get("decisions") or []],
        "action_items": [],
        "open_questions": [str(x) for x in d.get("open_questions") or []],
        "topics": [],
        "next_meeting": str(d.get("next_meeting") or ""),
    }
    for a in d.get("action_items") or []:
        if isinstance(a, dict):
            out["action_items"].append({"task": str(a.get("task", "")),
                                        "owner": str(a.get("owner") or "Unassigned"),
                                        "due": str(a.get("due") or "")})
        else:
            out["action_items"].append({"task": str(a), "owner": "Unassigned", "due": ""})
    for t in d.get("topics") or []:
        if isinstance(t, dict):
            out["topics"].append({"topic": str(t.get("topic", "")),
                                  "notes": [str(n) for n in t.get("notes") or []]})
    return out


def summarize(transcript_text: str, meeting_title: str, participants: list[str],
              output_language: str = "same") -> dict:
    if not settings.ANTHROPIC_API_KEY:
        raise SummaryError("ANTHROPIC_API_KEY is not set.")
    if not transcript_text.strip():
        raise SummaryError("The transcript is empty (nobody spoke, or the bot was not admitted).")

    if output_language in LANG_NAMES:
        lang_rule = f"Write all notes in {LANG_NAMES[output_language]}."
    else:
        lang_rule = "Write the notes in the main language spoken in the meeting."

    user = (f"Meeting: {meeting_title}\nParticipants: {', '.join(participants)}\n{lang_rule}\n\n"
            f"<transcript>\n{transcript_text}\n</transcript>")

    with httpx.Client(timeout=300) as c:
        r = c.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": settings.CLAUDE_MODEL, "max_tokens": 8000, "system": SYSTEM,
                  "messages": [{"role": "user", "content": user}]},
        )
    if r.status_code >= 400:
        raise SummaryError(f"Claude API error {r.status_code}: {r.text[:500]}")
    text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    return _normalize(_extract_json(text))
