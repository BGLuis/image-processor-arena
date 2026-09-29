// rust/src/codec/avif.rs
// Adaptador do codec AVIF puro:
// Lossy encode: ravif (sem asm)
// Lossless encode: zenravif (quantizer = 0)
// Decode: zenavif (baseado em rav1d-safe)

use crate::pam::PamImage;
use super::{CodecError, CodecMode, EncodeParams};

pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    let speed = params.effort.clamp(1, 10);

    match params.mode {
        CodecMode::Lossless => {
            let enc = zenravif::Encoder::new()
                .with_libavif_quality(100.0) // quantizer = 0
                .with_speed(speed);

            let w = pam.width as usize;
            let h = pam.height as usize;

            if pam.depth == 4 {
                let pixels: &[rgb::RGBA8] = bytemuck::cast_slice(&pam.data);
                let img = imgref::Img::new(pixels, w, h);
                let res = enc.encode_rgba(img).map_err(|e| CodecError::Encode(e.to_string()))?;
                Ok(res.avif_file)
            } else {
                let pixels: &[rgb::RGB8] = bytemuck::cast_slice(&pam.data);
                let img = imgref::Img::new(pixels, w, h);
                let res = enc.encode_rgb(img).map_err(|e| CodecError::Encode(e.to_string()))?;
                Ok(res.avif_file)
            }
        }
        CodecMode::Lossy => {
            let enc = ravif::Encoder::new()
                .with_quality(params.quality as f32)
                .with_speed(speed);

            let w = pam.width as usize;
            let h = pam.height as usize;

            if pam.depth == 4 {
                let pixels: &[rgb::RGBA8] = bytemuck::cast_slice(&pam.data);
                let img = imgref::Img::new(pixels, w, h);
                let res = enc.encode_rgba(img).map_err(|e| CodecError::Encode(e.to_string()))?;
                Ok(res.avif_file)
            } else {
                let pixels: &[rgb::RGB8] = bytemuck::cast_slice(&pam.data);
                let img = imgref::Img::new(pixels, w, h);
                let res = enc.encode_rgb(img).map_err(|e| CodecError::Encode(e.to_string()))?;
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
        let pixels: Vec<u8> = img.buf().iter().flat_map(|px| [px.r, px.g, px.b, px.a]).collect();
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
            .flat_map(|px| [(px.r >> 8) as u8, (px.g >> 8) as u8, (px.b >> 8) as u8])
            .collect();
        PamImage::new_rgb(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
    } else if desc.layout_compatible(zenpixels::PixelDescriptor::RGBA16) {
        let img = image
            .try_as_imgref::<rgb::Rgba<u16>>()
            .ok_or_else(|| CodecError::Decode("Falha ao converter buffer RGBA16".to_string()))?;
        let pixels: Vec<u8> = img
            .buf()
            .iter()
            .flat_map(|px| [
                (px.r >> 8) as u8,
                (px.g >> 8) as u8,
                (px.b >> 8) as u8,
                (px.a >> 8) as u8,
            ])
            .collect();
        PamImage::new_rgba(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
    } else if desc.layout_compatible(zenpixels::PixelDescriptor::GRAY8) {
        let slice = image.as_slice();
        let mut pixels = Vec::with_capacity((width * height * 3) as usize);
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
            let pixels: Vec<u8> = img.buf().iter().flat_map(|px| [px.r, px.g, px.b, px.a]).collect();
            PamImage::new_rgba(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
        } else if let Some(img) = image.try_as_imgref::<rgb::Rgb<u16>>() {
            let pixels: Vec<u8> = img
                .buf()
                .iter()
                .flat_map(|px| [(px.r >> 8) as u8, (px.g >> 8) as u8, (px.b >> 8) as u8])
                .collect();
            PamImage::new_rgb(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
        } else if let Some(img) = image.try_as_imgref::<rgb::Rgba<u16>>() {
            let pixels: Vec<u8> = img
                .buf()
                .iter()
                .flat_map(|px| [
                    (px.r >> 8) as u8,
                    (px.g >> 8) as u8,
                    (px.b >> 8) as u8,
                    (px.a >> 8) as u8,
                ])
                .collect();
            PamImage::new_rgba(width, height, pixels).map_err(|e| CodecError::Decode(e.to_string()))
        } else {
            Err(CodecError::UnsupportedFormat(format!("Layout de pixels AVIF não suportado: {desc:?}")))
        }
    }
}
