// rust/src/analyze/blurhash.rs
// Implementação estrita e determinística do algoritmo Wolt BlurHash (4x3 componentes):
// - Conversão sRGB -> Linear
// - Projeção em cossenos com normalização norm (1.0 para DC, 2.0 para AC)
// - Linear -> sRGB para o componente DC (24-bit RGB -> 4 caracteres Base83)
// - Quantização AC não-linear (sign_pow com exp 0.5) e escala quant_max
// - Codificação exata de 28 caracteres Base83

use std::f64::consts::PI;

const BLURHASH_CHARS: &[u8] = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~";

fn srgb_to_linear(value: u8) -> f64 {
    let v = value as f64 / 255.0;
    if v <= 0.04045 {
        v / 12.92
    } else {
        ((v + 0.055) / 1.055).powf(2.4)
    }
}

fn linear_to_srgb(value: f64) -> u32 {
    let v = 0.0f64.max(1.0f64.min(value));
    if v <= 0.0031308 {
        (v * 12.92 * 255.0 + 0.5) as u32
    } else {
        ((1.055 * v.powf(1.0 / 2.4) - 0.055) * 255.0 + 0.5) as u32
    }
}

fn sign_pow(val: f64, exp: f64) -> f64 {
    val.abs().powf(exp).copysign(val)
}

fn encode_base83(value: u32, length: usize) -> String {
    let mut divisor = 83u32.pow((length - 1) as u32);
    let mut res = Vec::with_capacity(length);
    for _ in 0..length {
        let digit = (value / divisor) % 83;
        divisor /= 83;
        res.push(BLURHASH_CHARS[digit as usize]);
    }
    String::from_utf8(res).unwrap()
}

pub fn compute_blurhash(
    rgb_bytes: &[u8],
    width: usize,
    height: usize,
    x_comp: usize,
    y_comp: usize,
) -> String {
    let mut factors = Vec::with_capacity(y_comp);

    for y in 0..y_comp {
        let mut row = Vec::with_capacity(x_comp);
        for x in 0..x_comp {
            let norm = if x == 0 && y == 0 { 1.0f64 } else { 2.0f64 };
            let mut r_acc = 0.0f64;
            let mut g_acc = 0.0f64;
            let mut b_acc = 0.0f64;

            for py in 0..height {
                let cos_y = (PI * (y as f64) * (py as f64) / (height as f64)).cos();
                let row_offset = py * width * 3;

                for px in 0..width {
                    let basis = (PI * (x as f64) * (px as f64) / (width as f64)).cos() * cos_y;
                    let idx = row_offset + px * 3;
                    r_acc += basis * srgb_to_linear(rgb_bytes[idx]);
                    g_acc += basis * srgb_to_linear(rgb_bytes[idx + 1]);
                    b_acc += basis * srgb_to_linear(rgb_bytes[idx + 2]);
                }
            }

            let scale = norm / ((width * height) as f64);
            row.push([r_acc * scale, g_acc * scale, b_acc * scale]);
        }
        factors.push(row);
    }

    let dc = factors[0][0];
    let mut ac = Vec::new();
    for y in 0..y_comp {
        for x in 0..x_comp {
            if x != 0 || y != 0 {
                ac.push(factors[y][x]);
            }
        }
    }

    let size_flag = ((x_comp - 1) + (y_comp - 1) * 9) as u32;
    let mut result = String::with_capacity(28);
    result.push_str(&encode_base83(size_flag, 1));

    let max_val: f64;
    if !ac.is_empty() {
        let mut actual_max = 0.0f64;
        for comp in &ac {
            for &ch in comp {
                if ch.abs() > actual_max {
                    actual_max = ch.abs();
                }
            }
        }
        let quant_max = (0.0f64).max((82.0f64).min((actual_max * 166.0 - 0.5).floor())) as u32;
        max_val = ((quant_max + 1) as f64) / 166.0;
        result.push_str(&encode_base83(quant_max, 1));
    } else {
        max_val = 1.0;
        result.push_str(&encode_base83(0, 1));
    }

    // DC component (24-bit sRGB)
    let dc_r = linear_to_srgb(dc[0]);
    let dc_g = linear_to_srgb(dc[1]);
    let dc_b = linear_to_srgb(dc[2]);
    let dc_val = (dc_r << 16) + (dc_g << 8) + dc_b;
    result.push_str(&encode_base83(dc_val, 4));

    // AC components
    for comp in ac {
        let qr = (0.0f64).max((18.0f64).min((sign_pow(comp[0] / max_val, 0.5) * 9.0 + 9.5).floor())) as u32;
        let qg = (0.0f64).max((18.0f64).min((sign_pow(comp[1] / max_val, 0.5) * 9.0 + 9.5).floor())) as u32;
        let qb = (0.0f64).max((18.0f64).min((sign_pow(comp[2] / max_val, 0.5) * 9.0 + 9.5).floor())) as u32;
        let val = qr * 361 + qg * 19 + qb;
        result.push_str(&encode_base83(val, 2));
    }

    result
}
