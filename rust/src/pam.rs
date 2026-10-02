// rust/src/pam.rs
// Leitor e escritor Netpbm PAM P7 de alta performance.
// Suporta DEPTH=3 (TUPLTYPE RGB) e DEPTH=4 (TUPLTYPE RGB_ALPHA) com MAXVAL 255.

use crate::limits;
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PamError {
    InvalidMagic,
    MissingHeader(String),
    UnsupportedDepth(u8),
    UnsupportedMaxval(u32),
    UnsupportedTupltype(String),
    InvalidDimensions(u32, u32),
    TooLarge {
        width: u32,
        height: u32,
        max_pixels: usize,
    },
    UnexpectedEof,
    BufferTooShort {
        expected: usize,
        actual: usize,
    },
    InvalidHeaderFormat(String),
}

impl fmt::Display for PamError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidMagic => write!(f, "Número mágico inválido: esperado P7"),
            Self::MissingHeader(h) => write!(f, "Campo obrigatório do cabeçalho ausente: {h}"),
            Self::UnsupportedDepth(d) => write!(f, "DEPTH não suportado: {d} (esperado 3 ou 4)"),
            Self::UnsupportedMaxval(m) => write!(f, "MAXVAL não suportado: {m} (esperado 255)"),
            Self::UnsupportedTupltype(t) => write!(
                f,
                "TUPLTYPE não suportado: '{t}' (esperado RGB ou RGB_ALPHA)"
            ),
            Self::InvalidDimensions(w, h) => write!(f, "Dimensões inválidas: {w}x{h}"),
            Self::TooLarge {
                width,
                height,
                max_pixels,
            } => write!(
                f,
                "Imagem de {width}x{height} excede o limite de {max_pixels} pixels"
            ),
            Self::UnexpectedEof => write!(f, "Fim inesperado do fluxo ao ler cabeçalho PAM"),
            Self::BufferTooShort { expected, actual } => {
                write!(
                    f,
                    "Tamanho de raster insuficiente: esperado {expected}, obtido {actual}"
                )
            }
            Self::InvalidHeaderFormat(msg) => write!(f, "Formato de cabeçalho inválido: {msg}"),
        }
    }
}

impl std::error::Error for PamError {}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PamImage {
    pub width: u32,
    pub height: u32,
    pub depth: u8,
    pub maxval: u32,
    pub tupltype: String,
    pub data: Vec<u8>,
}

/// Tamanho do raster em bytes, ou erro se a conta estourar `usize`.
fn raster_len(width: u32, height: u32, depth: usize) -> Result<usize, PamError> {
    (width as usize)
        .checked_mul(height as usize)
        .and_then(|pixels| pixels.checked_mul(depth))
        .ok_or(PamError::InvalidDimensions(width, height))
}

impl PamImage {
    /// Cria uma nova imagem PAM RGB (depth 3)
    pub fn new_rgb(width: u32, height: u32, data: Vec<u8>) -> Result<Self, PamError> {
        let expected = raster_len(width, height, 3)?;
        if data.len() < expected {
            return Err(PamError::BufferTooShort {
                expected,
                actual: data.len(),
            });
        }
        Ok(Self {
            width,
            height,
            depth: 3,
            maxval: 255,
            tupltype: "RGB".to_string(),
            data,
        })
    }

    /// Cria uma nova imagem PAM RGBA (depth 4)
    pub fn new_rgba(width: u32, height: u32, data: Vec<u8>) -> Result<Self, PamError> {
        let expected = raster_len(width, height, 4)?;
        if data.len() < expected {
            return Err(PamError::BufferTooShort {
                expected,
                actual: data.len(),
            });
        }
        Ok(Self {
            width,
            height,
            depth: 4,
            maxval: 255,
            tupltype: "RGB_ALPHA".to_string(),
            data,
        })
    }

    /// Faz o parsing de um buffer PAM P7 binário, com o teto de pixels do processo.
    pub fn parse(input: &[u8]) -> Result<Self, PamError> {
        Self::parse_with_limit(input, limits::max_pixels())
    }

    /// Como `parse`, recusando WIDTH*HEIGHT acima de `max_pixels` antes de copiar o raster.
    pub fn parse_with_limit(input: &[u8], max_pixels: usize) -> Result<Self, PamError> {
        // Encontra o marcador ENDHDR
        let endhdr_needle = b"ENDHDR";
        let endhdr_pos = input
            .windows(endhdr_needle.len())
            .position(|w| w == endhdr_needle)
            .ok_or(PamError::MissingHeader("ENDHDR".to_string()))?;

        // Determina onde começam os dados de raster (logo após o \n seguinte a ENDHDR)
        let mut raster_start = endhdr_pos + endhdr_needle.len();
        while raster_start < input.len()
            && (input[raster_start] == b'\r'
                || input[raster_start] == b' '
                || input[raster_start] == b'\t')
        {
            raster_start += 1;
        }
        if raster_start < input.len() && input[raster_start] == b'\n' {
            raster_start += 1;
        } else if raster_start >= input.len() {
            return Err(PamError::UnexpectedEof);
        }

        let header_str = std::str::from_utf8(&input[..endhdr_pos])
            .map_err(|e| PamError::InvalidHeaderFormat(e.to_string()))?;

        let mut lines = header_str.lines();
        let magic = lines.next().ok_or(PamError::InvalidMagic)?.trim();
        if magic != "P7" {
            return Err(PamError::InvalidMagic);
        }

        let mut width: Option<u32> = None;
        let mut height: Option<u32> = None;
        let mut depth: Option<u8> = None;
        let mut maxval: Option<u32> = None;
        let mut tupltype: Option<String> = None;

        for line in lines {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }

            let mut parts = line.split_whitespace();
            let key = parts.next().unwrap_or("").to_ascii_uppercase();
            let value = parts.next().unwrap_or("");

            match key.as_str() {
                "WIDTH" => {
                    let w: u32 = value.parse().map_err(|_| {
                        PamError::InvalidHeaderFormat(format!("WIDTH inválido: {value}"))
                    })?;
                    width = Some(w);
                }
                "HEIGHT" => {
                    let h: u32 = value.parse().map_err(|_| {
                        PamError::InvalidHeaderFormat(format!("HEIGHT inválido: {value}"))
                    })?;
                    height = Some(h);
                }
                "DEPTH" => {
                    let d: u8 = value.parse().map_err(|_| {
                        PamError::InvalidHeaderFormat(format!("DEPTH inválido: {value}"))
                    })?;
                    depth = Some(d);
                }
                "MAXVAL" => {
                    let m: u32 = value.parse().map_err(|_| {
                        PamError::InvalidHeaderFormat(format!("MAXVAL inválido: {value}"))
                    })?;
                    maxval = Some(m);
                }
                "TUPLTYPE" => {
                    tupltype = Some(value.to_string());
                }
                _ => {}
            }
        }

        let width = width.ok_or_else(|| PamError::MissingHeader("WIDTH".to_string()))?;
        let height = height.ok_or_else(|| PamError::MissingHeader("HEIGHT".to_string()))?;
        let depth = depth.ok_or_else(|| PamError::MissingHeader("DEPTH".to_string()))?;
        let maxval = maxval.ok_or_else(|| PamError::MissingHeader("MAXVAL".to_string()))?;
        let tupltype = tupltype.unwrap_or_else(|| {
            if depth == 4 {
                "RGB_ALPHA".to_string()
            } else {
                "RGB".to_string()
            }
        });

        if width == 0 || height == 0 {
            return Err(PamError::InvalidDimensions(width, height));
        }
        if depth != 3 && depth != 4 {
            return Err(PamError::UnsupportedDepth(depth));
        }
        if maxval != 255 {
            return Err(PamError::UnsupportedMaxval(maxval));
        }

        if (width as u64) * (height as u64) > max_pixels as u64 {
            return Err(PamError::TooLarge {
                width,
                height,
                max_pixels,
            });
        }
        let expected_bytes = raster_len(width, height, depth as usize)?;
        let raster = &input[raster_start..];
        if raster.len() < expected_bytes {
            return Err(PamError::BufferTooShort {
                expected: expected_bytes,
                actual: raster.len(),
            });
        }

        Ok(Self {
            width,
            height,
            depth,
            maxval,
            tupltype,
            data: raster[..expected_bytes].to_vec(),
        })
    }

    /// Codifica a imagem no formato binário canônico Netpbm PAM P7
    pub fn encode(&self) -> Vec<u8> {
        let header = format!(
            "P7\nWIDTH {}\nHEIGHT {}\nDEPTH {}\nMAXVAL {}\nTUPLTYPE {}\nENDHDR\n",
            self.width, self.height, self.depth, self.maxval, self.tupltype
        );
        let mut out = Vec::with_capacity(header.len() + self.data.len());
        out.extend_from_slice(header.as_bytes());
        out.extend_from_slice(&self.data);
        out
    }

    #[inline]
    pub fn has_alpha(&self) -> bool {
        self.depth == 4
    }

    #[inline]
    pub fn pixel_count(&self) -> usize {
        (self.width as usize) * (self.height as usize)
    }

    /// Extrai o pixel na coordenada (x, y) como (R, G, B, A).
    /// Se depth == 3, A é 255.
    #[inline]
    pub fn rgba_at(&self, x: u32, y: u32) -> (u8, u8, u8, u8) {
        let idx = ((y as usize) * (self.width as usize) + (x as usize)) * (self.depth as usize);
        if self.depth == 4 {
            (
                self.data[idx],
                self.data[idx + 1],
                self.data[idx + 2],
                self.data[idx + 3],
            )
        } else {
            (self.data[idx], self.data[idx + 1], self.data[idx + 2], 255)
        }
    }

    /// Retorna buffer contíguo de pixels RGB (descarta canal alpha se presente)
    pub fn to_rgb_bytes(&self) -> Vec<u8> {
        let num_pixels = self.pixel_count();
        if self.depth == 3 {
            self.data[..num_pixels * 3].to_vec()
        } else {
            let mut out = Vec::with_capacity(num_pixels * 3);
            for chunk in self.data.chunks_exact(4) {
                out.extend_from_slice(&chunk[0..3]);
            }
            out
        }
    }

    /// Retorna buffer contíguo de pixels RGBA (adiciona A=255 se depth == 3)
    pub fn to_rgba_bytes(&self) -> Vec<u8> {
        let num_pixels = self.pixel_count();
        if self.depth == 4 {
            self.data[..num_pixels * 4].to_vec()
        } else {
            let mut out = Vec::with_capacity(num_pixels * 4);
            for chunk in self.data.chunks_exact(3) {
                out.extend_from_slice(chunk);
                out.push(255);
            }
            out
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pam_roundtrip() {
        let width = 2;
        let height = 2;
        let data = vec![255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 0];
        let img = PamImage::new_rgb(width, height, data.clone()).unwrap();
        let encoded = img.encode();
        let parsed = PamImage::parse(&encoded).unwrap();

        assert_eq!(parsed.width, width);
        assert_eq!(parsed.height, height);
        assert_eq!(parsed.depth, 3);
        assert_eq!(parsed.data, data);
    }

    fn header(width: u64, height: u64, depth: u8) -> Vec<u8> {
        format!("P7\nWIDTH {width}\nHEIGHT {height}\nDEPTH {depth}\nMAXVAL 255\nENDHDR\n")
            .into_bytes()
    }

    #[test]
    fn parse_refuses_extreme_dimensions_without_copying() {
        for (width, height) in [
            (100_000u64, 100_000u64),
            (u32::MAX as u64, u32::MAX as u64),
            (u32::MAX as u64, 1),
        ] {
            let err = PamImage::parse(&header(width, height, 4)).unwrap_err();
            assert!(
                matches!(err, PamError::TooLarge { .. }),
                "{width}x{height}: {err:?}"
            );
        }
    }

    #[test]
    fn parse_with_limit_honours_the_ceiling() {
        let mut data = header(8, 8, 3);
        data.extend_from_slice(&[0u8; 8 * 8 * 3]);
        assert!(PamImage::parse_with_limit(&data, 64).is_ok());
        assert!(matches!(
            PamImage::parse_with_limit(&data, 63),
            Err(PamError::TooLarge { .. })
        ));
    }

    #[test]
    fn parse_reports_a_raster_shorter_than_the_header_declares() {
        let mut data = header(16, 16, 3);
        data.extend_from_slice(&[0u8; 10]);
        assert!(matches!(
            PamImage::parse(&data),
            Err(PamError::BufferTooShort { .. })
        ));
    }

    #[test]
    fn constructors_reject_dimensions_that_overflow() {
        let err = PamImage::new_rgb(u32::MAX, u32::MAX, Vec::new()).unwrap_err();
        assert!(matches!(
            err,
            PamError::InvalidDimensions(..) | PamError::BufferTooShort { .. }
        ));
    }
}
