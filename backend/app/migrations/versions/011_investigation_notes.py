"""011 investigation notes

Revision ID: 011_investigation_notes
Revises: 010_platform_layer
Create Date: 2026-07-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '011_investigation_notes'
down_revision = '010_platform_layer'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'investigation_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_investigation_notes_incident_id', 'investigation_notes', ['incident_id'])
    op.create_index('ix_investigation_notes_author_id', 'investigation_notes', ['author_id'])


def downgrade() -> None:
    op.drop_index('ix_investigation_notes_author_id', table_name='investigation_notes')
    op.drop_index('ix_investigation_notes_incident_id', table_name='investigation_notes')
    op.drop_table('investigation_notes')
