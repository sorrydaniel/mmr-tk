"""The mock converter, the stored pipeline and the raw-vs-final diff."""

from __future__ import annotations

from app import runner
from app.converter import mock
from app.models import Conversion, Requirement, RequirementSnapshot, Run
from app.pipeline import build_requirements, changed_fields, heading_lookup
from app.seed import SAMPLE_MMR_TEXT
from app.segmentation import HEADING, segment_text


def test_mock_skips_headings_and_flags_everything_uncertain():
    segments = segment_text(SAMPLE_MMR_TEXT)
    result = mock.convert(segments, heading_lookup=heading_lookup(segments), delay=0)

    assert result.mock is True
    assert result.model == "mock"
    assert len(result.rows) == len([s for s in segments if s.segment_type != HEADING])
    assert all(row.uncertain for row in result.rows)
    assert all(row.uncertain_reason for row in result.rows)


def test_mock_rows_point_back_at_one_segment_each():
    segments = segment_text(SAMPLE_MMR_TEXT)
    valid = {s.sid for s in segments}
    result = mock.convert(segments, delay=0)
    for row in result.rows:
        assert len(row.source_segments) == 1
        assert row.source_segments[0] in valid


def test_heading_lookup_assigns_the_heading_above_each_segment():
    segments = segment_text("1. Üldine\nAaa.\n2. Kaitse\nBbb.")
    lookup = heading_lookup(segments)
    assert lookup["S2"] == "1. Üldine"
    assert lookup["S4"] == "2. Kaitse"


def test_segment_above_the_first_heading_has_no_category_to_inherit():
    segments = segment_text("Aaa.\n1. Üldine\nBbb.")
    lookup = heading_lookup(segments)
    assert lookup["S1"] == ""


def _row_by_segment(conversion, sid: str):
    return next(r for r in conversion.requirements if sid in r.source_segments)


def test_requirement_above_the_first_heading_comes_from_the_default_list(seeded):
    """It must not quietly borrow the heading below it.

    S1 sits above "1. Üldine", so the MMR assigned it no category at all. Reporting
    MMR_HEADING there would make the research field claim a provenance the MMR never
    had - and it made category_source a constant across the whole sample.
    """
    session = seeded
    conversion, _ = _run(session)
    row = _row_by_segment(conversion, "S1")
    assert row.category_source == "DEFAULT_LIST"


def test_default_category_borrows_the_mmr_wording_when_it_means_the_same(seeded):
    """"Üldine" and a "1. Üldine" heading are one category, so column A shows one
    spelling - while the provenance still records the default list."""
    session = seeded
    conversion, _ = _run(session)
    row = _row_by_segment(conversion, "S1")
    assert row.category == "1. Üldine"
    assert row.category_source == "DEFAULT_LIST"


def test_rows_under_a_heading_are_tagged_as_coming_from_the_mmr(seeded):
    session = seeded
    conversion, _ = _run(session)
    assert _row_by_segment(conversion, "S10").category == "2. Kaitse ja keskkond"
    assert _row_by_segment(conversion, "S10").category_source == "MMR_HEADING"


def test_category_source_is_not_a_constant_across_the_sample(seeded):
    """The fixture exists to exercise both paths; if it only ever produces one value
    the field is useless as research data."""
    session = seeded
    conversion, _ = _run(session)
    assert len({r.category_source for r in conversion.requirements}) > 1


def _run(session) -> tuple[Conversion, Run]:
    conversion = Conversion(
        title="Test", mmr_id="mmr_test", mmr_text=SAMPLE_MMR_TEXT, procurement_profile="COTS"
    )
    session.add(conversion)
    session.flush()
    run = runner.queue_run(session, conversion)
    session.commit()
    runner.run_sync(run.id, mock_delay=0)
    session.expire_all()
    return session.get(Conversion, conversion.id), session.get(Run, run.id)


def test_full_run_stores_requirements_segments_and_metrics(seeded):
    session = seeded
    conversion, run = _run(session)

    assert run.status == "done"
    assert run.schema_valid is True
    assert run.mock is True
    assert run.rows_generated > 0
    assert run.uncertain_rows == run.rows_generated  # the mock flags every row
    assert conversion.status == "converted"
    assert len(conversion.segments) == len(segment_text(SAMPLE_MMR_TEXT))


def test_every_requirement_gets_an_immutable_snapshot(seeded):
    session = seeded
    conversion, _run_row = _run(session)
    requirements = conversion.requirements
    snapshots = session.query(RequirementSnapshot).all()

    assert len(snapshots) == len(requirements)
    for requirement in requirements:
        assert requirement.snapshot is not None
        assert requirement.snapshot.description == requirement.description


def test_informative_block_comes_first_in_the_stored_order(seeded):
    session = seeded
    conversion, _ = _run(session)
    classifications = [r.classification for r in conversion.requirements]
    if "I" in classifications:
        assert classifications[0] == "I"
        assert "I" not in classifications[classifications.index("M") :]


def test_verification_is_filled_from_the_mapping_not_by_the_model(seeded):
    session = seeded
    conversion, _ = _run(session)
    for requirement in conversion.requirements:
        assert requirement.verif_method
        assert requirement.verif_stage
        assert requirement.verif_source in ("MAPPING", "MMR_EXPLICIT")


def test_diff_ignores_whitespace_and_capitalisation_only_edits(seeded):
    session = seeded
    conversion, _ = _run(session)
    requirement = conversion.requirements[0]
    original = requirement.description

    requirement.description = "  " + original.upper() + "  "
    session.flush()
    assert changed_fields(requirement) == []

    requirement.description = original + " Lisatud nõue."
    session.flush()
    assert "description" in changed_fields(requirement)


def test_rerun_replaces_the_draft_but_keeps_the_run_log(seeded):
    session = seeded
    conversion, first = _run(session)

    second_run = runner.queue_run(session, conversion)
    session.commit()
    runner.run_sync(second_run.id, mock_delay=0)
    session.expire_all()

    conversion = session.get(Conversion, conversion.id)
    snapshots = session.query(RequirementSnapshot).all()

    # The draft was replaced: one snapshot per requirement, all from the second run.
    assert len(snapshots) == len(conversion.requirements)
    assert {s.run_id for s in snapshots} == {second_run.id}
    # Both attempts stay in the log.
    assert session.query(Run).count() == 2
    assert session.get(Run, first.id).status == "done"


def test_empty_mmr_fails_the_run_with_an_estonian_message(seeded):
    session = seeded
    conversion = Conversion(title="Tühi", mmr_id="mmr_empty", mmr_text="   ")
    session.add(conversion)
    session.flush()
    run = runner.queue_run(session, conversion)
    session.commit()
    runner.run_sync(run.id, mock_delay=0)
    session.expire_all()

    run = session.get(Run, run.id)
    assert run.status == "failed"
    assert "tühi" in (run.error or "").lower()
    assert session.get(Conversion, conversion.id).status == "failed"


def test_too_long_mmr_is_refused_rather_than_truncated(seeded, monkeypatch):
    monkeypatch.setattr("app.runner.MAX_SEGMENTS", 5)
    session = seeded
    conversion = Conversion(
        title="Pikk", mmr_id="mmr_long", mmr_text=" ".join(f"Nõue number {i}." for i in range(20))
    )
    session.add(conversion)
    session.flush()
    run = runner.queue_run(session, conversion)
    session.commit()
    runner.run_sync(run.id, mock_delay=0)
    session.expire_all()

    run = session.get(Run, run.id)
    assert run.status == "failed"
    assert "liiga pikk" in (run.error or "")
    assert session.query(Requirement).count() == 0


def test_orphaned_runs_are_failed_on_startup(seeded):
    session = seeded
    conversion = Conversion(title="Katkenud", mmr_id="mmr_orphan", mmr_text="Aaa.")
    session.add(conversion)
    session.flush()
    run = Run(conversion_id=conversion.id, mmr_id=conversion.mmr_id, status="calling")
    session.add(run)
    session.commit()

    assert runner.recover_orphaned_runs(session) == 1
    session.expire_all()
    run = session.get(Run, run.id)
    assert run.status == "failed"
    assert "taaskäivitusel" in (run.error or "")
