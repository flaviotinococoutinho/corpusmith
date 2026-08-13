# Corpusmith daemon (v1.0) — API local-first containerizada.
# O desktop (Electron) roda FORA do container e conecta em :8377;
# o token do handshake fica no volume (state/daemon.json).
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --global user.email corpusmith@local \
    && git config --global user.name "Corpusmith" \
    && git config --global init.defaultBranch main
WORKDIR /app
COPY pyproject.toml README.md* ./
COPY src ./src
COPY db ./db
COPY config ./config
RUN pip install --no-cache-dir -e .
ENV CORPUSMITH_HOME=/data CORPUSMITH_CONFIG=/app/docker-config.yaml
COPY docker-config.yaml ./docker-config.yaml
EXPOSE 8377
HEALTHCHECK --interval=30s --timeout=3s CMD \
  python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8377/health')" || exit 1
CMD ["sh", "-c", "python -m corpusmith.cli okf bootstrap; python -m corpusmith.cli seed; python -m corpusmith.cli daemon"]
