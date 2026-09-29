package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/image-processor-arena/go/internal/analyze"
	"github.com/image-processor-arena/go/internal/codec"
	"github.com/image-processor-arena/go/internal/pam"
)

func main() {
	defaultPort := "8080"
	if envPort := os.Getenv("PORT"); envPort != "" {
		defaultPort = envPort
	}

	portFlag := flag.String("port", defaultPort, "Port to listen on")
	flag.Parse()

	mux := http.NewServeMux()
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/run", handleRun)

	addr := ":" + *portFlag
	log.Printf("[arena-server] Pure Go server listening on %s (PID %d)", addr, os.Getpid())

	server := &http.Server{
		Addr:    addr,
		Handler: mux,
	}

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}

func handleRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	qParams := r.URL.Query()
	op := qParams.Get("op")
	format := qParams.Get("format")
	to := qParams.Get("to")
	mode := qParams.Get("mode")

	bodyBytes, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to read request body: %v", err), http.StatusBadRequest)
		return
	}
	_ = r.Body.Close()

	if len(bodyBytes) == 0 {
		http.Error(w, "Empty request body", http.StatusBadRequest)
		return
	}

	switch op {
	case "analyze":
		// Read PAM image
		pamImg, err := pam.Decode(bytes.NewReader(bodyBytes))
		if err != nil {
			http.Error(w, fmt.Sprintf("Failed to decode PAM body: %v", err), http.StatusBadRequest)
			return
		}

		start := time.Now()
		result := analyze.AnalyzeImage(pamImg)
		analyzeNs := time.Since(start).Nanoseconds()

		respJSON, err := json.Marshal(result)
		if err != nil {
			http.Error(w, fmt.Sprintf("JSON serialization error: %v", err), http.StatusInternalServerError)
			return
		}

		w.Header().Set("X-Arena-Analyze-Ns", strconv.FormatInt(analyzeNs, 10))
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(respJSON)

	case "encode":
		if format == "" {
			http.Error(w, "Missing 'format' query parameter", http.StatusBadRequest)
			return
		}

		encParams, err := codec.ParseParams(format, mode, qParams.Get("q"), qParams.Get("effort"))
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		pamImg, err := pam.Decode(bytes.NewReader(bodyBytes))
		if err != nil {
			http.Error(w, fmt.Sprintf("Failed to decode PAM body: %v", err), http.StatusBadRequest)
			return
		}

		var encBuf bytes.Buffer

		start := time.Now()
		if err := codec.Encode(&encBuf, pamImg, encParams); err != nil {
			http.Error(w, fmt.Sprintf("Encode error: %v", err), http.StatusInternalServerError)
			return
		}
		encodeNs := time.Since(start).Nanoseconds()

		w.Header().Set("X-Arena-Encode-Ns", strconv.FormatInt(encodeNs, 10))
		w.Header().Set("Content-Type", mimeForFormat(format))
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(encBuf.Bytes())

	case "decode":
		if format == "" {
			http.Error(w, "Missing 'format' query parameter", http.StatusBadRequest)
			return
		}

		start := time.Now()
		pamImg, err := codec.Decode(bytes.NewReader(bodyBytes), format)
		if err != nil {
			http.Error(w, fmt.Sprintf("Decode error: %v", err), http.StatusBadRequest)
			return
		}
		decodeNs := time.Since(start).Nanoseconds()

		pamBytes := pam.EncodeBytes(pamImg)

		w.Header().Set("X-Arena-Decode-Ns", strconv.FormatInt(decodeNs, 10))
		w.Header().Set("Content-Type", "image/x-netpbm-pam")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(pamBytes)

	case "transcode":
		if format == "" || to == "" {
			http.Error(w, "Missing 'format' or 'to' query parameter", http.StatusBadRequest)
			return
		}

		encParams, err := codec.ParseParams(to, mode, qParams.Get("q"), qParams.Get("effort"))
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		startDec := time.Now()
		pamImg, err := codec.Decode(bytes.NewReader(bodyBytes), format)
		if err != nil {
			http.Error(w, fmt.Sprintf("Decode error: %v", err), http.StatusBadRequest)
			return
		}
		decodeNs := time.Since(startDec).Nanoseconds()

		var encBuf bytes.Buffer

		startEnc := time.Now()
		if err := codec.Encode(&encBuf, pamImg, encParams); err != nil {
			http.Error(w, fmt.Sprintf("Encode error: %v", err), http.StatusInternalServerError)
			return
		}
		encodeNs := time.Since(startEnc).Nanoseconds()

		w.Header().Set("X-Arena-Decode-Ns", strconv.FormatInt(decodeNs, 10))
		w.Header().Set("X-Arena-Encode-Ns", strconv.FormatInt(encodeNs, 10))
		w.Header().Set("Content-Type", mimeForFormat(to))
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(encBuf.Bytes())

	default:
		http.Error(w, fmt.Sprintf("Unsupported op: %q", op), http.StatusBadRequest)
	}
}

func mimeForFormat(fmtStr string) string {
	switch codec.NormalizeFormat(fmtStr) {
	case "png":
		return "image/png"
	case "jpeg":
		return "image/jpeg"
	case "webp":
		return "image/webp"
	case "avif":
		return "image/avif"
	case "jxl":
		return "image/jxl"
	default:
		return "application/octet-stream"
	}
}
