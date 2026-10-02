#!/usr/bin/env bash
set -euo pipefail

# scripts/check-toolchain-sync.sh
# Garante que o toolchain Rust é um só: rust-toolchain.toml, a imagem docker/rust.Dockerfile e o CI usam a
# mesma versão, e nenhuma dependência do Cargo.lock exige um rust-version maior que ela (issue #12).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=== Verificação do toolchain Rust (image-processor-arena) ==="

toolchain="$(sed -n 's/^channel *= *"\(.*\)".*/\1/p' rust-toolchain.toml)"
docker_versions="$(sed -n 's/^FROM rust:\([0-9][0-9.]*\)-bookworm.*/\1/p' docker/rust.Dockerfile | sort -u)"
ci_versions="$(grep -E '^\s+toolchain: *[0-9]' .github/workflows/ci.yml | sed 's/.*toolchain: *//; s/[^0-9.].*//' | sort -u)"

errors=0
if [[ -z "${toolchain}" ]]; then
    echo "[-] rust-toolchain.toml sem 'channel'."
    exit 1
fi
echo "[*] rust-toolchain.toml : ${toolchain}"
echo "[*] docker/rust.Dockerfile: ${docker_versions:-<nenhuma tag fixa>}"
echo "[*] .github/workflows/ci.yml: ${ci_versions:-<nenhuma versão fixa>}"

if [[ "${docker_versions}" != "${toolchain}" ]]; then
    echo "[-] docker/rust.Dockerfile deve usar FROM rust:${toolchain}-bookworm."
    errors=$((errors + 1))
fi
if [[ "${ci_versions}" != "${toolchain}" ]]; then
    echo "[-] Todo 'toolchain:' do ci.yml deve ser ${toolchain}."
    errors=$((errors + 1))
fi

# Nenhuma dependência pode exigir um compilador mais novo que o fixado.
if command -v cargo >/dev/null 2>&1; then
    if ! python3 - "${toolchain}" <<'PY'
import json, subprocess, sys

toolchain = tuple(int(x) for x in sys.argv[1].split("."))
meta = json.loads(subprocess.run(
    ["cargo", "metadata", "--manifest-path", "rust/Cargo.toml", "--format-version", "1", "--locked"],
    check=True, capture_output=True, text=True).stdout)

def parse(v):
    parts = [int(x) for x in v.split(".")]
    return tuple(parts + [0] * (3 - len(parts)))

worst = max(((parse(p["rust_version"]), p["name"], p["version"]) for p in meta["packages"] if p.get("rust_version")),
            default=None)
print(f"[*] maior rust-version entre as dependências: {'.'.join(map(str, worst[0]))} ({worst[1]} {worst[2]})" if worst else "[*] nenhuma dependência declara rust-version")
if worst and worst[0] > toolchain:
    print(f"[-] {worst[1]} {worst[2]} exige Rust {'.'.join(map(str, worst[0]))}, acima do toolchain fixado ({sys.argv[1]}).")
    sys.exit(1)
PY
    then
        errors=$((errors + 1))
    fi
else
    echo "[!] cargo não encontrado: pulei a checagem de rust-version das dependências."
fi

if [[ ${errors} -gt 0 ]]; then
    echo "[-] Verificação do toolchain FALHOU com ${errors} problema(s)."
    exit 1
fi
echo "[✓] Toolchain Rust consistente."
