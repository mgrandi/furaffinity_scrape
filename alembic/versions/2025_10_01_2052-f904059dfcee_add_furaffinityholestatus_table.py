"""add FuraffinityHoleStatus table

Revision ID: f904059dfcee
Revises: 164a725fdfc7
Create Date: 2025-10-01 20:52:17.387705

"""
from alembic import op
import sqlalchemy as sa

from sqlalchemy_utils.types.choice import ChoiceType

from furaffinity_scrape import model

# revision identifiers, used by Alembic.
revision = 'f904059dfcee'
down_revision = '164a725fdfc7'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table('fa_hole_status',
        sa.Column('item_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('processed_status',
            ChoiceType(model.ProcessedStatus), nullable=False),
        sa.Column('file_path', sa.Unicode(), nullable=False),
        sa.Column('warc_sha512', sa.Unicode(), nullable=True),
        sa.Column('fa_submission_status',
            ChoiceType(model.FuraffinitySubmissionStatus), nullable=False),
        sa.PrimaryKeyConstraint('item_id', name='PK-fa_hole_status-item_id')
    )

    with op.batch_alter_table('fa_hole_status', schema=None) as batch_op:
        batch_op.create_index(
            'IX-fa_hole_status-run_id-processed_status',
            ['run_id', 'processed_status'], unique=False)



def downgrade() -> None:

    with op.batch_alter_table('fa_hole_status', schema=None) as batch_op:
        batch_op.drop_index('IX-fa_hole_status-run_id-processed_status')

    op.drop_table('fa_hole_status')
