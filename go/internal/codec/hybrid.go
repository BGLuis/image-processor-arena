//go:build hybrid

package codec

/*
#cgo CFLAGS: -O2
#include <stdlib.h>

static inline int arena_hybrid_available(void) {
    return 1;
}
*/
import "C"

import (
	"io"

	"github.com/image-processor-arena/go/internal/pam"
)

func init() {
	RegisterEncoder("hybrid", "cgo_stub", func(w io.Writer, pamImg *pam.Image, params Params) error {
		_ = C.arena_hybrid_available()
		return nil
	})
}
