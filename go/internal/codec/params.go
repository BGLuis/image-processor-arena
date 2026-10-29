package codec

import (
	"fmt"
	"image/png"
	"strconv"
	"strings"
)

// The parameter contract is shared with the Rust engine and documented in
// arena.toml ([params]); both engines must keep these values identical.
const (
	ModeLossy    = "lossy"
	ModeLossless = "lossless"

	DefaultMode = ModeLossy

	DefaultQ = 75
	MinQ     = 1
	MaxQ     = 100

	DefaultEffort = 4
	MinEffort     = 1
	MaxEffort     = 10
)

// effortStep maps effort 1..10 onto a 0..6 scale (rounded linear interpolation).
// WebP lossy uses it as the method (0..6) and JXL as the effort minus one (1..7).
var effortStep = [MaxEffort]int{0, 1, 1, 2, 3, 3, 4, 5, 5, 6}

func webpMethod(effort int) int { return effortStep[effort-MinEffort] }

func jxlEffort(effort int) int { return effortStep[effort-MinEffort] + 1 }

// avifSpeed inverts the scale: AVIF speed grows as the encoder gets faster, effort as it gets slower.
func avifSpeed(effort int) int { return MaxEffort + MinEffort - effort }

func pngCompression(effort int) png.CompressionLevel {
	switch {
	case effort <= 2:
		return png.BestSpeed
	case effort <= 6:
		return png.DefaultCompression
	default:
		return png.BestCompression
	}
}

var supportedFormats = map[string]bool{"png": true, "jpeg": true, "webp": true, "avif": true, "jxl": true}

// ParseFormat normalizes a format name and rejects anything the engine cannot decode or encode.
func ParseFormat(format string) (string, error) {
	f := NormalizeFormat(format)
	if !supportedFormats[f] {
		return "", fmt.Errorf("%w: %q", ErrUnsupportedFormat, f)
	}
	return f, nil
}

var validEncoderImpls = map[string]map[string]bool{
	"png":  {"stdlib": true, "image/png": true, "default": true},
	"jpeg": {"stdlib": true, "image/jpeg": true, "default": true},
	"webp": {"deepteams": true, "gowebp": true, "default": true},
	"avif": {"gav1d": true, "goavif": true, "default": true},
	"jxl":  {"gen2brain": true, "jxl": true, "default": true},
}

var validDecoderImpls = map[string]map[string]bool{
	"png":  {"stdlib": true, "image/png": true, "default": true},
	"jpeg": {"stdlib": true, "image/jpeg": true, "default": true},
	"webp": {"deepteams": true, "gowebp": true, "ximage": true, "golang.org/x/image/webp": true, "default": true},
	"avif": {"gav1d": true, "goavif": true, "default": true},
	"jxl":  {"gen2brain": true, "jxl": true, "default": true},
}

// ValidateDecoderImpl checks if the given decoder implementation is valid for the format.
func ValidateDecoderImpl(format, impl string) error {
	f := NormalizeFormat(format)
	if !supportedFormats[f] {
		return fmt.Errorf("%w: %q", ErrUnsupportedFormat, f)
	}
	imp := strings.ToLower(strings.TrimSpace(impl))
	if imp == "" || imp == "default" {
		return nil
	}
	if !validDecoderImpls[f][imp] {
		return fmt.Errorf("%w: unknown implementation %q for format %s", ErrInvalidParams, impl, f)
	}
	return nil
}

// ParseParams builds validated Params from the raw textual values of a request.
// An empty value selects the default; anything outside the contract is rejected, never clamped.
func ParseParams(format, mode, q, effort string, impl ...string) (Params, error) {
	qVal, err := parseBounded("q", q, DefaultQ, MinQ, MaxQ)
	if err != nil {
		return Params{}, err
	}
	effortVal, err := parseBounded("effort", effort, DefaultEffort, MinEffort, MaxEffort)
	if err != nil {
		return Params{}, err
	}
	implementation := ""
	if len(impl) > 0 {
		implementation = impl[0]
	}
	return Params{Format: format, Mode: mode, Q: qVal, Effort: effortVal, Impl: implementation}.resolve()
}

func parseBounded(name, raw string, def, lo, hi int) (int, error) {
	if raw == "" {
		return def, nil
	}
	v, err := strconv.Atoi(raw)
	if err != nil || v < lo || v > hi {
		return 0, fmt.Errorf("%w: %s must be an integer in %d..%d, got %q", ErrInvalidParams, name, lo, hi, raw)
	}
	return v, nil
}

// resolve fills zero values with the defaults and rejects values outside the contract.
func (p Params) resolve() (Params, error) {
	p.Format = NormalizeFormat(p.Format)
	if !supportedFormats[p.Format] {
		return Params{}, fmt.Errorf("%w: %q", ErrUnsupportedFormat, p.Format)
	}

	p.Mode = strings.ToLower(p.Mode)
	switch p.Mode {
	case "":
		p.Mode = DefaultMode
	case ModeLossy, ModeLossless:
	default:
		return Params{}, fmt.Errorf("%w: mode must be %q or %q, got %q", ErrInvalidParams, ModeLossy, ModeLossless, p.Mode)
	}

	if p.Q == 0 {
		p.Q = DefaultQ
	}
	if p.Q < MinQ || p.Q > MaxQ {
		return Params{}, fmt.Errorf("%w: q must be an integer in %d..%d, got %d", ErrInvalidParams, MinQ, MaxQ, p.Q)
	}

	if p.Effort == 0 {
		p.Effort = DefaultEffort
	}
	if p.Effort < MinEffort || p.Effort > MaxEffort {
		return Params{}, fmt.Errorf("%w: effort must be an integer in %d..%d, got %d", ErrInvalidParams, MinEffort, MaxEffort, p.Effort)
	}

	p.Impl = strings.ToLower(strings.TrimSpace(p.Impl))
	if p.Impl != "" && p.Impl != "default" {
		if !validEncoderImpls[p.Format][p.Impl] {
			return Params{}, fmt.Errorf("%w: unknown implementation %q for %s", ErrInvalidParams, p.Impl, p.Format)
		}
	}
	return p, nil
}
