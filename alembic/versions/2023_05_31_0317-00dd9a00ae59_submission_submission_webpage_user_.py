"""submission, submission_webpage, user tables

Revision ID: 00dd9a00ae59
Revises: 
Create Date: 2023-05-31 03:17:41.065984

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy_utils.types.url import URLType
from sqlalchemy_utils.types.arrow import ArrowType
from sqlalchemy_utils.types.choice import ChoiceType

from furaffinity_scrape import model


# revision identifiers, used by Alembic.
revision = '00dd9a00ae59'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table('submission',
        sa.Column('submission_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('furaffinity_submission_id', sa.Integer(), nullable=False),
        sa.Column('date_visited', ArrowType(), nullable=False),
        sa.Column('submission_status', ChoiceType(model.SubmissionStatus, impl=sa.Unicode()), nullable=False),
        sa.Column('processed_status', ChoiceType(model.ProcessedStatus, impl=sa.Unicode()), nullable=False),
        sa.Column('claimed_by', sa.Unicode(), nullable=False),
        sa.PrimaryKeyConstraint('submission_id', name='PK-submission-submission_id')
    )

    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.create_index('IX-submission-claimed_by', ['claimed_by'], unique=False)
        batch_op.create_index('IX-submission-date_visited', ['date_visited'], unique=False)
        batch_op.create_index('IX-submission-furaffinity_submission_id', ['furaffinity_submission_id'], unique=False)
        batch_op.create_index('IX-submission-processed_status', ['processed_status'], unique=False)
        batch_op.create_index('IX-submission-submission_status', ['submission_status'], unique=False)

    op.create_table('user',
        sa.Column('user_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('date_added', ArrowType(), nullable=False),
        sa.Column('user_name', sa.Unicode(), nullable=False),
        sa.PrimaryKeyConstraint('user_id', name='PK-user-user_id')
    )

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.create_index('IX-user-date_added', ['date_added'], unique=False)
        batch_op.create_index('IXUQ-user-user_name', ['user_name'], unique=True)

    op.create_table('submission_webpage',
        sa.Column('submission_webpage_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('date_visited', ArrowType(), nullable=False),
        sa.Column('raw_compressed_webpage_data', sa.LargeBinary(), nullable=False),
        sa.Column('encoding_status', ChoiceType(model.EncodingStatusEnum, impl=sa.Unicode()), nullable=False),
        sa.Column('original_data_sha512', sa.Unicode(), nullable=False),
        sa.Column('compressed_data_sha512', sa.Unicode(), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['submission.submission_id'], name='FK-submission_webpage-submission_id-submission-submission_id'),
        sa.PrimaryKeyConstraint('submission_webpage_id', name='PK-submission_webpage-submission_webpage_id')
    )

    with op.batch_alter_table('submission_webpage', schema=None) as batch_op:
        batch_op.create_index('IX-submission_webpage-compressed_data_sha512', ['compressed_data_sha512'], unique=False)
        batch_op.create_index('IX-submission_webpage-date_visited', ['date_visited'], unique=False)
        batch_op.create_index('IX-submission_webpage-original_data_sha512', ['original_data_sha512'], unique=False)
        batch_op.create_index('IX-submission_webpage-submission_id', ['submission_id'], unique=False)



def downgrade() -> None:

    with op.batch_alter_table('submission_webpage', schema=None) as batch_op:
        batch_op.drop_index('IX-submission_webpage-submission_id')
        batch_op.drop_index('IX-submission_webpage-original_data_sha512')
        batch_op.drop_index('IX-submission_webpage-date_visited')
        batch_op.drop_index('IX-submission_webpage-compressed_data_sha512')

    op.drop_table('submission_webpage')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index('IXUQ-user-user_name')
        batch_op.drop_index('IX-user-date_added')

    op.drop_table('user')

    with op.batch_alter_table('submission', schema=None) as batch_op:
        batch_op.drop_index('IX-submission-submission_status')
        batch_op.drop_index('IX-submission-processed_status')
        batch_op.drop_index('IX-submission-furaffinity_submission_id')
        batch_op.drop_index('IX-submission-date_visited')
        batch_op.drop_index('IX-submission-claimed_by')

    op.drop_table('submission')