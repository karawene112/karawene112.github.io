"""Builds the meeting notes as PDF (reportlab) and Word (python-docx)."""
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ACCENT = colors.HexColor("#4F46E5")
ACCENT_RGB = RGBColor(0x4F, 0x46, 0xE5)

# ---------- fonts (Unicode: accents + Arabic) ----------
_FONT_CANDIDATES = [
    os.getenv("PDF_FONT", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
FONT, FONT_BOLD = "Helvetica", "Helvetica-Bold"
for _p in _FONT_CANDIDATES:
    if _p and Path(_p).exists():
        pdfmetrics.registerFont(TTFont("Body", _p))
        bold = _p.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
        pdfmetrics.registerFont(TTFont("BodyBold", bold if Path(bold).exists() else _p))
        pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyBold",
                                      italic="Body", boldItalic="BodyBold")
        FONT, FONT_BOLD = "Body", "BodyBold"
        break

_ARABIC = re.compile(r"[\u0600-\u06FF]")
try:  # optional: correct Arabic letter shaping in PDFs
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:  # pragma: no cover
    arabic_reshaper = None


def _is_rtl(text: str) -> bool:
    return bool(_ARABIC.search(text or ""))


def _pdf_text(text: str) -> str:
    text = text or ""
    if arabic_reshaper and _is_rtl(text):
        text = get_display(arabic_reshaper.reshape(text))
    return escape(text)


# ---------- PDF ----------
def build_pdf(meeting: dict, notes: dict, lines: list[dict], out_path: Path,
              include_transcript: bool = True) -> Path:
    ss = getSampleStyleSheet()
    rtl = _is_rtl(notes.get("summary", ""))
    align = {"alignment": TA_RIGHT} if rtl else {}
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName=FONT, fontSize=10.5, leading=15, **align)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=11, textColor=colors.HexColor("#555555"))
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName=FONT_BOLD, fontSize=20, textColor=ACCENT,
                        spaceAfter=4, **({"alignment": TA_RIGHT} if rtl else {"alignment": 0}))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=FONT_BOLD, fontSize=13, textColor=ACCENT,
                        spaceBefore=12, spaceAfter=6, **align)
    cell = ParagraphStyle("c", parent=body, fontSize=9.5, leading=12)
    cell_h = ParagraphStyle("ch", parent=cell, fontName=FONT_BOLD, textColor=colors.white)

    story = [Paragraph(_pdf_text(notes.get("title") or meeting["title"]), h1)]
    meta = (f"{escape(meeting.get('platform') or '')} · {escape(meeting.get('date_label', ''))} · "
            f"Duration {escape(meeting.get('duration', ''))}<br/>"
            f"Participants: {_pdf_text(', '.join(meeting.get('participants', [])))}")
    story += [Paragraph(meta, small), Spacer(1, 10)]

    def bullets(items):
        return ListFlowable([ListItem(Paragraph(_pdf_text(i), body), leftIndent=12) for i in items],
                            bulletType="bullet", start="•", leftIndent=12)

    if notes.get("summary"):
        story += [Paragraph("Summary", h2), Paragraph(_pdf_text(notes["summary"]), body)]
    if notes.get("key_points"):
        story += [Paragraph("Key points", h2), bullets(notes["key_points"])]
    if notes.get("decisions"):
        story += [Paragraph("Decisions", h2), bullets(notes["decisions"])]
    if notes.get("action_items"):
        story.append(Paragraph("Action items", h2))
        data = [[Paragraph("Task", cell_h), Paragraph("Owner", cell_h), Paragraph("Due", cell_h)]]
        for a in notes["action_items"]:
            data.append([Paragraph(_pdf_text(a["task"]), cell), Paragraph(_pdf_text(a["owner"]), cell),
                         Paragraph(_pdf_text(a["due"] or "—"), cell)])
        t = Table(data, colWidths=[10 * cm, 3.8 * cm, 3.2 * cm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F4FF")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D3F0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
    if notes.get("open_questions"):
        story += [Paragraph("Open questions", h2), bullets(notes["open_questions"])]
    if notes.get("topics"):
        story.append(Paragraph("Discussion by topic", h2))
        for tp in notes["topics"]:
            story.append(Paragraph(f"<b>{_pdf_text(tp['topic'])}</b>", body))
            if tp["notes"]:
                story.append(bullets(tp["notes"]))
            story.append(Spacer(1, 4))
    if notes.get("next_meeting"):
        story += [Paragraph("Next meeting", h2), Paragraph(_pdf_text(notes["next_meeting"]), body)]
    if include_transcript and lines:
        story.append(Paragraph("Full transcript", h2))
        for l in lines:
            story.append(Paragraph(f"<font color='#888888'>[{l['time']}]</font> <b>{_pdf_text(l['speaker'])}:</b> "
                                   f"{_pdf_text(l['text'])}", small))
            story.append(Spacer(1, 2))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.HexColor("#999999"))
        canvas.drawString(2 * cm, 1.2 * cm, "Generated automatically from the meeting recording")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=2 * cm, title=notes.get("title", "Meeting notes"))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out_path


# ---------- Word ----------
def build_docx(meeting: dict, notes: dict, lines: list[dict], out_path: Path,
               include_transcript: bool = True) -> Path:
    d = Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(11)

    def para(text, style=None, bold=False, color=None, size=None):
        p = d.add_paragraph(style=style)
        run = p.add_run(text)
        run.bold = bold
        if color:
            run.font.color.rgb = color
        if size:
            run.font.size = Pt(size)
        if _is_rtl(text):
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run.font.rtl = True
        return p

    def heading(text):
        h = d.add_heading(text, level=2)
        for r in h.runs:
            r.font.color.rgb = ACCENT_RGB

    t = d.add_heading(notes.get("title") or meeting["title"], level=0)
    for r in t.runs:
        r.font.color.rgb = ACCENT_RGB
    para(f"{meeting.get('platform', '')} · {meeting.get('date_label', '')} · Duration {meeting.get('duration', '')}",
         color=RGBColor(0x66, 0x66, 0x66), size=9)
    para("Participants: " + ", ".join(meeting.get("participants", [])), color=RGBColor(0x66, 0x66, 0x66), size=9)

    if notes.get("summary"):
        heading("Summary")
        para(notes["summary"])
    for key, label in (("key_points", "Key points"), ("decisions", "Decisions")):
        if notes.get(key):
            heading(label)
            for i in notes[key]:
                para(i, style="List Bullet")
    if notes.get("action_items"):
        heading("Action items")
        tbl = d.add_table(rows=1, cols=3)
        tbl.style = "Light Grid Accent 1"
        for c, txt in zip(tbl.rows[0].cells, ("Task", "Owner", "Due")):
            c.text = txt
        for a in notes["action_items"]:
            row = tbl.add_row().cells
            row[0].text, row[1].text, row[2].text = a["task"], a["owner"], a["due"] or "—"
    if notes.get("open_questions"):
        heading("Open questions")
        for i in notes["open_questions"]:
            para(i, style="List Bullet")
    if notes.get("topics"):
        heading("Discussion by topic")
        for tp in notes["topics"]:
            para(tp["topic"], bold=True)
            for n in tp["notes"]:
                para(n, style="List Bullet")
    if notes.get("next_meeting"):
        heading("Next meeting")
        para(notes["next_meeting"])
    if include_transcript and lines:
        d.add_page_break()
        heading("Full transcript")
        for l in lines:
            p = d.add_paragraph()
            r1 = p.add_run(f"[{l['time']}] ")
            r1.font.color.rgb, r1.font.size = RGBColor(0x88, 0x88, 0x88), Pt(9)
            r2 = p.add_run(f"{l['speaker']}: ")
            r2.bold, r2.font.size = True, Pt(9)
            r3 = p.add_run(l["text"])
            r3.font.size = Pt(9)
            if _is_rtl(l["text"]):
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    d.save(str(out_path))
    return out_path
