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
