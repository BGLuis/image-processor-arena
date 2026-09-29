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
	"github.com/image-processor-arena/go/internal/pam"
)

func main() {
	var (
		opFlag     = flag.String("op", "", "Operation: analyze, encode, decode, transcode")
		formatFlag = flag.String("format", "", "Image format: png, jpeg, webp, avif, jxl")
		toFlag     = flag.String("to", "", "Target format for transcode")
		modeFlag   = flag.String("mode", "", "Compression mode: lossy, lossless")
		qFlag      = flag.Int("q", 0, "Quality level (1-100)")
		effortFlag = flag.Int("effort", 0, "Effort / speed / method setting")
		inputFlag  = flag.String("input", "", "Input file path (or '-' for stdin)")
		outputFlag = flag.String("output", "", "Output file path (or '-' for stdout)")
	)
	flag.Parse()

	if *opFlag == "" {
		fmt.Fprintln(os.Stderr, "Error: --op flag is required (analyze, encode, decode, transcode)")
		os.Exit(1)
	}

	var inputData []byte
	var err error

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
		pamImg, err := pam.Decode(bytes.NewReader(inputData))
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

		pamImg, err := pam.Decode(bytes.NewReader(inputData))
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding PAM input: %v\n", err)
			os.Exit(1)
		}

		var outBuf bytes.Buffer
		params := codec.Params{
			Format: fmtStr,
			Mode:   *modeFlag,
			Q:      *qFlag,
			Effort: *effortFlag,
		}
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

		pamImg, err := codec.Decode(bytes.NewReader(inputData), fmtStr)
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

		pamImg, err := codec.Decode(bytes.NewReader(inputData), fromFmt)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error decoding input: %v\n", err)
			os.Exit(1)
		}

		var outBuf bytes.Buffer
		params := codec.Params{
			Format: toFmt,
			Mode:   *modeFlag,
			Q:      *qFlag,
			Effort: *effortFlag,
		}
		if err := codec.Encode(&outBuf, pamImg, params); err != nil {
			fmt.Fprintf(os.Stderr, "Error encoding transcode: %v\n", err)
			os.Exit(1)
		}

		writeOutput(*outputFlag, outBuf.Bytes())

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
