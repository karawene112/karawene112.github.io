"""Turn Recall.ai's word-level transcript into readable speaker lines."""


def _fmt_time(seconds: float) -> str:
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def to_lines(raw: list) -> list[dict]:
    """Recall JSON -> [{speaker, start, time, text}], merging consecutive blocks by the same speaker."""
    lines: list[dict] = []
    for block in raw or []:
        p = block.get("participant") or {}
        speaker = p.get("name") or f"Speaker {p.get('id', '?')}"
        words = block.get("words") or []
        text = " ".join(w.get("text", "").strip() for w in words).strip()
        if not text:
            continue
        start = ((words[0].get("start_timestamp") or {}).get("relative")) or 0
        if lines and lines[-1]["speaker"] == speaker:
            lines[-1]["text"] += " " + text
        else:
            lines.append({"speaker": speaker, "start": start, "time": _fmt_time(start), "text": text})
    return lines


def to_text(lines: list[dict]) -> str:
    return "\n".join(f"[{l['time']}] {l['speaker']}: {l['text']}" for l in lines)


def participants(lines: list[dict]) -> list[str]:
    seen: list[str] = []
    for l in lines:
        if l["speaker"] not in seen:
            seen.append(l["speaker"])
    return seen


def duration(lines: list[dict]) -> str:
    return _fmt_time(lines[-1]["start"]) if lines else "00:00"
