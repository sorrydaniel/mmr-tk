"""Classification signals, the verification mapping table, and row ordering."""

from __future__ import annotations

import pytest

from app.classification import detect
from app.ordering import order_rows
from app.verification import resolve


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Kohver peab taluma lööke.", "M"),
        ("Kohvril tuleb olema rõhuklapp.", "M"),
        ("Rõhuklapi olemasolu on kohustuslik.", "M"),
        # No modal at all is still mandatory, per RKIK practice.
        ("Kohvri värv on oliivroheline.", "M"),
        ("Kohver peaks olema kerge.", "N"),
        ("Kohver on võimalusel varustatud ratastega.", "N"),
        ("Eelistatavalt kasutatakse polümeeri.", "N"),
        ("Ratastega alust pakutakse optsioonina.", "OP"),
        ("Valikuliselt lisatakse õlarihm.", "OP"),
        ("Käesoleva dokumendi eesmärk on kirjeldada kohvri nõudeid.", "I"),
    ],
)
def test_classification_signals(text, expected):
    classification, _signal, _ambiguous = detect(text)
    assert classification == expected


def test_signal_word_is_reported():
    _classification, signal, _ambiguous = detect("Kohver peaks olema kerge.")
    assert signal == "peaks"


def test_contradictory_modals_stay_mandatory_and_flag_ambiguity():
    classification, _signal, ambiguous = detect(
        "Kohver peab võimalusel olema varustatud ratastega."
    )
    assert classification == "M"
    assert ambiguous is True


def test_mapping_fills_method_and_stage_for_cots():
    result = resolve(
        mapping=None,
        profile="COTS",
        requirement_type="MEASURABLE",
        classification="M",
    )
    assert result.method == "Test"
    assert result.stage == "SAT kõik"
    assert result.with_bid == "jah, sertifikaat"
    assert result.source == "MAPPING"


def test_profile_changes_the_stage():
    cots = resolve(mapping=None, profile="COTS", requirement_type="MEASURABLE", classification="M")
    arendus = resolve(
        mapping=None, profile="ARENDUS", requirement_type="MEASURABLE", classification="M"
    )
    assert cots.stage != arendus.stage
    assert arendus.stage == "FAFAT"


def test_non_mandatory_rows_are_not_verified_with_the_bid():
    result = resolve(
        mapping=None, profile="COTS", requirement_type="MEASURABLE", classification="N"
    )
    assert result.with_bid == "ei"


def test_informative_rows_are_not_verified():
    result = resolve(
        mapping=None, profile="COTS", requirement_type="INFORMATIVE", classification="I"
    )
    assert (result.method, result.stage, result.with_bid) == ("N/A", "N/A", "ei")


def test_explicit_verification_overrides_the_mapping():
    result = resolve(
        mapping=None,
        profile="COTS",
        requirement_type="MEASURABLE",
        classification="M",
        explicit_method="Sertifikaat",
        explicit_stage="Lepingu sõlmimine",
        explicit_quote="tõendada katsearuandega",
    )
    assert result.source == "MMR_EXPLICIT"
    assert result.method == "Sertifikaat"
    assert result.quote == "tõendada katsearuandega"


def test_unknown_requirement_type_falls_back_to_not_applicable():
    result = resolve(mapping=None, profile="COTS", requirement_type=None, classification="M")
    assert (result.method, result.stage) == ("N/A", "N/A")


class Row:
    def __init__(self, classification, category):
        self.classification = classification
        self.category = category
        self.order = 0

    def __repr__(self) -> str:  # pragma: no cover - test output only
        return f"Row({self.classification}, {self.category})"


def test_informative_rows_form_one_block_at_the_very_start():
    rows = [
        Row("M", "2. Kaitse"),
        Row("I", "2. Kaitse"),
        Row("M", "1. Üldine"),
        Row("I", "1. Üldine"),
    ]
    ordered = order_rows(rows, ["1. Üldine", "2. Kaitse"])
    assert [r.classification for r in ordered[:2]] == ["I", "I"]


def test_categories_follow_mmr_heading_order_not_alphabetical():
    rows = [Row("M", "2. Kaitse"), Row("M", "1. Üldine")]
    ordered = order_rows(rows, ["1. Üldine", "2. Kaitse"])
    assert [r.category for r in ordered] == ["1. Üldine", "2. Kaitse"]


def test_numbering_differences_do_not_split_a_category():
    rows = [Row("M", "3. Kaitse"), Row("M", "1. Üldine"), Row("M", "Kaitse")]
    ordered = order_rows(rows, ["1. Üldine", "3. Kaitse"])
    assert [r.category for r in ordered] == ["1. Üldine", "3. Kaitse", "Kaitse"]


def test_unknown_categories_sort_last_and_keep_original_order():
    rows = [Row("M", "Muu"), Row("M", "1. Üldine"), Row("M", "Veel muu")]
    ordered = order_rows(rows, ["1. Üldine"])
    assert [r.category for r in ordered] == ["1. Üldine", "Muu", "Veel muu"]
