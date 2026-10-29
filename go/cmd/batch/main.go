package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/image-processor-arena/go/internal/analyze"
	"github.com/image-processor-arena/go/internal/codec"
	"github.com/image-processor-arena/go/internal/ops"
	"github.com/image-processor-arena/go/internal/pam"
)

func main() {
	var (
		opFlag       = flag.String("op", "", "Operation: analyze, encode, decode, transcode, resize, filter")
		formatFlag   = flag.String("format", "", "Image format: png, jpeg, webp, avif, jxl")
		toFlag       = flag.String("to", "", "Target format for transcode")
		modeFlag     = flag.String("mode", "", "Compression mode: lossy, lossless (default lossy)")
		qFlag        = flag.String("q", "", "Quality level 1-100 (default 75)")
		effortFlag   = flag.String("effort", "", "Effort level 1-10, higher is slower and smaller (default 4)")
		implFlag     = flag.String("impl", "", "Codec implementation name")
		fromImplFlag = flag.String("from-impl", "", "Source codec implementation name for decode/transcode")
		toImplFlag   = flag.String("to-impl", "", "Target codec implementation name for encode/transcode")
		wFlag        = flag.Int("w", 0, "Target width for resize")
		hFlag        = flag.Int("h", 0, "Target height for resize")
		filterFlag   = flag.String("filter", "", "Filter name (resize filter or convolution filter)")
		sigmaFlag    = flag.Float64("sigma", 1.0, "Sigma for filter operations")
		inputFlag    = flag.String("input", "", "Input file path (or '-' for stdin)")
		outputFlag   = flag.String("output", "", "Output file path (or '-' for stdout)")
	)
	flag.Parse()

	maxPixels, err := pam.MaxPixelsFromEnv(os.Getenv)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}

	if *opFlag == "" {
		fmt.Fprintln(os.Stderr, "Error: --op flag is required (analyze, encode, decode, transcode)")
		os.Exit(1)
	}

	var inputData []byte

	if *inputFlag == "" || *inputFlag == "-" {
		inputData, err = io.ReadAll(os.Stdin)
	} else {
		inputData, err = os.ReadFile(*inputFlag)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading input: %v\n", err)
		os.Exit(1)
	}

	if len(inputData) == 0 {
		fmt.Fprintln(os.Stderr, "Error: empty input")
		os.Exit(1)
	}

	switch *opFlag {
	case "analyze":
		pamImg, err := pam.DecodeLimit(bytes.NewReader(inputData), maxPixels)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding PAM input: %v\n", err)
			os.Exit(1)
		}

		result := analyze.AnalyzeImage(pamImg)
		jsonBytes, err := json.MarshalIndent(result, "", "  ")
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error serializing JSON: %v\n", err)
			os.Exit(1)
		}

		if *outputFlag != "" && *outputFlag != "-" {
			if err := os.WriteFile(*outputFlag, jsonBytes, 0644); err != nil {
				fmt.Fprintf(os.Stderr, "Error writing output file: %v\n", err)
				os.Exit(1)
			}
		}
		// Also output to stdout (required by harness verify_cross.py)
		fmt.Println(string(jsonBytes))

	case "encode":
		fmtStr := *formatFlag
		if fmtStr == "" {
			fmt.Fprintln(os.Stderr, "Error: --format is required for encode")
			os.Exit(1)
		}

		encImpl := *toImplFlag
		if encImpl == "" {
			encImpl = *implFlag
		}
		params, err := codec.ParseParams(fmtStr, *modeFlag, *qFlag, *effortFlag, encImpl)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}

		pamImg, err := pam.DecodeLimit(bytes.NewReader(inputData), maxPixels)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding PAM input: %v\n", err)
			os.Exit(1)
		}

		var outBuf bytes.Buffer
		if err := codec.Encode(&outBuf, pamImg, params); err != nil {
			fmt.Fprintf(os.Stderr, "Error encoding: %v\n", err)
			os.Exit(1)
		}

		writeOutput(*outputFlag, outBuf.Bytes())

	case "decode":
		fmtStr := *formatFlag
		if fmtStr == "" {
			// Try to infer from input filename
			if *inputFlag != "" && *inputFlag != "-" {
				parts := strings.Split(*inputFlag, ".")
				if len(parts) > 1 {
					fmtStr = parts[len(parts)-1]
				}
			}
		}
		if fmtStr == "" {
			fmt.Fprintln(os.Stderr, "Error: --format is required for decode")
			os.Exit(1)
		}

		decImpl := *fromImplFlag
		if decImpl == "" {
			decImpl = *implFlag
		}
		pamImg, err := codec.Decode(bytes.NewReader(inputData), fmtStr, decImpl)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding: %v\n", err)
			os.Exit(1)
		}

		pamBytes := pam.EncodeBytes(pamImg)
		writeOutput(*outputFlag, pamBytes)

	case "transcode":
		fromFmt := *formatFlag
		toFmt := *toFlag
		if fromFmt == "" || toFmt == "" {
			fmt.Fprintln(os.Stderr, "Error: --format and --to are required for transcode")
			os.Exit(1)
		}

		encImpl := *toImplFlag
		if encImpl == "" {
			encImpl = *implFlag
		}
		params, err := codec.ParseParams(toFmt, *modeFlag, *qFlag, *effortFlag, encImpl)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}

		decImpl := *fromImplFlag
		if decImpl == "" {
			decImpl = *implFlag
		}
		pamImg, err := codec.Decode(bytes.NewReader(inputData), fromFmt, decImpl)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding input: %v\n", err)
			os.Exit(1)
		}

		var outBuf bytes.Buffer
		if err := codec.Encode(&outBuf, pamImg, params); err != nil {
			fmt.Fprintf(os.Stderr, "Error encoding transcode: %v\n", err)
			os.Exit(1)
		}

		writeOutput(*outputFlag, outBuf.Bytes())

	case "resize":
		if *wFlag <= 0 || *hFlag <= 0 {
			fmt.Fprintln(os.Stderr, "Error: --w and --h must be positive integers")
			os.Exit(1)
		}
		if int64(*wFlag)*int64(*hFlag) > int64(maxPixels) || *wFlag > maxPixels || *hFlag > maxPixels {
			fmt.Fprintf(os.Stderr, "Error: dimensions %dx%d exceed maximum allowed pixels (%d)\n", *wFlag, *hFlag, maxPixels)
			os.Exit(1)
		}
		pamImg, err := pam.DecodeLimit(bytes.NewReader(inputData), maxPixels)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding PAM: %v\n", err)
			os.Exit(1)
		}
		filter := *filterFlag
		if filter == "" {
			filter = "lanczos3"
		}
		dstPam, err := ops.Resize(pamImg, *wFlag, *hFlag, filter, *implFlag)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error resizing: %v\n", err)
			os.Exit(1)
		}
		writeOutput(*outputFlag, pam.EncodeBytes(dstPam))

	case "filter":
		if *filterFlag == "" {
			fmt.Fprintln(os.Stderr, "Error: --filter is required for filter operation")
			os.Exit(1)
		}
		pamImg, err := pam.DecodeLimit(bytes.NewReader(inputData), maxPixels)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding PAM: %v\n", err)
			os.Exit(1)
		}
		dstPam, err := ops.Filter(pamImg, *filterFlag, *sigmaFlag, *implFlag)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error filtering: %v\n", err)
			os.Exit(1)
		}
		writeOutput(*outputFlag, pam.EncodeBytes(dstPam))

	case "seam_carving":
		if *wFlag <= 0 || *hFlag <= 0 {
			fmt.Fprintln(os.Stderr, "Error: --w and --h must be positive integers")
			os.Exit(1)
		}
		if int64(*wFlag)*int64(*hFlag) > int64(maxPixels) || *wFlag > maxPixels || *hFlag > maxPixels {
			fmt.Fprintf(os.Stderr, "Error: dimensions %dx%d exceed maximum allowed pixels (%d)\n", *wFlag, *hFlag, maxPixels)
			os.Exit(1)
		}
		pamImg, err := pam.DecodeLimit(bytes.NewReader(inputData), maxPixels)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding PAM: %v\n", err)
			os.Exit(1)
		}
		dstPam, err := ops.SeamCarve(pamImg, *wFlag, *hFlag)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error seam carving: %v\n", err)
			os.Exit(1)
		}
		writeOutput(*outputFlag, pam.EncodeBytes(dstPam))

	default:
		fmt.Fprintf(os.Stderr, "Unknown op: %q\n", *opFlag)
		os.Exit(1)
	}
}

func writeOutput(dest string, data []byte) {
	if dest == "" || dest == "-" {
		_, _ = os.Stdout.Write(data)
	} else {
		if err := os.WriteFile(dest, data, 0644); err != nil {
			fmt.Fprintf(os.Stderr, "Error writing output: %v\n", err)
			os.Exit(1)
		}
	}
}
