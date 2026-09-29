package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
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
