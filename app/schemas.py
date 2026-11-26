"""The LLM contract, validated with pydantic.

A row that references a segment id which does not exist is a hard failure: traceability
back to the MMR is the whole point, and a fabricated `S99` silently breaks it.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, ValidationInfo, field_validator, model_validator

from app.models import (
    CATEGORY_SOURCES,
    CLASSIFICATIONS,
    REQUIREMENT_TYPES,
    VERIF_METHODS,
    VERIF_SOURCES,
    VERIF_STAGES,
)

_SID_RE = re.compile(r"^S\d+$")

Classification = Literal["M", "N", "I", "OP"]
CategorySource = Literal["MMR_HEADING", "DEFAULT_LIST", "NEW"]
VerifSource = Literal["MAPPING", "MMR_EXPLICIT"]
RequirementType = Literal[
    "MEASURABLE", "DOCUMENT", "OPERABLE", "VISUAL", "DESIGN", "INFORMATIVE"
]


def _canonical(value: str, allowed: tuple[str, ...]) -> str | None:
    """Case- and whitespace-tolerant match against an allowed list."""
    needle = (value or "").strip().casefold()
    for candidate in allowed:
        if candidate.casefold() == needle:
            return candidate
    return None


class LlmRow(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    category: str = ""
    category_source: CategorySource = "NEW"
    description: str
    classification: Classification = "M"
    classification_signal: str | None = None
    requirement_type: RequirementType | None = None
    verif_source: VerifSource = "MAPPING"
    verif_method: str | None = None
    verif_stage: str | None = None
    verif_quote: str | None = None
    verif_description: str = ""
    comments: str = ""
    source_segments: list[str]
    uncertain: bool = False
    uncertain_reason: str | None = None

    @field_validator("description")
    @classmethod
    def _description_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description ei tohi olla tühi")
        return value.strip()

    @field_validator("verif_method")
    @classmethod
    def _method_allowed(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        canonical = _canonical(value, VERIF_METHODS)
        if canonical is None:
            raise ValueError(f"verif_method '{value}' ei ole lubatud; lubatud: {', '.join(VERIF_METHODS)}")
        return canonical

    @field_validator("verif_stage")
    @classmethod
    def _stage_allowed(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        canonical = _canonical(value, VERIF_STAGES)
        if canonical is None:
            raise ValueError(f"verif_stage '{value}' ei ole lubatud; lubatud: {', '.join(VERIF_STAGES)}")
        return canonical

    @field_validator("source_segments", mode="before")
    @classmethod
    def _coerce_segments(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in re.split(r"[,\s]+", value) if part.strip()]
        return value

    @field_validator("source_segments")
    @classmethod
    def _segments_well_formed(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("source_segments ei tohi olla tühi")
        cleaned = []
        for sid in value:
            sid = str(sid).strip().upper()
            if not _SID_RE.match(sid):
                raise ValueError(f"source_segments sisaldab vigast ID-d: '{sid}'")
            cleaned.append(sid)
        return cleaned

    @model_validator(mode="after")
    def _cross_field(self, info: ValidationInfo) -> "LlmRow":
        if self.uncertain and not (self.uncertain_reason or "").strip():
            raise ValueError("uncertain = true nõuab uncertain_reason'i")
        if not self.uncertain:
            self.uncertain_reason = None

        if self.verif_source == "MMR_EXPLICIT":
            if not self.verif_method or not self.verif_stage:
                raise ValueError(
                    "verif_source = MMR_EXPLICIT nõuab nii verif_method'i kui verif_stage'i"
                )
        else:
            # Verification comes from the mapping table; anything the model guessed here
            # is discarded rather than silently kept.
            self.verif_method = None
            self.verif_stage = None
            self.verif_quote = None

        context = info.context or {}
        valid_sids = context.get("valid_sids")
        if valid_sids is not None:
            unknown = [sid for sid in self.source_segments if sid not in valid_sids]
            if unknown:
                raise ValueError(
                    "source_segments viitab olematutele lõikudele: " + ", ".join(unknown)
                )
        return self


class SchemaFailure(ValueError):
    """Carries a message that is fed straight back to the model on the single retry."""


def extract_json_payload(text: str) -> Any:
    """Pull the JSON out of a model response that may be fenced or wrapped."""
    raw = (text or "").strip()
    if not raw:
        raise SchemaFailure("Mudel ei tagastanud midagi.")

    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S)
    if fenced:
        raw = fenced.group(1).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost array or object in the text.
    for opener, closer in (("[", "]"), ("{", "}")):
        start = raw.find(opener)
        end = raw.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise SchemaFailure("Vastus ei olnud korrektne JSON.")


def rows_from_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("rows", "requirements", "nouded", "read", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
        raise SchemaFailure(
            "JSON oli objekt, mitte massiiv. Oodatud on massiiv nõuete objektidest."
        )
    raise SchemaFailure("JSON ei olnud massiiv.")


def format_validation_error(error: ValidationError) -> str:
    parts = []
    for item in error.errors():
        location = ".".join(str(piece) for piece in item.get("loc", ()))
        parts.append(f"rida {location or '?'}: {item.get('msg', 'viga')}")
    return "; ".join(parts[:12])


def parse_rows(text: str, valid_sids: set[str] | None = None) -> list[LlmRow]:
    """Parse and validate a model response. Raises SchemaFailure with a readable message."""
    payload = extract_json_payload(text)
    raw_rows = rows_from_payload(payload)
    if not raw_rows:
        raise SchemaFailure("Mudel tagastas tühja nõuete massiivi.")

    context = {"valid_sids": valid_sids} if valid_sids is not None else {}
    rows: list[LlmRow] = []
    errors: list[str] = []
    for index, raw in enumerate(raw_rows):
        try:
            rows.append(LlmRow.model_validate(raw, context=context))
        except ValidationError as exc:
            errors.append(f"rida {index + 1}: {format_validation_error(exc)}")
        except TypeError:
            errors.append(f"rida {index + 1}: oodatud objekt, saadi {type(raw).__name__}")

    if errors:
        raise SchemaFailure("; ".join(errors[:12]))
    return rows


__all__ = [
    "LlmRow",
    "SchemaFailure",
    "parse_rows",
    "extract_json_payload",
    "rows_from_payload",
    "CLASSIFICATIONS",
    "CATEGORY_SOURCES",
    "REQUIREMENT_TYPES",
    "VERIF_METHODS",
    "VERIF_SOURCES",
    "VERIF_STAGES",
]
