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
