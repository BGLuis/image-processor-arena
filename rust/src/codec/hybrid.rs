// rust/src/codec/hybrid.rs
// Codecs híbridos FFI (Tier 3: hybrid) usando libturbojpeg e libwebp do sistema.

#[cfg(feature = "hybrid")]
#[allow(non_camel_case_types, non_snake_case)]
pub mod ffi {
    use libc::{c_char, c_int, c_uchar, c_ulong, c_void, size_t};

    pub type tjhandle = *mut c_void;

    pub const TJSAMP_420: c_int = 2;
    pub const TJPF_RGB: c_int = 0;
    pub const TJPF_RGBA: c_int = 7;

    #[repr(C)]
    pub struct WebPBitstreamFeatures {
        pub width: c_int,
        pub height: c_int,
        pub has_alpha: c_int,
        pub has_animation: c_int,
        pub format: c_int,
        pub pad: [u32; 5],
    }

    #[link(name = "turbojpeg")]
    extern "C" {
        pub fn tjInitCompress() -> tjhandle;
        pub fn tjInitDecompress() -> tjhandle;
        pub fn tjDestroy(handle: tjhandle) -> c_int;
        pub fn tjGetErrorStr2(handle: tjhandle) -> *const c_char;
        pub fn tjFree(buffer: *mut c_uchar);
        pub fn tjCompress2(
            handle: tjhandle,
            srcBuf: *const c_uchar,
            width: c_int,
            pitch: c_int,
            height: c_int,
            pixelFormat: c_int,
            jpegBuf: *mut *mut c_uchar,
            jpegSize: *mut c_ulong,
            jpegSubsamp: c_int,
            jpegQual: c_int,
            flags: c_int,
        ) -> c_int;
        pub fn tjDecompressHeader2(
            handle: tjhandle,
            jpegBuf: *const c_uchar,
            jpegSize: c_ulong,
            width: *mut c_int,
            height: *mut c_int,
            jpegSubsamp: *mut c_int,
        ) -> c_int;
        pub fn tjDecompress2(
            handle: tjhandle,
            jpegBuf: *const c_uchar,
            jpegSize: c_ulong,
            dstBuf: *mut c_uchar,
            width: c_int,
            pitch: c_int,
            height: c_int,
            pixelFormat: c_int,
            flags: c_int,
        ) -> c_int;
    }

    #[link(name = "webp")]
    extern "C" {
        pub fn WebPEncodeRGB(
            rgb: *const u8,
            width: c_int,
            height: c_int,
            stride: c_int,
            quality_factor: f32,
            output: *mut *mut u8,
        ) -> size_t;
        pub fn WebPEncodeRGBA(
            rgba: *const u8,
            width: c_int,
            height: c_int,
            stride: c_int,
            quality_factor: f32,
            output: *mut *mut u8,
        ) -> size_t;
        pub fn WebPEncodeLosslessRGB(
            rgb: *const u8,
            width: c_int,
            height: c_int,
            stride: c_int,
            output: *mut *mut u8,
        ) -> size_t;
        pub fn WebPEncodeLosslessRGBA(
            rgba: *const u8,
            width: c_int,
            height: c_int,
            stride: c_int,
            output: *mut *mut u8,
        ) -> size_t;
        pub fn WebPDecodeRGB(
            data: *const u8,
            data_size: size_t,
            width: *mut c_int,
            height: *mut c_int,
        ) -> *mut u8;
        pub fn WebPDecodeRGBA(
            data: *const u8,
            data_size: size_t,
            width: *mut c_int,
            height: *mut c_int,
        ) -> *mut u8;
        pub fn WebPGetFeaturesInternal(
            data: *const u8,
            data_size: size_t,
            features: *mut WebPBitstreamFeatures,
            abi_version: c_int,
        ) -> c_int;
        pub fn WebPFree(ptr: *mut c_void);
    }
}

#[cfg(feature = "hybrid")]
use super::{check_side, checked_len, CodecError, CodecMode, EncodeParams, JPEG_MAX_SIDE, WEBP_MAX_SIDE};
#[cfg(feature = "hybrid")]
use crate::pam::PamImage;

#[cfg(feature = "hybrid")]
pub fn jpeg_encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    check_side(pam, "JPEG", JPEG_MAX_SIDE)?;
    unsafe {
        let handle = ffi::tjInitCompress();
        if handle.is_null() {
            return Err(CodecError::Encode("Falha ao inicializar tjInitCompress".into()));
        }
        let (src_ptr, pixel_format) = if pam.depth == 4 {
            (pam.data.as_ptr(), ffi::TJPF_RGBA)
        } else {
            (pam.data.as_ptr(), ffi::TJPF_RGB)
        };
        let mut jpeg_buf: *mut libc::c_uchar = std::ptr::null_mut();
        let mut jpeg_size: libc::c_ulong = 0;
        let quality = params.quality.clamp(1, 100) as libc::c_int;
        let ret = ffi::tjCompress2(
            handle,
            src_ptr,
            pam.width as libc::c_int,
            0,
            pam.height as libc::c_int,
            pixel_format,
            &mut jpeg_buf,
            &mut jpeg_size,
            ffi::TJSAMP_420,
            quality,
            0,
        );
        if ret != 0 {
            let err_c = ffi::tjGetErrorStr2(handle);
            let err_msg = if !err_c.is_null() {
                std::ffi::CStr::from_ptr(err_c).to_string_lossy().to_string()
            } else {
                "tjCompress2 falhou".into()
            };
            ffi::tjDestroy(handle);
            return Err(CodecError::Encode(err_msg));
        }
        ffi::tjDestroy(handle);
        let out_bytes = std::slice::from_raw_parts(jpeg_buf, jpeg_size as usize).to_vec();
        ffi::tjFree(jpeg_buf);
        Ok(out_bytes)
    }
}

#[cfg(feature = "hybrid")]
pub fn jpeg_decode(data: &[u8]) -> Result<PamImage, CodecError> {
    unsafe {
        let handle = ffi::tjInitDecompress();
        if handle.is_null() {
            return Err(CodecError::Decode("Falha ao inicializar tjInitDecompress".into()));
        }
        let mut width: libc::c_int = 0;
        let mut height: libc::c_int = 0;
        let mut subsamp: libc::c_int = 0;
        let ret_hdr = ffi::tjDecompressHeader2(
            handle,
            data.as_ptr(),
            data.len() as libc::c_ulong,
            &mut width,
            &mut height,
            &mut subsamp,
        );
        if ret_hdr != 0 {
            let err_c = ffi::tjGetErrorStr2(handle);
            let err_msg = if !err_c.is_null() {
                std::ffi::CStr::from_ptr(err_c).to_string_lossy().to_string()
            } else {
                "tjDecompressHeader2 falhou".into()
            };
            ffi::tjDestroy(handle);
            return Err(CodecError::Decode(err_msg));
        }
        let w = width as u32;
        let h = height as u32;
        let len = checked_len(w, h, 3)?;
        let mut dst_buf = vec![0u8; len];
        let ret_dec = ffi::tjDecompress2(
            handle,
            data.as_ptr(),
            data.len() as libc::c_ulong,
            dst_buf.as_mut_ptr(),
            width,
            0,
            height,
            ffi::TJPF_RGB,
            0,
        );
        if ret_dec != 0 {
            let err_c = ffi::tjGetErrorStr2(handle);
            let err_msg = if !err_c.is_null() {
                std::ffi::CStr::from_ptr(err_c).to_string_lossy().to_string()
            } else {
                "tjDecompress2 falhou".into()
            };
            ffi::tjDestroy(handle);
            return Err(CodecError::Decode(err_msg));
        }
        ffi::tjDestroy(handle);
        PamImage::new_rgb(w, h, dst_buf).map_err(|e| CodecError::Decode(e.to_string()))
    }
}

#[cfg(feature = "hybrid")]
pub fn webp_encode(pam: &PamImage, params: &EncodeParams) -> Result<Vec<u8>, CodecError> {
    check_side(pam, "WebP", WEBP_MAX_SIDE)?;
    let w = pam.width as libc::c_int;
    let h = pam.height as libc::c_int;
    let stride = (pam.width * pam.depth as u32) as libc::c_int;
    let mut out_ptr: *mut u8 = std::ptr::null_mut();
    let size = unsafe {
        match params.mode {
            CodecMode::Lossless => {
                if pam.depth == 4 {
                    ffi::WebPEncodeLosslessRGBA(pam.data.as_ptr(), w, h, stride, &mut out_ptr)
                } else {
                    ffi::WebPEncodeLosslessRGB(pam.data.as_ptr(), w, h, stride, &mut out_ptr)
                }
            }
            CodecMode::Lossy => {
                let q = params.quality.clamp(1, 100) as f32;
                if pam.depth == 4 {
                    ffi::WebPEncodeRGBA(pam.data.as_ptr(), w, h, stride, q, &mut out_ptr)
                } else {
                    ffi::WebPEncodeRGB(pam.data.as_ptr(), w, h, stride, q, &mut out_ptr)
                }
            }
        }
    };
    if size == 0 || out_ptr.is_null() {
        return Err(CodecError::Encode("WebP encode via libwebp falhou".into()));
    }
    let out_vec = unsafe {
        let slice = std::slice::from_raw_parts(out_ptr, size);
        let vec = slice.to_vec();
        ffi::WebPFree(out_ptr as *mut libc::c_void);
        vec
    };
    Ok(out_vec)
}

#[cfg(feature = "hybrid")]
pub fn webp_decode(data: &[u8]) -> Result<PamImage, CodecError> {
    let mut features: ffi::WebPBitstreamFeatures = unsafe { std::mem::zeroed() };
    let status = unsafe {
        ffi::WebPGetFeaturesInternal(data.as_ptr(), data.len(), &mut features, 0x0210)
    };
    if status != 0 {
        return Err(CodecError::Decode("WebPGetFeatures falhou: cabeçalho inválido".into()));
    }
    if features.has_animation != 0 {
        return Err(CodecError::Decode("WebP animado não é suportado".into()));
    }
    let mut width: libc::c_int = 0;
    let mut height: libc::c_int = 0;
    let has_alpha = features.has_alpha != 0;
    let ptr = unsafe {
        if has_alpha {
            ffi::WebPDecodeRGBA(data.as_ptr(), data.len(), &mut width, &mut height)
        } else {
            ffi::WebPDecodeRGB(data.as_ptr(), data.len(), &mut width, &mut height)
        }
    };
    if ptr.is_null() {
        return Err(CodecError::Decode("WebPDecode falhou".into()));
    }
    let w = width as u32;
    let h = height as u32;
    let total_bytes = checked_len(w, h, if has_alpha { 4 } else { 3 })?;
    let pam_res = unsafe {
        let slice = std::slice::from_raw_parts(ptr, total_bytes);
        let bytes = slice.to_vec();
        ffi::WebPFree(ptr as *mut libc::c_void);
        if has_alpha {
            PamImage::new_rgba(w, h, bytes)
        } else {
            PamImage::new_rgb(w, h, bytes)
        }
    };
    pam_res.map_err(|e| CodecError::Decode(e.to_string()))
}
