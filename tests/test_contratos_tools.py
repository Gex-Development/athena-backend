from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from athena.ferramentas.contratos import (
    Celula,
    Classificacao,
    Confianca,
    EntradaBuscaPedido,
    EntradaClassificacao,
    EntradaFlood,
    EntradaGravacao,
    EntradaRisco,
    FichaPedido,
    Mensagem,
    Oferta,
    Risco,
)


def ficha(**extra):
    return FichaPedido(
        codigo="A2KZ8KVJ",
        plataforma="buygoods",
        valor_sem_taxas_usd=Decimal("348.00"),
        valor_cobrado_usd=Decimal("364.66"),
        desfecho="sem_estorno",
        **extra,
    )


def test_motivo_so_vem_com_confianca_alta():
    assert Classificacao(motivo="rastreio", confianca="alta", versao_catalogo="v3.4").motivo
    palpite = Classificacao(
        motivo=None, provavel="rastreio", confianca="a_confirmar", versao_catalogo="v3.4"
    )
    assert palpite.provavel == "rastreio"
    with pytest.raises(ValidationError, match="motivo só vai preenchido"):
        Classificacao(motivo="rastreio", confianca=Confianca.A_CONFIRMAR, versao_catalogo="v3.4")


def test_busca_de_pedido_exige_alguma_chave():
    assert EntradaBuscaPedido(codigo="A2KZ8KVJ").codigo == "A2KZ8KVJ"
    with pytest.raises(ValidationError, match="informe e-mail, telefone ou código"):
        EntradaBuscaPedido()


def test_ficha_separa_valor_sem_taxas_do_cobrado():
    pedido = ficha()

    assert pedido.valor_sem_taxas_usd < pedido.valor_cobrado_usd
    with pytest.raises(ValidationError):
        FichaPedido(codigo="X", plataforma="buygoods", valor_cobrado_usd=1, desfecho="sem_estorno")


def test_oferta_tem_teto_de_30_por_cento():
    assert Oferta(percentual=Decimal("0.05"), valor_usd=Decimal("17.40"), base_usd=Decimal("348"))
    with pytest.raises(ValidationError):
        Oferta(percentual=Decimal("0.31"), valor_usd=Decimal("1"), base_usd=Decimal("1"))


def test_risco_e_classificacao_validam_faixas():
    classificacao = Classificacao(motivo="cancelamento", confianca="alta", versao_catalogo="v3.4")
    entrada = EntradaRisco(
        classificacao=classificacao, ficha=ficha(), irritacao=4, mensagens_ultima_hora=2
    )

    assert Risco(score=0.8, prioridade="P1", celula=Celula.RETENCAO).celula == "retencao"
    assert entrada.irritacao == 4
    with pytest.raises(ValidationError):
        EntradaRisco(classificacao=classificacao, irritacao=6, mensagens_ultima_hora=0)
    with pytest.raises(ValidationError):
        Risco(score=1.2, prioridade="P0", celula="sac")


def test_entradas_de_flood_classificacao_e_gravacao():
    mensagem = Mensagem(conversa_id=1, contato_id=2, texto="oi", recebida_em=datetime.now(UTC))

    assert EntradaFlood(mensagem=mensagem).mensagem.contato_id == 2
    assert EntradaGravacao(conversa_id=1, atributos={"ia_motivo": "rastreio"}).atributos
    with pytest.raises(ValidationError):
        EntradaClassificacao(conversa_id=1, historico=[])
