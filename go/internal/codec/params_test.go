package codec

import (
	"bytes"
	"errors"
	"image"
	"image/png"
	"os"
	"strconv"
	"strings"
	"testing"

	"github.com/image-processor-arena/go/internal/pam"
)

// arenaParams reads the [params] table of arena.toml, the contract shared with the Rust engine.
func arenaParams(t *testing.T) map[string]string {
	t.Helper()
	raw, err := os.ReadFile("../../../arena.toml")
	if err != nil {
		t.Fatalf("Failed to read arena.toml: %v", err)
	}
	values := map[string]string{}
	inParams := false
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "[") {
			inParams = line == "[params]"
			continue
		}
		key, value, found := strings.Cut(line, "=")
		if !inParams || !found || strings.HasPrefix(line, "#") {
			continue
		}
		values[strings.TrimSpace(key)] = strings.Trim(strings.TrimSpace(value), `"`)
	}
	return values
}

func TestParamContractMatchesArenaToml(t *testing.T) {
	want := arenaParams(t)
	got := map[string]int{
		"q_default":      DefaultQ,
		"q_min":          MinQ,
		"q_max":          MaxQ,
		"effort_default": DefaultEffort,
		"effort_min":     MinEffort,
		"effort_max":     MaxEffort,
	}
	for key, value := range got {
		if want[key] != strconv.Itoa(value) {
			t.Errorf("%s: code has %d, arena.toml has %q", key, value, want[key])
		}
	}
	if want["mode_default"] != DefaultMode {
		t.Errorf("mode_default: code has %q, arena.toml has %q", DefaultMode, want["mode_default"])
	}

	table := strings.Trim(want["effort_step"], "[]")
	for i, cell := range strings.Split(table, ",") {
		if strings.TrimSpace(cell) != strconv.Itoa(effortStep[i]) {
			t.Errorf("effort_step[%d]: code has %d, arena.toml has %q", i, effortStep[i], strings.TrimSpace(cell))
		}
	}
}

func TestParseParamsDefaults(t *testing.T) {
	for _, format := range []string{"png", "jpeg", "webp", "avif", "jxl"} {
		got, err := ParseParams(format, "", "", "")
		if err != nil {
			t.Fatalf("%s: %v", format, err)
		}
		want := Params{Format: format, Mode: "lossy", Q: 75, Effort: 4}
		if got != want {
			t.Errorf("%s: got %+v, want %+v", format, got, want)
		}
	}
}

func TestParseParamsAcceptsContractBounds(t *testing.T) {
	for _, tc := range []struct{ q, effort string }{{"1", "1"}, {"100", "10"}} {
		if _, err := ParseParams("webp", "lossless", tc.q, tc.effort); err != nil {
			t.Errorf("q=%s effort=%s rejected: %v", tc.q, tc.effort, err)
		}
	}
}

func TestParseParamsRejectsOutsideContract(t *testing.T) {
	cases := []struct {
		name                       string
		format, mode, q, effort    string
		wantUnsupportedFormatError bool
	}{
		{name: "q zero", format: "webp", q: "0"},
		{name: "q above max", format: "webp", q: "101"},
		{name: "q far above max", format: "webp", q: "300"},
		{name: "q negative", format: "webp", q: "-5"},
		{name: "q not a number", format: "webp", q: "abc"},
		{name: "q fractional", format: "webp", q: "7.5"},
		{name: "effort zero", format: "webp", effort: "0"},
		{name: "effort above max", format: "webp", effort: "11"},
		{name: "effort negative", format: "webp", effort: "-1"},
		{name: "effort not a number", format: "webp", effort: "fast"},
		{name: "unknown mode", format: "webp", mode: "near-lossless"},
		{name: "unknown format", format: "bmp", wantUnsupportedFormatError: true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := ParseParams(tc.format, tc.mode, tc.q, tc.effort)
			want := ErrInvalidParams
			if tc.wantUnsupportedFormatError {
				want = ErrUnsupportedFormat
			}
			if !errors.Is(err, want) {
				t.Fatalf("got %v, want %v", err, want)
			}
		})
	}
}

func TestEncodeAppliesTheContractDefaults(t *testing.T) {
	img := getTestPAM(t)
	for _, format := range []string{"png", "jpeg", "webp", "jxl"} {
		var implicit, explicit bytes.Buffer
		if err := Encode(&implicit, img, Params{Format: format}); err != nil {
			t.Fatalf("%s implicit: %v", format, err)
		}
		if err := Encode(&explicit, img, Params{Format: format, Mode: "lossy", Q: 75, Effort: 4}); err != nil {
			t.Fatalf("%s explicit: %v", format, err)
		}
		if !bytes.Equal(implicit.Bytes(), explicit.Bytes()) {
			t.Errorf("%s: zero-value Params must encode exactly like mode=lossy q=75 effort=4", format)
		}
	}
}

func TestEncodeRejectsOutsideContract(t *testing.T) {
	img := getTestPAM(t)
	for _, p := range []Params{
		{Format: "webp", Q: 101},
		{Format: "webp", Q: -1},
		{Format: "webp", Effort: 11},
		{Format: "webp", Effort: -1},
		{Format: "webp", Mode: "nope"},
	} {
		if err := Encode(&bytes.Buffer{}, img, p); !errors.Is(err, ErrInvalidParams) {
			t.Errorf("%+v: got %v, want ErrInvalidParams", p, err)
		}
	}
}

func TestEffortMapping(t *testing.T) {
	wantWebpMethod := []int{0, 1, 1, 2, 3, 3, 4, 5, 5, 6}
	wantJxlEffort := []int{1, 2, 2, 3, 4, 4, 5, 6, 6, 7}
	wantAvifSpeed := []int{10, 9, 8, 7, 6, 5, 4, 3, 2, 1}
	wantPng := []png.CompressionLevel{
		png.BestSpeed, png.BestSpeed,
		png.DefaultCompression, png.DefaultCompression, png.DefaultCompression, png.DefaultCompression,
		png.BestCompression, png.BestCompression, png.BestCompression, png.BestCompression,
	}
	for effort := MinEffort; effort <= MaxEffort; effort++ {
		i := effort - MinEffort
		if got := webpMethod(effort); got != wantWebpMethod[i] {
			t.Errorf("webpMethod(%d) = %d, want %d", effort, got, wantWebpMethod[i])
		}
		if got := jxlEffort(effort); got != wantJxlEffort[i] {
			t.Errorf("jxlEffort(%d) = %d, want %d", effort, got, wantJxlEffort[i])
		}
		if got := avifSpeed(effort); got != wantAvifSpeed[i] {
			t.Errorf("avifSpeed(%d) = %d, want %d", effort, got, wantAvifSpeed[i])
		}
		if got := pngCompression(effort); got != wantPng[i] {
			t.Errorf("pngCompression(%d) = %d, want %d", effort, got, wantPng[i])
		}
	}
}

func loadFixture(t *testing.T, name string) *pam.Image {
	t.Helper()
	data, err := os.ReadFile("../../../harness/fixtures/synthetic/" + name)
	if err != nil {
		t.Fatalf("Failed to read fixture: %v", err)
	}
	img, err := pam.Decode(bytes.NewReader(data))
	if err != nil {
		t.Fatalf("Failed to decode PAM: %v", err)
	}
	return img
}

func TestEncoderInputLayout(t *testing.T) {
	rgb := loadFixture(t, "gradient_h.pam")
	if rgb.Depth != 3 {
		t.Fatalf("fixture gradient_h.pam must be depth 3, got %d", rgb.Depth)
	}
	opaque, ok := encoderInput(rgb).(*image.RGBA)
	if !ok || !opaque.Opaque() {
		t.Errorf("depth 3 must reach the encoders as an opaque *image.RGBA, got %T", encoderInput(rgb))
	}

	rgba := loadFixture(t, "alpha_boxes.pam")
	if rgba.Depth != 4 {
		t.Fatalf("fixture alpha_boxes.pam must be depth 4, got %d", rgba.Depth)
	}
	if _, ok := encoderInput(rgba).(*image.NRGBA); !ok {
		t.Errorf("depth 4 must reach the encoders as *image.NRGBA, got %T", encoderInput(rgba))
	}
}

// AVIF lossless is left out of the depth round-trips: its Go decode path is broken independently of this contract.
var depthRoundTripCases = []struct{ format, mode string }{
	{"png", "lossless"},
	{"webp", "lossy"},
	{"webp", "lossless"},
	{"avif", "lossy"},
	{"jxl", "lossy"},
	{"jxl", "lossless"},
}

func TestDepthRoundTrip(t *testing.T) {
	inputs := []struct {
		fixture string
		depth   int
	}{
		{"gradient_h.pam", 3},
		{"alpha_boxes.pam", 4},
	}
	for _, in := range inputs {
		src := loadFixture(t, in.fixture)
		for _, tc := range depthRoundTripCases {
			var enc bytes.Buffer
			if err := Encode(&enc, src, Params{Format: tc.format, Mode: tc.mode}); err != nil {
				t.Fatalf("%s %s encode: %v", tc.format, tc.mode, err)
			}
			out, err := Decode(bytes.NewReader(enc.Bytes()), tc.format)
			if err != nil {
				t.Fatalf("%s %s decode: %v", tc.format, tc.mode, err)
			}
			if out.Depth != in.depth {
				t.Errorf("%s %s: depth %d in, %d out", tc.format, tc.mode, in.depth, out.Depth)
			}
		}
	}
}

func TestJPEGRoundTripKeepsRGB(t *testing.T) {
	src := loadFixture(t, "gradient_h.pam")
	var enc bytes.Buffer
	if err := Encode(&enc, src, Params{Format: "jpeg"}); err != nil {
		t.Fatal(err)
	}
	out, err := Decode(bytes.NewReader(enc.Bytes()), "jpeg")
	if err != nil {
		t.Fatal(err)
	}
	if out.Depth != 3 {
		t.Errorf("jpeg: depth 3 in, %d out", out.Depth)
	}
}
