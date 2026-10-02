"""
arena_quality.py - Validação e qualidade das saídas do benchmark.

Decodifica as saídas dos dois engines com um decoder de REFERÊNCIA independente (Pillow, que embute
libjpeg, libwebp, libavif/dav1d e, com o plugin pillow-jxl-plugin, libjxl) e mede o PSNR contra a
imagem original. Os engines sob teste são Go e Rust puros; o harness é só ferramenta de medição e
pode usar bibliotecas nativas.

Dependências: `pip install -r harness/requirements.txt`.
"""

import io
from dataclasses import dataclass
from typing import Callable, Dict, Optional

try:  # Pillow é opcional na importação; require_reference() falha com mensagem clara.
    from PIL import Image, ImageChops, ImageStat

    try:
        import pillow_jxl  # noqa: F401  registra o decoder de JPEG XL
    except ImportError:
        pillow_jxl = None
    PILLOW_ERROR: Optional[str] = None
except ImportError as exc:  # pragma: no cover - depende do ambiente
    Image = ImageChops = ImageStat = None  # type: ignore[assignment]
    pillow_jxl = None
    PILLOW_ERROR = str(exc)

# Nome do formato em Pillow para cada formato da arena.
PILLOW_FORMAT = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP", "avif": "AVIF", "jxl": "JXL"}

# PSNR RGB mínimo em q=75, effort=4 por classe de imagem. Os piores valores medidos no corpus são
# ~38 dB (photo) e ~29 dB (demais) nos dois engines; os pisos são os mesmos dos testes de codec
# (go/internal/codec/quality_test.go, rust/tests/quality.rs).
MIN_PSNR_BY_CLASS = {"photo": 35.0, "screenshot": 27.0, "illustration": 27.0, "alpha": 27.0}
DEFAULT_MIN_PSNR = 27.0
# Decodificar o mesmo arquivo em dois decoders diferentes só deve diferir por arredondamento.
MIN_DECODE_PSNR = 40.0


class ReferenceUnavailable(RuntimeError):
    """Pillow (ou um de seus plugins) não está instalado."""


class ValidationError(RuntimeError):
    """A saída de um engine não é a que a operação deveria produzir."""


def require_reference(*formats: str) -> None:
    """Garante que o decoder de referência existe para os formatos pedidos."""
    if Image is None:
        raise ReferenceUnavailable(
            f"Pillow não está instalado ({PILLOW_ERROR}); rode `pip install -r harness/requirements.txt` "
            "ou use --no-validate."
        )
    for fmt in formats:
        name = PILLOW_FORMAT.get(fmt)
        if name is None:
            raise ReferenceUnavailable(f"formato desconhecido: {fmt}")
        if name == "JXL" and pillow_jxl is None:
            raise ReferenceUnavailable("pillow-jxl-plugin não está instalado (decoder de JPEG XL)")
        if name not in Image.registered_extensions().values():
            raise ReferenceUnavailable(f"esta build do Pillow não decodifica {name}")


# --------------------------------------------------------------------------------------
# PAM
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pam:
    width: int
    height: int
    depth: int
    pixels: bytes


def parse_pam_header(data: bytes) -> "tuple[int, int, int, int]":
    """Devolve (largura, altura, depth, deslocamento do raster) de um PAM P7; erro se inválido."""
    end = data.find(b"ENDHDR\n")
    if end < 0 or not data.startswith(b"P7\n"):
        raise ValueError("cabeçalho PAM inválido (P7/ENDHDR ausente)")
    fields: Dict[str, int] = {}
    for line in data[:end].decode("ascii", errors="replace").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("WIDTH", "HEIGHT", "DEPTH"):
            fields[parts[0]] = int(parts[1])
    missing = {"WIDTH", "HEIGHT", "DEPTH"} - set(fields)
    if missing:
        raise ValueError(f"cabeçalho PAM sem {', '.join(sorted(missing))}")
    if fields["WIDTH"] <= 0 or fields["HEIGHT"] <= 0 or fields["DEPTH"] not in (3, 4):
        raise ValueError(f"cabeçalho PAM fora do suportado: {fields}")
    return fields["WIDTH"], fields["HEIGHT"], fields["DEPTH"], end + len(b"ENDHDR\n")


def parse_pam(data: bytes) -> Pam:
    width, height, depth, offset = parse_pam_header(data)
    expected = width * height * depth
    pixels = data[offset : offset + expected]
    if len(pixels) != expected:
        raise ValueError(f"raster PAM truncado: {len(pixels)} de {expected} bytes")
    return Pam(width, height, depth, pixels)


def pam_to_image(pam: Pam) -> "Image.Image":
    return Image.frombytes("RGBA" if pam.depth == 4 else "RGB", (pam.width, pam.height), pam.pixels)


# --------------------------------------------------------------------------------------
# Decodificação de referência e métricas
# --------------------------------------------------------------------------------------


def reference_decode(fmt: str, data: bytes) -> "Image.Image":
    """Decodifica com a biblioteca de referência e devolve uma imagem RGB ou RGBA de 8 bits."""
    require_reference(fmt)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ValidationError(f"o decoder de referência rejeitou a saída {fmt}: {exc}") from exc
    if img.format != PILLOW_FORMAT[fmt]:
        raise ValidationError(f"a saída é {img.format}, esperado {PILLOW_FORMAT[fmt]}")
    has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
    return img.convert("RGBA" if has_alpha else "RGB")


def rgb_psnr(want: "Image.Image", got: "Image.Image") -> float:
    """PSNR RGB em dB sobre os pixels totalmente opacos de `want` (o encoder é livre para mudar a
    cor sob a transparência). Imagens idênticas dão +inf. É a mesma métrica dos testes de codec."""
    if want.size != got.size:
        raise ValidationError(f"dimensões diferentes: {got.size} contra {want.size}")
    diff = ImageChops.difference(want.convert("RGB"), got.convert("RGB"))
    mask = None
    if want.mode == "RGBA":
        mask = want.getchannel("A").point(lambda v: 255 if v == 255 else 0)
    stat = ImageStat.Stat(diff, mask)
    count = stat.count[0] * 3
    sse = sum(stat.sum2)
    if count == 0 or sse == 0:
        return float("inf")
    import math

    return 10.0 * math.log10(255.0 * 255.0 / (sse / count))


def exact_match(want: "Image.Image", got: "Image.Image") -> bool:
    """Igualdade de RGB e alpha; a ausência de alpha vale 255."""
    if want.size != got.size:
        return False
    # alpha_only=False: em RGBA o getbbox() padrão olha só o canal alpha e diria "idêntico" para
    # qualquer par de imagens com o mesmo alpha.
    return ImageChops.difference(want.convert("RGBA"), got.convert("RGBA")).getbbox(alpha_only=False) is None


def image_class(path: str) -> str:
    """photo, screenshot, illustration ou alpha a partir do nome do arquivo do corpus."""
    import os

    return os.path.splitext(os.path.basename(path))[0]


def min_psnr_for(path: str) -> float:
    return MIN_PSNR_BY_CLASS.get(image_class(path), DEFAULT_MIN_PSNR)


# --------------------------------------------------------------------------------------
# Busca do q equivalente
# --------------------------------------------------------------------------------------


def find_matching_q(psnr_at: Callable[[int], float], target: float, lo: int = 1, hi: int = 100) -> int:
    """Menor q em [lo, hi] cujo PSNR alcança `target`, supondo PSNR crescente em q (busca binária).

    Se nem `hi` alcança o alvo, devolve `hi`. O PSNR de cada q é calculado uma única vez."""
    cache: Dict[int, float] = {}

    def at(q: int) -> float:
        if q not in cache:
            cache[q] = psnr_at(q)
        return cache[q]

    if at(hi) < target:
        return hi
    while lo < hi:
        mid = (lo + hi) // 2
        if at(mid) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo
