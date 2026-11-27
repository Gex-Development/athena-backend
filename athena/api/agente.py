from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Engine

from athena.api.auth import Usuario, exigir_admin
from athena.config.banco import get_engine
from athena.eventos.registro import Evento, TipoEvento, listar

router = APIRouter(prefix="/v1/agente")

POR_PAGINA = 50


class PaginaEventos(BaseModel):
    itens: list[Evento]
    proximoCursor: str | None


@router.get("/eventos")
def eventos(
    _: Annotated[Usuario, Depends(exigir_admin)],
    engine: Annotated[Engine, Depends(get_engine)],
    conversa: int | None = None,
    tipo: TipoEvento | None = None,
    de: datetime | None = None,
    cursor: Annotated[str | None, Query(pattern=r"^\d+$")] = None,
) -> PaginaEventos:
    itens = listar(
        engine,
        conversa_id=conversa,
        tipo=tipo,
        desde=de,
        antes_de_id=int(cursor) if cursor else None,
        limite=POR_PAGINA,
    )
    proximo = itens[-1].id if len(itens) == POR_PAGINA else None
    return PaginaEventos(itens=itens, proximoCursor=proximo)
