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
  - **Carga concorrente**: `--mode load` do benchmark dispara o [`oha`](https://github.com/hatoo/oha) contra os dois servidores e reporta latência p50/p95/p99 e throughput.
  - **Isolamento de Recursos**: Orquestração via Docker Compose (perfil `bench-isolated`) com separação por afinidade de CPU entre servidores e harness, limites de memória e ramdisk `tmpfs`. Os conjuntos de CPU são configuráveis por variável de ambiente, porque os padrões (0-11 e 12-15) são de uma máquina específica.
- **Confiabilidade e Verificação**:
  - Validação cruzada formal contra gabarito matemático em Python (`verify_cross.py`).
  - Nenhum tempo entra no pódio sem a saída ser validada: o harness decodifica cada resultado com um decoder de referência (Pillow com libjxl e libavif) e exige igualdade exata nos modos lossless e um PSNR mínimo nos lossy. Tarefa que falha aparece na seção "Falhas" do relatório e o script termina com código 1.
  - Pódio e tabelas comparativas atualizados automaticamente em [`results/PODIUM.md`](results/PODIUM.md), com razão geométrica por operação, PSNR por tarefa lossy e comparação a qualidade equivalente para AVIF e JXL.

# 📋 Motivo
Depois de inúmeras discussões sobre qual linguagem tem o melhor processamento de imagem (entre Go e Rust), desisti de apenas discutir e resolvi implementar um benchmark prático e rigoroso para isso. (OBS: sabemos que o resultado não depende apenas da velocidade bruta da linguagem, mas fundamentalmente da maturidade de cada ecossistema e das escolhas de implementação das bibliotecas e codecs utilizados).

# 💻 Como iniciar

### Requisitos
Para executar os componentes localmente ou reproduzir os benchmarks, certifique-se de ter instalado:
- [Go](https://go.dev/dl/) (versão recomendada: **1.24+** ou **1.27**)
- [Rust & Cargo](https://www.rust-lang.org/tools/install) via `rustup`: o toolchain é fixado em **1.97.0** por [`rust-toolchain.toml`](rust-toolchain.toml) e o `rustup` o instala sozinho. A mesma versão é usada no CI e em `docker/rust.Dockerfile` (`scripts/check-toolchain-sync.sh` confere)
- [Python 3](https://www.python.org/downloads/) (versão recomendada: **3.10+**) e, para o benchmark, `pip install -r harness/requirements.txt` (Pillow com libjxl e libavif: o decoder de referência do harness; só o harness os usa, os engines continuam puros)
- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/install/) (opcional, para execução isolada em containers)
- Ferramentas opcionais para o harness local: [oha](https://github.com/hatoo/oha) 1.16 (só para `--mode load`) e, para gerar o corpus com os codecs de referência, `webp`, `libavif-bin`, `libjpeg-turbo-progs`, `libjxl-tools` (sem elas o gerador usa o Pillow)

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

- **Executar a suíte de benchmarks completa via HTTP** (o perfil `bench` roda servidores e harness **sem** limites de CPU nem de memória):
  ```sh
  docker compose --profile bench up --build
  ```

- **Executar com isolamento estrito de CPU e cgroups** (o isolamento está no perfil `bench-isolated`, não em `bench`):
  ```sh
  docker compose --profile bench-isolated up --build
  ```

  Os padrões (servidores nas CPUs 0-11, harness nas 12-15, 6 CPUs e 3 GiB por servidor) são de uma máquina de 16 CPUs lógicas com 12 núcleos de desempenho e **não servem para qualquer hardware**. Ajuste conforme o `lscpu -e` da sua máquina, sem sobrepor os dois conjuntos:
  ```sh
  ARENA_SERVER_CPUSET=0-3 ARENA_HARNESS_CPUSET=4-5 ARENA_SERVER_CPUS=2.0 ARENA_HARNESS_CPUS=2.0 \
    docker compose --profile bench-isolated up --build
  ```
  Variáveis: `ARENA_SERVER_CPUSET`, `ARENA_SERVER_CPUS`, `ARENA_SERVER_MEMORY`, `ARENA_HARNESS_CPUSET`, `ARENA_HARNESS_CPUS`, `ARENA_HARNESS_MEMORY`, `ARENA_GOMAXPROCS`. O container do harness roda sem root: para gravar em `./results`, passe `ARENA_UID=$(id -u) ARENA_GID=$(id -g)`.

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

   # Testes do harness (regra de empate, razão geométrica, busca do q equivalente, parser do oha, recusa de saídas inválidas)
   python3 -m unittest discover -s harness/tests
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

5. **Executar o Benchmark da Arena** (`pip install -r harness/requirements.txt` antes):
   ```sh
   # Modo batch: cronometra o PROCESSO inteiro (startup incluído; não mede velocidade de codec).
   # Atualiza results/PODIUM.md e results/benchmark_results.json
   python3 harness/benchmark_arena.py --mode batch

   # Modo http: com os servidores em execução, mede o tempo de CODEC que o servidor reporta (X-Arena-*-Ns)
   python3 harness/benchmark_arena.py --mode http --go-url http://localhost:8080/run --rust-url http://localhost:8081/run

   # Modo load: carga concorrente com o oha (p50/p95/p99 e req/s), gera results/LOAD.md e benchmark_load.json
   python3 harness/benchmark_arena.py --mode load --duration 10 --concurrency 8
   ```
   Cada saída é validada contra o decoder de referência antes de o tempo valer (`--no-validate` desliga, e o relatório registra isso). Tarefas com falha aparecem na seção "Falhas" e o código de saída é 1 (`--allow-failures` ignora). A comparação a qualidade equivalente de AVIF e JXL lossy roda por padrão (`--no-equal-quality` pula). Arquivos temporários vão para `ARENA_TMPDIR` ou para o `tmpfs_path` de `arena.toml`, quando existe.

6. **Corpus grande (4,19 MP por classe)**. O corpus versionado tem 512×512 (0,26 MP); nessa escala, custos fixos como o startup do Go pesam mais que o codec. O corpus de 2048×2048 é gerado em ~20 s, fora do git:
   ```sh
   python3 harness/generators/make_corpus.py --large
   python3 harness/benchmark_arena.py --mode http --corpus-dir harness/fixtures/corpus-large
   # Go e Rust, um contra o outro, sem gabarito (não há oráculo Python rápido para 4 MP):
   python3 harness/verify_cross.py --mode compare
   ```
   Contexto da decisão sobre o custo de `init()` do JXL no Go: [`docs/decisions/0001-go-jxl-init-cost.md`](docs/decisions/0001-go-jxl-init-cost.md).

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

### Limites de requisição e códigos de status

Os dois servidores validam `op`, formato (inclusive o de origem em `decode` e `transcode`), `mode`, `q` e `effort` **antes** de processar a imagem, e aplicam os mesmos limites, definidos em [`arena.toml`](arena.toml) (`[limits]`) e verificados por testes em Go e em Rust:

| Situação | Resposta |
|---|---|
| Corpo acima de `max_body_bytes` (padrão 256 MiB, `ARENA_MAX_BODY_BYTES`) | **413** |
| PAM com `WIDTH*HEIGHT` acima de `max_pixels` (padrão 40 MP, `ARENA_MAX_PIXELS`), ou raster declarado maior que o corpo | **400**, sem alocar o raster |
| Formato, modo, `q` ou `effort` inválido; combinação não suportada (`avif` lossless); arquivo corrompido | **400** |
| JPEG com lado acima de 65.535 px, WebP com lado acima de 16.383 px | **400** |
| Falha real do encoder | 500 |

Os `arena-batch` aplicam `ARENA_MAX_PIXELS` também. O servidor Go tem `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout` e `MaxHeaderBytes`; o cabeçalho PAM aceita qualquer espaço em branco entre chave e valor (como a especificação) e tem tamanho limitado. O perfil release do Rust usa `panic = unwind`, de modo que um panic em uma requisição devolve 500 e não derruba o processo.

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

Tempo só é comparável junto do tamanho de saída e da qualidade: o pódio mostra os bytes de Go e de Rust, a razão Go/Rust e o PSNR RGB de cada tarefa lossy (contra o original, decodificado pela referência; `exato` quando idêntico). Para AVIF e JXL lossy há ainda uma comparação a **qualidade equivalente**: o alvo é o PSNR do Go no `q` padrão, o Rust procura o menor `q` que o alcança, e tamanho e tempo são medidos nesses `q`.

Conversão de 16 para 8 bits (PNG e AVIF de alta profundidade): `round(v/257)` nos dois engines, a inversa exata da expansão `v8*257`.

# ⚠️ Limitações conhecidas

- **WebP animado é recusado** com erro nos dois engines: cada biblioteca compõe os quadros de um jeito (o blend do `image-webp` erra por um nível em relação aos decoders Go), então não existe um "primeiro quadro" portável.
- **JXL lossy com alpha não decodifica no Rust.** O `jxl-oxide` 0.12.6 (mesmo com o guard de `rust/vendor/jxl-modular`) falha com `UnexpectedEof` ao ler o arquivo que o próprio encoder Rust gera para a imagem RGBA do corpus (a partir do `effort` JXL 3, isto é, `effort` ≥ 4 no contrato; nos JXL 1 e 2 decodifica). O libjxl e o `gen2brain/jxl` decodificam o mesmo arquivo. O caso está excluído, de forma explícita, dos testes de PSNR do Rust (`known_decoder_defect`), e um teste canário falha assim que o decoder passar a aceitá-lo. Ver a issue de remoção do vendor.
- **`jxl-encoder` 0.3.1 escreve streams inválidos nos `effort` 9 e 10 (lossless) e em `PixelLayout::GrayAlpha8`.** Nos efforts 9 e 10 o libjxl recusa os arquivos (`Generic Error`) e, na imagem alpha, o encode não termina em 180 s; o `effort` 8 funciona. Por isso o contrato limita o JXL a `effort` 7, e um teste falha se alguém subir esse teto. O `GrayAlpha8` é recusado por três decoders. Os rascunhos dos relatórios para os projetos a montante, com arquivos de reprodução, estão em [`docs/upstream/`](docs/upstream/README.md) (nada foi publicado).
- **`jxl-encoder` 0.3.1 escreve linhas `DIAG ...` em stderr** (um `eprintln!` incondicional no caminho de árvore do modular) em `mode=lossless` com `effort=10`. A saída não é afetada e não dá para suprimir sem patchear a dependência; o harness captura o stderr dos binários, e no servidor as linhas vão para o log do processo.
- **`./scripts/check-purity-go.sh --portable` falha hoje, por limitação conhecida:** `github.com/deepteams/webp` traz assembly Go (`.s`) que não respeita `-tags noasm`. Assembly Go não é CGO nem FFI, então a verificação padrão (a do CI) passa; o modo `--portable` é uma auditoria opcional e está documentado no cabeçalho do script.
- **Custo de `init()` do `gen2brain/jxl` (~38 ms) no Go**, pago no startup de cada processo: o modo batch o mostra à parte; ver [`docs/decisions/0001-go-jxl-init-cost.md`](docs/decisions/0001-go-jxl-init-cost.md).
- **Licenciamento:** o projeto é AGPL-3.0-or-later e sete dependências Rust são AGPL-3.0-only; as consequências estão na seção [Licença](#-licença).

- **AVIF lossless não é suportado.** Nenhuma biblioteca pura disponível preserva o RGB no round-trip, então `mode=lossless` com `format=avif` retorna erro nos dois lados e o modo não faz parte do benchmark:
  - Go: `KarpelesLab/goavif` ignora `Options.Lossless` (a saída é idêntica com e sem a opção) e `gen2brain/gav1d/avif` sempre converte RGB para YCbCr BT.601 4:2:0 (na foto do corpus, 236.705 bytes RGB divergem, com erro de até 55).
  - Rust: `zenrav1e` (usado por `zenravif`) força `base_q_idx >= 1`, então `quantizer 0` nunca ativa o modo lossless do AV1 (na foto do corpus, 42.803 bytes RGB divergem mesmo com matriz identidade).

# 📜 Licença

O código deste repositório é distribuído sob a **GNU Affero General Public License v3.0 ou posterior** (`AGPL-3.0-or-later`); o texto está em [`LICENSE`](LICENSE).

A escolha segue as dependências. Sete crates Rust são licenciados como `AGPL-3.0-only OR LicenseRef-Imazen-Commercial`: `jxl-encoder`, `jxl-encoder-simd`, `rav1d-safe`, `zenavif`, `zenrav1e`, `zenravif` e `zenwebp`. Usamos a opção AGPL (a licença comercial não foi adquirida e **não** está na lista de licenças permitidas). Na prática:

- Binários do engine Rust (`arena-server`, `arena-batch`) são distribuídos sob a AGPL-3.0: o `-only` dessas dependências prevalece sobre o `or-later` do código deste repositório.
- Quem **serve a arena em rede** (o `arena-server`, em Go ou em Rust) deve oferecer o código-fonte correspondente aos usuários que interagem com ela (AGPL, seção 13). Para uso interno e para rodar o benchmark localmente nada muda.
- Contribuições são aceitas sob a mesma licença (AGPL-3.0-or-later).

| Componente | Licença | Observação |
|---|---|---|
| Código deste repositório | AGPL-3.0-or-later | `LICENSE`; `license` em `rust/Cargo.toml` |
| `jxl-encoder`, `jxl-encoder-simd`, `rav1d-safe`, `zenavif`, `zenrav1e`, `zenravif`, `zenwebp` (Rust) | AGPL-3.0-only (opção de `... OR LicenseRef-Imazen-Commercial`) | Permitidas por exceção **nomeada** em `rust/deny.toml`; uma nova dependência AGPL falha o CI até alguém decidir |
| Demais crates Rust | MIT, Apache-2.0, BSD-2/3-Clause, MPL-2.0, Zlib, CC0-1.0, Unicode-3.0, IJG | `cargo deny --manifest-path rust/Cargo.toml check licenses` roda no CI |
| `KarpelesLab/goavif`, `KarpelesLab/gowebp`, `deepteams/webp` (Go) | MIT | |
| `gen2brain/gav1d` (porta do dav1d), `gen2brain/jxl`, `golang.org/x/image`, `golang.org/x/text` (Go) | BSD-2-Clause / BSD-3-Clause | |
| `rust/vendor/jxl-modular` | MIT OR Apache-2.0 | cópia do `jxl-modular` 0.11.3 com um guard local (ver `rust/vendor/jxl-modular/LICENSE-*`) |
| Ferramentas do harness (`Pillow`: MIT-CMU; `pillow-jxl-plugin`: GPL-3.0-or-later; `oha`: MIT; libjxl, libavif, libwebp: BSD) | várias | Só medem e validam; não entram nos binários dos engines. A imagem `docker/harness.Dockerfile` as inclui, então quem a redistribuir deve cumprir também essas licenças |

# 📊 Resultados e Pódio
Os resultados consolidados da arena, comparativos de latência, throughput em Megapixels por segundo (MP/s) e detalhamento por codec estão documentados em:
👉 [`results/PODIUM.md`](results/PODIUM.md)

# 🤝 Contribuidores
<a href="https://github.com/bgluis/image-processor-arena/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=bgluis/image-processor-arena"/>
</a>
