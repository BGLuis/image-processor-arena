# Image Processor Arena: Go Puro × Rust Puro

Arena comparativa de alto desempenho para processamento de imagens entre **Go 100% puro** e **Rust 100% puro** sob alta carga, sem FFI, CGO, purego, WASM ou montagem de dependências C.

---

## 🎯 Visão Geral

- **Operações**: `encode`, `decode`, `transcode` e `analyze`
- **Formatos suportados**: PNG, JPEG, WebP (lossy e lossless), AVIF (lossy e lossless), JPEG XL
- **Formato de intercâmbio**: Netpbm PAM binário (`P7`, RGB e RGB_ALPHA, MAXVAL 255)
- **Métricas de Análise**: 16 métricas formais (BT.601 inteira, DCT-II para pHash, base83 para blurHash, SI Sobel, etc.) especificadas matematicamente em [`docs/analyze-spec.md`](docs/analyze-spec.md).

---

## 🛡️ Regras de Pureza

Nenhum código C compilado ou FFI é permitido:
- **Go**: `CGO_ENABLED=0`, verificado por [`scripts/check-purity-go.sh`](scripts/check-purity-go.sh) que bloqueia `CgoFiles`, `purego` e `wazero`.
- **Rust**: Verificado por [`scripts/check-purity-rust.sh`](scripts/check-purity-rust.sh) e [`rust/deny.toml`](rust/deny.toml) que bloqueiam `cc`, `cmake`, `bindgen`, `nasm-rs`, `pkg-config` e campo `links`.

---

## 🚀 Como Executar

### 1. Testes Nativos no Host

#### Validação de Pureza:
```bash
./scripts/check-purity-go.sh
./scripts/check-purity-rust.sh
```

#### Testes Unitários:
```bash
# Go
(cd go && go test -v ./...)

# Rust
cargo test --manifest-path rust/Cargo.toml
```

#### Validação Cruzada (16/16 fixtures contra Gabarito Python):
```bash
python3 harness/verify_cross.py --mode batch --target all
```

---

### 2. Servidores HTTP e Endpoints

Ambos os servidores implementam o mesmo contrato unificado:
```http
POST /run?op=encode|decode|transcode|analyze&format=<fmt>&to=<fmt>&mode=lossy|lossless&q=<n>&effort=<n>
```
Headers de telemetria retornados:
- `X-Arena-Encode-Ns: <nanoseconds>`
- `X-Arena-Decode-Ns: <nanoseconds>`
- `X-Arena-Analyze-Ns: <nanoseconds>`

#### Iniciar servidores localmente:
```bash
# Go (Porta 8080)
PORT=8080 go run ./go/cmd/server/main.go

# Rust (Porta 8081)
PORT=8081 cargo run --manifest-path rust/Cargo.toml --bin arena-server --release
```

#### Testar validação HTTP:
```bash
python3 harness/verify_cross.py --mode http --target go
python3 harness/verify_cross.py --mode http --target rust
```

---

### 3. Execução Isolada via Docker Compose

```bash
# Subir serviços em modo de desenvolvimento
docker compose --profile dev up --build

# Executar validação com isolamento de CPU e cgroups
docker compose --profile bench up --build
```
- Servidores Go e Rust amarrados aos **P-cores** (`cpuset: "0-11"`).
- Harness de carga amarrado aos **E-cores** (`cpuset: "12-15"`).
- Limite de memória fixo em 3 GiB com montagem em ramdisk `tmpfs`.
