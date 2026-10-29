package ops_test

import (
	"testing"

	"github.com/image-processor-arena/go/internal/ops"
	"github.com/image-processor-arena/go/internal/pam"
)

func makeTestPAM(w, h, depth int) *pam.Image {
	tupl := "RGB"
	if depth == 4 {
		tupl = "RGB_ALPHA"
	}
	pix := make([]byte, w*h*depth)
	for i := range pix {
		pix[i] = byte((i * 17) % 256)
	}
	return &pam.Image{
		Width:    w,
		Height:   h,
		Depth:    depth,
		MaxVal:   255,
		TuplType: tupl,
		Pix:      pix,
	}
}

func TestResize(t *testing.T) {
	src := makeTestPAM(100, 100, 3)

	filters := []string{"lanczos3", "catmullrom", "bilinear", "nearest"}
	impls := []string{"xdraw", "imaging"}

	for _, impl := range impls {
		for _, f := range filters {
			t.Run(impl+"/"+f, func(t *testing.T) {
				dst, err := ops.Resize(src, 50, 50, f, impl)
				if err != nil {
					t.Fatalf("Resize failed: %v", err)
				}
				if dst.Width != 50 || dst.Height != 50 {
					t.Errorf("expected 50x50, got %dx%d", dst.Width, dst.Height)
				}
				if dst.Depth != 3 {
					t.Errorf("expected depth 3, got %d", dst.Depth)
				}
			})
		}
	}
}

func TestResizeRGBA(t *testing.T) {
	src := makeTestPAM(64, 64, 4)
	dst, err := ops.Resize(src, 32, 32, "lanczos3", "xdraw")
	if err != nil {
		t.Fatalf("Resize failed: %v", err)
	}
	if dst.Width != 32 || dst.Height != 32 {
		t.Errorf("expected 32x32, got %dx%d", dst.Width, dst.Height)
	}
}

func TestResizeRejectsInvalid(t *testing.T) {
	src := makeTestPAM(10, 10, 3)
	if _, err := ops.Resize(src, -1, 10, "lanczos3", "xdraw"); err == nil {
		t.Error("expected error for negative width")
	}
	if _, err := ops.Resize(src, 10, 0, "lanczos3", "xdraw"); err == nil {
		t.Error("expected error for zero height")
	}
	if _, err := ops.Resize(src, 10, 10, "invalid_filter", "xdraw"); err == nil {
		t.Error("expected error for invalid filter")
	}
	if _, err := ops.Resize(src, 10, 10, "lanczos3", "invalid_impl"); err == nil {
		t.Error("expected error for invalid impl")
	}
}

func TestFilter(t *testing.T) {
	src := makeTestPAM(50, 50, 3)
	filters := []string{"blur", "sharpen", "grayscale", "invert", "edge"}
	for _, f := range filters {
		t.Run(f, func(t *testing.T) {
			dst, err := ops.Filter(src, f, 1.0, "imaging")
			if err != nil {
				t.Fatalf("Filter %s failed: %v", f, err)
			}
			if dst.Width != 50 || dst.Height != 50 {
				t.Errorf("expected 50x50, got %dx%d", dst.Width, dst.Height)
			}
		})
	}
}
