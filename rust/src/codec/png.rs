// rust/src/codec/png.rs
// Adaptador do codec PNG puro.

use super::{checked_len, params as contract, CodecError, EncodeParams};
use crate::pam::PamImage;
use std::io::Cursor;

pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    let mut out = Vec::new();
    let mut encoder = png::Encoder::new(&mut out, pam.width, pam.height);

    if pam.depth == 4 {
        encoder.set_color(png::ColorType::Rgba);
    } else {
        encoder.set_color(png::ColorType::Rgb);
    }
    encoder.set_depth(png::BitDepth::Eight);

    encoder.set_compression(contract::png_compression(params.effort));

    let mut writer = encoder
        .write_header()
        .map_err(|e| CodecError::Encode(e.to_string()))?;
    writer
        .write_image_data(&pam.data)
        .map_err(|e| CodecError::Encode(e.to_string()))?;
    drop(writer);

    Ok(out)
}

pub fn decode(data: &[u8]) -> Result<PamImage, CodecError> {
    let decoder = png::Decoder::new(Cursor::new(data));
    let mut reader = decoder
        .read_info()
        .map_err(|e| CodecError::Decode(e.to_string()))?;

    let info = reader.info();
    let width = info.width;
    let height = info.height;
    let color_type = info.color_type;
    let bit_depth = info.bit_depth;

    // O tamanho declarado no IHDR é conferido contra o teto de pixels antes de qualquer alocação.
    let max_len = checked_len(width, height, 8)?;
    let buf_size = reader.output_buffer_size().unwrap_or(max_len);
    if buf_size > max_len {
        return Err(CodecError::Decode(format!(
            "imagem de {width}x{height} excede o limite de pixels"
        )));
    }
    let mut buf = vec![0u8; buf_size];
    let output_info = reader
        .next_frame(&mut buf)
        .map_err(|e| CodecError::Decode(e.to_string()))?;
    buf.truncate(output_info.buffer_size());

    // Se o bit_depth for 16 bits, reduz para 8 bits
    if bit_depth == png::BitDepth::Sixteen {
        let mut eight_bit = Vec::with_capacity(buf.len() / 2);
        for chunk in buf.chunks_exact(2) {
            eight_bit.push(chunk[0]); // MSB
        }
        buf = eight_bit;
    }

    match color_type {
        png::ColorType::Rgb => {
            PamImage::new_rgb(width, height, buf).map_err(|e| CodecError::Decode(e.to_string()))
        }
        png::ColorType::Rgba => {
            PamImage::new_rgba(width, height, buf).map_err(|e| CodecError::Decode(e.to_string()))
        }
        png::ColorType::Grayscale => {
            let mut rgb = Vec::with_capacity((width * height * 3) as usize);
            for &g in &buf {
                rgb.push(g);
                rgb.push(g);
                rgb.push(g);
            }
            PamImage::new_rgb(width, height, rgb).map_err(|e| CodecError::Decode(e.to_string()))
        }
        png::ColorType::GrayscaleAlpha => {
            let mut rgba = Vec::with_capacity((width * height * 4) as usize);
            for chunk in buf.chunks_exact(2) {
                let g = chunk[0];
                let a = chunk[1];
                rgba.push(g);
                rgba.push(g);
                rgba.push(g);
                rgba.push(a);
            }
            PamImage::new_rgba(width, height, rgba).map_err(|e| CodecError::Decode(e.to_string()))
        }
        _ => Err(CodecError::UnsupportedFormat(format!(
            "PNG ColorType não suportado: {color_type:?}"
        ))),
    }
}
