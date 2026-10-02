package codec

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"testing"
)

// The fixtures cover layouts the arena encoders never write: indexed and sub-8-bit PNG,
// 16-bit PNG, grayscale JPEG XL and animated WebP. expected.json is shared with the Rust
// engine (rust/tests/decoders.rs), so both must return the same pixels.
type decoderFixture struct {
	Format string `json:"format"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
	Depth  int    `json:"depth"`
	Pixels string `json:"pixels"`
	Error  string `json:"error"`
}

func TestDecodersMatchTheSharedFixtures(t *testing.T) {
	dir := "../../../harness/fixtures/decoders"
	raw, err := os.ReadFile(filepath.Join(dir, "expected.json"))
	if err != nil {
		t.Fatalf("read expected.json: %v", err)
	}
	var expected map[string]decoderFixture
	if err := json.Unmarshal(raw, &expected); err != nil {
		t.Fatalf("parse expected.json: %v", err)
	}
	if len(expected) < 9 {
		t.Fatalf("expected.json has only %d entries", len(expected))
	}

	names := make([]string, 0, len(expected))
	for name := range expected {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		want := expected[name]
		t.Run(name, func(t *testing.T) {
			data, err := os.ReadFile(filepath.Join(dir, name))
			if err != nil {
				t.Fatalf("read fixture: %v", err)
			}
			got, err := Decode(bytes.NewReader(data), want.Format)

			if want.Error != "" {
				if err == nil {
					t.Fatalf("expected the decode to fail (%s), got %dx%d depth %d", want.Error, got.Width, got.Height, got.Depth)
				}
				return
			}
			if err != nil {
				t.Fatalf("decode: %v", err)
			}
			if got.Width != want.Width || got.Height != want.Height || got.Depth != want.Depth {
				t.Fatalf("got %dx%d depth %d, want %dx%d depth %d",
					got.Width, got.Height, got.Depth, want.Width, want.Height, want.Depth)
			}
			if gotHex := hex.EncodeToString(got.Pix); gotHex != want.Pixels {
				t.Fatalf("pixels differ\n got %s\nwant %s", gotHex, want.Pixels)
			}
		})
	}
}
