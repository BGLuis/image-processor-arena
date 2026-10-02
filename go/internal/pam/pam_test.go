package pam

import (
	"bytes"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestPAMRoundtrip(t *testing.T) {
	// Create sample PAM RGB image
	w, h := 16, 16
	pix := make([]byte, w*h*3)
	for i := range pix {
		pix[i] = byte(i % 256)
	}

	orig := &Image{
		Width:    w,
		Height:   h,
		Depth:    3,
		MaxVal:   255,
		TuplType: "RGB",
		Pix:      pix,
	}

	var buf bytes.Buffer
	if err := Encode(&buf, orig); err != nil {
		t.Fatalf("Encode failed: %v", err)
	}

	decoded, err := Decode(&buf)
	if err != nil {
		t.Fatalf("Decode failed: %v", err)
	}

	if decoded.Width != orig.Width || decoded.Height != orig.Height || decoded.Depth != orig.Depth {
		t.Fatalf("Header mismatch: got %dx%d d=%d, want %dx%d d=%d",
			decoded.Width, decoded.Height, decoded.Depth, orig.Width, orig.Height, orig.Depth)
	}

	if !bytes.Equal(decoded.Pix, orig.Pix) {
		t.Fatalf("Pixel data mismatch")
	}
}

func TestPAMReadSyntheticFixtures(t *testing.T) {
	fixturesDir := "../../../harness/fixtures/synthetic"
	files, err := os.ReadDir(fixturesDir)
	if err != nil {
		t.Skipf("Synthetic fixtures directory not found: %v", err)
		return
	}

	for _, file := range files {
		if filepath.Ext(file.Name()) != ".pam" {
			continue
		}
		path := filepath.Join(fixturesDir, file.Name())
		data, err := os.ReadFile(path)
		if err != nil {
			t.Errorf("Failed to read %s: %v", file.Name(), err)
			continue
		}

		img, err := Decode(bytes.NewReader(data))
		if err != nil {
			t.Errorf("Decode %s failed: %v", file.Name(), err)
			continue
		}

		if img.Width != 64 || img.Height != 64 {
			t.Errorf("%s: unexpected dims %dx%d", file.Name(), img.Width, img.Height)
		}

		expectedDepth := 3
		if file.Name() == "alpha_boxes.pam" {
			expectedDepth = 4
		}
		if img.Depth != expectedDepth {
			t.Errorf("%s: expected depth %d, got %d", file.Name(), expectedDepth, img.Depth)
		}
	}
}

// allocatedBy runs f and returns how many bytes it allocated, so a test can prove that a
// hostile header was refused before the raster was allocated.
func allocatedBy(f func()) uint64 {
	var before, after runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&before)
	f()
	runtime.ReadMemStats(&after)
	return after.TotalAlloc - before.TotalAlloc
}

func TestDecodeRefusesHugeDimensionsWithoutAllocating(t *testing.T) {
	for _, header := range []string{
		"P7\nWIDTH 100000\nHEIGHT 100000\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n",
		"P7\nWIDTH 9223372036854775807\nHEIGHT 2\nDEPTH 3\nMAXVAL 255\nENDHDR\n",
		"P7\nWIDTH 2\nHEIGHT 9223372036854775807\nDEPTH 3\nMAXVAL 255\nENDHDR\n",
	} {
		var err error
		alloc := allocatedBy(func() { _, err = Decode(strings.NewReader(header)) })
		if !errors.Is(err, ErrTooLarge) {
			t.Errorf("%q: got err=%v, want ErrTooLarge", header, err)
		}
		if alloc > 1<<20 {
			t.Errorf("%q: allocated %d bytes before refusing the image", header, alloc)
		}
	}
}

func TestDecodeChecksDeclaredSizeAgainstTheBodyBeforeAllocating(t *testing.T) {
	// 4000x4000x3 = 48 MB is within the limit, but the body carries only the header.
	header := "P7\nWIDTH 4000\nHEIGHT 4000\nDEPTH 3\nMAXVAL 255\nENDHDR\n"
	var err error
	alloc := allocatedBy(func() { _, err = Decode(bytes.NewReader([]byte(header))) })
	if !errors.Is(err, ErrTruncated) {
		t.Fatalf("got err=%v, want ErrTruncated", err)
	}
	if alloc > 1<<20 {
		t.Fatalf("allocated %d bytes for a body that cannot fill the raster", alloc)
	}
}

func TestDecodeLimitHonoursTheCallerCeiling(t *testing.T) {
	data := EncodeBytes(&Image{Width: 8, Height: 8, Depth: 3, MaxVal: 255, TuplType: "RGB", Pix: make([]byte, 8*8*3)})

	if _, err := DecodeLimit(bytes.NewReader(data), 64); err != nil {
		t.Fatalf("64 pixels under a 64 pixel limit: %v", err)
	}
	if _, err := DecodeLimit(bytes.NewReader(data), 63); !errors.Is(err, ErrTooLarge) {
		t.Fatalf("64 pixels under a 63 pixel limit: got err=%v, want ErrTooLarge", err)
	}
}

func TestDecodeAcceptsAnyWhitespaceInTheHeader(t *testing.T) {
	header := "P7\nWIDTH\t2\nHEIGHT   1\nDEPTH \t 3\nMAXVAL\t255\nTUPLTYPE  RGB\nENDHDR\n"
	img, err := Decode(strings.NewReader(header + "\x01\x02\x03\x04\x05\x06"))
	if err != nil {
		t.Fatalf("Decode failed: %v", err)
	}
	if img.Width != 2 || img.Height != 1 || img.Depth != 3 || img.TuplType != "RGB" {
		t.Fatalf("unexpected image: %dx%d depth %d tupltype %q", img.Width, img.Height, img.Depth, img.TuplType)
	}
	if !bytes.Equal(img.Pix, []byte{1, 2, 3, 4, 5, 6}) {
		t.Fatalf("unexpected pixels: %v", img.Pix)
	}
}

func TestDecodeBoundsTheHeader(t *testing.T) {
	longLine := "P7\n# " + strings.Repeat("x", maxHeaderLine+1) + "\nENDHDR\n"
	manyComments := "P7\n" + strings.Repeat("# filler\n", maxHeaderBytes/8) + "ENDHDR\n"
	for name, header := range map[string]string{"long line": longLine, "many lines": manyComments} {
		if _, err := Decode(strings.NewReader(header)); !errors.Is(err, ErrInvalidHeader) {
			t.Errorf("%s: got err=%v, want ErrInvalidHeader", name, err)
		}
	}
}

func BenchmarkPAMDecode(b *testing.B) {
	w, h := 64, 64
	pix := make([]byte, w*h*3)
	img := &Image{
		Width:    w,
		Height:   h,
		Depth:    3,
		MaxVal:   255,
		TuplType: "RGB",
		Pix:      pix,
	}
	data := EncodeBytes(img)
	r := bytes.NewReader(data)

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		r.Reset(data)
		_, err := Decode(r)
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkPAMEncode(b *testing.B) {
	w, h := 64, 64
	pix := make([]byte, w*h*3)
	img := &Image{
		Width:    w,
		Height:   h,
		Depth:    3,
		MaxVal:   255,
		TuplType: "RGB",
		Pix:      pix,
	}
	var buf bytes.Buffer
	buf.Grow(len(pix) + 128)

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		buf.Reset()
		if err := Encode(&buf, img); err != nil {
			b.Fatal(err)
		}
	}
}
