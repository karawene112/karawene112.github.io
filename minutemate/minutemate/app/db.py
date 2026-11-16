"""Tiny SQLite storage for meetings."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .config import settings

DB_PATH = settings.DATA_DIR / "minutemate.db"

# Meeting lifecycle (our own statuses)
SCHEDULED = "scheduled"      # bot created, waiting for join time
JOINING = "joining"          # bot is joining / in waiting room
RECORDING = "recording"      # bot is in the call and recording
PROCESSING = "processing"    # meeting ended, building notes
READY = "ready"              # notes + PDF/Word ready
FAILED = "failed"

ACTIVE_STATUSES = (SCHEDULED, JOINING, RECORDING)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                meeting_url TEXT NOT NULL,
                platform TEXT,
                join_at TEXT,
                attendee_emails TEXT DEFAULT '',
                output_language TEXT DEFAULT 'same',
                bot_id TEXT,
                status TEXT NOT NULL,
                status_detail TEXT DEFAULT '',
                transcript_json TEXT,
                summary_json TEXT,
                pdf_path TEXT,
                docx_path TEXT,
                emailed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def detect_platform(url: str) -> str:
    u = url.lower()
    if "zoom.us" in u:
        return "Zoom"
    if "teams.microsoft" in u or "teams.live" in u:
        return "Microsoft Teams"
    if "meet.google" in u:
        return "Google Meet"
    if "webex" in u:
        return "Webex"
    return "Other"


def create_meeting(title: str, meeting_url: str, join_at: Optional[str],
                   attendee_emails: str, output_language: str) -> str:
    mid = uuid.uuid4().hex[:12]
    ts = now()
    with _conn() as c:
        c.execute(
            """INSERT INTO meetings (id, title, meeting_url, platform, join_at, attendee_emails,
               output_language, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (mid, title, meeting_url, detect_platform(meeting_url), join_at,
             attendee_emails, output_language, SCHEDULED, ts, ts),
        )
    return mid


def update_meeting(mid: str, **fields: Any) -> None:
    if not fields:
        return
    for k in ("transcript_json", "summary_json"):
        if k in fields and not isinstance(fields[k], (str, type(None))):
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
    fields["updated_at"] = now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE meetings SET {cols} WHERE id = ?", (*fields.values(), mid))


def claim_for_processing(mid: str) -> bool:
    """Atomically move a meeting to PROCESSING so it is only processed once."""
    with _conn() as c:
        cur = c.execute(
            "UPDATE meetings SET status = ?, updated_at = ? WHERE id = ? AND status NOT IN (?, ?)",
            (PROCESSING, now(), mid, PROCESSING, READY),
        )
        return cur.rowcount == 1


def _row(r: Optional[sqlite3.Row]) -> Optional[dict]:
    if r is None:
        return None
    d = dict(r)
    for k in ("transcript_json", "summary_json"):
        d[k.replace("_json", "")] = json.loads(d[k]) if d.get(k) else None
    return d


def get_meeting(mid: str) -> Optional[dict]:
    with _conn() as c:
        return _row(c.execute("SELECT * FROM meetings WHERE id = ?", (mid,)).fetchone())


def get_by_bot(bot_id: str) -> Optional[dict]:
    with _conn() as c:
        return _row(c.execute("SELECT * FROM meetings WHERE bot_id = ?", (bot_id,)).fetchone())


def list_meetings() -> list[dict]:
    with _conn() as c:
        return [_row(r) for r in c.execute("SELECT * FROM meetings ORDER BY created_at DESC")]


def list_active() -> list[dict]:
    q = f"SELECT * FROM meetings WHERE status IN ({','.join('?' * len(ACTIVE_STATUSES))}) AND bot_id IS NOT NULL"
    with _conn() as c:
        return [_row(r) for r in c.execute(q, ACTIVE_STATUSES)]


def delete_meeting(mid: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM meetings WHERE id = ?", (mid,))
