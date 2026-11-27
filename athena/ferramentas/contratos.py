from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Confianca(StrEnum):
    ALTA = "alta"
    A_CONFIRMAR = "a_confirmar"
    INDEFINIDO = "indefinido"


class Celula(StrEnum):
    SAC = "sac"
    RETENCAO = "retencao"
    BKO = "bko"
    H48 = "48h"


class Prioridade(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class Canal(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    HELPDESK_BUYGOODS = "helpdesk_buygoods"


class Mensagem(BaseModel):
    conversa_id: int
    contato_id: int
    texto: str
    recebida_em: datetime


class EntradaFlood(BaseModel):
    mensagem: Mensagem


class SaidaFlood(BaseModel):
    barrada: bool
    motivo: Literal["duplicada", "rajada"] | None = None


class EntradaClassificacao(BaseModel):
    conversa_id: int
    historico: list[str] = Field(min_length=1)


class Classificacao(BaseModel):
    motivo: str | None
    submotivo: str | None = None
    provavel: str | None = None
    confianca: Confianca
    versao_catalogo: str

    @model_validator(mode="after")
    def motivo_so_com_confianca_alta(self) -> Classificacao:
        if self.confianca != Confianca.ALTA and self.motivo is not None:
            raise ValueError(
                "motivo só vai preenchido com confiança alta; o palpite vai em provavel"
            )
        return self


class EntradaBuscaPedido(BaseModel):
    email: str | None = None
    telefone: str | None = None
    codigo: str | None = None

    @model_validator(mode="after")
    def alguma_chave(self) -> EntradaBuscaPedido:
        if not (self.email or self.telefone or self.codigo):
            raise ValueError("informe e-mail, telefone ou código")
        return self


class PedidoEncontrado(BaseModel):
    codigo: str
    codigos_do_grupo: list[str] = []
    plataforma: str
    produto: str | None = None
    comprado_em: datetime | None = None
    como_achou: Literal["contato", "codigo", "ia", "corrigido"]


class SaidaBuscaPedido(BaseModel):
    pedidos: list[PedidoEncontrado]


class EntradaFicha(BaseModel):
    codigo: str


class FichaPedido(BaseModel):
    codigo: str
    plataforma: str
    valor_sem_taxas_usd: Decimal
    valor_cobrado_usd: Decimal
    estornado_usd: Decimal = Decimal("0")
    desfecho: Literal[
        "sem_estorno", "estorno_parcial", "estorno_com_restocking", "estorno_total", "disputa"
    ]
    garantia_ate: date | None = None


class EntradaRastreio(BaseModel):
    codigo: str


class Rastreio(BaseModel):
    codigo_rastreio: str | None = None
    transportadora: str | None = None
    status: str | None = None
    entregue_em: datetime | None = None


class EntradaRisco(BaseModel):
    classificacao: Classificacao
    ficha: FichaPedido | None = None
    irritacao: int = Field(ge=1, le=5)
    mensagens_ultima_hora: int = Field(ge=0)


class Risco(BaseModel):
    score: float = Field(ge=0, le=1)
    prioridade: Prioridade
    celula: Celula


class EntradaConhecimento(BaseModel):
    pergunta: str
    motivo: str | None = None


class TrechoConhecimento(BaseModel):
    titulo: str
    texto: str
    fonte: str


class SaidaConhecimento(BaseModel):
    trechos: list[TrechoConhecimento]


class EntradaOferta(BaseModel):
    motivo: str | None
    ficha: FichaPedido
    recusas_anteriores: int = Field(default=0, ge=0)
    irritado: bool = False


class Oferta(BaseModel):
    percentual: Decimal = Field(ge=0, le=Decimal("0.30"))
    valor_usd: Decimal
    base_usd: Decimal
    precisa_humano: bool = False


class EntradaChecagem(BaseModel):
    texto: str
    canal: Canal
    oferta: Oferta | None = None
    ficha: FichaPedido | None = None


class SaidaChecagem(BaseModel):
    aprovada: bool
    problemas: list[str] = []


class EntradaGravacao(BaseModel):
    conversa_id: int
    atributos: dict[str, str | int | float | bool | None] = {}
    nota_privada: str | None = None
    etiquetas: list[str] = []
    celula: Celula | None = None


class SaidaGravacao(BaseModel):
    gravados: list[str]
    preservados_do_humano: list[str] = []
