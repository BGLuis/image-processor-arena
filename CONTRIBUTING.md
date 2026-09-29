# Contribuindo com o Image Processor Arena / Contributing to Image Processor Arena

[🇧🇷 Português](#-guia-de-contribuição-português) • [🇺🇸 English](#-contribution-guide-english)

---

## 🇧🇷 Guia de Contribuição (Português)

Agradecemos o seu interesse em contribuir com a **Image Processor Arena**! Este projeto é um benchmark rigoroso e aberto para comparar implementações puras de processamento de imagem em Go e Rust.

### 🛡️ Regra de Ouro: Pureza Absoluta (0% CGO / 0% FFI)
Qualquer contribuição **deve** respeitar a política de pureza:
- **Go**: `CGO_ENABLED=0`. É proibido o uso de Cgo, `purego`, `wazero` ou bibliotecas com dependências nativas em C.
- **Rust**: Não são permitidos `cc`, `cmake`, `bindgen`, `nasm-rs`, `pkg-config` ou chaves `links` no `Cargo.toml`.
- Antes de submeter código, execute os scripts de pureza:
  ```bash
  ./scripts/check-purity-go.sh
  ./scripts/check-purity-rust.sh
  ```

---

### 🚀 Fluxo de Trabalho de Desenvolvimento

1. **Faça um Fork e Clone**:
   ```bash
   git clone https://github.com/SEU_USUARIO/image-processor-arena.git
   cd image-processor-arena
   ```

2. **Crie uma Branch Temática**:
   - `feat/nome-da-feature` para novas funcionalidades ou codecs puros.
   - `fix/descricao-do-bug` para correções de bugs.
   - `perf/otimizacao` para otimizações de algoritmos ou métricas.
   - `docs/melhoria` para atualizações de documentação.

3. **Padronização e Qualidade de Código**:
   - **Go**:
     ```bash
     cd go
     go fmt ./...
     go vet ./...
     go test -v ./...
     cd ..
     ```
   - **Rust**:
     ```bash
     cargo fmt --manifest-path rust/Cargo.toml --all
     cargo clippy --manifest-path rust/Cargo.toml --all-targets -- -D warnings
     cargo test --manifest-path rust/Cargo.toml
     ```

4. **Validação Cruzada (Cross-Validation)**:
   Se alterar a lógica de encoders, decoders ou métricas em `docs/analyze-spec.md`, garanta que os resultados batem com o gabarito matemático em Python:
   ```bash
   python3 harness/verify_cross.py --mode batch --target all
   ```

5. **Execução de Benchmarks**:
   Para validar o impacto de performance das alterações:
   ```bash
   python3 harness/benchmark_arena.py --mode batch
   ```

6. **Envie um Pull Request**:
   - Abra um Pull Request contra a branch `main`.
   - Preencha o template de PR detalhando as alterações e os testes realizados.

---

## 🇺🇸 Contribution Guide (English)

Thank you for your interest in contributing to **Image Processor Arena**! This project provides a rigorous, transparent benchmark comparing pure image processing implementations in Go and Rust.

### 🛡️ Golden Rule: Absolute Purity (0% CGO / 0% FFI)
Every single contribution **must** adhere to our strict purity rule:
- **Go**: `CGO_ENABLED=0`. Using Cgo, `purego`, `wazero`, or wrappers around native C libraries is strictly prohibited.
- **Rust**: Dependencies utilizing `cc`, `cmake`, `bindgen`, `nasm-rs`, `pkg-config`, or `links` in `Cargo.toml` are prohibited.
- Before submitting your code, run the purity check scripts:
  ```bash
  ./scripts/check-purity-go.sh
  ./scripts/check-purity-rust.sh
  ```

---

### 🚀 Development Workflow

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/image-processor-arena.git
   cd image-processor-arena
   ```

2. **Create a Topic Branch**:
   - `feat/feature-name` for new features or pure codecs.
   - `fix/bug-description` for bug fixes.
   - `perf/optimization` for metric or algorithm performance tuning.
   - `docs/improvement` for documentation updates.

3. **Code Quality and Standards**:
   - **Go**:
     ```bash
     cd go
     go fmt ./...
     go vet ./...
     go test -v ./...
     cd ..
     ```
   - **Rust**:
     ```bash
     cargo fmt --manifest-path rust/Cargo.toml --all
     cargo clippy --manifest-path rust/Cargo.toml --all-targets -- -D warnings
     cargo test --manifest-path rust/Cargo.toml
     ```

4. **Cross-Validation**:
   If modifying encoders, decoders, or analysis metrics specified in [`docs/analyze-spec.md`](docs/analyze-spec.md), verify parity against the Python reference:
   ```bash
   python3 harness/verify_cross.py --mode batch --target all
   ```

5. **Benchmark Verification**:
   To assess performance impacts:
   ```bash
   python3 harness/benchmark_arena.py --mode batch
   ```

6. **Submit a Pull Request**:
   - Open a PR against the `main` branch.
   - Complete the PR template describing your changes and verification steps.
