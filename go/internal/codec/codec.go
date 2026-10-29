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
	gav1davif "github.com/gen2brain/gav1d/avif"
	genjxl "github.com/gen2brain/jxl"
	"github.com/image-processor-arena/go/internal/pam"
	xwebp "golang.org/x/image/webp"
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
	Impl   string // Implementation name, "" means default
}

// Largest side each format can represent. The Rust engine enforces the same ceilings, so a
// request beyond them is a client error (400) in both servers instead of an encoder failure.
const (
	jpegMaxSide = 65535
	webpMaxSide = 16383
)

func checkSide(img *pam.Image, name string, max int) error {
	if img.Width > max || img.Height > max {
		return fmt.Errorf("%w: %s supports at most %d pixels per side, got %dx%d",
			ErrUnsupportedFormat, name, max, img.Width, img.Height)
	}
	return nil
}

// isAnimatedWebP reads the animation flag of the VP8X chunk, the same flag the Rust decoder checks.
func isAnimatedWebP(data []byte) bool {
	return len(data) > 20 &&
		string(data[0:4]) == "RIFF" && string(data[8:12]) == "WEBP" && string(data[12:16]) == "VP8X" &&
		data[20]&0x02 != 0
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

// EncoderAdapter represents an encoding function for a specific library.
type EncoderAdapter func(w io.Writer, pamImg *pam.Image, params Params) error

// DecoderAdapter represents a decoding function for a specific library.
type DecoderAdapter func(r io.Reader) (image.Image, error)

var (
	encoderAdapters = make(map[string]map[string]EncoderAdapter)
	decoderAdapters = make(map[string]map[string]DecoderAdapter)
)

// RegisterEncoder registers an encoder implementation for a given format.
func RegisterEncoder(format, name string, enc EncoderAdapter) {
	format = NormalizeFormat(format)
	name = strings.ToLower(strings.TrimSpace(name))
	if encoderAdapters[format] == nil {
		encoderAdapters[format] = make(map[string]EncoderAdapter)
	}
	encoderAdapters[format][name] = enc
}

// RegisterDecoder registers a decoder implementation for a given format.
func RegisterDecoder(format, name string, dec DecoderAdapter) {
	format = NormalizeFormat(format)
	name = strings.ToLower(strings.TrimSpace(name))
	if decoderAdapters[format] == nil {
		decoderAdapters[format] = make(map[string]DecoderAdapter)
	}
	decoderAdapters[format][name] = dec
}

func init() {
	// PNG
	RegisterEncoder("png", "stdlib", func(w io.Writer, pamImg *pam.Image, params Params) error {
		src := encoderInput(pamImg)
		enc := &png.Encoder{
			CompressionLevel: pngCompression(params.Effort),
		}
		return enc.Encode(w, src)
	})
	RegisterDecoder("png", "stdlib", func(r io.Reader) (image.Image, error) {
		return png.Decode(r)
	})

	// JPEG
	RegisterEncoder("jpeg", "stdlib", func(w io.Writer, pamImg *pam.Image, params Params) error {
		if err := checkSide(pamImg, "jpeg", jpegMaxSide); err != nil {
			return err
		}
		src := encoderInput(pamImg)
		opts := &jpeg.Options{
			Quality: params.Q,
		}
		return jpeg.Encode(w, src, opts)
	})
	RegisterDecoder("jpeg", "stdlib", func(r io.Reader) (image.Image, error) {
		return jpeg.Decode(r)
	})

	// WebP encoders
	RegisterEncoder("webp", "gowebp", func(w io.Writer, pamImg *pam.Image, params Params) error {
		if err := checkSide(pamImg, "webp", webpMaxSide); err != nil {
			return err
		}
		src := encoderInput(pamImg)
		if params.Mode == ModeLossless {
			opts := &gowebp.Options{
				Lossy:             false,
				UseExtendedFormat: false,
			}
			return gowebp.Encode(w, src, opts)
		}
		opts := &gowebp.Options{
			Lossy:             true,
			Quality:           float32(params.Q),
			Method:            webpMethod(params.Effort),
			UseExtendedFormat: true,
		}
		return gowebp.Encode(w, src, opts)
	})

	// WebP decoders
	RegisterDecoder("webp", "gowebp", func(r io.Reader) (image.Image, error) {
		return gowebp.Decode(r)
	})
	RegisterDecoder("webp", "ximage", func(r io.Reader) (image.Image, error) {
		return xwebp.Decode(r)
	})

	// AVIF
	RegisterEncoder("avif", "gav1d", func(w io.Writer, pamImg *pam.Image, params Params) error {
		if params.Mode == ModeLossless {
			return fmt.Errorf("%w: avif lossless", ErrUnsupportedFormat)
		}
		src := encoderInput(pamImg)
		opts := gav1davif.EncodeOptions{
			Quality: params.Q,
			Speed:   avifSpeed(params.Effort),
		}
		return gav1davif.Encode(w, src, opts)
	})
	RegisterDecoder("avif", "gav1d", func(r io.Reader) (image.Image, error) {
		return gav1davif.Decode(r)
	})
	RegisterDecoder("avif", "goavif", func(r io.Reader) (image.Image, error) {
		return goavif.Decode(r)
	})

	// JXL
	RegisterEncoder("jxl", "gen2brain", func(w io.Writer, pamImg *pam.Image, params Params) error {
		src := encoderInput(pamImg)
		opts := genjxl.EncodeOptions{
			Quality:  params.Q,
			Effort:   jxlEffort(params.Effort),
			Lossless: (params.Mode == ModeLossless),
		}
		return genjxl.Encode(w, src, opts)
	})
	RegisterDecoder("jxl", "gen2brain", func(r io.Reader) (image.Image, error) {
		return genjxl.Decode(r)
	})
}

// Encode encodes a PAM image into the target format.
func Encode(w io.Writer, pamImg *pam.Image, params Params) error {
	params, err := params.resolve()
	if err != nil {
		return err
	}
	format := params.Format
	impl := params.Impl
	if impl == "" || impl == "default" {
		if format == "webp" {
			if params.Mode == ModeLossless {
				impl = "gowebp"
			} else {
				impl = "deepteams"
			}
		} else if format == "png" || format == "jpeg" {
			impl = "stdlib"
		} else if format == "avif" {
			impl = "gav1d"
		} else if format == "jxl" {
			impl = "gen2brain"
		}
	}
	if impl == "image/png" || impl == "image/jpeg" {
		impl = "stdlib"
	}
	if impl == "jxl" {
		impl = "gen2brain"
	}

	adapters, ok := encoderAdapters[format]
	if !ok {
		return fmt.Errorf("%w: %q", ErrUnsupportedFormat, format)
	}
	enc, ok := adapters[impl]
	if !ok {
		return fmt.Errorf("%w: unknown encoder implementation %q for %s", ErrInvalidParams, impl, format)
	}
	return enc(w, pamImg, params)
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
func Decode(r io.Reader, format string, impl ...string) (*pam.Image, error) {
	fmtNorm := NormalizeFormat(format)
	if err := ValidateDecoderImpl(fmtNorm, ""); err != nil {
		return nil, err
	}
	implementation := ""
	if len(impl) > 0 {
		implementation = strings.ToLower(strings.TrimSpace(impl[0]))
	}
	if implementation != "" && implementation != "default" {
		if err := ValidateDecoderImpl(fmtNorm, implementation); err != nil {
			return nil, err
		}
	}
	if implementation == "image/png" || implementation == "image/jpeg" {
		implementation = "stdlib"
	}
	if implementation == "golang.org/x/image/webp" {
		implementation = "ximage"
	}
	if implementation == "jxl" {
		implementation = "gen2brain"
	}

	adapters, ok := decoderAdapters[fmtNorm]
	if !ok {
		return nil, fmt.Errorf("%w: %q", ErrUnsupportedFormat, fmtNorm)
	}

	var decoded image.Image
	var err error

	switch fmtNorm {
	case "webp":
		data, readErr := io.ReadAll(r)
		if readErr != nil {
			return nil, readErr
		}
		if isAnimatedWebP(data) {
			return nil, fmt.Errorf("decode webp: animated WebP is not supported")
		}
		if implementation != "" && implementation != "default" {
			dec, ok := adapters[implementation]
			if !ok {
				return nil, fmt.Errorf("%w: unknown decoder implementation %q for webp", ErrInvalidParams, implementation)
			}
			decoded, err = dec(bytes.NewReader(data))
		} else {
			if dec, ok := adapters["deepteams"]; ok {
				decoded, err = dec(bytes.NewReader(data))
			}
			if err != nil || decoded == nil {
				if dec, ok := adapters["gowebp"]; ok {
					decoded, err = dec(bytes.NewReader(data))
				}
			}
		}

	case "avif":
		data, readErr := io.ReadAll(r)
		if readErr != nil {
			return nil, readErr
		}
		if implementation != "" && implementation != "default" {
			dec, ok := adapters[implementation]
			if !ok {
				return nil, fmt.Errorf("%w: unknown decoder implementation %q for avif", ErrInvalidParams, implementation)
			}
			decoded, err = dec(bytes.NewReader(data))
		} else {
			decoded, err = adapters["gav1d"](bytes.NewReader(data))
			if err != nil {
				decoded, err = adapters["goavif"](bytes.NewReader(data))
			}
		}

	default:
		if implementation == "" || implementation == "default" {
			if fmtNorm == "png" || fmtNorm == "jpeg" {
				implementation = "stdlib"
			} else if fmtNorm == "jxl" {
				implementation = "gen2brain"
			}
		}
		dec, ok := adapters[implementation]
		if !ok {
			return nil, fmt.Errorf("%w: unknown decoder implementation %q for %s", ErrInvalidParams, implementation, fmtNorm)
		}
		decoded, err = dec(r)
	}

	if err != nil {
		return nil, fmt.Errorf("decode %s: %w", fmtNorm, err)
	}

	return pam.FromImage(decoded), nil
}
