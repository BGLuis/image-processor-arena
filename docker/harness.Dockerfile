# docker/harness.Dockerfile
# Imagem do Harness para a Arena de Processamento de Imagens
# Inclui encoders de referência (cjxl, cwebp, avifenc), o gerador de carga oha, o Pillow com libjxl e
# libavif (decoder de referência do harness) e Python 3. Só o harness usa estas ferramentas nativas:
# os engines Go e Rust continuam 100% puros.

FROM debian:bookworm-slim AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    jq \
    python3 \
    python3-venv \
    python3-pip \
    libjxl-tools \
    webp \
    libavif-bin \
    libjpeg-turbo-progs \
    procps \
    time \
    && rm -rf /var/lib/apt/lists/*

# oha: gerador de carga HTTP concorrente (modo `--mode load` do benchmark). Versão fixa e checksum
# verificado; arquitetura desconhecida e download que não seja 200 (curl -f) derrubam o build, em vez
# de gravar uma página de erro como se fosse o binário.
ARG OHA_VERSION=1.16.0
ARG OHA_SHA256_AMD64=620bb9e16fb53eabc9a3fc45f88bdb41fefa3fee5c05e75892011ce320391716
ARG OHA_SHA256_ARM64=99a790eb8c3e0feaca974bd6b32f0f8d4426a0c5b289f39e833e5b2c7529cd39
RUN set -eu; \
    case "$(uname -m)" in \
        x86_64)  OHA_ARCH=amd64; OHA_SHA256="${OHA_SHA256_AMD64}" ;; \
        aarch64) OHA_ARCH=arm64; OHA_SHA256="${OHA_SHA256_ARM64}" ;; \
        *) echo "arquitetura sem binário do oha: $(uname -m)" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/hatoo/oha/releases/download/v${OHA_VERSION}/oha-linux-${OHA_ARCH}" \
        -o /usr/local/bin/oha; \
    echo "${OHA_SHA256}  /usr/local/bin/oha" | sha256sum -c -; \
    chmod 0755 /usr/local/bin/oha; \
    oha --version

# Decoders de referência do harness (Pillow + libjxl), num venv para não tocar no Python do sistema.
COPY harness/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install -r /tmp/requirements.txt
ENV PATH="/opt/venv/bin:${PATH}"

# Usuário sem privilégios. Com volumes montados do host, passe o uid/gid de quem é dono de ./results
# (docker-compose.yml usa ARENA_UID/ARENA_GID) para o relatório poder ser gravado.
ARG ARENA_UID=10001
ARG ARENA_GID=10001
RUN groupadd -g "${ARENA_GID}" arena && \
    useradd -u "${ARENA_UID}" -g arena -d /arena -s /usr/sbin/nologin arena

WORKDIR /arena

# Copia scripts do harness
COPY harness/ /arena/harness/
COPY docs/ /arena/docs/
COPY arena.toml /arena/arena.toml

# Cria ponto de montagem de ramdisk para arquivos temporários e a pasta de resultados
RUN mkdir -p /arena/ramdisk /arena/results && chown -R arena:arena /arena

USER arena:arena

CMD ["python3", "harness/verify_cross.py", "--help"]
