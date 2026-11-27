import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "athena"


def upgrade() -> None:
    op.create_table(
        "configuracao",
        sa.Column("chave", sa.Text, primary_key=True),
        sa.Column("valor", postgresql.JSONB, nullable=False),
        sa.Column("alterado_por", sa.Text),
        sa.Column(
            "alterado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("configuracao", schema=SCHEMA)
