#!/usr/bin/env bash
set -euo pipefail

# rust/scripts/build-variants.sh
# Compila todas as variantes suportadas do engine Rust (portable, accelerated, native-cpu, hybrid)
# e as disponibiliza em rust/bin/ e rust/target/release/.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUST_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_RELEASE="${RUST_DIR}/target/release"
BIN_DIR="${RUST_DIR}/bin"

mkdir -p "${BIN_DIR}"
mkdir -p "${TARGET_RELEASE}"

echo "=== Compilando Variantes da Engine Rust ==="

# 1. Tier 3: Hybrid (FFI com libturbojpeg e libwebp)
echo "[*] Compilando Variante 3: rust:hybrid:stable:ffi (--features hybrid)..."
CARGO_TARGET_DIR="${RUST_DIR}/target/build-hybrid" cargo build --manifest-path "${RUST_DIR}/Cargo.toml" --release --features hybrid
cp "${RUST_DIR}/target/build-hybrid/release/arena-server" "${TARGET_RELEASE}/arena-server-hybrid"
cp "${RUST_DIR}/target/build-hybrid/release/arena-batch" "${TARGET_RELEASE}/arena-batch-hybrid"
cp "${TARGET_RELEASE}/arena-server-hybrid" "${BIN_DIR}/arena-server-hybrid"
cp "${TARGET_RELEASE}/arena-batch-hybrid" "${BIN_DIR}/arena-batch-hybrid"
rm -rf "${RUST_DIR}/target/build-hybrid"
echo "[+] Variante Hybrid pronta."

# 2. Tier 2: Accelerated Native-CPU (target-cpu=native)
echo "[*] Compilando Variante 2: rust:accelerated:stable:native-cpu (RUSTFLAGS=\"-C target-cpu=native\")..."
CARGO_TARGET_DIR="${RUST_DIR}/target/build-native" RUSTFLAGS="-C target-cpu=native" cargo build --manifest-path "${RUST_DIR}/Cargo.toml" --release
cp "${RUST_DIR}/target/build-native/release/arena-server" "${TARGET_RELEASE}/arena-server-native"
cp "${RUST_DIR}/target/build-native/release/arena-batch" "${TARGET_RELEASE}/arena-batch-native"
cp "${TARGET_RELEASE}/arena-server-native" "${BIN_DIR}/arena-server-native"
cp "${TARGET_RELEASE}/arena-batch-native" "${BIN_DIR}/arena-batch-native"
rm -rf "${RUST_DIR}/target/build-native"
echo "[+] Variante Native-CPU pronta."

# 3. Tier 1: Portable (no-simd / pura)
echo "[*] Compilando Variante 1: rust:portable:stable:no-simd (--features portable)..."
CARGO_TARGET_DIR="${RUST_DIR}/target/build-portable" cargo build --manifest-path "${RUST_DIR}/Cargo.toml" --release --features portable
cp "${RUST_DIR}/target/build-portable/release/arena-server" "${TARGET_RELEASE}/arena-server-portable"
cp "${RUST_DIR}/target/build-portable/release/arena-batch" "${TARGET_RELEASE}/arena-batch-portable"
cp "${TARGET_RELEASE}/arena-server-portable" "${BIN_DIR}/arena-server-portable"
cp "${TARGET_RELEASE}/arena-batch-portable" "${BIN_DIR}/arena-batch-portable"
rm -rf "${RUST_DIR}/target/build-portable"
echo "[+] Variante Portable pronta."

# 4. Tier 2: Accelerated Padrão (Best-of-Breed puro)
echo "[*] Compilando Variante Padrão: rust:accelerated:stable:padrao..."
cargo build --manifest-path "${RUST_DIR}/Cargo.toml" --release
cp "${TARGET_RELEASE}/arena-server" "${BIN_DIR}/arena-server"
cp "${TARGET_RELEASE}/arena-batch" "${BIN_DIR}/arena-batch"
echo "[+] Variante Padrão pronta."

echo "=== Todas as variantes foram compiladas com sucesso! ==="
echo "Binários disponíveis em ${BIN_DIR} e ${TARGET_RELEASE}:"
ls -la "${BIN_DIR}"
