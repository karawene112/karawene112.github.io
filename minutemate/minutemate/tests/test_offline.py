"""Offline test: runs the whole pipeline with a fake Recall.ai bot and fake Claude reply.

Run:  python -m tests.test_offline
Creates sample PDF and Word files in data/files/.
"""
import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())

from app import db, pipeline, recall, summarizer  # noqa: E402


def w(words, start):
    return [{"text": t, "start_timestamp": {"relative": start + i * 0.4, "absolute": None},
             "end_timestamp": {"relative": start + i * 0.4 + 0.3, "absolute": None}}
            for i, t in enumerate(words.split())]


SAMPLE_TRANSCRIPT = [
    {"participant": {"id": 1, "name": "Sara Haddad"}, "language_code": "en",
     "words": w("Good morning everyone. Let's review the Q4 launch plan for the Doha office.", 0)},
    {"participant": {"id": 2, "name": "Omar Khalil"}, "language_code": "en",
     "words": w("The marketing campaign is ready but we still need the final budget approval.", 12)},
    {"participant": {"id": 2, "name": "Omar Khalil"}, "language_code": "en",
     "words": w("I can send the budget to finance by Thursday.", 20)},
    {"participant": {"id": 3, "name": "Claire Dubois"}, "language_code": "fr",
     "words": w("Pour la partie technique, l'application sera prête le 1er décembre.", 31)},
    {"participant": {"id": 1, "name": "Sara Haddad"}, "language_code": "en",
     "words": w("Great. So we agree the launch date is December 8th. Claire, please share the test report.", 45)},
]

FAKE_NOTES = {
    "title": "Q4 Launch Plan – Doha Office",
    "summary": "The team reviewed the Q4 launch plan for the Doha office. Marketing is ready pending budget "
               "approval, and the app will be technically ready on 1 December. The launch date was set to 8 December.",
    "key_points": ["Marketing campaign is ready", "Final budget approval is still pending",
                   "Application technically ready on 1 December"],
    "decisions": ["Launch date confirmed for 8 December"],
    "action_items": [{"task": "Send the budget to finance", "owner": "Omar Khalil", "due": "Thursday"},
                     {"task": "Share the test report", "owner": "Claire Dubois", "due": ""}],
    "open_questions": ["Will finance approve the budget in time for the launch?"],
    "topics": [{"topic": "Marketing", "notes": ["Campaign ready", "Waiting on budget"]},
               {"topic": "Technical", "notes": ["App ready on 1 December"]}],
    "next_meeting": "",
}

FAKE_BOT = {"id": "bot_test_123", "status_changes": [{"code": "joining_call"}, {"code": "in_call_recording"},
                                                     {"code": "call_ended"}, {"code": "done"}],
            "recordings": [{"media_shortcuts": {"transcript": {"status": {"code": "done"},
                                                               "data": {"download_url": "https://x/t.json"}}}}]}


def main():
    db.init_db()
    # Mock the network calls
    recall.get_bot = lambda bot_id: FAKE_BOT
    recall.download_transcript = lambda url: SAMPLE_TRANSCRIPT
    pipeline.summarize = lambda text, title, people, lang: (print("--- transcript sent to Claude ---\n" + text), FAKE_NOTES)[1]
    summarizer.settings.ANTHROPIC_API_KEY = "test"

    mid = db.create_meeting("Weekly sync", "https://meet.google.com/abc-defg-hij", None, "a@b.com", "same")
    db.update_meeting(mid, bot_id="bot_test_123", status=db.RECORDING)

    # Status mapping
    m = db.get_meeting(mid)
    assert recall.latest_status(FAKE_BOT) == ("done", "")
    assert pipeline.apply_status(m, "in_waiting_room") == db.JOINING

    # Full processing (email skipped because SMTP isn't configured)
    pipeline.process_meeting(mid)
    m = db.get_meeting(mid)
    assert m["status"] == db.READY, m["status_detail"]
    assert os.path.getsize(m["pdf_path"]) > 2000 and os.path.getsize(m["docx_path"]) > 2000
    assert db.get_meeting(mid)["platform"] == "Google Meet"

    # Processing twice must not duplicate work
    assert db.claim_for_processing(mid) is False

    # JSON extraction from a Claude reply wrapped in ```json fences
    assert summarizer._extract_json('```json\n{"title": "x"}\n```')["title"] == "x"
    print("\nALL CHECKS PASSED")
    print("PDF :", m["pdf_path"])
    print("DOCX:", m["docx_path"])


if __name__ == "__main__":
    main()
