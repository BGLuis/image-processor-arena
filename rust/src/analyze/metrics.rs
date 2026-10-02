// rust/src/analyze/metrics.rs
// Implementação estrita das 16 métricas de imagem segundo docs/analyze-spec.md.

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

#[inline]
pub fn round6(v: f64) -> f64 {
    (v * 1_000_000.0).round() / 1_000_000.0
}

fn gcd(mut a: u32, mut b: u32) -> u32 {
    while b != 0 {
        let t = b;
        b = a % b;
        a = t;
    }
    a
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AspectRatio {
    pub str: String,
    pub float: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BlockInfo {
    pub w_mod: u32,
    pub h_mod: u32,
    pub partial_pixels: u64,
    pub partial_pct: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BlockAlignment {
    pub b8: BlockInfo,
    pub b16: BlockInfo,
    pub b64: BlockInfo,
    pub b256: BlockInfo,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ColorVariance {
    pub var_r: f64,
    pub var_g: f64,
    pub var_b: f64,
    pub var_sum: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AlphaMetrics {
    pub has_alpha: bool,
    pub sparsity: f64,
    pub binarity: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Adequacy420 {
    pub chroma_gradient_energy: f64,
    pub chroma_gradient_ratio: f64,
    pub mse_cb: f64,
    pub mse_cr: f64,
    pub mse_chroma: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct DominantColor {
    pub dominant_rgb: [u8; 3],
    pub dominant_bin: usize,
    pub mean_rgb: [f64; 3],
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AnalyzeResult {
    pub width: u32,
    pub height: u32,
    pub aspect_ratio: AspectRatio,
    pub block_alignment: BlockAlignment,
    pub mean_y: f64,
    pub entropy_y: f64,
    pub entropy_residual_y: f64,
    pub spatial_information: f64,
    pub gradient_energy: f64,
    pub laplacian_variance: f64,
    pub color_variance: ColorVariance,
    pub unique_colors: usize,
    pub alpha: AlphaMetrics,
    pub adequacy_420: Adequacy420,
    pub flat_area: f64,
    pub dominant_color: DominantColor,
    pub phash: String,
    pub blurhash: String,
}

pub fn analyze(width: u32, height: u32, depth: u8, raster: &[u8]) -> AnalyzeResult {
    let num_pixels = (width as usize) * (height as usize);
    let mut r_list = vec![0u8; num_pixels];
    let mut g_list = vec![0u8; num_pixels];
    let mut b_list = vec![0u8; num_pixels];
    let mut a_list = vec![255u8; num_pixels];

    if depth == 3 {
        for i in 0..num_pixels {
            let off = i * 3;
            r_list[i] = raster[off];
            g_list[i] = raster[off + 1];
            b_list[i] = raster[off + 2];
        }
    } else if depth == 4 {
        for i in 0..num_pixels {
            let off = i * 4;
            r_list[i] = raster[off];
            g_list[i] = raster[off + 1];
            b_list[i] = raster[off + 2];
            a_list[i] = raster[off + 3];
        }
    }

    // 1. Proporção canônica e float
    let g = gcd(width, height);
    let aspect_ratio = AspectRatio {
        str: format!("{}:{}", width / g, height / g),
        float: (width as f64) / (height as f64),
    };

    // 2. Alinhamento a blocos
    // As contas de área usam u64: width*height em u32 estoura em imagens grandes.
    let compute_block = |b: u32| {
        let full_w = u64::from(width / b) * u64::from(b);
        let full_h = u64::from(height / b) * u64::from(b);
        let partial_pixels = (num_pixels as u64) - full_w * full_h;
        BlockInfo {
            w_mod: width % b,
            h_mod: height % b,
            partial_pixels,
            partial_pct: (partial_pixels as f64) / (num_pixels as f64),
        }
    };

    let block_alignment = BlockAlignment {
        b8: compute_block(8),
        b16: compute_block(16),
        b64: compute_block(64),
        b256: compute_block(256),
    };

    // 3. Conversão BT.601 inteira
    let mut y_list = vec![0u8; num_pixels];
    let mut cb_list = vec![0u8; num_pixels];
    let mut cr_list = vec![0u8; num_pixels];

    let mut sum_y = 0u64;
    for i in 0..num_pixels {
        let r = r_list[i] as i32;
        let g_val = g_list[i] as i32;
        let b = b_list[i] as i32;

        let y_val = (77 * r + 150 * g_val + 29 * b + 128) >> 8;
        let cb_val = ((-43 * r - 85 * g_val + 128 * b + 128) >> 8) + 128;
        let cr_val = ((128 * r - 107 * g_val - 21 * b + 128) >> 8) + 128;

        let y = y_val.clamp(0, 255) as u8;
        let cb = cb_val.clamp(0, 255) as u8;
        let cr = cr_val.clamp(0, 255) as u8;

        y_list[i] = y;
        cb_list[i] = cb;
        cr_list[i] = cr;
        sum_y += y as u64;
    }

    let mean_y = (sum_y as f64) / (num_pixels as f64);

    // 4. Entropia de Shannon de Y
    let mut hist_y = [0u32; 256];
    for &y in &y_list {
        hist_y[y as usize] += 1;
    }
    let mut entropy_y = 0.0f64;
    let n_f64 = num_pixels as f64;
    for &cnt in &hist_y {
        if cnt > 0 {
            let p = (cnt as f64) / n_f64;
            entropy_y -= p * p.log2();
        }
    }

    // 5. Entropia do resíduo horizontal de Y
    let mut entropy_residual_y = 0.0f64;
    let w_usize = width as usize;
    let h_usize = height as usize;
    if width > 1 {
        let total_diffs = ((width - 1) as usize) * h_usize;
        let mut diff_counts = [0u32; 512]; // Offset +256 para abranger [-255, 255]
        for y_idx in 0..h_usize {
            let row_off = y_idx * w_usize;
            for x_idx in 1..w_usize {
                let diff = (y_list[row_off + x_idx] as i32) - (y_list[row_off + x_idx - 1] as i32);
                let bin = (diff + 256) as usize;
                diff_counts[bin] += 1;
            }
        }
        let total_diffs_f64 = total_diffs as f64;
        for &cnt in &diff_counts {
            if cnt > 0 {
                let p = (cnt as f64) / total_diffs_f64;
                entropy_residual_y -= p * p.log2();
            }
        }
    }

    // 6. Sobel, SI, Gradient Energy e Laplaciano
    let n_valid = if width > 2 && height > 2 {
        ((width - 2) as usize) * ((height - 2) as usize)
    } else {
        0
    };

    let mut spatial_information = 0.0f64;
    let mut gradient_energy = 0.0f64;
    let mut laplacian_variance = 0.0f64;
    let mut chroma_gradient_energy = 0.0f64;
    let mut chroma_gradient_ratio = 0.0f64;

    if n_valid > 0 {
        let mut sobel_m_list = Vec::with_capacity(n_valid);
        let mut laplacian_list = Vec::with_capacity(n_valid);

        let mut sum_m = 0.0f64;
        let mut sum_lap = 0.0f64;
        let mut sum_ge = 0.0f64;
        let mut sum_ge_cb = 0.0f64;
        let mut sum_ge_cr = 0.0f64;

        for y_idx in 1..(h_usize - 1) {
            let y_prev = (y_idx - 1) * w_usize;
            let y_curr = y_idx * w_usize;
            let y_next = (y_idx + 1) * w_usize;

            for x_idx in 1..(w_usize - 1) {
                // Y Sobel
                let gx = ((y_list[y_prev + x_idx + 1] as i32)
                    + 2 * (y_list[y_curr + x_idx + 1] as i32)
                    + (y_list[y_next + x_idx + 1] as i32))
                    - ((y_list[y_prev + x_idx - 1] as i32)
                        + 2 * (y_list[y_curr + x_idx - 1] as i32)
                        + (y_list[y_next + x_idx - 1] as i32));
                let gy = ((y_list[y_next + x_idx - 1] as i32)
                    + 2 * (y_list[y_next + x_idx] as i32)
                    + (y_list[y_next + x_idx + 1] as i32))
                    - ((y_list[y_prev + x_idx - 1] as i32)
                        + 2 * (y_list[y_prev + x_idx] as i32)
                        + (y_list[y_prev + x_idx + 1] as i32));

                let mag_sq = (gx * gx + gy * gy) as f64;
                let m = mag_sq.sqrt();
                sobel_m_list.push(m);
                sum_m += m;
                sum_ge += mag_sq;

                // Laplaciano 4 vizinhos
                let lap = ((y_list[y_curr + x_idx + 1] as i32)
                    + (y_list[y_curr + x_idx - 1] as i32)
                    + (y_list[y_next + x_idx] as i32)
                    + (y_list[y_prev + x_idx] as i32)
                    - 4 * (y_list[y_curr + x_idx] as i32)) as f64;
                laplacian_list.push(lap);
                sum_lap += lap;

                // Cb Sobel
                let gx_cb = ((cb_list[y_prev + x_idx + 1] as i32)
                    + 2 * (cb_list[y_curr + x_idx + 1] as i32)
                    + (cb_list[y_next + x_idx + 1] as i32))
                    - ((cb_list[y_prev + x_idx - 1] as i32)
                        + 2 * (cb_list[y_curr + x_idx - 1] as i32)
                        + (cb_list[y_next + x_idx - 1] as i32));
                let gy_cb = ((cb_list[y_next + x_idx - 1] as i32)
                    + 2 * (cb_list[y_next + x_idx] as i32)
                    + (cb_list[y_next + x_idx + 1] as i32))
                    - ((cb_list[y_prev + x_idx - 1] as i32)
                        + 2 * (cb_list[y_prev + x_idx] as i32)
                        + (cb_list[y_prev + x_idx + 1] as i32));
                let mag_sq_cb = (gx_cb * gx_cb + gy_cb * gy_cb) as f64;
                sum_ge_cb += mag_sq_cb;

                // Cr Sobel
                let gx_cr = ((cr_list[y_prev + x_idx + 1] as i32)
                    + 2 * (cr_list[y_curr + x_idx + 1] as i32)
                    + (cr_list[y_next + x_idx + 1] as i32))
                    - ((cr_list[y_prev + x_idx - 1] as i32)
                        + 2 * (cr_list[y_curr + x_idx - 1] as i32)
                        + (cr_list[y_next + x_idx - 1] as i32));
                let gy_cr = ((cr_list[y_next + x_idx - 1] as i32)
                    + 2 * (cr_list[y_next + x_idx] as i32)
                    + (cr_list[y_next + x_idx + 1] as i32))
                    - ((cr_list[y_prev + x_idx - 1] as i32)
                        + 2 * (cr_list[y_prev + x_idx] as i32)
                        + (cr_list[y_prev + x_idx + 1] as i32));
                let mag_sq_cr = (gx_cr * gx_cr + gy_cr * gy_cr) as f64;
                sum_ge_cr += mag_sq_cr;
            }
        }

        let n_val_f64 = n_valid as f64;
        let mean_m = sum_m / n_val_f64;
        let mut sum_var_m = 0.0f64;
        for &m in &sobel_m_list {
            let diff = m - mean_m;
            sum_var_m += diff * diff;
        }
        spatial_information = (sum_var_m / n_val_f64).sqrt();

        gradient_energy = sum_ge / n_val_f64;

        let mean_lap = sum_lap / n_val_f64;
        let mut sum_var_lap = 0.0f64;
        for &lap in &laplacian_list {
            let diff = lap - mean_lap;
            sum_var_lap += diff * diff;
        }
        laplacian_variance = sum_var_lap / n_val_f64;

        let chroma_ge_cb = sum_ge_cb / n_val_f64;
        let chroma_ge_cr = sum_ge_cr / n_val_f64;
        chroma_gradient_energy = chroma_ge_cb + chroma_ge_cr;
        chroma_gradient_ratio = if gradient_energy > 0.0 {
            chroma_gradient_energy / gradient_energy
        } else {
            0.0
        };
    }

    // 7. Variância de cor
    let mut sum_r = 0u64;
    let mut sum_g = 0u64;
    let mut sum_b = 0u64;
    for i in 0..num_pixels {
        sum_r += r_list[i] as u64;
        sum_g += g_list[i] as u64;
        sum_b += b_list[i] as u64;
    }
    let mean_r = (sum_r as f64) / n_f64;
    let mean_g = (sum_g as f64) / n_f64;
    let mean_b = (sum_b as f64) / n_f64;

    let mut sum_var_r = 0.0f64;
    let mut sum_var_g = 0.0f64;
    let mut sum_var_b = 0.0f64;
    for i in 0..num_pixels {
        let dr = (r_list[i] as f64) - mean_r;
        let dg = (g_list[i] as f64) - mean_g;
        let db = (b_list[i] as f64) - mean_b;
        sum_var_r += dr * dr;
        sum_var_g += dg * dg;
        sum_var_b += db * db;
    }
    let var_r = sum_var_r / n_f64;
    let var_g = sum_var_g / n_f64;
    let var_b = sum_var_b / n_f64;
    let var_sum = var_r + var_g + var_b;

    // 8. Cores únicas
    let mut unique_set = HashSet::with_capacity(num_pixels.min(100_000));
    for i in 0..num_pixels {
        let key = ((r_list[i] as u32) << 24)
            | ((g_list[i] as u32) << 16)
            | ((b_list[i] as u32) << 8)
            | (a_list[i] as u32);
        unique_set.insert(key);
    }
    let unique_colors = unique_set.len();

    // 9. Métricas de Alpha
    let has_alpha = depth == 4;
    let (alpha_sparsity, alpha_binarity) = if has_alpha {
        let mut zero_alpha = 0usize;
        let mut binary_alpha = 0usize;
        for &a in &a_list {
            if a == 0 {
                zero_alpha += 1;
                binary_alpha += 1;
            } else if a == 255 {
                binary_alpha += 1;
            }
        }
        ((zero_alpha as f64) / n_f64, (binary_alpha as f64) / n_f64)
    } else {
        (0.0, 1.0)
    };

    // 10. Adequação 4:2:0 - MSE de Ida e Volta 2x2 em Cb e Cr
    let mut sum_sq_err_cb = 0.0f64;
    let mut sum_sq_err_cr = 0.0f64;
    for by in (0..h_usize).step_by(2) {
        for bx in (0..w_usize).step_by(2) {
            let mut block_cb = [0u8; 4];
            let mut block_cr = [0u8; 4];
            let mut k = 0usize;
            for dy in 0..2 {
                let py = by + dy;
                if py >= h_usize {
                    continue;
                }
                let row_off = py * w_usize;
                for dx in 0..2 {
                    let px = bx + dx;
                    if px >= w_usize {
                        continue;
                    }
                    block_cb[k] = cb_list[row_off + px];
                    block_cr[k] = cr_list[row_off + px];
                    k += 1;
                }
            }
            if k > 0 {
                let mut s_cb = 0u32;
                let mut s_cr = 0u32;
                for j in 0..k {
                    s_cb += block_cb[j] as u32;
                    s_cr += block_cr[j] as u32;
                }
                let avg_cb = (s_cb as f64) / (k as f64);
                let avg_cr = (s_cr as f64) / (k as f64);
                for j in 0..k {
                    let d_cb = (block_cb[j] as f64) - avg_cb;
                    let d_cr = (block_cr[j] as f64) - avg_cr;
                    sum_sq_err_cb += d_cb * d_cb;
                    sum_sq_err_cr += d_cr * d_cr;
                }
            }
        }
    }
    let mse_cb = sum_sq_err_cb / n_f64;
    let mse_cr = sum_sq_err_cr / n_f64;
    let mse_chroma = (mse_cb + mse_cr) / 2.0;

    // 11. Fração de Área Plana (blocos 8x8 com Var(Y) < 16.0)
    let blocks_x = w_usize / 8;
    let blocks_y = h_usize / 8;
    let total_complete_blocks = blocks_x * blocks_y;
    let flat_area = if total_complete_blocks > 0 {
        let mut flat_blocks_count = 0usize;
        for by in 0..blocks_y {
            for bx in 0..blocks_x {
                let mut sum_block_y = 0.0f64;
                let mut block_y_vals = [0.0f64; 64];
                let mut b_idx = 0usize;
                for dy in 0..8 {
                    let row_off = (by * 8 + dy) * w_usize;
                    for dx in 0..8 {
                        let y_v = y_list[row_off + (bx * 8 + dx)] as f64;
                        block_y_vals[b_idx] = y_v;
                        sum_block_y += y_v;
                        b_idx += 1;
                    }
                }
                let block_mean = sum_block_y / 64.0;
                let mut block_var = 0.0f64;
                for &y_v in &block_y_vals {
                    let diff = y_v - block_mean;
                    block_var += diff * diff;
                }
                block_var /= 64.0;
                if block_var < 16.0 {
                    flat_blocks_count += 1;
                }
            }
        }
        (flat_blocks_count as f64) / (total_complete_blocks as f64)
    } else {
        1.0
    };

    // 12. Cor Dominante (histograma 12-bit com desempate pelo menor índice)
    let mut hist_12bit = vec![0u32; 4096];
    for i in 0..num_pixels {
        let r4 = (r_list[i] >> 4) as usize;
        let g4 = (g_list[i] >> 4) as usize;
        let b4 = (b_list[i] >> 4) as usize;
        let idx = (r4 << 8) | (g4 << 4) | b4;
        hist_12bit[idx] += 1;
    }

    let mut dominant_bin = 0usize;
    let mut max_count = -1i64;
    for (idx, &count) in hist_12bit.iter().enumerate() {
        if (count as i64) > max_count {
            max_count = count as i64;
            dominant_bin = idx;
        }
    }

    let r4_dom = ((dominant_bin >> 8) & 0xF) as u8;
    let g4_dom = ((dominant_bin >> 4) & 0xF) as u8;
    let b4_dom = (dominant_bin & 0xF) as u8;
    let dominant_rgb = [r4_dom * 17, g4_dom * 17, b4_dom * 17];

    // 13. pHash 64-bit
    let phash_str = super::phash::compute_phash(&y_list, w_usize, h_usize);

    // 14. BlurHash (canais separados, como no engine Go)
    let blurhash_str =
        super::blurhash::compute_blurhash(&r_list, &g_list, &b_list, w_usize, h_usize, 4, 3);

    AnalyzeResult {
        width,
        height,
        aspect_ratio,
        block_alignment,
        mean_y: round6(mean_y),
        entropy_y: round6(entropy_y),
        entropy_residual_y: round6(entropy_residual_y),
        spatial_information: round6(spatial_information),
        gradient_energy: round6(gradient_energy),
        laplacian_variance: round6(laplacian_variance),
        color_variance: ColorVariance {
            var_r: round6(var_r),
            var_g: round6(var_g),
            var_b: round6(var_b),
            var_sum: round6(var_sum),
        },
        unique_colors,
        alpha: AlphaMetrics {
            has_alpha,
            sparsity: round6(alpha_sparsity),
            binarity: round6(alpha_binarity),
        },
        adequacy_420: Adequacy420 {
            chroma_gradient_energy: round6(chroma_gradient_energy),
            chroma_gradient_ratio: round6(chroma_gradient_ratio),
            mse_cb: round6(mse_cb),
            mse_cr: round6(mse_cr),
            mse_chroma: round6(mse_chroma),
        },
        flat_area: round6(flat_area),
        dominant_color: DominantColor {
            dominant_rgb,
            dominant_bin,
            mean_rgb: [round6(mean_r), round6(mean_g), round6(mean_b)],
        },
        phash: phash_str,
        blurhash: blurhash_str,
    }
}
