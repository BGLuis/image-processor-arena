#!/usr/bin/env python3
"""
arena_server.py - Servidor HTTP da Arena de Processamento de Imagens em Python.

Implementa os endpoints:
- GET /health -> {"status": "ok"} (HTTP 200)
- POST /run?op=... -> operações de analyze, encode, decode, transcode.

Respeita:
- ARENA_MAX_BODY_BYTES (padrão 268435456 = 256MB): responde HTTP 413 se excedido
- ARENA_MAX_PIXELS (padrão 40000000): responde HTTP 400 se excedido antes de alocar
- Headers de telemetria de performance:
  - X-Arena-Analyze-Ns
  - X-Arena-Encode-Ns
  - X-Arena-Decode-Ns
  - X-Arena-Impl
"""

import json
import os
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from python.arena_pam import parse_pam, encode_pam, get_max_pixels, PamError
from python.arena_analyze import analyze
from python.arena_codecs import (
    parse_params,
    encode_image,
    decode_image,
    get_mime_type,
    CodecError,
    InvalidParamsError,
    UnsupportedFormatError,
)

ENV_MAX_BODY_BYTES = "ARENA_MAX_BODY_BYTES"
DEFAULT_MAX_BODY_BYTES = 256 * 1024 * 1024  # 256 MB


def get_max_body_bytes() -> int:
    raw = os.environ.get(ENV_MAX_BODY_BYTES)
    if not raw:
        return DEFAULT_MAX_BODY_BYTES
    try:
        val = int(raw)
        return val if val > 0 else DEFAULT_MAX_BODY_BYTES
    except ValueError:
        return DEFAULT_MAX_BODY_BYTES


class ArenaHTTPHandler(BaseHTTPRequestHandler):
    server_version = "ArenaPython/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/run":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        max_body_bytes = get_max_body_bytes()
        max_pixels = get_max_pixels()

        # Verifica Content-Length
        content_length_str = self.headers.get("Content-Length")
        if content_length_str is not None:
            try:
                content_length = int(content_length_str)
                if content_length > max_body_bytes:
                    self.send_error(
                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        f"Request body exceeds {max_body_bytes} bytes limit",
                    )
                    return
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length")
                return
        else:
            content_length = None

        # Leitura segura do corpo com limite
        if content_length is not None:
            body = self.rfile.read(content_length)
        else:
            body = self.rfile.read(max_body_bytes + 1)
            if len(body) > max_body_bytes:
                self.send_error(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    f"Request body exceeds {max_body_bytes} bytes limit",
                )
                return

        if not body:
            self.send_error(HTTPStatus.BAD_REQUEST, "Empty request body")
            return

        # Parsing de parâmetros da query string
        q_params = parse_qs(parsed.query)

        def get_single(key: str, default: str = "") -> str:
            vals = q_params.get(key)
            if vals and len(vals) > 0:
                return vals[0]
            return default

        op = get_single("op").lower().strip()
        format_param = get_single("format")
        to_param = get_single("to")
        mode_param = get_single("mode") or None
        q_param = get_single("q") or None
        effort_param = get_single("effort") or None
        impl_param = get_single("impl")
        from_impl_param = get_single("from_impl") or impl_param
        to_impl_param = get_single("to_impl") or impl_param

        try:
            if op == "analyze":
                pam_img = parse_pam(body, max_pixels=max_pixels)
                chosen_impl = impl_param or "pure"

                start = time.perf_counter_ns()
                result = analyze(pam_img, impl=chosen_impl)
                analyze_ns = time.perf_counter_ns() - start

                resp_bytes = json.dumps(result).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Arena-Analyze-Ns", str(analyze_ns))
                self.send_header("X-Arena-Impl", chosen_impl)
                self.end_headers()
                self.wfile.write(resp_bytes)

            elif op == "encode":
                if not format_param:
                    self.send_error(HTTPStatus.BAD_REQUEST, "Missing 'format' query parameter")
                    return

                params = parse_params(format_param, mode_param, q_param, effort_param, to_impl_param)
                pam_img = parse_pam(body, max_pixels=max_pixels)

                start = time.perf_counter_ns()
                out_bytes = encode_image(pam_img, params)
                encode_ns = time.perf_counter_ns() - start

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", get_mime_type(params.format))
                self.send_header("X-Arena-Encode-Ns", str(encode_ns))
                self.send_header("X-Arena-Impl", params.impl or "pillow")
                self.end_headers()
                self.wfile.write(out_bytes)

            elif op == "decode":
                if not format_param:
                    self.send_error(HTTPStatus.BAD_REQUEST, "Missing 'format' query parameter")
                    return

                start = time.perf_counter_ns()
                pam_img = decode_image(body, format_param, from_impl_param)
                decode_ns = time.perf_counter_ns() - start

                out_bytes = encode_pam(pam_img)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/x-netpbm-pam")
                self.send_header("X-Arena-Decode-Ns", str(decode_ns))
                self.send_header("X-Arena-Impl", from_impl_param or "pillow")
                self.end_headers()
                self.wfile.write(out_bytes)

            elif op == "transcode":
                if not format_param or not to_param:
                    self.send_error(HTTPStatus.BAD_REQUEST, "Missing 'format' or 'to' query parameter")
                    return

                params = parse_params(to_param, mode_param, q_param, effort_param, to_impl_param)

                start_dec = time.perf_counter_ns()
                pam_img = decode_image(body, format_param, from_impl_param)
                decode_ns = time.perf_counter_ns() - start_dec

                start_enc = time.perf_counter_ns()
                out_bytes = encode_image(pam_img, params)
                encode_ns = time.perf_counter_ns() - start_enc

                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", get_mime_type(params.format))
                self.send_header("X-Arena-Decode-Ns", str(decode_ns))
                self.send_header("X-Arena-Encode-Ns", str(encode_ns))
                self.send_header("X-Arena-Impl", params.impl or "pillow")
                self.end_headers()
                self.wfile.write(out_bytes)

            else:
                self.send_error(HTTPStatus.BAD_REQUEST, f"Unsupported op: '{op}'")

        except (PamError, CodecError, ValueError) as e:
            self.send_error(HTTPStatus.BAD_REQUEST, str(e))
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Internal server error: {e}")

    def log_message(self, format: str, *args) -> None:
        # Silencia logs rotineiros para não poluir testes de benchmark
        pass


def run_server(port: int = 8083) -> None:
    addr = ("", port)
    server = ThreadingHTTPServer(addr, ArenaHTTPHandler)
    print(f"[arena-server-python] Listening on port {port} (PID {os.getpid()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> int:
    port = int(os.environ.get("PORT", "8083"))
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
