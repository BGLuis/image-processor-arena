#!/usr/bin/env python3
"""
benchmark_arena.py - Suite Oficial de Benchmark e Construção do Pódio (Go Puro × Rust Puro).

Executa a matriz comparativa completa da Arena de Processamento de Imagens:
- Operações: analyze, encode, decode, transcode
- Formatos: PNG, JPEG, WebP (lossy/lossless), AVIF (lossy/lossless), JPEG XL (lossy/lossless)
- Corpus: photo, screenshot, illustration, alpha (Netpbm PAM P7)
- Modos:
    --mode batch: executa os binários locais compilados (arena-batch)
    --mode http: executa requisições HTTP contra servidores (/run)
Gera o relatório do PÓDIO em console, Markdown (results/PODIUM.md) e JSON (results/benchmark_results.json).
"""

import os
import sys
import time
import json
import shutil
import argparse
import subprocess
import tomllib
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple


ARENA_TOML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "arena.toml")


def load_param_contract(path: str = ARENA_TOML) -> Dict[str, Any]:
    """Lê a tabela [params] de arena.toml: o contrato único de mode/q/effort dos dois engines."""
    with open(path, "rb") as f:
        return tomllib.load(f)["params"]


def bytes_ratio(go_bytes: int, rust_bytes: int) -> Optional[float]:
    """Tamanho de saída Go / Rust; None quando a operação não produz arquivo comparável."""
    if go_bytes <= 0 or rust_bytes <= 0:
        return None
    return go_bytes / rust_bytes


def format_ratio(ratio: Optional[float]) -> str:
    return "-" if ratio is None else f"{ratio:.2f}x"


def read_pam_dims(filepath: str) -> Tuple[int, int, int]:
    try:
        with open(filepath, "rb") as f:
            header = f.read(256).decode("ascii", errors="ignore")
        width, height, depth = 0, 0, 3
        for line in header.split("\n"):
            parts = line.strip().split()
            if len(parts) == 2:
                if parts[0] == "WIDTH":
                    width = int(parts[1])
                elif parts[0] == "HEIGHT":
                    height = int(parts[1])
                elif parts[0] == "DEPTH":
                    depth = int(parts[1])
            elif line.strip() == "ENDHDR":
                break
        if width > 0 and height > 0:
            return width, height, depth
    except Exception:
        pass
    return 512, 512, 3


class ArenaBenchmark:
    def __init__(
        self,
        mode: str = "batch",
        go_bin: str = "./go/bin/arena-batch",
        rust_bin: str = "./rust/target/release/arena-batch",
        go_url: str = "http://localhost:8080/run",
        rust_url: str = "http://localhost:8081/run",
        corpus_dir: str = "./harness/fixtures/corpus",
        iterations: int = 5,
        warmup: int = 2,
        params: Optional[Dict[str, Any]] = None,
    ):
        self.params = params or load_param_contract()
        self.mode = mode
        self.go_bin = go_bin
        self.rust_bin = rust_bin
        self.go_url = go_url
        self.rust_url = rust_url
        self.corpus_dir = corpus_dir
        self.iterations = iterations
        self.warmup = warmup
        self.results: List[Dict[str, Any]] = []

    def run_cli_cmd(self, bin_path: str, cmd_args: List[str]) -> Tuple[float, Optional[int]]:
        cmd = [bin_path] + cmd_args
        t0 = time.perf_counter_ns()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        t1 = time.perf_counter_ns()
        if res.returncode != 0:
            err = res.stderr.decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"Comando falhou ({res.returncode}): {' '.join(cmd)}\n{err}")
        elapsed_ms = (t1 - t0) / 1e6
        return elapsed_ms, len(res.stdout) if res.stdout else None

    def run_http_req(self, url: str, query_params: Dict[str, str], body_data: bytes) -> Tuple[float, int]:
        qs = "&".join(f"{k}={v}" for k, v in query_params.items())
        full_url = f"{url}?{qs}"
        req = urllib.request.Request(
            full_url,
            data=body_data,
            headers={"Content-Type": "image/x-netpbm-pam"},
            method="POST",
        )
        t0 = time.perf_counter_ns()
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        t1 = time.perf_counter_ns()
        elapsed_ms = (t1 - t0) / 1e6
        return elapsed_ms, len(data)

    def benchmark_task(
        self,
        task_name: str,
        op: str,
        format_name: str,
        mode: str,
        q: int,
        effort: int,
        input_file: str,
        to_format: Optional[str] = None,
    ) -> Dict[str, Any]:
        width, height, depth = read_pam_dims(input_file)
        mp = (width * height) / 1e6
        if not self.params["q_min"] <= q <= self.params["q_max"]:
            raise ValueError(f"q={q} fora do contrato [{self.params['q_min']}, {self.params['q_max']}]")
        if not self.params["effort_min"] <= effort <= self.params["effort_max"]:
            raise ValueError(f"effort={effort} fora do contrato [{self.params['effort_min']}, {self.params['effort_max']}]")

        if op == "decode":
            out_ext = "pam"
        elif op == "transcode":
            out_ext = to_format or "bin"
        elif op == "analyze":
            out_ext = "json"
        else:
            out_ext = format_name

        # --- Benchmarking Go ---
        go_times = []
        go_out_bytes = 0
        tmp_go = f"/tmp/bench_go_{int(time.time()*1000)}.{out_ext}"

        # Warmup Go
        for _ in range(self.warmup):
            if self.mode == "batch":
                args = ["--op", op, "--format", format_name, "--mode", mode, "--q", str(q), "--effort", str(effort), "--input", input_file]
                if op != "analyze":
                    args.extend(["--output", tmp_go])
                if to_format:
                    args.extend(["--to", to_format])
                self.run_cli_cmd(self.go_bin, args)
            else:
                qp = {"op": op, "format": format_name, "mode": mode, "q": str(q), "effort": str(effort)}
                if to_format:
                    qp["to"] = to_format
                self.run_http_req(self.go_url, qp, open(input_file, "rb").read())

        # Runs Go
        for _ in range(self.iterations):
            if self.mode == "batch":
                args = ["--op", op, "--format", format_name, "--mode", mode, "--q", str(q), "--effort", str(effort), "--input", input_file]
                if op != "analyze":
                    args.extend(["--output", tmp_go])
                if to_format:
                    args.extend(["--to", to_format])
                el, _ = self.run_cli_cmd(self.go_bin, args)
                if os.path.exists(tmp_go):
                    go_out_bytes = os.path.getsize(tmp_go)
            else:
                qp = {"op": op, "format": format_name, "mode": mode, "q": str(q), "effort": str(effort)}
                if to_format:
                    qp["to"] = to_format
                el, go_out_bytes = self.run_http_req(self.go_url, qp, open(input_file, "rb").read())
            go_times.append(el)

        # --- Benchmarking Rust ---
        rust_times = []
        rust_out_bytes = 0
        tmp_rust = f"/tmp/bench_rust_{int(time.time()*1000)}.{out_ext}"

        # Warmup Rust
        for _ in range(self.warmup):
            if self.mode == "batch":
                args = ["--op", op, "--format", format_name, "--mode", mode, "--q", str(q), "--effort", str(effort), "--input", input_file]
                if op != "analyze":
                    args.extend(["--output", tmp_rust])
                if to_format:
                    args.extend(["--to", to_format])
                self.run_cli_cmd(self.rust_bin, args)
            else:
                qp = {"op": op, "format": format_name, "mode": mode, "q": str(q), "effort": str(effort)}
                if to_format:
                    qp["to"] = to_format
                self.run_http_req(self.rust_url, qp, open(input_file, "rb").read())

        # Runs Rust
        for _ in range(self.iterations):
            if self.mode == "batch":
                args = ["--op", op, "--format", format_name, "--mode", mode, "--q", str(q), "--effort", str(effort), "--input", input_file]
                if op != "analyze":
                    args.extend(["--output", tmp_rust])
                if to_format:
                    args.extend(["--to", to_format])
                el, _ = self.run_cli_cmd(self.rust_bin, args)
                if os.path.exists(tmp_rust):
                    rust_out_bytes = os.path.getsize(tmp_rust)
            else:
                qp = {"op": op, "format": format_name, "mode": mode, "q": str(q), "effort": str(effort)}
                if to_format:
                    qp["to"] = to_format
                el, rust_out_bytes = self.run_http_req(self.rust_url, qp, open(input_file, "rb").read())
            rust_times.append(el)

        # Limpeza
        if os.path.exists(tmp_go):
            os.remove(tmp_go)
        if os.path.exists(tmp_rust):
            os.remove(tmp_rust)

        go_times.sort()
        rust_times.sort()
        go_med = go_times[len(go_times) // 2]
        rust_med = rust_times[len(rust_times) // 2]

        go_mp_s = mp / (go_med / 1000.0) if go_med > 0 else 0
        rust_mp_s = mp / (rust_med / 1000.0) if rust_med > 0 else 0

        if op == "analyze":
            go_out_bytes = rust_out_bytes = 0

        winner = "Rust" if rust_med < go_med else "Go"
        speedup = (go_med / rust_med) if winner == "Rust" else (rust_med / go_med)

        return {
            "task": task_name,
            "op": op,
            "format": format_name,
            "mode": mode,
            "image": os.path.basename(input_file),
            "mp": mp,
            "go_ms": go_med,
            "go_mp_s": go_mp_s,
            "go_bytes": go_out_bytes,
            "rust_ms": rust_med,
            "rust_mp_s": rust_mp_s,
            "rust_bytes": rust_out_bytes,
            "bytes_ratio": bytes_ratio(go_out_bytes, rust_out_bytes),
            "winner": winner,
            "speedup": speedup,
        }

    def run_suite(self) -> List[Dict[str, Any]]:
        corpus_images = [
            os.path.join(self.corpus_dir, "photo.pam"),
            os.path.join(self.corpus_dir, "screenshot.pam"),
            os.path.join(self.corpus_dir, "illustration.pam"),
            os.path.join(self.corpus_dir, "alpha.pam"),
        ]

        q = self.params["q_default"]
        effort = self.params["effort_default"]
        tasks = []

        # 1. ANALYZE (16 métricas formais)
        for img in corpus_images:
            name = f"Analyze [{os.path.basename(img)}]"
            tasks.append((name, "analyze", "pam", "lossless", q, effort, img, None))

        # 2. ENCODE PNG
        for img in corpus_images:
            name = f"Encode PNG [{os.path.basename(img)}]"
            tasks.append((name, "encode", "png", "lossless", q, effort, img, None))

        # 3. ENCODE JPEG (exceto alpha)
        for img in corpus_images[:3]:
            name = f"Encode JPEG [{os.path.basename(img)}]"
            tasks.append((name, "encode", "jpeg", "lossy", q, effort, img, None))

        # 4. ENCODE WebP Lossy & Lossless
        for img in corpus_images:
            name = f"Encode WebP Lossy [{os.path.basename(img)}]"
            tasks.append((name, "encode", "webp", "lossy", q, effort, img, None))
            name_ll = f"Encode WebP Lossless [{os.path.basename(img)}]"
            tasks.append((name_ll, "encode", "webp", "lossless", q, effort, img, None))

        # 5. ENCODE AVIF Lossy & Lossless
        for img in corpus_images[:2]:  # photo e screenshot para avif
            name = f"Encode AVIF Lossy [{os.path.basename(img)}]"
            tasks.append((name, "encode", "avif", "lossy", q, effort, img, None))
            name_ll = f"Encode AVIF Lossless [{os.path.basename(img)}]"
            tasks.append((name_ll, "encode", "avif", "lossless", q, effort, img, None))

        # 6. ENCODE JPEG XL Lossy & Lossless
        for img in corpus_images[:2]:  # photo e screenshot para jxl
            name = f"Encode JXL Lossy [{os.path.basename(img)}]"
            tasks.append((name, "encode", "jxl", "lossy", q, effort, img, None))
            name_ll = f"Encode JXL Lossless [{os.path.basename(img)}]"
            tasks.append((name_ll, "encode", "jxl", "lossless", q, effort, img, None))

        # 7. DECODE (PNG, JPEG, WebP, AVIF, JXL)
        photo_png = os.path.join(self.corpus_dir, "photo.png")
        photo_jpg = os.path.join(self.corpus_dir, "photo.jpg")
        photo_webp = os.path.join(self.corpus_dir, "photo.webp")
        photo_avif = os.path.join(self.corpus_dir, "photo.avif")
        photo_jxl = os.path.join(self.corpus_dir, "photo.jxl")

        tasks.append(("Decode PNG [photo.png]", "decode", "png", "lossless", q, effort, photo_png, None))
        tasks.append(("Decode JPEG [photo.jpg]", "decode", "jpeg", "lossy", q, effort, photo_jpg, None))
        tasks.append(("Decode WebP [photo.webp]", "decode", "webp", "lossy", q, effort, photo_webp, None))
        tasks.append(("Decode AVIF [photo.avif]", "decode", "avif", "lossy", q, effort, photo_avif, None))
        tasks.append(("Decode JXL [photo.jxl]", "decode", "jxl", "lossy", q, effort, photo_jxl, None))

        # 8. TRANSCODE (PNG -> WebP, PNG -> AVIF, JPEG -> WebP, JXL -> PNG)
        tasks.append(("Transcode PNG -> WebP", "transcode", "png", "lossy", q, effort, photo_png, "webp"))
        tasks.append(("Transcode PNG -> AVIF", "transcode", "png", "lossy", q, effort, photo_png, "avif"))
        tasks.append(("Transcode JPEG -> WebP", "transcode", "jpeg", "lossy", q, effort, photo_jpg, "webp"))
        tasks.append(("Transcode JXL -> PNG", "transcode", "jxl", "lossless", q, effort, photo_jxl, "png"))

        print("=" * 80)
        print("          ARENA DE PROCESSAMENTO DE IMAGENS — BATERIA DE BENCHMARK")
        print(f"Modo: {self.mode.upper()} | Iterações: {self.iterations} | Warmup: {self.warmup}")
        print("=" * 80)

        results = []
        for i, (task_name, op, fmt, mode, q, effort, in_file, to_fmt) in enumerate(tasks, start=1):
            print(f"[{i:02d}/{len(tasks):02d}] Executando: {task_name:35s} ... ", end="", flush=True)
            try:
                res = self.benchmark_task(task_name, op, fmt, mode, q, effort, in_file, to_fmt)
                results.append(res)
                medal = "🦀 Rust" if res["winner"] == "Rust" else "🐹 Go"
                print(f"Vencedor: {medal} ({res['speedup']:.2f}x mais rápido) "
                      f"[Go: {res['go_ms']:.2f}ms | Rust: {res['rust_ms']:.2f}ms]")
            except Exception as e:
                print(f"ERRO: {e}")

        self.results = results
        return results

    def print_podium(self) -> None:
        if not self.results:
            print("Nenhum resultado para exibir.")
            return

        go_wins = sum(1 for r in self.results if r["winner"] == "Go")
        rust_wins = sum(1 for r in self.results if r["winner"] == "Rust")
        total = len(self.results)

        print("\n" + "=" * 90)
        print("                      🏆 PÓDIO OFICIAL DA ARENA: GO PURO × RUST PURO 🏆")
        print("=" * 90)

        if rust_wins > go_wins:
            champion = "🦀 RUST PURO 🦀"
            runner_up = "🐹 GO PURO 🐹"
            champ_score = f"{rust_wins}/{total} vitórias ({rust_wins/total*100:.1f}%)"
            runner_score = f"{go_wins}/{total} vitórias ({go_wins/total*100:.1f}%)"
        elif go_wins > rust_wins:
            champion = "🐹 GO PURO 🐹"
            runner_up = "🦀 RUST PURO 🦀"
            champ_score = f"{go_wins}/{total} vitórias ({go_wins/total*100:.1f}%)"
            runner_score = f"{rust_wins}/{total} vitórias ({rust_wins/total*100:.1f}%)"
        else:
            champion = "🤝 EMPATE TÉCNICO"
            runner_up = "🤝 EMPATE TÉCNICO"
            champ_score = f"{rust_wins}/{total} vitórias"
            runner_score = f"{go_wins}/{total} vitórias"

        print(f"\n   🥇 1º LUGAR (CAMPEÃO GERAL): {champion}")
        print(f"      Pontuação: {champ_score}")
        print(f"\n   🥈 2º LUGAR (VICE-CAMPEÃO):  {runner_up}")
        print(f"      Pontuação: {runner_score}")
        print("\n" + "-" * 90)

        # Tabela Detalhada
        print(f"{'Operação / Tarefa':32s} | {'Go (ms)':9s} | {'Go MP/s':8s} | {'Rust (ms)':9s} | {'Rust MP/s':9s} | {'Go (B)':9s} | {'Rust (B)':9s} | {'Go/Rust':7s} | {'Vencedor':8s} | {'Vantagem':8s}")
        print("-" * 140)
        for r in self.results:
            medal = "🦀 Rust" if r["winner"] == "Rust" else "🐹 Go"
            adv = f"{r['speedup']:.2f}x"
            print(f"{r['task']:32s} | {r['go_ms']:7.2f}ms | {r['go_mp_s']:7.2f} | {r['rust_ms']:7.2f}ms | {r['rust_mp_s']:8.2f} | {r['go_bytes']:9d} | {r['rust_bytes']:9d} | {format_ratio(r['bytes_ratio']):7s} | {medal:8s} | {adv:8s}")
        print("=" * 140)

    def export_reports(self, output_dir: str = "./results") -> None:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "benchmark_results.json")
        md_path = os.path.join(output_dir, "PODIUM.md")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)

        go_wins = sum(1 for r in self.results if r["winner"] == "Go")
        rust_wins = sum(1 for r in self.results if r["winner"] == "Rust")
        total = len(self.results)

        md = []
        md.append("# 🏆 Pódio da Arena: Go Puro × Rust Puro\n")
        md.append(f"**Modo de Execução**: `{self.mode.upper()}`  ")
        md.append(f"**Iterações por teste**: {self.iterations} (+ {self.warmup} warmup)  ")
        md.append(f"**Data da Coleta**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        md.append("## 🥇 Classificação Geral\n")
        if rust_wins >= go_wins:
            md.append(f"- 🥇 **1º Lugar: Rust Puro** ({rust_wins}/{total} vitórias - {rust_wins/total*100:.1f}%)")
            md.append(f"- 🥈 **2º Lugar: Go Puro** ({go_wins}/{total} vitórias - {go_wins/total*100:.1f}%)\n")
        else:
            md.append(f"- 🥇 **1º Lugar: Go Puro** ({go_wins}/{total} vitórias - {go_wins/total*100:.1f}%)")
            md.append(f"- 🥈 **2º Lugar: Rust Puro** ({rust_wins}/{total} vitórias - {rust_wins/total*100:.1f}%)\n")

        md.append("## 📊 Tabela Completa de Resultados\n")
        md.append(f"Parâmetros (arena.toml `[params]`): q={self.params['q_default']}, effort={self.params['effort_default']}, mode padrão `{self.params['mode_default']}`. "
                  "Go/Rust acima de 1 significa saída maior no Go; o tempo só é comparável junto do tamanho.\n")
        md.append("| Tarefa / Operação | Go (tempo) | Go Throughput | Rust (tempo) | Rust Throughput | Go (bytes) | Rust (bytes) | Go/Rust | 🥇 Vencedor | Vantagem |")
        md.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in self.results:
            medal = "🦀 Rust" if r["winner"] == "Rust" else "🐹 Go"
            md.append(f"| {r['task']} | {r['go_ms']:.2f} ms | {r['go_mp_s']:.2f} MP/s | {r['rust_ms']:.2f} ms | {r['rust_mp_s']:.2f} MP/s | {r['go_bytes']} | {r['rust_bytes']} | {format_ratio(r['bytes_ratio'])} | {medal} | **{r['speedup']:.2f}x** |")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        print(f"\n[✓] Relatórios exportados para:")
        print(f"    - JSON: {json_path}")
        print(f"    - Markdown: {md_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Arena Benchmark Runner & Podium Builder")
    parser.add_argument("--mode", choices=["batch", "http"], default="batch", help="Modo de benchmark (batch ou http)")
    parser.add_argument("--go-bin", default="./go/bin/arena-batch", help="Caminho do binário Go arena-batch")
    parser.add_argument("--rust-bin", default="./rust/target/release/arena-batch", help="Caminho do binário Rust arena-batch")
    parser.add_argument("--go-url", default="http://localhost:8080/run", help="URL do endpoint Go")
    parser.add_argument("--rust-url", default="http://localhost:8081/run", help="URL do endpoint Rust")
    parser.add_argument("--corpus-dir", default="./harness/fixtures/corpus", help="Diretório do corpus de imagens PAM")
    parser.add_argument("--iterations", type=int, default=5, help="Número de iterações medidas por teste")
    parser.add_argument("--warmup", type=int, default=2, help="Número de iterações de warmup descartadas")
    parser.add_argument("--output-dir", default="./results", help="Diretório para salvar os resultados")
    parser.add_argument("--arena-toml", default=ARENA_TOML, help="arena.toml com a tabela [params] (q, effort e mode padrão)")
    args = parser.parse_args()

    bench = ArenaBenchmark(
        mode=args.mode,
        go_bin=args.go_bin,
        rust_bin=args.rust_bin,
        go_url=args.go_url,
        rust_url=args.rust_url,
        corpus_dir=args.corpus_dir,
        iterations=args.iterations,
        warmup=args.warmup,
        params=load_param_contract(args.arena_toml),
    )

    bench.run_suite()
    bench.print_podium()
    bench.export_reports(args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
