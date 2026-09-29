// rust/src/codec/jxl.rs
// Adaptador do codec JPEG XL puro:
// Encode: jxl-encoder
// Decode: jxl-oxide

use super::{CodecError, CodecMode, EncodeParams};
use crate::pam::PamImage;
use std::io::Cursor;

pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    let effort = params.effort.clamp(1, 10);
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
            let quality = params.quality.clamp(1, 100) as f32;
            let distance = jxl_encoder::quality_to_distance(quality);
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

    let mut buf = vec![0u8; (width * height * channels) as usize];
    stream.write_to_buffer(&mut buf);

    if channels >= 4 {
        PamImage::new_rgba(width, height, buf).map_err(|e| CodecError::Decode(e.to_string()))
    } else {
        PamImage::new_rgb(width, height, buf).map_err(|e| CodecError::Decode(e.to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::codec::ImageFormat;
    use std::path::PathBuf;

    const MAX_TESTED_EFFORT: u8 = 7;
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

    #[test]
    fn test_lossless_roundtrip_is_exact_on_multi_group_images() {
        for name in ["photo", "screenshot", "illustration", "alpha"] {
            let pam = load_corpus_image(name);
            assert!(
                pam.width > MODULAR_GROUP_DIM && pam.height > MODULAR_GROUP_DIM,
                "{name} deve ocupar mais de um grupo modular"
            );

            for effort in 1..=MAX_TESTED_EFFORT {
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

                assert_eq!(decoded.data, pam.data, "pixels divergem em {name} effort {effort}");
            }
        }
    }
}
