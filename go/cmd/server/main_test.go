package main

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"runtime"
	"strconv"
	"strings"
	"testing"

	"github.com/image-processor-arena/go/internal/pam"
)

func loadSamplePAM(t *testing.T) []byte {
	t.Helper()
	pamPath := "../../../harness/fixtures/synthetic/solid_red.pam"
	data, err := os.ReadFile(pamPath)
	if err != nil {
		t.Fatalf("Failed to read fixture: %v", err)
	}
	return data
}

func TestHealthEndpoint(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rr := httptest.NewRecorder()

	handleHealth(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("Expected status 200, got %d", rr.Code)
	}
	if ct := rr.Header().Get("Content-Type"); ct != "application/json" {
		t.Fatalf("Expected application/json, got %q", ct)
	}
	var resp map[string]string
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Failed to parse JSON: %v", err)
	}
	if resp["status"] != "ok" {
		t.Fatalf("Expected status 'ok', got %q", resp["status"])
	}
}

func TestRunAnalyze(t *testing.T) {
	pamData := loadSamplePAM(t)
	req := httptest.NewRequest(http.MethodPost, "/run?op=analyze", bytes.NewReader(pamData))
	rr := httptest.NewRecorder()

	handleRun(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("Expected status 200, got %d: %s", rr.Code, rr.Body.String())
	}
	if ns := rr.Header().Get("X-Arena-Analyze-Ns"); ns == "" {
		t.Fatalf("Missing X-Arena-Analyze-Ns header")
	}
	var res map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &res); err != nil {
		t.Fatalf("Failed to parse analyze JSON: %v", err)
	}
	if int(res["width"].(float64)) != 64 || int(res["height"].(float64)) != 64 {
		t.Fatalf("Unexpected dimensions: %v x %v", res["width"], res["height"])
	}
}

func TestRunEncodeDecodeTranscode(t *testing.T) {
	pamData := loadSamplePAM(t)

	// 1. Encode PAM to PNG
	reqEnc := httptest.NewRequest(http.MethodPost, "/run?op=encode&format=png", bytes.NewReader(pamData))
	rrEnc := httptest.NewRecorder()
	handleRun(rrEnc, reqEnc)

	if rrEnc.Code != http.StatusOK {
		t.Fatalf("Encode failed: %d: %s", rrEnc.Code, rrEnc.Body.String())
	}
	if ns := rrEnc.Header().Get("X-Arena-Encode-Ns"); ns == "" {
		t.Fatalf("Missing X-Arena-Encode-Ns header")
	}
	pngBytes := rrEnc.Body.Bytes()
	if len(pngBytes) == 0 {
		t.Fatalf("Empty PNG bytes")
	}

	// 2. Decode PNG to PAM
	reqDec := httptest.NewRequest(http.MethodPost, "/run?op=decode&format=png", bytes.NewReader(pngBytes))
	rrDec := httptest.NewRecorder()
	handleRun(rrDec, reqDec)

	if rrDec.Code != http.StatusOK {
		t.Fatalf("Decode failed: %d: %s", rrDec.Code, rrDec.Body.String())
	}
	if ns := rrDec.Header().Get("X-Arena-Decode-Ns"); ns == "" {
		t.Fatalf("Missing X-Arena-Decode-Ns header")
	}
	decPAM, err := pam.Decode(bytes.NewReader(rrDec.Body.Bytes()))
	if err != nil {
		t.Fatalf("Failed to parse decoded PAM: %v", err)
	}
	if decPAM.Width != 64 || decPAM.Height != 64 {
		t.Fatalf("Decoded PAM dimensions mismatch")
	}

	// 3. Transcode PNG to WebP
	reqTrans := httptest.NewRequest(http.MethodPost, "/run?op=transcode&format=png&to=webp", bytes.NewReader(pngBytes))
	rrTrans := httptest.NewRecorder()
	handleRun(rrTrans, reqTrans)

	if rrTrans.Code != http.StatusOK {
		t.Fatalf("Transcode failed: %d: %s", rrTrans.Code, rrTrans.Body.String())
	}
	if ns := rrTrans.Header().Get("X-Arena-Decode-Ns"); ns == "" {
		t.Fatalf("Missing X-Arena-Decode-Ns header in transcode")
	}
	if ns := rrTrans.Header().Get("X-Arena-Encode-Ns"); ns == "" {
		t.Fatalf("Missing X-Arena-Encode-Ns header in transcode")
	}
	if ct := rrTrans.Header().Get("Content-Type"); ct != "image/webp" {
		t.Fatalf("Expected image/webp, got %q", ct)
	}
}

func postRun(t *testing.T, query string, body []byte) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/run?"+query, bytes.NewReader(body))
	rr := httptest.NewRecorder()
	handleRun(rr, req)
	return rr
}

func TestRunRejectsParamsOutsideContract(t *testing.T) {
	pamData := loadSamplePAM(t)
	encoded := postRun(t, "op=encode&format=png", pamData).Body.Bytes()

	for _, params := range []string{
		"q=0", "q=101", "q=300", "q=-1", "q=abc",
		"effort=0", "effort=11", "effort=fast",
		"mode=near-lossless",
	} {
		for _, target := range []struct {
			query string
			body  []byte
		}{
			{"op=encode&format=webp&" + params, pamData},
			{"op=transcode&format=png&to=webp&" + params, encoded},
		} {
			if rr := postRun(t, target.query, target.body); rr.Code != http.StatusBadRequest {
				t.Errorf("%s: expected 400, got %d", target.query, rr.Code)
			}
		}
	}

	if rr := postRun(t, "op=encode&format=bmp", pamData); rr.Code != http.StatusBadRequest {
		t.Errorf("unknown format: expected 400, got %d", rr.Code)
	}
}

func withLimits(t *testing.T, l limits) {
	t.Helper()
	old := srvLimits
	srvLimits = l
	t.Cleanup(func() { srvLimits = old })
}

func TestRunRejectsHugePAMHeaderWithoutAllocating(t *testing.T) {
	header := []byte("P7\nWIDTH 100000\nHEIGHT 100000\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n")

	var before, after runtime.MemStats
	runtime.GC()
	runtime.ReadMemStats(&before)
	rr := postRun(t, "op=encode&format=png", header)
	runtime.ReadMemStats(&after)

	if rr.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d: %s", rr.Code, rr.Body.String())
	}
	if alloc := after.TotalAlloc - before.TotalAlloc; alloc > 4<<20 {
		t.Fatalf("allocated %d bytes before refusing the header", alloc)
	}
}

func TestRunRejectsBodyAboveTheLimit(t *testing.T) {
	pamData := loadSamplePAM(t)
	withLimits(t, limits{maxBodyBytes: int64(len(pamData)) - 1, maxPixels: defaultMaxPixels})

	for _, query := range []string{"op=analyze", "op=encode&format=png", "op=decode&format=png"} {
		if rr := postRun(t, query, pamData); rr.Code != http.StatusRequestEntityTooLarge {
			t.Errorf("%s: expected 413, got %d", query, rr.Code)
		}
	}

	withLimits(t, limits{maxBodyBytes: int64(len(pamData)), maxPixels: defaultMaxPixels})
	if rr := postRun(t, "op=analyze", pamData); rr.Code != http.StatusOK {
		t.Errorf("body exactly at the limit: expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestRunRejectsOversizedContentLengthWithoutReading(t *testing.T) {
	withLimits(t, limits{maxBodyBytes: 1024, maxPixels: defaultMaxPixels})

	req := httptest.NewRequest(http.MethodPost, "/run?op=analyze", io.LimitReader(zeroReader{}, 1<<30))
	req.ContentLength = 1 << 30
	rr := httptest.NewRecorder()
	handleRun(rr, req)

	if rr.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("expected 413, got %d", rr.Code)
	}
}

type zeroReader struct{}

func (zeroReader) Read(p []byte) (int, error) { return len(p), nil }

func TestRunHonoursThePixelLimit(t *testing.T) {
	pamData := loadSamplePAM(t) // 64x64
	withLimits(t, limits{maxBodyBytes: defaultMaxBodyBytes, maxPixels: 64*64 - 1})

	if rr := postRun(t, "op=encode&format=png", pamData); rr.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", rr.Code)
	}
}

func TestRunClientErrorsAreNot500(t *testing.T) {
	pamData := loadSamplePAM(t)
	encoded := postRun(t, "op=encode&format=png", pamData).Body.Bytes()

	cases := []struct {
		name  string
		query string
		body  []byte
	}{
		{"unknown encode format", "op=encode&format=bmp", pamData},
		{"unknown decode format", "op=decode&format=bmp", encoded},
		{"unknown transcode source", "op=transcode&format=bmp&to=png", encoded},
		{"unknown transcode target", "op=transcode&format=png&to=bmp", encoded},
		{"avif lossless encode", "op=encode&format=avif&mode=lossless", pamData},
		{"avif lossless transcode", "op=transcode&format=png&to=avif&mode=lossless", encoded},
		{"unknown op", "op=resize", pamData},
		{"missing format", "op=encode", pamData},
	}
	for _, tc := range cases {
		if rr := postRun(t, tc.query, tc.body); rr.Code != http.StatusBadRequest {
			t.Errorf("%s: expected 400, got %d: %s", tc.name, rr.Code, rr.Body.String())
		}
	}
}

func rgbPAM(width, height int) []byte {
	return pam.EncodeBytes(&pam.Image{
		Width: width, Height: height, Depth: 3, MaxVal: 255, TuplType: "RGB",
		Pix: make([]byte, width*height*3),
	})
}

func TestRunFormatSideLimitsAreClientErrors(t *testing.T) {
	cases := []struct {
		name  string
		query string
		body  []byte
	}{
		{"jpeg 70000x1", "op=encode&format=jpeg", rgbPAM(70000, 1)},
		{"webp lossy 16384x1", "op=encode&format=webp&mode=lossy", rgbPAM(16384, 1)},
		{"webp lossless 16384x1", "op=encode&format=webp&mode=lossless", rgbPAM(16384, 1)},
	}
	for _, tc := range cases {
		if rr := postRun(t, tc.query, tc.body); rr.Code != http.StatusBadRequest {
			t.Errorf("%s: expected 400, got %d: %s", tc.name, rr.Code, rr.Body.String())
		}
	}

	// One pixel under each ceiling still encodes.
	if rr := postRun(t, "op=encode&format=jpeg", rgbPAM(65535, 1)); rr.Code != http.StatusOK {
		t.Errorf("jpeg 65535x1: expected 200, got %d: %s", rr.Code, rr.Body.String())
	}
}

func TestLimitDefaultsMatchArenaToml(t *testing.T) {
	raw, err := os.ReadFile("../../../arena.toml")
	if err != nil {
		t.Fatalf("read arena.toml: %v", err)
	}
	found := map[string]string{}
	inLimits := false
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "[") {
			inLimits = line == "[limits]"
			continue
		}
		if key, value, ok := strings.Cut(line, "="); inLimits && ok && !strings.HasPrefix(line, "#") {
			found[strings.TrimSpace(key)] = strings.TrimSpace(value)
		}
	}
	if got, want := found["max_body_bytes"], strconv.FormatInt(defaultMaxBodyBytes, 10); got != want {
		t.Errorf("max_body_bytes: arena.toml has %q, server default is %q", got, want)
	}
	if got, want := found["max_pixels"], strconv.Itoa(defaultMaxPixels); got != want {
		t.Errorf("max_pixels: arena.toml has %q, server default is %q", got, want)
	}
}

func TestLoadLimits(t *testing.T) {
	env := func(vars map[string]string) func(string) string {
		return func(key string) string { return vars[key] }
	}

	l, err := loadLimits(env(nil))
	if err != nil || l.maxBodyBytes != defaultMaxBodyBytes || l.maxPixels != defaultMaxPixels {
		t.Fatalf("defaults: got %+v, err=%v", l, err)
	}

	l, err = loadLimits(env(map[string]string{envMaxBodyBytes: "1024", envMaxPixels: "256"}))
	if err != nil || l.maxBodyBytes != 1024 || l.maxPixels != 256 {
		t.Fatalf("overrides: got %+v, err=%v", l, err)
	}

	for _, vars := range []map[string]string{
		{envMaxBodyBytes: "0"}, {envMaxBodyBytes: "-1"}, {envMaxBodyBytes: "lots"},
		{envMaxPixels: "0"}, {envMaxPixels: "1.5"},
	} {
		if _, err := loadLimits(env(vars)); err == nil {
			t.Errorf("%v: expected an error", vars)
		}
	}
}

func TestServerHasTimeouts(t *testing.T) {
	s := newServer(":0")
	if s.ReadHeaderTimeout <= 0 || s.ReadTimeout <= 0 || s.WriteTimeout <= 0 || s.IdleTimeout <= 0 || s.MaxHeaderBytes <= 0 {
		t.Fatalf("server must set every timeout and MaxHeaderBytes: %+v", s)
	}
}

func TestRunDefaultsMatchTheContract(t *testing.T) {
	pamData := loadSamplePAM(t)
	for _, format := range []string{"png", "jpeg", "webp", "jxl"} {
		implicit := postRun(t, "op=encode&format="+format, pamData)
		explicit := postRun(t, "op=encode&format="+format+"&mode=lossy&q=75&effort=4", pamData)
		if implicit.Code != http.StatusOK || explicit.Code != http.StatusOK {
			t.Fatalf("%s: implicit %d, explicit %d", format, implicit.Code, explicit.Code)
		}
		if !bytes.Equal(implicit.Body.Bytes(), explicit.Body.Bytes()) {
			t.Errorf("%s: omitted params must behave as mode=lossy q=75 effort=4", format)
		}
	}
}

func TestRunEmptyParamsSelectDefaults(t *testing.T) {
	pamData := loadSamplePAM(t)
	implicit := postRun(t, "op=encode&format=webp", pamData)
	empty := postRun(t, "op=encode&format=webp&mode=&q=&effort=", pamData)
	if empty.Code != http.StatusOK || !bytes.Equal(implicit.Body.Bytes(), empty.Body.Bytes()) {
		t.Errorf("empty params must equal omitted params, got status %d", empty.Code)
	}
}
