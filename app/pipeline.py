"""Turning validated model rows into stored requirements.

Three things happen here that the model is deliberately not trusted with: the category
source is verified against the MMR's actual headings, verification is filled from the
mapping table, and the rows are put into RKIK order. The immutable snapshot is written at
the same time -- it is the accuracy source for the study, so it must be created before the
engineer can touch anything.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import settings_store
from app.categories import (
    classify_source,
    first_category,
    heading_categories,
    normalise_key,
)
from app.classification import UNCERTAIN_CLASSIFICATION_REASON, backfill_signal
from app.models import DIFFABLE_FIELDS, Conversion, Requirement, RequirementSnapshot
from app.ordering import order_rows, renumber
from app.schemas import LlmRow
from app.segmentation import HEADING, Seg
from app.verification import resolve

_SNAPSHOT_FIELDS = (
    "category",
    "category_source",
    "description",
    "classification",
    "classification_signal",
    "requirement_type",
    "verif_with_bid",
    "verif_method",
    "verif_stage",
    "verif_source",
    "verif_quote",
    "verif_description",
    "comments",
    "source_segments",
    "uncertain",
    "uncertain_reason",
)


def heading_lookup(segments: list[Seg]) -> dict[str, str]:
    """sid -> the heading it sits under, so a row can inherit its category."""
    lookup: dict[str, str] = {}
    current = ""
    for seg in segments:
        if seg.segment_type == HEADING:
            current = seg.text.strip()
            continue
        lookup[seg.sid] = current
    return lookup


def _resolved_category(
    row: LlmRow, lookup: dict[str, str], headings: list[str], default_list: list[str]
) -> str:
    if (row.category or "").strip():
        return row.category.strip()
    for sid in row.source_segments:
        inherited = lookup.get(sid, "")
        if inherited:
            return inherited
    return first_category(headings, default_list)


def build_requirements(
    session: Session,
    conversion: Conversion,
    segments: list[Seg],
    rows: list[LlmRow],
    *,
    run_id: int | None = None,
) -> list[Requirement]:
    """Create Requirement rows and their immutable snapshots, in TK order."""
    headings = heading_categories(segments)
    lookup = heading_lookup(segments)
    default_list = settings_store.get_json(session, settings_store.DEFAULT_CATEGORIES) or []
    mapping = settings_store.get_json(session, settings_store.VERIF_MAPPING)
    profile = conversion.procurement_profile or "COTS"

    prepared: list[Requirement] = []
    for row in rows:
        category = _resolved_category(row, lookup, headings, default_list)
        signal = row.classification_signal or backfill_signal(row.classification, row.description)

        verification = resolve(
            mapping=mapping,
            profile=profile,
            requirement_type=row.requirement_type,
            classification=row.classification,
            explicit_method=row.verif_method,
            explicit_stage=row.verif_stage,
            explicit_quote=row.verif_quote,
        )

        uncertain = row.uncertain
        reason = row.uncertain_reason
        if uncertain and not reason:
            reason = UNCERTAIN_CLASSIFICATION_REASON

        prepared.append(
            Requirement(
                conversion_id=conversion.id,
                category=category,
                category_source=classify_source(category, headings, default_list),
                description=row.description,
                classification=row.classification,
                classification_signal=signal,
                requirement_type=row.requirement_type,
                verif_with_bid=verification.with_bid,
                verif_method=verification.method,
                verif_stage=verification.stage,
                verif_source=verification.source,
                verif_quote=verification.quote,
                verif_description=row.verif_description or "",
                comments=row.comments or "",
                source_segments=list(row.source_segments),
                uncertain=uncertain,
                uncertain_reason=reason,
            )
        )

    ordered = order_rows(prepared, headings)
    renumber(ordered)
    for requirement in ordered:
        session.add(requirement)
    session.flush()

    for requirement in ordered:
        payload = {name: getattr(requirement, name) for name in _SNAPSHOT_FIELDS}
        if isinstance(payload.get("source_segments"), list):
            payload["source_segments"] = list(payload["source_segments"])
        session.add(
            RequirementSnapshot(
                requirement_id=requirement.id,
                conversion_id=conversion.id,
                run_id=run_id,
                order=requirement.order,
                **payload,
            )
        )
    session.flush()
    return ordered


# --- diff -------------------------------------------------------------------------------


def _normalise_for_diff(value) -> str:
    """Whitespace-only and capitalisation-only edits are not changes."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ",".join(str(v).strip() for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return " ".join(str(value).split()).casefold()


def changed_fields(requirement: Requirement) -> list[str]:
    snapshot = requirement.snapshot
    if snapshot is None:
        return []
    out = []
    for name in DIFFABLE_FIELDS:
        if _normalise_for_diff(getattr(requirement, name)) != _normalise_for_diff(
            getattr(snapshot, name)
        ):
            out.append(name)
    return out


def category_changed(requirement: Requirement) -> bool:
    snapshot = requirement.snapshot
    if snapshot is None:
        return False
    return normalise_key(requirement.category) != normalise_key(snapshot.category)
