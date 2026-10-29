//go:build !noasm && !portable

package codec

import (
	"fmt"
	"image"
	"io"

	deepwebp "github.com/deepteams/webp"
	"github.com/image-processor-arena/go/internal/pam"
)

func init() {
	RegisterEncoder("webp", "deepteams", func(w io.Writer, pamImg *pam.Image, params Params) error {
		if err := checkSide(pamImg, "webp", webpMaxSide); err != nil {
			return err
		}
		if params.Mode == ModeLossless {
			return fmt.Errorf("%w: deepteams does not support lossless webp", ErrUnsupportedFormat)
		}
		src := encoderInput(pamImg)
		opts := deepwebp.DefaultOptions()
		opts.Lossless = false
		opts.Quality = float32(params.Q)
		opts.Method = webpMethod(params.Effort)
		return deepwebp.Encode(w, src, opts)
	})

	RegisterDecoder("webp", "deepteams", func(r io.Reader) (image.Image, error) {
		return deepwebp.Decode(r)
	})
}
