<div align="center">

<!-- Badges de Status do GitHub -->
[![GitHub Stars](https://shieldcn.dev/github/stars/bgluis/image-processor-arena.svg?variant=secondary&size=sm)](https://github.com/bgluis/image-processor-arena/stargazers)
[![GitHub Forks](https://shieldcn.dev/github/forks/bgluis/image-processor-arena.svg?variant=secondary&size=sm)](https://github.com/bgluis/image-processor-arena/network/members)
[![Watchers](https://shieldcn.dev/github/watchers/bgluis/image-processor-arena.svg?variant=secondary&size=sm)](https://github.com/bgluis/image-processor-arena/watchers)
[![Contributors](https://shieldcn.dev/github/contributors/bgluis/image-processor-arena.svg?theme=emerald&size=sm)](https://github.com/bgluis/image-processor-arena/graphs/contributors)
[![CI](https://github.com/bgluis/image-processor-arena/actions/workflows/ci.yml/badge.svg)](https://github.com/bgluis/image-processor-arena/actions/workflows/ci.yml)

<br/>

<!-- Badges das Tecnologias Utilizadas -->
![Go](https://shieldcn.dev/badge/Go-00ADD8.svg?logo=go&logoColor=white&variant=branded&size=sm)
![Rust](https://shieldcn.dev/badge/Rust-DEA584.svg?logo=rust&logoColor=white&variant=branded&size=sm)
![Python](https://shieldcn.dev/badge/Python-3776AB.svg?logo=python&logoColor=white&variant=branded&size=sm)
![Docker](https://shieldcn.dev/badge/Docker-2496ED.svg?logo=docker&logoColor=white&variant=branded&size=sm)

  <h3>Image Processor Arena: Go Puro × Rust Puro</h3>
  Arena de benchmark de alta precisão comparando o processamento de imagens 100% puro entre Go e Rust sob cargas reais, sem CGO ou FFI.

  <p align="center">
    <b>Português</b> • <a href="README.en.md">English</a>
  </p>
</div>

# 📖 Sobre
A **Image Processor Arena** é um ambiente comparativo e rigoroso de benchmarking de alto desempenho desenvolvido para medir, auditar e comparar o processamento de imagens entre implementações **100% Go Puro** e **100% Rust Puro** sob alta carga.

O projeto opera sob uma política estrita de pureza de ecossistema: **zero CGO, zero FFI, zero dependências C compiladas, zero purego e zero WASM**. Apenas código nativo seguro em suas respectivas linguagens é admitido, com validação de pureza automatizada por scripts dedicados (`./scripts/check-purity-*.sh`) e checagem da árvore de dependências (`rust/deny.toml`).

### Principais Destaques e Capacidades:
- **Operações Avaliadas**:
  - `encode`: Codificação de buffers brutos de pixels para formatos comprimidos.
  - `decode`: Decodificação de arquivos comprimidos para representação de pixels em memória.
  - `transcode`: Conversão direta de formato para formato sem persistência em disco.
  - `analyze`: Cálculo simultâneo de 16 métricas matemáticas estritas (definidas formalmente em [`docs/analyze-spec.md`](docs/analyze-spec.md)), incluindo pHash (DCT-II), blurHash (base83), Spatial Information (Sobel), Luminância BT.601 inteira, histogramas de cor, desvio padrão e entropia de Shannon.
- **Formatos Suportados**: PNG, JPEG, WebP (lossy e lossless), AVIF (somente lossy) e JPEG XL.
- **Formato de Intercâmbio Canônico**: Netpbm PAM binário (`P7`, tuplas `RGB` e `RGB_ALPHA`, `MAXVAL 255`), eliminando distorções de formato intermediário entre as duas linguagens.
- **Modos de Operação**:
  - **Batch CLI**: Binários de linha de comando (`arena-batch`) para benchmarks de throughput máximo com I/O de alta velocidade.
  - **Servidor HTTP**: Servidores REST unificados em Go (porta 8080) e Rust (porta 8081) com telemetria precisa exposta via cabeçalhos HTTP (`X-Arena-*-Ns`).
  - **Isolamento de Recursos**: Orquestração via Docker Compose com separação por afinidade de CPU (P-cores 0-11 para servidores e E-cores 12-15 para o harness de carga), limites fixos de memória e ramdisk `tmpfs`.
- **Confiabilidade e Verificação**:
  - Validação cruzada formal contra gabarito matemático em Python (`verify_cross.py`).
  - Pódio e tabelas comparativas atualizados automaticamente em [`results/PODIUM.md`](results/PODIUM.md).

# 📋 Motivo
Depois de inúmeras discussões sobre qual linguagem tem o melhor processamento de imagem (entre Go e Rust), desisti de apenas discutir e resolvi implementar um benchmark prático e rigoroso para isso. (OBS: sabemos que o resultado não depende apenas da velocidade bruta da linguagem, mas fundamentalmente da maturidade de cada ecossistema e das escolhas de implementação das bibliotecas e codecs utilizados).

# 💻 Como iniciar

### Requisitos
Para executar os componentes localmente ou reproduzir os benchmarks, certifique-se de ter instalado:
- [Go](https://go.dev/dl/) (versão recomendada: **1.24+** ou **1.27**)
- [Rust & Cargo](https://www.rust-lang.org/tools/install) (versão recomendada: **1.85+**, edição 2021)
- [Python 3](https://www.python.org/downloads/) (versão recomendada: **3.10+**)
- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/install/) (opcional, para execução isolada em containers)
- Codecs e ferramentas opcionais para o harness local: [oha](https://github.com/hatoo/oha), [hyperfine](https://github.com/sharkdp/hyperfine), `webp`, `libavif-bin`, `libjpeg-turbo-progs`, `libjxl-tools`

### Instalação

1. Clone o repositório do projeto:
   ```sh
   git clone https://github.com/bgluis/image-processor-arena.git
   ```

2. Navegue até o diretório do projeto:
   ```sh
   cd image-processor-arena
   ```

---

#### Método 1: Com Docker Compose (Recomendado)

O Docker Compose compila os binários em estágios multi-stage enxutos e gerencia as dependências automaticamente.

- **Subir os servidores em modo de desenvolvimento**:
  ```sh
  docker compose --profile dev up --build
  ```

- **Executar a suíte de benchmarks completa via HTTP**:
  ```sh
  docker compose --profile bench up --build
  ```

- **Executar os testes com isolamento estrito de CPU e cgroups (P-cores e E-cores)**:
  ```sh
  docker compose --profile bench-isolated up --build
  ```

---

#### Método 2: Execução Nativa / Local no Host

Se desejar executar os binários e scripts diretamente no host:

1. **Checagem de Pureza (0% CGO / FFI)**:
   ```sh
   ./scripts/check-purity-go.sh
   ./scripts/check-purity-rust.sh
   ```

2. **Executar os Testes Unitários**:
   ```sh
   # Testes unitários do Go
   (cd go && go test -v ./...)

   # Testes unitários do Rust
   cargo test --manifest-path rust/Cargo.toml
   ```

3. **Iniciar os Servidores HTTP**:
   ```sh
   # Go (Porta 8080)
   PORT=8080 go run ./go/cmd/server/main.go

   # Rust (Porta 8081 - em outro terminal)
   PORT=8081 cargo run --manifest-path rust/Cargo.toml --bin arena-server --release
   ```

4. **Executar a Validação Cruzada (16/16 fixtures contra Gabarito Python)**:
   ```sh
   # Validação direta via CLI Batch
   python3 harness/verify_cross.py --mode batch --target all

   # Validação via Servidor HTTP
   python3 harness/verify_cross.py --mode http --target go
   python3 harness/verify_cross.py --mode http --target rust
   ```

5. **Executar o Benchmark da Arena**:
   ```sh
   # Benchmark completo no modo Batch (atualiza results/PODIUM.md e results/benchmark_results.json)
   python3 harness/benchmark_arena.py --mode batch

   # Benchmark no modo HTTP (com os servidores em execução)
   python3 harness/benchmark_arena.py --mode http --go-url http://localhost:8080/run --rust-url http://localhost:8081/run
   ```

# 🔌 Contrato HTTP e Parâmetros

Ambos os servidores implementam o mesmo contrato unificado:
```http
POST /run?op=encode|decode|transcode|analyze&format=<fmt>&to=<fmt>&mode=lossy|lossless&q=<1..100>&effort=<1..10>
```
Headers de telemetria retornados:
- `X-Arena-Encode-Ns: <nanoseconds>`
- `X-Arena-Decode-Ns: <nanoseconds>`
- `X-Arena-Analyze-Ns: <nanoseconds>`

### Contrato de parâmetros

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
| JXL lossy | distância Butteraugli `0.1+(100-q)*0.09` para q>=30 (mapeamento nativo do `gen2brain/jxl`); o `quality_to_distance` do `jxl-encoder` difere (q75 dá 1.75 contra 2.35), então o Rust calcula a distância | `effort` JXL = `[0,1,1,2,3,3,4,5,5,6][effort-1] + 1` (1..7, faixa nativa do Go; o Rust é limitado a ela) |
| JXL lossless | nenhum | igual ao JXL lossy |

Os níveis de `effort` são casados por posição na escala de cada codec, não por algoritmo idêntico: o mesmo `effort` é o degrau mais próximo, não o mesmo trabalho. Os demais parâmetros nativos ficam nos defaults das bibliotecas.

Layout de pixel: entrada de profundidade 3 chega aos encoders como RGB opaco (`image.RGBA` opaco no Go, `Rgb8` no Rust, sem plano alpha) e profundidade 4 como RGBA com alpha direto. Um arquivo RGB volta como profundidade 3 no decode dos dois lados. No Go, os decoders de WebP, AVIF e JXL sempre devolvem `*image.NRGBA`, então uma imagem totalmente opaca é reduzida a profundidade 3 no decode (o Rust segue a declaração do arquivo).

Tempo só é comparável junto do tamanho de saída: o pódio do benchmark mostra os bytes de Go e de Rust e a razão Go/Rust. Recomendação para depois desta issue: medir PSNR/SSIM (ou SSIMULACRA2) dos codecs lossy no harness e comparar a tamanho ou qualidade equivalentes; hoje só o tamanho é reportado.

# ⚠️ Limitações conhecidas

- **AVIF lossless não é suportado.** Nenhuma biblioteca pura disponível preserva o RGB no round-trip, então `mode=lossless` com `format=avif` retorna erro nos dois lados e o modo não faz parte do benchmark:
  - Go: `KarpelesLab/goavif` ignora `Options.Lossless` (a saída é idêntica com e sem a opção) e `gen2brain/gav1d/avif` sempre converte RGB para YCbCr BT.601 4:2:0 (na foto do corpus, 236.705 bytes RGB divergem, com erro de até 55).
  - Rust: `zenrav1e` (usado por `zenravif`) força `base_q_idx >= 1`, então `quantizer 0` nunca ativa o modo lossless do AV1 (na foto do corpus, 42.803 bytes RGB divergem mesmo com matriz identidade).

# 📊 Resultados e Pódio
Os resultados consolidados da arena, comparativos de latência, throughput em Megapixels por segundo (MP/s) e detalhamento por codec estão documentados em:
👉 [`results/PODIUM.md`](results/PODIUM.md)

# 🤝 Contribuidores
<a href="https://github.com/bgluis/image-processor-arena/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=bgluis/image-processor-arena"/>
</a>
