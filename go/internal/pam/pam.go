package pam

import (
	"bufio"
	"bytes"
	"errors"
	"fmt"
	"image"
	"image/color"
	"io"
	"strconv"
	"strings"
)

var (
	ErrInvalidHeader = errors.New("pam: invalid header")
	ErrUnsupported   = errors.New("pam: unsupported format (only MAXVAL 255 and DEPTH 3 or 4 are supported)")
	ErrTruncated     = errors.New("pam: truncated pixel data")
)

// Image represents a Netpbm PAM (P7) image in memory.
type Image struct {
	Width    int
	Height   int
	Depth    int    // 3 for RGB, 4 for RGB_ALPHA
	MaxVal   int    // 255
	TuplType string // "RGB" or "RGB_ALPHA"
	Pix      []byte // row-major raster data (Width * Height * Depth bytes)
}

// ColorModel returns the standard color model for the PAM image.
func (img *Image) ColorModel() color.Model {
	return color.NRGBAModel
}

// Bounds returns the rectangle domain of the image.
func (img *Image) Bounds() image.Rectangle {
	return image.Rect(0, 0, img.Width, img.Height)
}

// At returns the color of the pixel at (x, y).
func (img *Image) At(x, y int) color.Color {
	if x < 0 || x >= img.Width || y < 0 || y >= img.Height {
		return color.NRGBA{}
	}
	if img.Depth == 3 {
		idx := (y*img.Width + x) * 3
		return color.NRGBA{
			R: img.Pix[idx],
			G: img.Pix[idx+1],
			B: img.Pix[idx+2],
			A: 255,
		}
	} else if img.Depth == 4 {
		idx := (y*img.Width + x) * 4
		return color.NRGBA{
			R: img.Pix[idx],
			G: img.Pix[idx+1],
			B: img.Pix[idx+2],
			A: img.Pix[idx+3],
		}
	}
	return color.NRGBA{}
}

// ToNRGBA converts the PAM image to an *image.NRGBA.
func (img *Image) ToNRGBA() *image.NRGBA {
	nrgba := image.NewNRGBA(image.Rect(0, 0, img.Width, img.Height))
	if img.Depth == 4 {
		copy(nrgba.Pix, img.Pix)
	} else if img.Depth == 3 {
		src := img.Pix
		dst := nrgba.Pix
		sIdx, dIdx := 0, 0
		n := img.Width * img.Height
		for i := 0; i < n; i++ {
			dst[dIdx] = src[sIdx]
			dst[dIdx+1] = src[sIdx+1]
			dst[dIdx+2] = src[sIdx+2]
			dst[dIdx+3] = 255
			sIdx += 3
			dIdx += 4
		}
	}
	return nrgba
}

// FromImage converts any image.Image into a PAM image.
func FromImage(m image.Image) *Image {
	bounds := m.Bounds()
	w, h := bounds.Dx(), bounds.Dy()

	// Check if source is already *image.NRGBA
	if nrgba, ok := m.(*image.NRGBA); ok && nrgba.Rect == bounds && nrgba.Stride == w*4 {
		pixCopy := make([]byte, len(nrgba.Pix))
		copy(pixCopy, nrgba.Pix)
		return &Image{
			Width:    w,
			Height:   h,
			Depth:    4,
			MaxVal:   255,
			TuplType: "RGB_ALPHA",
			Pix:      pixCopy,
		}
	}

	// Check if source image has transparency
	hasAlpha := false
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			_, _, _, a := m.At(x, y).RGBA()
			if a < 0xFFFF {
				hasAlpha = true
				break
			}
		}
		if hasAlpha {
			break
		}
	}

	if hasAlpha {
		pix := make([]byte, w*h*4)
		idx := 0
		for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
			for x := bounds.Min.X; x < bounds.Max.X; x++ {
				c := color.NRGBAModel.Convert(m.At(x, y)).(color.NRGBA)
				pix[idx] = c.R
				pix[idx+1] = c.G
				pix[idx+2] = c.B
				pix[idx+3] = c.A
				idx += 4
			}
		}
		return &Image{
			Width:    w,
			Height:   h,
			Depth:    4,
			MaxVal:   255,
			TuplType: "RGB_ALPHA",
			Pix:      pix,
		}
	}

	// 3-channel RGB
	pix := make([]byte, w*h*3)
	idx := 0
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			c := color.NRGBAModel.Convert(m.At(x, y)).(color.NRGBA)
			pix[idx] = c.R
			pix[idx+1] = c.G
			pix[idx+2] = c.B
			idx += 3
		}
	}
	return &Image{
		Width:    w,
		Height:   h,
		Depth:    3,
		MaxVal:   255,
		TuplType: "RGB",
		Pix:      pix,
	}
}

// Decode reads a Netpbm PAM P7 image from an io.Reader.
func Decode(r io.Reader) (*Image, error) {
	br, ok := r.(*bufio.Reader)
	if !ok {
		br = bufio.NewReader(r)
	}

	magic, err := br.ReadString('\n')
	if err != nil {
		return nil, ErrInvalidHeader
	}
	magic = strings.TrimSpace(magic)
	if magic != "P7" {
		return nil, fmt.Errorf("%w: expected magic P7, got %q", ErrInvalidHeader, magic)
	}

	var (
		width    int
		height   int
		depth    int
		maxval   int
		tupltype string
	)

	for {
		line, err := br.ReadString('\n')
		if err != nil {
			return nil, ErrInvalidHeader
		}
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		if trimmed == "ENDHDR" {
			break
		}

		parts := strings.SplitN(trimmed, " ", 2)
		key := strings.ToUpper(parts[0])
		val := ""
		if len(parts) > 1 {
			val = strings.TrimSpace(parts[1])
		}

		switch key {
		case "WIDTH":
			width, err = strconv.Atoi(val)
			if err != nil || width <= 0 {
				return nil, fmt.Errorf("%w: invalid width %q", ErrInvalidHeader, val)
			}
		case "HEIGHT":
			height, err = strconv.Atoi(val)
			if err != nil || height <= 0 {
				return nil, fmt.Errorf("%w: invalid height %q", ErrInvalidHeader, val)
			}
		case "DEPTH":
			depth, err = strconv.Atoi(val)
			if err != nil {
				return nil, fmt.Errorf("%w: invalid depth %q", ErrInvalidHeader, val)
			}
		case "MAXVAL":
			maxval, err = strconv.Atoi(val)
			if err != nil {
				return nil, fmt.Errorf("%w: invalid maxval %q", ErrInvalidHeader, val)
			}
		case "TUPLTYPE":
			tupltype = val
		}
	}

	if width <= 0 || height <= 0 {
		return nil, fmt.Errorf("%w: missing dimensions", ErrInvalidHeader)
	}
	if maxval != 255 {
		return nil, fmt.Errorf("%w: maxval=%d (only 255 supported)", ErrUnsupported, maxval)
	}
	if depth != 3 && depth != 4 {
		return nil, fmt.Errorf("%w: depth=%d (only 3 or 4 supported)", ErrUnsupported, depth)
	}
	if tupltype == "" {
		if depth == 3 {
			tupltype = "RGB"
		} else {
			tupltype = "RGB_ALPHA"
		}
	}

	totalBytes := width * height * depth
	pix := make([]byte, totalBytes)
	if _, err := io.ReadFull(br, pix); err != nil {
		if errors.Is(err, io.EOF) || errors.Is(err, io.ErrUnexpectedEOF) {
			return nil, ErrTruncated
		}
		return nil, err
	}

	return &Image{
		Width:    width,
		Height:   height,
		Depth:    depth,
		MaxVal:   maxval,
		TuplType: tupltype,
		Pix:      pix,
	}, nil
}

// Encode writes a Netpbm PAM P7 image to an io.Writer.
func Encode(w io.Writer, img *Image) error {
	header := fmt.Sprintf("P7\nWIDTH %d\nHEIGHT %d\nDEPTH %d\nMAXVAL %d\nTUPLTYPE %s\nENDHDR\n",
		img.Width, img.Height, img.Depth, img.MaxVal, img.TuplType)
	if _, err := io.WriteString(w, header); err != nil {
		return err
	}
	_, err := w.Write(img.Pix)
	return err
}

// EncodeBytes returns the complete PAM binary representation as a byte slice.
func EncodeBytes(img *Image) []byte {
	var buf bytes.Buffer
	_ = Encode(&buf, img)
	return buf.Bytes()
}
