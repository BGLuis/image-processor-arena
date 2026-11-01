#!/usr/bin/env bash
set -euo pipefail

# scripts/check-purity-go.sh
# Validador de pureza do ecossistema Go (CGO_ENABLED=0, sem CgoFiles, sem purego, sem wazero).
#
# Modos:
#   (sem argumento)  A verificação da política do projeto; é a que o CI roda. Assembly Go (.s) é
#                    permitido: não é CGO nem FFI.
#   --portable       Modo portável (Tier 1): com `-tags noasm,portable`, nenhum pacote externo
#                    possui arquivos .s nem CGO. O isolamento de webp_accelerated.go e webp_portable.go
#                    garante 0 dependências com assembly (deepteams/webp não é incluído).
#   --hybrid         Modo híbrido (Tier 3): com `-tags hybrid`, CGO é permitido (CGO_ENABLED=1),
#                    mas purego e wazero continuam estritamente proibidos.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_DIR="${ROOT_DIR}/go"

TIER="accelerated"
for arg in "$@"; do
    case "$arg" in
        --tier=portable|--portable|-tags=noasm)
            TIER="portable"
            ;;
        --tier=accelerated)
            TIER="accelerated"
            ;;
        --tier=hybrid)
            TIER="hybrid"
            ;;
    esac
done

echo "=== Verificação de Pureza Go (Tier: ${TIER}) ==="

# 1. Valida e impõe CGO_ENABLED
if [[ "${TIER}" == "hybrid" ]]; then
    export CGO_ENABLED=1
    echo "[*] Tier Híbrido ativo: CGO_ENABLED=1 habilitado."
else
    if [[ "${CGO_ENABLED:-0}" != "0" ]]; then
        echo "[-] ERRO: CGO_ENABLED deve ser 0 no tier ${TIER}! Valor atual: ${CGO_ENABLED}"
        exit 1
    fi
    export CGO_ENABLED=0
    echo "[+] CGO_ENABLED=0 confirmado."
fi

# 2. Executa go list -deps
cd "${GO_DIR}"

TAGS=""
PORTABLE_CHECK=false
if [[ "${TIER}" == "portable" ]]; then
    TAGS="-tags=noasm,portable"
    PORTABLE_CHECK=true
    echo "[*] Modo portável ativo (-tags noasm,portable)."
elif [[ "${TIER}" == "hybrid" ]]; then
    TAGS="-tags hybrid"
    echo "[*] Modo híbrido ativo (-tags hybrid)."
else
    echo "[*] Modo acelerado ativo (padrão)."
fi

echo "[*] Inspecionando dependências..."
DEPS_OUTPUT=$(go list ${TAGS} -deps -f '{{.ImportPath}}|{{.CgoFiles}}|{{.SFiles}}|{{.Standard}}' ./...)

ERRORS=0

while IFS='|' read -r import_path cgo_files s_files is_standard; do
    # Verifica CgoFiles (proibido em portable e accelerated)
    if [[ "${TIER}" != "hybrid" && -n "${cgo_files}" && "${cgo_files}" != "[]" ]]; then
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
