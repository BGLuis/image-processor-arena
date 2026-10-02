#!/usr/bin/env python3
"""Small decoder fixtures for layouts that the arena's own encoders never produce.

The corpus only ever contains files written by the arena encoders (8-bit RGB / RGBA), so the
decoders were never exercised on indexed or sub-8-bit PNG, 16-bit PNG, grayscale JPEG XL or
animated WebP. This script writes the fixtures and `expected.json`, the single source of truth
that both engines are compared against (rust/tests/decoders.rs and
go/internal/codec/decoders_test.go).

The PNG fixtures need only the standard library. The JPEG XL and WebP fixtures are written with
Pillow and its libjxl plugin, an independent reference encoder (the arena's own jxl-encoder 0.3.1
writes a gray+alpha stream that neither jxl-oxide nor gen2brain/jxl can read, so it cannot be
used here):

    pip install pillow pillow-jxl-plugin
    python3 harness/generators/make_decoder_fixtures.py

Without Pillow the script still writes the PNG fixtures and `expected.json`, and keeps the
committed JPEG XL and WebP files untouched.

Every entry of `expected.json` is the PAM an engine must return after decoding the file:
`depth` 3 is RGB, `depth` 4 is RGBA, `pixels` is the raster in hex. An entry with an `error`
key must make the decode fail instead.
"""

import json
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "fixtures" / "decoders"

PALETTE = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]


def chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def png(width, height, bit_depth, color_type, rows, plte=None, trns=None) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(row) for row in rows)  # filter type 0 on every row
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    if plte:
        out += chunk(b"PLTE", bytes(c for rgb in plte for c in rgb))
    if trns:
        out += chunk(b"tRNS", bytes(trns))
    return out + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def pack_bits(values, bits):
    """Pack samples MSB-first into bytes, as PNG does for bit depths below 8."""
    per_byte = 8 // bits
    padded = list(values) + [0] * (-len(values) % per_byte)
    out = []
    for i in range(0, len(padded), per_byte):
        byte = 0
        for v in padded[i : i + per_byte]:
            byte = (byte << bits) | v
        out.append(byte)
    return out


def raster(pixels) -> str:
    return bytes(c for px in pixels for c in px).hex()


def entry(fmt, width, height, depth, pixels):
    return {"format": fmt, "width": width, "height": height, "depth": depth, "pixels": raster(pixels)}


def build():
    files, expected = {}, {}

    # Palette PNG, 8 bits per index.
    idx = [[(x + y) % 4 for x in range(4)] for y in range(4)]
    files["indexed_4x4.png"] = png(4, 4, 8, 3, idx, plte=PALETTE)
    expected["indexed_4x4.png"] = entry(
        "png", 4, 4, 3, [PALETTE[i] for row in idx for i in row]
    )

    # Palette PNG, 2 bits per index: one byte per 4-pixel row.
    files["indexed_2bit_4x4.png"] = png(
        4, 4, 2, 3, [pack_bits(row, 2) for row in idx], plte=PALETTE
    )
    expected["indexed_2bit_4x4.png"] = expected["indexed_4x4.png"]

    # Palette PNG with a tRNS chunk: the decoded image carries a straight alpha channel.
    alphas = [255, 128, 0, 255]
    files["indexed_alpha_4x4.png"] = png(4, 4, 8, 3, idx, plte=PALETTE, trns=alphas)
    expected["indexed_alpha_4x4.png"] = entry(
        "png", 4, 4, 4, [PALETTE[i] + (alphas[i],) for row in idx for i in row]
    )

    # 1-bit grayscale: 1 is white, 0 is black.
    rows = [[1, 0, 1, 0, 1, 0, 1, 0], [1, 1, 1, 1, 0, 0, 0, 0]]
    files["gray1_8x2.png"] = png(8, 2, 1, 0, [pack_bits(r, 1) for r in rows])
    expected["gray1_8x2.png"] = entry(
        "png", 8, 2, 3, [(v * 255,) * 3 for r in rows for v in r]
    )

    # 2-bit grayscale expands to 0, 85, 170, 255.
    rows = [[0, 1, 2, 3], [3, 2, 1, 0]]
    files["gray2_4x2.png"] = png(4, 2, 2, 0, [pack_bits(r, 2) for r in rows])
    expected["gray2_4x2.png"] = entry(
        "png", 4, 2, 3, [(v * 85,) * 3 for r in rows for v in r]
    )

    # 16-bit RGB. The sample values separate truncation (v >> 8) from rounding (v / 257):
    # 0x00FF -> 0 vs 1, 0x01FF -> 1 vs 2, 0x7FFF -> 127 both, 0xFFFF -> 255 both.
    samples16 = [
        (0x0000, 0x00FF, 0x01FF),
        (0x7FFF, 0x8000, 0xFFFF),
        (0x1234, 0xABCD, 0x00FE),
        (0xFE01, 0xFF00, 0x0080),
    ]
    rows16 = [
        [b for px in samples16[:2] for v in px for b in struct.pack(">H", v)],
        [b for px in samples16[2:] for v in px for b in struct.pack(">H", v)],
    ]
    files["rgb16_2x2.png"] = png(2, 2, 16, 2, rows16)
    expected["rgb16_2x2.png"] = entry(
        "png", 2, 2, 3, [tuple((v + 128) // 257 for v in px) for px in samples16]
    )

    # Grayscale JPEG XL, produced by the Rust regeneration test.
    gray = [(x * 60 + y * 15 + 10) & 0xFF for y in range(4) for x in range(4)]
    expected["gray_4x4.jxl"] = entry("jxl", 4, 4, 3, [(v,) * 3 for v in gray])

    # Grayscale + alpha JPEG XL.
    alpha = [255 - 64 * (x % 2) - 32 * (y % 2) for y in range(4) for x in range(4)]
    expected["gray_alpha_4x4.jxl"] = entry(
        "jxl", 4, 4, 4, [(v, v, v, a) for v, a in zip(gray, alpha)]
    )

    # Two-frame animated WebP. The Rust decoder composites frames with an approximate blend that
    # drifts by one level from the Go decoders, so there is no portable "first frame": both
    # engines refuse animated WebP with an error instead.
    expected["animated_2f.webp"] = {"format": "webp", "error": "animated"}

    return files, expected


def write_pillow_fixtures(expected):
    """JPEG XL (gray, gray+alpha) and animated WebP through Pillow; False if Pillow is missing."""
    try:
        from PIL import Image
        import pillow_jxl  # noqa: F401  registers the JPEG XL writer
    except ImportError:
        return False

    def raw(name):
        return bytes.fromhex(expected[name]["pixels"])

    rgb = raw("gray_4x4.jxl")
    gray = Image.new("L", (4, 4))
    gray.putdata(list(rgb[0::3]))
    gray.save(OUT / "gray_4x4.jxl", lossless=True)

    rgba = raw("gray_alpha_4x4.jxl")
    gray_alpha = Image.new("LA", (4, 4))
    gray_alpha.putdata([(rgba[i], rgba[i + 3]) for i in range(0, len(rgba), 4)])
    gray_alpha.save(OUT / "gray_alpha_4x4.jxl", lossless=True)

    frame1 = Image.new("RGB", (4, 4))
    frame1.putdata([(x * 60, y * 60, 128) for y in range(4) for x in range(4)])
    frame2 = Image.new("RGB", (4, 4))
    frame2.putdata([(255 - x * 60, 255 - y * 60, 127) for y in range(4) for x in range(4)])
    frame1.save(
        OUT / "animated_2f.webp",
        save_all=True,
        append_images=[frame2],
        duration=100,
        loop=0,
        lossless=True,
    )
    return True


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files, expected = build()
    for name, data in files.items():
        (OUT / name).write_bytes(data)
    (OUT / "expected.json").write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(files)} PNG fixtures and expected.json to {OUT}")
    if write_pillow_fixtures(expected):
        print("wrote the JPEG XL and animated WebP fixtures with Pillow")
    else:
        print("Pillow or pillow-jxl-plugin missing: kept the committed JPEG XL and WebP fixtures")


if __name__ == "__main__":
    main()
