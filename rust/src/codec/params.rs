// rust/src/codec/params.rs
// Contrato único de parâmetros (mode, q, effort) compartilhado com o engine Go.
// Fonte da verdade documentada: seção [params] de arena.toml.

use super::{CodecError, CodecMode, EncodeParams, ImageFormat};
use std::str::FromStr;

pub const DEFAULT_MODE: CodecMode = CodecMode::Lossy;

pub const DEFAULT_Q: u8 = 75;
pub const MIN_Q: u8 = 1;
pub const MAX_Q: u8 = 100;

pub const DEFAULT_EFFORT: u8 = 4;
pub const MIN_EFFORT: u8 = 1;
pub const MAX_EFFORT: u8 = 10;

/// effort 1..=10 mapeado em 0..=6 (interpolação linear arredondada).
/// WebP lossy usa como method (0..=6) e JXL como effort menos um (1..=7).
pub const EFFORT_STEP: [u8; 10] = [0, 1, 1, 2, 3, 3, 4, 5, 5, 6];

fn effort_step(effort: u8) -> u8 {
    EFFORT_STEP[(effort.clamp(MIN_EFFORT, MAX_EFFORT) - MIN_EFFORT) as usize]
}

pub fn webp_method(effort: u8) -> u8 {
    effort_step(effort)
}

pub fn jxl_effort(effort: u8) -> u8 {
    effort_step(effort) + 1
}

/// A escala de speed do AVIF cresce com a velocidade do encoder, a de effort com a lentidão.
pub fn avif_speed(effort: u8) -> u8 {
    MAX_EFFORT + MIN_EFFORT - effort.clamp(MIN_EFFORT, MAX_EFFORT)
}

pub fn png_compression(effort: u8) -> png::Compression {
    match effort {
        0..=2 => png::Compression::Fast,
        3..=6 => png::Compression::Balanced,
        _ => png::Compression::High,
    }
}

/// Distância Butteraugli do mapeamento nativo do gen2brain/jxl. O `quality_to_distance` do
/// jxl-encoder usa outra curva (q75 dá 1.75 contra 2.35), então a distância é calculada aqui.
pub fn jxl_distance(q: u8) -> f32 {
    let q = f32::from(q);
    if q >= 30.0 {
        0.1 + (100.0 - q) * 0.09
    } else {
        53.0 / 3000.0 * q * q - 23.0 / 20.0 * q + 25.0
    }
}

/// base_q_idx do AV1 para q, o mapeamento nativo do gav1d.
pub fn avif_qindex(q: u8) -> u8 {
    ((100 - u32::from(q)) * 255 / 100) as u8
}

/// O ravif deriva o quantizer de `quality` por uma curva própria (`quality_to_quantizer`,
/// ravif 0.13.0 av1encoder.rs), que a q75 dá índice 128 contra 63 do gav1d. Inverte a curva
/// para que os dois encoders quantizem com o mesmo índice.
pub fn ravif_quality(q: u8) -> f32 {
    let x = f32::from(avif_qindex(q)) / 255.0;
    let unit = if x < 0.468 {
        1.0 - x / 2.6
    } else if x <= 0.75 {
        (0.875 - x) * 2.0
    } else {
        1.0 - x
    };
    (unit * 100.0).clamp(1.0, 100.0)
}

fn parse_bounded(name: &str, raw: Option<&str>, default: u8, min: u8, max: u8) -> Result<u8, CodecError> {
    let Some(raw) = raw.filter(|s| !s.is_empty()) else {
        return Ok(default);
    };
    raw.parse::<i64>()
        .ok()
        .filter(|v| (i64::from(min)..=i64::from(max)).contains(v))
        .map(|v| v as u8)
        .ok_or_else(|| {
            CodecError::InvalidParam(format!("{name} deve ser um inteiro entre {min} e {max}, recebido '{raw}'"))
        })
}

fn check_range(name: &str, value: u8, min: u8, max: u8) -> Result<(), CodecError> {
    if (min..=max).contains(&value) {
        Ok(())
    } else {
        Err(CodecError::InvalidParam(format!("{name} deve ser um inteiro entre {min} e {max}, recebido {value}")))
    }
}

impl EncodeParams {
    /// Monta os parâmetros a partir dos valores textuais de uma requisição. Valor ausente ou
    /// vazio seleciona o default; valor fora do contrato é rejeitado, nunca truncado.
    pub fn parse(
        format: &str,
        mode: Option<&str>,
        q: Option<&str>,
        effort: Option<&str>,
    ) -> Result<Self, CodecError> {
        let mode = match mode.filter(|s| !s.is_empty()) {
            Some(m) => CodecMode::from_str(m)?,
            None => DEFAULT_MODE,
        };
        Ok(Self {
            format: ImageFormat::from_str(format)?,
            mode,
            quality: parse_bounded("q", q, DEFAULT_Q, MIN_Q, MAX_Q)?,
            effort: parse_bounded("effort", effort, DEFAULT_EFFORT, MIN_EFFORT, MAX_EFFORT)?,
        })
    }

    pub fn validate(&self) -> Result<(), CodecError> {
        check_range("q", self.quality, MIN_Q, MAX_Q)?;
        check_range("effort", self.effort, MIN_EFFORT, MAX_EFFORT)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    /// Lê a tabela [params] de arena.toml, o contrato compartilhado com o engine Go.
    fn arena_params() -> std::collections::HashMap<String, String> {
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../arena.toml");
        let raw = fs::read_to_string(path).expect("arena.toml legível");
        let mut values = std::collections::HashMap::new();
        let mut in_params = false;
        for line in raw.lines().map(str::trim) {
            if line.starts_with('[') {
                in_params = line == "[params]";
                continue;
            }
            if let (true, false, Some((key, value))) = (in_params, line.starts_with('#'), line.split_once('=')) {
                values.insert(key.trim().to_string(), value.trim().trim_matches('"').to_string());
            }
        }
        values
    }

    #[test]
    fn contract_matches_arena_toml() {
        let want = arena_params();
        let got = [
            ("q_default", DEFAULT_Q),
            ("q_min", MIN_Q),
            ("q_max", MAX_Q),
            ("effort_default", DEFAULT_EFFORT),
            ("effort_min", MIN_EFFORT),
            ("effort_max", MAX_EFFORT),
        ];
        for (key, value) in got {
            assert_eq!(want[key], value.to_string(), "{key} diverge de arena.toml");
        }
        assert_eq!(want["mode_default"], "lossy");
        assert_eq!(DEFAULT_MODE, CodecMode::Lossy);

        let table: Vec<u8> = want["effort_step"]
            .trim_matches(|c| c == '[' || c == ']')
            .split(',')
            .map(|cell| cell.trim().parse().unwrap())
            .collect();
        assert_eq!(table, EFFORT_STEP, "effort_step diverge de arena.toml");
    }

    #[test]
    fn parse_defaults() {
        for format in ["png", "jpeg", "webp", "avif", "jxl"] {
            let p = EncodeParams::parse(format, None, None, None).unwrap();
            assert_eq!(p.mode, CodecMode::Lossy, "{format}");
            assert_eq!(p.quality, 75, "{format}");
            assert_eq!(p.effort, 4, "{format}");
        }
    }

    #[test]
    fn parse_empty_values_select_defaults() {
        let p = EncodeParams::parse("webp", Some(""), Some(""), Some("")).unwrap();
        assert_eq!((p.mode, p.quality, p.effort), (CodecMode::Lossy, 75, 4));
    }

    #[test]
    fn parse_accepts_contract_bounds() {
        for (q, effort) in [("1", "1"), ("100", "10")] {
            assert!(EncodeParams::parse("webp", Some("lossless"), Some(q), Some(effort)).is_ok(), "q={q} effort={effort}");
        }
    }

    #[test]
    fn parse_rejects_outside_contract() {
        let bad_q = ["0", "101", "300", "-5", "abc", "7.5"];
        let bad_effort = ["0", "11", "-1", "fast"];
        for q in bad_q {
            let err = EncodeParams::parse("webp", None, Some(q), None).unwrap_err();
            assert!(matches!(err, CodecError::InvalidParam(_)), "q={q}: {err:?}");
        }
        for effort in bad_effort {
            let err = EncodeParams::parse("webp", None, None, Some(effort)).unwrap_err();
            assert!(matches!(err, CodecError::InvalidParam(_)), "effort={effort}: {err:?}");
        }
        let err = EncodeParams::parse("webp", Some("near-lossless"), None, None).unwrap_err();
        assert!(matches!(err, CodecError::InvalidParam(_)), "{err:?}");
        let err = EncodeParams::parse("bmp", None, None, None).unwrap_err();
        assert!(matches!(err, CodecError::UnsupportedFormat(_)), "{err:?}");
    }

    #[test]
    fn effort_mapping() {
        let webp_method_want = [0, 1, 1, 2, 3, 3, 4, 5, 5, 6];
        let jxl_effort_want = [1, 2, 2, 3, 4, 4, 5, 6, 6, 7];
        let avif_speed_want = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1];
        for effort in MIN_EFFORT..=MAX_EFFORT {
            let i = (effort - MIN_EFFORT) as usize;
            assert_eq!(webp_method(effort), webp_method_want[i], "webp_method({effort})");
            assert_eq!(jxl_effort(effort), jxl_effort_want[i], "jxl_effort({effort})");
            assert_eq!(avif_speed(effort), avif_speed_want[i], "avif_speed({effort})");
            let tier = match effort {
                1..=2 => "Fast",
                3..=6 => "Balanced",
                _ => "High",
            };
            assert_eq!(format!("{:?}", png_compression(effort)), tier, "png_compression({effort})");
        }
    }

    #[test]
    fn jxl_distance_matches_the_go_encoder() {
        assert!((jxl_distance(75) - 2.35).abs() < 1e-5);
        assert!((jxl_distance(100) - 0.1).abs() < 1e-5);
        assert!((jxl_distance(30) - 6.4).abs() < 1e-5);
        assert!((jxl_distance(1) - 23.8).abs() < 0.1);
    }

    /// Cópia do `quality_to_quantizer` privado do ravif 0.13.0, para provar a inversão.
    fn ravif_quantizer(quality: f32) -> u8 {
        let q = quality / 100.0;
        let x = if q >= 0.82 {
            (1.0 - q) * 2.6
        } else if q > 0.25 {
            q.mul_add(-0.5, 1.0 - 0.125)
        } else {
            1.0 - q
        };
        (x * 255.0).round() as u8
    }

    #[test]
    fn ravif_quality_reproduces_the_gav1d_quantizer() {
        assert_eq!(avif_qindex(75), 63);
        assert_eq!(avif_qindex(100), 0);
        assert_eq!(avif_qindex(1), 252);
        for q in MIN_Q..=MAX_Q {
            let ravif_q = ravif_quality(q);
            assert!((1.0..=100.0).contains(&ravif_q), "q={q} gera quality {ravif_q} fora da faixa do ravif");
            assert_eq!(ravif_quantizer(ravif_q), avif_qindex(q), "q={q}");
        }
    }
}
