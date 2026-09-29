// rust/src/codec/mod.rs
// Adaptadores de codecs puros e despacho centralizado para encode, decode e transcode.

pub mod avif;
pub mod jpeg;
pub mod jxl;
pub mod png;
pub mod webp;

use crate::pam::PamImage;
use std::fmt;
use std::str::FromStr;
use std::time::Instant;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ImageFormat {
    Png,
    Jpeg,
    Webp,
    Avif,
    Jxl,
}

impl ImageFormat {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Png => "png",
            Self::Jpeg => "jpeg",
            Self::Webp => "webp",
            Self::Avif => "avif",
            Self::Jxl => "jxl",
        }
    }

    pub fn mime_type(&self) -> &'static str {
        match self {
            Self::Png => "image/png",
            Self::Jpeg => "image/jpeg",
            Self::Webp => "image/webp",
            Self::Avif => "image/avif",
            Self::Jxl => "image/jxl",
        }
    }
}

impl FromStr for ImageFormat {
    type Err = CodecError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_ascii_lowercase().as_str() {
            "png" => Ok(Self::Png),
            "jpeg" | "jpg" => Ok(Self::Jpeg),
            "webp" => Ok(Self::Webp),
            "avif" => Ok(Self::Avif),
            "jxl" => Ok(Self::Jxl),
            _ => Err(CodecError::UnsupportedFormat(format!("Formato desconhecido: '{s}'"))),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CodecMode {
    Lossy,
    Lossless,
}

impl FromStr for CodecMode {
    type Err = CodecError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_ascii_lowercase().as_str() {
            "lossy" => Ok(Self::Lossy),
            "lossless" => Ok(Self::Lossless),
            _ => Err(CodecError::InvalidParam(format!("Modo inválido: '{s}', esperado 'lossy' ou 'lossless'"))),
        }
    }
}

#[derive(Debug, Clone)]
pub struct EncodeParams {
    pub format: ImageFormat,
    pub mode: CodecMode,
    pub quality: u8,
    pub effort: u8,
}

impl Default for EncodeParams {
    fn default() -> Self {
        Self {
            format: ImageFormat::Png,
            mode: CodecMode::Lossy,
            quality: 75,
            effort: 4,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CodecError {
    Encode(String),
    Decode(String),
    UnsupportedFormat(String),
    InvalidParam(String),
}

impl fmt::Display for CodecError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Encode(msg) => write!(f, "Erro de codificação: {msg}"),
            Self::Decode(msg) => write!(f, "Erro de decodificação: {msg}"),
            Self::UnsupportedFormat(msg) => write!(f, "Formato não suportado: {msg}"),
            Self::InvalidParam(msg) => write!(f, "Parâmetro inválido: {msg}"),
        }
    }
}

impl std::error::Error for CodecError {}

/// Codifica uma imagem PAM no formato desejado
pub fn encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    match params.format {
        ImageFormat::Png => png::encode(pam, params),
        ImageFormat::Jpeg => jpeg::encode(pam, params),
        ImageFormat::Webp => webp::encode(pam, params),
        ImageFormat::Avif => avif::encode(pam, params),
        ImageFormat::Jxl => jxl::encode(pam, params),
    }
}

/// Decodifica um arquivo compactado para imagem PAM
pub fn decode(data: &[u8], format: ImageFormat) -> Result<PamImage, CodecError> {
    match format {
        ImageFormat::Png => png::decode(data),
        ImageFormat::Jpeg => jpeg::decode(data),
        ImageFormat::Webp => webp::decode(data),
        ImageFormat::Avif => avif::decode(data),
        ImageFormat::Jxl => jxl::decode(data),
    }
}

/// Transcodifica entre dois formatos com medição nanosegundo de decode e encode
pub fn transcode(
    data: &[u8],
    from_format: ImageFormat,
    params: &EncodeParams,
) -> Result<(Vec<u8>, u128, u128), CodecError> {
    let t0 = Instant::now();
    let pam = decode(data, from_format)?;
    let decode_ns = t0.elapsed().as_nanos();

    let t1 = Instant::now();
    let encoded = encode(&pam, params)?;
    let encode_ns = t1.elapsed().as_nanos();

    Ok((encoded, decode_ns, encode_ns))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_pam(width: u32, height: u32) -> PamImage {
        let mut data = Vec::with_capacity((width * height * 3) as usize);
        for y in 0..height {
            for x in 0..width {
                data.push((x * 255 / width) as u8);
                data.push((y * 255 / height) as u8);
                data.push(128u8);
            }
        }
        PamImage::new_rgb(width, height, data).unwrap()
    }

    #[test]
    fn test_codec_roundtrip_all() {
        let pam = create_test_pam(32, 32);

        // Test PNG
        let params_png = EncodeParams {
            format: ImageFormat::Png,
            mode: CodecMode::Lossless,
            quality: 100,
            effort: 4,
        };
        let png_bytes = encode(&pam, &params_png).expect("PNG encode falhou");
        let decoded_png = decode(&png_bytes, ImageFormat::Png).expect("PNG decode falhou");
        assert_eq!(decoded_png.width, 32);
        assert_eq!(decoded_png.height, 32);
        assert_eq!(decoded_png.data, pam.data);

        // Test JPEG
        let params_jpeg = EncodeParams {
            format: ImageFormat::Jpeg,
            mode: CodecMode::Lossy,
            quality: 85,
            effort: 4,
        };
        let jpeg_bytes = encode(&pam, &params_jpeg).expect("JPEG encode falhou");
        let decoded_jpeg = decode(&jpeg_bytes, ImageFormat::Jpeg).expect("JPEG decode falhou");
        assert_eq!(decoded_jpeg.width, 32);
        assert_eq!(decoded_jpeg.height, 32);

        // Test WebP Lossless
        let params_webp_lossless = EncodeParams {
            format: ImageFormat::Webp,
            mode: CodecMode::Lossless,
            quality: 100,
            effort: 4,
        };
        let webp_lossless_bytes = encode(&pam, &params_webp_lossless).expect("WebP lossless encode falhou");
        let decoded_webp_ll = decode(&webp_lossless_bytes, ImageFormat::Webp).expect("WebP lossless decode falhou");
        assert_eq!(decoded_webp_ll.width, 32);
        assert_eq!(decoded_webp_ll.height, 32);
        assert_eq!(decoded_webp_ll.data, pam.data);

        // Test WebP Lossy
        let params_webp_lossy = EncodeParams {
            format: ImageFormat::Webp,
            mode: CodecMode::Lossy,
            quality: 80,
            effort: 4,
        };
        let webp_lossy_bytes = encode(&pam, &params_webp_lossy).expect("WebP lossy encode falhou");
        let decoded_webp_lossy = decode(&webp_lossy_bytes, ImageFormat::Webp).expect("WebP lossy decode falhou");
        assert_eq!(decoded_webp_lossy.width, 32);
        assert_eq!(decoded_webp_lossy.height, 32);

        // Test JXL Lossless
        let params_jxl = EncodeParams {
            format: ImageFormat::Jxl,
            mode: CodecMode::Lossless,
            quality: 100,
            effort: 3,
        };
        let jxl_bytes = encode(&pam, &params_jxl).expect("JXL encode falhou");
        let decoded_jxl = decode(&jxl_bytes, ImageFormat::Jxl).expect("JXL decode falhou");
        assert_eq!(decoded_jxl.width, 32);
        assert_eq!(decoded_jxl.height, 32);
        assert_eq!(decoded_jxl.data, pam.data);

        // Test AVIF Lossy
        let params_avif = EncodeParams {
            format: ImageFormat::Avif,
            mode: CodecMode::Lossy,
            quality: 60,
            effort: 10,
        };
        let avif_bytes = encode(&pam, &params_avif).expect("AVIF encode falhou");
        let decoded_avif = decode(&avif_bytes, ImageFormat::Avif).expect("AVIF decode falhou");
        assert_eq!(decoded_avif.width, 32);
        assert_eq!(decoded_avif.height, 32);
    }

    // zenrav1e nunca entra no modo lossless do AV1, então o modo é recusado em vez de
    // gerar um arquivo com perdas rotulado como lossless.
    #[test]
    fn test_avif_lossless_is_refused() {
        let pam = create_test_pam(512, 512);
        let params = EncodeParams {
            format: ImageFormat::Avif,
            mode: CodecMode::Lossless,
            quality: 100,
            effort: 4,
        };

        let result = encode(&pam, &params);

        assert!(
            matches!(result, Err(CodecError::UnsupportedFormat(_))),
            "AVIF lossless deveria ser recusado, obtido: {:?}",
            result.map(|bytes| bytes.len())
        );
    }

    #[test]
    fn test_lossless_roundtrip_is_pixel_exact_512() {
        let pam = create_test_pam(512, 512);

        for format in [ImageFormat::Png, ImageFormat::Webp] {
            let params = EncodeParams {
                format,
                mode: CodecMode::Lossless,
                quality: 100,
                effort: 4,
            };
            let bytes = encode(&pam, &params).expect("encode lossless falhou");
            let decoded = decode(&bytes, format).expect("decode lossless falhou");
            assert_eq!(decoded.data, pam.data, "{} lossless divergiu", format.as_str());
        }
    }
}
