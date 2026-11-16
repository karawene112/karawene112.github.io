"""Emails the PDF + Word notes to the attendees (any SMTP: Gmail, Outlook, SendGrid...)."""
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from .config import settings


def parse_emails(raw: str) -> list[str]:
    parts = [p.strip() for p in (raw or "").replace(";", ",").replace("\n", ",").split(",")]
    return [p for p in parts if "@" in p and "." in p.split("@")[-1]]


def send_notes(to: list[str], notes: dict, meeting: dict, attachments: list[Path]) -> None:
    if not settings.email_enabled:
        raise RuntimeError("Email is not configured (set SMTP_HOST / SMTP_FROM).")
    if not to:
        raise RuntimeError("No attendee emails for this meeting.")

    msg = EmailMessage()
    msg["Subject"] = f"Meeting notes: {notes.get('title') or meeting['title']}"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = ", ".join(to)

    actions = "\n".join(f"  • {a['task']} — {a['owner']}" + (f" (due {a['due']})" if a["due"] else "")
                        for a in notes.get("action_items", [])) or "  • None"
    link = f"{settings.PUBLIC_BASE_URL}/meetings/{meeting['id']}"
    msg.set_content(
        f"Hi,\n\nHere are the notes from \"{meeting['title']}\".\n\n"
        f"SUMMARY\n{notes.get('summary', '')}\n\nACTION ITEMS\n{actions}\n\n"
        f"The full notes are attached as PDF and Word.\nOnline version: {link}\n\n— {settings.APP_NAME}\n"
    )
    for path in attachments:
        if path and Path(path).exists():
            data = Path(path).read_bytes()
            if str(path).endswith(".pdf"):
                msg.add_attachment(data, maintype="application", subtype="pdf", filename=Path(path).name)
            else:
                msg.add_attachment(data, maintype="application",
                                   subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   filename=Path(path).name)

    if settings.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, 465, context=ssl.create_default_context()) as s:
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as s:
            s.starttls(context=ssl.create_default_context())
            if settings.SMTP_USER:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
