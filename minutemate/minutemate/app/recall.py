"""Recall.ai client: sends the bot to Zoom / Teams / Google Meet and fetches the transcript."""
from typing import Optional

import httpx

from .config import settings

# Recall bot status codes -> our status
JOINING_CODES = {"joining_call", "in_waiting_room", "in_call_not_recording",
                 "recording_permission_allowed"}
RECORDING_CODES = {"in_call_recording"}
ENDED_CODES = {"call_ended", "done"}
FATAL_CODES = {"fatal", "recording_permission_denied"}


class RecallError(Exception):
    pass


def _headers() -> dict:
    if not settings.RECALL_API_KEY:
        raise RecallError("RECALL_API_KEY is not set.")
    return {"Authorization": f"Token {settings.RECALL_API_KEY}",
            "Content-Type": "application/json", "Accept": "application/json"}


def _check(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        raise RecallError(f"Recall.ai error {r.status_code}: {r.text[:500]}")
    return r.json() if r.content else {}


def create_bot(meeting_url: str, meeting_id: str, join_at: Optional[str] = None) -> dict:
    """Send a notetaker bot to the meeting. join_at = ISO 8601 UTC time to schedule it."""
    body: dict = {
        "meeting_url": meeting_url,
        "bot_name": settings.BOT_NAME,
        "metadata": {"meeting_id": meeting_id},
        "recording_config": {
            "transcript": {
                "provider": {
                    "recallai_streaming": {
                        "mode": "prioritize_accuracy",
                        "language_code": settings.TRANSCRIPT_LANGUAGE,
                    }
                },
                # Each participant's own audio stream -> real names on every line
                "diarization": {"use_separate_streams_when_available": True},
            },
        },
        # Tell everyone in the meeting that it's being recorded
        "chat": {
            "on_bot_join": {
                "send_to": "everyone",
                "message": (f"Hi everyone, I'm {settings.BOT_NAME}. I'm recording this meeting "
                            "to produce meeting notes for the attendees."),
            }
        },
    }
    if join_at:
        body["join_at"] = join_at
    with httpx.Client(timeout=30) as c:
        return _check(c.post(f"{settings.recall_base}/bot/", json=body, headers=_headers()))


def get_bot(bot_id: str) -> dict:
    with httpx.Client(timeout=30) as c:
        return _check(c.get(f"{settings.recall_base}/bot/{bot_id}/", headers=_headers()))


def leave_call(bot_id: str) -> None:
    with httpx.Client(timeout=30) as c:
        _check(c.post(f"{settings.recall_base}/bot/{bot_id}/leave_call/", headers=_headers()))


def delete_bot(bot_id: str) -> None:
    """Cancel a scheduled bot that hasn't joined yet."""
    with httpx.Client(timeout=30) as c:
        r = c.delete(f"{settings.recall_base}/bot/{bot_id}/", headers=_headers())
        if r.status_code >= 400 and r.status_code != 404:
            raise RecallError(f"Recall.ai error {r.status_code}: {r.text[:300]}")


def latest_status(bot: dict) -> tuple[str, str]:
    """Return (code, sub_code) of the bot's latest status."""
    changes = bot.get("status_changes") or []
    if changes:
        last = changes[-1]
        return last.get("code", ""), last.get("sub_code") or ""
    status = bot.get("status") or {}
    if isinstance(status, dict):
        return status.get("code", ""), status.get("sub_code") or ""
    return str(status), ""


def transcript_download_url(bot: dict) -> Optional[str]:
    for rec in bot.get("recordings") or []:
        t = ((rec.get("media_shortcuts") or {}).get("transcript") or {})
        url = (t.get("data") or {}).get("download_url")
        if url:
            return url
    return None


def transcript_status(bot: dict) -> str:
    for rec in bot.get("recordings") or []:
        t = ((rec.get("media_shortcuts") or {}).get("transcript") or {})
        st = t.get("status") or {}
        return st.get("code", "") if isinstance(st, dict) else str(st)
    return ""


def download_transcript(url: str) -> list:
    with httpx.Client(timeout=60) as c:
        r = c.get(url)
        if r.status_code >= 400:
            raise RecallError(f"Transcript download failed: {r.status_code}")
        return r.json()
