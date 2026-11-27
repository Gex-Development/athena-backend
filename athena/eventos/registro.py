import json
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Engine, text


class TipoEvento(StrEnum):
    RECEBIDA = "recebida"
    BARRADA_FLOOD = "barrada_flood"
    CLASSIFICADA = "classificada"
    PEDIDO_BUSCADO = "pedido_buscado"
    SUGERIDA = "sugerida"
    CHECAGEM_BARROU = "checagem_barrou"
    ENVIADA = "enviada"
    DEVOLVIDA_HUMANO = "devolvida_humano"
    FEEDBACK = "feedback"
    CONTROLE_ALTERADO = "controle_alterado"


class Evento(BaseModel):
    id: str
    conversaId: int
    tipo: TipoEvento
    emUtc: datetime
    versaoCatalogo: str | None = None
    duracaoMs: int | None = None
    dados: dict[str, Any] = {}


CHAVES_PROIBIDAS = {"texto", "mensagem", "conteudo", "email", "telefone", "nome", "cliente"}
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
TELEFONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")


def conferir_sem_dado_pessoal(dados: Any, caminho: str = "dados") -> None:
    if isinstance(dados, dict):
        for chave, valor in dados.items():
            if str(chave).lower() in CHAVES_PROIBIDAS:
                raise ValueError(f"{caminho}.{chave}: evento não guarda texto nem dado pessoal")
            conferir_sem_dado_pessoal(valor, f"{caminho}.{chave}")
    elif isinstance(dados, list):
        for indice, valor in enumerate(dados):
            conferir_sem_dado_pessoal(valor, f"{caminho}[{indice}]")
    elif isinstance(dados, str) and (EMAIL.search(dados) or TELEFONE.search(dados)):
        raise ValueError(f"{caminho}: parece e-mail ou telefone")


def registrar(
    engine: Engine,
    conversa_id: int,
    tipo: TipoEvento,
    *,
    versao_catalogo: str | None = None,
    duracao_ms: int | None = None,
    dados: dict[str, Any] | None = None,
) -> int:
    dados = dados or {}
    conferir_sem_dado_pessoal(dados)
    with engine.begin() as conexao:
        return conexao.execute(
            text(
                "INSERT INTO athena.eventos "
                "(conversa_id, tipo, versao_catalogo, duracao_ms, dados) "
                "VALUES (:conversa, :tipo, :versao, :duracao, CAST(:dados AS jsonb)) RETURNING id"
            ),
            {
                "conversa": conversa_id,
                "tipo": tipo.value,
                "versao": versao_catalogo,
                "duracao": duracao_ms,
                "dados": json.dumps(dados, default=str),
            },
        ).scalar_one()


def listar(
    engine: Engine,
    *,
    conversa_id: int | None = None,
    tipo: TipoEvento | None = None,
    desde: datetime | None = None,
    antes_de_id: int | None = None,
    limite: int = 50,
) -> list[Evento]:
    filtros = ["TRUE"]
    parametros: dict[str, Any] = {"limite": limite}
    for coluna, valor, condicao in (
        ("conversa", conversa_id, "conversa_id = :conversa"),
        ("tipo", tipo.value if tipo else None, "tipo = :tipo"),
        ("desde", desde, "em_utc >= :desde"),
        ("antes", antes_de_id, "id < :antes"),
    ):
        if valor is not None:
            filtros.append(condicao)
            parametros[coluna] = valor
    with engine.connect() as conexao:
        linhas = conexao.execute(
            text(
                "SELECT id, conversa_id, tipo, em_utc, versao_catalogo, duracao_ms, dados "
                f"FROM athena.eventos WHERE {' AND '.join(filtros)} "
                "ORDER BY id DESC LIMIT :limite"
            ),
            parametros,
        ).all()
    return [
        Evento(
            id=str(linha.id),
            conversaId=linha.conversa_id,
            tipo=linha.tipo,
            emUtc=linha.em_utc,
            versaoCatalogo=linha.versao_catalogo,
            duracaoMs=linha.duracao_ms,
            dados=linha.dados,
        )
        for linha in linhas
    ]


def apagar_antigos(engine: Engine, dias: int) -> int:
    limite = datetime.now(UTC) - timedelta(days=dias)
    with engine.begin() as conexao:
        return conexao.execute(
            text("DELETE FROM athena.eventos WHERE em_utc < :limite"), {"limite": limite}
        ).rowcount
