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
- **Supported Formats**: PNG, JPEG, WebP (lossy and lossless), AVIF (lossy and lossless), and JPEG XL.
- **Canonical Interchange Format**: Binary Netpbm PAM (`P7`, `RGB` and `RGB_ALPHA` tuples, `MAXVAL 255`), guaranteeing an identical, uncompressed baseline between both engines.
- **Execution Modes**:
  - **Batch CLI**: High-throughput command-line binaries (`arena-batch`) for maximum I/O speed on disk or tmpfs ramdisks.
  - **HTTP Server**: Unified REST servers in Go (port 8080) and Rust (port 8081) with microsecond telemetry exposed via HTTP response headers (`X-Arena-*-Ns`).
  - **Resource Isolation**: Docker Compose orchestration with CPU pinning (P-cores 0-11 for servers, E-cores 12-15 for the load harness), strict 3 GiB memory limits, and tmpfs mounts.
- **Reliability & Verification**:
  - Bit-for-bit mathematical cross-validation against a Python reference ground truth (`verify_cross.py`).
  - Automated benchmark reports and podium standings generated in [`results/PODIUM.md`](results/PODIUM.md).

# 📋 Motivation
After countless debates about which language has better image processing performance (between Go and Rust), I decided to stop arguing and build an empirical, rigorous benchmark arena for it. (Note: we know that performance depends not merely on raw language execution speed, but fundamentally on ecosystem maturity and the specific design choices made by codec and library authors).

# 💻 Getting Started

### Prerequisites
To run the components locally or reproduce benchmarks, make sure you have installed:
- [Go](https://go.dev/dl/) (recommended version: **1.24+** or **1.27**)
- [Rust & Cargo](https://www.rust-lang.org/tools/install) (recommended version: **1.85+**, 2021 edition)
- [Python 3](https://www.python.org/downloads/) (recommended version: **3.10+**)
- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) (optional, recommended for isolated and repeatable hardware testing)
- Optional harness tools: [oha](https://github.com/hatoo/oha), [hyperfine](https://github.com/sharkdp/hyperfine), `webp`, `libavif-bin`, `libjpeg-turbo-progs`, `libjxl-tools`

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

- **Run the automated benchmark suite via HTTP**:
  ```sh
  docker compose --profile bench up --build
  ```

- **Run benchmarks with hardware core pinning and cgroups isolation (P-cores & E-cores)**:
  ```sh
  docker compose --profile bench-isolated up --build
  ```

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

5. **Run the Arena Benchmark Suite**:
   ```sh
   # Full batch benchmark (updates results/PODIUM.md and results/benchmark_results.json)
   python3 harness/benchmark_arena.py --mode batch

   # HTTP benchmark against running server instances
   python3 harness/benchmark_arena.py --mode http --go-url http://localhost:8080/run --rust-url http://localhost:8081/run
   ```

# 📊 Results & Podium
Consolidated benchmark findings, latency comparisons, throughput numbers in Megapixels per second (MP/s), and codec-by-codec analyses are documented in:
👉 [`results/PODIUM.md`](results/PODIUM.md)

# 🤝 Contributors
<a href="https://github.com/bgluis/image-processor-arena/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=bgluis/image-processor-arena"/>
</a>
