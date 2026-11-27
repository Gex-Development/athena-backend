import re
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from athena.ferramentas.contratos import (
    Canal,
    Celula,
    EntradaChecagem,
    EntradaFlood,
    EntradaGravacao,
    EntradaOferta,
    EntradaRisco,
    Mensagem,
    Oferta,
    Prioridade,
    Risco,
    SaidaChecagem,
    SaidaFlood,
    SaidaGravacao,
)

JANELA_DUPLICADA = timedelta(minutes=10)
JANELA_RAJADA = timedelta(seconds=60)
LIMITE_RAJADA = 5

MOTIVOS_SO_HUMANO = {"saude", "chargeback", "fraude"}
CELULA_POR_MOTIVO = {
    "cancelamento": Celula.RETENCAO,
    "reembolso": Celula.RETENCAO,
    "devolucao": Celula.BKO,
    "calculo_reembolso": Celula.BKO,
    "garantia": Celula.BKO,
}
PRIMEIRA_OFERTA = Decimal("0.05")
OFERTA_IRRITADO = Decimal("0.15")
DEGRAU = Decimal("0.05")
TETO_OFERTA = Decimal("0.30")

JARGAO_INTERNO = ("chargeback", "gateway", "sla", "status pending", "trv", "upsell", "crm")
LIMITE_SMS = 1500
VALOR_EM_DOLAR = re.compile(r"US\$\s?([\d.]+(?:,\d{2})?)")


def guarda_flood(entrada: EntradaFlood, recentes: list[Mensagem]) -> SaidaFlood:
    atual = entrada.mensagem
    do_contato = [m for m in recentes if m.contato_id == atual.contato_id]
    texto = atual.texto.strip().lower()
    for anterior in do_contato:
        perto = atual.recebida_em - anterior.recebida_em <= JANELA_DUPLICADA
        if perto and anterior.texto.strip().lower() == texto:
            return SaidaFlood(barrada=True, motivo="duplicada")
    na_janela = [m for m in do_contato if atual.recebida_em - m.recebida_em <= JANELA_RAJADA]
    if len(na_janela) + 1 >= LIMITE_RAJADA:
        return SaidaFlood(barrada=True, motivo="rajada")
    return SaidaFlood(barrada=False)


def calcular_risco(entrada: EntradaRisco) -> Risco:
    motivo = entrada.classificacao.motivo or entrada.classificacao.provavel or ""
    score = (entrada.irritacao - 1) / 4 * 0.5
    if motivo in MOTIVOS_SO_HUMANO:
        score += 0.4
    if entrada.ficha and entrada.ficha.desfecho == "disputa":
        score += 0.3
    if entrada.ficha and entrada.ficha.valor_cobrado_usd >= 850:
        score += 0.1
    if entrada.mensagens_ultima_hora >= 3:
        score += 0.1
    score = min(round(score, 2), 1.0)
    prioridade = (
        Prioridade.P0
        if score >= 0.8
        else Prioridade.P1
        if score >= 0.6
        else Prioridade.P2
        if score >= 0.3
        else Prioridade.P3
    )
    return Risco(
        score=score, prioridade=prioridade, celula=CELULA_POR_MOTIVO.get(motivo, Celula.SAC)
    )


def definir_oferta(entrada: EntradaOferta) -> Oferta:
    base = entrada.ficha.valor_sem_taxas_usd
    inicio = OFERTA_IRRITADO if entrada.irritado else PRIMEIRA_OFERTA
    desejado = inicio + DEGRAU * entrada.recusas_anteriores
    humano = desejado > TETO_OFERTA or (entrada.motivo or "") in MOTIVOS_SO_HUMANO
    percentual = min(desejado, TETO_OFERTA)
    valor = (base * percentual).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Oferta(percentual=percentual, valor_usd=valor, base_usd=base, precisa_humano=humano)


def _valor_br(texto: str) -> Decimal:
    return Decimal(texto.replace(".", "").replace(",", "."))


def checar_resposta(entrada: EntradaChecagem) -> SaidaChecagem:
    problemas: list[str] = []
    minusculo = entrada.texto.lower()
    for termo in JARGAO_INTERNO:
        if re.search(rf"\b{re.escape(termo)}\b", minusculo):
            problemas.append(f"jargão interno no texto ao cliente: {termo}")
    if entrada.canal == Canal.SMS and len(entrada.texto) > LIMITE_SMS:
        problemas.append(f"SMS com {len(entrada.texto)} caracteres; o limite é {LIMITE_SMS}")
    valores = {_valor_br(v) for v in VALOR_EM_DOLAR.findall(entrada.texto)}
    if entrada.oferta:
        permitidos = {entrada.oferta.valor_usd, entrada.oferta.base_usd}
        if entrada.ficha:
            permitidos |= {entrada.ficha.valor_cobrado_usd, entrada.ficha.valor_sem_taxas_usd}
        for valor in sorted(valores - permitidos):
            problemas.append(f"valor US$ {valor} não vem da oferta nem da ficha")
    elif valores and not entrada.ficha:
        problemas.append("texto cita valor em dólar sem ficha do pedido")
    return SaidaChecagem(aprovada=not problemas, problemas=problemas)


def planejar_gravacao_chatwoot(
    entrada: EntradaGravacao, editados_pelo_humano: set[str]
) -> SaidaGravacao:
    gravados = [chave for chave in entrada.atributos if chave not in editados_pelo_humano]
    preservados = [chave for chave in entrada.atributos if chave in editados_pelo_humano]
    if entrada.nota_privada:
        gravados.append("nota_privada")
    if entrada.celula and "celula" not in editados_pelo_humano:
        gravados.append("celula")
    gravados.extend(f"etiqueta:{e}" for e in entrada.etiquetas)
    return SaidaGravacao(gravados=gravados, preservados_do_humano=preservados)
