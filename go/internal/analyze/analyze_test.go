package analyze

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"

	"github.com/image-processor-arena/go/internal/pam"
)

type GroundTruthResult struct {
	Width       int `json:"width"`
	Height      int `json:"height"`
	AspectRatio struct {
		Str   string  `json:"str"`
		Float float64 `json:"float"`
	} `json:"aspect_ratio"`
	BlockAlignment struct {
		B8   BlockInfo `json:"b8"`
		B16  BlockInfo `json:"b16"`
		B64  BlockInfo `json:"b64"`
		B256 BlockInfo `json:"b256"`
	} `json:"block_alignment"`
	MeanY              float64 `json:"mean_y"`
	EntropyY           float64 `json:"entropy_y"`
	EntropyResidualY   float64 `json:"entropy_residual_y"`
	SpatialInformation float64 `json:"spatial_information"`
	GradientEnergy     float64 `json:"gradient_energy"`
	LaplacianVariance  float64 `json:"laplacian_variance"`
	ColorVariance      struct {
		VarR   float64 `json:"var_r"`
		VarG   float64 `json:"var_g"`
		VarB   float64 `json:"var_b"`
		VarSum float64 `json:"var_sum"`
	} `json:"color_variance"`
	UniqueColors int `json:"unique_colors"`
	Alpha        struct {
		HasAlpha bool    `json:"has_alpha"`
		Sparsity float64 `json:"sparsity"`
		Binarity float64 `json:"binarity"`
	} `json:"alpha"`
	Adequacy420 struct {
		ChromaGradientEnergy float64 `json:"chroma_gradient_energy"`
		ChromaGradientRatio  float64 `json:"chroma_gradient_ratio"`
		MSE_Cb               float64 `json:"mse_cb"`
		MSE_Cr               float64 `json:"mse_cr"`
		MSE_Chroma           float64 `json:"mse_chroma"`
	} `json:"adequacy_420"`
	FlatArea      float64 `json:"flat_area"`
	DominantColor struct {
		DominantRGB [3]int     `json:"dominant_rgb"`
		DominantBin int        `json:"dominant_bin"`
		MeanRGB     [3]float64 `json:"mean_rgb"`
	} `json:"dominant_color"`
	PHash    string `json:"phash"`
	BlurHash string `json:"blurhash"`
}

func checkFloat(t *testing.T, field string, actual, expected, eps float64) {
	t.Helper()
	diff := math.Abs(actual - expected)
	if diff > eps {
		t.Errorf("%s mismatch: got %v, expected %v, diff=%e > eps=%e", field, actual, expected, diff, eps)
	}
}

func TestGroundTruthConformance(t *testing.T) {
	gtPath := "../../../harness/fixtures/ground_truth.json"
	gtBytes, err := os.ReadFile(gtPath)
	if err != nil {
		t.Fatalf("Failed to read ground_truth.json: %v", err)
	}

	var groundTruth map[string]GroundTruthResult
	if err := json.Unmarshal(gtBytes, &groundTruth); err != nil {
		t.Fatalf("Failed to parse ground_truth.json: %v", err)
	}

	fixturesDir := "../../../harness/fixtures/synthetic"

	for fname, exp := range groundTruth {
		t.Run(fname, func(t *testing.T) {
			pamPath := filepath.Join(fixturesDir, fname)
			f, err := os.Open(pamPath)
			if err != nil {
				t.Fatalf("Open failed: %v", err)
			}
			defer f.Close()

			img, err := pam.Decode(f)
			if err != nil {
				t.Fatalf("PAM decode failed: %v", err)
			}

			act := AnalyzeImage(img)

			// Exact dimensions
			if act.Width != exp.Width {
				t.Errorf("Width: got %d, expected %d", act.Width, exp.Width)
			}
			if act.Height != exp.Height {
				t.Errorf("Height: got %d, expected %d", act.Height, exp.Height)
			}

			// Aspect ratio
			if act.AspectRatio.Str != exp.AspectRatio.Str {
				t.Errorf("AspectRatio.Str: got %q, expected %q", act.AspectRatio.Str, exp.AspectRatio.Str)
			}
			checkFloat(t, "AspectRatio.Float", act.AspectRatio.Float, exp.AspectRatio.Float, 1e-6)

			// Block alignment
			type blockCheck struct {
				name string
				act  BlockInfo
				exp  BlockInfo
			}
			blocks := []blockCheck{
				{"b8", act.BlockAlignment.B8, exp.BlockAlignment.B8},
				{"b16", act.BlockAlignment.B16, exp.BlockAlignment.B16},
				{"b64", act.BlockAlignment.B64, exp.BlockAlignment.B64},
				{"b256", act.BlockAlignment.B256, exp.BlockAlignment.B256},
			}
			for _, bc := range blocks {
				if bc.act.WMod != bc.exp.WMod {
					t.Errorf("%s.WMod: got %d, expected %d", bc.name, bc.act.WMod, bc.exp.WMod)
				}
				if bc.act.HMod != bc.exp.HMod {
					t.Errorf("%s.HMod: got %d, expected %d", bc.name, bc.act.HMod, bc.exp.HMod)
				}
				if bc.act.PartialPixels != bc.exp.PartialPixels {
					t.Errorf("%s.PartialPixels: got %d, expected %d", bc.name, bc.act.PartialPixels, bc.exp.PartialPixels)
				}
				checkFloat(t, bc.name+".PartialPct", bc.act.PartialPct, bc.exp.PartialPct, 1e-6)
			}

			// Luminance and Entropies
			checkFloat(t, "MeanY", act.MeanY, exp.MeanY, 1e-4)
			checkFloat(t, "EntropyY", act.EntropyY, exp.EntropyY, 1e-4)
			checkFloat(t, "EntropyResidualY", act.EntropyResidualY, exp.EntropyResidualY, 1e-4)

			// Gradients and Frequency
			checkFloat(t, "SpatialInformation", act.SpatialInformation, exp.SpatialInformation, 1e-3)
			checkFloat(t, "GradientEnergy", act.GradientEnergy, exp.GradientEnergy, 1e-3)
			checkFloat(t, "LaplacianVariance", act.LaplacianVariance, exp.LaplacianVariance, 1e-3)

			// Color Variance
			checkFloat(t, "ColorVariance.VarR", act.ColorVariance.VarR, exp.ColorVariance.VarR, 1e-3)
			checkFloat(t, "ColorVariance.VarG", act.ColorVariance.VarG, exp.ColorVariance.VarG, 1e-3)
			checkFloat(t, "ColorVariance.VarB", act.ColorVariance.VarB, exp.ColorVariance.VarB, 1e-3)
			checkFloat(t, "ColorVariance.VarSum", act.ColorVariance.VarSum, exp.ColorVariance.VarSum, 1e-3)

			// Unique colors (exact)
			if act.UniqueColors != exp.UniqueColors {
				t.Errorf("UniqueColors: got %d, expected %d", act.UniqueColors, exp.UniqueColors)
			}

			// Alpha
			if act.Alpha.HasAlpha != exp.Alpha.HasAlpha {
				t.Errorf("Alpha.HasAlpha: got %v, expected %v", act.Alpha.HasAlpha, exp.Alpha.HasAlpha)
			}
			checkFloat(t, "Alpha.Sparsity", act.Alpha.Sparsity, exp.Alpha.Sparsity, 1e-4)
			checkFloat(t, "Alpha.Binarity", act.Alpha.Binarity, exp.Alpha.Binarity, 1e-4)

			// Adequacy 4:2:0
			checkFloat(t, "Adequacy420.ChromaGradientEnergy", act.Adequacy420.ChromaGradientEnergy, exp.Adequacy420.ChromaGradientEnergy, 1e-3)
			checkFloat(t, "Adequacy420.ChromaGradientRatio", act.Adequacy420.ChromaGradientRatio, exp.Adequacy420.ChromaGradientRatio, 1e-3)
			checkFloat(t, "Adequacy420.MSE_Cb", act.Adequacy420.MSE_Cb, exp.Adequacy420.MSE_Cb, 1e-3)
			checkFloat(t, "Adequacy420.MSE_Cr", act.Adequacy420.MSE_Cr, exp.Adequacy420.MSE_Cr, 1e-3)
			checkFloat(t, "Adequacy420.MSE_Chroma", act.Adequacy420.MSE_Chroma, exp.Adequacy420.MSE_Chroma, 1e-3)

			// Flat area
			checkFloat(t, "FlatArea", act.FlatArea, exp.FlatArea, 1e-4)

			// Dominant color (exact)
			if act.DominantColor.DominantBin != exp.DominantColor.DominantBin {
				t.Errorf("DominantColor.DominantBin: got %d, expected %d", act.DominantColor.DominantBin, exp.DominantColor.DominantBin)
			}
			if act.DominantColor.DominantRGB != exp.DominantColor.DominantRGB {
				t.Errorf("DominantColor.DominantRGB: got %v, expected %v", act.DominantColor.DominantRGB, exp.DominantColor.DominantRGB)
			}
			for ch := 0; ch < 3; ch++ {
				checkFloat(t, "DominantColor.MeanRGB", act.DominantColor.MeanRGB[ch], exp.DominantColor.MeanRGB[ch], 1e-3)
			}

			// pHash (exact 16-hex)
			if act.PHash != exp.PHash {
				t.Errorf("PHash: got %q, expected %q", act.PHash, exp.PHash)
			}

			// BlurHash (exact 28-char)
			if act.BlurHash != exp.BlurHash {
				t.Errorf("BlurHash: got %q, expected %q", act.BlurHash, exp.BlurHash)
			}
		})
	}
}

func BenchmarkAnalyzeImage(b *testing.B) {
	pamPath := "../../../harness/fixtures/synthetic/noise_deterministic.pam"
	f, err := os.Open(pamPath)
	if err != nil {
		b.Fatalf("Failed to open fixture: %v", err)
	}
	defer f.Close()

	img, err := pam.Decode(f)
	if err != nil {
		b.Fatalf("Failed to decode PAM: %v", err)
	}

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = AnalyzeImage(img)
	}
}

func BenchmarkPHash(b *testing.B) {
	yPixels := make([]uint8, 64*64)
	for i := range yPixels {
		yPixels[i] = uint8((i * 17) % 256)
	}

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = ComputePHash(yPixels, 64, 64)
	}
}

func BenchmarkBlurHash(b *testing.B) {
	r := make([]uint8, 64*64)
	g := make([]uint8, 64*64)
	bl := make([]uint8, 64*64)
	for i := range r {
		r[i] = uint8(i % 256)
		g[i] = uint8((i * 3) % 256)
		bl[i] = uint8((i * 7) % 256)
	}

	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = ComputeBlurHash(r, g, bl, 64, 64, 4, 3)
	}
}

