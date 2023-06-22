"""adding furaffinity scrape tables

Revision ID: fab0c026a608
Revises: 00dd9a00ae59
Create Date: 2023-06-04 23:51:09.915334

"""
from alembic import op
import sqlalchemy as sa

from sqlalchemy_utils.types.url import URLType
from sqlalchemy_utils.types.arrow import ArrowType
from sqlalchemy_utils.types.choice import ChoiceType

from furaffinity_scrape import model


# revision identifiers, used by Alembic.
revision = 'fab0c026a608'
down_revision = '00dd9a00ae59'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table('fa_scrape_attempt',
        sa.Column('scrape_attempt_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('furaffinity_submission_id', sa.Integer(), nullable=False),
        sa.Column('date_visited', ArrowType(), nullable=False),
        sa.Column('processed_status', ChoiceType(model.ProcessedStatus, impl=sa.Unicode()), nullable=False),
        sa.Column('claimed_by', sa.Unicode(), nullable=False),
        sa.Column('error_string', sa.Unicode(), nullable=True),
        sa.PrimaryKeyConstraint('scrape_attempt_id', name='PK-fa_scrape_attempt-scrape_attempt_id')
    )

    with op.batch_alter_table('fa_scrape_attempt', schema=None) as batch_op:
        batch_op.create_index('IX-fa_scrape_attempt-furaffinity_submission_id',
            ['furaffinity_submission_id'],
            unique=False)
        batch_op.create_index('IX-fa_scrape_attempt-furaffinity_submission_id-processed_status',
            ['furaffinity_submission_id', 'processed_status'],
            unique=False)

    op.create_table('fa_scrape_content',
        sa.Column('content_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('attempt_id', sa.Integer(), nullable=False),
        sa.Column('content_length', sa.Integer(), nullable=False),
        sa.Column('content_sha512', sa.Unicode(), nullable=False),
        sa.Column('content_binary', sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(
            ['attempt_id'],
            ['fa_scrape_attempt.scrape_attempt_id'],
            name='FK-fa_scrape_content-a_id-fa_scrape_attempt-scrape_attempt_id'),
        sa.PrimaryKeyConstraint(
            'content_id',
            name='PK-fa_scrape_content-content_id')
    )
    with op.batch_alter_table('fa_scrape_content', schema=None) as batch_op:
        batch_op.create_index('IX-fa_scrape_content-attempt_id', ['attempt_id'], unique=False)



def downgrade() -> None:

    with op.batch_alter_table('fa_scrape_content', schema=None) as batch_op:
        batch_op.drop_index('IX-fa_scrape_content-attempt_id')

    op.drop_table('fa_scrape_content')

    with op.batch_alter_table('fa_scrape_attempt', schema=None) as batch_op:
        batch_op.drop_index('IX-fa_scrape_attempt-furaffinity_submission_id-processed_status')
        batch_op.drop_index('IX-fa_scrape_attempt-furaffinity_submission_id')

    op.drop_table('fa_scrape_attempt')
