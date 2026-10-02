// rust/tests/decoders.rs
// Decoders contra fixtures com layouts que os encoders da arena nunca produzem: PNG indexado e
// de poucos bits, PNG de 16 bits, JXL em tons de cinza e WebP animado. O gabarito é
// harness/fixtures/decoders/expected.json, o mesmo que o teste do engine Go lê.

use arena_rust::codec::{self, ImageFormat};
use serde_json::{Map, Value};
use std::path::PathBuf;
use std::str::FromStr;

fn fixtures_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("harness/fixtures/decoders")
}

fn expected() -> Map<String, Value> {
    let raw = std::fs::read_to_string(fixtures_dir().join("expected.json"))
        .expect("expected.json legível; rode harness/generators/make_decoder_fixtures.py");
    serde_json::from_str(&raw).expect("expected.json válido")
}

fn unhex(hex: &str) -> Vec<u8> {
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).expect("hex válido"))
        .collect()
}

fn field(entry: &Value, key: &str) -> u64 {
    entry[key].as_u64().unwrap_or_else(|| panic!("campo {key}"))
}

#[test]
fn decoders_match_the_expected_pixels() {
    let expected = expected();
    assert!(expected.len() >= 9, "expected.json incompleto");

    for (name, entry) in &expected {
        let path = fixtures_dir().join(name);
        let bytes = std::fs::read(&path).unwrap_or_else(|e| {
            panic!("{name}: {e}; rode o teste ignorado regenerate_decoder_fixtures")
        });
        let format = ImageFormat::from_str(entry["format"].as_str().unwrap()).unwrap();

        if entry.get("error").is_some() {
            let result = codec::decode(&bytes, format);
            assert!(result.is_err(), "{name}: deveria ser recusado");
            continue;
        }
        let pam = codec::decode(&bytes, format).unwrap_or_else(|e| panic!("{name}: {e}"));

        assert_eq!(
            (pam.width as u64, pam.height as u64, pam.depth as u64),
            (
                field(entry, "width"),
                field(entry, "height"),
                field(entry, "depth")
            ),
            "{name}: dimensões ou depth"
        );
        assert_eq!(
            pam.data,
            unhex(entry["pixels"].as_str().unwrap()),
            "{name}: pixels"
        );
    }
}
