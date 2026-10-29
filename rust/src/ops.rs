// rust/src/ops.rs
// Implementação de operações sobre matrizes PAM: resize e filtros de convolução.

use crate::pam::{PamError, PamImage};
use fast_image_resize::images::Image as FirImage;
use fast_image_resize::{FilterType as FirFilter, PixelType, ResizeAlg, ResizeOptions, Resizer};
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OpError {
    InvalidParam(String),
    ProcessError(String),
    Pam(PamError),
}

impl fmt::Display for OpError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidParam(s) => write!(f, "Parâmetro inválido: {s}"),
            Self::ProcessError(s) => write!(f, "Erro no processamento: {s}"),
            Self::Pam(e) => write!(f, "Erro de PAM: {e}"),
        }
    }
}

impl std::error::Error for OpError {}

impl From<PamError> for OpError {
    fn from(err: PamError) -> Self {
        Self::Pam(err)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResampleFilter {
    Lanczos3,
    CatmullRom,
    Bilinear,
    Nearest,
}

impl ResampleFilter {
    pub fn parse(s: &str) -> Result<Self, OpError> {
        match s.to_ascii_lowercase().as_str() {
            "lanczos3" | "lanczos" => Ok(Self::Lanczos3),
            "catmullrom" | "bicubic" => Ok(Self::CatmullRom),
            "bilinear" | "linear" => Ok(Self::Bilinear),
            "nearest" | "box" => Ok(Self::Nearest),
            _ => Err(OpError::InvalidParam(format!(
                "Filtro de resize desconhecido: '{s}'"
            ))),
        }
    }

    pub fn to_fir(self) -> FirFilter {
        match self {
            Self::Lanczos3 => FirFilter::Lanczos3,
            Self::CatmullRom => FirFilter::CatmullRom,
            Self::Bilinear => FirFilter::Bilinear,
            Self::Nearest => FirFilter::Box,
        }
    }

    pub fn to_image(self) -> image::imageops::FilterType {
        match self {
            Self::Lanczos3 => image::imageops::FilterType::Lanczos3,
            Self::CatmullRom => image::imageops::FilterType::CatmullRom,
            Self::Bilinear => image::imageops::FilterType::Triangle,
            Self::Nearest => image::imageops::FilterType::Nearest,
        }
    }
}

pub fn resize_fir(
    pam: &PamImage,
    target_w: u32,
    target_h: u32,
    filter: ResampleFilter,
) -> Result<PamImage, OpError> {
    let src_pixel_type = if pam.depth == 4 {
        PixelType::U8x4
    } else {
        PixelType::U8x3
    };

    let src_image = FirImage::from_vec_u8(pam.width, pam.height, pam.data.clone(), src_pixel_type)
        .map_err(|e| OpError::ProcessError(format!("Erro ao criar imagem FIR de entrada: {e}")))?;

    let mut dst_image = FirImage::new(target_w, target_h, src_pixel_type);

    let mut resizer = Resizer::new();
    let resize_options = ResizeOptions::new().resize_alg(ResizeAlg::Interpolation(filter.to_fir()));
    resizer
        .resize(&src_image, &mut dst_image, &resize_options)
        .map_err(|e| OpError::ProcessError(format!("Erro durante FIR resize: {e}")))?;

    let dst_data = dst_image.into_vec();
    if pam.depth == 4 {
        PamImage::new_rgba(target_w, target_h, dst_data).map_err(OpError::Pam)
    } else {
        PamImage::new_rgb(target_w, target_h, dst_data).map_err(OpError::Pam)
    }
}

pub fn resize_image(
    pam: &PamImage,
    target_w: u32,
    target_h: u32,
    filter: ResampleFilter,
) -> Result<PamImage, OpError> {
    let filter_type = filter.to_image();
    if pam.depth == 4 {
        let img = image::RgbaImage::from_raw(pam.width, pam.height, pam.data.clone())
            .ok_or_else(|| OpError::ProcessError("Buffer RGBA inválido".to_string()))?;
        let resized = image::imageops::resize(&img, target_w, target_h, filter_type);
        PamImage::new_rgba(target_w, target_h, resized.into_raw()).map_err(OpError::Pam)
    } else {
        let img = image::RgbImage::from_raw(pam.width, pam.height, pam.data.clone())
            .ok_or_else(|| OpError::ProcessError("Buffer RGB inválido".to_string()))?;
        let resized = image::imageops::resize(&img, target_w, target_h, filter_type);
        PamImage::new_rgb(target_w, target_h, resized.into_raw()).map_err(OpError::Pam)
    }
}

pub fn resize(
    pam: &PamImage,
    target_w: u32,
    target_h: u32,
    filter: ResampleFilter,
    implementation: Option<&str>,
) -> Result<PamImage, OpError> {
    match implementation.unwrap_or("fast_image_resize") {
        "fast_image_resize" | "fir" | "" => resize_fir(pam, target_w, target_h, filter),
        "image" | "imageproc" => resize_image(pam, target_w, target_h, filter),
        other => Err(OpError::InvalidParam(format!(
            "Implementação de resize desconhecida: '{other}'. Opções: fast_image_resize, image"
        ))),
    }
}

pub fn filter(
    pam: &PamImage,
    filter_name: &str,
    sigma: Option<f32>,
    _implementation: Option<&str>,
) -> Result<PamImage, OpError> {
    let s = sigma.unwrap_or(1.0);
    match filter_name.to_ascii_lowercase().as_str() {
        "blur" | "gaussian_blur" => {
            if pam.depth == 4 {
                let img = image::RgbaImage::from_raw(pam.width, pam.height, pam.data.clone())
                    .ok_or_else(|| OpError::ProcessError("Buffer RGBA inválido".to_string()))?;
                let blurred = imageproc::filter::gaussian_blur_f32(&img, s);
                PamImage::new_rgba(pam.width, pam.height, blurred.into_raw()).map_err(OpError::Pam)
            } else {
                let img = image::RgbImage::from_raw(pam.width, pam.height, pam.data.clone())
                    .ok_or_else(|| OpError::ProcessError("Buffer RGB inválido".to_string()))?;
                let blurred = imageproc::filter::gaussian_blur_f32(&img, s);
                PamImage::new_rgb(pam.width, pam.height, blurred.into_raw()).map_err(OpError::Pam)
            }
        }
        "sharpen" => {
            let kernel: [f32; 9] = [0.0, -1.0, 0.0, -1.0, 5.0, -1.0, 0.0, -1.0, 0.0];
            if pam.depth == 4 {
                let img = image::RgbaImage::from_raw(pam.width, pam.height, pam.data.clone())
                    .ok_or_else(|| OpError::ProcessError("Buffer RGBA inválido".to_string()))?;
                let sharpened = imageproc::filter::filter3x3(&img, &kernel);
                PamImage::new_rgba(pam.width, pam.height, sharpened.into_raw())
                    .map_err(OpError::Pam)
            } else {
                let img = image::RgbImage::from_raw(pam.width, pam.height, pam.data.clone())
                    .ok_or_else(|| OpError::ProcessError("Buffer RGB inválido".to_string()))?;
                let sharpened = imageproc::filter::filter3x3(&img, &kernel);
                PamImage::new_rgb(pam.width, pam.height, sharpened.into_raw()).map_err(OpError::Pam)
            }
        }
        "grayscale" | "gray" => {
            if pam.depth == 4 {
                let img = image::RgbaImage::from_raw(pam.width, pam.height, pam.data.clone())
                    .ok_or_else(|| OpError::ProcessError("Buffer RGBA inválido".to_string()))?;
                let gray = image::imageops::grayscale(&img);
                let mut out = Vec::with_capacity((pam.width * pam.height * 4) as usize);
                for (i, p) in gray.pixels().enumerate() {
                    let y = p[0];
                    let a = img.as_raw()[i * 4 + 3];
                    out.extend_from_slice(&[y, y, y, a]);
                }
                PamImage::new_rgba(pam.width, pam.height, out).map_err(OpError::Pam)
            } else {
                let img = image::RgbImage::from_raw(pam.width, pam.height, pam.data.clone())
                    .ok_or_else(|| OpError::ProcessError("Buffer RGB inválido".to_string()))?;
                let gray = image::imageops::grayscale(&img);
                let mut out = Vec::with_capacity((pam.width * pam.height * 3) as usize);
                for p in gray.pixels() {
                    let y = p[0];
                    out.extend_from_slice(&[y, y, y]);
                }
                PamImage::new_rgb(pam.width, pam.height, out).map_err(OpError::Pam)
            }
        }
        "invert" => {
            let mut out = pam.data.clone();
            if pam.depth == 4 {
                for chunk in out.chunks_exact_mut(4) {
                    chunk[0] = 255 - chunk[0];
                    chunk[1] = 255 - chunk[1];
                    chunk[2] = 255 - chunk[2];
                }
                PamImage::new_rgba(pam.width, pam.height, out).map_err(OpError::Pam)
            } else {
                for byte in &mut out {
                    *byte = 255 - *byte;
                }
                PamImage::new_rgb(pam.width, pam.height, out).map_err(OpError::Pam)
            }
        }
        other => Err(OpError::InvalidParam(format!(
            "Filtro desconhecido: '{other}'. Opções: blur, sharpen, grayscale, invert"
        ))),
    }
}
