FROM agnohq/python:3.14

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    AGNO_TELEMETRY=false

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv export --locked --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt \
    && uv pip install --system -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY alembic.ini ./
COPY athena ./athena
COPY catalogo ./catalogo
COPY db ./db
COPY scripts ./scripts
RUN chmod +x /app/scripts/entrypoint.sh

USER 1000
EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["uvicorn", "athena.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
