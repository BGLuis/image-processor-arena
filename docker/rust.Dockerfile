# docker/rust.Dockerfile
# Imagem de produção e benchmark para o servidor Rust puro
FROM rust:1.85-bookworm AS builder

WORKDIR /app

# Copia manifestos de dependência para cache
COPY rust/Cargo.toml rust/Cargo.lock* ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release || true

# Copia código fonte e compila em release
COPY rust/ ./
RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/arena-server /usr/local/bin/arena-server
COPY --from=builder /app/target/release/arena-batch /usr/local/bin/arena-batch

ENV PORT=8081
EXPOSE 8081

CMD ["/usr/local/bin/arena-server"]
