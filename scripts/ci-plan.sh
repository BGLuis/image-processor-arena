#!/usr/bin/env bash
set -euo pipefail

# scripts/ci-plan.sh
# Decide quais pipelines rodam. Lê a lista de arquivos alterados (um por linha) no stdin e o registro
# .github/ci-variants.json; escreve key=value (JSON compacto) em $GITHUB_OUTPUT, ou no stdout se ausente.
# CI_FORCE_ALL=true ignora o diff e seleciona tudo (dispatch, agendado, branch nova).
# Para registrar uma variante nova basta adicionar uma entrada em "variants" no registro.

REGISTRY="${CI_REGISTRY:-.github/ci-variants.json}"
FORCE_ALL="${CI_FORCE_ALL:-false}"
OUT="${GITHUB_OUTPUT:-/dev/stdout}"

files_json="$(jq -R 'select(length > 0)' | jq -s .)"

jq -r --argjson files "${files_json}" --arg force "${FORCE_ALL}" '
  def hit($prefixes):
    $force == "true"
    or any($files[]; . as $f | any($prefixes[]; . as $p | $f | startswith($p)));
  . as $r
  | hit($r.shared) as $shared
  | [$r.variants[] | select($shared or hit([.path + "/"] + (.extra // [])))] as $picked
  | ($picked | length > 0) as $engines
  | [$r.variants[]
      | select(
          ([.id] | inside($picked | map(.id)))
          or ($engines and (.id == $r.arena.go or .id == $r.arena.rust)))] as $built
  | [$built[] | select(.lang == "go")] as $go
  | [$built[] | select(.lang == "rust")] as $rust
  | "go=" + ({include: $go} | tojson),
    "has_go=" + ($go | length > 0 | tostring),
    "rust=" + ({include: $rust} | tojson),
    "has_rust=" + ($rust | length > 0 | tostring),
    "arena=" + ($engines | tostring),
    "docker=" + ($engines or hit($r.docker) | tostring),
    "purity=" + ($engines or hit($r.docker) | tostring),
    "harness=" + (hit($r.harness + $r.shared) | tostring)
' "${REGISTRY}" >> "${OUT}"
