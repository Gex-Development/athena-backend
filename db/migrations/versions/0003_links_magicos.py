import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SCHEMA = "athena"


def upgrade() -> None:
    op.create_table(
        "links_magicos",
        sa.Column("token_hash", sa.Text, primary_key=True),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True)),
        schema=SCHEMA,
    )
    op.create_index(
        "links_magicos_email_criado", "links_magicos", ["email", "criado_em"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_table("links_magicos", schema=SCHEMA)
