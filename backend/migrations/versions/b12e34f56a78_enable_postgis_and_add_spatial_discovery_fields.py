"""enable postgis and add spatial discovery fields

Revision ID: b12e34f56a78
Revises: a05c8b520b04
Create Date: 2026-11-02 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = 'b12e34f56a78'
down_revision: Union[str, Sequence[str], None] = 'a05c8b520b04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Kích hoạt PostGIS extension theo đặc tả README.md mục 3
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # 2. Cập nhật bảng places
    op.add_column('places', sa.Column('normalized_address', sa.Text(), nullable=True))
    op.add_column(
        'places',
        sa.Column('location', Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=True),
    )

    # 3. Cập nhật bảng videos
    op.add_column('videos', sa.Column('duration_seconds', sa.Float(), nullable=True))
    op.add_column('videos', sa.Column('file_size_mb', sa.Float(), nullable=True))
    op.add_column('videos', sa.Column('transcript_text', sa.Text(), nullable=True))

    # 4. Cập nhật bảng video_place_matches
    op.add_column(
        'video_place_matches',
        sa.Column('confidence_status', sa.String(length=20), server_default='MEDIUM', nullable=False),
    )
    op.add_column('video_place_matches', sa.Column('evidence_sources', sa.JSON(), nullable=True))
    op.add_column(
        'video_place_matches',
        sa.Column('matched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 5. Cập nhật bảng analysis_runs
    op.alter_column('analysis_runs', 'user_id', existing_type=sa.Uuid(), nullable=True)
    op.add_column(
        'analysis_runs',
        sa.Column('trigger_source', sa.String(length=50), server_default='USER_SUBMIT', nullable=False),
    )
    op.add_column(
        'analysis_runs',
        sa.Column('priority', sa.Integer(), server_default='1', nullable=False),
    )
    op.add_column('analysis_runs', sa.Column('keyframes_data', sa.JSON(), nullable=True))
    op.add_column('analysis_runs', sa.Column('ocr_data', sa.JSON(), nullable=True))
    op.add_column('analysis_runs', sa.Column('execution_metrics', sa.JSON(), nullable=True))
    op.create_index(
        'ix_analysis_runs_status_priority_created',
        'analysis_runs',
        ['status', 'priority', 'created_at'],
        unique=False,
    )

    # 6. Tạo bảng discovery_scans
    op.create_table(
        'discovery_scans',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('center_location', Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=False),
        sa.Column('radius_m', sa.Float(), nullable=False),
        sa.Column('keywords_generated', sa.JSON(), nullable=True),
        sa.Column('videos_found_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('scanned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('discovery_scans')
    op.drop_index('ix_analysis_runs_status_priority_created', table_name='analysis_runs')
    op.drop_column('analysis_runs', 'execution_metrics')
    op.drop_column('analysis_runs', 'ocr_data')
    op.drop_column('analysis_runs', 'keyframes_data')
    op.drop_column('analysis_runs', 'priority')
    op.drop_column('analysis_runs', 'trigger_source')
    op.alter_column('analysis_runs', 'user_id', existing_type=sa.Uuid(), nullable=False)
    op.drop_column('video_place_matches', 'matched_at')
    op.drop_column('video_place_matches', 'evidence_sources')
    op.drop_column('video_place_matches', 'confidence_status')
    op.drop_column('videos', 'transcript_text')
    op.drop_column('videos', 'file_size_mb')
    op.drop_column('videos', 'duration_seconds')
    op.drop_column('places', 'location')
    op.drop_column('places', 'normalized_address')
