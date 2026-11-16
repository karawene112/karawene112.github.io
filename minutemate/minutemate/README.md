# MinuteMate: AI notetaker for online meetings

Paste a **Zoom, Microsoft Teams or Google Meet** link → a bot joins the call and records everyone →
when the meeting ends you get **notes as PDF and Word**, emailed to the attendees.

## What it does

| Feature | Details |
|---|---|
| Bot joins meetings | Zoom, Teams, Google Meet (and Webex) via Recall.ai, now or at a scheduled time |
| Recording notice | Bot posts a chat message telling everyone it is recording |
| Who said what | Uses each participant's own audio stream, so real names are in the transcript |
| Multilingual | Language auto-detection (Arabic / French / English…); notes in the meeting language or a chosen one |
| AI notes (Claude) | Summary, key points, decisions, action items (task / owner / due), open questions, notes by topic, next meeting |
| Exports | Branded PDF and Word (.docx) with the full transcript at the end |
| Email | Sends both files + summary to attendees automatically (any SMTP: Gmail, Outlook, SendGrid…) |
| Edit and resend | Correct the notes in the browser, which regenerates PDF/Word, then resend |
| Controls | Live status, make the bot leave, cancel a scheduled bot, retry, delete |
| Reliability | Webhooks **plus** a background status check, so it also works on your laptop without webhooks |
| Login | Password-protected dashboard |

## How it works

```
Meeting link ─► Recall.ai bot joins ─► records + transcribes ─► "done" (webhook or polling)
            ─► transcript ─► Claude writes the notes ─► PDF + Word ─► email to attendees
```

Code map:
- `app/main.py`: web pages, routes, Recall.ai webhook, background poller
- `app/recall.py`: Recall.ai API (create bot, status, transcript, leave/cancel)
- `app/summarizer.py`: Claude prompt and JSON notes
- `app/documents.py`: PDF and Word builders
- `app/emailer.py`: SMTP email with attachments
- `app/pipeline.py`: the end-to-end flow
- `app/db.py`: SQLite storage

## 1. Get your API keys

1. **Recall.ai**: sign up at recall.ai, create an API key and note your **region** (e.g. `us-east-1`).
2. **Claude**: create a key at console.anthropic.com.
3. **Email (optional)**: for Gmail use `smtp.gmail.com`, port `587`, and a Google **App Password**.

## 2. Run it on your computer

```bash
cd minutemate
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then fill in your keys
uvicorn app.main:app --reload
```
Open http://localhost:8000, log in with `APP_PASSWORD`, paste a meeting link and click **Send bot**.

On localhost Recall.ai can't call your webhook, so the app checks the bot status every `POLL_SECONDS`
(60 s by default). You can also click **Check status now**.

## 3. Put it online (so the whole team can use it)

Any host that runs Docker works (Render, Railway, Fly.io, a VPS):
1. Push this folder to GitHub (the `.env` file is git-ignored, so set the variables in the host's dashboard).
2. Create a new web service from the repo using the `Dockerfile`, and attach a disk mounted at `/data`.
3. Set `PUBLIC_BASE_URL` to your app's URL.
4. In the **Recall.ai dashboard → Webhooks**, add:
   `https://YOUR-APP-URL/webhooks/recall?token=YOUR_WEBHOOK_TOKEN`
   and subscribe to the bot status change events.

## Test without any API keys

```bash
python -m tests.test_offline
```
Runs the full flow with a sample multilingual meeting (Recall.ai and Claude mocked) and creates a sample PDF and Word file.

## Good to know

- **Consent**: the bot is visible in the participant list and posts a chat notice. Still tell participants
  you're recording, and check local laws.
- **Company Zoom/Teams settings**: some organisations block external bots or keep them in the waiting room;
  someone must admit the bot. If it isn't admitted the meeting shows *Failed* with the reason.
- **Costs**: Recall.ai bills per recorded hour (bot + transcription) and Claude per summary, roughly a
  few dollars per meeting hour in total. Check current prices on both sites.
- **Arabic in PDFs**: `arabic-reshaper` and `python-bidi` (in requirements) shape Arabic text correctly.
  Word files handle Arabic natively.

## Next features to add

- Calendar sync (Google/Outlook) so the bot joins every meeting automatically (Recall.ai Calendar API)
- Multiple users / company workspaces with Google or Microsoft login
- Send action items to Slack, Teams, Trello or Asana
- Search across past meetings and "ask a question about this meeting"
- Auto-delete recordings after X days (data retention)
