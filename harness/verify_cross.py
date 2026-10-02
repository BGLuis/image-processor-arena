#!/usr/bin/env python3
"""
verify_cross.py - Validador Cruzado de Conformidade para op=analyze.

Compara as saídas dos servidores HTTP ou binários batch de Go e Rust contra o
gabarito oficial harness/fixtures/ground_truth.json com as tolerâncias de
docs/analyze-spec.md.

Modos de uso:
  python3 harness/verify_cross.py --mode self             # Valida o oráculo Python contra o gabarito
  python3 harness/verify_cross.py --mode http --target go  # Valida servidor Go HTTP
  python3 harness/verify_cross.py --mode http --target rust# Valida servidor Rust HTTP
  python3 harness/verify_cross.py --mode http --target all # Valida ambos servidores HTTP
  python3 harness/verify_cross.py --mode batch            # Valida binários CLI locais
"""

import os
import sys
import json
import math
import argparse
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, List, Tuple, Optional

# Tolerâncias epsilon especificadas em docs/analyze-spec.md
EPSILON_TABLE = {
    "aspect_ratio.float": 1e-6,
    "block_alignment.partial_pct": 1e-6,
    "mean_y": 1e-4,
    "entropy_y": 1e-4,
    "entropy_residual_y": 1e-4,
    "spatial_information": 1e-3,
    "gradient_energy": 1e-3,
    "laplacian_variance": 1e-3,
    "color_variance.var_r": 1e-3,
    "color_variance.var_g": 1e-3,
    "color_variance.var_b": 1e-3,
    "color_variance.var_sum": 1e-3,
    "alpha.sparsity": 1e-4,
    "alpha.binarity": 1e-4,
    "adequacy_420.chroma_gradient_energy": 1e-3,
    "adequacy_420.chroma_gradient_ratio": 1e-3,
    "adequacy_420.mse_cb": 1e-3,
    "adequacy_420.mse_cr": 1e-3,
    "adequacy_420.mse_chroma": 1e-3,
    "flat_area": 1e-4,
    "dominant_color.mean_rgb": 1e-3,
}


class DiffReporter:
    def __init__(self):
        self.errors: List[str] = []

    def check_exact(self, path: str, actual: Any, expected: Any) -> bool:
        if actual != expected:
            self.errors.append(f"    [FAIL] {path}: obtido {actual!r}, esperado {expected!r} (exato)")
            return False
        return True

    def check_float(self, path: str, actual: float, expected: float, eps: float) -> bool:
        delta = abs(float(actual) - float(expected))
        if delta > eps:
            self.errors.append(
                f"    [FAIL] {path}: obtido {actual:.6f}, esperado {expected:.6f}, delta={delta:.6e} > eps={eps:.6e}"
            )
            return False
        return True


def compare_result(actual: Dict[str, Any], expected: Dict[str, Any]) -> List[str]:
    reporter = DiffReporter()

    # Dimensões e Proporção
    reporter.check_exact("width", actual.get("width"), expected.get("width"))
    reporter.check_exact("height", actual.get("height"), expected.get("height"))

    ar_act = actual.get("aspect_ratio", {})
    ar_exp = expected.get("aspect_ratio", {})
    reporter.check_exact("aspect_ratio.str", ar_act.get("str"), ar_exp.get("str"))
    reporter.check_float("aspect_ratio.float", ar_act.get("float", 0.0), ar_exp.get("float", 0.0), 1e-6)

    # Block Alignment
    ba_act = actual.get("block_alignment", {})
    ba_exp = expected.get("block_alignment", {})
    for b_key in ["b8", "b16", "b64", "b256"]:
        b_act = ba_act.get(b_key, {})
        b_exp = ba_exp.get(b_key, {})
        reporter.check_exact(f"block_alignment.{b_key}.w_mod", b_act.get("w_mod"), b_exp.get("w_mod"))
        reporter.check_exact(f"block_alignment.{b_key}.h_mod", b_act.get("h_mod"), b_exp.get("h_mod"))
        reporter.check_exact(
            f"block_alignment.{b_key}.partial_pixels",
            b_act.get("partial_pixels"),
            b_exp.get("partial_pixels"),
        )
        reporter.check_float(
            f"block_alignment.{b_key}.partial_pct",
            b_act.get("partial_pct", 0.0),
            b_exp.get("partial_pct", 0.0),
            1e-6,
        )

    # Luminância e Entropias
    reporter.check_float("mean_y", actual.get("mean_y", 0.0), expected.get("mean_y", 0.0), 1e-4)
    reporter.check_float("entropy_y", actual.get("entropy_y", 0.0), expected.get("entropy_y", 0.0), 1e-4)
    reporter.check_float(
        "entropy_residual_y",
        actual.get("entropy_residual_y", 0.0),
        expected.get("entropy_residual_y", 0.0),
        1e-4,
    )

    # Métricas de Gradiente e Frequência
    reporter.check_float(
        "spatial_information",
        actual.get("spatial_information", 0.0),
        expected.get("spatial_information", 0.0),
        1e-3,
    )
    reporter.check_float(
        "gradient_energy", actual.get("gradient_energy", 0.0), expected.get("gradient_energy", 0.0), 1e-3
    )
    reporter.check_float(
        "laplacian_variance",
        actual.get("laplacian_variance", 0.0),
        expected.get("laplacian_variance", 0.0),
        1e-3,
    )

    # Variância de Cor
    cv_act = actual.get("color_variance", {})
    cv_exp = expected.get("color_variance", {})
    reporter.check_float("color_variance.var_r", cv_act.get("var_r", 0.0), cv_exp.get("var_r", 0.0), 1e-3)
    reporter.check_float("color_variance.var_g", cv_act.get("var_g", 0.0), cv_exp.get("var_g", 0.0), 1e-3)
    reporter.check_float("color_variance.var_b", cv_act.get("var_b", 0.0), cv_exp.get("var_b", 0.0), 1e-3)
    reporter.check_float("color_variance.var_sum", cv_act.get("var_sum", 0.0), cv_exp.get("var_sum", 0.0), 1e-3)

    # Cores Únicas
    reporter.check_exact("unique_colors", actual.get("unique_colors"), expected.get("unique_colors"))

    # Alpha
    al_act = actual.get("alpha", {})
    al_exp = expected.get("alpha", {})
    reporter.check_exact("alpha.has_alpha", al_act.get("has_alpha"), al_exp.get("has_alpha"))
    reporter.check_float("alpha.sparsity", al_act.get("sparsity", 0.0), al_exp.get("sparsity", 0.0), 1e-4)
    reporter.check_float("alpha.binarity", al_act.get("binarity", 0.0), al_exp.get("binarity", 0.0), 1e-4)

    # Adequação 4:2:0
    ad_act = actual.get("adequacy_420", {})
    ad_exp = expected.get("adequacy_420", {})
    reporter.check_float(
        "adequacy_420.chroma_gradient_energy",
        ad_act.get("chroma_gradient_energy", 0.0),
        ad_exp.get("chroma_gradient_energy", 0.0),
        1e-3,
    )
    reporter.check_float(
        "adequacy_420.chroma_gradient_ratio",
        ad_act.get("chroma_gradient_ratio", 0.0),
        ad_exp.get("chroma_gradient_ratio", 0.0),
        1e-3,
    )
    reporter.check_float("adequacy_420.mse_cb", ad_act.get("mse_cb", 0.0), ad_exp.get("mse_cb", 0.0), 1e-3)
    reporter.check_float("adequacy_420.mse_cr", ad_act.get("mse_cr", 0.0), ad_exp.get("mse_cr", 0.0), 1e-3)
    reporter.check_float(
        "adequacy_420.mse_chroma",
        ad_act.get("mse_chroma", 0.0),
        ad_exp.get("mse_chroma", 0.0),
        1e-3,
    )

    # Área Plana
    reporter.check_float("flat_area", actual.get("flat_area", 0.0), expected.get("flat_area", 0.0), 1e-4)

    # Cor Dominante
    dc_act = actual.get("dominant_color", {})
    dc_exp = expected.get("dominant_color", {})
    reporter.check_exact(
        "dominant_color.dominant_rgb",
        dc_act.get("dominant_rgb"),
        dc_exp.get("dominant_rgb"),
    )
    reporter.check_exact(
        "dominant_color.dominant_bin",
        dc_act.get("dominant_bin"),
        dc_exp.get("dominant_bin"),
    )
    m_act = dc_act.get("mean_rgb", [0.0, 0.0, 0.0])
    m_exp = dc_exp.get("mean_rgb", [0.0, 0.0, 0.0])
    for ch_idx, ch_name in enumerate(["r", "g", "b"]):
        reporter.check_float(
            f"dominant_color.mean_rgb[{ch_name}]",
            m_act[ch_idx] if len(m_act) > ch_idx else 0.0,
            m_exp[ch_idx] if len(m_exp) > ch_idx else 0.0,
            1e-3,
        )

    # pHash (exato 16 caracteres hexadecimais)
    reporter.check_exact("phash", actual.get("phash"), expected.get("phash"))

    # BlurHash (string oficial Wolt)
    reporter.check_exact("blurhash", actual.get("blurhash"), expected.get("blurhash"))

    return reporter.errors


# ---------------------------------------------------------------------------
# Executores por Modo
# ---------------------------------------------------------------------------

def run_http_analyze(url: str, pam_bytes: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    req = urllib.request.Request(
        url,
        data=pam_bytes,
        headers={"Content-Type": "image/x-netpbm-pam"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body), None
    except Exception as e:
        return None, str(e)


def run_batch_analyze(bin_path: str, pam_path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not os.path.exists(bin_path):
        return None, f"Binário não encontrado: {bin_path}"
    try:
        proc = subprocess.run(
            [bin_path, "--op", "analyze", "--input", pam_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=True,
        )
        return json.loads(proc.stdout), None
    except Exception as e:
        return None, str(e)


def run_self_analyze(pam_path: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    from harness.generators.make_fixtures import analyze_pam_file

    try:
        return analyze_pam_file(pam_path), None
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Ponto de Entrada Principal
# ---------------------------------------------------------------------------
def read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validação Cruzada de op=analyze para Go, Rust e Python.")
    parser.add_argument(
        "--mode",
        choices=["self", "http", "batch"],
        default="self",
        help="Modo de teste: 'self' (oráculo Python), 'http' (endpoint POST), 'batch' (CLI)",
    )
    parser.add_argument(
        "--target",
        choices=["all", "go", "rust"],
        default="all",
        help="Alvo do teste em modo http ou batch (padrão: all)",
    )
    parser.add_argument("--go-url", default="http://localhost:8080/run?op=analyze", help="URL do endpoint Go")
    parser.add_argument("--rust-url", default="http://localhost:8081/run?op=analyze", help="URL do endpoint Rust")
    parser.add_argument("--go-bin", default="./go/bin/arena-batch", help="Caminho do binário CLI Go")
    parser.add_argument("--rust-bin", default="./rust/target/release/arena-batch", help="Caminho do binário CLI Rust")
    parser.add_argument("--fixtures-dir", default=None, help="Diretório das fixtures sintéticas")
    parser.add_argument("--ground-truth", default=None, help="Caminho do ground_truth.json")
    args = parser.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    fixtures_dir = args.fixtures_dir or os.path.join(base_dir, "harness", "fixtures", "synthetic")
    gt_path = args.ground_truth or os.path.join(base_dir, "harness", "fixtures", "ground_truth.json")

    if not os.path.exists(gt_path):
        print(f"[!] Arquivo de gabarito não encontrado: {gt_path}")
        print("    Execute primeiro: python3 harness/generators/make_fixtures.py")
        return 1

    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth: Dict[str, Dict[str, Any]] = json.load(f)

    print("=" * 70)
    print("Arena de Processamento de Imagens — Validação Cruzada (op=analyze)")
    print(f"Modo: {args.mode.upper()} | Alvo: {args.target.upper()}")
    print(f"Gabarito: {gt_path} ({len(ground_truth)} fixtures)")
    print("=" * 70)

    # Determina alvos a testar
    targets = []
    if args.mode == "self":
        targets.append(("Python Oracle", run_self_analyze, None))
    elif args.mode == "http":
        if args.target in ["all", "go"]:
            targets.append(("Go HTTP (Port 8080)", lambda p: run_http_analyze(args.go_url, read_file(p)), args.go_url))
        if args.target in ["all", "rust"]:
            targets.append(("Rust HTTP (Port 8081)", lambda p: run_http_analyze(args.rust_url, read_file(p)), args.rust_url))
    elif args.mode == "batch":
        if args.target in ["all", "go"]:
            targets.append(("Go Batch CLI", lambda p: run_batch_analyze(args.go_bin, p), args.go_bin))
        if args.target in ["all", "rust"]:
            targets.append(("Rust Batch CLI", lambda p: run_batch_analyze(args.rust_bin, p), args.rust_bin))

    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    for target_name, runner_fn, target_info in targets:
        print(f"\n[*] Testando alvo: {target_name} ({target_info or ''})")

        for fname, expected in ground_truth.items():
            pam_path = os.path.join(fixtures_dir, fname)
            total_tests += 1

            if not os.path.exists(pam_path):
                print(f"  [X] {fname:25s} -> ERRO: Fixture não encontrada no disco ({pam_path})")
                failed_tests += 1
                continue

            actual, err = runner_fn(pam_path)
            if err:
                print(f"  [X] {fname:25s} -> ERRO: {err}")
                failed_tests += 1
                continue

            diffs = compare_result(actual, expected)
            if diffs:
                print(f"  [X] {fname:25s} -> FALHA ({len(diffs)} divergências)")
                for d in diffs:
                    print(d)
                failed_tests += 1
            else:
                print(f"  [✓] {fname:25s} -> PASSOU (todas as 16 métricas conferem)")
                passed_tests += 1

    print("\n" + "=" * 70)
    print(f"Resumo da Validação: Total={total_tests}, Passou={passed_tests}, Falhou={failed_tests}")
    print("=" * 70)

    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    # Garante que sys.path inclui o diretório base para imports relativos
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    sys.exit(main())
