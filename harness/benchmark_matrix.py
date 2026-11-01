#!/usr/bin/env python3
"""
benchmark_matrix.py - Bateria multi-implementação (Go, Rust, C++ e Python em todas as variantes).

Sobe o servidor HTTP de cada variante compilada, um de cada vez, e mede as mesmas tarefas do pódio
(ArenaBenchmark.build_tasks) com as mesmas regras: tempo de codec dos headers X-Arena-*-Ns, mediana com
p25-p75, warmup descartado e cada saída validada pelo decoder de referência antes de o tempo valer.

Grava results/benchmark_matrix.json em formato longo (uma linha por tarefa x implementação), a fonte do
dashboard. O duelo Go x Rust (benchmark_arena.py, results/PODIUM.md) continua sendo o relatório oficial.

Uma variante que responde 4xx/501 a uma tarefa não a suporta (ex.: Python puro só codifica PNG): a linha
fica com status "unsupported" e conta como cobertura incompleta, não como falha. Qualquer outro erro, ou
uma saída recusada pela validação, é "failed" e faz o script terminar com código 1.

Pré-requisito: compilar as variantes (go/scripts/build-variants.sh, rust/scripts/build-variants.sh,
make -C cpp all). Variantes sem binário são puladas com aviso.
"""

import argparse
import dataclasses
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import arena_quality as quality
from benchmark_arena import (
    ARENA_TOML,
    MIN_ITERATIONS,
    ArenaBenchmark,
    Engine,
    HttpClient,
    Task,
    default_tmp_dir,
    environment,
    format_stats,
    load_arena_toml,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SERVER_START_TIMEOUT_S = 30.0
UNSUPPORTED_STATUS = re.compile(r"^HTTP (4\d\d|501)\b")


@dataclass(frozen=True)
class Variant:
    language: str
    tier: str
    toolchain: str  # chave de TOOLCHAIN_PROBES
    lib: str
    server: Tuple[str, ...]  # comando relativo à raiz do repositório
    impl: Optional[str] = None  # valor de ?impl= enviado em toda requisição


# Nomes de tier e lib seguem os scripts de build de cada linguagem (go/rust build-variants.sh, cpp/Makefile).
# O Python sobe com o interpretador do harness para herdar numpy/Pillow/pillow-jxl-plugin do mesmo ambiente.
VARIANTS: Tuple[Variant, ...] = (
    Variant("go", "portable", "go", "noasm", ("go/bin/arena-server-portable",)),
    Variant("go", "accelerated", "go", "padrao", ("go/bin/arena-server",)),
    Variant("go", "accelerated", "go", "pgo", ("go/bin/arena-server-pgo",)),
    Variant("go", "hybrid", "go", "cgo", ("go/bin/arena-server-hybrid",)),
    Variant("rust", "portable", "rust", "no-simd", ("rust/target/release/arena-server-portable",)),
    Variant("rust", "accelerated", "rust", "padrao", ("rust/target/release/arena-server",)),
    Variant("rust", "accelerated", "rust", "native-cpu", ("rust/target/release/arena-server-native",)),
    Variant("rust", "accelerated", "rust", "image-rs", ("rust/target/release/arena-server",), impl="image-rs"),
    Variant("rust", "hybrid", "rust", "ffi", ("rust/target/release/arena-server-hybrid",)),
    Variant("cpp", "portable", "gcc", "lodepng", ("cpp/bin/arena-server-portable",)),
    Variant("cpp", "accelerated", "gcc", "native", ("cpp/bin/arena-server",)),
    Variant("cpp", "accelerated", "clang", "native", ("cpp/bin/arena-server-clang",)),
    Variant("python", "portable", "python", "pure", (sys.executable, "python/bin/arena-server"), impl="pure"),
    Variant("python", "accelerated", "python", "numpy", (sys.executable, "python/bin/arena-server"), impl="numpy"),
    Variant("python", "hybrid", "python", "pillow", (sys.executable, "python/bin/arena-server"), impl="pillow"),
)

TOOLCHAIN_PROBES: Dict[str, Tuple[List[str], str, str]] = {
    # chave: (comando, regex da versão, formato do rótulo)
    "go": (["go", "version"], r"go(\d+\.\d+)", "{}"),
    "rust": (["rustc", "--version"], r"(\d+\.\d+)", "{}"),
    "gcc": (["g++", "-dumpfullversion"], r"(\d+)", "gcc {}"),
    "clang": (["clang++", "--version"], r"version (\d+)", "clang {}"),
    "python": ([sys.executable, "--version"], r"(\d+\.\d+)", "{}"),
}


def toolchain_label(key: str) -> str:
    cmd, pattern, label = TOOLCHAIN_PROBES[key]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return "desconhecido"
    match = re.search(pattern, out)
    return label.format(match.group(1)) if match else "desconhecido"


def impl_id(v: Variant, toolchain: str) -> str:
    return f"{v.language}:{v.tier}:{toolchain}:{v.lib}"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    """Um servidor de variante vivo durante o bloco `with`."""

    def __init__(self, cmd: Tuple[str, ...], port: int, log_path: str):
        self.cmd = [c if os.path.isabs(c) else os.path.join(REPO_ROOT, c) for c in cmd]
        self.port = port
        self.log_path = log_path
        self.proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "Server":
        log = open(self.log_path, "wb")
        try:
            self.proc = subprocess.Popen(
                self.cmd, cwd=REPO_ROOT, env={**os.environ, "PORT": str(self.port)},
                stdout=log, stderr=subprocess.STDOUT,
            )
        finally:
            log.close()
        deadline = time.monotonic() + SERVER_START_TIMEOUT_S
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"servidor terminou com código {self.proc.returncode} ao iniciar: {self.tail_log()}")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return self
            except OSError:
                time.sleep(0.1)
        self.__exit__(None, None, None)
        raise RuntimeError(f"servidor não abriu a porta {self.port} em {SERVER_START_TIMEOUT_S:.0f}s")

    def __exit__(self, *_: Any) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()

    def tail_log(self, limit: int = 400) -> str:
        try:
            with open(self.log_path, "rb") as f:
                return f.read()[-limit:].decode(errors="replace").strip()
        except OSError:
            return ""


def classify_error(exc: Exception) -> str:
    return "unsupported" if UNSUPPORTED_STATUS.match(str(exc)) else "failed"


def short_error(exc: Exception, limit: int = 300) -> str:
    """Uma linha legível: o servidor Python responde erros como página HTML (BaseHTTPRequestHandler)."""
    text = re.sub(r"<(style|head)[^>]*>.*?</\1>", " ", str(exc), flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def measure_task(bench: ArenaBenchmark, engine: Engine, task: Task, body: bytes) -> Dict[str, Any]:
    """Mede uma tarefa numa variante. Devolve status, estatísticas e qualidade (ou o erro)."""
    q, effort = bench.params["q_default"], bench.params["effort_default"]
    try:
        stats, output = bench.measure_engine(engine, task, q, effort, body, os.devnull)
    except Exception as exc:  # noqa: BLE001 - o tipo do erro só decide o status
        return {"status": classify_error(exc), "error": short_error(exc)}
    try:
        stats["quality"] = bench.validate_output(task, output)
    except quality.ValidationError as exc:
        return {"status": "failed", "error": f"saída recusada: {exc}"}
    if task.op == "analyze":
        stats["out_bytes"] = 0
    return {"status": "ok", **stats}


def run_matrix(bench: ArenaBenchmark, variants: List[Variant], log_dir: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    tasks = bench.build_tasks()
    toolchains = {key: toolchain_label(key) for key in {v.toolchain for v in variants}}
    rows: List[Dict[str, Any]] = []
    measured_variants: List[Dict[str, Any]] = []

    for v in variants:
        ident = impl_id(v, toolchains[v.toolchain])
        binary = v.server[-1]
        if not os.path.exists(os.path.join(REPO_ROOT, binary)):
            print(f"\n[!] {ident}: {binary} não encontrado, variante pulada (compile-a antes)")
            continue
        port = free_port()
        print(f"\n=== {ident} (porta {port}) ===")
        engine = Engine(ident, "", f"http://127.0.0.1:{port}/run")
        bench.clients[ident] = HttpClient(engine.url)
        log_path = os.path.join(log_dir, ident.replace(":", "_") + ".log")
        try:
            with Server(v.server, port, log_path):
                for task_id, task in enumerate(tasks, start=1):
                    vtask = dataclasses.replace(task, impl=v.impl) if v.impl and not task.impl else task
                    with open(vtask.input_file, "rb") as f:
                        body = f.read()
                    print(f"  [{task_id:02d}/{len(tasks):02d}] {task.name:35s} ... ", end="", flush=True)
                    res = measure_task(bench, engine, vtask, body)
                    width, height = bench.task_dims(task)
                    mp = width * height / 1e6
                    if res["status"] == "ok":
                        median = res["codec_ms"]["median"]
                        res["throughput_mp_s"] = mp / (median / 1000.0) if median > 0 else None
                        print(f"{format_stats(res['codec_ms'])} ms")
                    else:
                        print(f"{res['status'].upper()}: {res['error'][:120]}")
                    rows.append({
                        "task_id": task_id,
                        "task": task.name,
                        "op": task.op,
                        "format": task.fmt,
                        "mode": task.mode,
                        "image": os.path.basename(task.input_file),
                        "mp": mp,
                        "impl_id": ident,
                        "language": v.language,
                        "tier": v.tier,
                        "toolchain": toolchains[v.toolchain],
                        "lib": v.lib,
                        **res,
                    })
        except RuntimeError as exc:
            print(f"[!] {ident}: {exc}")
            rows.extend({
                "task_id": i, "task": t.name, "op": t.op, "format": t.fmt, "mode": t.mode,
                "image": os.path.basename(t.input_file), "impl_id": ident, "language": v.language,
                "tier": v.tier, "toolchain": toolchains[v.toolchain], "lib": v.lib,
                "status": "failed", "error": f"servidor indisponível: {exc}",
            } for i, t in enumerate(tasks, start=1))
        finally:
            bench.clients.pop(ident).close()
        measured_variants.append({
            "impl_id": ident, "language": v.language, "tier": v.tier, "toolchain": toolchains[v.toolchain],
            "lib": v.lib, "server": " ".join(v.server[-1:]), "impl": v.impl,
        })
    return rows, measured_variants


def main() -> int:
    parser = argparse.ArgumentParser(description="Bateria multi-implementação da Arena (fonte do dashboard)")
    parser.add_argument("--only", default="", help="Prefixos linguagem[:tier[:lib]] separados por vírgula (ex.: go,rust:hybrid)")
    parser.add_argument("--corpus-dir", default="./harness/fixtures/corpus", help="Diretório do corpus de imagens PAM")
    parser.add_argument("--iterations", type=int, default=MIN_ITERATIONS, help=f"Iterações medidas por tarefa (mínimo {MIN_ITERATIONS})")
    parser.add_argument("--warmup", type=int, default=2, help="Iterações de warmup descartadas")
    parser.add_argument("--output", default="./results/benchmark_matrix.json", help="Arquivo JSON de saída")
    parser.add_argument("--arena-toml", default=ARENA_TOML, help="arena.toml com a tabela [params]")
    parser.add_argument("--tmp-dir", default=None, help="Diretório dos arquivos temporários")
    parser.add_argument("--allow-failures", action="store_true", help="Terminar com código 0 mesmo com falhas")
    args = parser.parse_args()
    if args.iterations < MIN_ITERATIONS:
        parser.error(f"--iterations deve ser >= {MIN_ITERATIONS}")

    prefixes = [p.strip() for p in args.only.split(",") if p.strip()]
    variants = [v for v in VARIANTS if not prefixes or any(f"{v.language}:{v.tier}:{v.lib}".startswith(p) for p in prefixes)]

    arena = load_arena_toml(args.arena_toml)
    try:
        bench = ArenaBenchmark(
            mode="http", corpus_dir=args.corpus_dir, iterations=args.iterations, warmup=args.warmup,
            params=arena["params"], validate=True, equal_quality=False,
            tmp_dir=args.tmp_dir or default_tmp_dir(arena),
        )
    except quality.ReferenceUnavailable as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    bench.engines = []
    bench.clients = {}

    with tempfile.TemporaryDirectory(prefix="arena_matrix_logs_") as log_dir:
        rows, measured = run_matrix(bench, variants, log_dir)

    doc = {
        "metadata": {
            "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "http",
            "primary_metric": "codec_ms",
            "iterations": args.iterations,
            "warmup": args.warmup,
            "environment": environment(),
            "variants": measured,
        },
        "results": rows,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("ok", "unsupported", "failed")}
    print(f"\n[✓] {len(measured)} variantes, {len(rows)} medições -> {args.output}")
    print(f"    ok={counts['ok']} unsupported={counts['unsupported']} failed={counts['failed']}")
    failed = [r for r in rows if r["status"] == "failed"]
    for r in failed:
        print(f"    FALHA [{r['impl_id']}] {r['task']}: {r['error'][:160]}")
    if failed and not args.allow_failures:
        print(f"\nTerminando com código 1: {len(failed)} falha(s). Use --allow-failures para ignorar.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
