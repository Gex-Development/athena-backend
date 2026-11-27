import os
import threading
import time

import pytest
from agno.db.postgres import PostgresDb
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

URL_TESTE = os.environ.get("ATHENA_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not URL_TESTE, reason="sem Postgres de teste")


def configuracao_alembic(url: str | None = URL_TESTE) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    return config


def tabelas(schema: str) -> set[str]:
    motor = create_engine(URL_TESTE)
    try:
        return set(inspect(motor).get_table_names(schema=schema))
    finally:
        motor.dispose()


def test_migrations_sobem_e_descem_no_schema_athena():
    config = configuracao_alembic()

    command.upgrade(config, "head")
    assert {"alembic_version", "configuracao"} <= tabelas("athena")

    command.downgrade(config, "base")
    assert tabelas("athena") == {"alembic_version"}

    command.upgrade(config, "head")
    assert "configuracao" in tabelas("athena")


def test_update_em_configuracao_atualiza_alterado_em():
    command.upgrade(configuracao_alembic(), "head")
    motor = create_engine(URL_TESTE)
    with motor.begin() as conexao:
        conexao.execute(text("DELETE FROM athena.configuracao WHERE chave = 'teste'"))
        conexao.execute(
            text(
                "INSERT INTO athena.configuracao (chave, valor, alterado_em) "
                "VALUES ('teste', '1', '2020-01-01')"
            )
        )
    with motor.begin() as conexao:
        conexao.execute(text("UPDATE athena.configuracao SET valor = '2' WHERE chave = 'teste'"))
        alterado = conexao.execute(
            text(
                "SELECT alterado_em > now() - interval '1 minute' FROM athena.configuracao "
                "WHERE chave = 'teste'"
            )
        ).scalar_one()
        conexao.execute(text("DELETE FROM athena.configuracao WHERE chave = 'teste'"))
    motor.dispose()

    assert alterado


def test_segunda_replica_espera_a_trava_das_migrations():
    command.upgrade(configuracao_alembic(), "head")
    falhas: list[BaseException] = []

    def rodar_replica() -> None:
        try:
            command.upgrade(configuracao_alembic(), "head")
        except BaseException as falha:
            falhas.append(falha)

    motor = create_engine(URL_TESTE)
    with motor.connect() as dona_da_trava:
        dona_da_trava.execute(text("SELECT pg_advisory_lock(hashtext('athena.migrations'))"))
        replica = threading.Thread(target=rodar_replica)
        replica.start()
        esperando = 0
        for _ in range(50):
            esperando = dona_da_trava.execute(
                text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted")
            ).scalar_one()
            if esperando:
                break
            time.sleep(0.1)
        dona_da_trava.execute(text("SELECT pg_advisory_unlock(hashtext('athena.migrations'))"))
        dona_da_trava.commit()
    replica.join(timeout=30)
    with motor.connect() as conexao:
        versao = conexao.execute(
            text("SELECT version_num FROM athena.alembic_version")
        ).scalar_one()
    motor.dispose()

    assert esperando == 1
    assert not replica.is_alive()
    assert falhas == []
    assert versao == ScriptDirectory.from_config(configuracao_alembic()).get_current_head()


def test_modo_offline_so_imprime_sql(capsys):
    banco_inexistente = "postgresql+psycopg://x:x@127.0.0.1:1/nada_teste"

    command.upgrade(configuracao_alembic(banco_inexistente), "head", sql=True)

    saida = capsys.readouterr().out
    assert saida.lstrip().startswith("BEGIN;")
    assert saida.rstrip().endswith("COMMIT;")
    assert "CREATE SCHEMA IF NOT EXISTS athena" in saida
    assert "CREATE TABLE athena.configuracao" in saida


def test_guarda_recusa_banco_que_nao_e_descartavel():
    from conftest import banco_descartavel

    assert banco_descartavel("postgresql+psycopg://a:b@h:5432/athena_teste")
    assert banco_descartavel("postgresql://a:b@h/athena_test")
    assert not banco_descartavel("postgresql+psycopg://a:b@h:5432/athena")
    assert not banco_descartavel("postgresql://a:b@h/athena_teste_real")


def test_tabelas_do_agno_ficam_no_schema_ai_sem_conflito():
    command.upgrade(configuracao_alembic(), "head")

    PostgresDb(db_url=URL_TESTE)._create_all_tables()

    assert "agno_sessions" in tabelas("ai")
    assert "configuracao" in tabelas("athena")
    assert not tabelas("ai") & tabelas("athena")
