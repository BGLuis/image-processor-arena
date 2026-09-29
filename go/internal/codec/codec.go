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
	Effort int    // Effort [1..10], 0 means default
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
	params, err := params.resolve()
	if err != nil {
		return err
	}
	format, q, mode := params.Format, params.Q, params.Mode
	src := encoderInput(pamImg)

	switch format {
	case "png":
		enc := &png.Encoder{
			CompressionLevel: pngCompression(params.Effort),
		}
		return enc.Encode(w, src)

	case "jpeg":
		// Standard library JPEG encoder only supports lossy baseline
		opts := &jpeg.Options{
			Quality: q,
		}
		// image/jpeg handles image.Image, but for RGB without alpha, *image.RGBA or *image.NRGBA is fine.
		return jpeg.Encode(w, src, opts)

	case "webp":
		if mode == "lossless" {
			opts := &gowebp.Options{
				Lossy:             false,
				UseExtendedFormat: true,
			}
			return gowebp.Encode(w, src, opts)
		} else {
			// Lossy WebP with deepteams/webp
			opts := deepwebp.DefaultOptions()
			opts.Lossless = false
			opts.Quality = float32(q)
			opts.Method = webpMethod(params.Effort)
			return deepwebp.Encode(w, src, opts)
		}

	case "avif":
		if mode == "lossless" {
			// goavif ignores Options.Lossless and gav1d/avif always converts RGB to
			// BT.601 4:2:0, so no available pure-Go encoder round-trips RGB exactly.
			return fmt.Errorf("%w: avif lossless", ErrUnsupportedFormat)
		} else {
			// Lossy AVIF with gav1d/avif
			opts := gav1davif.EncodeOptions{
				Quality: q,
				Speed:   avifSpeed(params.Effort),
			}
			return gav1davif.Encode(w, src, opts)
		}

	case "jxl":
		opts := genjxl.EncodeOptions{
			Quality:  q,
			Effort:   jxlEffort(params.Effort),
			Lossless: (mode == "lossless"),
		}
		return genjxl.Encode(w, src, opts)

	default:
		return fmt.Errorf("%w: %q", ErrUnsupportedFormat, format)
	}
}

// encoderInput picks the in-memory layout handed to every encoder: depth 3 becomes an
// opaque *image.RGBA (the encoders then emit no alpha plane and the stdlib JPEG encoder
// takes its RGBA fast path), depth 4 stays straight-alpha *image.NRGBA like the PAM samples.
func encoderInput(pamImg *pam.Image) image.Image {
	nrgba := pamImg.ToNRGBA()
	if pamImg.Depth == 3 {
		return &image.RGBA{Pix: nrgba.Pix, Stride: nrgba.Stride, Rect: nrgba.Rect}
	}
	return nrgba
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
