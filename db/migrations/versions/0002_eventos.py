import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCHEMA = "athena"
TIPOS = (
    "recebida",
    "barrada_flood",
    "classificada",
    "pedido_buscado",
    "sugerida",
    "checagem_barrou",
    "enviada",
    "devolvida_humano",
    "feedback",
    "controle_alterado",
)


def upgrade() -> None:
    op.create_table(
        "eventos",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("conversa_id", sa.BigInteger, nullable=False),
        sa.Column("tipo", sa.Text, nullable=False),
        sa.Column(
            "em_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("versao_catalogo", sa.Text),
        sa.Column("duracao_ms", sa.Integer),
        sa.Column("dados", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.CheckConstraint(f"tipo IN {TIPOS}", name="eventos_tipo_valido"),
        schema=SCHEMA,
    )
    op.create_index("eventos_conversa_em", "eventos", ["conversa_id", "em_utc"], schema=SCHEMA)
    op.create_index("eventos_tipo_em", "eventos", ["tipo", "em_utc"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("eventos", schema=SCHEMA)
