"""The mock converter.

Used whenever ANTHROPIC_API_KEY is absent, and by every test. It exercises the whole
pipeline -- segmentation, classification signals, the verification mapping, ordering,
export -- without a network call or a key, which is what makes the test suite runnable
anywhere.

Every row it produces is marked uncertain: a mock draft must never be mistaken for a
model draft in the research data.
"""

from __future__ import annotations

import time

from app.classification import detect
from app.converter.base import ConverterResult
from app.schemas import LlmRow
from app.segmentation import HEADING, Seg

MOCK_DELAY_SECONDS = 1.5
MOCK_REASON = "Mock-režiim: rida on genereeritud ilma mudelita, sisu ei ole kontrollitud."

_TYPE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("DOCUMENT", ("standard", "normatiiv", "direktiiv", "sertifikaat", "dokument", "juhend", "mil-std")),
    ("MEASURABLE", ("mm", "cm", "kg", "°c", "temperatuur", "mass", "mõõt", "vibratsioon", "löögi", "ip")),
    ("VISUAL", ("värv", "märgis", "tähist", "silt", "komplekt")),
    ("OPERABLE", ("mahu", "sisaldama", "avan", "käsitse", "kanda", "paigald", "sobi")),
    ("DESIGN", ("projekteer", "disain", "analüüs")),
)


def _requirement_type(text: str, classification: str) -> str:
    if classification == "I":
        return "INFORMATIVE"
    lowered = text.casefold()
    for requirement_type, hints in _TYPE_HINTS:
        if any(hint in lowered for hint in hints):
            return requirement_type
    return "OPERABLE"


def convert(
    segments: list[Seg],
    *,
    heading_lookup: dict[str, str] | None = None,
    delay: float = MOCK_DELAY_SECONDS,
) -> ConverterResult:
    """One row per non-heading segment, all flagged uncertain."""
    if delay:
        time.sleep(delay)

    lookup = heading_lookup or {}
    rows: list[LlmRow] = []
    for seg in segments:
        if seg.segment_type == HEADING:
            continue
        classification, signal, ambiguous = detect(seg.text)
        reason = MOCK_REASON
        if ambiguous:
            reason = f"{MOCK_REASON} Klassifikatsioon ebaselge."
        rows.append(
            LlmRow(
                category=lookup.get(seg.sid, ""),
                category_source="MMR_HEADING" if lookup.get(seg.sid) else "NEW",
                description=seg.text,
                classification=classification,
                classification_signal=signal,
                requirement_type=_requirement_type(seg.text, classification),
                verif_source="MAPPING",
                source_segments=[seg.sid],
                uncertain=True,
                uncertain_reason=reason,
            )
        )

    return ConverterResult(
        rows=rows,
        model="mock",
        input_tokens=0,
        output_tokens=0,
        processing_seconds=delay,
        retry_used=False,
        mock=True,
        raw_text="",
    )
