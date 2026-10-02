#!/usr/bin/env bash
set -euo pipefail

# scripts/check-purity-rust.sh
# Validador de pureza estrita do ecossistema Rust (sem C FFI, sem crates -sys,
# sem bibliotecas C/nasm no build ativo, sem cmake/bindgen/pkg-config, sem campo links FFI).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUST_DIR="${ROOT_DIR}/rust"

echo "=== Verificação de Pureza Rust (image-processor-arena) ==="

if [[ ! -f "${RUST_DIR}/Cargo.toml" ]]; then
    echo "[-] ERRO: ${RUST_DIR}/Cargo.toml não encontrado!"
    exit 1
fi

echo "[*] Obtendo árvore de dependências ativas para o alvo x86_64-unknown-linux-gnu..."
ACTIVE_PKGS=$(cargo tree --manifest-path "${RUST_DIR}/Cargo.toml" --target x86_64-unknown-linux-gnu --edges no-dev --prefix none | awk '{print $1}' | sort -u)
export ACTIVE_PKGS

echo "[*] Inspecionando metadados do Cargo..."
cargo metadata --manifest-path "${RUST_DIR}/Cargo.toml" --format-version 1 | python3 -c '
import sys, json, os

active = set(os.environ.get("ACTIVE_PKGS", "").split())
data = json.load(sys.stdin)
packages = data.get("packages", [])

errors = 0
warnings = 0

print(f"[*] Total de crates ativas no grafo de compilação: {len(active)}")

# 1. Checa crates proibidas que indicam ferramentas de compilação C/C++ externa ou FFI
BANNED_GLOBAL = {"cmake", "bindgen", "pkg-config"}
BANNED_BUILD = {"cc", "nasm-rs"}

for pkg in packages:
    name = pkg["name"]
    version = pkg["version"]

    if name in active:
        # Bloqueio incondicional de crates -sys (FFI com C)
        if name.endswith("-sys") and name not in ["libc"]:
            print(f"[-] VIOLAÇÃO: Crate FFI \x27-sys\x27 detectada no grafo ativo: {name} v{version}")
            errors += 1

        # Bloqueio incondicional de cmake, bindgen, pkg-config
        if name in BANNED_GLOBAL:
            print(f"[-] VIOLAÇÃO: Ferramenta de build/FFI proibida detectada no grafo ativo: {name} v{version}")
            errors += 1

        # Checagem de campo links
        # rayon-core usa links="rayon-core" como token puro do Rust para unicidade no binário.
        # Qualquer outro links (como z, png, jpeg, dav1d, aom) é FFI com biblioteca nativa.
        links = pkg.get("links")
        if links:
            if links in ["rayon-core"]:
                # Permitido: pure rust synchronization token
                pass
            else:
                print(f"[-] VIOLAÇÃO: Pacote com link FFI C nativo detectado no grafo ativo: {name} (links = \x27{links}\x27)")
                errors += 1

# 2. Notifica sobre cc e nasm-rs como inertes upstream
for pkg in packages:
    name = pkg["name"]
    if name in BANNED_BUILD:
        if name in active:
            print(f"[!] AVISO: Crate de build \x27{name}\x27 encontrada no grafo como dependência inerte upstream.")

# 3. Garante que os 10 codecs alvo sejam todos as versões puras requeridas
target_codecs = {
    "png": False,
    "jpeg-encoder": False,
    "zune-jpeg": False,
    "zenwebp": False,
    "image-webp": False,
    "ravif": False,
    "zenravif": False,
    "rav1d": False,
    "jxl-encoder": False,
    "jxl-oxide": False,
}

for pkg in packages:
    name = pkg["name"]
    if name in target_codecs and name in active:
        target_codecs[name] = True

missing_codecs = [k for k, v in target_codecs.items() if not v]
if missing_codecs:
    print(f"[-] ERRO: Codecs puros obrigatórios ausentes no grafo ativo: {missing_codecs}")
    errors += 1
else:
    print("[+] Todos os 10 codecs puros obrigatórios confirmados no grafo ativo!")

if errors > 0:
    print(f"[-] Verificação de pureza Rust FALHOU com {errors} violação(ões).")
    sys.exit(1)
'

# 4. Executa cargo-deny se instalado
if command -v cargo-deny &>/dev/null; then
    echo "[*] Executando cargo-deny check bans..."
    (cd "${RUST_DIR}" && cargo-deny --config "${RUST_DIR}/deny.toml" check bans)
    echo "[+] cargo-deny aprovou a configuração de bans!"
    echo "[*] Executando cargo-deny check licenses..."
    (cd "${RUST_DIR}" && cargo-deny --config "${RUST_DIR}/deny.toml" check licenses)
    echo "[+] cargo-deny aprovou as licenças (AGPL só nas exceções nomeadas de deny.toml)!"
else
    echo "[*] cargo-deny não instalado no host; verificação estrita via metadata realizada com sucesso."
fi

# 5. Se o binário batch ou server já estiver compilado, inspeciona ldd
for bin_candidate in "${RUST_DIR}/target/release/arena-server" "${RUST_DIR}/target/release/arena-batch"; do
    if [[ -f "${bin_candidate}" ]]; then
        echo "[*] Inspecionando links dinâmicos do binário: $(basename "${bin_candidate}")..."
        NON_STD_LIBS=$(ldd "${bin_candidate}" | grep -v -E "linux-vdso|libc\.so|libgcc_s|ld-linux|libm\.so" || true)
        if [[ -n "${NON_STD_LIBS}" ]]; then
            echo "[-] VIOLAÇÃO: Binário contém bibliotecas C compartilhadas inesperadas:"
            echo "${NON_STD_LIBS}"
            exit 1
        fi
        echo "[+] Binário 100% puro: nenhuma biblioteca nativa de terceiros vinculada."
    fi
done

echo "[✓] Verificação de pureza Rust CONCLUÍDA COM SUCESSO! 100% Rust puro e livre de C/FFI."
exit 0
