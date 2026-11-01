// rust/src/codec/webp.rs
// Adaptador do codec WebP puro:
// Lossy encode: zenwebp
// Lossless encode: image-webp
// Decode: image-webp

use super::{check_side, checked_len, params as contract, CodecError, CodecMode, EncodeParams};
use crate::pam::PamImage;
use std::io::Cursor;

pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    #[cfg(feature = "hybrid")]
    if matches!(
        params.implementation.as_deref(),
        Some("hybrid") | Some("ffi")
    ) {
        return super::hybrid::webp_encode(pam, params);
    }

    if matches!(
        params.implementation.as_deref(),
        Some("image-rs") | Some("image")
    ) {
        check_side(pam, "WebP", super::WEBP_MAX_SIDE)?;
        if params.mode == CodecMode::Lossy {
            return Err(CodecError::UnsupportedFormat(
                "image-rs WebPEncoder suporta apenas lossless".into(),
            ));
        }
        use image::codecs::webp::WebPEncoder;
        use image::ImageEncoder;
        let mut out = Vec::new();
        let encoder = WebPEncoder::new_lossless(&mut out);
        let color = if pam.depth == 4 {
            image::ExtendedColorType::Rgba8
        } else {
            image::ExtendedColorType::Rgb8
        };
        encoder
            .write_image(&pam.data, pam.width, pam.height, color)
            .map_err(|e| CodecError::Encode(e.to_string()))?;
        return Ok(out);
    }

    check_side(pam, "WebP", super::WEBP_MAX_SIDE)?;
    match params.mode {
        CodecMode::Lossy => {
            let quality = params.quality.clamp(1, 100) as f32;
            let method = contract::webp_method(params.effort);
            let config = zenwebp::EncoderConfig::new_lossy()
                .with_quality(quality)
                .with_method(method);

            let color = if pam.depth == 4 {
                zenwebp::PixelLayout::Rgba8
            } else {
                zenwebp::PixelLayout::Rgb8
            };

            let req = zenwebp::EncodeRequest::new(&config, &pam.data, color, pam.width, pam.height);
            req.encode()
                .map_err(|e| CodecError::Encode(format!("{e:?}")))
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

pub fn decode(data: &[u8], implementation: Option<&str>) -> Result<PamImage, CodecError> {
    #[cfg(feature = "hybrid")]
    if matches!(implementation, Some("hybrid") | Some("ffi")) {
        return super::hybrid::webp_decode(data);
    }

    if matches!(implementation, Some("image-rs") | Some("image")) {
        use image::codecs::webp::WebPDecoder;
        use image::ImageDecoder;
        let decoder =
            WebPDecoder::new(Cursor::new(data)).map_err(|e| CodecError::Decode(e.to_string()))?;
        let (width, height) = decoder.dimensions();
        let has_alpha = decoder.color_type().has_alpha();
        let total_bytes = checked_len(width, height, if has_alpha { 4 } else { 3 })?;
        let mut buf = vec![0u8; total_bytes];
        decoder
            .read_image(&mut buf)
            .map_err(|e| CodecError::Decode(e.to_string()))?;
        let decode_err = |e: crate::pam::PamError| CodecError::Decode(e.to_string());
        return if has_alpha {
            PamImage::new_rgba(width, height, buf).map_err(decode_err)
        } else {
            PamImage::new_rgb(width, height, buf).map_err(decode_err)
        };
    }

    let mut decoder = image_webp::WebPDecoder::new(Cursor::new(data))
        .map_err(|e| CodecError::Decode(e.to_string()))?;

    // Cada biblioteca compõe os quadros de um jeito (o blend do image-webp erra por um nível),
    // então não existe "primeiro quadro" portável: os dois engines recusam WebP animado.
    if decoder.is_animated() {
        return Err(CodecError::Decode(
            "WebP animado não é suportado".to_string(),
        ));
    }

    let (width, height) = decoder.dimensions();
    let has_alpha = decoder.has_alpha();
    let total_bytes = checked_len(width, height, if has_alpha { 4 } else { 3 })?;

    let mut buf = vec![0u8; total_bytes];
    decoder
        .read_image(&mut buf)
        .map_err(|e| CodecError::Decode(e.to_string()))?;

    if has_alpha {
        PamImage::new_rgba(width, height, buf).map_err(|e| CodecError::Decode(e.to_string()))
    } else {
        PamImage::new_rgb(width, height, buf).map_err(|e| CodecError::Decode(e.to_string()))
    }
}
