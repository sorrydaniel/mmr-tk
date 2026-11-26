"""Schema validation: valid and invalid model output."""

from __future__ import annotations

import json

import pytest

from app.schemas import SchemaFailure, parse_rows

VALID_SIDS = {"S1", "S2", "S3"}


def row(**overrides) -> dict:
    base = {
        "category": "1. Üldine",
        "category_source": "MMR_HEADING",
        "description": "Kohver peab taluma -30 °C kuni +50 °C.",
        "classification": "M",
        "classification_signal": "peab",
        "requirement_type": "MEASURABLE",
        "verif_source": "MAPPING",
        "verif_method": None,
        "verif_stage": None,
        "verif_quote": None,
        "verif_description": "",
        "comments": "",
        "source_segments": ["S1"],
        "uncertain": False,
        "uncertain_reason": None,
    }
    base.update(overrides)
    return base


def test_valid_row_parses():
    rows = parse_rows(json.dumps([row()]), VALID_SIDS)
    assert len(rows) == 1
    assert rows[0].classification == "M"
    assert rows[0].source_segments == ["S1"]


def test_json_in_a_code_fence_is_accepted():
    payload = "```json\n" + json.dumps([row()]) + "\n```"
    assert len(parse_rows(payload, VALID_SIDS)) == 1


def test_object_wrapper_is_accepted():
    payload = json.dumps({"rows": [row()]})
    assert len(parse_rows(payload, VALID_SIDS)) == 1


def test_prose_around_the_json_is_tolerated():
    payload = "Siin on tulemus:\n" + json.dumps([row()]) + "\nLoodan, et sobib."
    assert len(parse_rows(payload, VALID_SIDS)) == 1


def test_unknown_segment_id_is_rejected():
    with pytest.raises(SchemaFailure) as exc:
        parse_rows(json.dumps([row(source_segments=["S99"])]), VALID_SIDS)
    assert "S99" in str(exc.value)


def test_malformed_segment_id_is_rejected():
    with pytest.raises(SchemaFailure):
        parse_rows(json.dumps([row(source_segments=["lause 7"])]), VALID_SIDS)


def test_empty_source_segments_is_rejected():
    with pytest.raises(SchemaFailure):
        parse_rows(json.dumps([row(source_segments=[])]), VALID_SIDS)


def test_empty_description_is_rejected():
    with pytest.raises(SchemaFailure):
        parse_rows(json.dumps([row(description="   ")]), VALID_SIDS)


def test_bad_classification_is_rejected():
    with pytest.raises(SchemaFailure):
        parse_rows(json.dumps([row(classification="X")]), VALID_SIDS)


def test_bad_verif_method_is_rejected():
    with pytest.raises(SchemaFailure):
        parse_rows(
            json.dumps(
                [row(verif_source="MMR_EXPLICIT", verif_method="Katse", verif_stage="FAFAT")]
            ),
            VALID_SIDS,
        )


def test_verif_method_matches_case_insensitively():
    rows = parse_rows(
        json.dumps(
            [
                row(
                    verif_source="MMR_EXPLICIT",
                    verif_method="test",
                    verif_stage="fafat",
                    verif_quote="tõendada katsearuandega",
                )
            ]
        ),
        VALID_SIDS,
    )
    assert rows[0].verif_method == "Test"
    assert rows[0].verif_stage == "FAFAT"


def test_uncertain_without_reason_is_rejected():
    with pytest.raises(SchemaFailure):
        parse_rows(json.dumps([row(uncertain=True, uncertain_reason=None)]), VALID_SIDS)


def test_explicit_verification_without_stage_is_rejected():
    with pytest.raises(SchemaFailure):
        parse_rows(
            json.dumps([row(verif_source="MMR_EXPLICIT", verif_method="Test")]), VALID_SIDS
        )


def test_mapping_source_discards_guessed_verification():
    # Anything the model guessed under MAPPING is dropped: the table decides.
    rows = parse_rows(
        json.dumps([row(verif_method="Test", verif_stage="FAFAT", verif_quote="x")]),
        VALID_SIDS,
    )
    assert rows[0].verif_method is None
    assert rows[0].verif_stage is None
    assert rows[0].verif_quote is None


def test_not_json_at_all_is_rejected():
    with pytest.raises(SchemaFailure):
        parse_rows("Vabandust, ma ei saa seda teha.", VALID_SIDS)


def test_empty_array_is_rejected():
    with pytest.raises(SchemaFailure):
        parse_rows("[]", VALID_SIDS)


def test_error_message_names_the_offending_row():
    payload = json.dumps([row(), row(classification="Z")])
    with pytest.raises(SchemaFailure) as exc:
        parse_rows(payload, VALID_SIDS)
    assert "rida 2" in str(exc.value)
