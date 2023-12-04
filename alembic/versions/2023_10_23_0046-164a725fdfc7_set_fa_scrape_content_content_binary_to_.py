"""Set fa_scrape_content.content_binary to be nullable


Revision ID: 164a725fdfc7
Revises: fab0c026a608
Create Date: 2023-10-23 00:46:34.995831

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '164a725fdfc7'
down_revision = 'fab0c026a608'
branch_labels = None
depends_on = None


def upgrade() -> None:

    with op.batch_alter_table('fa_scrape_content', schema=None) as batch_op:
        batch_op.alter_column('content_binary',
               existing_type=sa.LargeBinary(),
               nullable=True)

    # ### end Alembic commands ###


def downgrade() -> None:

    with op.batch_alter_table('fa_scrape_content', schema=None) as batch_op:
        batch_op.alter_column('content_binary',
               existing_type=sa.LargeBinary(),
               nullable=False)

    # ### end Alembic commands ###
