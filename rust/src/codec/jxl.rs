// rust/src/codec/jxl.rs
// Adaptador do codec JPEG XL puro:
// Encode: jxl-encoder
// Decode: jxl-oxide

use super::{checked_len, params as contract, CodecError, CodecMode, EncodeParams};
use crate::pam::PamImage;
use std::io::Cursor;

pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    let effort = contract::jxl_effort(params.effort);
    let layout = if pam.depth == 4 {
        jxl_encoder::PixelLayout::Rgba8
    } else {
        jxl_encoder::PixelLayout::Rgb8
    };

    match params.mode {
        CodecMode::Lossless => {
            let config = jxl_encoder::LosslessConfig::new().with_effort(effort);

            let out = config
                .encode(&pam.data, pam.width, pam.height, layout)
                .map_err(|e| CodecError::Encode(format!("{:?}", e.decompose().0)))?;

            Ok(out)
        }
        CodecMode::Lossy => {
            let distance = contract::jxl_distance(params.quality);
            let config = jxl_encoder::LossyConfig::new(distance).with_effort(effort);

            let out = config
                .encode(&pam.data, pam.width, pam.height, layout)
                .map_err(|e| CodecError::Encode(format!("{:?}", e.decompose().0)))?;

            Ok(out)
        }
    }
}

pub fn decode(data: &[u8]) -> Result<PamImage, CodecError> {
    let image = jxl_oxide::JxlImage::builder()
        .read(Cursor::new(data))
        .map_err(|e| CodecError::Decode(format!("{e:?}")))?;

    let render = image
        .render_frame(0)
        .map_err(|e| CodecError::Decode(format!("{e:?}")))?;

    let mut stream = render.stream();
    let width = stream.width();
    let height = stream.height();
    let channels = stream.channels();

    let mut buf = vec![0u8; checked_len(width, height, channels)?];
    stream.write_to_buffer(&mut buf);

    let decode_err = |e: crate::pam::PamError| CodecError::Decode(e.to_string());
    match channels {
        // Tons de cinza viram R = G = B, como no engine Go.
        1 => {
            let rgb = buf.iter().flat_map(|&g| [g, g, g]).collect();
            PamImage::new_rgb(width, height, rgb).map_err(decode_err)
        }
        2 => {
            let rgba = buf
                .chunks_exact(2)
                .flat_map(|ga| [ga[0], ga[0], ga[0], ga[1]])
                .collect();
            PamImage::new_rgba(width, height, rgba).map_err(decode_err)
        }
        3 => PamImage::new_rgb(width, height, buf).map_err(decode_err),
        4 => PamImage::new_rgba(width, height, buf).map_err(decode_err),
        other => Err(CodecError::UnsupportedFormat(format!(
            "JXL com {other} canais por pixel"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::codec::ImageFormat;
    use std::path::PathBuf;

    const MODULAR_GROUP_DIM: u32 = 256;

    fn load_corpus_image(name: &str) -> PamImage {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .join("harness/fixtures/corpus")
            .join(format!("{name}.pam"));
        let bytes = std::fs::read(&path).unwrap_or_else(|e| panic!("falha ao ler {path:?}: {e}"));
        PamImage::parse(&bytes).expect("falha ao parsear PAM do corpus")
    }

    fn corpus() -> impl Iterator<Item = (&'static str, PamImage)> {
        ["photo", "screenshot", "illustration", "alpha"]
            .into_iter()
            .map(|name| {
                let pam = load_corpus_image(name);
                assert!(
                    pam.width > MODULAR_GROUP_DIM && pam.height > MODULAR_GROUP_DIM,
                    "{name} deve ocupar mais de um grupo modular"
                );
                (name, pam)
            })
    }

    /// Todos os `effort` do contrato (1..=10, que o contrato mapeia para JXL 1..=7).
    #[test]
    fn test_lossless_roundtrip_is_exact_on_multi_group_images() {
        for (name, pam) in corpus() {
            for effort in contract::MIN_EFFORT..=contract::MAX_EFFORT {
                let params = EncodeParams {
                    format: ImageFormat::Jxl,
                    mode: CodecMode::Lossless,
                    quality: 100,
                    effort,
                };
                let encoded = encode(&pam, &params)
                    .unwrap_or_else(|e| panic!("encode falhou em {name} effort {effort}: {e}"));
                let decoded = decode(&encoded)
                    .unwrap_or_else(|e| panic!("decode falhou em {name} effort {effort}: {e}"));

                assert_eq!(
                    decoded.data, pam.data,
                    "pixels divergem em {name} effort {effort}"
                );
            }
        }
    }

    /// Maior `effort` do jxl-encoder 0.3.1 que escreve streams válidos. Medido no corpus: o 8 decodifica
    /// bit a bit no jxl-oxide (com o guard do vendor) e no libjxl; os efforts 9 e 10 escrevem streams que
    /// o próprio libjxl recusa ("Generic Error" em photo, screenshot e illustration), e na imagem alpha
    /// o encode não termina em 180 s. O contrato limita o JXL a 7, abaixo disso.
    const LAST_VALID_ENCODER_EFFORT: u8 = 8;

    #[test]
    fn test_lossless_roundtrip_is_exact_at_the_highest_valid_encoder_effort() {
        for (name, pam) in corpus() {
            let layout = if pam.depth == 4 {
                jxl_encoder::PixelLayout::Rgba8
            } else {
                jxl_encoder::PixelLayout::Rgb8
            };
            let encoded = jxl_encoder::LosslessConfig::new()
                .with_effort(LAST_VALID_ENCODER_EFFORT)
                .encode(&pam.data, pam.width, pam.height, layout)
                .unwrap_or_else(|e| panic!("encode falhou em {name}: {:?}", e.decompose().0));
            let decoded =
                decode(&encoded).unwrap_or_else(|e| panic!("decode falhou em {name}: {e}"));

            assert_eq!(decoded.data, pam.data, "pixels divergem em {name}");
        }
    }

    /// Guarda do teto do contrato: subir o `effort` máximo do JXL para 9 ou mais exporia os usuários aos
    /// streams inválidos descritos acima.
    #[test]
    fn test_contract_never_reaches_the_broken_encoder_efforts() {
        let highest = (contract::MIN_EFFORT..=contract::MAX_EFFORT)
            .map(contract::jxl_effort)
            .max()
            .unwrap();
        assert!(
            highest <= LAST_VALID_ENCODER_EFFORT,
            "o contrato chega ao effort {highest} do jxl-encoder; os efforts 9 e 10 escrevem streams inválidos"
        );
    }
}
