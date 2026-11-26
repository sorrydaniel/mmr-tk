"""initial schema: all tables for phases 1-3

Every table for phases 1, 2 and 3 is created here, empty. Later phases then ship as code
only and never run a migration against a database that by then holds real study data.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-26

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('conversion',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('mmr_id', sa.String(length=100), nullable=False),
    sa.Column('mmr_text', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('procurement_profile', sa.String(length=20), nullable=False),
    sa.Column('assigned_order', sa.String(length=20), nullable=True),
    sa.Column('arm_a_imported_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('first_llm_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('order_gap_days', sa.Float(), nullable=True),
    sa.Column('order_violation', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('setting',
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('answer_key',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=300), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('locked', sa.Boolean(), nullable=False),
    sa.Column('rows_parsed', sa.Integer(), nullable=False),
    sa.Column('timing_violation', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_answer_key_conversion_id'), 'answer_key', ['conversion_id'], unique=False)
    op.create_table('blind_code',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=12), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=False),
    sa.Column('arm', sa.String(length=4), nullable=False),
    sa.Column('variant', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blind_code_code'), 'blind_code', ['code'], unique=True)
    op.create_index(op.f('ix_blind_code_conversion_id'), 'blind_code', ['conversion_id'], unique=False)
    op.create_table('manual_import',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=300), nullable=False),
    sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('rows_parsed', sa.Integer(), nullable=False),
    sa.Column('warnings', sa.Text(), nullable=True),
    sa.Column('rows', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_manual_import_conversion_id'), 'manual_import', ['conversion_id'], unique=False)
    op.create_table('missing_note',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=False),
    sa.Column('reviewer_code', sa.String(length=20), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_missing_note_conversion_id'), 'missing_note', ['conversion_id'], unique=False)
    op.create_table('requirement',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=False),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.Column('edited_by_user', sa.Boolean(), nullable=False),
    sa.Column('added_by_hand', sa.Boolean(), nullable=False),
    sa.Column('deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('category', sa.String(length=200), nullable=False),
    sa.Column('category_source', sa.String(length=20), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('classification', sa.String(length=4), nullable=False),
    sa.Column('classification_signal', sa.String(length=100), nullable=True),
    sa.Column('requirement_type', sa.String(length=20), nullable=True),
    sa.Column('verif_with_bid', sa.String(length=200), nullable=False),
    sa.Column('verif_method', sa.String(length=60), nullable=False),
    sa.Column('verif_stage', sa.String(length=60), nullable=False),
    sa.Column('verif_source', sa.String(length=20), nullable=False),
    sa.Column('verif_quote', sa.Text(), nullable=True),
    sa.Column('verif_description', sa.Text(), nullable=False),
    sa.Column('comments', sa.Text(), nullable=False),
    sa.Column('source_segments', sa.JSON(), nullable=False),
    sa.Column('uncertain', sa.Boolean(), nullable=False),
    sa.Column('uncertain_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_requirement_conversion_id'), 'requirement', ['conversion_id'], unique=False)
    op.create_table('review',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=False),
    sa.Column('reviewer_code', sa.String(length=20), nullable=False),
    sa.Column('mode', sa.String(length=20), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('minutes', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_conversion_id'), 'review', ['conversion_id'], unique=False)
    op.create_table('run',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=True),
    sa.Column('mmr_id', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('processing_seconds', sa.Float(), nullable=False),
    sa.Column('queue_seconds', sa.Float(), nullable=False),
    sa.Column('rows_generated', sa.Integer(), nullable=False),
    sa.Column('schema_valid', sa.Boolean(), nullable=False),
    sa.Column('uncertain_rows', sa.Integer(), nullable=False),
    sa.Column('retry_used', sa.Boolean(), nullable=False),
    sa.Column('mock', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_run_conversion_id'), 'run', ['conversion_id'], unique=False)
    op.create_table('segment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=False),
    sa.Column('sid', sa.String(length=16), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('segment_type', sa.String(length=20), nullable=False),
    sa.Column('list_level', sa.Integer(), nullable=True),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('conversion_id', 'sid', name='uq_segment_conversion_sid')
    )
    op.create_index(op.f('ix_segment_conversion_id'), 'segment', ['conversion_id'], unique=False)
    op.create_table('requirement_flag',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('requirement_id', sa.Integer(), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=False),
    sa.Column('reviewer_code', sa.String(length=20), nullable=False),
    sa.Column('flag', sa.String(length=20), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requirement_id'], ['requirement.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('requirement_id', 'reviewer_code', name='uq_flag_requirement_reviewer')
    )
    op.create_index(op.f('ix_requirement_flag_conversion_id'), 'requirement_flag', ['conversion_id'], unique=False)
    op.create_index(op.f('ix_requirement_flag_requirement_id'), 'requirement_flag', ['requirement_id'], unique=False)
    op.create_table('requirement_snapshot',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('requirement_id', sa.Integer(), nullable=False),
    sa.Column('conversion_id', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.Integer(), nullable=True),
    sa.Column('order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('category', sa.String(length=200), nullable=False),
    sa.Column('category_source', sa.String(length=20), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('classification', sa.String(length=4), nullable=False),
    sa.Column('classification_signal', sa.String(length=100), nullable=True),
    sa.Column('requirement_type', sa.String(length=20), nullable=True),
    sa.Column('verif_with_bid', sa.String(length=200), nullable=False),
    sa.Column('verif_method', sa.String(length=60), nullable=False),
    sa.Column('verif_stage', sa.String(length=60), nullable=False),
    sa.Column('verif_source', sa.String(length=20), nullable=False),
    sa.Column('verif_quote', sa.Text(), nullable=True),
    sa.Column('verif_description', sa.Text(), nullable=False),
    sa.Column('comments', sa.Text(), nullable=False),
    sa.Column('source_segments', sa.JSON(), nullable=False),
    sa.Column('uncertain', sa.Boolean(), nullable=False),
    sa.Column('uncertain_reason', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['conversion_id'], ['conversion.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requirement_id'], ['requirement.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['run_id'], ['run.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_requirement_snapshot_conversion_id'), 'requirement_snapshot', ['conversion_id'], unique=False)
    op.create_index(op.f('ix_requirement_snapshot_requirement_id'), 'requirement_snapshot', ['requirement_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_requirement_snapshot_requirement_id'), table_name='requirement_snapshot')
    op.drop_index(op.f('ix_requirement_snapshot_conversion_id'), table_name='requirement_snapshot')
    op.drop_table('requirement_snapshot')
    op.drop_index(op.f('ix_requirement_flag_requirement_id'), table_name='requirement_flag')
    op.drop_index(op.f('ix_requirement_flag_conversion_id'), table_name='requirement_flag')
    op.drop_table('requirement_flag')
    op.drop_index(op.f('ix_segment_conversion_id'), table_name='segment')
    op.drop_table('segment')
    op.drop_index(op.f('ix_run_conversion_id'), table_name='run')
    op.drop_table('run')
    op.drop_index(op.f('ix_review_conversion_id'), table_name='review')
    op.drop_table('review')
    op.drop_index(op.f('ix_requirement_conversion_id'), table_name='requirement')
    op.drop_table('requirement')
    op.drop_index(op.f('ix_missing_note_conversion_id'), table_name='missing_note')
    op.drop_table('missing_note')
    op.drop_index(op.f('ix_manual_import_conversion_id'), table_name='manual_import')
    op.drop_table('manual_import')
    op.drop_index(op.f('ix_blind_code_conversion_id'), table_name='blind_code')
    op.drop_index(op.f('ix_blind_code_code'), table_name='blind_code')
    op.drop_table('blind_code')
    op.drop_index(op.f('ix_answer_key_conversion_id'), table_name='answer_key')
    op.drop_table('answer_key')
    op.drop_table('setting')
    op.drop_table('conversion')
