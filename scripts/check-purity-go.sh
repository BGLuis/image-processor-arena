#!/usr/bin/env bash
set -euo pipefail

# scripts/check-purity-go.sh
# Validador de pureza do ecossistema Go (CGO_ENABLED=0, sem CgoFiles, sem purego, sem wazero).
#
# Modos:
#   (sem argumento)  A verificação da política do projeto; é a que o CI roda. Assembly Go (.s) é
#                    permitido: não é CGO nem FFI.
#   --portable       Auditoria opcional: com `-tags noasm`, nenhum pacote de terceiros deveria ter
#                    arquivos .s. LIMITAÇÃO CONHECIDA: falha hoje, e isso é esperado. O
#                    github.com/deepteams/webp (internal/dsp e internal/lossy) traz assembly amd64/arm64
#                    que não respeita a tag `noasm`, então o modo lista esses pacotes e sai com 1. Ele
#                    não é usado no CI; serve para medir o quanto falta para um build sem assembly
#                    (por exemplo para GOARCH sem implementação). Não indica violação da política.

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
    if [[ "${PORTABLE_CHECK}" == true ]]; then
        echo "[i] Em --portable isto é uma limitação conhecida (ver o cabeçalho do script): as dependências"
        echo "    listadas acima trazem assembly Go e não respeitam -tags noasm. Não é violação da política."
    fi
    exit 1
fi

echo "[✓] Verificação de pureza Go CONCLUÍDA COM SUCESSO! 100% Go puro e livre de CGO/purego/wazero."
exit 0
