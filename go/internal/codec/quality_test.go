package codec

import (
	"bytes"
	"testing"
)

// Minimum RGB PSNR at the contract defaults (q=75, effort=4). Measured on the corpus the lowest
// values are ~38 dB for photo and ~29 dB for the other classes in every engine; the floors leave
// 2-3 dB of room for library upgrades and still fail an encoder that writes the wrong picture.
var minPSNR = map[string]float64{"photo": 35, "screenshot": 27, "illustration": 27, "alpha": 27}

var lossyFormats = []string{"jpeg", "webp", "avif", "jxl"}

func encodeDecode(t *testing.T, name, format string, p Params) (encoded int, decodedDepth int, psnr float64) {
	t.Helper()
	img := loadCorpusPAM(t, name)
	p.Format = format

	var buf bytes.Buffer
	if err := Encode(&buf, img, p); err != nil {
		t.Fatalf("%s %s: encode: %v", format, name, err)
	}
	decoded, err := Decode(bytes.NewReader(buf.Bytes()), format)
	if err != nil {
		t.Fatalf("%s %s: decode: %v", format, name, err)
	}
	if decoded.Width != img.Width || decoded.Height != img.Height {
		t.Fatalf("%s %s: decoded %dx%d, want %dx%d", format, name, decoded.Width, decoded.Height, img.Width, img.Height)
	}
	return buf.Len(), decoded.Depth, rgbPSNR(img, decoded)
}

func TestLossyRoundtripQualityOnTheCorpus(t *testing.T) {
	for _, format := range lossyFormats {
		for name, floor := range minPSNR {
			t.Run(format+"/"+name, func(t *testing.T) {
				_, depth, psnr := encodeDecode(t, name, format, Params{Mode: "lossy", Q: 75, Effort: 4})
				if psnr < floor {
					t.Errorf("PSNR %.2f dB is below the %.0f dB floor", psnr, floor)
				}
				// JPEG has no alpha; every other lossy format must keep the channel.
				if wantDepth := map[bool]int{true: 3, false: 4}[name != "alpha" || format == "jpeg"]; depth != wantDepth {
					t.Errorf("decoded depth %d, want %d", depth, wantDepth)
				}
			})
		}
	}
}

// A quality parameter that is ignored or inverted is a silent benchmark bug: output size and
// PSNR must both grow with q.
func TestLossyQualityGrowsWithQ(t *testing.T) {
	for _, format := range lossyFormats {
		t.Run(format, func(t *testing.T) {
			lowBytes, _, lowPSNR := encodeDecode(t, "photo", format, Params{Mode: "lossy", Q: 30, Effort: 4})
			highBytes, _, highPSNR := encodeDecode(t, "photo", format, Params{Mode: "lossy", Q: 90, Effort: 4})
			if highPSNR < lowPSNR+3 {
				t.Errorf("PSNR q=90 %.2f dB is not at least 3 dB above q=30 %.2f dB", highPSNR, lowPSNR)
			}
			if highBytes <= lowBytes {
				t.Errorf("q=90 wrote %d bytes, q=30 wrote %d: size must grow with q", highBytes, lowBytes)
			}
		})
	}
}
