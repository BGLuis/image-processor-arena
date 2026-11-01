"""
arena_codecs.py - Codecs de imagem e validação de parâmetros da Arena.

Cumpre o contrato exato de parâmetros da Arena ([params] em arena.toml):
- Formatos suportados: png, jpeg, webp, avif, jxl
- q: inteiro em 1..100 (default 75), fora da faixa rejeita
- effort: inteiro em 1..10 (default 4), fora da faixa rejeita
- mode: 'lossy' ou 'lossless' (default 'lossy'), fora disso rejeita
- avif com mode=lossless é sempre recusado
- Limites de dimensões: jpeg > 65535 px e webp > 16383 px por lado são recusados
- WebP animado no decode é sempre recusado

Variantes por Categoria (--impl / ?impl=):
- Tier 1 (portable): impl='pure' (100% Python puro para PNG, rejeita outros formatos com 400)
- Tier 2 (accelerated): impl='numpy' (PNG vetorizado com NumPy + zlib)
- Tier 3 (hybrid): impl='pillow' (Pillow + pillow_jxl cobrindo todos os 5 formatos)
- Tier 3 (hybrid): impl='opencv' e impl='pyvips' (adaptadores opcionais ou erro informativo 400)
"""

import io
import struct
import zlib
from dataclasses import dataclass
from typing import Optional, Tuple

from python.arena_pam import PamImage

# Constantes do contrato
MODE_LOSSY = "lossy"
MODE_LOSSLESS = "lossless"
DEFAULT_MODE = MODE_LOSSY

DEFAULT_Q = 75
MIN_Q = 1
MAX_Q = 100

DEFAULT_EFFORT = 4
MIN_EFFORT = 1
MAX_EFFORT = 10

JPEG_MAX_SIDE = 65535
WEBP_MAX_SIDE = 16383

EFFORT_STEP = [0, 1, 1, 2, 3, 3, 4, 5, 5, 6]

SUPPORTED_FORMATS = {"png", "jpeg", "webp", "avif", "jxl"}


class CodecError(Exception):
    """Erro base para operações de codec."""
    pass


class InvalidParamsError(CodecError):
    """Parâmetros inválidos ou fora do contrato (gera HTTP 400 / batch exit 1)."""
    pass


class UnsupportedFormatError(CodecError):
    """Formato não suportado pela implementação (gera HTTP 400 / batch exit 1)."""
    pass


@dataclass
class CodecParams:
    format: str
    mode: str = DEFAULT_MODE
    q: int = DEFAULT_Q
    effort: int = DEFAULT_EFFORT
    impl: str = ""

    def validate_for_encode(self, width: int, height: int) -> None:
        if self.format == "jpeg":
            if width > JPEG_MAX_SIDE or height > JPEG_MAX_SIDE:
                raise InvalidParamsError(
                    f"jpeg supports at most {JPEG_MAX_SIDE} pixels per side, got {width}x{height}"
                )
        elif self.format == "webp":
            if width > WEBP_MAX_SIDE or height > WEBP_MAX_SIDE:
                raise InvalidParamsError(
                    f"webp supports at most {WEBP_MAX_SIDE} pixels per side, got {width}x{height}"
                )
        elif self.format == "avif":
            if self.mode == MODE_LOSSLESS:
                raise UnsupportedFormatError("avif lossless is not supported")


def normalize_format(fmt_str: str) -> str:
    s = fmt_str.strip().lower()
    if s.startswith("."):
        s = s[1:]
    if s == "jpg":
        return "jpeg"
    return s


def parse_params(
    format_str: str,
    mode_str: Optional[str] = None,
    q_str: Optional[str] = None,
    effort_str: Optional[str] = None,
    impl_str: Optional[str] = None,
) -> CodecParams:
    """Valida estritamente os parâmetros segundo o contrato arena.toml."""
    fmt = normalize_format(format_str)
    if fmt not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(f"Unsupported format: {fmt_str}")

    # Modo
    mode = (mode_str or "").strip().lower()
    if not mode:
        mode = DEFAULT_MODE
    elif mode not in (MODE_LOSSY, MODE_LOSSLESS):
        raise InvalidParamsError(f"mode must be '{MODE_LOSSY}' or '{MODE_LOSSLESS}', got '{mode_str}'")

    # Q (Qualidade)
    if q_str is not None and str(q_str).strip() != "":
        try:
            q_val = int(q_str)
        except ValueError:
            raise InvalidParamsError(f"q must be an integer in {MIN_Q}..{MAX_Q}, got '{q_str}'")
        if q_val < MIN_Q or q_val > MAX_Q:
            raise InvalidParamsError(f"q must be an integer in {MIN_Q}..{MAX_Q}, got {q_val}")
    else:
        q_val = DEFAULT_Q

    # Effort
    if effort_str is not None and str(effort_str).strip() != "":
        try:
            effort_val = int(effort_str)
        except ValueError:
            raise InvalidParamsError(f"effort must be an integer in {MIN_EFFORT}..{MAX_EFFORT}, got '{effort_str}'")
        if effort_val < MIN_EFFORT or effort_val > MAX_EFFORT:
            raise InvalidParamsError(f"effort must be an integer in {MIN_EFFORT}..{MAX_EFFORT}, got {effort_val}")
    else:
        effort_val = DEFAULT_EFFORT

    impl = (impl_str or "").strip().lower()

    return CodecParams(
        format=fmt,
        mode=mode,
        q=q_val,
        effort=effort_val,
        impl=impl,
    )


def is_animated_webp(data: bytes) -> bool:
    """Verifica se o payload WebP contém flag de animação no cabeçalho VP8X."""
    return (
        len(data) > 20
        and data[0:4] == b"RIFF"
        and data[8:12] == b"WEBP"
        and data[12:16] == b"VP8X"
        and bool(data[20] & 0x02)
    )


def get_mime_type(format_str: str) -> str:
    fmt = normalize_format(format_str)
    if fmt == "png":
        return "image/png"
    if fmt == "jpeg":
        return "image/jpeg"
    if fmt == "webp":
        return "image/webp"
    if fmt == "avif":
        return "image/avif"
    if fmt == "jxl":
        return "image/jxl"
    if fmt == "pam":
        return "image/x-netpbm-pam"
    return "application/octet-stream"


# ---------------------------------------------------------------------------
# Tier 1 (portable): Pure Python PNG Encoder / Decoder
# ---------------------------------------------------------------------------
def _paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    elif pb <= pc:
        return b
    return c


def encode_png_pure(pam: PamImage, effort: int = DEFAULT_EFFORT) -> bytes:
    width, height, depth = pam.width, pam.height, pam.depth
    color_type = 2 if depth == 3 else 6
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(
        ">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    )

    stride = width * depth
    raw = pam.data

    # Aplicação de filtros PNG
    scanlines = bytearray((stride + 1) * height)
    if effort <= 2:
        # None filter para velocidade
        for y in range(height):
            dst_off = y * (stride + 1)
            src_off = y * stride
            scanlines[dst_off] = 0
            scanlines[dst_off + 1 : dst_off + 1 + stride] = raw[src_off : src_off + stride]
    else:
        # Sub filter para melhor compressão
        for y in range(height):
            dst_off = y * (stride + 1)
            src_off = y * stride
            scanlines[dst_off] = 1  # Sub
            for x in range(stride):
                curr = raw[src_off + x]
                left = raw[src_off + x - depth] if x >= depth else 0
                scanlines[dst_off + 1 + x] = (curr - left) & 0xFF

    comp_level = 1 if effort <= 2 else (6 if effort <= 6 else 9)
    compressed = zlib.compress(bytes(scanlines), comp_level)
    idat_chunk = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(
        ">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
    )
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + ihdr_chunk + idat_chunk + iend_chunk


def decode_png_pure(data: bytes) -> PamImage:
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise InvalidParamsError("Invalid PNG signature")

    pos = 8
    width = height = depth = 0
    idat_parts = []

    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        cdata = data[pos + 8 : pos + 8 + length]
        crc = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])[0]

        computed_crc = zlib.crc32(data[pos + 4 : pos + 8 + length]) & 0xFFFFFFFF
        if computed_crc != crc:
            raise InvalidParamsError(f"PNG chunk {ctype.decode('ascii', 'ignore')} CRC error")

        pos += 12 + length

        if ctype == b"IHDR":
            width, height, bit_depth, color_type, comp_m, filt_m, interlace_m = struct.unpack(">IIBBBBB", cdata)
            if bit_depth != 8:
                raise UnsupportedFormatError(f"Unsupported PNG bit depth: {bit_depth}")
            if color_type == 2:
                depth = 3
            elif color_type == 6:
                depth = 4
            else:
                raise UnsupportedFormatError(f"Unsupported PNG color type: {color_type}")
            if interlace_m != 0:
                raise UnsupportedFormatError("Interlaced PNG not supported in pure decoder")
        elif ctype == b"IDAT":
            idat_parts.append(cdata)
        elif ctype == b"IEND":
            break

    if not idat_parts:
        raise InvalidParamsError("PNG missing IDAT chunks")

    try:
        raw = zlib.decompress(b"".join(idat_parts))
    except Exception as e:
        raise InvalidParamsError(f"PNG decompression error: {e}")

    stride = width * depth
    expected_size = (stride + 1) * height
    if len(raw) < expected_size:
        raise InvalidParamsError("PNG truncated scanlines")

    recon = bytearray(stride * height)
    for y in range(height):
        f_type = raw[y * (stride + 1)]
        src_row = raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)]
        dst_off = y * stride
        prev_off = (y - 1) * stride if y > 0 else -1

        if f_type == 0:  # None
            recon[dst_off : dst_off + stride] = src_row
        elif f_type == 1:  # Sub
            for x in range(stride):
                left = recon[dst_off + x - depth] if x >= depth else 0
                recon[dst_off + x] = (src_row[x] + left) & 0xFF
        elif f_type == 2:  # Up
            for x in range(stride):
                up = recon[prev_off + x] if prev_off >= 0 else 0
                recon[dst_off + x] = (src_row[x] + up) & 0xFF
        elif f_type == 3:  # Average
            for x in range(stride):
                left = recon[dst_off + x - depth] if x >= depth else 0
                up = recon[prev_off + x] if prev_off >= 0 else 0
                recon[dst_off + x] = (src_row[x] + ((left + up) >> 1)) & 0xFF
        elif f_type == 4:  # Paeth
            for x in range(stride):
                left = recon[dst_off + x - depth] if x >= depth else 0
                up = recon[prev_off + x] if prev_off >= 0 else 0
                up_left = recon[prev_off + x - depth] if (prev_off >= 0 and x >= depth) else 0
                recon[dst_off + x] = (src_row[x] + _paeth_predictor(left, up, up_left)) & 0xFF
        else:
            raise InvalidParamsError(f"Unknown PNG filter type: {f_type}")

    tupltype = "RGB" if depth == 3 else "RGB_ALPHA"
    return PamImage(width=width, height=height, depth=depth, tupltype=tupltype, data=bytes(recon), maxval=255)


# ---------------------------------------------------------------------------
# Tier 2 (accelerated): NumPy Vectorized PNG Encoder / Decoder
# ---------------------------------------------------------------------------
try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def encode_png_numpy(pam: PamImage, effort: int = DEFAULT_EFFORT) -> bytes:
    if not HAVE_NUMPY:
        return encode_png_pure(pam, effort)

    width, height, depth = pam.width, pam.height, pam.depth
    color_type = 2 if depth == 3 else 6
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(
        ">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    )

    stride = width * depth
    arr = np.frombuffer(pam.data, dtype=np.uint8).reshape((height, stride))

    scanlines = np.empty((height, stride + 1), dtype=np.uint8)
    if effort <= 2:
        scanlines[:, 0] = 0  # None
        scanlines[:, 1:] = arr
    else:
        # Sub filter vetorizado
        scanlines[:, 0] = 1  # Sub
        scanlines[:, 1 : 1 + depth] = arr[:, :depth]
        diff = arr[:, depth:] - arr[:, :-depth]  # uint8 overflow automático
        scanlines[:, 1 + depth :] = diff

    comp_level = 1 if effort <= 2 else (6 if effort <= 6 else 9)
    compressed = zlib.compress(scanlines.tobytes(), comp_level)
    idat_chunk = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(
        ">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF
    )
    iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + ihdr_chunk + idat_chunk + iend_chunk


def decode_png_numpy(data: bytes) -> PamImage:
    # O decoder pure é universalmente robusto e unfiltra todos os 5 stencils
    return decode_png_pure(data)


# ---------------------------------------------------------------------------
# Tier 3 (hybrid): Pillow Encoder / Decoder (Default geral da Arena)
# ---------------------------------------------------------------------------
try:
    from PIL import Image
    try:
        import pillow_jxl
        HAVE_PILLOW_JXL = True
    except ImportError:
        HAVE_PILLOW_JXL = False
    HAVE_PILLOW = True
except ImportError:
    Image = None
    HAVE_PILLOW = False
    HAVE_PILLOW_JXL = False


def encode_pillow(pam: PamImage, params: CodecParams) -> bytes:
    if not HAVE_PILLOW:
        raise InvalidParamsError("Pillow is not installed in the environment")

    params.validate_for_encode(pam.width, pam.height)
    fmt = params.format

    mode = "RGB" if pam.depth == 3 else "RGBA"
    im = Image.frombytes(mode, (pam.width, pam.height), pam.data)

    buf = io.BytesIO()

    if fmt == "png":
        comp_level = 1 if params.effort <= 2 else (6 if params.effort <= 6 else 9)
        im.save(buf, format="PNG", compress_level=comp_level)

    elif fmt == "jpeg":
        if im.mode == "RGBA":
            im = im.convert("RGB")
        im.save(buf, format="JPEG", quality=params.q, subsampling=2)

    elif fmt == "webp":
        method = EFFORT_STEP[params.effort - 1]
        if params.mode == MODE_LOSSLESS:
            im.save(buf, format="WEBP", lossless=True)
        else:
            im.save(buf, format="WEBP", lossless=False, quality=params.q, method=method)

    elif fmt == "avif":
        speed = 11 - params.effort
        im.save(buf, format="AVIF", quality=params.q, speed=speed)

    elif fmt == "jxl":
        if not HAVE_PILLOW_JXL:
            raise UnsupportedFormatError("JPEG XL support requires pillow_jxl plugin")
        jxl_eff = EFFORT_STEP[params.effort - 1] + 1
        lossless = (params.mode == MODE_LOSSLESS)
        im.save(buf, format="JXL", quality=params.q, effort=jxl_eff, lossless=lossless)

    else:
        raise UnsupportedFormatError(f"Unsupported format: {fmt}")

    return buf.getvalue()


def decode_pillow(data: bytes, format_hint: str) -> PamImage:
    if not HAVE_PILLOW:
        raise InvalidParamsError("Pillow is not installed in the environment")

    fmt = normalize_format(format_hint)

    # Detecção obrigatória de WebP animado
    if fmt == "webp" and is_animated_webp(data):
        raise InvalidParamsError("decode webp: animated WebP is not supported")

    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:
        raise InvalidParamsError(f"Decode error for {fmt}: {e}")

    if getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1:
        if fmt == "webp":
            raise InvalidParamsError("decode webp: animated WebP is not supported")

    # Mapeamento de modos de cor
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        depth = 4
        tupltype = "RGB_ALPHA"
    else:
        im = im.convert("RGB")
        depth = 3
        tupltype = "RGB"

    return PamImage(
        width=im.width,
        height=im.height,
        depth=depth,
        tupltype=tupltype,
        data=im.tobytes(),
        maxval=255,
    )


# ---------------------------------------------------------------------------
# Tier 3 (hybrid): Alternativas OpenCV e PyVips
# ---------------------------------------------------------------------------
try:
    import cv2
    HAVE_OPENCV = True
except ImportError:
    cv2 = None
    HAVE_OPENCV = False

try:
    import pyvips
    HAVE_PYVIPS = True
except ImportError:
    pyvips = None
    HAVE_PYVIPS = False


def encode_opencv(pam: PamImage, params: CodecParams) -> bytes:
    if not HAVE_OPENCV:
        raise InvalidParamsError("implementation 'opencv' requested but 'cv2' is not installed in the environment")
    # Se cv2 estiver instalado, mapear formatos suportados
    raise UnsupportedFormatError("OpenCV encoder adapter not configured")


def decode_opencv(data: bytes, format_hint: str) -> PamImage:
    if not HAVE_OPENCV:
        raise InvalidParamsError("implementation 'opencv' requested but 'cv2' is not installed in the environment")
    raise UnsupportedFormatError("OpenCV decoder adapter not configured")


def encode_pyvips(pam: PamImage, params: CodecParams) -> bytes:
    if not HAVE_PYVIPS:
        raise InvalidParamsError("implementation 'pyvips' requested but 'pyvips' is not installed in the environment")
    raise UnsupportedFormatError("pyvips encoder adapter not configured")


def decode_pyvips(data: bytes, format_hint: str) -> PamImage:
    if not HAVE_PYVIPS:
        raise InvalidParamsError("implementation 'pyvips' requested but 'pyvips' is not installed in the environment")
    raise UnsupportedFormatError("pyvips decoder adapter not configured")


# ---------------------------------------------------------------------------
# Roteadores Principais de Encode e Decode
# ---------------------------------------------------------------------------
def encode_image(pam: PamImage, params: CodecParams) -> bytes:
    """Codifica uma imagem PAM no formato e implementação desejados."""
    impl = (params.impl or "").lower().strip()

    if impl in ("pure", "portable"):
        if params.format != "png":
            raise UnsupportedFormatError(
                f"Format '{params.format}' is not supported in pure Python mode (impl='pure'). "
                f"Tier 1 Pure Python supports only PNG."
            )
        params.validate_for_encode(pam.width, pam.height)
        return encode_png_pure(pam, params.effort)

    elif impl in ("numpy", "accelerated"):
        if params.format != "png":
            raise UnsupportedFormatError(
                f"Format '{params.format}' is not supported in numpy mode (impl='numpy'). "
                f"Tier 2 accelerated supports only PNG."
            )
        params.validate_for_encode(pam.width, pam.height)
        return encode_png_numpy(pam, params.effort)

    elif impl in ("opencv",):
        return encode_opencv(pam, params)

    elif impl in ("pyvips",):
        return encode_pyvips(pam, params)

    elif impl in ("pillow", "hybrid", "default", ""):
        # Default para formatos gerais: Pillow
        return encode_pillow(pam, params)

    else:
        raise InvalidParamsError(f"Unknown codec implementation: '{impl}'")


def decode_image(data: bytes, format_str: str, impl_str: Optional[str] = None) -> PamImage:
    """Decodifica dados comprimidos em uma imagem PAM."""
    fmt = normalize_format(format_str)
    if fmt not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(f"Unsupported format: {format_str}")

    impl = (impl_str or "").lower().strip()

    if impl in ("pure", "portable"):
        if fmt != "png":
            raise UnsupportedFormatError(
                f"Format '{fmt}' is not supported in pure Python mode (impl='pure'). "
                f"Tier 1 Pure Python supports only PNG."
            )
        return decode_png_pure(data)

    elif impl in ("numpy", "accelerated"):
        if fmt != "png":
            raise UnsupportedFormatError(
                f"Format '{fmt}' is not supported in numpy mode (impl='numpy'). "
                f"Tier 2 accelerated supports only PNG."
            )
        return decode_png_numpy(data)

    elif impl in ("opencv",):
        return decode_opencv(data, fmt)

    elif impl in ("pyvips",):
        return decode_pyvips(data, fmt)

    elif impl in ("pillow", "hybrid", "default", ""):
        # Default para formatos gerais: Pillow
        return decode_pillow(data, fmt)

    else:
        raise InvalidParamsError(f"Unknown codec implementation: '{impl}'")
