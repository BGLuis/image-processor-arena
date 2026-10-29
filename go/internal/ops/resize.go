package ops

import (
	"errors"
	"fmt"
	"image"
	"math"
	"strings"

	"github.com/disintegration/imaging"
	"github.com/image-processor-arena/go/internal/pam"
	"golang.org/x/image/draw"
)

var (
	ErrInvalidParam = errors.New("ops: invalid parameter")
)

var lanczos3Kernel = &draw.Kernel{
	Support: 3,
	At: func(t float64) float64 {
		if t < 0 {
			t = -t
		}
		if t < 1e-5 {
			return 1.0
		}
		if t >= 3.0 {
			return 0.0
		}
		piT := math.Pi * t
		return (math.Sin(piT) / piT) * (math.Sin(piT/3.0) / (piT / 3.0))
	},
}

func Resize(src *pam.Image, targetW, targetH int, filterName, impl string) (*pam.Image, error) {
	if targetW <= 0 || targetH <= 0 {
		return nil, fmt.Errorf("%w: dimensions must be positive, got %dx%d", ErrInvalidParam, targetW, targetH)
	}
	f := strings.ToLower(strings.TrimSpace(filterName))
	if f == "" {
		f = "lanczos3"
	}

	switch strings.ToLower(strings.TrimSpace(impl)) {
	case "", "xdraw", "draw":
		var scaler draw.Interpolator
		switch f {
		case "lanczos3", "lanczos":
			scaler = lanczos3Kernel
		case "catmullrom", "bicubic":
			scaler = draw.CatmullRom
		case "bilinear", "linear":
			scaler = draw.BiLinear
		case "nearest", "box":
			scaler = draw.NearestNeighbor
		default:
			return nil, fmt.Errorf("%w: unknown resize filter: %q", ErrInvalidParam, filterName)
		}

		dst := image.NewNRGBA(image.Rect(0, 0, targetW, targetH))
		srcImg := src.ToNRGBA()
		scaler.Scale(dst, dst.Bounds(), srcImg, srcImg.Bounds(), draw.Over, nil)
		return pam.FromImage(dst), nil

	case "imaging":
		var resampleFilter imaging.ResampleFilter
		switch f {
		case "lanczos3", "lanczos":
			resampleFilter = imaging.Lanczos
		case "catmullrom", "bicubic":
			resampleFilter = imaging.CatmullRom
		case "bilinear", "linear":
			resampleFilter = imaging.Linear
		case "nearest":
			resampleFilter = imaging.NearestNeighbor
		case "box":
			resampleFilter = imaging.Box
		default:
			return nil, fmt.Errorf("%w: unknown resize filter: %q", ErrInvalidParam, filterName)
		}

		srcImg := src.ToNRGBA()
		dst := imaging.Resize(srcImg, targetW, targetH, resampleFilter)
		return pam.FromImage(dst), nil

	default:
		return nil, fmt.Errorf("%w: unknown resize impl: %q", ErrInvalidParam, impl)
	}
}
