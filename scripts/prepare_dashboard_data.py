#!/usr/bin/env python3
"""
scripts/prepare_dashboard_data.py

Lê os resultados brutos da Arena e gera os arquivos JSON estruturados para o
DuckDB-Wasm e o dashboard Next.js em dashboard/public/data/:
- results/benchmark_matrix.json (todas as implementações) -> results.json
- results/benchmark_results.json (duelo Go x Rust) -> benchmark_results.json,
  per_operation.json, equal_quality.json e metadata.json
"""

import json
import os
import sys

def long_format(matrix_file):
    """Linhas do dashboard a partir de results/benchmark_matrix.json (harness/benchmark_matrix.py).

    rel_time é a mediana dividida pela mais rápida da tarefa entre as implementações que a suportam;
    task_rank 1 é a vitória. Tarefas não suportadas ou com falha ficam de fora (contam como cobertura).
    """
    with open(matrix_file, "r", encoding="utf-8") as f:
        rows = [r for r in json.load(f)["results"] if r["status"] == "ok"]

    by_task = {}
    for r in rows:
        by_task.setdefault(r["task_id"], []).append(r)

    out = []
    for task_id in sorted(by_task):
        ranked = sorted(by_task[task_id], key=lambda r: r["codec_ms"]["median"])
        fastest = ranked[0]["codec_ms"]["median"]
        for rank, r in enumerate(ranked, start=1):
            codec = r["codec_ms"]
            psnr = r.get("quality", {}).get("psnr_db")
            out.append({
                "task_id": task_id,
                "task": r["task"],
                "op": r["op"],
                "format": r["format"],
                "mode": r["mode"],
                "image": r["image"],
                "mp": r["mp"],
                "language": r["language"],
                "tier": r["tier"],
                "toolchain": r["toolchain"],
                "lib": r["lib"],
                "impl_id": r["impl_id"],
                "codec_median_ms": round(codec["median"], 3),
                "p25": round(codec["p25"], 3),
                "p75": round(codec["p75"], 3),
                "bytes": r.get("out_bytes") or 0,
                "psnr_db": round(psnr, 2) if isinstance(psnr, (int, float)) else None,
                "rel_time": round(codec["median"] / fastest, 2) if fastest > 0 else 1.0,
                "task_rank": rank,
            })
    return out


def prepare_data(results_file="results/benchmark_results.json", output_dir="dashboard/public/data",
                 matrix_file="results/benchmark_matrix.json"):
    for path in (results_file, matrix_file):
        if not os.path.exists(path):
            print(f"Erro: Arquivo {path} não encontrado.")
            if path == matrix_file:
                print("  Gere-o com: python3 harness/benchmark_matrix.py")
            sys.exit(1)

    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    metadata = data.get("metadata", {})
    per_operation = data.get("per_operation", [])
    raw_results = data.get("results", [])
    equal_quality = data.get("equal_quality", [])

    flat_results = []
    for idx, r in enumerate(raw_results):
        go_data = r.get("go", {})
        rust_data = r.get("rust", {})

        go_codec = go_data.get("codec_ms", {}) or {}
        rust_codec = rust_data.get("codec_ms", {}) or {}

        go_wall = go_data.get("wall_ms", {}) or {}
        rust_wall = rust_data.get("wall_ms", {}) or {}

        go_q = r.get("q", {}).get("go") if isinstance(r.get("q"), dict) else None
        rust_q = r.get("q", {}).get("rust") if isinstance(r.get("q"), dict) else None

        go_quality = go_data.get("quality", {}) or {}
        rust_quality = rust_data.get("quality", {}) or {}

        go_median = go_codec.get("median")
        rust_median = rust_codec.get("median")
        speedup_factor = (go_median / rust_median) if (go_median and rust_median and rust_median > 0) else None

        flat_item = {
            "id": idx + 1,
            "task": r.get("task", ""),
            "op": r.get("op", ""),
            "format": r.get("format", ""),
            "mode": r.get("mode", ""),
            "image": r.get("image", ""),
            "mp": r.get("mp", 0.0),
            "metric": r.get("metric", "codec_ms"),
            "q_go": go_q,
            "q_rust": rust_q,
            "winner": r.get("winner", ""),
            "speedup": r.get("speedup", 1.0),
            "speedup_factor": round(speedup_factor, 4) if speedup_factor else None,
            "bytes_ratio": r.get("bytes_ratio"),
            
            # Go Metrics
            "go_codec_median_ms": go_codec.get("median"),
            "go_codec_p25_ms": go_codec.get("p25"),
            "go_codec_p75_ms": go_codec.get("p75"),
            "go_codec_min_ms": go_codec.get("min"),
            "go_codec_max_ms": go_codec.get("max"),
            "go_wall_median_ms": go_wall.get("median"),
            "go_throughput_mp_s": go_data.get("throughput_mp_s"),
            "go_bytes": go_data.get("out_bytes", 0),
            "go_psnr_db": go_quality.get("psnr_db"),
            "go_exact": bool(go_quality.get("exact")),

            # Rust Metrics
            "rust_codec_median_ms": rust_codec.get("median"),
            "rust_codec_p25_ms": rust_codec.get("p25"),
            "rust_codec_p75_ms": rust_codec.get("p75"),
            "rust_codec_min_ms": rust_codec.get("min"),
            "rust_codec_max_ms": rust_codec.get("max"),
            "rust_wall_median_ms": rust_wall.get("median"),
            "rust_throughput_mp_s": rust_data.get("throughput_mp_s"),
            "rust_bytes": rust_data.get("out_bytes", 0),
            "rust_psnr_db": rust_quality.get("psnr_db"),
            "rust_exact": bool(rust_quality.get("exact")),
        }
        flat_results.append(flat_item)

    # 1. results.json (formato longo): uma linha por tarefa x implementação medida com sucesso
    long_results = long_format(matrix_file)
    with open(matrix_file, "r", encoding="utf-8") as f:
        matrix_meta = json.load(f)["metadata"]

    long_results_path = os.path.join(output_dir, "results.json")
    with open(long_results_path, "w", encoding="utf-8") as f:
        json.dump(long_results, f, ensure_ascii=False, indent=2)

    # 2. Salvar benchmark_results.json
    results_path = os.path.join(output_dir, "benchmark_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(flat_results, f, ensure_ascii=False, indent=2)

    # 3. Salvar per_operation.json
    per_op_path = os.path.join(output_dir, "per_operation.json")
    with open(per_op_path, "w", encoding="utf-8") as f:
        json.dump(per_operation, f, ensure_ascii=False, indent=2)

    # 4. Salvar equal_quality.json
    eq_path = os.path.join(output_dir, "equal_quality.json")
    with open(eq_path, "w", encoding="utf-8") as f:
        json.dump(equal_quality, f, ensure_ascii=False, indent=2)

    # 5. Salvar metadata.json com agregações pré-calculadas
    total_tasks = len(flat_results)
    rust_wins = sum(1 for r in flat_results if r["winner"] == "Rust")
    go_wins = sum(1 for r in flat_results if r["winner"] == "Go")
    ties = sum(1 for r in flat_results if r["winner"] in ("Empate", "Tie"))

    formats = sorted(list(set(r["format"] for r in flat_results if r["format"])))
    ops = sorted(list(set(r["op"] for r in flat_results if r["op"])))
    modes = sorted(list(set(r["mode"] for r in flat_results if r["mode"])))
    images = sorted(list(set(r["image"] for r in flat_results if r["image"])))

    full_metadata = {
        "summary": {
            "total_tasks": total_tasks,
            "rust_wins": rust_wins,
            "go_wins": go_wins,
            "ties": ties,
            "rust_win_percentage": round((rust_wins / total_tasks) * 100, 1) if total_tasks else 0,
            "go_win_percentage": round((go_wins / total_tasks) * 100, 1) if total_tasks else 0,
            "ties_percentage": round((ties / total_tasks) * 100, 1) if total_tasks else 0,
            "global_geomean": next((r["geomean_go_over_rust"] for r in per_operation if r.get("op") == "total"), None),
        },
        "filters_options": {
            "formats": formats,
            "ops": ops,
            "modes": modes,
            "images": images,
        },
        "environment": matrix_meta.get("environment", {}),
        "collected_at": matrix_meta.get("collected_at", ""),
        "iterations": matrix_meta.get("iterations"),
        "warmup": matrix_meta.get("warmup"),
        "mode": matrix_meta.get("mode", "http"),
        "primary_metric": matrix_meta.get("primary_metric", "codec_ms"),
        "notes": metadata.get("notes", []),
    }

    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(full_metadata, f, ensure_ascii=False, indent=2)

    print(f"✓ Dados preparados com sucesso em {output_dir}/")
    print(f"  - Tarefas processadas: {total_tasks}")
    print(f"  - Vitórias Rust: {rust_wins} | Go: {go_wins} | Empates: {ties}")
    print(f"  - Registros em results.json: {len(long_results)} ({len({r['impl_id'] for r in long_results})} implementações)")
    print(f"  - Arquivos gerados: results.json, benchmark_results.json, per_operation.json, equal_quality.json, metadata.json")

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "results/benchmark_results.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "dashboard/public/data"
    matrix = sys.argv[3] if len(sys.argv) > 3 else "results/benchmark_matrix.json"
    prepare_data(src, dst, matrix)
