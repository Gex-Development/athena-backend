import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from athena.eventos.registro import (
    TipoEvento,
    apagar_antigos,
    conferir_sem_dado_pessoal,
    listar,
    registrar,
)

URL_TESTE = os.environ.get("ATHENA_TEST_DATABASE_URL")
precisa_banco = pytest.mark.skipif(not URL_TESTE, reason="sem Postgres de teste")


@pytest.mark.parametrize(
    "dados",
    [
        {"texto": "quero cancelar"},
        {"pedido": {"email": "x"}},
        {"contato": "maria@gexcorp.com.br"},
        {"origem": "+1 (305) 555-0199"},
        {"lista": ["ok", "joao@gmail.com"]},
    ],
)
def test_evento_recusa_texto_e_dado_pessoal(dados):
    with pytest.raises(ValueError):
        conferir_sem_dado_pessoal(dados)


def test_evento_aceita_codigos_e_numeros():
    conferir_sem_dado_pessoal({"motivo": "cancelamento", "confianca": 0.93, "pedido": "A2KZ8KVJ"})


@pytest.fixture
def engine():
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", URL_TESTE)
    command.upgrade(config, "head")
    motor = create_engine(URL_TESTE)
    with motor.begin() as conexao:
        conexao.execute(text("TRUNCATE athena.eventos"))
    yield motor
    motor.dispose()


@precisa_banco
def test_registra_e_lista_a_trilha_da_conversa(engine):
    registrar(engine, 77, TipoEvento.RECEBIDA, duracao_ms=12)
    registrar(
        engine, 77, TipoEvento.CLASSIFICADA, versao_catalogo="v3.4", dados={"motivo": "rastreio"}
    )
    registrar(engine, 99, TipoEvento.RECEBIDA)

    trilha = listar(engine, conversa_id=77)

    assert [e.tipo for e in trilha] == [TipoEvento.CLASSIFICADA, TipoEvento.RECEBIDA]
    assert trilha[0].versaoCatalogo == "v3.4"
    assert trilha[0].dados == {"motivo": "rastreio"}
    assert trilha[1].duracaoMs == 12
    assert listar(engine, tipo=TipoEvento.RECEBIDA, antes_de_id=int(trilha[1].id)) == []


@precisa_banco
def test_banco_recusa_tipo_fora_do_contrato(engine):
    with pytest.raises(Exception, match="eventos_tipo_valido"), engine.begin() as conexao:
        conexao.execute(text("INSERT INTO athena.eventos (conversa_id, tipo) VALUES (1, 'outro')"))


@precisa_banco
def test_retencao_apaga_so_os_antigos(engine):
    registrar(engine, 5, TipoEvento.RECEBIDA)
    with engine.begin() as conexao:
        conexao.execute(
            text(
                "INSERT INTO athena.eventos (conversa_id, tipo, em_utc) "
                "VALUES (5, 'enviada', now() - interval '200 days')"
            )
        )

    assert apagar_antigos(engine, 180) == 1
    assert len(listar(engine, conversa_id=5)) == 1
