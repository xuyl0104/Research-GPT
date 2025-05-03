"""Add faiss_path, chunks_path to embeddings and user_id, evidence to messages

Revision ID: fe37a6c55164
Revises: <your_last_revision_id>
Create Date: 2024-04-30

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg


# revision identifiers, used by Alembic.
revision = 'fe37a6c55164'
down_revision = '<your_last_revision_id>'  # replace with actual ID
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to embeddings
    op.add_column('embeddings', sa.Column('faiss_path', sa.String(), nullable=True))
    op.add_column('embeddings', sa.Column('chunks_path', sa.String(), nullable=True))

    # Add new columns to messages
    op.add_column('messages', sa.Column('user_id', pg.UUID(as_uuid=True), nullable=False))
    op.add_column('messages', sa.Column('evidence', pg.JSONB(), nullable=True))

    # Create indexes
    op.create_index('ix_messages_embedding_id', 'messages', ['embedding_id'])
    op.create_index('ix_messages_user_id', 'messages', ['user_id'])
    op.create_index('ix_messages_created_at', 'messages', ['created_at'])


def downgrade():
    # Drop columns and indexes
    op.drop_index('ix_messages_created_at', table_name='messages')
    op.drop_index('ix_messages_user_id', table_name='messages')
    op.drop_index('ix_messages_embedding_id', table_name='messages')

    op.drop_column('messages', 'evidence')
    op.drop_column('messages', 'user_id')

    op.drop_column('embeddings', 'chunks_path')
    op.drop_column('embeddings', 'faiss_path')
