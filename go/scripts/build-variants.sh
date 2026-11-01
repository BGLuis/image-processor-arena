#!/usr/bin/env bash
set -euo pipefail

# go/scripts/build-variants.sh
# Compila todas as variantes suportadas do ecossistema Go para a Arena:
#   1. Portable:    go:portable:1.27:noasm     (CGO_ENABLED=0, -tags "noasm portable")
#   2. Padrão:      go:accelerated:1.27:padrao (CGO_ENABLED=0)
#   3. PGO:         go:accelerated:1.27:pgo    (CGO_ENABLED=0, Profile-Guided Optimization)
#   4. Híbrido:     go:hybrid:1.27:cgo         (CGO_ENABLED=1, -tags hybrid)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BIN_DIR="${GO_DIR}/bin"

mkdir -p "${BIN_DIR}"
cd "${GO_DIR}"

echo "=========================================================="
echo "  Image Processor Arena - Go Multi-Version Builder"
echo "=========================================================="

# 0. Garante que os perfis PGO existem
if [[ ! -f "cmd/server/default.pgo" || ! -f "cmd/batch/default.pgo" ]]; then
    echo "[*] Gerando perfis PGO de referência via cmd/pgo_gen..."
    go run ./cmd/pgo_gen
fi

# 1. Variante Portable (Tier 1)
echo "[1/4] Compilando Variante Portável (CGO_ENABLED=0, -tags 'noasm portable')..."
CGO_ENABLED=0 go build -tags "noasm portable" -pgo=off -o "${BIN_DIR}/arena-server-portable" ./cmd/server
CGO_ENABLED=0 go build -tags "noasm portable" -pgo=off -o "${BIN_DIR}/arena-batch-portable" ./cmd/batch
echo "  -> ${BIN_DIR}/arena-server-portable"
echo "  -> ${BIN_DIR}/arena-batch-portable"

# 2. Variante Padrão / Accelerated (Tier 2 - Default)
echo "[2/4] Compilando Variante Padrão Acelerada (CGO_ENABLED=0)..."
CGO_ENABLED=0 go build -pgo=off -o "${BIN_DIR}/arena-server" ./cmd/server
CGO_ENABLED=0 go build -pgo=off -o "${BIN_DIR}/arena-batch" ./cmd/batch
echo "  -> ${BIN_DIR}/arena-server"
echo "  -> ${BIN_DIR}/arena-batch"

# 3. Variante PGO / Accelerated (Tier 2 - PGO)
echo "[3/4] Compilando Variante Acelerada com PGO (CGO_ENABLED=0, -pgo=auto)..."
CGO_ENABLED=0 go build -pgo=auto -o "${BIN_DIR}/arena-server-pgo" ./cmd/server
CGO_ENABLED=0 go build -pgo=auto -o "${BIN_DIR}/arena-batch-pgo" ./cmd/batch
echo "  -> ${BIN_DIR}/arena-server-pgo"
echo "  -> ${BIN_DIR}/arena-batch-pgo"

# 4. Variante Híbrida (Tier 3 - CGO)
echo "[4/4] Compilando Variante Híbrida CGO (CGO_ENABLED=1, -tags hybrid)..."
CGO_ENABLED=1 go build -tags hybrid -pgo=off -o "${BIN_DIR}/arena-server-hybrid" ./cmd/server
CGO_ENABLED=1 go build -tags hybrid -pgo=off -o "${BIN_DIR}/arena-batch-hybrid" ./cmd/batch
echo "  -> ${BIN_DIR}/arena-server-hybrid"
echo "  -> ${BIN_DIR}/arena-batch-hybrid"

echo "=========================================================="
echo "  Build concluído com sucesso! Binários gerados:"
echo "=========================================================="
ls -lh "${BIN_DIR}"/arena-*
