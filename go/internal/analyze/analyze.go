package analyze

import (
	"fmt"
	"math"
	"slices"

	"github.com/image-processor-arena/go/internal/pam"
)

const blurhashChars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~"

// AspectRatio holds aspect ratio representation.
type AspectRatio struct {
	Str   string  `json:"str"`
	Float float64 `json:"float"`
}

// BlockInfo holds block alignment properties for a block size b.
type BlockInfo struct {
	WMod          int     `json:"w_mod"`
	HMod          int     `json:"h_mod"`
	PartialPixels int     `json:"partial_pixels"`
	PartialPct    float64 `json:"partial_pct"`
}

// BlockAlignment holds block alignment metrics for b in {8, 16, 64, 256}.
type BlockAlignment struct {
	B8   BlockInfo `json:"b8"`
	B16  BlockInfo `json:"b16"`
	B64  BlockInfo `json:"b64"`
	B256 BlockInfo `json:"b256"`
}

// ColorVariance holds population variance for RGB channels and their sum.
type ColorVariance struct {
	VarR   float64 `json:"var_r"`
	VarG   float64 `json:"var_g"`
	VarB   float64 `json:"var_b"`
	VarSum float64 `json:"var_sum"`
}

// AlphaMetrics holds transparency metrics.
type AlphaMetrics struct {
	HasAlpha bool    `json:"has_alpha"`
	Sparsity float64 `json:"sparsity"`
	Binarity float64 `json:"binarity"`
}

// Adequacy420 holds metrics indicating suitability for 4:2:0 subsampling.
type Adequacy420 struct {
	ChromaGradientEnergy float64 `json:"chroma_gradient_energy"`
	ChromaGradientRatio  float64 `json:"chroma_gradient_ratio"`
	MSE_Cb               float64 `json:"mse_cb"`
	MSE_Cr               float64 `json:"mse_cr"`
	MSE_Chroma           float64 `json:"mse_chroma"`
}

// DominantColor holds dominant color histogram mode and arithmetic mean.
type DominantColor struct {
	DominantRGB [3]int     `json:"dominant_rgb"`
	DominantBin int        `json:"dominant_bin"`
	MeanRGB     [3]float64 `json:"mean_rgb"`
}

// Result holds the 16 content metrics for op=analyze.
type Result struct {
	Width              int            `json:"width"`
	Height             int            `json:"height"`
	AspectRatio        AspectRatio    `json:"aspect_ratio"`
	BlockAlignment     BlockAlignment `json:"block_alignment"`
	MeanY              float64        `json:"mean_y"`
	EntropyY           float64        `json:"entropy_y"`
	EntropyResidualY   float64        `json:"entropy_residual_y"`
	SpatialInformation float64        `json:"spatial_information"`
	GradientEnergy     float64        `json:"gradient_energy"`
	LaplacianVariance  float64        `json:"laplacian_variance"`
	ColorVariance      ColorVariance  `json:"color_variance"`
	UniqueColors       int            `json:"unique_colors"`
	Alpha              AlphaMetrics   `json:"alpha"`
	Adequacy420        Adequacy420    `json:"adequacy_420"`
	FlatArea           float64        `json:"flat_area"`
	DominantColor      DominantColor  `json:"dominant_color"`
	PHash              string         `json:"phash"`
	BlurHash           string         `json:"blurhash"`
}

func gcd(a, b int) int {
	for b != 0 {
		a, b = b, a%b
	}
	return a
}

func clamp255(v int) uint8 {
	if v < 0 {
		return 0
	}
	if v > 255 {
		return 255
	}
	return uint8(v)
}

func round6(val float64) float64 {
	return math.Round(val*1e6) / 1e6
}

// AnalyzeImage computes all 16 formal image metrics on the given PAM image.
func AnalyzeImage(img *pam.Image) *Result {
	width := img.Width
	height := img.Height
	depth := img.Depth
	numPixels := width * height
	nF := float64(numPixels)

	// Extract R, G, B, A lists
	rList := make([]uint8, numPixels)
	gList := make([]uint8, numPixels)
	bList := make([]uint8, numPixels)
	aList := make([]uint8, numPixels)

	raster := img.Pix
	if depth == 3 {
		for i := 0; i < numPixels; i++ {
			off := i * 3
			rList[i] = raster[off]
			gList[i] = raster[off+1]
			bList[i] = raster[off+2]
			aList[i] = 255
		}
	} else if depth == 4 {
		for i := 0; i < numPixels; i++ {
			off := i * 4
			rList[i] = raster[off]
			gList[i] = raster[off+1]
			bList[i] = raster[off+2]
			aList[i] = raster[off+3]
		}
	}

	// 1. Aspect Ratio
	g := gcd(width, height)
	aspectRatio := AspectRatio{
		Str:   fmt.Sprintf("%d:%d", width/g, height/g),
		Float: float64(width) / float64(height),
	}

	// 2. Block Alignment for b in {8, 16, 64, 256}
	computeBlock := func(b int) BlockInfo {
		fullW := (width / b) * b
		fullH := (height / b) * b
		partialPix := numPixels - (fullW * fullH)
		return BlockInfo{
			WMod:          width % b,
			HMod:          height % b,
			PartialPixels: partialPix,
			PartialPct:    float64(partialPix) / nF,
		}
	}
	blockAlignment := BlockAlignment{
		B8:   computeBlock(8),
		B16:  computeBlock(16),
		B64:  computeBlock(64),
		B256: computeBlock(256),
	}

	// 3. BT.601 integer conversion to Y, Cb, Cr
	yList := make([]uint8, numPixels)
	cbList := make([]uint8, numPixels)
	crList := make([]uint8, numPixels)

	var sumY int64
	var sumR, sumG, sumB int64

	for i := 0; i < numPixels; i++ {
		r := int(rList[i])
		gc := int(gList[i])
		b := int(bList[i])

		sumR += int64(r)
		sumG += int64(gc)
		sumB += int64(b)

		yVal := (77*r + 150*gc + 29*b + 128) >> 8
		cbVal := (((-43*r - 85*gc + 128*b + 128) >> 8) + 128)
		crVal := (((128*r - 107*gc - 21*b + 128) >> 8) + 128)

		y := clamp255(yVal)
		cb := clamp255(cbVal)
		cr := clamp255(crVal)

		yList[i] = y
		cbList[i] = cb
		crList[i] = cr
		sumY += int64(y)
	}

	meanY := float64(sumY) / nF

	// 4. Shannon Entropy of Y
	var histY [256]int
	for _, yv := range yList {
		histY[yv]++
	}
	var entropyY float64
	for _, cnt := range histY {
		if cnt > 0 {
			p := float64(cnt) / nF
			entropyY -= p * math.Log2(p)
		}
	}

	// 5. Horizontal Residual Entropy of Y (Y[x, y] - Y[x-1, y])
	var entropyResidualY float64
	if width > 1 {
		var diffCounts [511]int
		totalDiffs := float64((width - 1) * height)
		for yIdx := 0; yIdx < height; yIdx++ {
			rowOff := yIdx * width
			for xIdx := 1; xIdx < width; xIdx++ {
				diff := int(yList[rowOff+xIdx]) - int(yList[rowOff+xIdx-1])
				diffCounts[diff+255]++
			}
		}
		for _, cnt := range diffCounts {
			if cnt > 0 {
				p := float64(cnt) / totalDiffs
				entropyResidualY -= p * math.Log2(p)
			}
		}
	}

	// 6. Sobel, SI, Gradient Energy, Laplacian Variance and Chroma Gradient
	var spatialInformation, gradientEnergy, laplacianVariance float64
	var chromaGradientEnergy, chromaGradientRatio float64

	nValid := (width - 2) * (height - 2)
	if width > 2 && height > 2 {
		sobelMList := make([]float64, nValid)
		laplacianList := make([]float64, nValid)

		var sumSobelM float64
		var sumMagSq float64
		var sumLap float64
		var sumMagSqCb float64
		var sumMagSqCr float64

		vIdx := 0
		for yIdx := 1; yIdx < height-1; yIdx++ {
			yPrev := (yIdx - 1) * width
			yCurr := yIdx * width
			yNext := (yIdx + 1) * width

			for xIdx := 1; xIdx < width-1; xIdx++ {
				// Y Sobel
				gx := (int(yList[yPrev+xIdx+1]) + 2*int(yList[yCurr+xIdx+1]) + int(yList[yNext+xIdx+1])) -
					(int(yList[yPrev+xIdx-1]) + 2*int(yList[yCurr+xIdx-1]) + int(yList[yNext+xIdx-1]))
				gy := (int(yList[yNext+xIdx-1]) + 2*int(yList[yNext+xIdx]) + int(yList[yNext+xIdx+1])) -
					(int(yList[yPrev+xIdx-1]) + 2*int(yList[yPrev+xIdx]) + int(yList[yPrev+xIdx+1]))

				magSq := float64(gx*gx + gy*gy)
				mag := math.Sqrt(magSq)
				sobelMList[vIdx] = mag
				sumSobelM += mag
				sumMagSq += magSq

				// 4-neighbor Laplacian
				lap := int(yList[yCurr+xIdx+1]) +
					int(yList[yCurr+xIdx-1]) +
					int(yList[yNext+xIdx]) +
					int(yList[yPrev+xIdx]) -
					4*int(yList[yCurr+xIdx])
				lapF := float64(lap)
				laplacianList[vIdx] = lapF
				sumLap += lapF

				// Cb Sobel
				gxCb := (int(cbList[yPrev+xIdx+1]) + 2*int(cbList[yCurr+xIdx+1]) + int(cbList[yNext+xIdx+1])) -
					(int(cbList[yPrev+xIdx-1]) + 2*int(cbList[yCurr+xIdx-1]) + int(cbList[yNext+xIdx-1]))
				gyCb := (int(cbList[yNext+xIdx-1]) + 2*int(cbList[yNext+xIdx]) + int(cbList[yNext+xIdx+1])) -
					(int(cbList[yPrev+xIdx-1]) + 2*int(cbList[yPrev+xIdx]) + int(cbList[yPrev+xIdx+1]))
				sumMagSqCb += float64(gxCb*gxCb + gyCb*gyCb)

				// Cr Sobel
				gxCr := (int(crList[yPrev+xIdx+1]) + 2*int(crList[yCurr+xIdx+1]) + int(crList[yNext+xIdx+1])) -
					(int(crList[yPrev+xIdx-1]) + 2*int(crList[yCurr+xIdx-1]) + int(crList[yNext+xIdx-1]))
				gyCr := (int(crList[yNext+xIdx-1]) + 2*int(crList[yNext+xIdx]) + int(crList[yNext+xIdx+1])) -
					(int(crList[yPrev+xIdx-1]) + 2*int(crList[yPrev+xIdx]) + int(crList[yPrev+xIdx+1]))
				sumMagSqCr += float64(gxCr*gxCr + gyCr*gyCr)

				vIdx++
			}
		}

		nV := float64(nValid)
		meanM := sumSobelM / nV
		var varM float64
		for _, m := range sobelMList {
			diff := m - meanM
			varM += diff * diff
		}
		spatialInformation = math.Sqrt(varM / nV)
		gradientEnergy = sumMagSq / nV

		meanLap := sumLap / nV
		var varLap float64
		for _, l := range laplacianList {
			diff := l - meanLap
			varLap += diff * diff
		}
		laplacianVariance = varLap / nV

		chromaGeCb := sumMagSqCb / nV
		chromaGeCr := sumMagSqCr / nV
		chromaGradientEnergy = chromaGeCb + chromaGeCr
		if gradientEnergy > 0 {
			chromaGradientRatio = chromaGradientEnergy / gradientEnergy
		}
	}

	// 7. Color Variance
	meanR := float64(sumR) / nF
	meanG := float64(sumG) / nF
	meanB := float64(sumB) / nF

	var varR, varG, varB float64
	for i := 0; i < numPixels; i++ {
		dr := float64(rList[i]) - meanR
		dg := float64(gList[i]) - meanG
		db := float64(bList[i]) - meanB
		varR += dr * dr
		varG += dg * dg
		varB += db * db
	}
	varR /= nF
	varG /= nF
	varB /= nF
	varSum := varR + varG + varB

	// 8. Unique Colors (32-bit RGBA cardinality)
	initCap := numPixels
	if initCap > 65536 {
		initCap = 65536
	}
	uniqueSet := make(map[uint32]struct{}, initCap)
	for i := 0; i < numPixels; i++ {
		key := (uint32(rList[i]) << 24) | (uint32(gList[i]) << 16) | (uint32(bList[i]) << 8) | uint32(aList[i])
		uniqueSet[key] = struct{}{}
	}
	uniqueColors := len(uniqueSet)

	// 9. Alpha Metrics
	hasAlpha := (depth == 4)
	var alphaSparsity, alphaBinarity float64
	if hasAlpha {
		zeroCnt := 0
		binCnt := 0
		for _, a := range aList {
			if a == 0 {
				zeroCnt++
			}
			if a == 0 || a == 255 {
				binCnt++
			}
		}
		alphaSparsity = float64(zeroCnt) / nF
		alphaBinarity = float64(binCnt) / nF
	} else {
		alphaSparsity = 0.0
		alphaBinarity = 1.0
	}

	// 10. Adequacy 4:2:0 - 2x2 Roundtrip MSE
	var sumSqErrCb, sumSqErrCr float64
	for by := 0; by < height; by += 2 {
		for bx := 0; bx < width; bx += 2 {
			var bCb [4]uint8
			var bCr [4]uint8
			k := 0
			for dy := 0; dy < 2; dy++ {
				py := by + dy
				if py >= height {
					continue
				}
				rowOff := py * width
				for dx := 0; dx < 2; dx++ {
					px := bx + dx
					if px >= width {
						continue
					}
					bCb[k] = cbList[rowOff+px]
					bCr[k] = crList[rowOff+px]
					k++
				}
			}
			if k > 0 {
				var sumCb, sumCr float64
				for i := 0; i < k; i++ {
					sumCb += float64(bCb[i])
					sumCr += float64(bCr[i])
				}
				avgCb := sumCb / float64(k)
				avgCr := sumCr / float64(k)
				for i := 0; i < k; i++ {
					dCb := float64(bCb[i]) - avgCb
					dCr := float64(bCr[i]) - avgCr
					sumSqErrCb += dCb * dCb
					sumSqErrCr += dCr * dCr
				}
			}
		}
	}
	mseCb := sumSqErrCb / nF
	mseCr := sumSqErrCr / nF
	mseChroma := (mseCb + mseCr) / 2.0

	// 11. Flat Area Fraction (8x8 disjoint blocks with Var(Y) < 16.0)
	blocksX := width / 8
	blocksY := height / 8
	totalCompleteBlocks := blocksX * blocksY
	var flatArea float64
	if totalCompleteBlocks > 0 {
		flatBlocksCount := 0
		for by := 0; by < blocksY; by++ {
			for bx := 0; bx < blocksX; bx++ {
				var sumBlockY int
				for dy := 0; dy < 8; dy++ {
					rowOff := (by*8 + dy) * width
					bStart := bx * 8
					for dx := 0; dx < 8; dx++ {
						sumBlockY += int(yList[rowOff+bStart+dx])
					}
				}
				blockMean := float64(sumBlockY) / 64.0
				var blockVar float64
				for dy := 0; dy < 8; dy++ {
					rowOff := (by*8 + dy) * width
					bStart := bx * 8
					for dx := 0; dx < 8; dx++ {
						diff := float64(yList[rowOff+bStart+dx]) - blockMean
						blockVar += diff * diff
					}
				}
				blockVar /= 64.0
				if blockVar < 16.0 {
					flatBlocksCount++
				}
			}
		}
		flatArea = float64(flatBlocksCount) / float64(totalCompleteBlocks)
	} else {
		flatArea = 1.0
	}

	// 12. Dominant Color (12-bit RGB histogram mode, tie-breaker: lowest bin)
	var hist12bit [4096]int
	for i := 0; i < numPixels; i++ {
		r4 := int(rList[i] >> 4)
		g4 := int(gList[i] >> 4)
		b4 := int(bList[i] >> 4)
		idx := (r4 << 8) | (g4 << 4) | b4
		hist12bit[idx]++
	}
	dominantBin := 0
	maxCount := -1
	for idx, count := range hist12bit {
		if count > maxCount {
			maxCount = count
			dominantBin = idx
		}
	}
	r4Dom := (dominantBin >> 8) & 0xF
	g4Dom := (dominantBin >> 4) & 0xF
	b4Dom := dominantBin & 0xF
	dominantRGB := [3]int{r4Dom * 17, g4Dom * 17, b4Dom * 17}

	// 13. pHash 64-bit
	phashStr := ComputePHash(yList, width, height)

	// 14. Wolt BlurHash
	blurhashStr := ComputeBlurHash(rList, gList, bList, width, height, 4, 3)

	return &Result{
		Width:              width,
		Height:             height,
		AspectRatio:        aspectRatio,
		BlockAlignment:     blockAlignment,
		MeanY:              round6(meanY),
		EntropyY:           round6(entropyY),
		EntropyResidualY:   round6(entropyResidualY),
		SpatialInformation: round6(spatialInformation),
		GradientEnergy:     round6(gradientEnergy),
		LaplacianVariance:  round6(laplacianVariance),
		ColorVariance: ColorVariance{
			VarR:   round6(varR),
			VarG:   round6(varG),
			VarB:   round6(varB),
			VarSum: round6(varSum),
		},
		UniqueColors: uniqueColors,
		Alpha: AlphaMetrics{
			HasAlpha: hasAlpha,
			Sparsity: round6(alphaSparsity),
			Binarity: round6(alphaBinarity),
		},
		Adequacy420: Adequacy420{
			ChromaGradientEnergy: round6(chromaGradientEnergy),
			ChromaGradientRatio:  round6(chromaGradientRatio),
			MSE_Cb:               round6(mseCb),
			MSE_Cr:               round6(mseCr),
			MSE_Chroma:           round6(mseChroma),
		},
		FlatArea: round6(flatArea),
		DominantColor: DominantColor{
			DominantRGB: dominantRGB,
			DominantBin: dominantBin,
			MeanRGB:     [3]float64{round6(meanR), round6(meanG), round6(meanB)},
		},
		PHash:    phashStr,
		BlurHash: blurhashStr,
	}
}

// ComputePHash computes the 64-bit perceptual hash with 32x32 area-average resize and DCT-II.
func ComputePHash(yPixels []uint8, width, height int) string {
	// 1. Continuous area-average resize to 32x32
	var I [32][32]float64
	sw := float64(width) / 32.0
	sh := float64(height) / 32.0

	for v := 0; v < 32; v++ {
		y0 := float64(v) * sh
		y1 := float64(v+1) * sh
		syMin := int(math.Floor(y0))
		syMax := int(math.Ceil(y1))
		if syMax > height {
			syMax = height
		}

		for u := 0; u < 32; u++ {
			x0 := float64(u) * sw
			x1 := float64(u+1) * sw
			sxMin := int(math.Floor(x0))
			sxMax := int(math.Ceil(x1))
			if sxMax > width {
				sxMax = width
			}

			total := 0.0
			totalWeight := 0.0
			for py := syMin; py < syMax; py++ {
				wy := math.Max(0.0, math.Min(float64(py)+1.0, y1)-math.Max(float64(py), y0))
				rowOff := py * width
				for px := sxMin; px < sxMax; px++ {
					wx := math.Max(0.0, math.Min(float64(px)+1.0, x1)-math.Max(float64(px), x0))
					w := wx * wy
					total += float64(yPixels[rowOff+px]) * w
					totalWeight += w
				}
			}
			if totalWeight > 0 {
				I[v][u] = total / totalWeight
			}
		}
	}

	// 2. 2D DCT-II for 8x8 low-frequency submatrix. The 8x32 cosine table is computed once
	// (same expression as before) instead of ~65 thousand math.Cos calls per image.
	var cosTab [8][32]float64
	for k := 0; k < 8; k++ {
		for n := 0; n < 32; n++ {
			cosTab[k][n] = math.Cos(math.Pi * float64(2*n+1) * float64(k) / 64.0)
		}
	}

	var D [8][8]float64
	for v := 0; v < 8; v++ {
		for u := 0; u < 8; u++ {
			s := 0.0
			for y := 0; y < 32; y++ {
				cosY := cosTab[v][y]
				for x := 0; x < 32; x++ {
					cosX := cosTab[u][x]
					s += I[y][x] * cosX * cosY
				}
			}
			if math.Abs(s) < 1e-6 {
				s = 0.0
			}
			D[v][u] = s
		}
	}

	// 3. Exclude DC (0,0) -> C[0,0] = 0.0
	var coeffs [64]float64
	idx := 0
	for v := 0; v < 8; v++ {
		for u := 0; u < 8; u++ {
			if u == 0 && v == 0 {
				coeffs[idx] = 0.0
			} else {
				coeffs[idx] = D[v][u]
			}
			idx++
		}
	}

	// 4. Median of the 64 coefficients
	var sortedCoeffs [64]float64
	copy(sortedCoeffs[:], coeffs[:])
	slices.Sort(sortedCoeffs[:])
	median := (sortedCoeffs[31] + sortedCoeffs[32]) / 2.0

	// 5. Construct 64-bit hash (MSB at index 0)
	var hashVal uint64
	for i := 0; i < 64; i++ {
		if coeffs[i] > median {
			hashVal |= (uint64(1) << (63 - i))
		}
	}

	return fmt.Sprintf("%016x", hashVal)
}

func srgbToLinear(value uint8) float64 {
	v := float64(value) / 255.0
	if v <= 0.04045 {
		return v / 12.92
	}
	return math.Pow((v+0.055)/1.055, 2.4)
}

func linearToSRGB(value float64) int {
	v := math.Max(0.0, math.Min(1.0, value))
	if v <= 0.0031308 {
		return int(v*12.92*255.0 + 0.5)
	}
	return int((1.055*math.Pow(v, 1.0/2.4)-0.055)*255.0 + 0.5)
}

func signPow(val, exp float64) float64 {
	return math.Copysign(math.Pow(math.Abs(val), exp), val)
}

func encodeBase83(value int, length int) string {
	divisor := 1
	for i := 0; i < length-1; i++ {
		divisor *= 83
	}
	res := make([]byte, length)
	for i := 0; i < length; i++ {
		digit := (value / divisor) % 83
		divisor /= 83
		res[i] = blurhashChars[digit]
	}
	return string(res)
}

// cosineTable returns cos(pi*k*n/length) for k in [0, comps) and n in [0, length). The Rust engine
// builds the same tables, so neither engine calls cos once per pixel.
func cosineTable(comps, length int) [][]float64 {
	table := make([][]float64, comps)
	for k := range table {
		table[k] = make([]float64, length)
		for n := range table[k] {
			table[k][n] = math.Cos(math.Pi * float64(k*n) / float64(length))
		}
	}
	return table
}

// ComputeBlurHash computes the official Wolt BlurHash with xComp=4, yComp=3.
func ComputeBlurHash(rList, gList, bList []uint8, width, height, xComp, yComp int) string {
	// sRGB -> linear only has 256 inputs, so Pow runs 256 times instead of once per pixel and channel.
	var linear [256]float64
	for v := range linear {
		linear[v] = srgbToLinear(uint8(v))
	}
	cosX := cosineTable(xComp, width)
	cosY := cosineTable(yComp, height)

	factors := make([][][3]float64, yComp)
	for y := 0; y < yComp; y++ {
		factors[y] = make([][3]float64, xComp)
		for x := 0; x < xComp; x++ {
			norm := 2.0
			if x == 0 && y == 0 {
				norm = 1.0
			}
			var rAcc, gAcc, bAcc float64
			for py := 0; py < height; py++ {
				cy := cosY[y][py]
				rowOff := py * width
				for px := 0; px < width; px++ {
					basis := cosX[x][px] * cy
					idx := rowOff + px
					rAcc += basis * linear[rList[idx]]
					gAcc += basis * linear[gList[idx]]
					bAcc += basis * linear[bList[idx]]
				}
			}
			scale := norm / float64(width*height)
			factors[y][x] = [3]float64{rAcc * scale, gAcc * scale, bAcc * scale}
		}
	}

	dc := factors[0][0]
	var ac [][3]float64
	for y := 0; y < yComp; y++ {
		for x := 0; x < xComp; x++ {
			if x != 0 || y != 0 {
				ac = append(ac, factors[y][x])
			}
		}
	}

	sizeFlag := (xComp - 1) + (yComp-1)*9
	res := encodeBase83(sizeFlag, 1)

	var maxVal float64
	if len(ac) > 0 {
		actualMax := 0.0
		for _, comp := range ac {
			for _, ch := range comp {
				actualMax = math.Max(actualMax, math.Abs(ch))
			}
		}
		quantMax := int(math.Floor(actualMax*166.0 - 0.5))
		if quantMax < 0 {
			quantMax = 0
		} else if quantMax > 82 {
			quantMax = 82
		}
		maxVal = float64(quantMax+1) / 166.0
		res += encodeBase83(quantMax, 1)
	} else {
		maxVal = 1.0
		res += encodeBase83(0, 1)
	}

	// DC component (24-bit sRGB)
	dcR := linearToSRGB(dc[0])
	dcG := linearToSRGB(dc[1])
	dcB := linearToSRGB(dc[2])
	dcVal := (dcR << 16) + (dcG << 8) + dcB
	res += encodeBase83(dcVal, 4)

	// AC components
	for _, comp := range ac {
		qr := int(math.Floor(signPow(comp[0]/maxVal, 0.5)*9.0 + 9.5))
		if qr < 0 {
			qr = 0
		} else if qr > 18 {
			qr = 18
		}
		qg := int(math.Floor(signPow(comp[1]/maxVal, 0.5)*9.0 + 9.5))
		if qg < 0 {
			qg = 0
		} else if qg > 18 {
			qg = 18
		}
		qb := int(math.Floor(signPow(comp[2]/maxVal, 0.5)*9.0 + 9.5))
		if qb < 0 {
			qb = 0
		} else if qb > 18 {
			qb = 18
		}
		res += encodeBase83(qr*361+qg*19+qb, 2)
	}

	return res
}
