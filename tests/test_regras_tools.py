from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from athena.ferramentas.contratos import (
    Classificacao,
    EntradaChecagem,
    EntradaFlood,
    EntradaGravacao,
    EntradaOferta,
    EntradaRisco,
    FichaPedido,
    Mensagem,
)
from athena.ferramentas.regras import (
    calcular_risco,
    checar_resposta,
    definir_oferta,
    guarda_flood,
    planejar_gravacao_chatwoot,
)

AGORA = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)


def msg(texto, segundos_atras=0, contato=1):
    return Mensagem(
        conversa_id=10,
        contato_id=contato,
        texto=texto,
        recebida_em=AGORA - timedelta(seconds=segundos_atras),
    )


def ficha(desfecho="sem_estorno", cobrado="364.66"):
    return FichaPedido(
        codigo="A2KZ8KVJ",
        plataforma="buygoods",
        valor_sem_taxas_usd=Decimal("348.00"),
        valor_cobrado_usd=Decimal(cobrado),
        desfecho=desfecho,
    )


def test_flood_barra_duplicada_e_rajada_e_deixa_passar_o_normal():
    assert guarda_flood(EntradaFlood(mensagem=msg("Oi")), [msg("oi ", 120)]).motivo == "duplicada"
    rajada = [msg(f"m{i}", i * 5) for i in range(1, 5)]
    assert guarda_flood(EntradaFlood(mensagem=msg("nova")), rajada).motivo == "rajada"
    outros = [msg("oi", 30, contato=2), msg("antiga", 3600)]
    assert guarda_flood(EntradaFlood(mensagem=msg("oi")), outros).barrada is False


def risco(motivo, irritacao=1, **extra):
    classificacao = Classificacao(motivo=motivo, confianca="alta", versao_catalogo="v3.4")
    return calcular_risco(
        EntradaRisco(
            classificacao=classificacao, irritacao=irritacao, mensagens_ultima_hora=0, **extra
        )
    )


def test_risco_define_prioridade_e_celula_por_regra():
    calmo = risco("rastreio")
    assert (calmo.score, calmo.prioridade, calmo.celula) == (0.0, "P3", "sac")
    assert risco("cancelamento", irritacao=3).celula == "retencao"
    assert risco("devolucao").celula == "bko"
    grave = risco("chargeback", irritacao=5, ficha=ficha("disputa", "900"))
    assert (grave.score, grave.prioridade) == (1.0, "P0")


@pytest.mark.parametrize(
    ("recusas", "irritado", "percentual", "valor", "humano"),
    [
        (0, False, "0.05", "17.40", False),
        (2, False, "0.15", "52.20", False),
        (0, True, "0.15", "52.20", False),
        (5, False, "0.30", "104.40", False),
        (6, False, "0.30", "104.40", True),
    ],
)
def test_oferta_sobre_valor_sem_taxas_com_teto(recusas, irritado, percentual, valor, humano):
    oferta = definir_oferta(
        EntradaOferta(
            motivo="cancelamento", ficha=ficha(), recusas_anteriores=recusas, irritado=irritado
        )
    )

    assert (oferta.percentual, oferta.valor_usd) == (Decimal(percentual), Decimal(valor))
    assert oferta.base_usd == Decimal("348.00")
    assert oferta.precisa_humano is humano


def test_oferta_de_saude_vai_para_humano():
    assert definir_oferta(EntradaOferta(motivo="saude", ficha=ficha())).precisa_humano


def test_checagem_barra_jargao_sms_longo_e_valor_inventado():
    oferta = definir_oferta(EntradaOferta(motivo="cancelamento", ficha=ficha()))
    certo = "Podemos devolver 5% do produto de US$ 348,00, ou seja, US$ 17,40."
    assert checar_resposta(
        EntradaChecagem(texto=certo, canal="email", oferta=oferta, ficha=ficha())
    ).aprovada

    errado = checar_resposta(
        EntradaChecagem(texto="Seu upsell rende US$ 25,00 de volta.", canal="email", oferta=oferta)
    )
    assert errado.problemas == [
        "jargão interno no texto ao cliente: upsell",
        "valor US$ 25.00 não vem da oferta nem da ficha",
    ]
    longo = checar_resposta(EntradaChecagem(texto="a" * 1501, canal="sms"))
    assert longo.problemas == ["SMS com 1501 caracteres; o limite é 1500"]


def test_gravacao_nunca_sobrescreve_o_humano():
    entrada = EntradaGravacao(
        conversa_id=10,
        atributos={"ia_motivo": "rastreio", "ia_pedido": "A2KZ8KVJ"},
        nota_privada="Sugestão da Athena",
        etiquetas=["ia-sugeriu"],
        celula="sac",
    )

    saida = planejar_gravacao_chatwoot(entrada, editados_pelo_humano={"ia_pedido", "celula"})

    assert saida.gravados == ["ia_motivo", "nota_privada", "etiqueta:ia-sugeriu"]
    assert saida.preservados_do_humano == ["ia_pedido"]
