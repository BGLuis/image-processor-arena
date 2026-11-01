//go:build hybrid

package codec

import (
	"bytes"
	"testing"

	"github.com/image-processor-arena/go/internal/pam"
)

func makeTestPAM(w, h, depth int) *pam.Image {
	img := &pam.Image{
		Width:    w,
		Height:   h,
		Depth:    depth,
		MaxVal:   255,
		TuplType: "RGB",
		Pix:      make([]byte, w*h*depth),
	}
	if depth == 4 {
		img.TuplType = "RGB_ALPHA"
	}
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			idx := (y*w + x) * depth
			img.Pix[idx] = byte((x * 255) / w)
			img.Pix[idx+1] = byte((y * 255) / h)
			img.Pix[idx+2] = byte(((x + y) * 255) / (w + h))
			if depth == 4 {
				img.Pix[idx+3] = 255
			}
		}
	}
	return img
}

func TestHybridJPEG(t *testing.T) {
	for _, impl := range []string{"hybrid", "cgo", "turbojpeg"} {
		src := makeTestPAM(64, 64, 3)
		params := Params{
			Format: "jpeg",
			Mode:   ModeLossy,
			Q:      80,
			Effort: 4,
			Impl:   impl,
		}

		var buf bytes.Buffer
		if err := Encode(&buf, src, params); err != nil {
			t.Fatalf("Encode JPEG (%s) failed: %v", impl, err)
		}
		if buf.Len() == 0 {
			t.Fatalf("Encode JPEG (%s) produced empty buffer", impl)
		}

		decoded, err := Decode(bytes.NewReader(buf.Bytes()), "jpeg", impl)
		if err != nil {
			t.Fatalf("Decode JPEG (%s) failed: %v", impl, err)
		}
		if decoded.Width != 64 || decoded.Height != 64 {
			t.Fatalf("Decode JPEG (%s) dimension mismatch: got %dx%d, want 64x64", impl, decoded.Width, decoded.Height)
		}
	}
}

func TestHybridWebP(t *testing.T) {
	for _, impl := range []string{"hybrid", "cgo", "libwebp"} {
		// Test Lossy
		src := makeTestPAM(64, 64, 3)
		params := Params{
			Format: "webp",
			Mode:   ModeLossy,
			Q:      80,
			Effort: 4,
			Impl:   impl,
		}
		var buf bytes.Buffer
		if err := Encode(&buf, src, params); err != nil {
			t.Fatalf("Encode WebP lossy (%s) failed: %v", impl, err)
		}
		decoded, err := Decode(bytes.NewReader(buf.Bytes()), "webp", impl)
		if err != nil {
			t.Fatalf("Decode WebP lossy (%s) failed: %v", impl, err)
		}
		if decoded.Width != 64 || decoded.Height != 64 {
			t.Fatalf("Decode WebP lossy (%s) dimension mismatch: got %dx%d, want 64x64", impl, decoded.Width, decoded.Height)
		}

		// Test Lossless
		paramsLossless := Params{
			Format: "webp",
			Mode:   ModeLossless,
			Q:      100,
			Effort: 4,
			Impl:   impl,
		}
		var bufLossless bytes.Buffer
		if err := Encode(&bufLossless, src, paramsLossless); err != nil {
			t.Fatalf("Encode WebP lossless (%s) failed: %v", impl, err)
		}
		decodedLossless, err := Decode(bytes.NewReader(bufLossless.Bytes()), "webp", impl)
		if err != nil {
			t.Fatalf("Decode WebP lossless (%s) failed: %v", impl, err)
		}
		if decodedLossless.Width != 64 || decodedLossless.Height != 64 {
			t.Fatalf("Decode WebP lossless (%s) dimension mismatch: got %dx%d, want 64x64", impl, decodedLossless.Width, decodedLossless.Height)
		}
	}
}

func TestHybridAllFormats(t *testing.T) {
	src := makeTestPAM(32, 32, 3)
	formats := []string{"png", "jpeg", "webp", "avif", "jxl"}

	for _, format := range formats {
		params := Params{
			Format: format,
			Mode:   ModeLossy,
			Q:      75,
			Effort: 4,
			Impl:   "hybrid",
		}
		var buf bytes.Buffer
		if err := Encode(&buf, src, params); err != nil {
			t.Fatalf("Encode %s (hybrid) failed: %v", format, err)
		}

		decoded, err := Decode(bytes.NewReader(buf.Bytes()), format, "hybrid")
		if err != nil {
			t.Fatalf("Decode %s (hybrid) failed: %v", format, err)
		}
		if decoded.Width != 32 || decoded.Height != 32 {
			t.Fatalf("Decode %s (hybrid) dimension mismatch: got %dx%d, want 32x32", format, decoded.Width, decoded.Height)
		}
	}
}
