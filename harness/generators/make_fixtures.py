#!/usr/bin/env python3
"""
make_fixtures.py - Gerador de fixtures sintéticas PAM e oráculo matemático de 'op=analyze'.

Gera 8 imagens sintéticas no formato PAM P7 e calcula o gabarito oficial em
harness/fixtures/ground_truth.json de acordo com a especificação docs/analyze-spec.md.
"""

import os
import sys
import json
import math
import random
from typing import Dict, Any, Tuple, List

# ---------------------------------------------------------------------------
# Constantes Wolt BlurHash
# ---------------------------------------------------------------------------
BLURHASH_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~"


def srgb_to_linear(value: int) -> float:
    v = float(value) / 255.0
    if v <= 0.04045:
        return v / 12.92
    return ((v + 0.055) / 1.055) ** 2.4


def linear_to_srgb(value: float) -> int:
    v = max(0.0, min(1.0, value))
    if v <= 0.0031308:
        return int(v * 12.92 * 255.0 + 0.5)
    return int((1.055 * (v ** (1.0 / 2.4)) - 0.055) * 255.0 + 0.5)


def sign_pow(val: float, exp: float) -> float:
    return math.copysign(abs(val) ** exp, val)


def encode_base83(value: int, length: int) -> str:
    divisor = 83 ** (length - 1)
    res = []
    for _ in range(length):
        digit = (value // divisor) % 83
        divisor //= 83
        res.append(BLURHASH_CHARS[digit])
    return "".join(res)


def compute_blurhash(rgb_bytes: bytes, width: int, height: int, x_comp: int = 4, y_comp: int = 3) -> str:
    factors: List[List[List[float]]] = []
    for y in range(y_comp):
        row = []
        for x in range(x_comp):
            norm = 1.0 if (x == 0 and y == 0) else 2.0
            r_acc, g_acc, b_acc = 0.0, 0.0, 0.0
            for py in range(height):
                cos_y = math.cos(math.pi * y * py / height)
                row_offset = py * width * 3
                for px in range(width):
                    basis = math.cos(math.pi * x * px / width) * cos_y
                    idx = row_offset + px * 3
                    r_acc += basis * srgb_to_linear(rgb_bytes[idx])
                    g_acc += basis * srgb_to_linear(rgb_bytes[idx + 1])
                    b_acc += basis * srgb_to_linear(rgb_bytes[idx + 2])
            scale = norm / (width * height)
            row.append([r_acc * scale, g_acc * scale, b_acc * scale])
        factors.append(row)

    dc = factors[0][0]
    ac: List[List[float]] = []
    for y in range(y_comp):
        for x in range(x_comp):
            if x != 0 or y != 0:
                ac.append(factors[y][x])

    size_flag = (x_comp - 1) + (y_comp - 1) * 9
    parts = [encode_base83(size_flag, 1)]

    ac_count = len(ac)
    if ac_count > 0:
        actual_max = 0.0
        for comp in ac:
            for ch in comp:
                actual_max = max(actual_max, abs(ch))
        quant_max = max(0, min(82, math.floor(actual_max * 166.0 - 0.5)))
        max_val = (quant_max + 1) / 166.0
        parts.append(encode_base83(quant_max, 1))
    else:
        max_val = 1.0
        parts.append(encode_base83(0, 1))

    # DC component (24-bit sRGB)
    dc_r = linear_to_srgb(dc[0])
    dc_g = linear_to_srgb(dc[1])
    dc_b = linear_to_srgb(dc[2])
    dc_val = (dc_r << 16) + (dc_g << 8) + dc_b
    parts.append(encode_base83(dc_val, 4))

    # AC components
    for comp in ac:
        qr = max(0, min(18, math.floor(sign_pow(comp[0] / max_val, 0.5) * 9.0 + 9.5)))
        qg = max(0, min(18, math.floor(sign_pow(comp[1] / max_val, 0.5) * 9.0 + 9.5)))
        qb = max(0, min(18, math.floor(sign_pow(comp[2] / max_val, 0.5) * 9.0 + 9.5)))
        parts.append(encode_base83(qr * 361 + qg * 19 + qb, 2))

    return "".join(parts)


# ---------------------------------------------------------------------------
# pHash 64-bit com redimensionamento 32x32 por média de área e DCT-II
# ---------------------------------------------------------------------------
def compute_phash(y_pixels: List[int], width: int, height: int) -> str:
    # 1. Redimensionamento 32x32 por média de área contínua
    I = [[0.0] * 32 for _ in range(32)]
    sw = width / 32.0
    sh = height / 32.0
    for v in range(32):
        y0 = v * sh
        y1 = (v + 1) * sh
        sy_min = int(math.floor(y0))
        sy_max = min(height, int(math.ceil(y1)))
        for u in range(32):
            x0 = u * sw
            x1 = (u + 1) * sw
            sx_min = int(math.floor(x0))
            sx_max = min(width, int(math.ceil(x1)))
            total = 0.0
            total_weight = 0.0
            for py in range(sy_min, sy_max):
                wy = max(0.0, min(py + 1.0, y1) - max(float(py), y0))
                row_off = py * width
                for px in range(sx_min, sx_max):
                    wx = max(0.0, min(px + 1.0, x1) - max(float(px), x0))
                    w = wx * wy
                    total += y_pixels[row_off + px] * w
                    total_weight += w
            I[v][u] = total / total_weight if total_weight > 0 else 0.0

    # 2. 2D DCT-II para submatriz 8x8 de baixas frequências
    D = [[0.0] * 8 for _ in range(8)]
    for v in range(8):
        for u in range(8):
            s = 0.0
            for y in range(32):
                cos_y = math.cos(math.pi * (2 * y + 1) * v / 64.0)
                for x in range(32):
                    cos_x = math.cos(math.pi * (2 * x + 1) * u / 64.0)
                    s += I[y][x] * cos_x * cos_y
            if abs(s) < 1e-6:
                s = 0.0
            D[v][u] = s

    # 3. Submatriz 8x8 excluindo DC (0,0) -> C[0]=0.0
    coeffs: List[float] = []
    for v in range(8):
        for u in range(8):
            if u == 0 and v == 0:
                coeffs.append(0.0)
            else:
                coeffs.append(D[v][u])

    # 4. Mediana dos 64 coeficientes
    sorted_c = sorted(coeffs)
    median = (sorted_c[31] + sorted_c[32]) / 2.0

    # 5. Bit = coeff > mediana (MSB na posição 0)
    hash_val = 0
    for i, c in enumerate(coeffs):
        if c > median:
            hash_val |= (1 << (63 - i))

    return f"{hash_val:016x}"


# ---------------------------------------------------------------------------
# Leitor PAM P7
# ---------------------------------------------------------------------------
def read_pam(filepath: str) -> Tuple[int, int, int, str, bytes]:
    with open(filepath, "rb") as f:
        content = f.read()

    header_end = content.find(b"\nENDHDR\n")
    if header_end == -1:
        # Tenta com \r\n
        header_end = content.find(b"\nENDHDR\r\n")
        data_start = header_end + len(b"\nENDHDR\r\n")
    else:
        data_start = header_end + len(b"\nENDHDR\n")

    header_text = content[:header_end].decode("ascii")
    width = 0
    height = 0
    depth = 0
    tupltype = ""

    for line in header_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        key = parts[0].upper()
        val = parts[1].strip() if len(parts) > 1 else ""
        if key == "WIDTH":
            width = int(val)
        elif key == "HEIGHT":
            height = int(val)
        elif key == "DEPTH":
            depth = int(val)
        elif key == "TUPLTYPE":
            tupltype = val

    raster = content[data_start:]
    expected_len = width * height * depth
    if len(raster) < expected_len:
        raise ValueError(f"Tamanho de raster insuficiente: obtido {len(raster)}, esperado {expected_len}")

    return width, height, depth, tupltype, raster[:expected_len]


# ---------------------------------------------------------------------------
# Escritor PAM P7
# ---------------------------------------------------------------------------
def write_pam(filepath: str, width: int, height: int, depth: int, tupltype: str, data: bytes) -> None:
    header = (
        f"P7\n"
        f"WIDTH {width}\n"
        f"HEIGHT {height}\n"
        f"DEPTH {depth}\n"
        f"MAXVAL 255\n"
        f"TUPLTYPE {tupltype}\n"
        f"ENDHDR\n"
    ).encode("ascii")
    with open(filepath, "wb") as f:
        f.write(header)
        f.write(data)


# ---------------------------------------------------------------------------
# Oráculo Matemático Oficial
# ---------------------------------------------------------------------------
def analyze_pam_file(filepath: str) -> Dict[str, Any]:
    width, height, depth, tupltype, raster = read_pam(filepath)
    num_pixels = width * height

    # Extrai canais R, G, B e opcional A
    r_list: List[int] = [0] * num_pixels
    g_list: List[int] = [0] * num_pixels
    b_list: List[int] = [0] * num_pixels
    a_list: List[int] = [255] * num_pixels

    if depth == 3:
        for i in range(num_pixels):
            off = i * 3
            r_list[i] = raster[off]
            g_list[i] = raster[off + 1]
            b_list[i] = raster[off + 2]
    elif depth == 4:
        for i in range(num_pixels):
            off = i * 4
            r_list[i] = raster[off]
            g_list[i] = raster[off + 1]
            b_list[i] = raster[off + 2]
            a_list[i] = raster[off + 3]

    # 1. Proporção canônica e float
    g = math.gcd(width, height)
    aspect_ratio = {
        "str": f"{width // g}:{height // g}",
        "float": float(width) / float(height),
    }

    # 2. Alinhamento de blocos para b in {8, 16, 64, 256}
    block_alignment = {}
    for b in [8, 16, 64, 256]:
        full_w = (width // b) * b
        full_h = (height // b) * b
        partial_pixels = num_pixels - (full_w * full_h)
        block_alignment[f"b{b}"] = {
            "w_mod": width % b,
            "h_mod": height % b,
            "partial_pixels": partial_pixels,
            "partial_pct": float(partial_pixels) / float(num_pixels),
        }

    # 3. Conversão de cores BT.601 inteira
    y_list: List[int] = [0] * num_pixels
    cb_list: List[int] = [0] * num_pixels
    cr_list: List[int] = [0] * num_pixels

    for i in range(num_pixels):
        r = r_list[i]
        g_c = g_list[i]
        b = b_list[i]
        y_val = (77 * r + 150 * g_c + 29 * b + 128) >> 8
        cb_val = (((-43 * r - 85 * g_c + 128 * b + 128) >> 8) + 128)
        cr_val = (((128 * r - 107 * g_c - 21 * b + 128) >> 8) + 128)

        y_list[i] = max(0, min(255, y_val))
        cb_list[i] = max(0, min(255, cb_val))
        cr_list[i] = max(0, min(255, cr_val))

    mean_y = sum(y_list) / float(num_pixels)

    # 4. Entropia de Shannon de Y
    hist_y = [0] * 256
    for y_v in y_list:
        hist_y[y_v] += 1
    entropy_y = 0.0
    for count in hist_y:
        if count > 0:
            p = count / float(num_pixels)
            entropy_y -= p * math.log2(p)

    # 5. Entropia do resíduo horizontal de Y (Y[x, y] - Y[x-1, y])
    diff_counts: Dict[int, int] = {}
    total_diffs = (width - 1) * height
    if width > 1:
        for y_idx in range(height):
            row_off = y_idx * width
            for x_idx in range(1, width):
                diff = y_list[row_off + x_idx] - y_list[row_off + x_idx - 1]
                diff_counts[diff] = diff_counts.get(diff, 0) + 1
        entropy_residual_y = 0.0
        for cnt in diff_counts.values():
            if cnt > 0:
                p = cnt / float(total_diffs)
                entropy_residual_y -= p * math.log2(p)
    else:
        entropy_residual_y = 0.0

    # 6. Sobel, Informação Espacial (SI), Energia de Gradiente e Laplaciano
    n_valid = (width - 2) * (height - 2) if (width > 2 and height > 2) else 0

    if n_valid > 0:
        sobel_m_list: List[float] = [0.0] * n_valid
        gx_sq_plus_gy_sq_list: List[float] = [0.0] * n_valid
        laplacian_list: List[float] = [0.0] * n_valid

        # Para adequação 4:2:0 (energia de gradiente Cb e Cr)
        gx_sq_plus_gy_sq_cb: List[float] = [0.0] * n_valid
        gx_sq_plus_gy_sq_cr: List[float] = [0.0] * n_valid

        v_idx = 0
        for y_idx in range(1, height - 1):
            y_prev = (y_idx - 1) * width
            y_curr = y_idx * width
            y_next = (y_idx + 1) * width

            for x_idx in range(1, width - 1):
                # Y Sobel
                gx = (
                    (y_list[y_prev + x_idx + 1] + 2 * y_list[y_curr + x_idx + 1] + y_list[y_next + x_idx + 1])
                    - (y_list[y_prev + x_idx - 1] + 2 * y_list[y_curr + x_idx - 1] + y_list[y_next + x_idx - 1])
                )
                gy = (
                    (y_list[y_next + x_idx - 1] + 2 * y_list[y_next + x_idx] + y_list[y_next + x_idx + 1])
                    - (y_list[y_prev + x_idx - 1] + 2 * y_list[y_prev + x_idx] + y_list[y_prev + x_idx + 1])
                )
                mag_sq = float(gx * gx + gy * gy)
                sobel_m_list[v_idx] = math.sqrt(mag_sq)
                gx_sq_plus_gy_sq_list[v_idx] = mag_sq

                # Laplaciano 4-vizinhos
                lap = (
                    y_list[y_curr + x_idx + 1]
                    + y_list[y_curr + x_idx - 1]
                    + y_list[y_next + x_idx]
                    + y_list[y_prev + x_idx]
                    - 4 * y_list[y_curr + x_idx]
                )
                laplacian_list[v_idx] = float(lap)

                # Cb Sobel
                gx_cb = (
                    (cb_list[y_prev + x_idx + 1] + 2 * cb_list[y_curr + x_idx + 1] + cb_list[y_next + x_idx + 1])
                    - (cb_list[y_prev + x_idx - 1] + 2 * cb_list[y_curr + x_idx - 1] + cb_list[y_next + x_idx - 1])
                )
                gy_cb = (
                    (cb_list[y_next + x_idx - 1] + 2 * cb_list[y_next + x_idx] + cb_list[y_next + x_idx + 1])
                    - (cb_list[y_prev + x_idx - 1] + 2 * cb_list[y_prev + x_idx] + cb_list[y_prev + x_idx + 1])
                )
                gx_sq_plus_gy_sq_cb[v_idx] = float(gx_cb * gx_cb + gy_cb * gy_cb)

                # Cr Sobel
                gx_cr = (
                    (cr_list[y_prev + x_idx + 1] + 2 * cr_list[y_curr + x_idx + 1] + cr_list[y_next + x_idx + 1])
                    - (cr_list[y_prev + x_idx - 1] + 2 * cr_list[y_curr + x_idx - 1] + cr_list[y_next + x_idx - 1])
                )
                gy_cr = (
                    (cr_list[y_next + x_idx - 1] + 2 * cr_list[y_next + x_idx] + cr_list[y_next + x_idx + 1])
                    - (cr_list[y_prev + x_idx - 1] + 2 * cr_list[y_prev + x_idx] + cr_list[y_prev + x_idx + 1])
                )
                gx_sq_plus_gy_sq_cr[v_idx] = float(gx_cr * gx_cr + gy_cr * gy_cr)

                v_idx += 1

        # SI (desvio padrão populacional da magnitude de Sobel)
        mean_m = sum(sobel_m_list) / float(n_valid)
        spatial_information = math.sqrt(sum((m - mean_m) ** 2 for m in sobel_m_list) / float(n_valid))

        # Gradient energy (média de Gx^2 + Gy^2)
        gradient_energy = sum(gx_sq_plus_gy_sq_list) / float(n_valid)

        # Variância Laplaciana populacional
        mean_lap = sum(laplacian_list) / float(n_valid)
        laplacian_variance = sum((l - mean_lap) ** 2 for l in laplacian_list) / float(n_valid)

        # Croma gradiente
        chroma_ge_cb = sum(gx_sq_plus_gy_sq_cb) / float(n_valid)
        chroma_ge_cr = sum(gx_sq_plus_gy_sq_cr) / float(n_valid)
        chroma_gradient_energy = chroma_ge_cb + chroma_ge_cr
        chroma_gradient_ratio = (chroma_gradient_energy / gradient_energy) if gradient_energy > 0 else 0.0
    else:
        spatial_information = 0.0
        gradient_energy = 0.0
        laplacian_variance = 0.0
        chroma_gradient_energy = 0.0
        chroma_gradient_ratio = 0.0

    # 7. Variância de cor
    mean_r = sum(r_list) / float(num_pixels)
    mean_g = sum(g_list) / float(num_pixels)
    mean_b = sum(b_list) / float(num_pixels)

    var_r = sum((r - mean_r) ** 2 for r in r_list) / float(num_pixels)
    var_g = sum((g_c - mean_g) ** 2 for g_c in g_list) / float(num_pixels)
    var_b = sum((b - mean_b) ** 2 for b in b_list) / float(num_pixels)
    var_sum = var_r + var_g + var_b

    # 8. Contagem exata de cores únicas (32 bits RGBA)
    unique_set = set()
    for i in range(num_pixels):
        key = (r_list[i] << 24) | (g_list[i] << 16) | (b_list[i] << 8) | a_list[i]
        unique_set.add(key)
    unique_colors = len(unique_set)

    # 9. Métricas de Alpha
    has_alpha = (depth == 4)
    if has_alpha:
        zero_alpha_count = sum(1 for a in a_list if a == 0)
        binary_alpha_count = sum(1 for a in a_list if a == 0 or a == 255)
        alpha_sparsity = zero_alpha_count / float(num_pixels)
        alpha_binarity = binary_alpha_count / float(num_pixels)
    else:
        alpha_sparsity = 0.0
        alpha_binarity = 1.0

    # 10. Adequação 4:2:0 - MSE de Ida e Volta 2x2 em Cb e Cr
    sum_sq_err_cb = 0.0
    sum_sq_err_cr = 0.0

    for by in range(0, height, 2):
        for bx in range(0, width, 2):
            block_cb = []
            block_cr = []
            for dy in range(2):
                py = by + dy
                if py >= height:
                    continue
                row_off = py * width
                for dx in range(2):
                    px = bx + dx
                    if px >= width:
                        continue
                    block_cb.append(cb_list[row_off + px])
                    block_cr.append(cr_list[row_off + px])
            k = len(block_cb)
            if k > 0:
                avg_cb = sum(block_cb) / float(k)
                avg_cr = sum(block_cr) / float(k)
                for val in block_cb:
                    sum_sq_err_cb += (val - avg_cb) ** 2
                for val in block_cr:
                    sum_sq_err_cr += (val - avg_cr) ** 2

    mse_cb = sum_sq_err_cb / float(num_pixels)
    mse_cr = sum_sq_err_cr / float(num_pixels)
    mse_chroma = (mse_cb + mse_cr) / 2.0

    # 11. Fração de Área Plana (blocos 8x8 com Var(Y) < 16.0)
    blocks_x = width // 8
    blocks_y = height // 8
    total_complete_blocks = blocks_x * blocks_y
    if total_complete_blocks > 0:
        flat_blocks_count = 0
        for by in range(blocks_y):
            for bx in range(blocks_x):
                block_y_vals = []
                for dy in range(8):
                    row_off = (by * 8 + dy) * width
                    for dx in range(8):
                        block_y_vals.append(y_list[row_off + (bx * 8 + dx)])
                block_mean = sum(block_y_vals) / 64.0
                block_var = sum((y_v - block_mean) ** 2 for y_v in block_y_vals) / 64.0
                if block_var < 16.0:
                    flat_blocks_count += 1
        flat_area = flat_blocks_count / float(total_complete_blocks)
    else:
        flat_area = 1.0

    # 12. Cor dominante (moda 12-bit RGB com desempate pelo menor índice)
    hist_12bit = [0] * 4096
    for i in range(num_pixels):
        r4 = r_list[i] >> 4
        g4 = g_list[i] >> 4
        b4 = b_list[i] >> 4
        idx = (r4 << 8) | (g4 << 4) | b4
        hist_12bit[idx] += 1

    dominant_bin = 0
    max_count = -1
    for idx, count in enumerate(hist_12bit):
        if count > max_count:
            max_count = count
            dominant_bin = idx

    r4_dom = (dominant_bin >> 8) & 0xF
    g4_dom = (dominant_bin >> 4) & 0xF
    b4_dom = dominant_bin & 0xF
    dominant_rgb = [r4_dom * 17, g4_dom * 17, b4_dom * 17]

    # 13. pHash 64-bit
    phash_str = compute_phash(y_list, width, height)

    # 14. Wolt BlurHash
    # Prepara array RGB contíguo para BlurHash (ignora canal alpha)
    rgb_raw = bytearray(num_pixels * 3)
    for i in range(num_pixels):
        rgb_raw[i * 3] = r_list[i]
        rgb_raw[i * 3 + 1] = g_list[i]
        rgb_raw[i * 3 + 2] = b_list[i]
    blurhash_str = compute_blurhash(bytes(rgb_raw), width, height, 4, 3)

    return {
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "block_alignment": block_alignment,
        "mean_y": round(mean_y, 6),
        "entropy_y": round(entropy_y, 6),
        "entropy_residual_y": round(entropy_residual_y, 6),
        "spatial_information": round(spatial_information, 6),
        "gradient_energy": round(gradient_energy, 6),
        "laplacian_variance": round(laplacian_variance, 6),
        "color_variance": {
            "var_r": round(var_r, 6),
            "var_g": round(var_g, 6),
            "var_b": round(var_b, 6),
            "var_sum": round(var_sum, 6),
        },
        "unique_colors": unique_colors,
        "alpha": {
            "has_alpha": has_alpha,
            "sparsity": round(alpha_sparsity, 6),
            "binarity": round(alpha_binarity, 6),
        },
        "adequacy_420": {
            "chroma_gradient_energy": round(chroma_gradient_energy, 6),
            "chroma_gradient_ratio": round(chroma_gradient_ratio, 6),
            "mse_cb": round(mse_cb, 6),
            "mse_cr": round(mse_cr, 6),
            "mse_chroma": round(mse_chroma, 6),
        },
        "flat_area": round(flat_area, 6),
        "dominant_color": {
            "dominant_rgb": dominant_rgb,
            "dominant_bin": dominant_bin,
            "mean_rgb": [round(mean_r, 6), round(mean_g, 6), round(mean_b, 6)],
        },
        "phash": phash_str,
        "blurhash": blurhash_str,
    }


# ---------------------------------------------------------------------------
# Geração das Fixtures Sintéticas
# ---------------------------------------------------------------------------
def generate_synthetic_fixtures(output_dir: str) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []

    # 1. solid_red.pam (64x64, RGB)
    w, h = 64, 64
    red_data = bytes([255, 0, 0] * (w * h))
    path = os.path.join(output_dir, "solid_red.pam")
    write_pam(path, w, h, 3, "RGB", red_data)
    generated_files.append(path)

    # 2. solid_black.pam (64x64, RGB)
    black_data = bytes([0, 0, 0] * (w * h))
    path = os.path.join(output_dir, "solid_black.pam")
    write_pam(path, w, h, 3, "RGB", black_data)
    generated_files.append(path)

    # 3. checkerboard_1x1.pam (64x64, RGB)
    check1_buf = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            val = 255 if (x + y) % 2 == 0 else 0
            idx = (y * w + x) * 3
            check1_buf[idx] = val
            check1_buf[idx + 1] = val
            check1_buf[idx + 2] = val
    path = os.path.join(output_dir, "checkerboard_1x1.pam")
    write_pam(path, w, h, 3, "RGB", bytes(check1_buf))
    generated_files.append(path)

    # 4. checkerboard_8x8.pam (64x64, RGB)
    check8_buf = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            val = 255 if ((x // 8) + (y // 8)) % 2 == 0 else 0
            idx = (y * w + x) * 3
            check8_buf[idx] = val
            check8_buf[idx + 1] = val
            check8_buf[idx + 2] = val
    path = os.path.join(output_dir, "checkerboard_8x8.pam")
    write_pam(path, w, h, 3, "RGB", bytes(check8_buf))
    generated_files.append(path)

    # 5. gradient_h.pam (64x64, RGB)
    grad_h_buf = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            val = int(x * 255 / (w - 1))
            idx = (y * w + x) * 3
            grad_h_buf[idx] = val
            grad_h_buf[idx + 1] = val
            grad_h_buf[idx + 2] = val
    path = os.path.join(output_dir, "gradient_h.pam")
    write_pam(path, w, h, 3, "RGB", bytes(grad_h_buf))
    generated_files.append(path)

    # 6. gradient_v.pam (64x64, RGB)
    grad_v_buf = bytearray(w * h * 3)
    for y in range(h):
        for x in range(w):
            val = int(y * 255 / (h - 1))
            idx = (y * w + x) * 3
            grad_v_buf[idx] = val
            grad_v_buf[idx + 1] = val
            grad_v_buf[idx + 2] = val
    path = os.path.join(output_dir, "gradient_v.pam")
    write_pam(path, w, h, 3, "RGB", bytes(grad_v_buf))
    generated_files.append(path)

    # 7. noise_deterministic.pam (64x64, RGB, seed=42)
    rng = random.Random(42)
    noise_buf = bytearray(w * h * 3)
    for i in range(w * h * 3):
        noise_buf[i] = rng.randint(0, 255)
    path = os.path.join(output_dir, "noise_deterministic.pam")
    write_pam(path, w, h, 3, "RGB", bytes(noise_buf))
    generated_files.append(path)

    # 8. alpha_boxes.pam (64x64, RGB_ALPHA)
    # 4 quadrantes 32x32:
    # (0,0): Vermelho, A=0
    # (1,0): Verde, A=85
    # (0,1): Azul, A=170
    # (1,1): Amarelo, A=255
    alpha_buf = bytearray(w * h * 4)
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            if x < 32 and y < 32:
                # Top-Left: Red, transparent
                alpha_buf[idx] = 255
                alpha_buf[idx + 1] = 0
                alpha_buf[idx + 2] = 0
                alpha_buf[idx + 3] = 0
            elif x >= 32 and y < 32:
                # Top-Right: Green, semi-transparent
                alpha_buf[idx] = 0
                alpha_buf[idx + 1] = 255
                alpha_buf[idx + 2] = 0
                alpha_buf[idx + 3] = 85
            elif x < 32 and y >= 32:
                # Bottom-Left: Blue, semi-opaque
                alpha_buf[idx] = 0
                alpha_buf[idx + 1] = 0
                alpha_buf[idx + 2] = 255
                alpha_buf[idx + 3] = 170
            else:
                # Bottom-Right: Yellow, opaque
                alpha_buf[idx] = 255
                alpha_buf[idx + 1] = 255
                alpha_buf[idx + 2] = 0
                alpha_buf[idx + 3] = 255
    path = os.path.join(output_dir, "alpha_boxes.pam")
    write_pam(path, w, h, 4, "RGB_ALPHA", bytes(alpha_buf))
    generated_files.append(path)

    return generated_files


def main() -> int:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    synthetic_dir = os.path.join(base_dir, "harness", "fixtures", "synthetic")
    ground_truth_path = os.path.join(base_dir, "harness", "fixtures", "ground_truth.json")

    print(f"[*] Gerando fixtures sintéticas em: {synthetic_dir}")
    fixture_files = generate_synthetic_fixtures(synthetic_dir)
    print(f"[+] {len(fixture_files)} fixtures geradas com sucesso.")

    ground_truth: Dict[str, Any] = {}
    print(f"[*] Executando oráculo matemático para cada fixture...")
    for fpath in fixture_files:
        fname = os.path.basename(fpath)
        print(f"    - Analisando {fname}...")
        result = analyze_pam_file(fpath)
        ground_truth[fname] = result

    print(f"[*] Gravando gabarito oficial em: {ground_truth_path}")
    os.makedirs(os.path.dirname(ground_truth_path), exist_ok=True)
    with open(ground_truth_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2, sort_keys=True)

    print(f"[+] Gabarito gravado com {len(ground_truth)} entradas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
