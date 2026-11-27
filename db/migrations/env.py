import sys

from alembic import context
from sqlalchemy import Connection, create_engine, text

from athena.config.settings import get_settings

SCHEMA = "athena"
TRAVA = "athena.migrations"
ESPERA_TRAVA = "10min"


def url_do_banco() -> str:
    url = context.config.get_main_option("sqlalchemy.url")
    return url or get_settings().database_url


def migrar_offline() -> None:
    context.configure(
        url=url_do_banco(),
        literal_binds=True,
        version_table_schema=SCHEMA,
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        context.run_migrations()


def pegar_trava(conexao: Connection) -> None:
    livre = conexao.execute(
        text("SELECT pg_try_advisory_lock(hashtext(:t))"), {"t": TRAVA}
    ).scalar_one()
    if livre:
        return
    print(
        f"Outra réplica está migrando. Esperando a trava por até {ESPERA_TRAVA}.",
        file=sys.stderr,
        flush=True,
    )
    conexao.execute(text(f"SET LOCAL lock_timeout = '{ESPERA_TRAVA}'"))
    conexao.execute(text("SELECT pg_advisory_lock(hashtext(:t))"), {"t": TRAVA})


def migrar_online() -> None:
    motor = create_engine(url_do_banco())
    try:
        with motor.connect() as conexao:
            pegar_trava(conexao)
            try:
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
            finally:
                conexao.rollback()
                conexao.execute(text("SELECT pg_advisory_unlock(hashtext(:t))"), {"t": TRAVA})
                conexao.commit()
    finally:
        motor.dispose()


if context.is_offline_mode():
    migrar_offline()
else:
    migrar_online()
