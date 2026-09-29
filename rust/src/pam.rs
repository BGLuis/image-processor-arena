// rust/src/pam.rs
// Leitor e escritor Netpbm PAM P7 de alta performance.
// Suporta DEPTH=3 (TUPLTYPE RGB) e DEPTH=4 (TUPLTYPE RGB_ALPHA) com MAXVAL 255.

use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PamError {
    InvalidMagic,
    MissingHeader(String),
    UnsupportedDepth(u8),
    UnsupportedMaxval(u32),
    UnsupportedTupltype(String),
    InvalidDimensions(u32, u32),
    UnexpectedEof,
    BufferTooShort { expected: usize, actual: usize },
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

impl PamImage {
    /// Cria uma nova imagem PAM RGB (depth 3)
    pub fn new_rgb(width: u32, height: u32, data: Vec<u8>) -> Result<Self, PamError> {
        let expected = (width as usize) * (height as usize) * 3;
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
        let expected = (width as usize) * (height as usize) * 4;
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

    /// Faz o parsing de um buffer PAM P7 binário
    pub fn parse(input: &[u8]) -> Result<Self, PamError> {
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

        let expected_bytes = (width as usize) * (height as usize) * (depth as usize);
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
}
