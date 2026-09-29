#!/usr/bin/env bash
set -euo pipefail

# scripts/check-purity-go.sh
# Validador de pureza do ecossistema Go (CGO_ENABLED=0, sem CgoFiles, sem purego, sem wazero).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_DIR="${ROOT_DIR}/go"

echo "=== Verificação de Pureza Go (image-processor-arena) ==="

# 1. Valida e impõe CGO_ENABLED=0
if [[ "${CGO_ENABLED:-0}" != "0" ]]; then
    echo "[-] ERRO: CGO_ENABLED deve ser 0! Valor atual: ${CGO_ENABLED}"
    exit 1
fi
export CGO_ENABLED=0
echo "[+] CGO_ENABLED=0 confirmado."

# 2. Executa go list -deps
cd "${GO_DIR}"

TAGS=""
PORTABLE_CHECK=false
if [[ "${1:-}" == "--portable" || "${1:-}" == "-tags=noasm" ]]; then
    TAGS="-tags noasm"
    PORTABLE_CHECK=true
    echo "[*] Modo portável ativo (-tags noasm)."
fi

echo "[*] Inspecionando dependências..."
DEPS_OUTPUT=$(go list ${TAGS} -deps -f '{{.ImportPath}}|{{.CgoFiles}}|{{.SFiles}}|{{.Standard}}' ./...)

ERRORS=0

while IFS='|' read -r import_path cgo_files s_files is_standard; do
    # Verifica CgoFiles
    if [[ -n "${cgo_files}" && "${cgo_files}" != "[]" ]]; then
        echo "[-] VIOLAÇÃO: Pacote ${import_path} contém CgoFiles: ${cgo_files}"
        ERRORS=$((ERRORS + 1))
    fi

    # Verifica bibliotecas proibidas: purego
    if [[ "${import_path}" == *"purego"* ]]; then
        echo "[-] VIOLAÇÃO: Import proibido de purego detectado: ${import_path}"
        ERRORS=$((ERRORS + 1))
    fi

    # Verifica bibliotecas proibidas: wazero
    if [[ "${import_path}" == *"wazero"* ]]; then
        echo "[-] VIOLAÇÃO: Import proibido de wazero detectado: ${import_path}"
        ERRORS=$((ERRORS + 1))
    fi

    # Se modo portável for solicitado, proíbe SFiles fora da stdlib
    if [[ "${PORTABLE_CHECK}" == true && "${is_standard}" != "true" ]]; then
        if [[ -n "${s_files}" && "${s_files}" != "[]" ]]; then
            echo "[-] VIOLAÇÃO PORTÁVEL: Pacote não-padrão ${import_path} contém SFiles em modo noasm: ${s_files}"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done <<< "${DEPS_OUTPUT}"

if [[ ${ERRORS} -gt 0 ]]; then
    echo "[-] Verificação de pureza Go FALHOU com ${ERRORS} violação(ões)."
    exit 1
fi

echo "[✓] Verificação de pureza Go CONCLUÍDA COM SUCESSO! 100% Go puro e livre de CGO/purego/wazero."
exit 0
