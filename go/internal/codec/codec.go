package codec

import (
	"bytes"
	"errors"
	"fmt"
	"image"
	"image/jpeg"
	"image/png"
	"io"
	"strings"

	goavif "github.com/KarpelesLab/goavif"
	gowebp "github.com/KarpelesLab/gowebp"
	deepwebp "github.com/deepteams/webp"
	gav1davif "github.com/gen2brain/gav1d/avif"
	genjxl "github.com/gen2brain/jxl"
	"github.com/image-processor-arena/go/internal/pam"
)

var (
	ErrUnsupportedFormat = errors.New("codec: unsupported format")
	ErrInvalidParams     = errors.New("codec: invalid parameters")
)

// Params defines parameters for image encoding / transcoding.
type Params struct {
	Format string // png, jpeg, jpg, webp, avif, jxl
	Mode   string // lossy or lossless
	Q      int    // Quality [1..100], 0 means default
	Effort int    // Effort / Speed / Method level
}

// NormalizeFormat standardizes format string.
func NormalizeFormat(fmtStr string) string {
	s := strings.ToLower(strings.TrimSpace(fmtStr))
	s = strings.TrimPrefix(s, ".")
	if s == "jpg" {
		return "jpeg"
	}
	return s
}

// Encode encodes a PAM image into the target format.
func Encode(w io.Writer, pamImg *pam.Image, params Params) error {
	format := NormalizeFormat(params.Format)
	q := params.Q
	if q <= 0 {
		q = 75 // reasonable default across codecs
	}
	if q > 100 {
		q = 100
	}

	mode := strings.ToLower(params.Mode)
	if mode == "" {
		if format == "png" {
			mode = "lossless"
		} else {
			mode = "lossy"
		}
	}

	// Codecs work with image.Image. For Depth 3 and 4, pamImg implements image.Image.
	// However, many third-party pure-Go encoders optimize for *image.NRGBA or *image.RGBA.
	// Providing pamImg.ToNRGBA() gives universal compatibility.
	nrgba := pamImg.ToNRGBA()

	switch format {
	case "png":
		enc := &png.Encoder{
			CompressionLevel: png.DefaultCompression,
		}
		if params.Effort > 0 {
			if params.Effort <= 2 {
				enc.CompressionLevel = png.BestSpeed
			} else if params.Effort >= 7 {
				enc.CompressionLevel = png.BestCompression
			} else {
				enc.CompressionLevel = png.DefaultCompression
			}
		}
		return enc.Encode(w, nrgba)

	case "jpeg":
		// Standard library JPEG encoder only supports lossy baseline
		opts := &jpeg.Options{
			Quality: q,
		}
		// image/jpeg handles image.Image, but for RGB without alpha, *image.RGBA or *image.NRGBA is fine.
		return jpeg.Encode(w, nrgba, opts)

	case "webp":
		if mode == "lossless" {
			opts := &gowebp.Options{
				Lossy:             false,
				UseExtendedFormat: true,
			}
			return gowebp.Encode(w, nrgba, opts)
		} else {
			// Lossy WebP with deepteams/webp
			opts := deepwebp.DefaultOptions()
			opts.Lossless = false
			opts.Quality = float32(q)
			if params.Effort >= 0 && params.Effort <= 6 {
				opts.Method = params.Effort
			} else {
				opts.Method = 4
			}
			return deepwebp.Encode(w, nrgba, opts)
		}

	case "avif":
		if mode == "lossless" {
			// goavif ignores Options.Lossless and gav1d/avif always converts RGB to
			// BT.601 4:2:0, so no available pure-Go encoder round-trips RGB exactly.
			return fmt.Errorf("%w: avif lossless", ErrUnsupportedFormat)
		} else {
			// Lossy AVIF with gav1d/avif
			speed := params.Effort
			if speed < 0 || speed > 10 {
				speed = gav1davif.DefaultSpeed
			}
			opts := gav1davif.EncodeOptions{
				Quality: q,
				Speed:   speed,
			}
			return gav1davif.Encode(w, nrgba, opts)
		}

	case "jxl":
		opts := genjxl.EncodeOptions{
			Quality:  q,
			Effort:   params.Effort,
			Lossless: (mode == "lossless"),
		}
		return genjxl.Encode(w, nrgba, opts)

	default:
		return fmt.Errorf("%w: %q", ErrUnsupportedFormat, format)
	}
}

// Decode decodes a compressed image into a Netpbm PAM image.
func Decode(r io.Reader, format string) (*pam.Image, error) {
	fmtNorm := NormalizeFormat(format)

	var decoded image.Image
	var err error

	switch fmtNorm {
	case "png":
		decoded, err = png.Decode(r)
	case "jpeg":
		decoded, err = jpeg.Decode(r)
	case "webp":
		// Read entire stream if needed since some webp decoders require seek or full buffer
		data, readErr := io.ReadAll(r)
		if readErr != nil {
			return nil, readErr
		}
		decoded, err = deepwebp.Decode(bytes.NewReader(data))
		if err != nil {
			// Fallback to gowebp
			decoded, err = gowebp.Decode(bytes.NewReader(data))
		}
	case "avif":
		data, readErr := io.ReadAll(r)
		if readErr != nil {
			return nil, readErr
		}
		decoded, err = gav1davif.Decode(bytes.NewReader(data))
		if err != nil {
			// Fallback to goavif
			decoded, err = goavif.Decode(bytes.NewReader(data))
		}
	case "jxl":
		decoded, err = genjxl.Decode(r)
	default:
		// Attempt standard image.Decode
		decoded, _, err = image.Decode(r)
	}

	if err != nil {
		return nil, fmt.Errorf("decode %s: %w", fmtNorm, err)
	}

	return pam.FromImage(decoded), nil
}
