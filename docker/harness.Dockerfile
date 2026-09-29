# docker/harness.Dockerfile
# Imagem do Harness para a Arena de Processamento de Imagens
# Inclui encoders/decoders de referência, ferramentas de carga (oha, hyperfine) e Python 3

FROM debian:bookworm-slim AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    jq \
    python3 \
    python3-minimal \
    libjxl-tools \
    webp \
    libavif-bin \
    libjpeg-turbo-progs \
    procps \
    time \
    && rm -rf /var/lib/apt/lists/*

# Instala oha (gerador de carga HTTP de alta concorrência em Rust puro)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then OHA_ARCH="x86_64-unknown-linux-musl"; \
    elif [ "$ARCH" = "aarch64" ]; then OHA_ARCH="aarch64-unknown-linux-musl"; \
    fi && \
    curl -sSL "https://github.com/hatoo/oha/releases/download/v1.6.0/oha-${OHA_ARCH}" -o /usr/local/bin/oha && \
    chmod +x /usr/local/bin/oha

# Instala hyperfine (benchmark de comandos CLI batch)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then HF_ARCH="x86_64-unknown-linux-musl"; \
    elif [ "$ARCH" = "aarch64" ]; then HF_ARCH="aarch64-unknown-linux-musl"; \
    fi && \
    curl -sSL "https://github.com/sharkdp/hyperfine/releases/download/v1.19.0/hyperfine-v1.19.0-${HF_ARCH}.tar.gz" | tar -xz -C /tmp && \
    mv /tmp/hyperfine-v1.19.0-${HF_ARCH}/hyperfine /usr/local/bin/hyperfine && \
    rm -rf /tmp/hyperfine* && \
    chmod +x /usr/local/bin/hyperfine

WORKDIR /arena

# Copia scripts do harness
COPY harness/ /arena/harness/
COPY docs/ /arena/docs/

# Cria ponto de montagem de ramdisk para corpus em memória
RUN mkdir -p /arena/ramdisk /arena/results

CMD ["python3", "harness/verify_cross.py", "--help"]
