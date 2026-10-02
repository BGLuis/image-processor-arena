// rust/src/analyze/blurhash.rs
// Implementação estrita e determinística do algoritmo Wolt BlurHash (4x3 componentes):
// - Conversão sRGB -> Linear
// - Projeção em cossenos com normalização norm (1.0 para DC, 2.0 para AC)
// - Linear -> sRGB para o componente DC (24-bit RGB -> 4 caracteres Base83)
// - Quantização AC não-linear (sign_pow com exp 0.5) e escala quant_max
// - Codificação exata de 28 caracteres Base83

use std::f64::consts::PI;

const BLURHASH_CHARS: &[u8] =
    b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~";

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

/// Tabela de cossenos `cos(PI * k * n / len)` para k em 0..comps e n em 0..len. A expressão é a
/// mesma que o laço interno avaliava pixel a pixel, então os valores são idênticos; o Go monta
/// as mesmas tabelas, e nenhum dos dois engines chama `cos` por pixel.
fn cosine_table(comps: usize, len: usize) -> Vec<Vec<f64>> {
    (0..comps)
        .map(|k| {
            (0..len)
                .map(|n| (PI * (k as f64) * (n as f64) / (len as f64)).cos())
                .collect()
        })
        .collect()
}

pub fn compute_blurhash(
    r_list: &[u8],
    g_list: &[u8],
    b_list: &[u8],
    width: usize,
    height: usize,
    x_comp: usize,
    y_comp: usize,
) -> String {
    // sRGB -> linear só tem 256 entradas; o `powf` roda 256 vezes, não 3 * 12 * N.
    let linear: [f64; 256] = std::array::from_fn(|v| srgb_to_linear(v as u8));
    let cos_x = cosine_table(x_comp, width);
    let cos_y = cosine_table(y_comp, height);

    let mut factors = Vec::with_capacity(y_comp);

    for (y, cos_y_row) in cos_y.iter().enumerate() {
        let mut row = Vec::with_capacity(x_comp);
        for (x, cos_x_row) in cos_x.iter().enumerate() {
            let norm = if x == 0 && y == 0 { 1.0f64 } else { 2.0f64 };
            let mut r_acc = 0.0f64;
            let mut g_acc = 0.0f64;
            let mut b_acc = 0.0f64;

            for (py, &cy) in cos_y_row.iter().enumerate() {
                let row_offset = py * width;

                for (px, &cx) in cos_x_row.iter().enumerate() {
                    let basis = cx * cy;
                    let idx = row_offset + px;
                    r_acc += basis * linear[r_list[idx] as usize];
                    g_acc += basis * linear[g_list[idx] as usize];
                    b_acc += basis * linear[b_list[idx] as usize];
                }
            }

            let scale = norm / ((width * height) as f64);
            row.push([r_acc * scale, g_acc * scale, b_acc * scale]);
        }
        factors.push(row);
    }

    let dc = factors[0][0];
    let mut ac = Vec::new();
    for (y, row) in factors.iter().enumerate() {
        for (x, &component) in row.iter().enumerate() {
            if x != 0 || y != 0 {
                ac.push(component);
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
        let qr = (0.0f64).max((18.0f64).min((sign_pow(comp[0] / max_val, 0.5) * 9.0 + 9.5).floor()))
            as u32;
        let qg = (0.0f64).max((18.0f64).min((sign_pow(comp[1] / max_val, 0.5) * 9.0 + 9.5).floor()))
            as u32;
        let qb = (0.0f64).max((18.0f64).min((sign_pow(comp[2] / max_val, 0.5) * 9.0 + 9.5).floor()))
            as u32;
        let val = qr * 361 + qg * 19 + qb;
        result.push_str(&encode_base83(val, 2));
    }

    result
}
