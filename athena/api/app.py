from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from athena.api.agente import router as agente_router
from athena.api.auth import router as auth_router

app = FastAPI(title="Athena", version="0.1.0")
app.include_router(auth_router)
app.include_router(agente_router)


@app.exception_handler(HTTPException)
def erro_no_formato_do_contrato(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(exc.detail, status_code=exc.status_code)
    return JSONResponse({"error": str(exc.detail), "code": "error"}, status_code=exc.status_code)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
