//go:build noasm || portable

package codec

import (
	"bytes"
	"image"
	"io"

	"github.com/image-processor-arena/go/internal/pam"
)

func init() {
	RegisterEncoder("webp", "deepteams", func(w io.Writer, pamImg *pam.Image, params Params) error {
		// Em modo portável sem assembly, deepteams utiliza o encoder puro gowebp (tanto lossy quanto lossless)
		return encoderAdapters["webp"]["gowebp"](w, pamImg, params)
	})

	RegisterDecoder("webp", "deepteams", func(r io.Reader) (image.Image, error) {
		// Em modo portável sem assembly, deepteams utiliza gowebp com fallback para ximage
		data, err := io.ReadAll(r)
		if err != nil {
			return nil, err
		}
		img, err := decoderAdapters["webp"]["gowebp"](bytes.NewReader(data))
		if err == nil && img != nil {
			return img, nil
		}
		if xdec, ok := decoderAdapters["webp"]["ximage"]; ok {
			ximg, xerr := xdec(bytes.NewReader(data))
			if xerr == nil && ximg != nil {
				return ximg, nil
			}
		}
		return nil, err
	})
}
