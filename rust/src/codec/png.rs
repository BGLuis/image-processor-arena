// rust/src/codec/png.rs
// Adaptador do codec PNG puro.

use super::{checked_len, params as contract, u16_to_u8, CodecError, EncodeParams};
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
    let mut decoder = png::Decoder::new(Cursor::new(data));
    // EXPAND leva PNG indexado e de 1, 2 ou 4 bits a 8 bits por canal e converte tRNS em alpha,
    // como o image/png do Go. Os 16 bits ficam como estão e são reduzidos abaixo, com arredondamento.
    decoder.set_transformations(png::Transformations::EXPAND);
    let mut reader = decoder
        .read_info()
        .map_err(|e| CodecError::Decode(e.to_string()))?;

    let (width, height) = {
        let info = reader.info();
        (info.width, info.height)
    };
    let (color_type, bit_depth) = reader.output_color_type();

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

    if bit_depth == png::BitDepth::Sixteen {
        buf = buf
            .chunks_exact(2)
            .map(|pair| u16_to_u8(u16::from_be_bytes([pair[0], pair[1]])))
            .collect();
    }

    let decode_err = |e: crate::pam::PamError| CodecError::Decode(e.to_string());
    match color_type {
        png::ColorType::Rgb => PamImage::new_rgb(width, height, buf).map_err(decode_err),
        png::ColorType::Rgba => PamImage::new_rgba(width, height, buf).map_err(decode_err),
        png::ColorType::Grayscale => {
            let rgb = buf.iter().flat_map(|&g| [g, g, g]).collect();
            PamImage::new_rgb(width, height, rgb).map_err(decode_err)
        }
        png::ColorType::GrayscaleAlpha => {
            let rgba = buf
                .chunks_exact(2)
                .flat_map(|ga| [ga[0], ga[0], ga[0], ga[1]])
                .collect();
            PamImage::new_rgba(width, height, rgba).map_err(decode_err)
        }
        png::ColorType::Indexed => Err(CodecError::UnsupportedFormat(
            "PNG indexado não foi expandido pelo decoder".to_string(),
        )),
    }
}
