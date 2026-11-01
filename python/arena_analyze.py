"""
arena_analyze.py - Implementações de op=analyze para a Arena de Imagens.

Implementações disponíveis:
- Tier 1 (portable): impl='pure' (100% Python Puro, usando stdlib math/struct)
- Tier 2 (accelerated): impl='numpy' (Vetorizado com NumPy)

Calcula todas as 16 métricas especificadas em docs/analyze-spec.md:
1. width
2. height
3. aspect_ratio
4. block_alignment
5. mean_y
6. entropy_y
7. entropy_residual_y
8. spatial_information
9. gradient_energy
10. laplacian_variance
11. color_variance
12. unique_colors
13. alpha
14. adequacy_420
15. flat_area
16. dominant_color (+ phash, blurhash)
"""

import math
from typing import Any, Dict, List, Tuple
from python.arena_pam import PamImage

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

    dc_r = linear_to_srgb(dc[0])
    dc_g = linear_to_srgb(dc[1])
    dc_b = linear_to_srgb(dc[2])
    dc_val = (dc_r << 16) + (dc_g << 8) + dc_b
    parts.append(encode_base83(dc_val, 4))

    for comp in ac:
        qr = max(0, min(18, math.floor(sign_pow(comp[0] / max_val, 0.5) * 9.0 + 9.5)))
        qg = max(0, min(18, math.floor(sign_pow(comp[1] / max_val, 0.5) * 9.0 + 9.5)))
        qb = max(0, min(18, math.floor(sign_pow(comp[2] / max_val, 0.5) * 9.0 + 9.5)))
        parts.append(encode_base83(qr * 361 + qg * 19 + qb, 2))

    return "".join(parts)


def compute_phash(y_pixels: List[int], width: int, height: int) -> str:
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

    coeffs: List[float] = []
    for v in range(8):
        for u in range(8):
            if u == 0 and v == 0:
                coeffs.append(0.0)
            else:
                coeffs.append(D[v][u])

    sorted_c = sorted(coeffs)
    median = (sorted_c[31] + sorted_c[32]) / 2.0

    hash_val = 0
    for i, c in enumerate(coeffs):
        if c > median:
            hash_val |= (1 << (63 - i))

    return f"{hash_val:016x}"


# ---------------------------------------------------------------------------
# Implementação 1: 100% Python Puro (Tier 1 Portable)
# ---------------------------------------------------------------------------
def analyze_pure(pam: PamImage) -> Dict[str, Any]:
    width = pam.width
    height = pam.height
    depth = pam.depth
    raster = pam.data
    num_pixels = width * height

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

    g = math.gcd(width, height)
    aspect_ratio = {
        "str": f"{width // g}:{height // g}",
        "float": float(width) / float(height),
    }

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

    hist_y = [0] * 256
    for y_v in y_list:
        hist_y[y_v] += 1
    entropy_y = 0.0
    for count in hist_y:
        if count > 0:
            p = count / float(num_pixels)
            entropy_y -= p * math.log2(p)

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

    n_valid = (width - 2) * (height - 2) if (width > 2 and height > 2) else 0

    if n_valid > 0:
        sobel_m_list: List[float] = [0.0] * n_valid
        gx_sq_plus_gy_sq_list: List[float] = [0.0] * n_valid
        laplacian_list: List[float] = [0.0] * n_valid
        gx_sq_plus_gy_sq_cb: List[float] = [0.0] * n_valid
        gx_sq_plus_gy_sq_cr: List[float] = [0.0] * n_valid

        v_idx = 0
        for y_idx in range(1, height - 1):
            y_prev = (y_idx - 1) * width
            y_curr = y_idx * width
            y_next = (y_idx + 1) * width

            for x_idx in range(1, width - 1):
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

                lap = (
                    y_list[y_curr + x_idx + 1]
                    + y_list[y_curr + x_idx - 1]
                    + y_list[y_next + x_idx]
                    + y_list[y_prev + x_idx]
                    - 4 * y_list[y_curr + x_idx]
                )
                laplacian_list[v_idx] = float(lap)

                gx_cb = (
                    (cb_list[y_prev + x_idx + 1] + 2 * cb_list[y_curr + x_idx + 1] + cb_list[y_next + x_idx + 1])
                    - (cb_list[y_prev + x_idx - 1] + 2 * cb_list[y_curr + x_idx - 1] + cb_list[y_next + x_idx - 1])
                )
                gy_cb = (
                    (cb_list[y_next + x_idx - 1] + 2 * cb_list[y_next + x_idx] + cb_list[y_next + x_idx + 1])
                    - (cb_list[y_prev + x_idx - 1] + 2 * cb_list[y_prev + x_idx] + cb_list[y_prev + x_idx + 1])
                )
                gx_sq_plus_gy_sq_cb[v_idx] = float(gx_cb * gx_cb + gy_cb * gy_cb)

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

        mean_m = sum(sobel_m_list) / float(n_valid)
        spatial_information = math.sqrt(sum((m - mean_m) ** 2 for m in sobel_m_list) / float(n_valid))
        gradient_energy = sum(gx_sq_plus_gy_sq_list) / float(n_valid)

        mean_lap = sum(laplacian_list) / float(n_valid)
        laplacian_variance = sum((l - mean_lap) ** 2 for l in laplacian_list) / float(n_valid)

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

    mean_r = sum(r_list) / float(num_pixels)
    mean_g = sum(g_list) / float(num_pixels)
    mean_b = sum(b_list) / float(num_pixels)

    var_r = sum((r - mean_r) ** 2 for r in r_list) / float(num_pixels)
    var_g = sum((g_c - mean_g) ** 2 for g_c in g_list) / float(num_pixels)
    var_b = sum((b - mean_b) ** 2 for b in b_list) / float(num_pixels)
    var_sum = var_r + var_g + var_b

    unique_set = set()
    for i in range(num_pixels):
        key = (r_list[i] << 24) | (g_list[i] << 16) | (b_list[i] << 8) | a_list[i]
        unique_set.add(key)
    unique_colors = len(unique_set)

    has_alpha = (depth == 4)
    if has_alpha:
        zero_alpha_count = sum(1 for a in a_list if a == 0)
        binary_alpha_count = sum(1 for a in a_list if a == 0 or a == 255)
        alpha_sparsity = zero_alpha_count / float(num_pixels)
        alpha_binarity = binary_alpha_count / float(num_pixels)
    else:
        alpha_sparsity = 0.0
        alpha_binarity = 1.0

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

    phash_str = compute_phash(y_list, width, height)

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
# Implementação 2: Python Vetorizado com NumPy (Tier 2 Accelerated)
# ---------------------------------------------------------------------------
try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def analyze_numpy(pam: PamImage) -> Dict[str, Any]:
    if not HAVE_NUMPY:
        # Fallback gracioso para pure se numpy não estiver presente
        return analyze_pure(pam)

    width = pam.width
    height = pam.height
    depth = pam.depth
    num_pixels = width * height

    arr = np.frombuffer(pam.data, dtype=np.uint8).reshape((height, width, depth))
    R = arr[:, :, 0].astype(np.int32)
    G = arr[:, :, 1].astype(np.int32)
    B = arr[:, :, 2].astype(np.int32)
    A = arr[:, :, 3] if depth == 4 else np.full((height, width), 255, dtype=np.uint8)

    # Conversão BT.601 inteira
    Y_int = ((77 * R + 150 * G + 29 * B + 128) >> 8)
    Cb_int = (((-43 * R - 85 * G + 128 * B + 128) >> 8) + 128)
    Cr_int = (((128 * R - 107 * G - 21 * B + 128) >> 8) + 128)

    Y = np.clip(Y_int, 0, 255).astype(np.uint8)
    Cb = np.clip(Cb_int, 0, 255).astype(np.uint8)
    Cr = np.clip(Cr_int, 0, 255).astype(np.uint8)

    # 1. Proporção
    g = math.gcd(width, height)
    aspect_ratio = {
        "str": f"{width // g}:{height // g}",
        "float": float(width) / float(height),
    }

    # 2. Alinhamento de blocos
    block_alignment = {}
    for b in [8, 16, 64, 256]:
        fw = (width // b) * b
        fh = (height // b) * b
        partial = num_pixels - (fw * fh)
        block_alignment[f"b{b}"] = {
            "w_mod": width % b,
            "h_mod": height % b,
            "partial_pixels": partial,
            "partial_pct": float(partial) / float(num_pixels),
        }

    # 3. Luminância média
    mean_y = float(np.sum(Y)) / float(num_pixels)

    # 4. Entropia de Y
    hist_y = np.bincount(Y.ravel(), minlength=256)
    p_y = hist_y[hist_y > 0] / float(num_pixels)
    entropy_y = -float(np.sum(p_y * np.log2(p_y)))

    # 5. Entropia do resíduo horizontal
    if width > 1:
        diff = Y[:, 1:].astype(np.int16) - Y[:, :-1].astype(np.int16)
        hist_diff = np.bincount(diff.ravel() + 255, minlength=511)
        tot_diff = (width - 1) * height
        p_d = hist_diff[hist_diff > 0] / float(tot_diff)
        entropy_residual_y = -float(np.sum(p_d * np.log2(p_d)))
    else:
        entropy_residual_y = 0.0

    # 6. Sobel, SI, GE, Laplacian
    n_valid = (width - 2) * (height - 2) if (width > 2 and height > 2) else 0
    if n_valid > 0:
        yf = Y.astype(np.float64)
        cbf = Cb.astype(np.float64)
        crf = Cr.astype(np.float64)

        gx = (yf[:-2, 2:] + 2 * yf[1:-1, 2:] + yf[2:, 2:]) - (yf[:-2, :-2] + 2 * yf[1:-1, :-2] + yf[2:, :-2])
        gy = (yf[2:, :-2] + 2 * yf[2:, 1:-1] + yf[2:, 2:]) - (yf[:-2, :-2] + 2 * yf[:-2, 1:-1] + yf[:-2, 2:])
        mag_sq = gx * gx + gy * gy
        sobel_m = np.sqrt(mag_sq)
        mean_m = float(np.mean(sobel_m))
        spatial_information = float(np.sqrt(np.mean((sobel_m - mean_m) ** 2)))
        gradient_energy = float(np.mean(mag_sq))

        lap = yf[1:-1, 2:] + yf[1:-1, :-2] + yf[2:, 1:-1] + yf[:-2, 1:-1] - 4.0 * yf[1:-1, 1:-1]
        mean_lap = float(np.mean(lap))
        laplacian_variance = float(np.mean((lap - mean_lap) ** 2))

        gx_cb = (cbf[:-2, 2:] + 2 * cbf[1:-1, 2:] + cbf[2:, 2:]) - (cbf[:-2, :-2] + 2 * cbf[1:-1, :-2] + cbf[2:, :-2])
        gy_cb = (cbf[2:, :-2] + 2 * cbf[2:, 1:-1] + cbf[2:, 2:]) - (cbf[:-2, :-2] + 2 * cbf[:-2, 1:-1] + cbf[:-2, 2:])
        cb_ge = float(np.mean(gx_cb**2 + gy_cb**2))

        gx_cr = (crf[:-2, 2:] + 2 * crf[1:-1, 2:] + crf[2:, 2:]) - (crf[:-2, :-2] + 2 * crf[1:-1, :-2] + crf[2:, :-2])
        gy_cr = (crf[2:, :-2] + 2 * crf[2:, 1:-1] + crf[2:, 2:]) - (crf[:-2, :-2] + 2 * crf[:-2, 1:-1] + crf[:-2, 2:])
        cr_ge = float(np.mean(gx_cr**2 + gy_cr**2))

        chroma_gradient_energy = cb_ge + cr_ge
        chroma_gradient_ratio = (chroma_gradient_energy / gradient_energy) if gradient_energy > 0 else 0.0
    else:
        spatial_information = gradient_energy = laplacian_variance = chroma_gradient_energy = chroma_gradient_ratio = 0.0

    # 7. Variância de cor
    rf = R.astype(np.float64)
    gf = G.astype(np.float64)
    bf = B.astype(np.float64)
    mr, mg, mb = float(np.mean(rf)), float(np.mean(gf)), float(np.mean(bf))
    var_r = float(np.mean((rf - mr) ** 2))
    var_g = float(np.mean((gf - mg) ** 2))
    var_b = float(np.mean((bf - mb) ** 2))
    var_sum = var_r + var_g + var_b

    # 8. Cores únicas
    keys = (R.astype(np.uint32) << 24) | (G.astype(np.uint32) << 16) | (B.astype(np.uint32) << 8) | A.astype(np.uint32)
    unique_colors = int(len(np.unique(keys)))

    # 9. Alpha
    has_alpha = (depth == 4)
    if has_alpha:
        alpha_sparsity = float(np.count_nonzero(A == 0)) / float(num_pixels)
        alpha_binarity = float(np.count_nonzero((A == 0) | (A == 255))) / float(num_pixels)
    else:
        alpha_sparsity = 0.0
        alpha_binarity = 1.0

    # 10. Adequação 4:2:0
    if width % 2 == 0 and height % 2 == 0:
        cbb = Cb.reshape(height // 2, 2, width // 2, 2).transpose(0, 2, 1, 3).reshape(-1, 4).astype(np.float64)
        cbm = np.mean(cbb, axis=1, keepdims=True)
        mse_cb = float(np.sum((cbb - cbm) ** 2) / float(num_pixels))
        crb = Cr.reshape(height // 2, 2, width // 2, 2).transpose(0, 2, 1, 3).reshape(-1, 4).astype(np.float64)
        crm = np.mean(crb, axis=1, keepdims=True)
        mse_cr = float(np.sum((crb - crm) ** 2) / float(num_pixels))
        mse_chroma = (mse_cb + mse_cr) / 2.0
    else:
        # Fallback genérico se dimensões forem ímpares
        sum_sq_err_cb = 0.0
        sum_sq_err_cr = 0.0
        for by in range(0, height, 2):
            for bx in range(0, width, 2):
                block_cb = Cb[by : min(by + 2, height), bx : min(bx + 2, width)].astype(np.float64)
                block_cr = Cr[by : min(by + 2, height), bx : min(bx + 2, width)].astype(np.float64)
                avg_cb = float(np.mean(block_cb))
                avg_cr = float(np.mean(block_cr))
                sum_sq_err_cb += float(np.sum((block_cb - avg_cb) ** 2))
                sum_sq_err_cr += float(np.sum((block_cr - avg_cr) ** 2))
        mse_cb = sum_sq_err_cb / float(num_pixels)
        mse_cr = sum_sq_err_cr / float(num_pixels)
        mse_chroma = (mse_cb + mse_cr) / 2.0

    # 11. Área plana (blocos 8x8)
    bx = width // 8
    by = height // 8
    if bx > 0 and by > 0:
        yb = Y[: by * 8, : bx * 8].reshape(by, 8, bx, 8).transpose(0, 2, 1, 3).reshape(by * bx, 64).astype(np.float64)
        ym = np.mean(yb, axis=1, keepdims=True)
        yv = np.mean((yb - ym) ** 2, axis=1)
        flat_area = float(np.count_nonzero(yv < 16.0)) / float(bx * by)
    else:
        flat_area = 1.0

    # 12. Cor dominante
    idx12 = ((R >> 4) << 8) | ((G >> 4) << 4) | (B >> 4)
    hist12 = np.bincount(idx12.ravel(), minlength=4096)
    dominant_bin = int(np.argmax(hist12))
    dominant_rgb = [
        int(((dominant_bin >> 8) & 0xF) * 17),
        int(((dominant_bin >> 4) & 0xF) * 17),
        int((dominant_bin & 0xF) * 17),
    ]
    mean_rgb = [round(mr, 6), round(mg, 6), round(mb, 6)]

    # 13. pHash e BlurHash
    phash_str = compute_phash(Y.ravel().tolist(), width, height)
    rgb_bytes = arr[:, :, :3].tobytes()
    blurhash_str = compute_blurhash(rgb_bytes, width, height, 4, 3)

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
            "mean_rgb": mean_rgb,
        },
        "phash": phash_str,
        "blurhash": blurhash_str,
    }


def analyze(pam: PamImage, impl: str = "pure") -> Dict[str, Any]:
    """
    Roteador de análise de acordo com a implementação solicitada:
    - 'pure' ou 'portable' -> analyze_pure
    - 'numpy' ou 'accelerated' -> analyze_numpy
    - Padrão: se impl for vazia ou 'default', usa 'pure' para garantir máxima portabilidade.
    """
    normalized_impl = (impl or "").lower().strip()
    if normalized_impl in ("numpy", "accelerated"):
        return analyze_numpy(pam)
    return analyze_pure(pam)
