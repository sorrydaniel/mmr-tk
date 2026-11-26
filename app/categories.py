"""Category resolution and normalisation.

Categories come from the MMR's own headings wherever possible. The normalised key exists
only for ordering and matching -- the original string is always what is displayed and
exported, because the delivered TK must use the Defence Forces' own wording.
"""

from __future__ import annotations

import re

from app.segmentation import HEADING, Seg

_LEADING_NUMBER_RE = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s*")

MMR_HEADING = "MMR_HEADING"
DEFAULT_LIST = "DEFAULT_LIST"
NEW = "NEW"

FALLBACK_CATEGORY = "Üldine"


def normalise_key(category: str) -> str:
    """`3. Kaitse` and `kaitse` must match; `Kaitse` is still what gets exported."""
    text = (category or "").replace(" ", " ").strip()
    text = _LEADING_NUMBER_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def heading_categories(segments: list[Seg]) -> list[str]:
    """Heading texts in order of first appearance, de-duplicated by normalised key."""
    seen: set[str] = set()
    out: list[str] = []
    for seg in segments:
        if seg.segment_type != HEADING:
            continue
        key = normalise_key(seg.text)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(seg.text.strip())
    return out


def classify_source(category: str, headings: list[str], default_list: list[str]) -> str:
    """What the category actually is, regardless of what the model claimed it was."""
    key = normalise_key(category)
    if not key:
        return NEW
    if key in {normalise_key(h) for h in headings}:
        return MMR_HEADING
    if key in {normalise_key(d) for d in default_list}:
        return DEFAULT_LIST
    return NEW


def first_category(headings: list[str], default_list: list[str]) -> str:
    """Where the informative block goes: the MMR's own introductory heading if it has one."""
    if headings:
        return headings[0]
    if default_list:
        return default_list[0]
    return FALLBACK_CATEGORY


def category_order(categories: list[str], headings: list[str]) -> dict[str, int]:
    """Index per normalised key: MMR heading order first, then first appearance."""
    order: dict[str, int] = {}
    for heading in headings:
        key = normalise_key(heading)
        if key and key not in order:
            order[key] = len(order)
    for category in categories:
        key = normalise_key(category)
        if key and key not in order:
            order[key] = len(order)
    return order
