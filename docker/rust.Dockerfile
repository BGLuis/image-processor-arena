# syntax=docker/dockerfile:1.4
# docker/rust.Dockerfile
# Imagem de desenvolvimento, teste, benchmark e produção para a arena Rust pura.

# -----------------------------------------------------------------------------
# Base: Ambiente com toolchain Rust e dependências essenciais
# -----------------------------------------------------------------------------
FROM rust:1.85-bookworm AS base

WORKDIR /app

# Instala ferramentas necessárias para inspeção e testes
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Estágio Dev / Test: Executa validação de pureza e suíte completa de testes
# -----------------------------------------------------------------------------
FROM base AS test

WORKDIR /arena

# Copia manifests, código, fixtures e scripts
COPY rust/Cargo.toml rust/Cargo.lock* ./rust/
COPY rust/deny.toml ./rust/
COPY rust/src/ ./rust/src/
COPY rust/vendor/ ./rust/vendor/
COPY harness/ ./harness/
COPY docs/ ./docs/
COPY scripts/ ./scripts/

RUN chmod +x ./scripts/check-purity-rust.sh

# Compila e roda os testes com cache mount
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/usr/local/cargo/git \
    --mount=type=cache,target=/arena/rust/target \
    cargo test --manifest-path rust/Cargo.toml

# Executa verificação de pureza
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/usr/local/cargo/git \
    --mount=type=cache,target=/arena/rust/target \
    ./scripts/check-purity-rust.sh

# -----------------------------------------------------------------------------
# Estágio Builder: Compila binários em release
# -----------------------------------------------------------------------------
FROM base AS builder

WORKDIR /app

COPY rust/Cargo.toml rust/Cargo.lock* ./rust/
COPY rust/deny.toml ./rust/
COPY rust/src/ ./rust/src/
COPY rust/vendor/ ./rust/vendor/

RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/usr/local/cargo/git \
    --mount=type=cache,target=/app/rust/target \
    cargo build --release --manifest-path rust/Cargo.toml && \
    mkdir -p /app/bin && \
    cp /app/rust/target/release/arena-server /app/bin/arena-server && \
    cp /app/rust/target/release/arena-batch /app/bin/arena-batch

# -----------------------------------------------------------------------------
# Estágio Runtime: Imagem de produção mínima não-root
# -----------------------------------------------------------------------------
FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Cria usuário não-root dedicado
RUN groupadd -g 10001 arena && \
    useradd -u 10001 -g arena -d /app -s /usr/sbin/nologin arena && \
    mkdir -p /app && chown -R arena:arena /app

WORKDIR /app

# Copia os binários compilados
COPY --from=builder /app/bin/arena-server /usr/local/bin/arena-server
COPY --from=builder /app/bin/arena-batch /usr/local/bin/arena-batch

# Atalhos em /app
RUN ln -s /usr/local/bin/arena-server /app/server && \
    ln -s /usr/local/bin/arena-batch /app/batch

USER arena:arena

ENV PORT=8081 \
    RUST_LOG=info

EXPOSE 8081

HEALTHCHECK --interval=2s --timeout=2s --retries=10 --start-period=3s \
    CMD curl -s -f http://localhost:8081/health || exit 1

CMD ["/usr/local/bin/arena-server"]
