package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"time"

	"github.com/image-processor-arena/go/internal/analyze"
	"github.com/image-processor-arena/go/internal/codec"
	"github.com/image-processor-arena/go/internal/pam"
)

// The request limits are shared with the Rust server ([limits] in arena.toml) and can be
// overridden through the same environment variables on both.
const (
	envMaxBodyBytes = "ARENA_MAX_BODY_BYTES"
	envMaxPixels    = "ARENA_MAX_PIXELS"

	defaultMaxBodyBytes int64 = 256 << 20
	defaultMaxPixels          = pam.DefaultMaxPixels

	maxHeaderBytes    = 64 << 10
	readHeaderTimeout = 10 * time.Second
	readTimeout       = 2 * time.Minute
	writeTimeout      = 5 * time.Minute
	idleTimeout       = 2 * time.Minute
)

type limits struct {
	maxBodyBytes int64
	maxPixels    int
}

// srvLimits is read by every request; main replaces it once from the environment before serving.
var srvLimits = limits{maxBodyBytes: defaultMaxBodyBytes, maxPixels: defaultMaxPixels}

func loadLimits(getenv func(string) string) (limits, error) {
	l := limits{maxBodyBytes: defaultMaxBodyBytes, maxPixels: defaultMaxPixels}
	if raw := getenv(envMaxBodyBytes); raw != "" {
		v, err := strconv.ParseInt(raw, 10, 64)
		if err != nil || v <= 0 {
			return limits{}, fmt.Errorf("%s must be a positive integer, got %q", envMaxBodyBytes, raw)
		}
		l.maxBodyBytes = v
	}
	if raw := getenv(envMaxPixels); raw != "" {
		v, err := strconv.Atoi(raw)
		if err != nil || v <= 0 {
			return limits{}, fmt.Errorf("%s must be a positive integer, got %q", envMaxPixels, raw)
		}
		l.maxPixels = v
	}
	return l, nil
}

func main() {
	defaultPort := "8080"
	if envPort := os.Getenv("PORT"); envPort != "" {
		defaultPort = envPort
	}

	portFlag := flag.String("port", defaultPort, "Port to listen on")
	flag.Parse()

	var err error
	if srvLimits, err = loadLimits(os.Getenv); err != nil {
		log.Fatalf("Invalid configuration: %v", err)
	}

	addr := ":" + *portFlag
	log.Printf("[arena-server] Pure Go server listening on %s (PID %d, max body %d B, max %d px)",
		addr, os.Getpid(), srvLimits.maxBodyBytes, srvLimits.maxPixels)

	if err := newServer(addr).ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
}

func newServer(addr string) *http.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", handleHealth)
	mux.HandleFunc("/run", handleRun)

	return &http.Server{
		Addr:              addr,
		Handler:           mux,
		MaxHeaderBytes:    maxHeaderBytes,
		ReadHeaderTimeout: readHeaderTimeout,
		ReadTimeout:       readTimeout,
		WriteTimeout:      writeTimeout,
		IdleTimeout:       idleTimeout,
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

// runRequest is a /run query already checked against the parameter contract, so that nothing
// invalid reaches the decoder or the encoder.
type runRequest struct {
	op     string
	from   string // source format for decode and transcode
	params codec.Params
}

func parseRunRequest(qParams url.Values) (runRequest, error) {
	req := runRequest{op: qParams.Get("op")}
	format := qParams.Get("format")

	switch req.op {
	case "analyze":
	case "encode":
		if format == "" {
			return req, errors.New("Missing 'format' query parameter")
		}
		params, err := codec.ParseParams(format, qParams.Get("mode"), qParams.Get("q"), qParams.Get("effort"))
		if err != nil {
			return req, err
		}
		req.params = params
	case "decode":
		if format == "" {
			return req, errors.New("Missing 'format' query parameter")
		}
		from, err := codec.ParseFormat(format)
		if err != nil {
			return req, err
		}
		req.from = from
	case "transcode":
		to := qParams.Get("to")
		if format == "" || to == "" {
			return req, errors.New("Missing 'format' or 'to' query parameter")
		}
		from, err := codec.ParseFormat(format)
		if err != nil {
			return req, err
		}
		params, err := codec.ParseParams(to, qParams.Get("mode"), qParams.Get("q"), qParams.Get("effort"))
		if err != nil {
			return req, err
		}
		req.from, req.params = from, params
	default:
		return req, fmt.Errorf("Unsupported op: %q", req.op)
	}
	return req, nil
}

// readBody reads at most srvLimits.maxBodyBytes and answers 413 itself when the body is larger.
func readBody(w http.ResponseWriter, r *http.Request) ([]byte, bool) {
	if r.ContentLength > srvLimits.maxBodyBytes {
		tooLarge(w)
		return nil, false
	}

	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, srvLimits.maxBodyBytes))
	_ = r.Body.Close()
	if err != nil {
		var tooBig *http.MaxBytesError
		if errors.As(err, &tooBig) {
			tooLarge(w)
		} else {
			http.Error(w, fmt.Sprintf("Failed to read request body: %v", err), http.StatusBadRequest)
		}
		return nil, false
	}
	if len(body) == 0 {
		http.Error(w, "Empty request body", http.StatusBadRequest)
		return nil, false
	}
	return body, true
}

func tooLarge(w http.ResponseWriter) {
	http.Error(w, fmt.Sprintf("Request body exceeds the %d byte limit (%s)", srvLimits.maxBodyBytes, envMaxBodyBytes),
		http.StatusRequestEntityTooLarge)
}

func decodePAM(w http.ResponseWriter, body []byte) (*pam.Image, bool) {
	img, err := pam.DecodeLimit(bytes.NewReader(body), srvLimits.maxPixels)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to decode PAM body: %v", err), http.StatusBadRequest)
		return nil, false
	}
	return img, true
}

// encodeStatus separates what the client asked for (an unsupported format/mode combination,
// a parameter outside the contract) from a genuine encoder failure.
func encodeStatus(err error) int {
	if errors.Is(err, codec.ErrUnsupportedFormat) || errors.Is(err, codec.ErrInvalidParams) {
		return http.StatusBadRequest
	}
	return http.StatusInternalServerError
}

func handleRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	req, err := parseRunRequest(r.URL.Query())
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	body, ok := readBody(w, r)
	if !ok {
		return
	}

	switch req.op {
	case "analyze":
		pamImg, ok := decodePAM(w, body)
		if !ok {
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
		pamImg, ok := decodePAM(w, body)
		if !ok {
			return
		}

		var encBuf bytes.Buffer

		start := time.Now()
		if err := codec.Encode(&encBuf, pamImg, req.params); err != nil {
			http.Error(w, fmt.Sprintf("Encode error: %v", err), encodeStatus(err))
			return
		}
		encodeNs := time.Since(start).Nanoseconds()

		w.Header().Set("X-Arena-Encode-Ns", strconv.FormatInt(encodeNs, 10))
		w.Header().Set("Content-Type", mimeForFormat(req.params.Format))
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(encBuf.Bytes())

	case "decode":
		start := time.Now()
		pamImg, err := codec.Decode(bytes.NewReader(body), req.from)
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
		startDec := time.Now()
		pamImg, err := codec.Decode(bytes.NewReader(body), req.from)
		if err != nil {
			http.Error(w, fmt.Sprintf("Decode error: %v", err), http.StatusBadRequest)
			return
		}
		decodeNs := time.Since(startDec).Nanoseconds()

		var encBuf bytes.Buffer

		startEnc := time.Now()
		if err := codec.Encode(&encBuf, pamImg, req.params); err != nil {
			http.Error(w, fmt.Sprintf("Encode error: %v", err), encodeStatus(err))
			return
		}
		encodeNs := time.Since(startEnc).Nanoseconds()

		w.Header().Set("X-Arena-Decode-Ns", strconv.FormatInt(decodeNs, 10))
		w.Header().Set("X-Arena-Encode-Ns", strconv.FormatInt(encodeNs, 10))
		w.Header().Set("Content-Type", mimeForFormat(req.params.Format))
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(encBuf.Bytes())
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
