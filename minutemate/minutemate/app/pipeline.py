"""The core flow: bot status -> transcript -> Claude notes -> PDF + Word -> email."""
import logging
import re
from datetime import datetime
from pathlib import Path

from . import db, recall
from .config import settings
from .documents import build_docx, build_pdf
from .emailer import parse_emails, send_notes
from .summarizer import summarize
from .transcript import duration, participants, to_lines, to_text

log = logging.getLogger("minutemate")
FILES = settings.DATA_DIR / "files"


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", text, flags=re.U).strip("-").lower()
    return (s or "meeting")[:60]


def apply_status(meeting: dict, code: str, sub_code: str = "") -> str:
    """Map a Recall status code onto our meeting status. Returns the new status."""
    status = meeting["status"]
    if status in (db.PROCESSING, db.READY):
        return status
    detail = code + (f" ({sub_code})" if sub_code else "")
    if code in recall.JOINING_CODES:
        status = db.JOINING
        detail = ("The bot is in the waiting room. Someone needs to let it in."
                  if code == "in_waiting_room" else "The bot is joining the meeting…")
    elif code in recall.RECORDING_CODES:
        status = db.RECORDING
        detail = "The bot is in the meeting and recording. You can close this page."
    elif code == "call_ended":
        detail = "Meeting ended. Preparing the transcript…"
    elif code in recall.FATAL_CODES:
        status = db.FAILED
        detail = _friendly_failure(code, sub_code)
    db.update_meeting(meeting["id"], status=status, status_detail=detail)
    return status


def _friendly_failure(code: str, sub_code: str) -> str:
    reasons = {
        "recording_permission_denied": "The host did not allow the bot to record.",
        "bot_kicked_from_waiting_room": "The bot was removed from the waiting room.",
        "bot_not_admitted": "Nobody let the bot in from the waiting room.",
        "meeting_not_found": "Meeting link not found or meeting not started.",
        "meeting_password_incorrect": "Wrong meeting password in the link.",
        "meeting_requires_sign_in": "The meeting only allows signed-in users.",
    }
    return reasons.get(sub_code) or reasons.get(code) or f"Bot failed: {code} {sub_code}".strip()


def process_meeting(meeting_id: str, send_email: bool = True) -> None:
    """Fetch transcript, summarise, build files, email. Safe to call more than once."""
    if not db.claim_for_processing(meeting_id):
        return
    m = db.get_meeting(meeting_id)
    try:
        bot = recall.get_bot(m["bot_id"])
        url = recall.transcript_download_url(bot)
        if not url:
            ts = recall.transcript_status(bot)
            if ts in ("processing", ""):
                # Not ready yet: go back to "recording" so the poller retries later.
                db.update_meeting(meeting_id, status=db.RECORDING, status_detail="Waiting for transcript…")
                return
            raise RuntimeError(f"No transcript available (status: {ts}).")

        raw = recall.download_transcript(url)
        lines = to_lines(raw)
        db.update_meeting(meeting_id, transcript_json=raw, status_detail="Writing notes…")
        notes = summarize(to_text(lines), m["title"], participants(lines), m["output_language"])
        regenerate_files(meeting_id, raw=raw, notes=notes)

        if send_email and parse_emails(m["attendee_emails"]) and settings.email_enabled:
            email_meeting(meeting_id)
    except Exception as e:  # noqa: BLE001
        log.exception("Processing failed for %s", meeting_id)
        db.update_meeting(meeting_id, status=db.FAILED, status_detail=f"Processing failed: {e}")


def doc_meta(m: dict, lines: list[dict]) -> dict:
    created = datetime.fromisoformat(m["created_at"])
    return {**m, "participants": participants(lines), "duration": duration(lines),
            "date_label": created.strftime("%d %b %Y")}


def regenerate_files(meeting_id: str, raw=None, notes=None) -> None:
    m = db.get_meeting(meeting_id)
    raw = raw if raw is not None else m["transcript"]
    notes = notes if notes is not None else m["summary"]
    lines = to_lines(raw or [])
    meta = doc_meta(m, lines)
    base = f"{_slug(notes.get('title') or m['title'])}-{meeting_id}"
    pdf = build_pdf(meta, notes, lines, FILES / f"{base}.pdf")
    docx = build_docx(meta, notes, lines, FILES / f"{base}.docx")
    db.update_meeting(meeting_id, summary_json=notes, pdf_path=str(pdf), docx_path=str(docx),
                      status=db.READY, status_detail="Notes ready")


def email_meeting(meeting_id: str) -> None:
    m = db.get_meeting(meeting_id)
    send_notes(parse_emails(m["attendee_emails"]), m["summary"], m,
               [Path(m["pdf_path"]), Path(m["docx_path"])])
    db.update_meeting(meeting_id, emailed_at=db.now())


def poll_once() -> None:
    """Backup for webhooks: check every active bot's status."""
    for m in db.list_active():
        try:
            bot = recall.get_bot(m["bot_id"])
            code, sub = recall.latest_status(bot)
            if code == "done":
                process_meeting(m["id"])
            elif code:
                apply_status(m, code, sub)
        except Exception:  # noqa: BLE001
            log.exception("Polling failed for %s", m["id"])
