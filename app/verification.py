"""Verification columns D, E and F.

The model does not choose how a requirement is verified -- that is RKIK house practice,
not MMR content, and letting the model guess produced inconsistency across rows, which is
worse than being wrong because it cannot be measured. The model names the requirement
type; this table decides the rest, keyed by (requirement_type, procurement_profile).

The only exception is an MMR that states the verification explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.settings_store import DEFAULT_VERIF_MAPPING

NOT_APPLICABLE = "N/A"
NO_BID_VERIFICATION = "ei"


@dataclass(frozen=True)
class Verification:
    with_bid: str
    method: str
    stage: str
    source: str  # MAPPING | MMR_EXPLICIT
    quote: str | None = None


def _entry(
    mapping: dict | None, profile: str, requirement_type: str | None
) -> dict[str, str] | None:
    table = mapping or DEFAULT_VERIF_MAPPING
    by_profile = table.get(profile) or table.get("COTS") or {}
    if requirement_type and requirement_type in by_profile:
        return by_profile[requirement_type]
    return None


def resolve(
    *,
    mapping: dict | None,
    profile: str,
    requirement_type: str | None,
    classification: str,
    explicit_method: str | None = None,
    explicit_stage: str | None = None,
    explicit_quote: str | None = None,
) -> Verification:
    """Fill D/E/F for one row."""
    if explicit_method and explicit_stage:
        with_bid = NO_BID_VERIFICATION
        entry = _entry(mapping, profile, requirement_type)
        if entry and classification == "M":
            with_bid = entry.get("with_bid", NO_BID_VERIFICATION)
        return Verification(
            with_bid=with_bid,
            method=explicit_method,
            stage=explicit_stage,
            source="MMR_EXPLICIT",
            quote=explicit_quote,
        )

    if classification == "I":
        return Verification(
            with_bid=NO_BID_VERIFICATION,
            method=NOT_APPLICABLE,
            stage=NOT_APPLICABLE,
            source="MAPPING",
        )

    entry = _entry(mapping, profile, requirement_type)
    if entry is None:
        return Verification(
            with_bid=NO_BID_VERIFICATION,
            method=NOT_APPLICABLE,
            stage=NOT_APPLICABLE,
            source="MAPPING",
        )

    # verif_with_bid is only requested for mandatory rows; negotiable rows and
    # directives are confirmed later, not with the bid.
    with_bid = (
        entry.get("with_bid", NO_BID_VERIFICATION)
        if classification == "M"
        else NO_BID_VERIFICATION
    )
    return Verification(
        with_bid=with_bid,
        method=entry.get("method", NOT_APPLICABLE),
        stage=entry.get("stage", NOT_APPLICABLE),
        source="MAPPING",
    )
