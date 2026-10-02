<div align="center">

<!-- GitHub Status Badges -->
[![GitHub Stars](https://shieldcn.dev/github/stars/bgluis/image-processor-arena.svg?variant=secondary&size=sm)](https://github.com/bgluis/image-processor-arena/stargazers)
[![GitHub Forks](https://shieldcn.dev/github/forks/bgluis/image-processor-arena.svg?variant=secondary&size=sm)](https://github.com/bgluis/image-processor-arena/network/members)
[![Watchers](https://shieldcn.dev/github/watchers/bgluis/image-processor-arena.svg?variant=secondary&size=sm)](https://github.com/bgluis/image-processor-arena/watchers)
[![Contributors](https://shieldcn.dev/github/contributors/bgluis/image-processor-arena.svg?theme=emerald&size=sm)](https://github.com/bgluis/image-processor-arena/graphs/contributors)
[![CI](https://github.com/bgluis/image-processor-arena/actions/workflows/ci.yml/badge.svg)](https://github.com/bgluis/image-processor-arena/actions/workflows/ci.yml)

<br/>

<!-- Technology Badges -->
![Go](https://shieldcn.dev/badge/Go-00ADD8.svg?logo=go&logoColor=white&variant=branded&size=sm)
![Rust](https://shieldcn.dev/badge/Rust-DEA584.svg?logo=rust&logoColor=white&variant=branded&size=sm)
![Python](https://shieldcn.dev/badge/Python-3776AB.svg?logo=python&logoColor=white&variant=branded&size=sm)
![Docker](https://shieldcn.dev/badge/Docker-2496ED.svg?logo=docker&logoColor=white&variant=branded&size=sm)

  <h3>Image Processor Arena: Pure Go × Pure Rust</h3>
  High-precision benchmark arena comparing 100% pure image processing between Go and Rust under real-world workloads, with zero CGO or FFI.

  <p align="center">
    <a href="README.md">Português</a> • <b>English</b>
  </p>
</div>

# 📖 About
**Image Processor Arena** is a rigorous, high-performance benchmarking arena designed to measure, audit, and compare image processing performance between **100% Pure Go** and **100% Pure Rust** implementations under heavy workload.

The arena enforces a strict ecosystem purity rule: **zero CGO, zero FFI, zero compiled C dependencies, zero purego, and zero WASM**. Only safe, native code written in each respective language is allowed. Purity is validated through dedicated verification scripts (`./scripts/check-purity-*.sh`) and dependency tree audits via `cargo-deny` (`rust/deny.toml`).

### Key Highlights & Features:
- **Benchmarked Operations**:
  - `encode`: Encodes raw pixel buffers into compressed file formats.
  - `decode`: Decodes compressed images into in-memory pixel representations.
  - `transcode`: Direct format-to-format conversion without touching disk storage.
  - `analyze`: Simultaneous computation of 16 rigorous mathematical metrics (formally specified in [`docs/analyze-spec.md`](docs/analyze-spec.md)), including pHash (DCT-II), blurHash (base83), Spatial Information (Sobel), integer BT.601 luminance, color histograms, standard deviation, and Shannon entropy.
- **Supported Formats**: PNG, JPEG, WebP (lossy and lossless), AVIF (lossy only), and JPEG XL.
- **Canonical Interchange Format**: Binary Netpbm PAM (`P7`, `RGB` and `RGB_ALPHA` tuples, `MAXVAL 255`), guaranteeing an identical, uncompressed baseline between both engines.
- **Execution Modes**:
  - **Batch CLI**: High-throughput command-line binaries (`arena-batch`) for maximum I/O speed on disk or tmpfs ramdisks.
  - **HTTP Server**: Unified REST servers in Go (port 8080) and Rust (port 8081) with microsecond telemetry exposed via HTTP response headers (`X-Arena-*-Ns`).
  - **Concurrent load**: the benchmark's `--mode load` drives [`oha`](https://github.com/hatoo/oha) against both servers and reports p50/p95/p99 latency and throughput.
  - **Resource Isolation**: Docker Compose orchestration (the `bench-isolated` profile) with CPU pinning between servers and harness, memory limits, and tmpfs mounts. The CPU sets are configurable through environment variables because the defaults (0-11 and 12-15) belong to one specific machine.
- **Reliability & Verification**:
  - Bit-for-bit mathematical cross-validation against a Python reference ground truth (`verify_cross.py`).
  - No timing reaches the podium before its output is validated: the harness decodes every result with a reference decoder (Pillow with libjxl and libavif) and demands bit equality for lossless modes and a minimum PSNR for lossy ones. A failing task appears in the report's "Falhas" section and the script exits with code 1.
  - Automated benchmark reports and podium standings generated in [`results/PODIUM.md`](results/PODIUM.md), with a per-operation geometric-mean ratio, PSNR for every lossy task, and an equal-quality comparison for AVIF and JXL.

# 📋 Motivation
After countless debates about which language has better image processing performance (between Go and Rust), I decided to stop arguing and build an empirical, rigorous benchmark arena for it. (Note: we know that performance depends not merely on raw language execution speed, but fundamentally on ecosystem maturity and the specific design choices made by codec and library authors).

# 💻 Getting Started

### Prerequisites
To run the components locally or reproduce benchmarks, make sure you have installed:
- [Go](https://go.dev/dl/) (recommended version: **1.24+** or **1.27**)
- [Rust & Cargo](https://www.rust-lang.org/tools/install) through `rustup`: the toolchain is pinned to **1.97.0** by [`rust-toolchain.toml`](rust-toolchain.toml) and `rustup` installs it on its own. CI and `docker/rust.Dockerfile` use the same version (`scripts/check-toolchain-sync.sh` checks it)
- [Python 3](https://www.python.org/downloads/) (recommended version: **3.10+**) and, for the benchmark, `pip install -r harness/requirements.txt` (Pillow with libjxl and libavif: the harness's reference decoder; only the harness uses them, the engines stay pure)
- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (optional, recommended for isolated and repeatable hardware testing)
- Optional harness tools: [oha](https://github.com/hatoo/oha) 1.16 (only for `--mode load`) and, to generate the corpus with the reference codecs, `webp`, `libavif-bin`, `libjpeg-turbo-progs`, `libjxl-tools` (the generator falls back to Pillow without them)

### Installation

1. Clone the project repository:
   ```sh
   git clone https://github.com/bgluis/image-processor-arena.git
   ```

2. Navigate to the project directory:
   ```sh
   cd image-processor-arena
   ```

---

#### Method 1: Using Docker Compose (Recommended)

Docker Compose builds minimal multi-stage images and isolates CPU/memory resources automatically.

- **Start servers in development mode**:
  ```sh
  docker compose --profile dev up --build
  ```

- **Run the automated benchmark suite via HTTP** (the `bench` profile runs servers and harness with **no** CPU or memory limits):
  ```sh
  docker compose --profile bench up --build
  ```

- **Run with hardware core pinning and cgroups isolation** (isolation lives in the `bench-isolated` profile, not in `bench`):
  ```sh
  docker compose --profile bench-isolated up --build
  ```

  The defaults (servers on CPUs 0-11, harness on 12-15, 6 CPUs and 3 GiB per server) come from a 16-logical-CPU machine with 12 performance cores and **do not suit every machine**. Adjust them to your `lscpu -e`, keeping the two sets disjoint:
  ```sh
  ARENA_SERVER_CPUSET=0-3 ARENA_HARNESS_CPUSET=4-5 ARENA_SERVER_CPUS=2.0 ARENA_HARNESS_CPUS=2.0 \
    docker compose --profile bench-isolated up --build
  ```
  Variables: `ARENA_SERVER_CPUSET`, `ARENA_SERVER_CPUS`, `ARENA_SERVER_MEMORY`, `ARENA_HARNESS_CPUSET`, `ARENA_HARNESS_CPUS`, `ARENA_HARNESS_MEMORY`, `ARENA_GOMAXPROCS`. The harness container runs as non-root: to write to `./results`, pass `ARENA_UID=$(id -u) ARENA_GID=$(id -g)`.

---

#### Method 2: Native Host Execution

If you prefer running the binaries and harness directly on your host machine:

1. **Verify Ecosystem Purity (0% CGO / FFI)**:
   ```sh
   ./scripts/check-purity-go.sh
   ./scripts/check-purity-rust.sh
   ```

2. **Run Unit Tests**:
   ```sh
   # Go unit tests
   (cd go && go test -v ./...)

   # Rust unit tests
   cargo test --manifest-path rust/Cargo.toml

   # Harness tests (tie rule, geometric mean, equal-quality search, oha parser, refusal of bad outputs)
   python3 -m unittest discover -s harness/tests
   ```

3. **Start HTTP Servers**:
   ```sh
   # Go server (Port 8080)
   PORT=8080 go run ./go/cmd/server/main.go

   # Rust server (Port 8081 - in another terminal)
   PORT=8081 cargo run --manifest-path rust/Cargo.toml --bin arena-server --release
   ```

4. **Run Cross-Validation (16/16 fixtures against Python ground truth)**:
   ```sh
   # Batch CLI mode
   python3 harness/verify_cross.py --mode batch --target all

   # HTTP mode
   python3 harness/verify_cross.py --mode http --target go
   python3 harness/verify_cross.py --mode http --target rust
   ```

5. **Run the Arena Benchmark Suite** (`pip install -r harness/requirements.txt` first):
   ```sh
   # batch mode: times the whole PROCESS (startup included; not codec speed).
   # Updates results/PODIUM.md and results/benchmark_results.json
   python3 harness/benchmark_arena.py --mode batch

   # http mode: against running servers, measures the CODEC time the server reports (X-Arena-*-Ns)
   python3 harness/benchmark_arena.py --mode http --go-url http://localhost:8080/run --rust-url http://localhost:8081/run

   # load mode: concurrent load with oha (p50/p95/p99 and req/s), writes results/LOAD.md and benchmark_load.json
   python3 harness/benchmark_arena.py --mode load --duration 10 --concurrency 8
   ```
   Every output is validated against the reference decoder before its time counts (`--no-validate` disables it, and the report records that). Failing tasks appear in the "Falhas" section and the exit code is 1 (`--allow-failures` ignores it). The equal-quality comparison of lossy AVIF and JXL runs by default (`--no-equal-quality` skips it). Temporary files go to `ARENA_TMPDIR` or to the `tmpfs_path` of `arena.toml` when it exists.

6. **Large corpus (4.19 MP per class)**. The versioned corpus is 512×512 (0.26 MP); at that scale fixed costs such as Go's startup outweigh the codec. The 2048×2048 corpus takes ~20 s to generate and is kept out of git:
   ```sh
   python3 harness/generators/make_corpus.py --large
   python3 harness/benchmark_arena.py --mode http --corpus-dir harness/fixtures/corpus-large
   # Go against Rust, no ground truth (there is no fast Python oracle for 4 MP):
   python3 harness/verify_cross.py --mode compare
   ```
   Background for the decision on Go's JXL `init()` cost: [`docs/decisions/0001-go-jxl-init-cost.md`](docs/decisions/0001-go-jxl-init-cost.md) (Portuguese).

# 🔌 HTTP Contract and Parameters

Both servers and both `arena-batch` binaries share one parameter contract, defined in [`arena.toml`](arena.toml) (`[params]`) and enforced by tests in Go and Rust: `q` is an integer 1..100 (default 75), `effort` is an integer 1..10 (default 4), `mode` is `lossy` or `lossless` (default `lossy`). Out-of-range or non-numeric values return HTTP 400 (batch exits with status 1) and are never clamped. The per-codec mapping of `q` and `effort` is documented in the Portuguese [README](README.md#-contrato-http-e-parâmetros).

Both servers validate `op`, the formats (including the source format of `decode` and `transcode`), `mode`, `q` and `effort` **before** processing the image, and enforce the same limits, defined in [`arena.toml`](arena.toml) (`[limits]`) and checked by tests in both engines:

| Situation | Response |
|---|---|
| Body above `max_body_bytes` (default 256 MiB, `ARENA_MAX_BODY_BYTES`) | **413** |
| PAM with `WIDTH*HEIGHT` above `max_pixels` (default 40 MP, `ARENA_MAX_PIXELS`), or a declared raster larger than the body | **400**, without allocating the raster |
| Invalid format, mode, `q` or `effort`; unsupported combination (`avif` lossless); corrupt file | **400** |
| JPEG with a side above 65,535 px, WebP with a side above 16,383 px | **400** |
| Real encoder failure | 500 |

The `arena-batch` binaries honour `ARENA_MAX_PIXELS` too. The Rust release profile uses `panic = unwind`, so a panic inside one request returns 500 and does not take the process down. 16-bit samples (PNG, AVIF) are reduced to 8 bits as `round(v/257)` in both engines.

# ⚠️ Known Limitations

- **Animated WebP is refused** with an error in both engines: each library composites frames differently (`image-webp`'s blend is off by one level against the Go decoders), so there is no portable "first frame".
- **Lossy JXL with alpha does not decode in Rust.** `jxl-oxide` 0.12.6 (even with the `rust/vendor/jxl-modular` guard) fails with `UnexpectedEof` on the file the Rust encoder itself writes for the corpus RGBA image (from JXL effort 3, i.e. contract `effort` ≥ 4; JXL efforts 1 and 2 decode). libjxl and `gen2brain/jxl` decode the same file. The case is explicitly excluded from the Rust PSNR tests (`known_decoder_defect`), and a canary test fails as soon as the decoder accepts it. See the vendor-removal issue.
- **`jxl-encoder` 0.3.1 writes invalid streams at lossless `effort` 9 and 10 and for `PixelLayout::GrayAlpha8`.** At efforts 9 and 10 libjxl rejects the files (`Generic Error`) and on the alpha image the encode does not finish in 180 s; `effort` 8 works. That is why the contract caps JXL at `effort` 7, and a test fails if the cap is raised. `GrayAlpha8` is rejected by three decoders. Draft reports for the upstream projects, with reproduction files, are in [`docs/upstream/`](docs/upstream/README.md) (nothing was published).
- **`jxl-encoder` 0.3.1 writes `DIAG ...` lines to stderr** (an unconditional `eprintln!` in the modular tree path) for `mode=lossless` with `effort=10`. The output is unaffected and it cannot be silenced without patching the dependency; the harness captures the binaries' stderr, and in the server the lines go to the process log.
- **`./scripts/check-purity-go.sh --portable` fails today, as a known limitation:** `github.com/deepteams/webp` ships Go assembly (`.s`) that ignores `-tags noasm`. Go assembly is neither CGO nor FFI, so the default check (the CI one) passes; `--portable` is an optional audit, documented in the script header.
- **Go's `gen2brain/jxl` `init()` costs ~38 ms**, paid at every process start: batch mode reports it separately; see [`docs/decisions/0001-go-jxl-init-cost.md`](docs/decisions/0001-go-jxl-init-cost.md).
- **Licensing:** the project is AGPL-3.0-or-later and seven Rust dependencies are AGPL-3.0-only; the consequences are in the [License](#-license) section.

- **AVIF lossless is not supported.** No available pure library preserves RGB on a round trip, so `mode=lossless` with `format=avif` returns an error on both sides and the mode is not part of the benchmark:
  - Go: `KarpelesLab/goavif` ignores `Options.Lossless` (the output is identical with and without it) and `gen2brain/gav1d/avif` always converts RGB to BT.601 4:2:0 YCbCr (on the corpus photo, 236,705 RGB bytes differ, with error up to 55).
  - Rust: `zenrav1e` (used by `zenravif`) forces `base_q_idx >= 1`, so `quantizer 0` never enables AV1 lossless mode (on the corpus photo, 42,803 RGB bytes differ even with the identity matrix).

# 📜 License

The code in this repository is distributed under the **GNU Affero General Public License v3.0 or later** (`AGPL-3.0-or-later`); the text is in [`LICENSE`](LICENSE).

The choice follows the dependencies. Seven Rust crates are licensed as `AGPL-3.0-only OR LicenseRef-Imazen-Commercial`: `jxl-encoder`, `jxl-encoder-simd`, `rav1d-safe`, `zenavif`, `zenrav1e`, `zenravif` and `zenwebp`. We use the AGPL option (the commercial license has not been acquired and is **not** in the allowed-license list). In practice:

- Binaries of the Rust engine (`arena-server`, `arena-batch`) are distributed under the AGPL-3.0: the `-only` of those dependencies prevails over the `or-later` of this repository's code.
- Anyone who **serves the arena over a network** (`arena-server`, Go or Rust) must offer the corresponding source to the users who interact with it (AGPL, section 13). Internal use and running the benchmark locally are unaffected.
- Contributions are accepted under the same license (AGPL-3.0-or-later).

| Component | License | Notes |
|---|---|---|
| Code in this repository | AGPL-3.0-or-later | `LICENSE`; `license` in `rust/Cargo.toml` |
| `jxl-encoder`, `jxl-encoder-simd`, `rav1d-safe`, `zenavif`, `zenrav1e`, `zenravif`, `zenwebp` (Rust) | AGPL-3.0-only (the option of `... OR LicenseRef-Imazen-Commercial`) | Allowed by **named** exception in `rust/deny.toml`; a new AGPL dependency fails CI until someone decides |
| Other Rust crates | MIT, Apache-2.0, BSD-2/3-Clause, MPL-2.0, Zlib, CC0-1.0, Unicode-3.0, IJG | `cargo deny --manifest-path rust/Cargo.toml check licenses` runs in CI |
| `KarpelesLab/goavif`, `KarpelesLab/gowebp`, `deepteams/webp` (Go) | MIT | |
| `gen2brain/gav1d` (dav1d port), `gen2brain/jxl`, `golang.org/x/image`, `golang.org/x/text` (Go) | BSD-2-Clause / BSD-3-Clause | |
| `rust/vendor/jxl-modular` | MIT OR Apache-2.0 | copy of `jxl-modular` 0.11.3 with one local guard (see `rust/vendor/jxl-modular/LICENSE-*`) |
| Harness tools (`Pillow`: MIT-CMU; `pillow-jxl-plugin`: GPL-3.0-or-later; `oha`: MIT; libjxl, libavif, libwebp: BSD) | various | They only measure and validate; they are not part of the engine binaries. `docker/harness.Dockerfile` includes them, so whoever redistributes that image must honour those licenses too |

# 📊 Results & Podium
Consolidated benchmark findings, latency comparisons, throughput numbers in Megapixels per second (MP/s), and codec-by-codec analyses are documented in:
👉 [`results/PODIUM.md`](results/PODIUM.md)

# 🤝 Contributors
<a href="https://github.com/bgluis/image-processor-arena/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=bgluis/image-processor-arena"/>
</a>
