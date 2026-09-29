package codec

import (
	"bytes"
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

func TestCodecAVIFLossless(t *testing.T) {
	testRoundtrip(t, "avif", "lossless", 0)
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
