#!/usr/bin/env python3
"""
benchmark_arena.py - Suite Oficial de Benchmark e Construção do Pódio (Go Puro × Rust Puro).

Executa a matriz comparativa completa da Arena de Processamento de Imagens:
- Operações: analyze, encode, decode, transcode
- Formatos: PNG, JPEG, WebP (lossy/lossless), AVIF (lossy), JPEG XL (lossy/lossless)
- Corpus: photo, screenshot, illustration, alpha (Netpbm PAM P7)
- Modos:
    --mode http: executa requisições HTTP sequenciais contra os servidores (/run); a métrica primária é
        o tempo de codec reportado pelos headers X-Arena-*-Ns, e o tempo de parede do cliente é
        reportado à parte
    --mode batch: executa os binários locais compilados (arena-batch); cronometra o processo inteiro e
        reporta o custo de startup de cada binário separadamente. Não mede velocidade de codec.
    --mode load: carga HTTP concorrente com `oha` (latência p50/p95/p99 e throughput)
Cada tempo é reportado como mediana com p25-p75 (mínimo de 5 iterações medidas).

Nenhum tempo é aceito sem antes validar a saída: cada resultado é decodificado por um decoder de
REFERÊNCIA (Pillow, ver harness/requirements.txt) e comparado ao original (lossless: igualdade exata;
lossy: PSNR mínimo). Uma tarefa que falha não some do placar: ela aparece na seção "Falhas" dos
relatórios e o script termina com código 1.

Gera o relatório do PÓDIO em console, Markdown (results/PODIUM.md) e JSON (results/benchmark_results.json);
o modo load gera results/LOAD.md e results/benchmark_load.json.
"""

import argparse
import http.client
import json
import math
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import arena_load as load
import arena_quality as quality

MIN_ITERATIONS = 5
STARTUP_PROBE_ARGS = ["--op", "analyze", "--input", "/dev/null"]
CODEC_TIME_HEADERS = {
    "analyze": ("X-Arena-Analyze-Ns",),
    "encode": ("X-Arena-Encode-Ns",),
    "decode": ("X-Arena-Decode-Ns",),
    "transcode": ("X-Arena-Decode-Ns", "X-Arena-Encode-Ns"),
}
# Tolerância do modo load: sem repetições por tarefa não há p25-p75, então duas vazões a menos de
# 5% uma da outra contam como empate.
LOAD_TIE_TOLERANCE = 0.05
EQUAL_QUALITY_FORMATS = ("avif", "jxl")

ARENA_TOML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "arena.toml")

TIE_RULE = (
    "Regra de empate (a mesma no console, no Markdown e no JSON): há empate estatístico quando os "
    "intervalos p25-p75 das duas medianas se sobrepõem; só vale como vitória uma diferença fora deles."
)
RATIO_NOTE = (
    "Razão geométrica = média geométrica de (tempo do Go ÷ tempo do Rust) sobre as tarefas; acima de 1 o "
    "Rust é mais rápido, abaixo de 1 o Go. Ela pondera a magnitude, que a contagem de vitórias ignora."
)


def load_arena_toml(path: str = ARENA_TOML) -> Dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_param_contract(path: str = ARENA_TOML) -> Dict[str, Any]:
    """Lê a tabela [params] de arena.toml: o contrato único de mode/q/effort dos dois engines."""
    return load_arena_toml(path)["params"]


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


def geometric_mean(values: List[float]) -> Optional[float]:
    positive = [v for v in values if v > 0]
    if not positive:
        return None
    return math.exp(sum(math.log(v) for v in positive) / len(positive))


def describe_ratio(ratio: Optional[float]) -> str:
    """Lê a razão Go/Rust em linguagem corrente."""
    if ratio is None:
        return "-"
    if abs(ratio - 1.0) < 0.005:
        return "equivalentes"
    return f"Rust {ratio:.2f}x mais rápido" if ratio > 1 else f"Go {1 / ratio:.2f}x mais rápido"


def go_over_rust(result: Dict[str, Any]) -> Optional[float]:
    """Tempo do Go ÷ tempo do Rust na métrica primária da tarefa."""
    go = result["go"][result["metric"]]["median"]
    rust = result["rust"][result["metric"]]["median"]
    return go / rust if go > 0 and rust > 0 else None


def standings(results: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    go_wins = sum(1 for r in results if r["winner"] == "Go")
    rust_wins = sum(1 for r in results if r["winner"] == "Rust")
    return go_wins, rust_wins, len(results) - go_wins - rust_wins


def per_operation(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Placar e razão geométrica por operação (analyze, encode, decode, transcode) e no total."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        groups.setdefault(r["op"], []).append(r)
    rows = []
    for op, rs in [*groups.items(), ("total", results)]:
        go_wins, rust_wins, ties = standings(rs)
        ratios = [x for x in (go_over_rust(r) for r in rs) if x is not None]
        rows.append(
            {
                "op": op,
                "tasks": len(rs),
                "go_wins": go_wins,
                "rust_wins": rust_wins,
                "ties": ties,
                "geomean_go_over_rust": geometric_mean(ratios),
            }
        )
    return rows


def read_pam_dims(filepath: str) -> Tuple[int, int, int]:
    """Largura, altura e depth do cabeçalho de um PAM; levanta ValueError se for inválido."""
    with open(filepath, "rb") as f:
        header = f.read(4096)
    try:
        width, height, depth, _ = quality.parse_pam_header(header)
    except ValueError as exc:
        raise ValueError(f"{filepath}: {exc}") from exc
    return width, height, depth


def cpu_model() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "desconhecido"


def environment() -> Dict[str, Any]:
    env: Dict[str, Any] = {
        "platform": platform.platform(),
        "cpu": cpu_model(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
    }
    if quality.Image is not None:
        env["reference_decoder"] = f"Pillow {quality.Image.__version__}" + (
            " + pillow-jxl-plugin" if quality.pillow_jxl else ""
        )
    return env


@dataclass(frozen=True)
class Engine:
    key: str
    bin_path: str
    url: str


@dataclass(frozen=True)
class Task:
    name: str
    op: str
    fmt: str
    mode: str
    input_file: str
    to_format: Optional[str] = None

    @property
    def target_format(self) -> str:
        return self.to_format or self.fmt

    @property
    def lossless_output(self) -> bool:
        """A saída é lossless por construção (PNG) ou porque o modo lossless foi pedido."""
        return self.target_format == "png" or (self.mode == "lossless" and self.target_format in ("webp", "jxl"))


class TaskFailure(RuntimeError):
    """Uma tarefa não pôde ser medida ou teve a saída recusada; vai para a seção Falhas."""

    def __init__(self, engine: Optional[str], message: str):
        super().__init__(message)
        self.engine = engine
        self.message = message


class HttpClient:
    """Cliente HTTP/1.1 com conexão persistente por engine: o tempo de parede deixa de incluir um
    handshake TCP por requisição."""

    def __init__(self, url: str):
        parsed = urllib.parse.urlparse(url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 80
        self.path = parsed.path or "/run"
        self.conn: Optional[http.client.HTTPConnection] = None

    def post(self, query: Dict[str, str], body: bytes) -> Tuple[float, Dict[str, str], bytes]:
        target = f"{self.path}?{urllib.parse.urlencode(query)}"
        headers = {"Content-Type": "image/x-netpbm-pam"}
        for attempt in (0, 1):
            if self.conn is None:
                self.conn = http.client.HTTPConnection(self.host, self.port, timeout=60)
            try:
                t0 = time.perf_counter_ns()
                self.conn.request("POST", target, body=body, headers=headers)
                resp = self.conn.getresponse()
                data = resp.read()
                wall_ms = (time.perf_counter_ns() - t0) / 1e6
            except (http.client.HTTPException, OSError):
                self.close()
                if attempt:
                    raise
                continue
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}: {data[:200].decode(errors='replace')}")
            return wall_ms, {k.lower(): v for k, v in resp.getheaders()}, data
        raise AssertionError("inalcançável")

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None


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
        validate: bool = True,
        equal_quality: bool = True,
        tmp_dir: Optional[str] = None,
    ):
        if iterations < MIN_ITERATIONS:
            raise ValueError(f"iterations deve ser >= {MIN_ITERATIONS} (recebido: {iterations})")
        self.params = params or load_param_contract()
        self.mode = mode
        self.engines = [Engine("go", go_bin, go_url), Engine("rust", rust_bin, rust_url)]
        self.clients = {e.key: HttpClient(e.url) for e in self.engines}
        self.corpus_dir = corpus_dir
        self.iterations = iterations
        self.warmup = warmup
        self.validate = validate
        self.equal_quality_enabled = equal_quality
        self.tmp_dir = tmp_dir
        self.results: List[Dict[str, Any]] = []
        self.equal_quality: List[Dict[str, Any]] = []
        self.failures: List[Dict[str, Any]] = []
        self.load_results: List[Dict[str, Any]] = []
        self.load_meta: Dict[str, Any] = {}
        self.startup_ms: Dict[str, Dict[str, float]] = {}
        self._reference_images: Dict[str, Any] = {}
        if validate:
            quality.require_reference("png", "jpeg", "webp", "avif", "jxl")

    # ------------------------------------------------------------------ medição

    @property
    def metric(self) -> str:
        return "codec_ms" if self.mode == "http" else "wall_ms"

    def corpus(self, name: str) -> str:
        return os.path.join(self.corpus_dir, name)

    def workdir(self) -> "tempfile.TemporaryDirectory[str]":
        return tempfile.TemporaryDirectory(prefix="arena_bench_", dir=self.tmp_dir)

    def run_cli_cmd(self, bin_path: str, cmd_args: List[str]) -> Tuple[float, bytes]:
        cmd = [bin_path] + cmd_args
        t0 = time.perf_counter_ns()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        t1 = time.perf_counter_ns()
        if res.returncode != 0:
            err = res.stderr.decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"Comando falhou ({res.returncode}): {' '.join(cmd)}\n{err}")
        return (t1 - t0) / 1e6, res.stdout

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

    def request_args(self, task: Task, q: int, effort: int) -> Tuple[List[str], Dict[str, str]]:
        batch_args = [
            "--op", task.op, "--format", task.fmt, "--mode", task.mode,
            "--q", str(q), "--effort", str(effort), "--input", task.input_file,
        ]
        query = {"op": task.op, "format": task.fmt, "mode": task.mode, "q": str(q), "effort": str(effort)}
        if task.to_format:
            batch_args.extend(["--to", task.to_format])
            query["to"] = task.to_format
        return batch_args, query

    def run_http_req(self, engine: Engine, op: str, query: Dict[str, str], body: bytes) -> Tuple[float, float, bytes]:
        wall_ms, headers, data = self.clients[engine.key].post(query, body)
        codec_ns = 0
        for header in CODEC_TIME_HEADERS[op]:
            value = headers.get(header.lower())
            if value is None:
                raise RuntimeError(f"Resposta sem o header {header} (op={op}, url={engine.url})")
            codec_ns += int(value)
        return wall_ms, codec_ns / 1e6, data

    def encode_once(self, engine: Engine, task: Task, q: int, effort: int) -> bytes:
        """Uma execução sem cronometragem, para a busca do q equivalente."""
        batch_args, query = self.request_args(task, q, effort)
        if self.mode == "http":
            with open(task.input_file, "rb") as f:
                return self.clients[engine.key].post(query, f.read())[2]
        with self.workdir() as workdir:
            out = os.path.join(workdir, f"{engine.key}.{task.target_format}")
            self.run_cli_cmd(engine.bin_path, batch_args + ["--output", out])
            with open(out, "rb") as f:
                return f.read()

    def measure_engine(
        self, engine: Engine, task: Task, q: int, effort: int, body: Optional[bytes], output_path: str
    ) -> Tuple[Dict[str, Any], bytes]:
        wall_samples: List[float] = []
        codec_samples: List[float] = []
        output = b""
        batch_args, query = self.request_args(task, q, effort)
        cli_args = list(batch_args)
        if task.op != "analyze":
            cli_args.extend(["--output", output_path])

        for i in range(self.warmup + self.iterations):
            if self.mode == "batch":
                wall_ms, stdout = self.run_cli_cmd(engine.bin_path, cli_args)
                if task.op == "analyze":
                    output = stdout
                else:
                    with open(output_path, "rb") as f:
                        output = f.read()
            else:
                assert body is not None
                wall_ms, codec_ms, output = self.run_http_req(engine, task.op, query, body)
            if i < self.warmup:
                continue
            wall_samples.append(wall_ms)
            if self.mode == "http":
                codec_samples.append(codec_ms)

        result: Dict[str, Any] = {
            "wall_ms": summarize(wall_samples),
            "codec_ms": None,
            "net_of_startup_ms": None,
            "out_bytes": len(output),
        }
        if self.mode == "http":
            result["codec_ms"] = summarize(codec_samples)
        else:
            startup_median = self.startup_ms[engine.key]["median"]
            result["net_of_startup_ms"] = summarize([max(w - startup_median, 0.0) for w in wall_samples])
        return result, output

    # ------------------------------------------------------------------ validação

    def reference_image(self, path: str) -> Any:
        """Imagem original decodificada pela referência (o PAM do corpus, ou o arquivo comprimido)."""
        if path not in self._reference_images:
            with open(path, "rb") as f:
                data = f.read()
            ext = os.path.splitext(path)[1].lstrip(".").lower()
            if ext == "pam":
                img = quality.pam_to_image(quality.parse_pam(data))
            else:
                img = quality.reference_decode({"jpg": "jpeg"}.get(ext, ext), data)
            self._reference_images[path] = img
        return self._reference_images[path]

    def judge(self, want: Any, got: Any, expect_exact: bool, min_psnr: float) -> Dict[str, Any]:
        psnr = quality.rgb_psnr(want, got)
        exact = quality.exact_match(want, got)
        if expect_exact and not exact:
            raise quality.ValidationError(f"saída lossless difere do original (PSNR {psnr:.2f} dB)")
        if not expect_exact and psnr < min_psnr:
            raise quality.ValidationError(f"PSNR {psnr:.2f} dB abaixo do mínimo de {min_psnr:.0f} dB")
        return {"validated": True, "exact": exact, "psnr_db": None if math.isinf(psnr) else round(psnr, 3)}

    def validate_output(self, task: Task, output: bytes) -> Dict[str, Any]:
        """Recusa a saída que não é o que a operação deveria produzir. Devolve as métricas de qualidade."""
        if not self.validate:
            return {"validated": False, "exact": None, "psnr_db": None}

        if task.op == "analyze":
            try:
                doc = json.loads(output)
            except ValueError as exc:
                raise quality.ValidationError(f"analyze não devolveu JSON: {exc}") from exc
            width, height, _ = read_pam_dims(task.input_file)
            if (doc.get("width"), doc.get("height")) != (width, height):
                raise quality.ValidationError(
                    f"analyze reportou {doc.get('width')}x{doc.get('height')}, esperado {width}x{height}"
                )
            return {"validated": True, "exact": None, "psnr_db": None}

        original = self.reference_image(task.input_file)
        floor = quality.min_psnr_for(task.input_file)
        if task.op == "encode":
            got = quality.reference_decode(task.fmt, output)
            return self.judge(original, got, task.lossless_output, floor)
        if task.op == "decode":
            got = quality.pam_to_image(quality.parse_pam(output))
            # PNG tem decodificação exata; nos demais, dois decoders só diferem por arredondamento.
            return self.judge(original, got, task.fmt == "png", quality.MIN_DECODE_PSNR)
        got = quality.reference_decode(task.target_format, output)
        # Um destino lossless só acrescenta o arredondamento do decoder sob teste; um lossy, a perda do encode.
        floor = quality.MIN_DECODE_PSNR if task.lossless_output else floor
        return self.judge(original, got, task.fmt == "png" and task.lossless_output, floor)

    # ------------------------------------------------------------------ tarefas

    def benchmark_task(self, task: Task, q_by_engine: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        width, height = self.task_dims(task)
        mp = (width * height) / 1e6
        effort = self.params["effort_default"]
        qs = {e.key: (q_by_engine or {}).get(e.key, self.params["q_default"]) for e in self.engines}
        for q in qs.values():
            if not self.params["q_min"] <= q <= self.params["q_max"]:
                raise ValueError(f"q={q} fora do contrato [{self.params['q_min']}, {self.params['q_max']}]")
        if not self.params["effort_min"] <= effort <= self.params["effort_max"]:
            raise ValueError(f"effort={effort} fora do contrato [{self.params['effort_min']}, {self.params['effort_max']}]")

        out_ext = {"decode": "pam", "analyze": "json"}.get(task.op, task.target_format)

        body = None
        if self.mode == "http":
            with open(task.input_file, "rb") as f:
                body = f.read()

        measured: Dict[str, Dict[str, Any]] = {}
        with self.workdir() as workdir:
            for engine in self.engines:
                output_path = os.path.join(workdir, f"{engine.key}.{out_ext}")
                try:
                    stats, output = self.measure_engine(engine, task, qs[engine.key], effort, body, output_path)
                    stats["quality"] = self.validate_output(task, output)
                except quality.ValidationError as exc:
                    raise TaskFailure(engine.key, f"saída recusada: {exc}") from exc
                except Exception as exc:
                    raise TaskFailure(engine.key, str(exc)) from exc
                measured[engine.key] = stats

        if task.op == "analyze":
            measured["go"]["out_bytes"] = measured["rust"]["out_bytes"] = 0

        go_primary = measured["go"][self.metric]
        rust_primary = measured["rust"][self.metric]
        winner, speedup = decide_winner(go_primary, rust_primary)

        for engine_result, primary in ((measured["go"], go_primary), (measured["rust"], rust_primary)):
            engine_result["throughput_mp_s"] = (
                mp / (primary["median"] / 1000.0) if self.mode == "http" and primary["median"] > 0 else None
            )

        return {
            "task": task.name,
            "op": task.op,
            "format": task.fmt,
            "mode": task.mode,
            "image": os.path.basename(task.input_file),
            "mp": mp,
            "metric": self.metric,
            "q": qs,
            "go": measured["go"],
            "rust": measured["rust"],
            "bytes_ratio": bytes_ratio(measured["go"]["out_bytes"], measured["rust"]["out_bytes"]),
            "winner": winner,
            "speedup": speedup,
        }

    def task_dims(self, task: Task) -> Tuple[int, int]:
        """Dimensões da imagem da tarefa. Entradas comprimidas (photo.png) têm o PAM de mesmo nome no
        corpus; sem ele a tarefa falha, em vez de assumir um tamanho."""
        path = task.input_file
        if not path.endswith(".pam"):
            path = os.path.splitext(path)[0] + ".pam"
        try:
            width, height, _ = read_pam_dims(path)
        except (OSError, ValueError) as exc:
            raise TaskFailure(None, f"dimensões da imagem indisponíveis: {exc}") from exc
        return width, height

    def build_tasks(self) -> List[Task]:
        names = ["photo", "screenshot", "illustration", "alpha"]
        pams = [self.corpus(f"{n}.pam") for n in names]
        base = lambda p: os.path.basename(p)  # noqa: E731
        tasks: List[Task] = []

        # 1. ANALYZE (16 métricas formais)
        for img in pams:
            tasks.append(Task(f"Analyze [{base(img)}]", "analyze", "pam", "lossless", img))
        # 2. ENCODE PNG
        for img in pams:
            tasks.append(Task(f"Encode PNG [{base(img)}]", "encode", "png", "lossless", img))
        # 3. ENCODE JPEG (exceto alpha: o JPEG não tem canal alpha)
        for img in pams[:3]:
            tasks.append(Task(f"Encode JPEG [{base(img)}]", "encode", "jpeg", "lossy", img))
        # 4. ENCODE WebP Lossy & Lossless
        for img in pams:
            tasks.append(Task(f"Encode WebP Lossy [{base(img)}]", "encode", "webp", "lossy", img))
            tasks.append(Task(f"Encode WebP Lossless [{base(img)}]", "encode", "webp", "lossless", img))
        # 5. ENCODE AVIF Lossy (lossless é recusado: nenhuma biblioteca pura o implementa)
        for img in pams[:2]:
            tasks.append(Task(f"Encode AVIF Lossy [{base(img)}]", "encode", "avif", "lossy", img))
        # 6. ENCODE JPEG XL Lossy & Lossless
        for img in pams[:2]:
            tasks.append(Task(f"Encode JXL Lossy [{base(img)}]", "encode", "jxl", "lossy", img))
            tasks.append(Task(f"Encode JXL Lossless [{base(img)}]", "encode", "jxl", "lossless", img))
        # 7. DECODE (PNG, JPEG, WebP, AVIF, JXL)
        photo = {"png": "photo.png", "jpeg": "photo.jpg", "webp": "photo.webp", "avif": "photo.avif", "jxl": "photo.jxl"}
        for fmt, filename in photo.items():
            mode = "lossless" if fmt == "png" else "lossy"
            tasks.append(Task(f"Decode {fmt.upper()} [{filename}]", "decode", fmt, mode, self.corpus(filename)))
        # 8. TRANSCODE
        tasks.append(Task("Transcode PNG -> WebP", "transcode", "png", "lossy", self.corpus("photo.png"), "webp"))
        tasks.append(Task("Transcode PNG -> AVIF", "transcode", "png", "lossy", self.corpus("photo.png"), "avif"))
        tasks.append(Task("Transcode JPEG -> WebP", "transcode", "jpeg", "lossy", self.corpus("photo.jpg"), "webp"))
        tasks.append(Task("Transcode JXL -> PNG", "transcode", "jxl", "lossless", self.corpus("photo.jxl"), "png"))
        return tasks

    def banner(self) -> None:
        print("=" * 80)
        print("          ARENA DE PROCESSAMENTO DE IMAGENS — BATERIA DE BENCHMARK")
        print(f"Modo: {self.mode.upper()} | Iterações: {self.iterations} | Warmup: {self.warmup} | "
              f"Validação das saídas: {'ligada' if self.validate else 'DESLIGADA'}")
        print("=" * 80)

    def record_failure(self, task_name: str, failure: TaskFailure) -> None:
        self.failures.append({"task": task_name, "engine": failure.engine, "error": failure.message})
        who = f"[{failure.engine}] " if failure.engine else ""
        print(f"FALHA: {who}{failure.message}")

    def run_suite(self) -> List[Dict[str, Any]]:
        tasks = self.build_tasks()
        self.banner()

        if self.mode == "batch":
            self.measure_startup()
            for engine in self.engines:
                print(f"Startup {engine.key:5s}: {format_stats(self.startup_ms[engine.key])} ms")

        results = []
        for i, task in enumerate(tasks, start=1):
            print(f"[{i:02d}/{len(tasks):02d}] Executando: {task.name:35s} ... ", end="", flush=True)
            try:
                res = self.benchmark_task(task)
            except TaskFailure as failure:
                self.record_failure(task.name, failure)
                continue
            results.append(res)
            print(f"Vencedor: {res['winner']} ({res['speedup']:.2f}x) "
                  f"[Go: {format_stats(res['go'][res['metric']])} ms | Rust: {format_stats(res['rust'][res['metric']])} ms]")
        self.results = results

        if self.equal_quality_enabled and self.validate:
            self.run_equal_quality(tasks)
        return results

    # ------------------------------------------------------------------ qualidade equivalente

    def run_equal_quality(self, tasks: List[Task]) -> None:
        """AVIF e JXL lossy não têm o mesmo q equivalente nos dois engines (o gav1d grava 4:2:0 e o ravif
        4:4:4, os mapeamentos de q são nativos). O alvo é o PSNR do Go no q padrão; o Rust busca o menor q
        que o alcança. Tamanho e tempo são então comparados a qualidade equivalente."""
        candidates = [t for t in tasks if t.op == "encode" and t.fmt in EQUAL_QUALITY_FORMATS and t.mode == "lossy"]
        print("\n" + "-" * 80)
        print("Comparação a qualidade equivalente (alvo: PSNR do Go no q padrão)")
        go, rust = self.engines
        effort = self.params["effort_default"]
        q_default = self.params["q_default"]

        for task in candidates:
            print(f"  {task.name:35s} ... ", end="", flush=True)
            try:
                original = self.reference_image(task.input_file)

                def psnr_of(engine: Engine, q: int) -> float:
                    got = quality.reference_decode(task.fmt, self.encode_once(engine, task, q, effort))
                    return quality.rgb_psnr(original, got)

                target = psnr_of(go, q_default)
                rust_q = quality.find_matching_q(
                    lambda q: psnr_of(rust, q), target, self.params["q_min"], self.params["q_max"]
                )
                res = self.benchmark_task(task, {"go": q_default, "rust": rust_q})
            except (TaskFailure, quality.ValidationError) as failure:
                message = failure.message if isinstance(failure, TaskFailure) else str(failure)
                self.failures.append({"task": f"{task.name} (qualidade equivalente)", "engine": None, "error": message})
                print(f"FALHA: {message}")
                continue

            row = {
                "task": task.name,
                "format": task.fmt,
                "image": res["image"],
                "target_psnr_db": round(target, 3),
                "go_q": q_default,
                "rust_q": rust_q,
                "go_psnr_db": res["go"]["quality"]["psnr_db"],
                "rust_psnr_db": res["rust"]["quality"]["psnr_db"],
                "go_bytes": res["go"]["out_bytes"],
                "rust_bytes": res["rust"]["out_bytes"],
                "bytes_ratio": res["bytes_ratio"],
                "metric": res["metric"],
                "go_time_ms": res["go"][res["metric"]],
                "rust_time_ms": res["rust"][res["metric"]],
                "winner": res["winner"],
                "speedup": res["speedup"],
            }
            self.equal_quality.append(row)
            print(f"Rust q={rust_q} (PSNR {row['rust_psnr_db']} dB, alvo {row['target_psnr_db']} dB) "
                  f"-> Go/Rust bytes {format_ratio(row['bytes_ratio'])}, vencedor {row['winner']} ({row['speedup']:.2f}x)")

    # ------------------------------------------------------------------ relatórios (pódio)

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
        common = [
            TIE_RULE,
            RATIO_NOTE,
            "Cada saída é decodificada por um decoder de referência (Pillow/libjxl/libavif) antes de o tempo ser "
            "aceito; lossless exige igualdade exata e lossy um PSNR mínimo por classe de imagem. "
            "PSNR RGB sobre os pixels opacos do original. O tempo só é comparável junto do tamanho e da qualidade."
            if self.validate
            else "ATENÇÃO: a validação das saídas foi desligada (--no-validate); os tempos não foram conferidos.",
        ]
        if self.mode == "http":
            return [
                "Métrica primária: tempo de codec reportado pelo servidor nos headers X-Arena-*-Ns "
                "(transcode = decode + encode; analyze = só a análise nos dois servidores). A coluna de parede "
                "do cliente inclui rede, PAM e serialização. Requisições sequenciais em conexão persistente.",
                *common,
            ]
        return [
            "Modo batch cronometra o processo inteiro, incluindo o startup do binário. "
            "Ele NÃO mede velocidade de codec; para isso use --mode http.",
            "Startup medido executando cada binário com entrada vazia/inválida (--op analyze --input /dev/null).",
            "Coluna 'líquido de startup' = tempo de parede de cada amostra menos a mediana do startup do binário; "
            "é uma aproximação, não um tempo de codec isolado.",
            *common,
        ]

    def quality_cell(self, engine_result: Dict[str, Any]) -> str:
        q = engine_result["quality"]
        if not q["validated"]:
            return "n/v"
        if q["exact"]:
            return "exato"
        return "-" if q["psnr_db"] is None else f"{q['psnr_db']:.2f} dB"

    def print_podium(self) -> None:
        if not self.results and not self.failures:
            print("Nenhum resultado para exibir.")
            return

        labels = self.metric_labels()
        go_wins, rust_wins, ties = standings(self.results)
        total = len(self.results)
        overall = per_operation(self.results)[-1] if self.results else None

        print("\n" + "=" * 140)
        print("                      PÓDIO DA ARENA: GO PURO × RUST PURO")
        print("=" * 140)
        print(f"Métrica primária: {labels['column']}")
        if overall:
            print(f"{labels['verdict']}: Go {go_wins}/{total} | Rust {rust_wins}/{total} | Empates estatísticos {ties}/{total}")
            print(f"Razão geométrica Go/Rust (tempo): {format_ratio(overall['geomean_go_over_rust'])} -> "
                  f"{describe_ratio(overall['geomean_go_over_rust'])}")

        if self.startup_ms:
            print("\nCusto de startup do binário (processo com entrada inválida, ms):")
            for engine in self.engines:
                s = self.startup_ms[engine.key]
                print(f"  {engine.key:5s} {format_stats(s)}  (min {s['min']:.2f} / max {s['max']:.2f})")

        if self.results:
            print("\nPor operação:")
            print(f"  {'Operação':10s} | {'Tarefas':7s} | {'Go':3s} | {'Rust':4s} | {'Emp.':4s} | Razão geométrica Go/Rust")
            for row in per_operation(self.results):
                print(f"  {row['op']:10s} | {row['tasks']:7d} | {row['go_wins']:3d} | {row['rust_wins']:4d} | "
                      f"{row['ties']:4d} | {format_ratio(row['geomean_go_over_rust'])} ({describe_ratio(row['geomean_go_over_rust'])})")

            print("\n" + "-" * 140)
            print(f"Tempos: mediana [p25-p75] em ms, {self.iterations} iterações medidas")
            print(f"{'Tarefa':34s} | {'Go':22s} | {'Rust':22s} | {'Go (B)':9s} | {'Rust (B)':9s} | {'Go/Rust':7s} | "
                  f"{'PSNR Go':9s} | {'PSNR Rust':9s} | {'Vencedor':8s} | {'Vantagem':8s}")
            print("-" * 140)
            for r in self.results:
                print(f"{r['task']:34s} | {format_stats(r['go'][r['metric']]):22s} | {format_stats(r['rust'][r['metric']]):22s} | "
                      f"{r['go']['out_bytes']:9d} | {r['rust']['out_bytes']:9d} | {format_ratio(r['bytes_ratio']):7s} | "
                      f"{self.quality_cell(r['go']):9s} | {self.quality_cell(r['rust']):9s} | {r['winner']:8s} | {r['speedup']:.2f}x")
            print("=" * 140)

        if self.equal_quality:
            print("\nQualidade equivalente (alvo = PSNR do Go no q padrão; Rust busca o menor q que o alcança):")
            for row in self.equal_quality:
                print(f"  {row['task']:30s} Go q={row['go_q']} / Rust q={row['rust_q']} | "
                      f"{row['go_bytes']} B vs {row['rust_bytes']} B ({format_ratio(row['bytes_ratio'])}) | "
                      f"vencedor {row['winner']} ({row['speedup']:.2f}x)")

        if self.failures:
            print("\n" + "!" * 100)
            print(f"FALHAS ({len(self.failures)}): estas tarefas NÃO entram no placar")
            for f in self.failures:
                print(f"  - {f['task']}" + (f" [{f['engine']}]" if f["engine"] else "") + f": {f['error']}")
            print("!" * 100)
        for note in self.notes():
            print(f"* {note}")

    def export_reports(self, output_dir: str = "./results") -> None:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, "benchmark_results.json")
        md_path = os.path.join(output_dir, "PODIUM.md")
        labels = self.metric_labels()
        collected_at = time.strftime("%Y-%m-%d %H:%M:%S")
        operations = per_operation(self.results) if self.results else []

        metadata = {
            "mode": self.mode,
            "primary_metric": self.metric,
            "primary_metric_description": labels["column"],
            "iterations": self.iterations,
            "warmup": self.warmup,
            "collected_at": collected_at,
            "startup_ms": self.startup_ms or None,
            "validated": self.validate,
            "tie_rule": TIE_RULE,
            "environment": environment(),
            "notes": self.notes(),
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metadata": metadata,
                    "per_operation": operations,
                    "results": self.results,
                    "equal_quality": self.equal_quality,
                    "failures": self.failures,
                },
                f,
                indent=2,
                allow_nan=False,
            )

        go_wins, rust_wins, ties = standings(self.results)
        total = len(self.results)
        overall = operations[-1] if operations else None
        env = metadata["environment"]

        md = []
        md.append("# 🏆 Pódio da Arena: Go Puro × Rust Puro\n")
        md.append(f"**Modo de Execução**: `{self.mode.upper()}`  ")
        md.append(f"**Métrica primária**: {labels['column']}  ")
        md.append(f"**Iterações por teste**: {self.iterations} medidas (+ {self.warmup} warmup); tempos como mediana [p25-p75]  ")
        md.append(f"**Máquina**: {env['cpu']} ({env['cpu_count']} CPUs lógicas), {env['platform']}  ")
        md.append(f"**Data da Coleta**: {collected_at}\n")
        md.append("## Notas de Medição\n")
        for note in self.notes():
            md.append(f"- {note}")
        md.append("")

        if self.failures:
            md.append("## ❌ Falhas (estas tarefas não entram no placar)\n")
            md.append("| Tarefa | Engine | Erro |")
            md.append("|---|---|---|")
            for f in self.failures:
                error = f["error"].replace("|", "\\|").replace("\n", " ")
                md.append(f"| {f['task']} | {f['engine'] or '-'} | {error} |")
            md.append("")

        if self.startup_ms:
            md.append("## ⏱️ Custo de Startup do Binário (não é custo de codec)\n")
            md.append("| Binário | Startup mediana [p25-p75] | Mín | Máx |")
            md.append("|---|---|---|---|")
            for engine in self.engines:
                s = self.startup_ms[engine.key]
                md.append(f"| {engine.key.capitalize()} | {format_stats(s)} ms | {s['min']:.2f} ms | {s['max']:.2f} ms |")
            md.append("")

        if overall:
            md.append("## 🥇 Classificação Geral\n")
            md.append(f"**Razão geométrica Go/Rust (tempo): {format_ratio(overall['geomean_go_over_rust'])}** "
                      f"({describe_ratio(overall['geomean_go_over_rust'])}).\n")
            md.append(f"{labels['verdict']} (empate estatístico quando os intervalos p25-p75 se sobrepõem):\n")
            md.append(f"- Go Puro: {go_wins}/{total} ({go_wins/total*100:.1f}%)")
            md.append(f"- Rust Puro: {rust_wins}/{total} ({rust_wins/total*100:.1f}%)")
            md.append(f"- Empates estatísticos: {ties}/{total} ({ties/total*100:.1f}%)\n")

            md.append("## 🧮 Por Operação\n")
            md.append("| Operação | Tarefas | Go | Rust | Empates | Razão geométrica Go/Rust | Leitura |")
            md.append("|---|---|---|---|---|---|---|")
            for row in operations:
                md.append(f"| {row['op']} | {row['tasks']} | {row['go_wins']} | {row['rust_wins']} | {row['ties']} "
                          f"| {format_ratio(row['geomean_go_over_rust'])} | {describe_ratio(row['geomean_go_over_rust'])} |")
            md.append("")

        md.append("## 📊 Tabela Completa de Resultados\n")
        md.append(f"Parâmetros (arena.toml `[params]`): q={self.params['q_default']}, effort={self.params['effort_default']}, mode padrão `{self.params['mode_default']}`. "
                  "Go/Rust acima de 1 significa saída maior no Go; o tempo só é comparável junto do tamanho e da "
                  "qualidade (PSNR RGB contra o original, decodificado pela referência; `exato` = idêntico bit a bit).\n")
        if self.mode == "http":
            md.append("| Tarefa / Operação | Go codec (ms) | Go MP/s | Rust codec (ms) | Rust MP/s | Go parede cliente (ms) | Rust parede cliente (ms) | Go (bytes) | Rust (bytes) | Go/Rust | PSNR Go | PSNR Rust | 🥇 Vencedor (codec) | Vantagem |")
            md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for r in self.results:
                md.append(
                    f"| {r['task']} | {format_stats(r['go']['codec_ms'])} | {r['go']['throughput_mp_s']:.2f} "
                    f"| {format_stats(r['rust']['codec_ms'])} | {r['rust']['throughput_mp_s']:.2f} "
                    f"| {r['go']['wall_ms']['median']:.2f} | {r['rust']['wall_ms']['median']:.2f} "
                    f"| {r['go']['out_bytes']} | {r['rust']['out_bytes']} | {format_ratio(r['bytes_ratio'])} "
                    f"| {self.quality_cell(r['go'])} | {self.quality_cell(r['rust'])} "
                    f"| {r['winner']} | **{r['speedup']:.2f}x** |"
                )
        else:
            md.append("| Tarefa / Operação | Go processo completo (ms) | Rust processo completo (ms) | Go líquido de startup (ms) | Rust líquido de startup (ms) | Go (bytes) | Rust (bytes) | Go/Rust | PSNR Go | PSNR Rust | 🥇 Vencedor (processo completo) | Vantagem |")
            md.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for r in self.results:
                md.append(
                    f"| {r['task']} | {format_stats(r['go']['wall_ms'])} | {format_stats(r['rust']['wall_ms'])} "
                    f"| {format_stats(r['go']['net_of_startup_ms'])} | {format_stats(r['rust']['net_of_startup_ms'])} "
                    f"| {r['go']['out_bytes']} | {r['rust']['out_bytes']} | {format_ratio(r['bytes_ratio'])} "
                    f"| {self.quality_cell(r['go'])} | {self.quality_cell(r['rust'])} "
                    f"| {r['winner']} | **{r['speedup']:.2f}x** |"
                )

        if self.equal_quality:
            md.append("\n## ⚖️ Comparação a Qualidade Equivalente (AVIF e JXL lossy)\n")
            md.append("O mesmo `q` não dá a mesma qualidade nos dois engines (o gav1d grava AVIF 4:2:0 e o ravif 4:4:4; "
                      "os mapeamentos de `q` são nativos de cada biblioteca). Alvo = PSNR do Go no `q` padrão; o Rust "
                      "usa o menor `q` que alcança esse PSNR. Tamanho e tempo abaixo são medidos nesses `q`.\n")
            md.append("| Tarefa | Alvo (dB) | Go q | Rust q | PSNR Go | PSNR Rust | Go (bytes) | Rust (bytes) | Go/Rust | Go tempo (ms) | Rust tempo (ms) | 🥇 Vencedor | Vantagem |")
            md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for row in self.equal_quality:
                md.append(
                    f"| {row['task']} | {row['target_psnr_db']:.2f} | {row['go_q']} | {row['rust_q']} "
                    f"| {row['go_psnr_db']} | {row['rust_psnr_db']} | {row['go_bytes']} | {row['rust_bytes']} "
                    f"| {format_ratio(row['bytes_ratio'])} | {format_stats(row['go_time_ms'])} | {format_stats(row['rust_time_ms'])} "
                    f"| {row['winner']} | **{row['speedup']:.2f}x** |"
                )

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        print(f"\n[✓] Relatórios exportados para:")
        print(f"    - JSON: {json_path}")
        print(f"    - Markdown: {md_path}")

    # ------------------------------------------------------------------ modo load

    def load_tasks(self) -> List[Task]:
        photo = self.corpus("photo.pam")
        return [
            Task("Analyze [photo.pam]", "analyze", "pam", "lossless", photo),
            Task("Encode PNG [photo.pam]", "encode", "png", "lossless", photo),
            Task("Encode JPEG [photo.pam]", "encode", "jpeg", "lossy", photo),
            Task("Encode WebP Lossy [photo.pam]", "encode", "webp", "lossy", photo),
            Task("Encode AVIF Lossy [photo.pam]", "encode", "avif", "lossy", photo),
            Task("Encode JXL Lossy [photo.pam]", "encode", "jxl", "lossy", photo),
            Task("Decode PNG [photo.png]", "decode", "png", "lossless", self.corpus("photo.png")),
            Task("Decode JPEG [photo.jpg]", "decode", "jpeg", "lossy", self.corpus("photo.jpg")),
            Task("Decode WebP [photo.webp]", "decode", "webp", "lossy", self.corpus("photo.webp")),
            Task("Decode AVIF [photo.avif]", "decode", "avif", "lossy", self.corpus("photo.avif")),
            Task("Decode JXL [photo.jxl]", "decode", "jxl", "lossy", self.corpus("photo.jxl")),
            Task("Transcode PNG -> WebP", "transcode", "png", "lossy", self.corpus("photo.png"), "webp"),
            Task("Transcode JXL -> PNG", "transcode", "jxl", "lossless", self.corpus("photo.jxl"), "png"),
        ]

    def run_load_suite(self, duration_s: float, concurrency: int, oha_bin: str) -> List[Dict[str, Any]]:
        """Carga concorrente (oha) contra os dois servidores, um de cada vez. Antes de cada carga uma
        requisição isolada é validada contra a referência: medir vazão de uma resposta errada não vale."""
        oha_path = load.require_oha(oha_bin)
        tasks = self.load_tasks()
        print("=" * 80)
        print("          ARENA DE PROCESSAMENTO DE IMAGENS — CARGA CONCORRENTE (oha)")
        print(f"Duração por engine: {duration_s:g}s | Concorrência: {concurrency} | oha: {oha_path}")
        print("=" * 80)

        effort = self.params["effort_default"]
        q = self.params["q_default"]
        results = []
        for i, task in enumerate(tasks, start=1):
            print(f"[{i:02d}/{len(tasks):02d}] {task.name:35s} ... ", end="", flush=True)
            _, query = self.request_args(task, q, effort)
            row: Dict[str, Any] = {"task": task.name, "op": task.op, "format": task.fmt}
            try:
                for engine in self.engines:
                    with open(task.input_file, "rb") as f:
                        body = f.read()
                    try:
                        output = self.clients[engine.key].post(query, body)[2]
                        self.validate_output(task, output)
                    except quality.ValidationError as exc:
                        raise TaskFailure(engine.key, f"saída recusada: {exc}") from exc
                    except Exception as exc:
                        raise TaskFailure(engine.key, str(exc)) from exc

                    url = f"{engine.url}?{urllib.parse.urlencode(query)}"
                    try:
                        stats = load.run_oha(url, task.input_file, duration_s, concurrency, oha_bin=oha_bin)
                    except load.LoadError as exc:
                        raise TaskFailure(engine.key, str(exc)) from exc
                    if stats.success_rate < 1.0:
                        raise TaskFailure(
                            engine.key,
                            f"{stats.requests - stats.ok_requests} de {stats.requests} requisições sem 2xx "
                            f"(status {stats.status_codes}, erros {stats.errors})",
                        )
                    row[engine.key] = stats.to_dict()
            except TaskFailure as failure:
                self.record_failure(task.name, failure)
                continue

            go_rps, rust_rps = row["go"]["requests_per_sec"], row["rust"]["requests_per_sec"]
            row["throughput_ratio_rust_over_go"] = rust_rps / go_rps if go_rps > 0 else None
            row["p99_ratio_go_over_rust"] = (
                row["go"]["latency_ms"]["p99"] / row["rust"]["latency_ms"]["p99"] if row["rust"]["latency_ms"]["p99"] > 0 else None
            )
            ratio = row["throughput_ratio_rust_over_go"] or 1.0
            row["winner"] = "Empate" if abs(ratio - 1.0) <= LOAD_TIE_TOLERANCE else ("Rust" if ratio > 1 else "Go")
            results.append(row)
            print(f"Go {go_rps:7.1f} req/s (p99 {row['go']['latency_ms']['p99']:.1f} ms) | "
                  f"Rust {rust_rps:7.1f} req/s (p99 {row['rust']['latency_ms']['p99']:.1f} ms) | {row['winner']}")
        self.load_results = results
        self.load_meta = {"duration_s": duration_s, "concurrency": concurrency, "oha": oha_path}
        return results

    def export_load_reports(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)
        results = self.load_results
        collected_at = time.strftime("%Y-%m-%d %H:%M:%S")
        ratios = [r["throughput_ratio_rust_over_go"] for r in results if r["throughput_ratio_rust_over_go"]]
        geo = geometric_mean(ratios)
        env = environment()

        with open(os.path.join(output_dir, "benchmark_load.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metadata": {**self.load_meta, "collected_at": collected_at, "environment": env,
                                 "tie_tolerance": LOAD_TIE_TOLERANCE, "validated": self.validate},
                    "geomean_throughput_rust_over_go": geo,
                    "results": results,
                    "failures": self.failures,
                },
                f,
                indent=2,
                allow_nan=False,
            )

        md = ["# 🔥 Carga Concorrente: Go Puro × Rust Puro\n"]
        md.append(f"**Carga**: `oha`, {self.load_meta['duration_s']:g}s por engine, concorrência {self.load_meta['concurrency']}  ")
        md.append(f"**Máquina**: {env['cpu']} ({env['cpu_count']} CPUs lógicas), {env['platform']}  ")
        md.append(f"**Data da Coleta**: {collected_at}\n")
        md.append("## Notas\n")
        md.append(f"- Os servidores rodam um de cada vez; cada tarefa só entra depois de uma requisição isolada ser validada contra o decoder de referência e de a carga terminar com 100% de respostas 2xx.")
        md.append(f"- Vencedor por vazão (req/s); empate quando as vazões diferem menos de {LOAD_TIE_TOLERANCE:.0%}. Sem repetições por tarefa não há p25-p75, então esta é a regra do modo load.")
        md.append("- Latências em ms (p50/p95/p99 por requisição, medidas pelo cliente `oha`); MP/s = megapixels da imagem de entrada por segundo de vazão.")
        if geo:
            md.append(f"- Razão geométrica de vazão Rust ÷ Go: **{geo:.2f}x**.")
        md.append("")
        if self.failures:
            md.append("## ❌ Falhas\n")
            md.append("| Tarefa | Engine | Erro |")
            md.append("|---|---|---|")
            for f in self.failures:
                error = f["error"].replace("|", "\\|").replace("\n", " ")
                md.append(f"| {f['task']} | {f['engine'] or '-'} | {error} |")
            md.append("")
        md.append("## Resultados\n")
        md.append("| Tarefa | Go req/s | Go p50 | Go p95 | Go p99 | Rust req/s | Rust p50 | Rust p95 | Rust p99 | Rust/Go vazão | 🥇 Vencedor |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in results:
            g, u = r["go"], r["rust"]
            md.append(
                f"| {r['task']} | {g['requests_per_sec']:.1f} | {g['latency_ms']['p50']:.1f} | {g['latency_ms']['p95']:.1f} | {g['latency_ms']['p99']:.1f} "
                f"| {u['requests_per_sec']:.1f} | {u['latency_ms']['p50']:.1f} | {u['latency_ms']['p95']:.1f} | {u['latency_ms']['p99']:.1f} "
                f"| {r['throughput_ratio_rust_over_go']:.2f}x | {r['winner']} |"
            )
        with open(os.path.join(output_dir, "LOAD.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        print(f"\n[✓] Relatórios de carga exportados para {output_dir} (LOAD.md, benchmark_load.json)")

    def print_failures_summary(self) -> None:
        if self.failures:
            print("\n" + "!" * 100)
            print(f"FALHAS ({len(self.failures)}):")
            for f in self.failures:
                print(f"  - {f['task']}" + (f" [{f['engine']}]" if f["engine"] else "") + f": {f['error']}")
            print("!" * 100)


def default_tmp_dir(arena: Dict[str, Any]) -> Optional[str]:
    """ARENA_TMPDIR, senão o `tmpfs_path` de arena.toml quando existir (o ramdisk do compose), senão o
    diretório temporário do sistema. Arquivos de saída em disco lento distorcem o tempo de parede do batch."""
    explicit = os.environ.get("ARENA_TMPDIR")
    if explicit:
        return explicit
    tmpfs = arena.get("benchmarks", {}).get("tmpfs_path")
    return tmpfs if tmpfs and os.path.isdir(tmpfs) and os.access(tmpfs, os.W_OK) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Arena Benchmark Runner & Podium Builder")
    parser.add_argument("--mode", choices=["batch", "http", "load"], default="batch",
                        help="batch (processo inteiro), http (tempo de codec do servidor) ou load (carga concorrente com oha)")
    parser.add_argument("--go-bin", default="./go/bin/arena-batch", help="Caminho do binário Go arena-batch")
    parser.add_argument("--rust-bin", default="./rust/target/release/arena-batch", help="Caminho do binário Rust arena-batch")
    parser.add_argument("--go-url", default="http://localhost:8080/run", help="URL do endpoint Go")
    parser.add_argument("--rust-url", default="http://localhost:8081/run", help="URL do endpoint Rust")
    parser.add_argument("--corpus-dir", default="./harness/fixtures/corpus", help="Diretório do corpus de imagens PAM")
    parser.add_argument("--iterations", type=int, default=MIN_ITERATIONS, help=f"Número de iterações medidas por teste (mínimo {MIN_ITERATIONS})")
    parser.add_argument("--warmup", type=int, default=2, help="Número de iterações de warmup descartadas")
    parser.add_argument("--output-dir", default="./results", help="Diretório para salvar os resultados")
    parser.add_argument("--arena-toml", default=ARENA_TOML, help="arena.toml com a tabela [params] (q, effort e mode padrão)")
    parser.add_argument("--no-validate", action="store_true", help="NÃO validar as saídas contra o decoder de referência (não recomendado)")
    parser.add_argument("--no-equal-quality", action="store_true", help="Pular a comparação a qualidade equivalente (AVIF e JXL lossy)")
    parser.add_argument("--allow-failures", action="store_true", help="Terminar com código 0 mesmo que alguma tarefa tenha falhado (as falhas continuam nos relatórios)")
    parser.add_argument("--tmp-dir", default=None, help="Diretório dos arquivos temporários (padrão: ARENA_TMPDIR ou o tmpfs_path de arena.toml)")
    parser.add_argument("--duration", type=float, default=10.0, help="[load] segundos de carga por engine e tarefa")
    parser.add_argument("--concurrency", type=int, default=os.cpu_count() or 4, help="[load] conexões concorrentes do oha")
    parser.add_argument("--oha-bin", default="oha", help="[load] caminho do binário oha")
    args = parser.parse_args()
    if args.iterations < MIN_ITERATIONS:
        parser.error(f"--iterations deve ser >= {MIN_ITERATIONS} para reportar mediana e dispersão")

    arena = load_arena_toml(args.arena_toml)
    try:
        bench = ArenaBenchmark(
            mode=args.mode,
            go_bin=args.go_bin,
            rust_bin=args.rust_bin,
            go_url=args.go_url,
            rust_url=args.rust_url,
            corpus_dir=args.corpus_dir,
            iterations=args.iterations,
            warmup=args.warmup,
            params=arena["params"],
            validate=not args.no_validate,
            equal_quality=not args.no_equal_quality,
            tmp_dir=args.tmp_dir or default_tmp_dir(arena),
        )
    except quality.ReferenceUnavailable as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2

    if args.mode == "load":
        try:
            bench.run_load_suite(args.duration, args.concurrency, args.oha_bin)
        except load.LoadError as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            return 2
        bench.export_load_reports(args.output_dir)
        bench.print_failures_summary()
    else:
        bench.run_suite()
        bench.print_podium()
        bench.export_reports(args.output_dir)

    if bench.failures and not args.allow_failures:
        print(f"\nTerminando com código 1: {len(bench.failures)} falha(s). Use --allow-failures para ignorar.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
