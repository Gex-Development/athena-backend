# athena-backend

Athena V2 · agente de atendimento GEX (Python 3.12, uv, FastAPI, Agno, Postgres/PgVector).

## Rodar local

Pré-requisito: [uv](https://docs.astral.sh/uv/) instalado. O uv baixa o Python 3.12 se faltar.

```bash
uv sync
cp .env.example .env
uv run uvicorn athena.api.app:app --reload
```

A API sobe em `http://127.0.0.1:8000`. `GET /health` responde `{"status":"ok"}`.

## Verificações

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

A CI roda ruff, pytest e gitleaks em toda PR para `development` e `main`.

## Fluxo git

- `main` é produção e `development` é integração; as duas só recebem código por PR.
- Cada issue tem uma branch curta `feature/`, `fix/` ou `chore/`, criada de `development`.
- Commits seguem Conventional Commits e cada PR soma até 300 linhas, sem contar lockfiles.
- A PR entra em `development` por squash, com CI verde; a release vai de `development` para `main` com tag semver.
- As regras completas estão na skill `gex-fluxo-git`.
