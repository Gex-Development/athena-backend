import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

URL_TESTE = os.environ.get("ATHENA_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not URL_TESTE, reason="sem Postgres de teste")


def configuracao_alembic() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", URL_TESTE)
    return config


def tabelas_athena() -> set[str]:
    motor = create_engine(URL_TESTE)
    try:
        return set(inspect(motor).get_table_names(schema="athena"))
    finally:
        motor.dispose()


def test_migrations_sobem_e_descem_no_schema_athena():
    config = configuracao_alembic()

    command.upgrade(config, "head")
    assert {"alembic_version", "configuracao"} <= tabelas_athena()

    command.downgrade(config, "base")
    assert tabelas_athena() == {"alembic_version"}

    command.upgrade(config, "head")
    assert "configuracao" in tabelas_athena()
