#!/usr/bin/env python3
"""
arena_batch.py - CLI Batch da Arena de Processamento de Imagens em Python.

Compatível com os CLIs Go (go/cmd/batch) e Rust (rust/src/bin/batch.rs):
- Comandos: --op [analyze, encode, decode, transcode, resize, filter]
- Suporta stdin/stdout com '-' e arquivos em disco.
- Exit 0 em sucesso; exit 1 com mensagem em stderr em caso de erro.
"""

import argparse
import json
import os
import sys
from typing import Optional

from python.arena_pam import parse_pam, encode_pam, get_max_pixels, PamError
from python.arena_analyze import analyze
from python.arena_codecs import (
    parse_params,
    encode_image,
    decode_image,
    CodecError,
    InvalidParamsError,
    UnsupportedFormatError,
)


def read_input(input_path: str) -> bytes:
    if input_path == "-" or not input_path:
        return sys.stdin.buffer.read()
    with open(input_path, "rb") as f:
        return f.read()


def write_output(output_path: Optional[str], data: bytes) -> None:
    if output_path and output_path != "-":
        with open(output_path, "wb") as f:
            f.write(data)
    else:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI Batch da Arena de Processamento de Imagens em Python")
    parser.add_argument("--op", required=True, help="Operação: analyze, encode, decode, transcode, resize, filter")
    parser.add_argument("--format", default="", help="Formato da imagem: png, jpeg, webp, avif, jxl")
    parser.add_argument("--to", default="", help="Formato de destino para transcode")
    parser.add_argument("--mode", default=None, help="Modo de compressão: lossy ou lossless")
    parser.add_argument("--q", default=None, help="Qualidade 1-100 (padrão 75)")
    parser.add_argument("--effort", default=None, help="Effort 1-10 (padrão 4)")
    parser.add_argument("--impl", default="", help="Nome da implementação (pure, numpy, pillow, etc.)")
    parser.add_argument("--from-impl", default="", help="Implementação do decoder para decode/transcode")
    parser.add_argument("--to-impl", default="", help="Implementação do encoder para encode/transcode")
    parser.add_argument("--w", type=int, default=0, help="Largura alvo para resize")
    parser.add_argument("--h", type=int, default=0, help="Altura alvo para resize")
    parser.add_argument("--filter", default="", help="Nome do filtro")
    parser.add_argument("--sigma", type=float, default=1.0, help="Sigma do filtro")
    parser.add_argument("--input", required=True, help="Caminho do arquivo de entrada (ou '-' para stdin)")
    parser.add_argument("--output", default=None, help="Caminho do arquivo de saída (ou '-' para stdout)")

    args = parser.parse_args()

    op = args.op.lower().strip()
    max_pixels = get_max_pixels()

    try:
        input_data = read_input(args.input)
    except Exception as e:
        sys.stderr.write(f"Error reading input: {e}\n")
        return 1

    if not input_data:
        sys.stderr.write("Error: empty input\n")
        return 1

    try:
        if op == "analyze":
            pam_img = parse_pam(input_data, max_pixels=max_pixels)
            impl = args.impl.strip() if args.impl else "pure"
            result = analyze(pam_img, impl=impl)
            json_bytes = json.dumps(result, indent=2).encode("utf-8")

            if args.output and args.output != "-":
                with open(args.output, "wb") as f:
                    f.write(json_bytes)

            # Sempre imprime na saída padrão para compatibilidade com o harness verify_cross.py
            sys.stdout.write(json_bytes.decode("utf-8") + "\n")
            sys.stdout.flush()
            return 0

        elif op == "encode":
            fmt_str = args.format.strip()
            if not fmt_str:
                sys.stderr.write("Error: --format is required for encode\n")
                return 1

            enc_impl = args.to_impl.strip() or args.impl.strip()
            params = parse_params(fmt_str, args.mode, args.q, args.effort, enc_impl)
            pam_img = parse_pam(input_data, max_pixels=max_pixels)

            out_bytes = encode_image(pam_img, params)
            write_output(args.output, out_bytes)
            return 0

        elif op == "decode":
            fmt_str = args.format.strip()
            if not fmt_str and args.input and args.input != "-":
                parts = args.input.rsplit(".", 1)
                if len(parts) > 1:
                    fmt_str = parts[1]

            if not fmt_str:
                sys.stderr.write("Error: --format is required for decode\n")
                return 1

            dec_impl = args.from_impl.strip() or args.impl.strip()
            pam_img = decode_image(input_data, fmt_str, dec_impl)
            out_bytes = encode_pam(pam_img)
            write_output(args.output, out_bytes)
            return 0

        elif op == "transcode":
            from_fmt = args.format.strip()
            to_fmt = args.to.strip()
            if not from_fmt or not to_fmt:
                sys.stderr.write("Error: --format and --to are required for transcode\n")
                return 1

            dec_impl = args.from_impl.strip() or args.impl.strip()
            enc_impl = args.to_impl.strip() or args.impl.strip()
            params = parse_params(to_fmt, args.mode, args.q, args.effort, enc_impl)

            pam_img = decode_image(input_data, from_fmt, dec_impl)
            out_bytes = encode_image(pam_img, params)
            write_output(args.output, out_bytes)
            return 0

        else:
            sys.stderr.write(f"Error: unsupported op '{op}'\n")
            return 1

    except (PamError, CodecError, ValueError) as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Unexpected error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
