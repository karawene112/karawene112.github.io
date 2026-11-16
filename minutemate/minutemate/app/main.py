"""MinuteMate web app: send a notetaker bot to online meetings and get PDF/Word notes."""
import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import db, pipeline, recall
from .config import settings
from .emailer import parse_emails
from .transcript import to_lines

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("minutemate")
HERE = Path(__file__).parent


async def _poller():
    while True:
        await asyncio.sleep(settings.POLL_SECONDS)
        try:
            await asyncio.to_thread(pipeline.poll_once)
        except Exception:  # noqa: BLE001
            log.exception("poller error")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    task = asyncio.create_task(_poller())
    yield
    task.cancel()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, max_age=60 * 60 * 24 * 14)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals["app_name"] = settings.APP_NAME

STATUS_LABELS = {
    db.SCHEDULED: ("Scheduled", "grey"), db.JOINING: ("Joining", "blue"),
    db.RECORDING: ("Recording", "red"), db.PROCESSING: ("Writing notes", "amber"),
    db.READY: ("Ready", "green"), db.FAILED: ("Failed", "darkred"),
}
templates.env.globals["status_labels"] = STATUS_LABELS


# ---------------- auth ----------------
def _logged_in(request: Request) -> bool:
    return request.session.get("auth") is True


def _guard(request: Request):
    if not _logged_in(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
def login(request: Request, password: str = Form(...)):
    if hmac.compare_digest(password, settings.APP_PASSWORD):
        request.session["auth"] = True
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": "Wrong password"}, status_code=401)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---------------- pages ----------------
def _setup_warnings() -> list[str]:
    w = []
    if not settings.RECALL_API_KEY:
        w.append("RECALL_API_KEY is missing: the bot can't join meetings.")
    if not settings.ANTHROPIC_API_KEY:
        w.append("ANTHROPIC_API_KEY is missing: notes can't be written.")
    if not settings.email_enabled:
        w.append("Email is not configured: notes won't be emailed (downloads still work).")
    if settings.APP_PASSWORD == "change-me":
        w.append("Change APP_PASSWORD in your .env file.")
    return w


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    _guard(request)
    return templates.TemplateResponse(request, "dashboard.html", {
        "meetings": db.list_meetings(), "warnings": _setup_warnings(),
        "error": request.query_params.get("error"),
    })


@app.post("/meetings")
def create_meeting(request: Request, meeting_url: str = Form(...), title: str = Form(""),
                   join_at: str = Form(""), tz_offset: int = Form(0),
                   attendee_emails: str = Form(""), output_language: str = Form("same")):
    _guard(request)
    meeting_url = meeting_url.strip()
    if not meeting_url.startswith("http"):
        return RedirectResponse("/?error=Please+paste+a+full+meeting+link+(https://...)", status_code=303)

    join_iso: Optional[str] = None
    if join_at:
        # Browser sends local time + its UTC offset in minutes (JS getTimezoneOffset)
        local = datetime.fromisoformat(join_at)
        utc = (local + timedelta(minutes=tz_offset)).replace(tzinfo=timezone.utc)
        if utc > datetime.now(timezone.utc) + timedelta(minutes=10):
            join_iso = utc.isoformat().replace("+00:00", "Z")

    title = title.strip() or f"{db.detect_platform(meeting_url)} meeting"
    mid = db.create_meeting(title, meeting_url, join_iso, attendee_emails.strip(), output_language)
    try:
        bot = recall.create_bot(meeting_url, mid, join_iso)
        db.update_meeting(mid, bot_id=bot["id"],
                          status=db.SCHEDULED if join_iso else db.JOINING,
                          status_detail="Bot scheduled" if join_iso else "Bot is joining the meeting…")
    except Exception as e:  # noqa: BLE001
        db.update_meeting(mid, status=db.FAILED, status_detail=str(e))
    return RedirectResponse(f"/meetings/{mid}", status_code=303)


@app.get("/meetings/{mid}", response_class=HTMLResponse)
def meeting_page(request: Request, mid: str):
    _guard(request)
    m = db.get_meeting(mid)
    if not m:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "meeting.html", {
        "m": m, "lines": to_lines(m["transcript"] or []), "notes": m["summary"],
        "emails": parse_emails(m["attendee_emails"]), "email_enabled": settings.email_enabled,
        "flash": request.query_params.get("msg"),
    })


@app.get("/meetings/{mid}/status")
def meeting_status(request: Request, mid: str):
    _guard(request)
    m = db.get_meeting(mid)
    if not m:
        raise HTTPException(404)
    return {"status": m["status"], "detail": m["status_detail"]}


@app.post("/meetings/{mid}/refresh")
def refresh(request: Request, mid: str, background: BackgroundTasks):
    """Check status now (instead of waiting for the poller)."""
    _guard(request)
    m = db.get_meeting(mid)
    if m and m["bot_id"]:
        try:
            code, sub = recall.latest_status(recall.get_bot(m["bot_id"]))
            if code == "done":
                background.add_task(pipeline.process_meeting, mid)
            else:
                pipeline.apply_status(m, code, sub)
        except Exception as e:  # noqa: BLE001
            return RedirectResponse(f"/meetings/{mid}?msg=Could+not+refresh:+{e}", status_code=303)
    return RedirectResponse(f"/meetings/{mid}", status_code=303)


@app.post("/meetings/{mid}/retry")
def retry(request: Request, mid: str, background: BackgroundTasks):
    """Re-run transcript -> notes -> files (e.g. after fixing an API key)."""
    _guard(request)
    db.update_meeting(mid, status=db.RECORDING, status_detail="Retrying…")
    background.add_task(pipeline.process_meeting, mid, False)
    return RedirectResponse(f"/meetings/{mid}?msg=Retrying…", status_code=303)


@app.post("/meetings/{mid}/stop")
def stop_bot(request: Request, mid: str):
    _guard(request)
    m = db.get_meeting(mid)
    try:
        if m["status"] == db.SCHEDULED:
            recall.delete_bot(m["bot_id"])
            db.update_meeting(mid, status=db.FAILED, status_detail="Cancelled before the meeting")
        else:
            recall.leave_call(m["bot_id"])
            db.update_meeting(mid, status_detail="Bot asked to leave. Notes will follow shortly.")
    except Exception as e:  # noqa: BLE001
        return RedirectResponse(f"/meetings/{mid}?msg=Error:+{e}", status_code=303)
    return RedirectResponse(f"/meetings/{mid}", status_code=303)


@app.post("/meetings/{mid}/notes")
def edit_notes(request: Request, mid: str, title: str = Form(...), summary: str = Form(""),
               key_points: str = Form(""), decisions: str = Form(""), action_items: str = Form(""),
               open_questions: str = Form("")):
    """Let the user correct the notes before (re)sending. Lists = one item per line."""
    _guard(request)
    m = db.get_meeting(mid)
    notes = dict(m["summary"] or {})

    def lines_of(s):
        return [x.strip(" •-\t") for x in s.splitlines() if x.strip(" •-\t")]

    actions = []
    for row in lines_of(action_items):
        parts = [p.strip() for p in row.split("|")]
        actions.append({"task": parts[0], "owner": parts[1] if len(parts) > 1 and parts[1] else "Unassigned",
                        "due": parts[2] if len(parts) > 2 else ""})
    notes.update(title=title.strip(), summary=summary.strip(), key_points=lines_of(key_points),
                 decisions=lines_of(decisions), action_items=actions, open_questions=lines_of(open_questions))
    pipeline.regenerate_files(mid, notes=notes)
    return RedirectResponse(f"/meetings/{mid}?msg=Notes+updated,+PDF+and+Word+regenerated", status_code=303)


@app.post("/meetings/{mid}/attendees")
def update_attendees(request: Request, mid: str, attendee_emails: str = Form("")):
    _guard(request)
    db.update_meeting(mid, attendee_emails=attendee_emails.strip())
    return RedirectResponse(f"/meetings/{mid}?msg=Attendees+saved", status_code=303)


@app.post("/meetings/{mid}/email")
def email(request: Request, mid: str):
    _guard(request)
    try:
        pipeline.email_meeting(mid)
        msg = "Notes+emailed+to+attendees"
    except Exception as e:  # noqa: BLE001
        msg = f"Email+failed:+{e}"
    return RedirectResponse(f"/meetings/{mid}?msg={msg}", status_code=303)


@app.get("/meetings/{mid}/download/{kind}")
def download(request: Request, mid: str, kind: str):
    _guard(request)
    m = db.get_meeting(mid)
    path = m and (m["pdf_path"] if kind == "pdf" else m["docx_path"] if kind == "docx" else None)
    if not path or not Path(path).exists():
        raise HTTPException(404, "File not ready yet")
    return FileResponse(path, filename=Path(path).name)


@app.post("/meetings/{mid}/delete")
def delete(request: Request, mid: str):
    _guard(request)
    m = db.get_meeting(mid)
    if m:
        for p in (m["pdf_path"], m["docx_path"]):
            if p and Path(p).exists():
                Path(p).unlink()
        db.delete_meeting(mid)
    return RedirectResponse("/", status_code=303)


# ---------------- Recall.ai webhook ----------------
@app.post("/webhooks/recall")
async def recall_webhook(request: Request, background: BackgroundTasks, token: str = ""):
    """Set this URL in the Recall.ai dashboard: {PUBLIC_BASE_URL}/webhooks/recall?token=WEBHOOK_TOKEN"""
    if not hmac.compare_digest(token, settings.WEBHOOK_TOKEN):
        raise HTTPException(401)
    payload = await request.json()
    event = payload.get("event", "")
    data = payload.get("data") or {}
    bot_id = (data.get("bot") or {}).get("id")
    if not bot_id or not event.startswith("bot."):
        return JSONResponse({"ok": True})
    m = db.get_by_bot(bot_id)
    if not m:
        return JSONResponse({"ok": True, "ignored": "unknown bot"})
    code = (data.get("data") or {}).get("code") or event.split(".", 1)[1]
    sub = (data.get("data") or {}).get("sub_code") or ""
    log.info("Webhook %s for meeting %s", event, m["id"])
    if code == "done":
        background.add_task(pipeline.process_meeting, m["id"])
    else:
        pipeline.apply_status(m, code, sub)
    return JSONResponse({"ok": True})


@app.get("/health")
def health():
    return {"ok": True}
