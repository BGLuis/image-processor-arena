# docker/go.Dockerfile
# Imagem de produção e benchmark para o servidor Go puro
FROM golang:1.24-bookworm AS builder

WORKDIR /app

# Copia dependências primeiro para cache do Go mod
COPY go/go.mod go/go.sum* ./
RUN go mod download || true

# Copia código fonte e compila sem cgo (pure Go)
COPY go/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /arena-server ./cmd/server && \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /arena-batch ./cmd/batch

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /arena-server /usr/local/bin/arena-server
COPY --from=builder /arena-batch /usr/local/bin/arena-batch

ENV PORT=8080
EXPOSE 8080

CMD ["/usr/local/bin/arena-server"]
