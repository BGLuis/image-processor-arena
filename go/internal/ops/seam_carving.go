package ops

import (
	"fmt"

	"github.com/esimov/caire"
	"github.com/image-processor-arena/go/internal/pam"
)

func SeamCarve(src *pam.Image, targetW, targetH int) (*pam.Image, error) {
	if targetW <= 0 || targetH <= 0 {
		return nil, fmt.Errorf("%w: target dimensions must be positive, got %dx%d", ErrInvalidParam, targetW, targetH)
	}
	if targetW > src.Width || targetH > src.Height {
		return nil, fmt.Errorf("%w: seam carving reduction: target %dx%d exceeds source %dx%d",
			ErrInvalidParam, targetW, targetH, src.Width, src.Height)
	}

	p := &caire.Processor{
		NewWidth:  targetW,
		NewHeight: targetH,
	}

	res, err := p.Resize(src.ToNRGBA())
	if err != nil {
		return nil, fmt.Errorf("seam carving failed: %w", err)
	}

	return pam.FromImage(res), nil
}
