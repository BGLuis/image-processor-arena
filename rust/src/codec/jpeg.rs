// rust/src/codec/jpeg.rs
// Adaptador do codec JPEG:
// Encode: jpeg-encoder
// Decode: zune-jpeg

use super::{check_side, CodecError, EncodeParams, JPEG_MAX_SIDE};
use crate::pam::PamImage;
use std::io::Cursor;

pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    check_side(pam, "JPEG", JPEG_MAX_SIDE)?;
    // check_side garante que cabem em u16; a conversão checada impede um truncamento silencioso.
    let (width, height) = match (u16::try_from(pam.width), u16::try_from(pam.height)) {
        (Ok(w), Ok(h)) => (w, h),
        _ => {
            return Err(CodecError::InvalidInput(format!(
                "JPEG suporta no máximo {JPEG_MAX_SIDE} pixels por lado, recebido {}x{}",
                pam.width, pam.height
            )))
        }
    };

    let mut out = Vec::new();
    let quality = params.quality.clamp(1, 100);
    let mut encoder = jpeg_encoder::Encoder::new(&mut out, quality);
    // O default do jpeg-encoder passa a 4:4:4 em q >= 90; o Go sempre grava 4:2:0.
    encoder.set_sampling_factor(jpeg_encoder::SamplingFactor::F_2_2);

    // JPEG baseline não suporta canal alpha nativo
    if pam.depth == 4 {
        let rgb_data = pam.to_rgb_bytes();
        encoder
            .encode(&rgb_data, width, height, jpeg_encoder::ColorType::Rgb)
            .map_err(|e| CodecError::Encode(e.to_string()))?;
    } else {
        encoder
            .encode(&pam.data, width, height, jpeg_encoder::ColorType::Rgb)
            .map_err(|e| CodecError::Encode(e.to_string()))?;
    }

    Ok(out)
}

pub fn decode(data: &[u8]) -> Result<PamImage, CodecError> {
    let mut decoder = zune_jpeg::JpegDecoder::new(Cursor::new(data));
    let pixels = decoder
        .decode()
        .map_err(|e| CodecError::Decode(format!("{e:?}")))?;
    let (width, height) = decoder
        .dimensions()
        .ok_or_else(|| CodecError::Decode("Dimensões JPEG desconhecidas".to_string()))?;

    PamImage::new_rgb(width as u32, height as u32, pixels)
        .map_err(|e| CodecError::Decode(e.to_string()))
}
