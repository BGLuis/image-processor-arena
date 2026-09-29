#!/usr/bin/env python3
"""
benchmark_arena.py - Suite Oficial de Benchmark e Construção do Pódio (Go Puro × Rust Puro).

Executa a matriz comparativa completa da Arena de Processamento de Imagens:
- Operações: analyze, encode, decode, transcode
- Formatos: PNG, JPEG, WebP (lossy/lossless), AVIF (lossy), JPEG XL (lossy/lossless)
- Corpus: photo, screenshot, illustration, alpha (Netpbm PAM P7)
- Modos:
    --mode http: executa requisições HTTP contra servidores (/run); a métrica primária é o tempo de codec
        reportado pelos headers X-Arena-*-Ns, e o tempo de parede do cliente é reportado à parte
    --mode batch: executa os binários locais compilados (arena-batch); cronometra o processo inteiro e
        reporta o custo de startup de cada binário separadamente. Não mede velocidade de codec.
Cada tempo é reportado como mediana com p25-p75 (mínimo de 5 iterações medidas).
Gera o relatório do PÓDIO em console, Markdown (results/PODIUM.md) e JSON (results/benchmark_results.json).
"""

import os
import sys
import time
import json
import shutil
import argparse
import statistics
import subprocess
import tempfile
import tomllib
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

MIN_ITERATIONS = 5
STARTUP_PROBE_ARGS = ["--op", "analyze", "--input", "/dev/null"]
CODEC_TIME_HEADERS = {
    "analyze": ("X-Arena-Analyze-Ns",),
    "encode": ("X-Arena-Encode-Ns",),
    "decode": ("X-Arena-Decode-Ns",),
    "transcode": ("X-Arena-Decode-Ns", "X-Arena-Encode-Ns"),
}
ANALYZE_CAVEAT = (
    "op=analyze: os servidores cronometram trechos diferentes (Rust inclui parse do PAM e serialização JSON; "
    "Go mede só a análise), então o tempo de analyze não é comparável entre Go e Rust (issue #7)."
)

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


def summarize(samples: List[float]) -> Dict[str, float]:
    ordered = sorted(samples)
    p25, _, p75 = statistics.quantiles(ordered, n=4, method="inclusive")
    return {
        "median": statistics.median(ordered),
        "p25": p25,
        "p75": p75,
        "min": ordered[0],
        "max": ordered[-1],
        "n": len(ordered),
    }


def format_stats(stats: Dict[str, float]) -> str:
    return f"{stats['median']:.2f} [{stats['p25']:.2f}-{stats['p75']:.2f}]"


def decide_winner(go: Dict[str, float], rust: Dict[str, float]) -> Tuple[str, float]:
    fastest = min(go["median"], rust["median"])
    speedup = max(go["median"], rust["median"]) / fastest if fastest > 0 else 0.0
    if go["p25"] <= rust["p75"] and rust["p25"] <= go["p75"]:
        return "Empate", speedup
    return ("Go" if go["median"] < rust["median"] else "Rust"), speedup


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


@dataclass(frozen=True)
class Engine:
    key: str
    bin_path: str
    url: str


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
        if iterations < MIN_ITERATIONS:
            raise ValueError(f"iterations deve ser >= {MIN_ITERATIONS} (recebido: {iterations})")
        self.params = params or load_param_contract()
        self.mode = mode
        self.engines = [Engine("go", go_bin, go_url), Engine("rust", rust_bin, rust_url)]
        self.corpus_dir = corpus_dir
        self.iterations = iterations
        self.warmup = warmup
        self.results: List[Dict[str, Any]] = []
        self.startup_ms: Dict[str, Dict[str, float]] = {}

    @property
    def metric(self) -> str:
        return "codec_ms" if self.mode == "http" else "wall_ms"

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

    def run_startup_probe(self, bin_path: str) -> float:
        t0 = time.perf_counter_ns()
        subprocess.run([bin_path] + STARTUP_PROBE_ARGS, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return (time.perf_counter_ns() - t0) / 1e6

    def measure_startup(self) -> None:
        for engine in self.engines:
            samples = []
            for i in range(self.warmup + self.iterations):
                elapsed_ms = self.run_startup_probe(engine.bin_path)
                if i >= self.warmup:
                    samples.append(elapsed_ms)
            self.startup_ms[engine.key] = summarize(samples)

    def run_http_req(
        self, url: str, op: str, query_params: Dict[str, str], body_data: bytes
    ) -> Tuple[float, float, int]:
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
            codec_ns = 0
            for header in CODEC_TIME_HEADERS[op]:
                value = resp.headers.get(header)
                if value is None:
                    raise RuntimeError(f"Resposta sem o header {header} (op={op}, url={url})")
                codec_ns += int(value)
        t1 = time.perf_counter_ns()
        wall_ms = (t1 - t0) / 1e6
        return wall_ms, codec_ns / 1e6, len(data)

    def measure_engine(
        self,
        engine: Engine,
        op: str,
        batch_args: List[str],
        query_params: Dict[str, str],
        body_data: Optional[bytes],
        output_path: str,
    ) -> Dict[str, Any]:
        wall_samples: List[float] = []
        codec_samples: List[float] = []
        out_bytes = 0

        cli_args = list(batch_args)
        if op != "analyze":
            cli_args.extend(["--output", output_path])

        for i in range(self.warmup + self.iterations):
            if self.mode == "batch":
                wall_ms, stdout_bytes = self.run_cli_cmd(engine.bin_path, cli_args)
                out_bytes = os.path.getsize(output_path) if os.path.exists(output_path) else (stdout_bytes or 0)
            else:
                wall_ms, codec_ms, out_bytes = self.run_http_req(engine.url, op, query_params, body_data)
            if i < self.warmup:
                continue
            wall_samples.append(wall_ms)
            if self.mode == "http":
                codec_samples.append(codec_ms)

        result: Dict[str, Any] = {
            "wall_ms": summarize(wall_samples),
            "codec_ms": None,
            "net_of_startup_ms": None,
            "out_bytes": out_bytes,
        }
        if self.mode == "http":
            result["codec_ms"] = summarize(codec_samples)
        else:
            startup_median = self.startup_ms[engine.key]["median"]
            result["net_of_startup_ms"] = summarize([max(w - startup_median, 0.0) for w in wall_samples])
        return result

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

        batch_args = ["--op", op, "--format", format_name, "--mode", mode, "--q", str(q), "--effort", str(effort), "--input", input_file]
        query_params = {"op": op, "format": format_name, "mode": mode, "q": str(q), "effort": str(effort)}
        if to_format:
            batch_args.extend(["--to", to_format])
            query_params["to"] = to_format

        body_data = None
        if self.mode == "http":
            with open(input_file, "rb") as f:
                body_data = f.read()

        measured: Dict[str, Dict[str, Any]] = {}
        with tempfile.TemporaryDirectory(prefix="arena_bench_") as workdir:
            for engine in self.engines:
                output_path = os.path.join(workdir, f"{engine.key}.{out_ext}")
                measured[engine.key] = self.measure_engine(engine, op, batch_args, query_params, body_data, output_path)

        if op == "analyze":
            measured["go"]["out_bytes"] = measured["rust"]["out_bytes"] = 0

        go_primary = measured["go"][self.metric]
        rust_primary = measured["rust"][self.metric]
        winner, speedup = decide_winner(go_primary, rust_primary)

        for engine_result, primary in ((measured["go"], go_primary), (measured["rust"], rust_primary)):
            engine_result["throughput_mp_s"] = (
                mp / (primary["median"] / 1000.0) if self.mode == "http" and primary["median"] > 0 else None
            )

        return {
            "task": task_name,
            "op": op,
            "format": format_name,
            "mode": mode,
            "image": os.path.basename(input_file),
            "mp": mp,
            "metric": self.metric,
            "go": measured["go"],
            "rust": measured["rust"],
            "bytes_ratio": bytes_ratio(measured["go"]["out_bytes"], measured["rust"]["out_bytes"]),
            "winner": winner,
            "speedup": speedup,
            "caveat": ANALYZE_CAVEAT if self.mode == "http" and op == "analyze" else None,
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

        # 5. ENCODE AVIF Lossy (lossless não é suportado por nenhuma biblioteca pura)
        for img in corpus_images[:2]:  # photo e screenshot para avif
            name = f"Encode AVIF Lossy [{os.path.basename(img)}]"
            tasks.append((name, "encode", "avif", "lossy", q, effort, img, None))

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

        if self.mode == "batch":
            self.measure_startup()
            for engine in self.engines:
                print(f"Startup {engine.key:5s}: {format_stats(self.startup_ms[engine.key])} ms")

        results = []
        for i, (task_name, op, fmt, mode, q, effort, in_file, to_fmt) in enumerate(tasks, start=1):
            print(f"[{i:02d}/{len(tasks):02d}] Executando: {task_name:35s} ... ", end="", flush=True)
            try:
                res = self.benchmark_task(task_name, op, fmt, mode, q, effort, in_file, to_fmt)
                results.append(res)
                print(f"Vencedor: {res['winner']} ({res['speedup']:.2f}x) "
                      f"[Go: {format_stats(res['go'][res['metric']])} ms | Rust: {format_stats(res['rust'][res['metric']])} ms]")
            except Exception as e:
                print(f"ERRO: {e}")

        self.results = results
        return results

    def standings(self) -> Tuple[int, int, int]:
        go_wins = sum(1 for r in self.results if r["winner"] == "Go")
        rust_wins = sum(1 for r in self.results if r["winner"] == "Rust")
        ties = len(self.results) - go_wins - rust_wins
        return go_wins, rust_wins, ties

    def metric_labels(self) -> Dict[str, str]:
        if self.mode == "http":
            return {
                "column": "codec (servidor, X-Arena-*-Ns)",
                "winner": "Vencedor (codec)",
                "verdict": "Vitórias em tempo de codec",
            }
        return {
            "column": "processo completo (startup + codec + I/O)",
            "winner": "Vencedor (processo completo)",
            "verdict": "Vitórias em tempo de processo completo (NÃO é velocidade de codec)",
        }

    def notes(self) -> List[str]:
        if self.mode == "http":
            return [
                "Métrica primária: tempo de codec reportado pelo servidor nos headers X-Arena-*-Ns "
                "(transcode = decode + encode). A coluna de parede do cliente inclui rede, PAM e serialização.",
                ANALYZE_CAVEAT,
            ]
        return [
            "Modo batch cronometra o processo inteiro, incluindo o startup do binário. "
            "Ele NÃO mede velocidade de codec; para isso use --mode http.",
            "Startup medido executando cada binário com entrada vazia/inválida (--op analyze --input /dev/null).",
            "Coluna 'líquido de startup' = tempo de parede de cada amostra menos a mediana do startup do binário; "
            "é uma aproximação, não um tempo de codec isolado.",
        ]

    def print_podium(self) -> None:
        if not self.results:
            print("Nenhum resultado para exibir.")
            return

        labels = self.metric_labels()
        go_wins, rust_wins, ties = self.standings()
        total = len(self.results)

        print("\n" + "=" * 110)
        print("                      PÓDIO DA ARENA: GO PURO × RUST PURO")
        print("=" * 110)
        print(f"Métrica primária: {labels['column']}")
        print(f"{labels['verdict']}: Go {go_wins}/{total} | Rust {rust_wins}/{total} | Empates estatísticos {ties}/{total}")

        if self.startup_ms:
            print("\nCusto de startup do binário (processo com entrada inválida, ms):")
            for engine in self.engines:
                print(f"  {engine.key:5s} {format_stats(self.startup_ms[engine.key])}  (min {self.startup_ms[engine.key]['min']:.2f} / max {self.startup_ms[engine.key]['max']:.2f})")

        print("\n" + "-" * 110)
        print(f"Tempos: mediana [p25-p75] em ms, {self.iterations} iterações medidas")
        print(f"{'Tarefa':34s} | {'Go':22s} | {'Rust':22s} | {'Go (B)':9s} | {'Rust (B)':9s} | {'Go/Rust':7s} | {'Vencedor':8s} | {'Vantagem':8s}")
        print("-" * 140)
        for r in self.results:
            task = r["task"] + (" †" if r["caveat"] else "")
            adv = f"{r['speedup']:.2f}x"
            print(f"{task:34s} | {format_stats(r['go'][r['metric']]):22s} | {format_stats(r['rust'][r['metric']]):22s} | {r['go']['out_bytes']:9d} | {r['rust']['out_bytes']:9d} | {format_ratio(r['bytes_ratio']):7s} | {r['winner']:8s} | {adv:8s}")
        print("=" * 140)
        for note in self.notes():
            print(f"* {note}")

    def export_reports(self, output_dir: str = "./results") -> None:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "benchmark_results.json")
        md_path = os.path.join(output_dir, "PODIUM.md")
        labels = self.metric_labels()
        collected_at = time.strftime("%Y-%m-%d %H:%M:%S")

        metadata = {
            "mode": self.mode,
            "primary_metric": self.metric,
            "primary_metric_description": labels["column"],
            "iterations": self.iterations,
            "warmup": self.warmup,
            "collected_at": collected_at,
            "startup_ms": self.startup_ms or None,
            "notes": self.notes(),
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"metadata": metadata, "results": self.results}, f, indent=2)

        go_wins, rust_wins, ties = self.standings()
        total = len(self.results)

        md = []
        md.append("# 🏆 Pódio da Arena: Go Puro × Rust Puro\n")
        md.append(f"**Modo de Execução**: `{self.mode.upper()}`  ")
        md.append(f"**Métrica primária**: {labels['column']}  ")
        md.append(f"**Iterações por teste**: {self.iterations} medidas (+ {self.warmup} warmup); tempos como mediana [p25-p75]  ")
        md.append(f"**Data da Coleta**: {collected_at}\n")
        md.append("## Notas de Medição\n")
        for note in self.notes():
            md.append(f"- {note}")
        md.append("")

        if self.startup_ms:
            md.append("## ⏱️ Custo de Startup do Binário (não é custo de codec)\n")
            md.append("| Binário | Startup mediana [p25-p75] | Mín | Máx |")
            md.append("|---|---|---|---|")
            for engine in self.engines:
                s = self.startup_ms[engine.key]
                md.append(f"| {engine.key.capitalize()} | {format_stats(s)} ms | {s['min']:.2f} ms | {s['max']:.2f} ms |")
            md.append("")

        md.append("## 🥇 Classificação Geral\n")
        md.append(f"{labels['verdict']} (empate estatístico quando os intervalos p25-p75 se sobrepõem):\n")
        md.append(f"- Go Puro: {go_wins}/{total} ({go_wins/total*100:.1f}%)")
        md.append(f"- Rust Puro: {rust_wins}/{total} ({rust_wins/total*100:.1f}%)")
        md.append(f"- Empates estatísticos: {ties}/{total} ({ties/total*100:.1f}%)\n")

        md.append("## 📊 Tabela Completa de Resultados\n")
        md.append(f"Parâmetros (arena.toml `[params]`): q={self.params['q_default']}, effort={self.params['effort_default']}, mode padrão `{self.params['mode_default']}`. "
                  "Go/Rust acima de 1 significa saída maior no Go; o tempo só é comparável junto do tamanho.\n")
        if self.mode == "http":
            md.append("| Tarefa / Operação | Go codec (ms) | Go MP/s | Rust codec (ms) | Rust MP/s | Go parede cliente (ms) | Rust parede cliente (ms) | Go (bytes) | Rust (bytes) | Go/Rust | 🥇 Vencedor (codec) | Vantagem |")
            md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for r in self.results:
                task = r["task"] + (" †" if r["caveat"] else "")
                md.append(
                    f"| {task} | {format_stats(r['go']['codec_ms'])} | {r['go']['throughput_mp_s']:.2f} "
                    f"| {format_stats(r['rust']['codec_ms'])} | {r['rust']['throughput_mp_s']:.2f} "
                    f"| {r['go']['wall_ms']['median']:.2f} | {r['rust']['wall_ms']['median']:.2f} "
                    f"| {r['go']['out_bytes']} | {r['rust']['out_bytes']} | {format_ratio(r['bytes_ratio'])} "
                    f"| {r['winner']} | **{r['speedup']:.2f}x** |"
                )
            md.append("\n† " + ANALYZE_CAVEAT)
        else:
            md.append("| Tarefa / Operação | Go processo completo (ms) | Rust processo completo (ms) | Go líquido de startup (ms) | Rust líquido de startup (ms) | Go (bytes) | Rust (bytes) | Go/Rust | 🥇 Vencedor (processo completo) | Vantagem |")
            md.append("|---|---|---|---|---|---|---|---|---|---|")
            for r in self.results:
                md.append(
                    f"| {r['task']} | {format_stats(r['go']['wall_ms'])} | {format_stats(r['rust']['wall_ms'])} "
                    f"| {format_stats(r['go']['net_of_startup_ms'])} | {format_stats(r['rust']['net_of_startup_ms'])} "
                    f"| {r['go']['out_bytes']} | {r['rust']['out_bytes']} | {format_ratio(r['bytes_ratio'])} "
                    f"| {r['winner']} | **{r['speedup']:.2f}x** |"
                )

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
    parser.add_argument("--iterations", type=int, default=MIN_ITERATIONS, help=f"Número de iterações medidas por teste (mínimo {MIN_ITERATIONS})")
    parser.add_argument("--warmup", type=int, default=2, help="Número de iterações de warmup descartadas")
    parser.add_argument("--output-dir", default="./results", help="Diretório para salvar os resultados")
    parser.add_argument("--arena-toml", default=ARENA_TOML, help="arena.toml com a tabela [params] (q, effort e mode padrão)")
    args = parser.parse_args()
    if args.iterations < MIN_ITERATIONS:
        parser.error(f"--iterations deve ser >= {MIN_ITERATIONS} para reportar mediana e dispersão")

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
