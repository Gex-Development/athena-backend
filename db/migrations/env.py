from alembic import context
from sqlalchemy import create_engine, text

from athena.config.settings import get_settings

SCHEMA = "athena"


def url_do_banco() -> str:
    url = context.config.get_main_option("sqlalchemy.url")
    return url or get_settings().database_url


def migrar() -> None:
    motor = create_engine(url_do_banco())
    with motor.connect() as conexao:
        conexao.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        conexao.commit()
        context.configure(
            connection=conexao,
            target_metadata=None,
            version_table_schema=SCHEMA,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()
    motor.dispose()


migrar()
