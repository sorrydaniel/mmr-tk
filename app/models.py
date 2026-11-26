"""All tables for phases 1-3.

Everything is created in the initial migration, empty, so phases 2 and 3 ship as code only
and never run a migration against a database that by then holds real study data.

Enum-like columns are plain strings validated in application code rather than database
enums: a PostgreSQL enum needs a migration every time a value is added, and several of
these lists (verification methods, stages) are expected to be tuned.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# --- phase 1 ---------------------------------------------------------------------------

CONVERSION_STATUSES = ("draft", "converted", "failed", "reviewed")
PROCUREMENT_PROFILES = ("COTS", "MOTS", "ARENDUS")
ASSIGNED_ORDERS = ("A_FIRST", "B_FIRST")


class Conversion(Base):
    __tablename__ = "conversion"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    mmr_id: Mapped[str] = mapped_column(String(100), nullable=False)
    mmr_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    procurement_profile: Mapped[str] = mapped_column(String(20), nullable=False, default="COTS")

    # phase 2: study order bookkeeping
    assigned_order: Mapped[str | None] = mapped_column(String(20), nullable=True)
    arm_a_imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_llm_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_gap_days: Mapped[float | None] = mapped_column(Float)
    order_violation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    segments: Mapped[list["Segment"]] = relationship(
        back_populates="conversion", cascade="all, delete-orphan", order_by="Segment.order"
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="conversion", cascade="all, delete-orphan", order_by="Requirement.order"
    )
    runs: Mapped[list["Run"]] = relationship(
        back_populates="conversion", cascade="all, delete-orphan", order_by="Run.created_at"
    )


SEGMENT_TYPES = ("HEADING", "BULLET", "TABLE_ROW", "SENTENCE")


class Segment(Base):
    __tablename__ = "segment"
    __table_args__ = (UniqueConstraint("conversion_id", "sid", name="uq_segment_conversion_sid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversion_id: Mapped[int] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    sid: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    segment_type: Mapped[str] = mapped_column(String(20), nullable=False, default="SENTENCE")
    list_level: Mapped[int | None] = mapped_column(Integer)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    conversion: Mapped[Conversion] = relationship(back_populates="segments")


CLASSIFICATIONS = ("M", "N", "I", "OP")
CATEGORY_SOURCES = ("MMR_HEADING", "DEFAULT_LIST", "NEW")
VERIF_SOURCES = ("MAPPING", "MMR_EXPLICIT")

VERIF_METHODS = (
    "Funktsionaalne kontroll",
    "Funktsionaalne demonstratsioon",
    "Test",
    "Analüüs",
    "Sertifikaat",
    "N/A",
)

VERIF_STAGES = (
    "Lepingu sõlmimine",
    "Lepingu täitmine",
    "Disainietapid",
    "FAFAT",
    "FAFAT + suvaline FAT",
    "FAT kõik",
    "SAT kõik",
    "Viimane tarne",
    "N/A",
)

REQUIREMENT_TYPES = (
    "MEASURABLE",
    "DOCUMENT",
    "OPERABLE",
    "VISUAL",
    "DESIGN",
    "INFORMATIVE",
)

# Columns compared when computing the raw-vs-final diff.
DIFFABLE_FIELDS = (
    "category",
    "description",
    "classification",
    "verif_with_bid",
    "verif_method",
    "verif_stage",
    "verif_description",
    "comments",
)


class RequirementPayload:
    """Shared column definitions for Requirement and its immutable snapshot."""

    category: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    category_source: Mapped[str] = mapped_column(String(20), nullable=False, default="NEW")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    classification: Mapped[str] = mapped_column(String(4), nullable=False, default="M")
    classification_signal: Mapped[str | None] = mapped_column(String(100))
    requirement_type: Mapped[str | None] = mapped_column(String(20))
    verif_with_bid: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    verif_method: Mapped[str] = mapped_column(String(60), nullable=False, default="N/A")
    verif_stage: Mapped[str] = mapped_column(String(60), nullable=False, default="N/A")
    verif_source: Mapped[str] = mapped_column(String(20), nullable=False, default="MAPPING")
    verif_quote: Mapped[str | None] = mapped_column(Text)
    verif_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    comments: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_segments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uncertain_reason: Mapped[str | None] = mapped_column(Text)


class Requirement(Base, RequirementPayload):
    __tablename__ = "requirement"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversion_id: Mapped[int] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    edited_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    added_by_hand: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    conversion: Mapped[Conversion] = relationship(back_populates="requirements")
    snapshot: Mapped["RequirementSnapshot | None"] = relationship(
        back_populates="requirement", cascade="all, delete-orphan", uselist=False
    )


class RequirementSnapshot(Base, RequirementPayload):
    """Written once, at creation, from the raw LLM output. Never updated.

    This is the accuracy source for the study. The live Requirement row is what the
    engineer corrects; the difference between the two is review effort, not accuracy.
    """

    __tablename__ = "requirement_snapshot"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), unique=True, index=True
    )
    conversion_id: Mapped[int] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[int | None] = mapped_column(ForeignKey("run.id", ondelete="SET NULL"))
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    requirement: Mapped[Requirement] = relationship(back_populates="snapshot")


RUN_STATUSES = ("queued", "splitting", "calling", "validating", "done", "failed")
RUN_ACTIVE_STATUSES = ("queued", "splitting", "calling", "validating")


class Run(Base):
    __tablename__ = "run"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversion_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    mmr_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Model time only. Queue time is tracked separately so the research numbers are not
    # polluted by how long the task waited for a worker.
    processing_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    queue_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    rows_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uncertain_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text)

    conversion: Mapped[Conversion | None] = relationship(back_populates="runs")


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# --- phase 2 ---------------------------------------------------------------------------


class ManualImport(Base):
    """An arm A TK, written by hand in Excel and imported so it goes through the same
    normalising, blinded export pipeline as the app's own output."""

    __tablename__ = "manual_import"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversion_id: Mapped[int] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    rows_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[str | None] = mapped_column(Text)
    rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class AnswerKey(Base):
    """The scoring reference, written while sanitising the MMR, before either arm.

    Locked once uploaded; its timestamp must predate both arms or it is flagged.
    """

    __tablename__ = "answer_key"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversion_id: Mapped[int] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rows_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timing_violation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BlindCode(Base):
    """code -> (conversion, arm, raw|final). Kept out of the exported files themselves;
    only the key CSV resolves it."""

    __tablename__ = "blind_code"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    conversion_id: Mapped[int] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    arm: Mapped[str] = mapped_column(String(4), nullable=False)  # A | B
    variant: Mapped[str] = mapped_column(String(10), nullable=False)  # raw | final
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- phase 3 ---------------------------------------------------------------------------

REVIEW_MODES = ("PARANDA", "HINDA")
FLAG_VALUES = ("VALE", "VAJAB_MUUTMIST")


class Review(Base):
    __tablename__ = "review"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversion_id: Mapped[int] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    reviewer_code: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="HINDA")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    minutes: Mapped[float | None] = mapped_column(Float)


class RequirementFlag(Base):
    """One flag per (requirement, reviewer). Reviewers never see each other's flags."""

    __tablename__ = "requirement_flag"
    __table_args__ = (
        UniqueConstraint("requirement_id", "reviewer_code", name="uq_flag_requirement_reviewer"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirement.id", ondelete="CASCADE"), index=True
    )
    conversion_id: Mapped[int] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    reviewer_code: Mapped[str] = mapped_column(String(20), nullable=False)
    flag: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class MissingNote(Base):
    """"Puuduv nõue" in flag-only mode: a per-reviewer note, never a row in the draft."""

    __tablename__ = "missing_note"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversion_id: Mapped[int] = mapped_column(
        ForeignKey("conversion.id", ondelete="CASCADE"), index=True
    )
    reviewer_code: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
