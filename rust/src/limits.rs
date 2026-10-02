// rust/src/limits.rs
// Limites de requisição compartilhados com o servidor Go (tabela [limits] de arena.toml).
// Os dois servidores aplicam os mesmos valores e aceitam as mesmas variáveis de ambiente.

use std::sync::atomic::{AtomicUsize, Ordering};

pub const ENV_MAX_BODY_BYTES: &str = "ARENA_MAX_BODY_BYTES";
pub const ENV_MAX_PIXELS: &str = "ARENA_MAX_PIXELS";

pub const DEFAULT_MAX_BODY_BYTES: usize = 268_435_456;
pub const DEFAULT_MAX_PIXELS: usize = 40_000_000;

static MAX_PIXELS: AtomicUsize = AtomicUsize::new(DEFAULT_MAX_PIXELS);

/// Teto de pixels aplicado pelo parser PAM e pelos decoders. O servidor e o batch o fixam uma
/// única vez na partida; o valor padrão vale em testes e em quem usa a biblioteca diretamente.
pub fn max_pixels() -> usize {
    MAX_PIXELS.load(Ordering::Relaxed)
}

pub fn set_max_pixels(value: usize) {
    MAX_PIXELS.store(value, Ordering::Relaxed);
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Limits {
    pub max_body_bytes: usize,
    pub max_pixels: usize,
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            max_body_bytes: DEFAULT_MAX_BODY_BYTES,
            max_pixels: DEFAULT_MAX_PIXELS,
        }
    }
}

fn positive(name: &str, raw: Option<String>, default: usize) -> Result<usize, String> {
    let Some(raw) = raw.filter(|s| !s.is_empty()) else {
        return Ok(default);
    };
    raw.parse::<usize>()
        .ok()
        .filter(|v| *v > 0)
        .ok_or_else(|| format!("{name} deve ser um inteiro positivo, recebido '{raw}'"))
}

impl Limits {
    /// Lê os limites por uma função de consulta (variáveis de ambiente em produção).
    pub fn from_lookup(get: impl Fn(&str) -> Option<String>) -> Result<Self, String> {
        Ok(Self {
            max_body_bytes: positive(
                ENV_MAX_BODY_BYTES,
                get(ENV_MAX_BODY_BYTES),
                DEFAULT_MAX_BODY_BYTES,
            )?,
            max_pixels: positive(ENV_MAX_PIXELS, get(ENV_MAX_PIXELS), DEFAULT_MAX_PIXELS)?,
        })
    }

    pub fn from_env() -> Result<Self, String> {
        Self::from_lookup(|key| std::env::var(key).ok())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::fs;

    fn lookup(vars: &[(&str, &str)]) -> impl Fn(&str) -> Option<String> {
        let map: HashMap<String, String> = vars
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        move |key| map.get(key).cloned()
    }

    #[test]
    fn defaults_apply_when_unset_or_empty() {
        assert_eq!(Limits::from_lookup(lookup(&[])), Ok(Limits::default()));
        let empty = lookup(&[(ENV_MAX_BODY_BYTES, ""), (ENV_MAX_PIXELS, "")]);
        assert_eq!(Limits::from_lookup(empty), Ok(Limits::default()));
    }

    #[test]
    fn overrides_are_read() {
        let got = Limits::from_lookup(lookup(&[
            (ENV_MAX_BODY_BYTES, "1024"),
            (ENV_MAX_PIXELS, "256"),
        ]));
        assert_eq!(
            got,
            Ok(Limits {
                max_body_bytes: 1024,
                max_pixels: 256
            })
        );
    }

    #[test]
    fn invalid_values_are_rejected() {
        for (key, value) in [
            (ENV_MAX_BODY_BYTES, "0"),
            (ENV_MAX_BODY_BYTES, "-1"),
            (ENV_MAX_BODY_BYTES, "lots"),
            (ENV_MAX_PIXELS, "0"),
            (ENV_MAX_PIXELS, "1.5"),
        ] {
            assert!(
                Limits::from_lookup(lookup(&[(key, value)])).is_err(),
                "{key}={value}"
            );
        }
    }

    /// Lê a tabela [limits] de arena.toml, o contrato compartilhado com o servidor Go.
    #[test]
    fn defaults_match_arena_toml() {
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../arena.toml");
        let raw = fs::read_to_string(path).expect("arena.toml legível");
        let mut in_limits = false;
        let mut found = HashMap::new();
        for line in raw.lines().map(str::trim) {
            if line.starts_with('[') {
                in_limits = line == "[limits]";
                continue;
            }
            if let (true, false, Some((key, value))) =
                (in_limits, line.starts_with('#'), line.split_once('='))
            {
                found.insert(key.trim().to_string(), value.trim().to_string());
            }
        }
        assert_eq!(
            found["max_body_bytes"],
            DEFAULT_MAX_BODY_BYTES.to_string(),
            "max_body_bytes diverge de arena.toml"
        );
        assert_eq!(
            found["max_pixels"],
            DEFAULT_MAX_PIXELS.to_string(),
            "max_pixels diverge de arena.toml"
        );
    }
}
