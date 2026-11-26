"""Segmentation, including the Estonian cases a naive full-stop split gets wrong."""

from __future__ import annotations

import pytest

from app.segmentation import (
    BULLET,
    HEADING,
    SENTENCE,
    TABLE_ROW,
    numbered_text,
    segment_text,
    split_sentences,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        # Abbreviations must not end a sentence.
        ("Kohver peab taluma min. 5 lööki.", 1),
        ("Kasutatakse nt. kaablit, jne. Lõpp.", 1),
        ("Mõõdud on suured, sh. kõrgus.", 1),
        # "Vt." is an abbreviation, but "3." here genuinely ends a sentence.
        ("Vt. lisa 3. Kohver on suur.", 2),
        # A number mid-sentence must still be able to end one.
        ("Kohver kaalub 12. Mass on kriitiline.", 2),
        # Real boundaries still split.
        ("Kohver peab olema tugev. Kohver peab olema kerge.", 2),
        ("Esimene lause! Teine lause? Kolmas lause.", 3),
    ],
)
def test_sentence_counts(text, expected):
    assert len(split_sentences(text)) == expected


def test_never_splits_inside_numbers():
    assert split_sentences("Mõõtmed on 1,5 m ja 2.5 m kokku.") == [
        "Mõõtmed on 1,5 m ja 2.5 m kokku."
    ]


def test_never_splits_after_digit_period_at_line_start():
    # "1." is list numbering, not the end of a sentence.
    assert split_sentences("1. Üldine nõue kehtib.") == ["1. Üldine nõue kehtib."]


def test_handles_degree_and_plusminus_without_splitting():
    text = "Temperatuurivahemik on -30 °C kuni +50 °C ja täpsus ± 2 °C."
    assert split_sentences(text) == [text]


def test_numbered_heading_is_a_heading():
    segments = segment_text("1. Üldine\nKohver peab olema tugev.")
    assert [s.segment_type for s in segments] == [HEADING, SENTENCE]
    assert segments[0].text == "1. Üldine"


def test_colon_line_is_not_a_heading():
    # "Kohver peab sisaldama:" introduces a list; it is a requirement stem.
    segments = segment_text("Kohver peab sisaldama:\n- vahtplast\n- klapp")
    assert segments[0].segment_type == SENTENCE
    assert [s.segment_type for s in segments[1:]] == [BULLET, BULLET]


def test_bullets_keep_level_and_lose_their_marker():
    segments = segment_text("- esimene\n  - teine")
    assert all(s.segment_type == BULLET for s in segments)
    assert segments[0].text == "esimene"
    assert segments[1].list_level > segments[0].list_level


def test_table_rows_join_cells_with_pipe():
    segments = segment_text("Mõõt | Nõue | Ühik")
    assert len(segments) == 1
    assert segments[0].segment_type == TABLE_ROW
    assert segments[0].text == "Mõõt | Nõue | Ühik"


def test_ids_are_sequential_and_unique():
    segments = segment_text("1. Üldine\nAaa. Bbb.\n- ccc")
    assert [s.sid for s in segments] == [f"S{i}" for i in range(1, len(segments) + 1)]
    assert len({s.sid for s in segments}) == len(segments)


def test_wrapped_paragraph_lines_are_joined_before_splitting():
    # A PDF wraps mid-sentence; that must not become two segments.
    segments = segment_text("Kohver peab olema\nvalmistatud polümeerist.")
    assert len(segments) == 1
    assert segments[0].text == "Kohver peab olema valmistatud polümeerist."


def test_numbered_text_includes_ids_and_types():
    segments = segment_text("1. Üldine\nKohver peab olema tugev.")
    rendered = numbered_text(segments)
    assert "S1 [HEADING]: 1. Üldine" in rendered
    assert "S2 [SENTENCE]: Kohver peab olema tugev." in rendered


def test_sample_mmr_contains_every_hard_case():
    from app.seed import SAMPLE_MMR_TEXT

    segments = segment_text(SAMPLE_MMR_TEXT)
    types = [s.segment_type for s in segments]

    assert types.count(HEADING) == 2
    assert BULLET in types
    assert TABLE_ROW in types
    # A requirement above the first heading, so the default category list gets exercised.
    assert types[0] == SENTENCE
    text = " ".join(s.text for s in segments)
    assert "piisavalt vastupidav" in text  # vague
    assert "peaks" in text  # N signal
    assert "optsioonina" in text  # OP signal
    assert "katsearuandega" in text  # explicit verification
    assert "dokumendi eesmärk" in text  # informative intent


def test_empty_text_yields_nothing():
    assert segment_text("") == []
    assert segment_text("   \n\n  ") == []
