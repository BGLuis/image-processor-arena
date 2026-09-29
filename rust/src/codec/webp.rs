// rust/src/codec/webp.rs
// Adaptador do codec WebP puro:
// Lossy encode: zenwebp
// Lossless encode: image-webp
// Decode: image-webp

use crate::pam::PamImage;
use super::{CodecError, CodecMode, EncodeParams};
use std::io::Cursor;

pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    match params.mode {
        CodecMode::Lossy => {
            let quality = params.quality.clamp(1, 100) as f32;
            let method = ((params.effort as u64 * 6) / 10).min(6) as u8;
            let config = zenwebp::EncoderConfig::new_lossy()
                .with_quality(quality)
                .with_method(method);

            let color = if pam.depth == 4 {
                zenwebp::PixelLayout::Rgba8
            } else {
                zenwebp::PixelLayout::Rgb8
            };

            let req = zenwebp::EncodeRequest::new(&config, &pam.data, color, pam.width, pam.height);
            req.encode().map_err(|e| CodecError::Encode(format!("{e:?}")))
        }
        CodecMode::Lossless => {
            let mut out = Vec::new();
            let encoder = image_webp::WebPEncoder::new(&mut out);

            let color_type = if pam.depth == 4 {
                image_webp::ColorType::Rgba8
            } else {
                image_webp::ColorType::Rgb8
            };

            encoder
                .encode(&pam.data, pam.width, pam.height, color_type)
                .map_err(|e| CodecError::Encode(e.to_string()))?;

            Ok(out)
        }
    }
}

pub fn decode(data: &[u8]) -> Result<PamImage, CodecError> {
    let mut decoder = image_webp::WebPDecoder::new(Cursor::new(data))
        .map_err(|e| CodecError::Decode(e.to_string()))?;

    let (width, height) = decoder.dimensions();
    let has_alpha = decoder.has_alpha();
    let depth = if has_alpha { 4 } else { 3 };
    let total_bytes = (width as usize) * (height as usize) * (depth as usize);

    let mut buf = vec![0u8; total_bytes];
    decoder.read_image(&mut buf).map_err(|e| CodecError::Decode(e.to_string()))?;

    if has_alpha {
        PamImage::new_rgba(width, height, buf).map_err(|e| CodecError::Decode(e.to_string()))
    } else {
        PamImage::new_rgb(width, height, buf).map_err(|e| CodecError::Decode(e.to_string()))
    }
}
