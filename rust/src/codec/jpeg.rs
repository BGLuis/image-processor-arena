// rust/src/codec/jpeg.rs
// Adaptador do codec JPEG:
// Encode: jpeg-encoder
// Decode: zune-jpeg

use crate::pam::PamImage;
use super::{CodecError, EncodeParams};
use std::io::Cursor;

pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    let mut out = Vec::new();
    let quality = params.quality.clamp(1, 100);
    let encoder = jpeg_encoder::Encoder::new(&mut out, quality);

    // JPEG baseline não suporta canal alpha nativo
    if pam.depth == 4 {
        let rgb_data = pam.to_rgb_bytes();
        encoder
            .encode(&rgb_data, pam.width as u16, pam.height as u16, jpeg_encoder::ColorType::Rgb)
            .map_err(|e| CodecError::Encode(e.to_string()))?;
    } else {
        encoder
            .encode(&pam.data, pam.width as u16, pam.height as u16, jpeg_encoder::ColorType::Rgb)
            .map_err(|e| CodecError::Encode(e.to_string()))?;
    }

    Ok(out)
}

pub fn decode(data: &[u8]) -> Result<PamImage, CodecError> {
    let mut decoder = zune_jpeg::JpegDecoder::new(Cursor::new(data));
    let pixels = decoder.decode().map_err(|e| CodecError::Decode(format!("{e:?}")))?;
    let (width, height) = decoder.dimensions().ok_or_else(|| CodecError::Decode("Dimensões JPEG desconhecidas".to_string()))?;

    PamImage::new_rgb(width as u32, height as u32, pixels).map_err(|e| CodecError::Decode(e.to_string()))
}
