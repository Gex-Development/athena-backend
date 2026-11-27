from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION athena.tocar_alterado_em() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.alterado_em = now();
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER configuracao_alterado_em BEFORE UPDATE ON athena.configuracao "
        "FOR EACH ROW EXECUTE FUNCTION athena.tocar_alterado_em()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER configuracao_alterado_em ON athena.configuracao")
    op.execute("DROP FUNCTION athena.tocar_alterado_em()")
