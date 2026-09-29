// rust/src/codec/jxl.rs
// Adaptador do codec JPEG XL puro:
// Encode: jxl-encoder
// Decode: jxl-oxide

use crate::pam::PamImage;
use super::{params as contract, CodecError, CodecMode, EncodeParams};
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
            let config = jxl_encoder::LosslessConfig::new()
                .with_effort(effort);

            let out = config
                .encode(&pam.data, pam.width, pam.height, layout)
                .map_err(|e| CodecError::Encode(format!("{:?}", e.decompose().0)))?;

            Ok(out)
        }
        CodecMode::Lossy => {
            let distance = contract::jxl_distance(params.quality);
            let config = jxl_encoder::LossyConfig::new(distance)
                .with_effort(effort);

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
