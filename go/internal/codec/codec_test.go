package codec

import (
	"bytes"
	"errors"
	"io"
	"os"
	"testing"

	"github.com/image-processor-arena/go/internal/pam"
)

func getTestPAM(t *testing.T) *pam.Image {
	t.Helper()
	pamPath := "../../../harness/fixtures/synthetic/gradient_h.pam"
	data, err := os.ReadFile(pamPath)
	if err != nil {
		t.Fatalf("Failed to read fixture: %v", err)
	}
	img, err := pam.Decode(bytes.NewReader(data))
	if err != nil {
		t.Fatalf("Failed to decode PAM: %v", err)
	}
	return img
}

func testRoundtrip(t *testing.T, format string, mode string, q int) {
	img := getTestPAM(t)

	var encBuf bytes.Buffer
	err := Encode(&encBuf, img, Params{
		Format: format,
		Mode:   mode,
		Q:      q,
		Effort: 4,
	})
	if err != nil {
		t.Fatalf("Encode format=%s mode=%s failed: %v", format, mode, err)
	}

	if encBuf.Len() == 0 {
		t.Fatalf("Encode format=%s mode=%s produced empty output", format, mode)
	}

	decPAM, err := Decode(bytes.NewReader(encBuf.Bytes()), format)
	if err != nil {
		t.Fatalf("Decode format=%s mode=%s failed: %v", format, mode, err)
	}

	if decPAM.Width != img.Width || decPAM.Height != img.Height {
		t.Fatalf("Dimension mismatch for %s: got %dx%d, want %dx%d",
			format, decPAM.Width, decPAM.Height, img.Width, img.Height)
	}
}

func TestCodecPNG(t *testing.T) {
	testRoundtrip(t, "png", "lossless", 0)
}

func TestCodecJPEG(t *testing.T) {
	testRoundtrip(t, "jpeg", "lossy", 80)
}

func TestCodecWebPLossy(t *testing.T) {
	testRoundtrip(t, "webp", "lossy", 75)
}

func TestCodecWebPLossless(t *testing.T) {
	testRoundtrip(t, "webp", "lossless", 0)
}

func TestCodecAVIFLossy(t *testing.T) {
	testRoundtrip(t, "avif", "lossy", 60)
}

// No pure-Go AVIF encoder round-trips RGB exactly, so the mode must be refused
// instead of silently producing a lossy file labelled lossless.
func TestCodecAVIFLosslessIsRefused(t *testing.T) {
	img := loadCorpusPAM(t, "photo")

	err := Encode(io.Discard, img, Params{Format: "avif", Mode: "lossless", Q: 100, Effort: 4})
	if !errors.Is(err, ErrUnsupportedFormat) {
		t.Fatalf("avif lossless encode: got err=%v, want ErrUnsupportedFormat", err)
	}
}

func TestLosslessRoundtripIsPixelExact(t *testing.T) {
	for _, format := range []string{"png", "webp", "jxl"} {
		for _, name := range []string{"photo", "screenshot", "illustration", "alpha"} {
			t.Run(format+"/"+name, func(t *testing.T) {
				img := loadCorpusPAM(t, name)

				var encBuf bytes.Buffer
				if err := Encode(&encBuf, img, Params{Format: format, Mode: "lossless", Q: 100, Effort: 4}); err != nil {
					t.Fatalf("Encode failed: %v", err)
				}
				decoded, err := Decode(bytes.NewReader(encBuf.Bytes()), format)
				if err != nil {
					t.Fatalf("Decode failed: %v", err)
				}

				if diff := countChannelDiffs(t, img, decoded); diff != 0 {
					t.Fatalf("%d channel bytes differ after lossless round-trip", diff)
				}
			})
		}
	}
}

func loadCorpusPAM(t *testing.T, name string) *pam.Image {
	t.Helper()
	data, err := os.ReadFile("../../../harness/fixtures/corpus/" + name + ".pam")
	if err != nil {
		t.Fatalf("Failed to read corpus image: %v", err)
	}
	img, err := pam.Decode(bytes.NewReader(data))
	if err != nil {
		t.Fatalf("Failed to decode PAM: %v", err)
	}
	return img
}

// countChannelDiffs compares RGB, and alpha when both images carry it.
// A depth-4 image whose alpha is fully opaque may come back as depth 3.
func countChannelDiffs(t *testing.T, want, got *pam.Image) int {
	t.Helper()
	if want.Width != got.Width || want.Height != got.Height {
		t.Fatalf("dimension mismatch: got %dx%d, want %dx%d", got.Width, got.Height, want.Width, want.Height)
	}

	diffs := 0
	for i := 0; i < want.Width*want.Height; i++ {
		for c := 0; c < 3; c++ {
			if want.Pix[i*want.Depth+c] != got.Pix[i*got.Depth+c] {
				diffs++
			}
		}
		wantAlpha, gotAlpha := byte(255), byte(255)
		if want.Depth == 4 {
			wantAlpha = want.Pix[i*4+3]
		}
		if got.Depth == 4 {
			gotAlpha = got.Pix[i*4+3]
		}
		if wantAlpha != gotAlpha {
			diffs++
		}
	}
	return diffs
}

func TestCodecJXLLossy(t *testing.T) {
	testRoundtrip(t, "jxl", "lossy", 80)
}

func TestCodecJXLLossless(t *testing.T) {
	testRoundtrip(t, "jxl", "lossless", 0)
}

func BenchmarkCodecPNGEncode(b *testing.B) {
	pamPath := "../../../harness/fixtures/synthetic/solid_red.pam"
	data, _ := os.ReadFile(pamPath)
	img, _ := pam.Decode(bytes.NewReader(data))

	var buf bytes.Buffer
	buf.Grow(1024 * 64)

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		buf.Reset()
		_ = Encode(&buf, img, Params{Format: "png", Mode: "lossless"})
	}
}

func BenchmarkCodecJPEGEncode(b *testing.B) {
	pamPath := "../../../harness/fixtures/synthetic/solid_red.pam"
	data, _ := os.ReadFile(pamPath)
	img, _ := pam.Decode(bytes.NewReader(data))

	var buf bytes.Buffer
	buf.Grow(1024 * 64)

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		buf.Reset()
		_ = Encode(&buf, img, Params{Format: "jpeg", Mode: "lossy", Q: 80})
	}
}
