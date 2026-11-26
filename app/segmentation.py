"""Segmenting an MMR.

Not "sentence splitting": an MMR is not a stream of sentences. It contains category
headings, bullet lists and tables, and a naive split on full stops both invents
boundaries (`nt.`, `jne.`, `min.`) and destroys the heading structure that carries the
category information. Every segment gets an id, so a TK row can point back at exactly
what it came from.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

HEADING = "HEADING"
BULLET = "BULLET"
TABLE_ROW = "TABLE_ROW"
SENTENCE = "SENTENCE"

# Estonian abbreviations that end in a full stop and must never end a sentence.
ABBREVIATIONS: frozenset[str] = frozenset(
    {
        "nt",
        "jne",
        "jt",
        "sh",
        "s.h",
        "k.a",
        "min",
        "max",
        "vt",
        "u",
        "ca",
        "lk",
        "nr",
        "tk",
        "mm",
        "cm",
        "kg",
        "jm",
        "st",
        "s.o",
        "vms",
        "vmt",
    }
)

_BULLET_RE = re.compile(r"^\s*(?:[-•▪‣·*–—]|\(?\d{1,2}\)|[a-zõäöüšž]\))\s+")
_NUMBERED_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(\S.*)$")
_WORD_CHARS = r"[0-9A-Za-zÕÄÖÜŠŽõäöüšž.]"
_TRAILING_TOKEN_RE = re.compile(rf"({_WORD_CHARS}+)$")
_SENTENCE_END_RE = re.compile(r"[.!?…]+")
_TABLE_SEP = " | "


@dataclass
class Seg:
    sid: str
    text: str
    segment_type: str
    order: int
    list_level: int | None = None

    def as_dict(self) -> dict:
        return {
            "sid": self.sid,
            "text": self.text,
            "segment_type": self.segment_type,
            "order": self.order,
            "list_level": self.list_level,
        }


@dataclass
class _Builder:
    segments: list[Seg] = field(default_factory=list)

    def add(self, text: str, segment_type: str, list_level: int | None = None) -> None:
        cleaned = normalise_whitespace(text)
        if not cleaned:
            return
        order = len(self.segments)
        self.segments.append(
            Seg(
                sid=f"S{order + 1}",
                text=cleaned,
                segment_type=segment_type,
                order=order,
                list_level=list_level,
            )
        )


def normalise_whitespace(text: str) -> str:
    return re.sub(r"[ \t ]+", " ", (text or "").replace(" ", " ")).strip()


# --- sentence splitting ------------------------------------------------------------------


def _is_abbreviation_before(block: str, end: int) -> bool:
    """True when the full stop at `end` belongs to an abbreviation or to list numbering."""
    match = _TRAILING_TOKEN_RE.search(block[:end])
    if not match:
        return False
    token = match.group(1).rstrip(".").lower()
    if not token:
        return False
    if token in ABBREVIATIONS:
        return True
    # Leading list numbering ("1. Üldine nõue kehtib.") is not a sentence boundary.
    # A number anywhere else is one: "Kohver kaalub 12." does end a sentence.
    return token.isdigit() and match.start() == 0


def split_sentences(block: str) -> list[str]:
    """Split a paragraph into sentences, respecting Estonian abbreviations and numbers."""
    text = normalise_whitespace(block)
    if not text:
        return []

    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(text):
        end = match.end()
        if end >= len(text):
            break
        rest = text[end:]
        stripped = rest.lstrip()
        if len(rest) == len(stripped):
            # No whitespace after the stop: "1.5", "nt.x" - not a boundary.
            continue
        if not stripped:
            break
        nxt = stripped[0]
        if not (nxt.isupper() or nxt.isdigit() or nxt in "\"'„«"):
            continue
        if _is_abbreviation_before(text, match.start()):
            continue
        piece = text[start:end].strip()
        if piece:
            sentences.append(piece)
        start = end + (len(rest) - len(stripped))

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


# --- line classification -----------------------------------------------------------------


def _looks_like_heading(line: str, standalone: bool = True) -> bool:
    """`standalone` means nothing continues this line on the next one.

    Without that check a wrapped paragraph ("Kohver peab olema" / "valmistatud
    polümeerist.") turns into a bogus heading - which is exactly what text extracted
    from a PDF looks like.
    """
    text = line.strip()
    if not text or len(text) > 100:
        return False
    if text.endswith(":"):
        # "Kohver peab sisaldama:" introduces a list; it is a requirement stem.
        return False

    numbered = _NUMBERED_RE.match(text)
    if numbered:
        body = numbered.group(2).strip()
        if len(body) <= 60 and not body.endswith((".", "!", "?")):
            return True
        return body.endswith(".") and len(body.split()) <= 4

    letters = [c for c in text if c.isalpha()]
    if letters and text == text.upper():
        return True

    if standalone and len(text) <= 60 and not text.endswith((".", "!", "?", ",", ";")):
        return True
    return False


def _bullet_level(line: str) -> int:
    indent = len(line) - len(line.lstrip(" \t"))
    return 1 + indent // 2


def segment_text(text: str) -> list[Seg]:
    """Segment pasted text, a .txt upload, or text extracted from a PDF."""
    builder = _Builder()
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraph: list[str] = []

    def flush() -> None:
        if not paragraph:
            return
        block = " ".join(paragraph)
        paragraph.clear()
        for sentence in split_sentences(block):
            builder.add(sentence, SENTENCE)

    lines = raw.split("\n")
    for index, line in enumerate(lines):
        if not line.strip():
            flush()
            continue
        following = lines[index + 1] if index + 1 < len(lines) else ""
        standalone = not following.strip() or bool(_BULLET_RE.match(following))
        if _TABLE_SEP in line or line.count("\t") >= 2:
            flush()
            cells = [c.strip() for c in re.split(r"\t+|\s*\|\s*", line) if c.strip()]
            builder.add(_TABLE_SEP.join(cells), TABLE_ROW)
            continue
        if _BULLET_RE.match(line):
            flush()
            level = _bullet_level(line)
            builder.add(_BULLET_RE.sub("", line, count=1), BULLET, list_level=level)
            continue
        if _looks_like_heading(line, standalone=standalone):
            flush()
            builder.add(line, HEADING)
            continue
        paragraph.append(line.strip())

    flush()
    return builder.segments


# --- uploads ------------------------------------------------------------------------------


def segment_docx(data: bytes) -> list[Seg]:
    """Use the Word document's own structure rather than guessing from punctuation.

    python-docx does not expose the rendered auto-numbering text, so the list level is
    stored instead of a fabricated "1.2.3".
    """
    import docx  # imported lazily; only needed for uploads
    from docx.document import Document as DocxDocument
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document: DocxDocument = docx.Document(io.BytesIO(data))
    builder = _Builder()
    body = document.element.body
    paragraph: list[str] = []

    def flush() -> None:
        if not paragraph:
            return
        block = " ".join(paragraph)
        paragraph.clear()
        for sentence in split_sentences(block):
            builder.add(sentence, SENTENCE)

    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            para = Paragraph(child, document)
            text = normalise_whitespace(para.text)
            if not text:
                flush()
                continue
            style = (para.style.name or "") if para.style is not None else ""
            numbering = child.find(
                ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr"
            )
            if style.startswith(("Heading", "Title", "Pealkiri")) or style in {
                "Subtitle",
                "Alapealkiri",
            }:
                flush()
                builder.add(text, HEADING)
            elif numbering is not None or style.startswith(("List", "Loend")):
                flush()
                level = 1
                ilvl = child.find(
                    ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ilvl"
                )
                if ilvl is not None:
                    raw = ilvl.get(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
                    )
                    if raw is not None and raw.isdigit():
                        level = int(raw) + 1
                builder.add(text, BULLET, list_level=level)
            elif _looks_like_heading(text):
                flush()
                builder.add(text, HEADING)
            else:
                paragraph.append(text)
        elif tag == "tbl":
            flush()
            table = Table(child, document)
            for row in table.rows:
                cells = [normalise_whitespace(c.text) for c in row.cells]
                joined = _TABLE_SEP.join(c for c in cells if c)
                builder.add(joined, TABLE_ROW)

    flush()
    return builder.segments


def segment_pdf(data: bytes) -> list[Seg]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return segment_text("\n\n".join(pages))


class UnsupportedUpload(ValueError):
    pass


def segment_upload(filename: str, data: bytes) -> list[Seg]:
    name = (filename or "").lower()
    if name.endswith(".docx"):
        return segment_docx(data)
    if name.endswith(".pdf"):
        return segment_pdf(data)
    if name.endswith(".txt"):
        return segment_text(data.decode("utf-8", errors="replace"))
    raise UnsupportedUpload("Toetatud failitüübid on .docx, .pdf ja .txt")


def extract_text(filename: str, data: bytes) -> str:
    """Plain text of an upload, for storing on the conversion."""
    return "\n".join(seg.text for seg in segment_upload(filename, data))


def numbered_text(segments: list[Seg]) -> str:
    """The MMR as handed to the model: every segment prefixed with its id and type."""
    lines = []
    for seg in segments:
        prefix = f"{seg.sid} [{seg.segment_type}]"
        lines.append(f"{prefix}: {seg.text}")
    return "\n".join(lines)
