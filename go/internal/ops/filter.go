package ops

import (
	"fmt"
	"image"
	"strings"

	"github.com/disintegration/imaging"
	"github.com/image-processor-arena/go/internal/pam"
)

func Filter(src *pam.Image, filterName string, sigma float64, impl string) (*pam.Image, error) {
	f := strings.ToLower(strings.TrimSpace(filterName))
	if f == "" {
		return nil, fmt.Errorf("%w: missing filter name", ErrInvalidParam)
	}
	if sigma <= 0 {
		sigma = 1.0
	}

	switch strings.ToLower(strings.TrimSpace(impl)) {
	case "", "imaging":
		srcImg := src.ToNRGBA()
		var dst image.Image
		switch f {
		case "blur", "gaussian_blur":
			dst = imaging.Blur(srcImg, sigma)
		case "sharpen":
			dst = imaging.Sharpen(srcImg, sigma)
		case "grayscale", "gray":
			dst = imaging.Grayscale(srcImg)
		case "invert":
			dst = imaging.Invert(srcImg)
		case "edge", "sobel":
			dst = imaging.Convolve3x3(srcImg, [9]float64{
				-1, 0, 1,
				-2, 0, 2,
				-1, 0, 1,
			}, nil)
		default:
			return nil, fmt.Errorf("%w: unknown filter: %q", ErrInvalidParam, filterName)
		}
		return pam.FromImage(dst), nil

	default:
		return nil, fmt.Errorf("%w: unknown filter impl: %q", ErrInvalidParam, impl)
	}
}
