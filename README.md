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
POST /run?op=encode|decode|transcode|analyze&format=<fmt>&to=<fmt>&mode=lossy|lossless&q=<1..100>&effort=<1..10>
```
Headers de telemetria retornados:
- `X-Arena-Encode-Ns: <nanoseconds>`
- `X-Arena-Decode-Ns: <nanoseconds>`
- `X-Arena-Analyze-Ns: <nanoseconds>`

#### Contrato de parâmetros

Os dois servidores e os dois `arena-batch` seguem a mesma tabela, definida em [`arena.toml`](arena.toml) (`[params]`) e verificada por testes em Go e em Rust:

| Parâmetro | Faixa | Default | Fora da faixa |
|---|---|---|---|
| `q` | inteiro 1..100 | 75 | HTTP 400 / batch com saída 1 (nunca truncado) |
| `effort` | inteiro 1..10, maior é mais lento e menor | 4 | HTTP 400 / batch com saída 1 |
| `mode` | `lossy` ou `lossless` | `lossy` (PNG é sempre lossless e ignora `mode`; JPEG é sempre lossy) | HTTP 400 / batch com saída 1 |

Valor ausente ou vazio seleciona o default. `q=0`, `q=300`, `effort=abc` e formato desconhecido retornam 400 nos dois servidores. Os parâmetros só são validados em `encode` e `transcode` (no `transcode` valem para o formato de destino).

Como cada codec tem uma escala nativa própria, `q` e `effort` são mapeados por codec. O mapeamento parte da documentação e do código das bibliotecas (`gen2brain/jxl`, `gen2brain/gav1d`, `deepteams/webp`, `ravif`, `zenwebp`, `jxl-encoder`, `png`, `jpeg-encoder`); onde um codec não tem o parâmetro, a tabela diz isso:

| Codec | `q` | `effort` |
|---|---|---|
| PNG | nenhum (só lossless) | 1-2 deflate mais rápido, 3-6 padrão, 7-10 melhor (Go `BestSpeed`/`Default`/`BestCompression`, Rust `Fast`/`Balanced`/`High`) |
| JPEG | qualidade nativa 1..100 (tabelas Annex K com a escala do libjpeg nos dois; o Rust força 4:2:0 como o Go, pois o default do `jpeg-encoder` muda para 4:4:4 em q>=90) | nenhum |
| WebP lossy | qualidade nativa 1..100 | `method` = `[0,1,1,2,3,3,4,5,5,6][effort-1]` (0..6, faixa nativa dos dois) |
| WebP lossless | nenhum | nenhum (nem `gowebp` nem `image-webp` expõem controle) |
| AVIF lossy | índice de quantização AV1 `(100-q)*255/100`, o mapeamento nativo do `gav1d`. O `ravif` usa outra curva (a q75 dá índice 128 contra 63), então o Rust passa a qualidade do `ravif` que produz o mesmo índice | `speed = 11-effort` (invertido: no AVIF, speed 10 é o mais rápido). Limitação sem solução pública: o `gav1d` grava sempre 4:2:0 e o `ravif` sempre 4:4:4, então o mesmo índice não dá a mesma qualidade (no corpus, o PSNR RGB do Rust ficou 7 a 14 dB acima do Go, com arquivos maiores em `photo` e menores em `screenshot`) |
| AVIF lossless | nenhum | `speed = 11-effort` |
| JXL lossy | distância Butteraugli `0.1+(100-q)*0.09` para q>=30 (mapeamento nativo do `gen2brain/jxl`); o `quality_to_distance` do `jxl-encoder` difere (q75 dá 1.75 contra 2.35), então o Rust calcula a distância | `effort` JXL = `[0,1,1,2,3,3,4,5,5,6][effort-1] + 1` (1..7, faixa nativa do Go; o Rust é limitado a ela) |
| JXL lossless | nenhum | igual ao JXL lossy |

Os níveis de `effort` são casados por posição na escala de cada codec, não por algoritmo idêntico: o mesmo `effort` é o degrau mais próximo, não o mesmo trabalho. Os demais parâmetros nativos ficam nos defaults das bibliotecas.

Layout de pixel: entrada de profundidade 3 chega aos encoders como RGB opaco (`image.RGBA` opaco no Go, `Rgb8` no Rust, sem plano alpha) e profundidade 4 como RGBA com alpha direto. Um arquivo RGB volta como profundidade 3 no decode dos dois lados. No Go, os decoders de WebP, AVIF e JXL sempre devolvem `*image.NRGBA`, então uma imagem totalmente opaca é reduzida a profundidade 3 no decode (o Rust segue a declaração do arquivo).

Tempo só é comparável junto do tamanho de saída: o pódio do benchmark mostra os bytes de Go e de Rust e a razão Go/Rust. Recomendação para depois desta issue: medir PSNR/SSIM (ou SSIMULACRA2) dos codecs lossy no harness e comparar a tamanho ou qualidade equivalentes; hoje só o tamanho é reportado.

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
