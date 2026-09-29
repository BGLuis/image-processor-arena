## 📋 Descrição / Description

<!-- Descreva de forma concisa as mudanças introduzidas por este Pull Request. -->
<!-- Concisely describe the changes introduced by this Pull Request. -->

---

## 🏷️ Tipo de Alteração / Type of Change

- [ ] 🐛 Correção de Bug / Bug fix
- [ ] ✨ Nova Funcionalidade / New feature (novo codec puro, nova métrica, etc.)
- [ ] ⚡ Otimização de Performance / Performance optimization
- [ ] 🧪 Testes ou Benchmarks / Tests or benchmarks
- [ ] 📝 Documentação / Documentation
- [ ] 🔧 Infraestrutura ou Docker / Tooling or CI/CD

---

## 🛡️ Checklist de Pureza Absoluta (Obrigatório)

> [!IMPORTANT]
> A política fundamental desta arena é a inexistência de CGO ou FFI em tempo de compilação ou execução.

- [ ] **Go**: Nenhuma biblioteca CGO ou dependência com wrappers C foi adicionada (`CGO_ENABLED=0`).
- [ ] **Rust**: Nenhuma dependência utiliza `cc`, `cmake`, `bindgen`, `nasm-rs`, `pkg-config` ou chaves `links` no `Cargo.toml`.
- [ ] Os scripts de pureza foram executados e passaram com êxito:
  ```bash
  ./scripts/check-purity-go.sh
  ./scripts/check-purity-rust.sh
  ```

---

## 🧪 Testes e Validação Realizados / Verification Performed

- [ ] Testes unitários do Go executados com sucesso: `(cd go && go test -v ./...)`
- [ ] Testes unitários do Rust executados com sucesso: `cargo test --manifest-path rust/Cargo.toml`
- [ ] Validação cruzada (cross-validation) executada contra o gabarito: `python3 harness/verify_cross.py --mode batch --target all`
- [ ] Resultados de benchmarks atualizados (se aplicável): `python3 harness/benchmark_arena.py --mode batch`

---

## 🔗 Issues Relacionadas / Related Issues

Closes #
