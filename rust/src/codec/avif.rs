// rust/src/codec/avif.rs
// Adaptador do codec AVIF puro:
// Lossy encode: ravif (sem asm)
// Lossless encode: não suportado
// Decode: zenavif (baseado em rav1d-safe)

use super::{checked_len, params as contract, u16_to_u8, CodecError, CodecMode, EncodeParams};
use crate::pam::PamImage;

pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    let speed = contract::avif_speed(params.effort);

    match params.mode {
        // zenrav1e clamps base_q_idx to at least 1, so quantizer 0 never enters AV1
        // lossless mode; the RGB it produces differs from the input.
        CodecMode::Lossless => Err(CodecError::UnsupportedFormat("avif lossless".to_string())),
        CodecMode::Lossy => {
            let quality = contract::ravif_quality(params.quality);
            let enc = ravif::Encoder::new()
                .with_quality(quality)
                .with_alpha_quality(quality)
                .with_speed(speed);

            let w = pam.width as usize;
            let h = pam.height as usize;

            if pam.depth == 4 {
                let pixels: &[rgb::RGBA8] = bytemuck::cast_slice(&pam.data);
                let img = imgref::Img::new(pixels, w, h);
                let res = enc
                    .encode_rgba(img)
                    .map_err(|e| CodecError::Encode(e.to_string()))?;
                Ok(res.avif_file)
            } else {
                let pixels: &[rgb::RGB8] = bytemuck::cast_slice(&pam.data);
                let img = imgref::Img::new(pixels, w, h);
                let res = enc
                    .encode_rgb(img)
                    .map_err(|e| CodecError::Encode(e.to_string()))?;
                Ok(res.avif_file)
            }
        }
    }
}

pub fn decode(data: &[u8]) -> Result<PamImage, CodecError> {
    let image = zenavif::decode(data).map_err(|e| CodecError::Decode(format!("{e:?}")))?;
    let width = image.width() as u32;
    let height = image.height() as u32;
    let desc = image.descriptor();

    if desc.layout_compatible(zenpixels::PixelDescriptor::RGBA8) {
        let img = image
            .try_as_imgref::<rgb::Rgba<u8>>()
            .ok_or_else(|| CodecError::Decode("Falha ao converter buffer RGBA8".to_string()))?;
        let pixels: Vec<u8> = img
            .buf()
            .iter()
            .flat_map(|px| [px.r, px.g, px.b, px.a])
            .collect();
        PamImage::new_rgba(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
    } else if desc.layout_compatible(zenpixels::PixelDescriptor::RGB8) {
        let img = image
            .try_as_imgref::<rgb::Rgb<u8>>()
            .ok_or_else(|| CodecError::Decode("Falha ao converter buffer RGB8".to_string()))?;
        let pixels: Vec<u8> = img.buf().iter().flat_map(|px| [px.r, px.g, px.b]).collect();
        PamImage::new_rgb(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
    } else if desc.layout_compatible(zenpixels::PixelDescriptor::RGB16) {
        let img = image
            .try_as_imgref::<rgb::Rgb<u16>>()
            .ok_or_else(|| CodecError::Decode("Falha ao converter buffer RGB16".to_string()))?;
        let pixels: Vec<u8> = img
            .buf()
            .iter()
            .flat_map(|px| [u16_to_u8(px.r), u16_to_u8(px.g), u16_to_u8(px.b)])
            .collect();
        PamImage::new_rgb(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
    } else if desc.layout_compatible(zenpixels::PixelDescriptor::RGBA16) {
        let img = image
            .try_as_imgref::<rgb::Rgba<u16>>()
            .ok_or_else(|| CodecError::Decode("Falha ao converter buffer RGBA16".to_string()))?;
        let pixels: Vec<u8> = img
            .buf()
            .iter()
            .flat_map(|px| {
                [
                    u16_to_u8(px.r),
                    u16_to_u8(px.g),
                    u16_to_u8(px.b),
                    u16_to_u8(px.a),
                ]
            })
            .collect();
        PamImage::new_rgba(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
    } else if desc.layout_compatible(zenpixels::PixelDescriptor::GRAY8) {
        let slice = image.as_slice();
        let mut pixels = Vec::with_capacity(checked_len(width, height, 3)?);
        for y in 0..height {
            for &g in slice.row(y) {
                pixels.push(g);
                pixels.push(g);
                pixels.push(g);
            }
        }
        PamImage::new_rgb(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
    } else {
        // Fallback tentando extrair tipos conhecidos
        if let Some(img) = image.try_as_imgref::<rgb::Rgb<u8>>() {
            let pixels: Vec<u8> = img.buf().iter().flat_map(|px| [px.r, px.g, px.b]).collect();
            PamImage::new_rgb(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
        } else if let Some(img) = image.try_as_imgref::<rgb::Rgba<u8>>() {
            let pixels: Vec<u8> = img
                .buf()
                .iter()
                .flat_map(|px| [px.r, px.g, px.b, px.a])
                .collect();
            PamImage::new_rgba(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
        } else if let Some(img) = image.try_as_imgref::<rgb::Rgb<u16>>() {
            let pixels: Vec<u8> = img
                .buf()
                .iter()
                .flat_map(|px| [u16_to_u8(px.r), u16_to_u8(px.g), u16_to_u8(px.b)])
                .collect();
            PamImage::new_rgb(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
        } else if let Some(img) = image.try_as_imgref::<rgb::Rgba<u16>>() {
            let pixels: Vec<u8> = img
                .buf()
                .iter()
                .flat_map(|px| {
                    [
                        u16_to_u8(px.r),
                        u16_to_u8(px.g),
                        u16_to_u8(px.b),
                        u16_to_u8(px.a),
                    ]
                })
                .collect();
            PamImage::new_rgba(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
        } else {
            Err(CodecError::UnsupportedFormat(format!(
                "Layout de pixels AVIF não suportado: {desc:?}"
            )))
        }
    }
}
