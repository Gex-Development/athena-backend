# athena-backend

Athena V2 · agente de atendimento GEX (Python 3.14, uv, FastAPI, AgentOS do Agno, Postgres/PgVector).

## Rodar local

Com Docker, sobe o Postgres com pgvector e a API:

```bash
docker compose up --build
```

Sem Docker, com [uv](https://docs.astral.sh/uv/) e um Postgres rodando:

```bash
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn athena.main:app --reload
```

A API sobe em `http://127.0.0.1:8000`. `GET /health` responde `{"status":"ok"}`. As migrations criam o schema `athena`; as tabelas do Agno ficam no schema `ai`. No Docker, o container da API roda as migrations antes de subir, com trava para uma réplica por vez.

## Produção

Roda no Dokploy a partir do `Dockerfile`. Variáveis obrigatórias: `ATHENA_DATABASE_URL` e, fora do ambiente `local`, `ATHENA_JWT_CHAVE_PUBLICA` (chave RS256 que o AgentOS usa para proteger as rotas dele). As rotas `/v1/*` usam o login da Athena. O comando `chill` deixa o container parado, para o worker enquanto ele não tem processo próprio.

## Verificações

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Os testes de banco só rodam com `ATHENA_TEST_DATABASE_URL` apontando para um Postgres descartável, com nome terminado em `_teste` ou `_test` (por exemplo `postgresql+psycopg://athena:athena@127.0.0.1:5432/athena_teste`). Eles apagam e recriam tabelas, e recusam qualquer outro nome. A variável pode vir do ambiente ou do `.env`.

A CI roda ruff, pytest e gitleaks em toda PR para `development` e `main`.

## Fluxo git

- `main` é produção e `development` é integração; as duas só recebem código por PR.
- Cada issue tem uma branch curta `feature/`, `fix/` ou `chore/`, criada de `development`.
- Commits seguem Conventional Commits e cada PR soma até 300 linhas, sem contar lockfiles.
- A PR entra em `development` por squash, com CI verde; a release vai de `development` para `main` com tag semver.
- As regras completas estão na skill `gex-fluxo-git`.
