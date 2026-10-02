package pam

import (
	"bytes"
	"errors"
	"image"
	"image/color"
	"math/rand"
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

func samePAM(t *testing.T, name string, got, want *Image) {
	t.Helper()
	if got.Width != want.Width || got.Height != want.Height || got.Depth != want.Depth || got.TuplType != want.TuplType {
		t.Errorf("%s: got %dx%d depth %d %s, want %dx%d depth %d %s", name,
			got.Width, got.Height, got.Depth, got.TuplType, want.Width, want.Height, want.Depth, want.TuplType)
		return
	}
	if !bytes.Equal(got.Pix, want.Pix) {
		t.Errorf("%s: pixels differ from the generic conversion", name)
	}
}

// Every fast path must return exactly what the At()-based conversion returns for 8-bit sources,
// including sub-images whose Rect does not start at the origin.
func TestFromImageFastPathsMatchTheGenericConversion(t *testing.T) {
	rng := rand.New(rand.NewSource(7))
	rect := image.Rect(0, 0, 13, 7)
	inner := image.Rect(2, 1, 9, 5)

	nrgba := image.NewNRGBA(rect)
	rng.Read(nrgba.Pix)
	opaqueNRGBA := image.NewNRGBA(rect)
	rng.Read(opaqueNRGBA.Pix)
	for i := 3; i < len(opaqueNRGBA.Pix); i += 4 {
		opaqueNRGBA.Pix[i] = 255
	}
	opaqueRGBA := image.NewRGBA(rect)
	rng.Read(opaqueRGBA.Pix)
	for i := 3; i < len(opaqueRGBA.Pix); i += 4 {
		opaqueRGBA.Pix[i] = 255
	}
	translucentRGBA := image.NewRGBA(rect)
	for i := 0; i < len(translucentRGBA.Pix); i += 4 { // valid premultiplied samples
		a := byte(rng.Intn(256))
		translucentRGBA.Pix[i], translucentRGBA.Pix[i+1], translucentRGBA.Pix[i+2], translucentRGBA.Pix[i+3] =
			byte(rng.Intn(int(a)+1)), byte(rng.Intn(int(a)+1)), byte(rng.Intn(int(a)+1)), a
	}
	gray := image.NewGray(rect)
	rng.Read(gray.Pix)

	images := map[string]image.Image{
		"nrgba":              nrgba,
		"nrgba opaque":       opaqueNRGBA,
		"nrgba sub-image":    nrgba.SubImage(inner),
		"nrgba opaque sub":   opaqueNRGBA.SubImage(inner),
		"rgba opaque":        opaqueRGBA,
		"rgba opaque sub":    opaqueRGBA.SubImage(inner),
		"rgba translucent":   translucentRGBA,
		"gray":               gray,
		"gray sub-image":     gray.SubImage(inner),
		"ycbcr 4:2:0":        newYCbCr(rng, rect, image.YCbCrSubsampleRatio420),
		"ycbcr 4:2:2":        newYCbCr(rng, rect, image.YCbCrSubsampleRatio422),
		"ycbcr 4:4:4":        newYCbCr(rng, rect, image.YCbCrSubsampleRatio444),
		"ycbcr 4:2:0 sub":    newYCbCr(rng, rect, image.YCbCrSubsampleRatio420).SubImage(inner),
		"ycbcr 4:4:0":        newYCbCr(rng, rect, image.YCbCrSubsampleRatio440),
		"paletted (At path)": newPaletted(rng, rect),
	}
	for name, img := range images {
		samePAM(t, name, FromImage(img), fromGeneric(img))
	}
}

func newYCbCr(rng *rand.Rand, rect image.Rectangle, ratio image.YCbCrSubsampleRatio) *image.YCbCr {
	img := image.NewYCbCr(rect, ratio)
	rng.Read(img.Y)
	rng.Read(img.Cb)
	rng.Read(img.Cr)
	return img
}

func newPaletted(rng *rand.Rand, rect image.Rectangle) *image.Paletted {
	palette := color.Palette{
		color.NRGBA{255, 0, 0, 255}, color.NRGBA{0, 255, 0, 128}, color.NRGBA{0, 0, 255, 0}, color.NRGBA{9, 9, 9, 255},
	}
	img := image.NewPaletted(rect, palette)
	for i := range img.Pix {
		img.Pix[i] = uint8(rng.Intn(len(palette)))
	}
	return img
}

func TestFromImageRoundsSixteenBitSamples(t *testing.T) {
	// round(v/257), computed independently as (v*255 + 32767) / 65535.
	want := func(v uint32) byte { return byte((v*255 + 32767) / 65535) }

	samples := []uint32{0, 1, 127, 128, 255, 256, 257, 0x00FF, 0x01FF, 0x7FFF, 0x8000, 0xABCD, 0xFE01, 0xFFFE, 0xFFFF}
	rect := image.Rect(0, 0, len(samples), 1)

	gray16 := image.NewGray16(rect)
	nrgba64 := image.NewNRGBA64(rect)
	rgba64 := image.NewRGBA64(rect)
	for i, v := range samples {
		gray16.SetGray16(i, 0, color.Gray16{Y: uint16(v)})
		nrgba64.SetNRGBA64(i, 0, color.NRGBA64{R: uint16(v), G: uint16(v), B: uint16(v), A: 0xFFFF})
		rgba64.SetRGBA64(i, 0, color.RGBA64{R: uint16(v), G: uint16(v), B: uint16(v), A: 0xFFFF})
	}

	for name, img := range map[string]image.Image{"gray16": gray16, "nrgba64": nrgba64, "rgba64": rgba64} {
		got := FromImage(img)
		if got.Depth != 3 {
			t.Fatalf("%s: opaque image should be depth 3, got %d", name, got.Depth)
		}
		for i, v := range samples {
			for c := 0; c < 3; c++ {
				if g := got.Pix[i*3+c]; g != want(v) {
					t.Errorf("%s: sample %#x channel %d: got %d, want %d", name, v, c, g, want(v))
				}
			}
		}
	}

	// 8-bit values expanded to 16 bits (v*257) must come back unchanged.
	exact := image.NewNRGBA64(image.Rect(0, 0, 256, 1))
	for v := 0; v < 256; v++ {
		exact.SetNRGBA64(v, 0, color.NRGBA64{R: uint16(v * 257), G: uint16(v * 257), B: uint16(v * 257), A: 0xFFFF})
	}
	back := FromImage(exact)
	for v := 0; v < 256; v++ {
		if back.Pix[v*3] != byte(v) {
			t.Fatalf("8-bit value %d expanded to 16 bits came back as %d", v, back.Pix[v*3])
		}
	}
}

func TestFromImageSixteenBitAlpha(t *testing.T) {
	rect := image.Rect(0, 0, 2, 1)

	straight := image.NewNRGBA64(rect)
	straight.SetNRGBA64(0, 0, color.NRGBA64{R: 0xFFFF, G: 0x8000, B: 0x0000, A: 0x8000})
	straight.SetNRGBA64(1, 0, color.NRGBA64{R: 0x0100, G: 0x0200, B: 0x0300, A: 0xFFFF})
	got := FromImage(straight)
	want := []byte{255, 128, 0, 128, 1, 2, 3, 255}
	if got.Depth != 4 || !bytes.Equal(got.Pix, want) {
		t.Errorf("nrgba64: got depth %d %v, want depth 4 %v", got.Depth, got.Pix, want)
	}

	// Premultiplied input is divided by alpha in 16 bits first, with integer division like
	// color.NRGBAModel: 0x8000*0xFFFF/0x8000 = 0xFFFF (255) and 0x4000*0xFFFF/0x8000 = 0x7FFF (127).
	premult := image.NewRGBA64(rect)
	premult.SetRGBA64(0, 0, color.RGBA64{R: 0x8000, G: 0x4000, B: 0, A: 0x8000})
	premult.SetRGBA64(1, 0, color.RGBA64{A: 0xFFFF})
	got = FromImage(premult)
	want = []byte{255, 127, 0, 128, 0, 0, 0, 255}
	if got.Depth != 4 || !bytes.Equal(got.Pix, want) {
		t.Errorf("rgba64 premultiplied: got depth %d %v, want depth 4 %v", got.Depth, got.Pix, want)
	}
}

func BenchmarkFromImage(b *testing.B) {
	rect := image.Rect(0, 0, 1024, 1024)
	rng := rand.New(rand.NewSource(1))
	ycbcr := newYCbCr(rng, rect, image.YCbCrSubsampleRatio420)
	nrgba := image.NewNRGBA(rect)
	for i := range nrgba.Pix {
		nrgba.Pix[i] = 255
	}

	for name, img := range map[string]image.Image{"ycbcr": ycbcr, "nrgba opaque": nrgba} {
		b.Run(name+"/fast", func(b *testing.B) {
			b.ReportAllocs()
			for i := 0; i < b.N; i++ {
				_ = FromImage(img)
			}
		})
		b.Run(name+"/generic", func(b *testing.B) {
			b.ReportAllocs()
			for i := 0; i < b.N; i++ {
				_ = fromGeneric(img)
			}
		})
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
