"""Settings live in the database so they can be tuned without a redeploy.

Defaults are seeded on first run. Anything the engineer is expected to tune -- the
verification mapping, the classification fill colours, the missing-aspect stems -- is a
setting, not a constant in code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DEFAULT_MODEL, get_config
from app.models import Setting

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.md"

# --- keys -------------------------------------------------------------------------------

MODEL = "model"
TEMPERATURE = "temperature"
SYSTEM_PROMPT = "system_prompt"
DEFAULT_CATEGORIES = "default_categories"
VERIF_MAPPING = "verif_mapping"
CLASS_FILL_M = "class_fill_M"
CLASS_FILL_N = "class_fill_N"
CLASS_FILL_I = "class_fill_I"
CLASS_FILL_OP = "class_fill_OP"
UNCERTAIN_FILL = "uncertain_fill"
MISSING_ASPECTS = "missing_aspects"
HINDA_SHOW_HINTS = "hinda_show_hints"
GROUP_ROW_LABEL = "group_row_label"

# --- defaults ---------------------------------------------------------------------------

DEFAULT_CATEGORY_LIST = [
    "Üldine",
    "Mahutavus/Jõudlus",
    "Kaitse/Keskkond",
    "Liidesed",
    "Toide",
    "Logistika",
    "Koolitus ja dokumentatsioon",
    "Direktiivid ja standardid",
]

# Verification is RKIK house practice, not MMR content: the model classifies the
# requirement type and this table decides how it is verified.
# with_bid applies to M rows; everything else gets "ei".
_COTS = {
    "MEASURABLE": {"method": "Test", "stage": "SAT kõik", "with_bid": "jah, sertifikaat"},
    "DOCUMENT": {"method": "Sertifikaat", "stage": "Lepingu sõlmimine", "with_bid": "ei"},
    "OPERABLE": {
        "method": "Funktsionaalne demonstratsioon",
        "stage": "SAT kõik",
        "with_bid": "jah, sertifikaat",
    },
    "VISUAL": {
        "method": "Funktsionaalne kontroll",
        "stage": "SAT kõik",
        "with_bid": "jah, sertifikaat",
    },
    "DESIGN": {"method": "Analüüs", "stage": "Lepingu täitmine", "with_bid": "jah, sertifikaat"},
    "INFORMATIVE": {"method": "N/A", "stage": "N/A", "with_bid": "ei"},
}

_ARENDUS = {
    "MEASURABLE": {"method": "Test", "stage": "FAFAT", "with_bid": "jah, sertifikaat"},
    "DOCUMENT": {"method": "Sertifikaat", "stage": "Lepingu sõlmimine", "with_bid": "ei"},
    "OPERABLE": {
        "method": "Funktsionaalne demonstratsioon",
        "stage": "FAFAT",
        "with_bid": "jah, sertifikaat",
    },
    "VISUAL": {
        "method": "Funktsionaalne kontroll",
        "stage": "FAFAT",
        "with_bid": "jah, sertifikaat",
    },
    "DESIGN": {"method": "Analüüs", "stage": "Disainietapid", "with_bid": "jah, sertifikaat"},
    "INFORMATIVE": {"method": "N/A", "stage": "N/A", "with_bid": "ei"},
}

DEFAULT_VERIF_MAPPING: dict[str, dict[str, dict[str, str]]] = {
    "COTS": _COTS,
    "MOTS": dict(_COTS),  # same as COTS until told otherwise
    "ARENDUS": _ARENDUS,
}

# Estonian is heavily inflected, so these are stems, matched as substrings.
DEFAULT_MISSING_ASPECTS: dict[str, list[str]] = {
    "Garantii": ["garantii"],
    "Koolitus": ["koolit", "väljaõp"],
    "Hooldus": ["hooldu"],
    "Dokumentatsioon": ["dokumentatsioon", "käsiraamat", "juhend"],
    "Varuosad": ["varuosa"],
    "Märgistus": ["tähist", "markeer", "silt", "märgis"],
    "Pakend ja transport": ["pakend", "pakk"],
    "Paigaldus": ["paigald"],
    "Tarne": ["tarn"],
}

# From the real template. M and I are read off the reference TK; N and OP are unknown
# until a filled TK is opened, so they stay empty and simply paint nothing.
DEFAULTS: dict[str, str] = {
    MODEL: DEFAULT_MODEL,
    TEMPERATURE: "0.2",
    DEFAULT_CATEGORIES: json.dumps(DEFAULT_CATEGORY_LIST, ensure_ascii=False),
    VERIF_MAPPING: json.dumps(DEFAULT_VERIF_MAPPING, ensure_ascii=False),
    CLASS_FILL_M: "FF00B0F0",
    CLASS_FILL_N: "",
    CLASS_FILL_I: "FFFFE699",
    CLASS_FILL_OP: "",
    UNCERTAIN_FILL: "FFE4DFEC",
    MISSING_ASPECTS: json.dumps(DEFAULT_MISSING_ASPECTS, ensure_ascii=False),
    HINDA_SHOW_HINTS: "true",
    GROUP_ROW_LABEL: "",
}


@lru_cache(maxsize=1)
def default_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return "Sa oled RKIK tehnilise kirjelduse koostaja. Vasta ainult JSON-iga."


def all_defaults() -> dict[str, str]:
    out = dict(DEFAULTS)
    out[SYSTEM_PROMPT] = default_system_prompt()
    out[MODEL] = get_config().anthropic_model or DEFAULT_MODEL
    return out


# --- access -----------------------------------------------------------------------------


def get(session: Session, key: str) -> str:
    row = session.get(Setting, key)
    if row is not None:
        return row.value
    return all_defaults().get(key, "")


def get_json(session: Session, key: str) -> Any:
    raw = get(session, key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fallback = all_defaults().get(key, "")
        return json.loads(fallback) if fallback else None


def set_value(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value


def set_json(session: Session, key: str, value: Any) -> None:
    set_value(session, key, json.dumps(value, ensure_ascii=False))


def get_all(session: Session) -> dict[str, str]:
    stored = {s.key: s.value for s in session.scalars(select(Setting))}
    merged = all_defaults()
    merged.update(stored)
    return merged


def temperature(session: Session) -> float:
    try:
        value = float(get(session, TEMPERATURE))
    except (TypeError, ValueError):
        return 0.2
    return min(1.0, max(0.0, value))


def class_fill(session: Session, classification: str) -> str:
    key = {
        "M": CLASS_FILL_M,
        "N": CLASS_FILL_N,
        "I": CLASS_FILL_I,
        "OP": CLASS_FILL_OP,
    }.get(classification, "")
    return get(session, key).strip() if key else ""


def seed_defaults(session: Session) -> int:
    """Insert any missing default setting. Never overwrites a stored value."""
    existing = {s.key for s in session.scalars(select(Setting))}
    added = 0
    for key, value in all_defaults().items():
        if key not in existing:
            session.add(Setting(key=key, value=value))
            added += 1
    return added
