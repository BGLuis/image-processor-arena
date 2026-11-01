package main

import (
	"bytes"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"runtime/pprof"

	"github.com/image-processor-arena/go/internal/analyze"
	"github.com/image-processor-arena/go/internal/codec"
	"github.com/image-processor-arena/go/internal/ops"
	"github.com/image-processor-arena/go/internal/pam"
)

func findCorpusDir(explicit string) (string, error) {
	if explicit != "" {
		if fi, err := os.Stat(explicit); err == nil && fi.IsDir() {
			return explicit, nil
		}
		return "", fmt.Errorf("specified corpus directory %q not found", explicit)
	}

	candidates := []string{
		"harness/fixtures/corpus",
		"../harness/fixtures/corpus",
		"../../harness/fixtures/corpus",
		"../../../harness/fixtures/corpus",
	}
	for _, c := range candidates {
		if fi, err := os.Stat(c); err == nil && fi.IsDir() {
			return c, nil
		}
	}
	return "", fmt.Errorf("could not locate harness/fixtures/corpus directory")
}

func main() {
	corpusFlag := flag.String("corpus", "", "Path to corpus directory")
	outServerFlag := flag.String("out-server", "cmd/server/default.pgo", "Path for server default.pgo")
	outBatchFlag := flag.String("out-batch", "cmd/batch/default.pgo", "Path for batch default.pgo")
	iterationsFlag := flag.Int("iterations", 3, "Number of workload iterations")
	flag.Parse()

	corpusDir, err := findCorpusDir(*corpusFlag)
	if err != nil {
		log.Fatalf("Error finding corpus: %v", err)
	}
	log.Printf("[pgo_gen] Using corpus from: %s", corpusDir)

	// Load all PAM files and encoded files
	pamFiles, err := filepath.Glob(filepath.Join(corpusDir, "*.pam"))
	if err != nil || len(pamFiles) == 0 {
		log.Fatalf("No .pam files found in %s", corpusDir)
	}

	var pamImages []*pam.Image
	for _, pf := range pamFiles {
		data, err := os.ReadFile(pf)
		if err != nil {
			log.Fatalf("Failed to read %s: %v", pf, err)
		}
		img, err := pam.Decode(bytes.NewReader(data))
		if err != nil {
			log.Fatalf("Failed to decode %s: %v", pf, err)
		}
		pamImages = append(pamImages, img)
	}
	log.Printf("[pgo_gen] Loaded %d PAM images", len(pamImages))

	// Collect encoded files
	var encodedFiles []string
	for _, ext := range []string{"*.png", "*.jpg", "*.webp", "*.avif", "*.jxl"} {
		matches, _ := filepath.Glob(filepath.Join(corpusDir, ext))
		encodedFiles = append(encodedFiles, matches...)
	}
	log.Printf("[pgo_gen] Loaded %d encoded images for decoding workload", len(encodedFiles))

	// Create temporary profile file
	tmpProf, err := os.CreateTemp("", "arena_pgo_*.pprof")
	if err != nil {
		log.Fatalf("Failed to create temp profile file: %v", err)
	}
	tmpProfPath := tmpProf.Name()
	defer os.Remove(tmpProfPath)

	log.Printf("[pgo_gen] Starting CPU profiling into %s...", tmpProfPath)
	if err := pprof.StartCPUProfile(tmpProf); err != nil {
		log.Fatalf("Could not start CPU profile: %v", err)
	}

	formats := []string{"png", "jpeg", "webp", "avif", "jxl"}

	// Run workload
	for iter := 0; iter < *iterationsFlag; iter++ {
		// 1. Analyze PAMs
		for _, img := range pamImages {
			_ = analyze.AnalyzeImage(img)
		}

		// 2. Encode PAMs
		for _, img := range pamImages {
			for _, fmtStr := range formats {
				var buf bytes.Buffer
				p := codec.Params{
					Format: fmtStr,
					Mode:   codec.ModeLossy,
					Q:      75,
					Effort: 4,
				}
				_ = codec.Encode(&buf, img, p)
			}
			// WebP Lossless
			var bufLossless bytes.Buffer
			_ = codec.Encode(&bufLossless, img, codec.Params{
				Format: "webp",
				Mode:   codec.ModeLossless,
				Q:      100,
				Effort: 4,
			})
		}

		// 3. Decode & Transcode encoded files
		for _, ef := range encodedFiles {
			ext := filepath.Ext(ef)
			if len(ext) > 1 {
				fmtStr := ext[1:]
				data, err := os.ReadFile(ef)
				if err == nil {
					decImg, err := codec.Decode(bytes.NewReader(data), fmtStr)
					if err == nil && decImg != nil {
						var transBuf bytes.Buffer
						_ = codec.Encode(&transBuf, decImg, codec.Params{
							Format: "jpeg",
							Mode:   codec.ModeLossy,
							Q:      75,
							Effort: 4,
						})
					}
				}
			}
		}

		// 4. Resize and Filter operations
		for _, img := range pamImages {
			_, _ = ops.Resize(img, 128, 128, "lanczos3", "xdraw")
			_, _ = ops.Filter(img, "blur", 1.0, "imaging")
		}
	}

	pprof.StopCPUProfile()
	_ = tmpProf.Close()
	log.Printf("[pgo_gen] Workload complete, CPU profile recorded.")

	// Copy profile to outServerFlag and outBatchFlag
	profData, err := os.ReadFile(tmpProfPath)
	if err != nil {
		log.Fatalf("Failed to read back profile data: %v", err)
	}

	writeDest := func(destPath string) {
		if destPath == "" {
			return
		}
		if err := os.MkdirAll(filepath.Dir(destPath), 0755); err != nil {
			log.Fatalf("Failed to create dir for %s: %v", destPath, err)
		}
		if err := os.WriteFile(destPath, profData, 0644); err != nil {
			log.Fatalf("Failed to write profile to %s: %v", destPath, err)
		}
		log.Printf("[pgo_gen] Successfully generated PGO profile: %s (%d bytes)", destPath, len(profData))
	}

	writeDest(*outServerFlag)
	writeDest(*outBatchFlag)
}
