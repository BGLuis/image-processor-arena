"""
arena_pam.py - Parser e serializer Netpbm PAM (P7) para a Arena de Imagens.

Suporta:
- Tuplas RGB (depth 3) e RGB_ALPHA (depth 4) com MAXVAL 255.
- Validação estrita de limites: largura, altura, tupltype, maxval e ARENA_MAX_PIXELS.
- Verificação do limite de pixels ANTES de alocar buffers de imagem.
"""

import os
from dataclasses import dataclass
from typing import Optional

ENV_MAX_PIXELS = "ARENA_MAX_PIXELS"
DEFAULT_MAX_PIXELS = 40_000_000


class PamError(ValueError):
    """Erro de parsing ou validação de formato PAM."""
    pass


@dataclass
class PamImage:
    width: int
    height: int
    depth: int
    tupltype: str
    data: bytes
    maxval: int = 255

    @property
    def pixels(self) -> int:
        return self.width * self.height


def get_max_pixels() -> int:
    raw = os.environ.get(ENV_MAX_PIXELS)
    if not raw:
        return DEFAULT_MAX_PIXELS
    try:
        val = int(raw)
        if val <= 0:
            return DEFAULT_MAX_PIXELS
        return val
    except ValueError:
        return DEFAULT_MAX_PIXELS


def parse_pam(data: bytes, max_pixels: Optional[int] = None) -> PamImage:
    """
    Decodifica bytes no formato PAM P7 Netpbm.
    Valida limites antes de alocar dados do raster.
    """
    if not data:
        raise PamError("Empty PAM data")

    if max_pixels is None:
        max_pixels = get_max_pixels()

    # Localiza o marcador ENDHDR
    endhdr_idx = data.find(b"\nENDHDR\n")
    if endhdr_idx != -1:
        data_start = endhdr_idx + len(b"\nENDHDR\n")
    else:
        endhdr_idx = data.find(b"\nENDHDR\r\n")
        if endhdr_idx != -1:
            data_start = endhdr_idx + len(b"\nENDHDR\r\n")
        else:
            endhdr_idx = data.find(b"ENDHDR\n")
            if endhdr_idx != -1:
                data_start = endhdr_idx + len(b"ENDHDR\n")
            else:
                endhdr_idx = data.find(b"ENDHDR\r\n")
                if endhdr_idx != -1:
                    data_start = endhdr_idx + len(b"ENDHDR\r\n")
                else:
                    raise PamError("Invalid PAM header: ENDHDR marker not found")

    header_bytes = data[:endhdr_idx]
    try:
        header_text = header_bytes.decode("ascii")
    except UnicodeDecodeError as e:
        raise PamError(f"Invalid PAM header (non-ASCII characters): {e}")

    lines = header_text.splitlines()
    if not lines or lines[0].strip() != "P7":
        raise PamError("Invalid PAM header: missing P7 magic number")

    width: Optional[int] = None
    height: Optional[int] = None
    depth: Optional[int] = None
    maxval: Optional[int] = None
    tupltype: Optional[str] = None

    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        key = parts[0].upper()
        val = parts[1].strip() if len(parts) > 1 else ""

        if key == "WIDTH":
            try:
                width = int(val)
            except ValueError:
                raise PamError(f"Invalid PAM WIDTH: {val}")
        elif key == "HEIGHT":
            try:
                height = int(val)
            except ValueError:
                raise PamError(f"Invalid PAM HEIGHT: {val}")
        elif key == "DEPTH":
            try:
                depth = int(val)
            except ValueError:
                raise PamError(f"Invalid PAM DEPTH: {val}")
        elif key == "MAXVAL":
            try:
                maxval = int(val)
            except ValueError:
                raise PamError(f"Invalid PAM MAXVAL: {val}")
        elif key == "TUPLTYPE":
            tupltype = val

    if width is None or height is None:
        raise PamError("PAM header missing WIDTH or HEIGHT")
    if width <= 0 or height <= 0:
        raise PamError(f"Invalid PAM dimensions: {width}x{height}")

    # Validação estrita de limites antes de qualquer processamento de raster
    total_pixels = width * height
    if total_pixels > max_pixels:
        raise PamError(
            f"Image dimensions {width}x{height} ({total_pixels} pixels) exceed limit of {max_pixels} pixels"
        )

    if depth is None or depth not in (3, 4):
        raise PamError(f"Unsupported PAM DEPTH: {depth} (only 3 and 4 are supported)")
    if maxval is None or maxval != 255:
        raise PamError(f"Unsupported PAM MAXVAL: {maxval} (only 255 is supported)")

    expected_tupl = "RGB" if depth == 3 else "RGB_ALPHA"
    if tupltype is None or tupltype == "":
        tupltype = expected_tupl
    elif tupltype != expected_tupl:
        raise PamError(f"Mismatched TUPLTYPE {tupltype} for depth {depth} (expected {expected_tupl})")

    expected_len = total_pixels * depth
    raster = data[data_start:]
    if len(raster) < expected_len:
        raise PamError(f"Truncated pixel data: got {len(raster)} bytes, expected {expected_len}")

    return PamImage(
        width=width,
        height=height,
        depth=depth,
        tupltype=tupltype,
        data=raster[:expected_len],
        maxval=maxval,
    )


def encode_pam(img: PamImage) -> bytes:
    """Serializa uma PamImage no formato Netpbm PAM P7."""
    header = (
        f"P7\n"
        f"WIDTH {img.width}\n"
        f"HEIGHT {img.height}\n"
        f"DEPTH {img.depth}\n"
        f"MAXVAL {img.maxval}\n"
        f"TUPLTYPE {img.tupltype}\n"
        f"ENDHDR\n"
    ).encode("ascii")
    return header + bytes(img.data)
