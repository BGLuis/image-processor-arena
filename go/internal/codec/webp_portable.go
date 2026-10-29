//go:build noasm || portable

package codec

import (
	"image"
	"io"

	"github.com/image-processor-arena/go/internal/pam"
)

func init() {
	RegisterEncoder("webp", "deepteams", func(w io.Writer, pamImg *pam.Image, params Params) error {
		// Em modo portável sem assembly, deepteams utiliza o encoder puro gowebp
		return encoderAdapters["webp"]["gowebp"](w, pamImg, params)
	})

	RegisterDecoder("webp", "deepteams", func(r io.Reader) (image.Image, error) {
		// Em modo portável sem assembly, deepteams utiliza o decoder puro gowebp
		return decoderAdapters["webp"]["gowebp"](r)
	})
}
