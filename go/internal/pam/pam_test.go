package pam

import (
	"bytes"
	"os"
	"path/filepath"
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
