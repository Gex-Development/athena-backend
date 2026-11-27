from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from athena.api.agente import router as agente_router
from athena.api.auth import router as auth_router
from athena.api.magic_link import router as magic_link_router

app = FastAPI(title="Athena", version="0.1.0")
app.include_router(auth_router)
app.include_router(magic_link_router)
app.include_router(agente_router)


@app.exception_handler(HTTPException)
def erro_no_formato_do_contrato(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(exc.detail, status_code=exc.status_code)
    return JSONResponse({"error": str(exc.detail), "code": "error"}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
def validacao_no_formato_do_contrato(_: Request, exc: RequestValidationError) -> JSONResponse:
    campos = sorted(
        {
            ".".join(p for p in erro["loc"][1:] if isinstance(p, str))
            for erro in exc.errors()
            if erro["type"] != "json_invalid"
        }
        - {""}
    )
    mensagem = (
        f"Dados inválidos: {', '.join(campos)}."
        if campos
        else "Corpo da requisição ausente ou inválido."
    )
    return JSONResponse({"error": mensagem, "code": "invalid_request"}, status_code=422)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
