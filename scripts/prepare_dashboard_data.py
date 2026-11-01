#!/usr/bin/env python3
"""
scripts/prepare_dashboard_data.py

Lê os resultados brutos da Arena (results/benchmark_results.json) e gera
os arquivos JSON estruturados para o DuckDB-Wasm e o dashboard Next.js
em dashboard/public/data/.
"""

import json
import os
import sys

def prepare_data(results_file="results/benchmark_results.json", output_dir="dashboard/public/data"):
    if not os.path.exists(results_file):
        print(f"Erro: Arquivo {results_file} não encontrado.")
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

    # 1. Gerar results.json (formato longo com 68 registros: 34 Rust acelerado + 34 Go acelerado padrão)
    long_results = []
    for idx, r in enumerate(raw_results):
        task_id = idx + 1
        task = r.get("task", "")
        op = r.get("op", "")
        fmt = r.get("format", "")
        mode = r.get("mode", "")
        img = r.get("image", "")
        mp = r.get("mp", 0.0)
        winner = r.get("winner", "")

        go_data = r.get("go", {}) or {}
        rust_data = r.get("rust", {}) or {}

        go_codec = go_data.get("codec_ms", {}) or {}
        rust_codec = rust_data.get("codec_ms", {}) or {}

        go_median = go_codec.get("median") or 0.0
        rust_median = rust_codec.get("median") or 0.0

        min_median = min(go_median, rust_median) if (go_median > 0 and rust_median > 0) else 1.0

        rust_rel = round(rust_median / min_median, 2) if min_median > 0 else 1.0
        go_rel = round(go_median / min_median, 2) if min_median > 0 else 1.0

        rust_quality = rust_data.get("quality", {}) or {}
        go_quality = go_data.get("quality", {}) or {}

        rust_psnr = rust_quality.get("psnr_db")
        go_psnr = go_quality.get("psnr_db")

        rust_p25 = rust_codec.get("p25")
        rust_p75 = rust_codec.get("p75")
        go_p25 = go_codec.get("p25")
        go_p75 = go_codec.get("p75")

        rust_row = {
            "task_id": task_id,
            "task": task,
            "op": op,
            "format": fmt,
            "mode": mode,
            "image": img,
            "mp": mp,
            "language": "rust",
            "tier": "accelerated",
            "toolchain": "stable 1.90",
            "lib": "padrão",
            "impl_id": "rust:accelerated:stable:padrao",
            "codec_median_ms": round(rust_median, 3) if rust_median else 0.0,
            "p25": round(rust_p25, 3) if isinstance(rust_p25, (int, float)) else round(rust_median, 3),
            "p75": round(rust_p75, 3) if isinstance(rust_p75, (int, float)) else round(rust_median, 3),
            "bytes": rust_data.get("out_bytes") or 0,
            "psnr_db": round(rust_psnr, 2) if isinstance(rust_psnr, (int, float)) else None,
            "rel_time": rust_rel,
            "winner": winner
        }

        go_row = {
            "task_id": task_id,
            "task": task,
            "op": op,
            "format": fmt,
            "mode": mode,
            "image": img,
            "mp": mp,
            "language": "go",
            "tier": "accelerated",
            "toolchain": "1.25",
            "lib": "padrão",
            "impl_id": "go:accelerated:1.25:padrao",
            "codec_median_ms": round(go_median, 3) if go_median else 0.0,
            "p25": round(go_p25, 3) if isinstance(go_p25, (int, float)) else round(go_median, 3),
            "p75": round(go_p75, 3) if isinstance(go_p75, (int, float)) else round(go_median, 3),
            "bytes": go_data.get("out_bytes") or 0,
            "psnr_db": round(go_psnr, 2) if isinstance(go_psnr, (int, float)) else None,
            "rel_time": go_rel,
            "winner": winner
        }

        long_results.append(rust_row)
        long_results.append(go_row)

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
            "global_geomean": 2.67,  # Rust 2.67x mais rápido reportado no PODIUM
        },
        "filters_options": {
            "formats": formats,
            "ops": ops,
            "modes": modes,
            "images": images,
        },
        "environment": metadata.get("environment", {}),
        "collected_at": metadata.get("collected_at", ""),
        "mode": metadata.get("mode", "http"),
        "primary_metric": metadata.get("primary_metric", "codec_ms"),
        "notes": metadata.get("notes", []),
    }

    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(full_metadata, f, ensure_ascii=False, indent=2)

    print(f"✓ Dados preparados com sucesso em {output_dir}/")
    print(f"  - Tarefas processadas: {total_tasks}")
    print(f"  - Vitórias Rust: {rust_wins} | Go: {go_wins} | Empates: {ties}")
    print(f"  - Registros em results.json: {len(long_results)}")
    print(f"  - Arquivos gerados: results.json, benchmark_results.json, per_operation.json, equal_quality.json, metadata.json")

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "results/benchmark_results.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "dashboard/public/data"
    prepare_data(src, dst)
