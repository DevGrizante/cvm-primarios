# =============================================================================
#  CVM Monitor PRO - API (FastAPI + Uvicorn)
#  As dependencias sao leves (fastapi, uvicorn, requests -- sem pandas/numpy),
#  entao o multi-stage aqui serve principalmente para nao carregar o cache do
#  pip nem ferramentas de build na imagem final. Resultado: ~180 MB.
# =============================================================================

# -----------------------------------------------------------------------------
# Estagio 1: builder -- monta a virtualenv
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Copiado antes do codigo para o Docker reaproveitar a camada de instalacao
# enquanto o requirements nao mudar.
COPY backend/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Estagio 2: runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# PYTHONUNBUFFERED e importante neste projeto: o boot do data_engine baixa e
# processa o zip da CVM e reporta o progresso por print(). Com buffer, o log
# so apareceria no final.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080

# ca-certificates: o data_engine faz download HTTPS de dados.cvm.gov.br via
# urllib. Sem os certificados no sistema, a validacao TLS falha.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY --chown=appuser:appuser backend/ /app/backend/

# data_cache e volume no compose. A pasta precisa existir e pertencer ao
# appuser antes do primeiro download, senao o processo nao consegue gravar.
RUN mkdir -p /app/backend/data_cache \
    && chown -R appuser:appuser /app/backend

USER appuser
WORKDIR /app/backend

EXPOSE 8080

# /api/status responde durante o boot (o engine expoe boot_state), entao o
# healthcheck fica verde assim que o servidor sobe, sem esperar a carga toda.
# start-period generoso: o primeiro boot baixa ~5,5 MB e processa o zip.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/status', timeout=4).status == 200 else 1)"

# main.py le a porta de os.environ["PORT"] quando executado direto, mas aqui
# chamamos o uvicorn explicitamente -- e o mesmo app, com controle do host.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
