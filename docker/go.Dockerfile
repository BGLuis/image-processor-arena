# syntax=docker/dockerfile:1.4
# docker/go.Dockerfile
# Multi-stage Dockerfile para o servidor e ferramentas Go puras (image-processor-arena)

# ---------------------------------------------------------------------------
# Stage 1: Base com dependências cacheadas
# ---------------------------------------------------------------------------
FROM golang:1.27-bookworm AS base

WORKDIR /workspace

# Copia dependências primeiro para cache do Go mod
COPY go/go.mod go/go.sum* ./go/
WORKDIR /workspace/go
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# ---------------------------------------------------------------------------
# Stage 2: Test / Dev (validação de pureza e testes unitários)
# ---------------------------------------------------------------------------
FROM base AS test

WORKDIR /workspace
COPY go/ ./go/
COPY harness/ ./harness/
COPY docs/ ./docs/
COPY scripts/ ./scripts/
COPY arena.toml ./arena.toml

RUN chmod +x ./scripts/check-purity-go.sh

WORKDIR /workspace/go
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go test -v ./...

RUN /workspace/scripts/check-purity-go.sh

# ---------------------------------------------------------------------------
# Stage 3: Builder (compilação de binários estáticos sem CGO)
# ---------------------------------------------------------------------------
FROM base AS builder

WORKDIR /workspace/go
COPY go/ ./

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /app/server ./cmd/server && \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /app/batch ./cmd/batch

# ---------------------------------------------------------------------------
# Stage 4: Runtime mínimo não-root
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 arena \
    && useradd -u 10001 -g arena -m -s /bin/bash arenauser

WORKDIR /app

# Copia binários compilados
COPY --from=builder /app/server /app/server
COPY --from=builder /app/batch /app/batch
COPY --from=builder /app/server /usr/local/bin/arena-server
COPY --from=builder /app/batch /usr/local/bin/arena-batch

RUN chown -R 10001:10001 /app

USER 10001:10001

ENV PORT=8080
EXPOSE 8080

CMD ["/app/server"]
