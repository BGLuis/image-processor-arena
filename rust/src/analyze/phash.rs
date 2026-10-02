// rust/src/analyze/phash.rs
// Cálculo estrito e determinístico do pHash de 64 bits contra a especificação formal:
// 1. Redimensionamento 32x32 por média de área contínua sobre a luminância Y
// 2. DCT-II bidimensional para frequências baixas 8x8 com truncamento |s| < 1e-6
// 3. Exclusão do componente DC (0,0) (fixado em 0.0)
// 4. Mediana dos 64 coeficientes
// 5. Hash de 64 bits hex minúsculo com 16 caracteres

use std::f64::consts::PI;

pub fn compute_phash(y_pixels: &[u8], width: usize, height: usize) -> String {
    // 1. Redimensionamento 32x32 por média de área contínua
    let mut grid = [[0.0f64; 32]; 32];
    let sw = width as f64 / 32.0;
    let sh = height as f64 / 32.0;

    for (v, grid_row) in grid.iter_mut().enumerate() {
        let y0 = v as f64 * sh;
        let y1 = (v + 1) as f64 * sh;
        let sy_min = y0.floor() as usize;
        let sy_max = (y1.ceil() as usize).min(height);

        for (u, cell) in grid_row.iter_mut().enumerate() {
            let x0 = u as f64 * sw;
            let x1 = (u + 1) as f64 * sw;
            let sx_min = x0.floor() as usize;
            let sx_max = (x1.ceil() as usize).min(width);

            let mut total = 0.0f64;
            let mut total_weight = 0.0f64;

            for py in sy_min..sy_max {
                let py_f = py as f64;
                let wy = 0.0f64.max((py_f + 1.0).min(y1) - py_f.max(y0));
                let row_off = py * width;

                for px in sx_min..sx_max {
                    let px_f = px as f64;
                    let wx = 0.0f64.max((px_f + 1.0).min(x1) - px_f.max(x0));
                    let w = wx * wy;

                    total += (y_pixels[row_off + px] as f64) * w;
                    total_weight += w;
                }
            }

            *cell = if total_weight > 0.0 {
                total / total_weight
            } else {
                0.0
            };
        }
    }

    // 2. 2D DCT-II para submatriz 8x8 de baixas frequências. A tabela 8x32 de cossenos é
    // calculada uma vez (a expressão é a mesma de antes), em vez de ~65 mil chamadas a `cos`.
    let mut cos_tab = [[0.0f64; 32]; 8];
    for (k, row) in cos_tab.iter_mut().enumerate() {
        for (n, cell) in row.iter_mut().enumerate() {
            *cell = (PI * ((2 * n + 1) as f64) * (k as f64) / 64.0).cos();
        }
    }

    let mut d = [[0.0f64; 8]; 8];
    for (v, d_row) in d.iter_mut().enumerate() {
        for (u, cell) in d_row.iter_mut().enumerate() {
            let mut s = 0.0f64;
            for (y, grid_row) in grid.iter().enumerate() {
                let cos_y = cos_tab[v][y];
                for (x, &value) in grid_row.iter().enumerate() {
                    let cos_x = cos_tab[u][x];
                    s += value * cos_x * cos_y;
                }
            }
            if s.abs() < 1e-6 {
                s = 0.0;
            }
            *cell = s;
        }
    }

    // 3. Submatriz 8x8 excluindo DC (0,0) -> C[0] = 0.0
    let mut coeffs = Vec::with_capacity(64);
    for (v, d_row) in d.iter().enumerate() {
        for (u, &value) in d_row.iter().enumerate() {
            if u == 0 && v == 0 {
                coeffs.push(0.0);
            } else {
                coeffs.push(value);
            }
        }
    }

    // 4. Mediana dos 64 coeficientes
    let mut sorted_c = coeffs.clone();
    sorted_c.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let median = (sorted_c[31] + sorted_c[32]) / 2.0;

    // 5. Bit = coeff > median (MSB na posição 0)
    let mut hash_val: u64 = 0;
    for (i, &c) in coeffs.iter().enumerate() {
        if c > median {
            hash_val |= 1u64 << (63 - i);
        }
    }

    format!("{hash_val:016x}")
}
