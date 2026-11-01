//go:build hybrid

package codec

/*
#cgo pkg-config: libturbojpeg libwebp
#include <stdlib.h>
#include <turbojpeg.h>
#include <webp/encode.h>
#include <webp/decode.h>

static int arena_tj_compress(const unsigned char *src, int width, int pitch, int height,
                             int pixel_format, int jpeg_qual, int jpeg_subsamp,
                             unsigned char **out_buf, unsigned long *out_size) {
    tjhandle handle = tjInitCompress();
    if (!handle) return -1;

    unsigned char *jpeg_buf = NULL;
    unsigned long jpeg_size = 0;
    int flags = TJFLAG_ACCURATEDCT;

    int ret = tjCompress2(handle, src, width, pitch, height, pixel_format,
                          &jpeg_buf, &jpeg_size, jpeg_subsamp, jpeg_qual, flags);
    tjDestroy(handle);

    if (ret != 0) {
        if (jpeg_buf) tjFree(jpeg_buf);
        return -1;
    }
    *out_buf = jpeg_buf;
    *out_size = jpeg_size;
    return 0;
}

static int arena_tj_decompress(const unsigned char *jpeg_buf, unsigned long jpeg_size,
                               int *width, int *height, unsigned char **out_buf) {
    tjhandle handle = tjInitDecompress();
    if (!handle) return -1;

    int w = 0, h = 0, subsamp = 0, colorspace = 0;
    if (tjDecompressHeader3(handle, jpeg_buf, jpeg_size, &w, &h, &subsamp, &colorspace) != 0) {
        tjDestroy(handle);
        return -1;
    }

    unsigned char *rgb_buf = (unsigned char *)malloc((size_t)w * (size_t)h * 4);
    if (!rgb_buf) {
        tjDestroy(handle);
        return -1;
    }

    if (tjDecompress2(handle, jpeg_buf, jpeg_size, rgb_buf, w, 0, h, TJPF_RGBA, 0) != 0) {
        free(rgb_buf);
        tjDestroy(handle);
        return -1;
    }

    tjDestroy(handle);
    *width = w;
    *height = h;
    *out_buf = rgb_buf;
    return 0;
}

static size_t arena_webp_encode(const unsigned char *src, int width, int height, int stride,
                                int depth, int lossless, float quality, unsigned char **out_buf) {
    if (depth == 3) {
        if (lossless) {
            return WebPEncodeLosslessRGB(src, width, height, stride, out_buf);
        } else {
            return WebPEncodeRGB(src, width, height, stride, quality, out_buf);
        }
    } else {
        if (lossless) {
            return WebPEncodeLosslessRGBA(src, width, height, stride, out_buf);
        } else {
            return WebPEncodeRGBA(src, width, height, stride, quality, out_buf);
        }
    }
}

static unsigned char* arena_webp_decode(const unsigned char *data, size_t size, int *w, int *h) {
    if (!WebPGetInfo(data, size, w, h)) {
        return NULL;
    }
    return WebPDecodeRGBA(data, size, w, h);
}
*/
import "C"

import (
	"errors"
	"fmt"
	"image"
	"io"
	"unsafe"

	"github.com/image-processor-arena/go/internal/pam"
)

func encodeJPEGHybrid(w io.Writer, pamImg *pam.Image, params Params) error {
	if err := checkSide(pamImg, "jpeg", jpegMaxSide); err != nil {
		return err
	}
	if len(pamImg.Pix) == 0 {
		return errors.New("empty raster")
	}
	pixelFormat := C.TJPF_RGB
	if pamImg.Depth == 4 {
		pixelFormat = C.TJPF_RGBA
	}
	pitch := C.int(pamImg.Width * pamImg.Depth)

	var outBuf *C.uchar
	var outSize C.ulong
	srcPtr := (*C.uchar)(unsafe.Pointer(&pamImg.Pix[0]))
	ret := C.arena_tj_compress(srcPtr, C.int(pamImg.Width), pitch, C.int(pamImg.Height),
		C.int(pixelFormat), C.int(params.Q), C.TJSAMP_420, &outBuf, &outSize)
	if ret != 0 {
		return fmt.Errorf("turbojpeg encode failed")
	}
	defer C.tjFree(outBuf)

	jpegBytes := C.GoBytes(unsafe.Pointer(outBuf), C.int(outSize))
	_, err := w.Write(jpegBytes)
	return err
}

func decodeJPEGHybrid(r io.Reader) (image.Image, error) {
	data, err := io.ReadAll(r)
	if err != nil {
		return nil, err
	}
	if len(data) == 0 {
		return nil, errors.New("empty jpeg data")
	}

	var w, h C.int
	var outBuf *C.uchar
	dataPtr := (*C.uchar)(unsafe.Pointer(&data[0]))
	ret := C.arena_tj_decompress(dataPtr, C.ulong(len(data)), &w, &h, &outBuf)
	if ret != 0 {
		return nil, fmt.Errorf("turbojpeg decode failed")
	}
	defer C.free(unsafe.Pointer(outBuf))

	totalBytes := int(w) * int(h) * 4
	raw := C.GoBytes(unsafe.Pointer(outBuf), C.int(totalBytes))
	img := &image.RGBA{
		Pix:    raw,
		Stride: int(w) * 4,
		Rect:   image.Rect(0, 0, int(w), int(h)),
	}
	return img, nil
}

func encodeWebPHybrid(w io.Writer, pamImg *pam.Image, params Params) error {
	if err := checkSide(pamImg, "webp", webpMaxSide); err != nil {
		return err
	}
	if len(pamImg.Pix) == 0 {
		return errors.New("empty raster")
	}
	stride := C.int(pamImg.Width * pamImg.Depth)
	var isLossless C.int
	if params.Mode == ModeLossless {
		isLossless = 1
	}

	var outBuf *C.uchar
	srcPtr := (*C.uchar)(unsafe.Pointer(&pamImg.Pix[0]))
	outSize := C.arena_webp_encode(srcPtr, C.int(pamImg.Width), C.int(pamImg.Height),
		stride, C.int(pamImg.Depth), isLossless, C.float(params.Q), &outBuf)
	if outSize == 0 {
		return fmt.Errorf("libwebp encode failed")
	}
	defer C.WebPFree(unsafe.Pointer(outBuf))

	webpBytes := C.GoBytes(unsafe.Pointer(outBuf), C.int(outSize))
	_, err := w.Write(webpBytes)
	return err
}

func decodeWebPHybrid(r io.Reader) (image.Image, error) {
	data, err := io.ReadAll(r)
	if err != nil {
		return nil, err
	}
	if len(data) == 0 {
		return nil, errors.New("empty webp data")
	}
	if isAnimatedWebP(data) {
		return nil, fmt.Errorf("decode webp: animated WebP is not supported")
	}

	var w, h C.int
	dataPtr := (*C.uchar)(unsafe.Pointer(&data[0]))
	res := C.arena_webp_decode(dataPtr, C.size_t(len(data)), &w, &h)
	if res == nil {
		return nil, fmt.Errorf("libwebp decode failed")
	}
	defer C.WebPFree(unsafe.Pointer(res))

	totalBytes := int(w) * int(h) * 4
	raw := C.GoBytes(unsafe.Pointer(res), C.int(totalBytes))
	img := &image.NRGBA{
		Pix:    raw,
		Stride: int(w) * 4,
		Rect:   image.Rect(0, 0, int(w), int(h)),
	}
	return img, nil
}

func init() {
	// JPEG CGO
	for _, name := range []string{"hybrid", "cgo", "turbojpeg", "libturbojpeg"} {
		RegisterEncoder("jpeg", name, encodeJPEGHybrid)
		RegisterDecoder("jpeg", name, decodeJPEGHybrid)
	}

	// WebP CGO
	for _, name := range []string{"hybrid", "cgo", "libwebp"} {
		RegisterEncoder("webp", name, encodeWebPHybrid)
		RegisterDecoder("webp", name, decodeWebPHybrid)
	}

	// PNG hybrid (stdlib wrapper)
	for _, name := range []string{"hybrid", "cgo", "libpng"} {
		RegisterEncoder("png", name, func(w io.Writer, pamImg *pam.Image, params Params) error {
			return encoderAdapters["png"]["stdlib"](w, pamImg, params)
		})
		RegisterDecoder("png", name, func(r io.Reader) (image.Image, error) {
			return decoderAdapters["png"]["stdlib"](r)
		})
	}

	// AVIF hybrid (gav1d wrapper)
	for _, name := range []string{"hybrid", "cgo"} {
		RegisterEncoder("avif", name, func(w io.Writer, pamImg *pam.Image, params Params) error {
			return encoderAdapters["avif"]["gav1d"](w, pamImg, params)
		})
		RegisterDecoder("avif", name, func(r io.Reader) (image.Image, error) {
			return decoderAdapters["avif"]["gav1d"](r)
		})
	}

	// JXL hybrid (gen2brain wrapper)
	for _, name := range []string{"hybrid", "cgo", "libjxl"} {
		RegisterEncoder("jxl", name, func(w io.Writer, pamImg *pam.Image, params Params) error {
			return encoderAdapters["jxl"]["gen2brain"](w, pamImg, params)
		})
		RegisterDecoder("jxl", name, func(r io.Reader) (image.Image, error) {
			return decoderAdapters["jxl"]["gen2brain"](r)
		})
	}
}
