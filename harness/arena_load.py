"""
arena_load.py - Carga HTTP concorrente com `oha` (latência p50/p95/p99 e throughput).

O modo --mode http do benchmark é sequencial e mede o tempo de codec que o servidor reporta. Este
módulo mede o outro lado: o servidor sob requisições concorrentes, o que importa para a promessa de
"alta carga" do projeto. O `oha` é instalado em docker/harness.Dockerfile.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional


DEADLINE_ABORT = "aborted due to deadline"


class LoadError(RuntimeError):
    """O oha não rodou, ou a carga terminou com respostas que não são 2xx."""


@dataclass(frozen=True)
class LoadStats:
    requests: int
    ok_requests: int
    requests_per_sec: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    status_codes: Dict[str, int] = field(default_factory=dict)
    errors: Dict[str, int] = field(default_factory=dict)
    # Requisições em voo quando o tempo da carga acabou: o oha as cancela e as conta como erro, mas
    # são um efeito da medição (no máximo uma por conexão), não uma falha do servidor.
    aborted_at_deadline: int = 0

    @property
    def success_rate(self) -> float:
        return self.ok_requests / self.requests if self.requests else 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "requests": self.requests,
            "ok_requests": self.ok_requests,
            "success_rate": self.success_rate,
            "requests_per_sec": self.requests_per_sec,
            "latency_ms": {
                "mean": self.mean_ms,
                "p50": self.p50_ms,
                "p95": self.p95_ms,
                "p99": self.p99_ms,
                "max": self.max_ms,
            },
            "status_codes": self.status_codes,
            "errors": self.errors,
            "aborted_at_deadline": self.aborted_at_deadline,
        }


def parse_oha_json(text: str) -> LoadStats:
    """Lê a saída de `oha --output-format json` (tempos em segundos no JSON, em ms aqui)."""
    try:
        doc = json.loads(text)
        summary = doc["summary"]
        percentiles = doc["latencyPercentiles"]
        status_codes = {str(k): int(v) for k, v in (doc.get("statusCodeDistribution") or {}).items()}
        errors = {str(k): int(v) for k, v in (doc.get("errorDistribution") or {}).items()}
        aborted = errors.pop(DEADLINE_ABORT, 0)
        return LoadStats(
            requests=sum(status_codes.values()) + sum(errors.values()),
            ok_requests=sum(n for code, n in status_codes.items() if code.startswith("2")),
            requests_per_sec=float(summary["requestsPerSec"]),
            mean_ms=float(summary["average"]) * 1000.0,
            p50_ms=float(percentiles["p50"]) * 1000.0,
            p95_ms=float(percentiles["p95"]) * 1000.0,
            p99_ms=float(percentiles["p99"]) * 1000.0,
            max_ms=float(summary["slowest"]) * 1000.0,
            status_codes=status_codes,
            errors=errors,
            aborted_at_deadline=aborted,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LoadError(f"saída do oha em formato inesperado ({exc!r})") from exc


def oha_command(
    url: str,
    body_path: str,
    duration_s: float,
    concurrency: int,
    content_type: str = "application/octet-stream",
    oha_bin: str = "oha",
) -> List[str]:
    return [
        oha_bin,
        "--no-tui",
        "--output-format",
        "json",
        "-z",
        f"{duration_s:g}s",
        "-c",
        str(concurrency),
        "-m",
        "POST",
        "-T",
        content_type,
        "-D",
        body_path,
        url,
    ]


def require_oha(oha_bin: str = "oha") -> str:
    path = shutil.which(oha_bin)
    if path is None:
        raise LoadError(
            f"'{oha_bin}' não está no PATH; ele vem na imagem docker/harness.Dockerfile "
            "(https://github.com/hatoo/oha)."
        )
    return path


def run_oha(
    url: str,
    body_path: str,
    duration_s: float,
    concurrency: int,
    content_type: str = "application/octet-stream",
    oha_bin: str = "oha",
    timeout: Optional[float] = None,
) -> LoadStats:
    cmd = oha_command(url, body_path, duration_s, concurrency, content_type, oha_bin)
    res = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout or duration_s + 60
    )
    if res.returncode != 0:
        raise LoadError(f"oha falhou ({res.returncode}): {res.stderr.decode(errors='replace').strip()}")
    stats = parse_oha_json(res.stdout.decode())
    if stats.requests == 0:
        raise LoadError(f"o oha não completou nenhuma requisição em {url}")
    return stats
