"""
test_python_engine.py - Testes de conformidade e contrato para os engines Python da Arena.
"""

import io
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

# Garante path do repositório
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from python.arena_pam import (
    PamImage,
    PamError,
    parse_pam,
    encode_pam,
    DEFAULT_MAX_PIXELS,
)
from python.arena_analyze import analyze, analyze_pure, analyze_numpy
from python.arena_codecs import (
    parse_params,
    encode_image,
    decode_image,
    is_animated_webp,
    InvalidParamsError,
    UnsupportedFormatError,
)
from python.arena_server import ArenaHTTPHandler
from harness.verify_cross import compare_result


class TestArenaPAM(unittest.TestCase):
    def test_parse_and_encode_roundtrip_rgb(self):
        data = bytes(range(48))  # 4x4 x 3 = 48 bytes
        pam = PamImage(width=4, height=4, depth=3, tupltype="RGB", data=data)
        encoded = encode_pam(pam)
        self.assertTrue(encoded.startswith(b"P7\n"))
        self.assertIn(b"WIDTH 4\n", encoded)
        self.assertIn(b"HEIGHT 4\n", encoded)
        self.assertIn(b"DEPTH 3\n", encoded)
        self.assertIn(b"MAXVAL 255\n", encoded)
        self.assertIn(b"TUPLTYPE RGB\n", encoded)
        self.assertIn(b"ENDHDR\n", encoded)

        parsed = parse_pam(encoded)
        self.assertEqual(parsed.width, 4)
        self.assertEqual(parsed.height, 4)
        self.assertEqual(parsed.depth, 3)
        self.assertEqual(parsed.tupltype, "RGB")
        self.assertEqual(parsed.data, data)

    def test_parse_and_encode_roundtrip_rgba(self):
        data = bytes([255] * 64)  # 4x4 x 4 = 64 bytes
        pam = PamImage(width=4, height=4, depth=4, tupltype="RGB_ALPHA", data=data)
        encoded = encode_pam(pam)
        parsed = parse_pam(encoded)
        self.assertEqual(parsed.width, 4)
        self.assertEqual(parsed.height, 4)
        self.assertEqual(parsed.depth, 4)
        self.assertEqual(parsed.tupltype, "RGB_ALPHA")
        self.assertEqual(parsed.data, data)

    def test_max_pixels_limit_rejected_before_allocation(self):
        # 50.000.000 pixels excede o limite padrão de 40.000.000
        hdr = (
            b"P7\n"
            b"WIDTH 10000\n"
            b"HEIGHT 5000\n"
            b"DEPTH 3\n"
            b"MAXVAL 255\n"
            b"TUPLTYPE RGB\n"
            b"ENDHDR\n"
        )
        with self.assertRaises(PamError) as cm:
            parse_pam(hdr, max_pixels=DEFAULT_MAX_PIXELS)
        self.assertIn("exceed", str(cm.exception).lower())

    def test_truncated_raster_rejected(self):
        hdr = (
            b"P7\n"
            b"WIDTH 10\n"
            b"HEIGHT 10\n"
            b"DEPTH 3\n"
            b"MAXVAL 255\n"
            b"TUPLTYPE RGB\n"
            b"ENDHDR\n"
        )
        with self.assertRaises(PamError) as cm:
            parse_pam(hdr + b"shortdata")
        self.assertIn("truncated", str(cm.exception).lower())

    def test_invalid_header_cases(self):
        with self.assertRaises(PamError):
            parse_pam(b"")
        with self.assertRaises(PamError):
            parse_pam(b"NOT_P7\nWIDTH 10\nENDHDR\n")
        with self.assertRaises(PamError):
            # MAXVAL != 255
            parse_pam(b"P7\nWIDTH 2\nHEIGHT 2\nDEPTH 3\nMAXVAL 65535\nTUPLTYPE RGB\nENDHDR\n" + bytes(12))


class TestArenaParamsContract(unittest.TestCase):
    def test_valid_defaults(self):
        p = parse_params("png")
        self.assertEqual(p.format, "png")
        self.assertEqual(p.mode, "lossy")
        self.assertEqual(p.q, 75)
        self.assertEqual(p.effort, 4)

    def test_q_range_rejection(self):
        # 1..100 é válido
        parse_params("jpeg", q_str="1")
        parse_params("jpeg", q_str="100")

        # Fora de 1..100 rejeita
        for invalid_q in ["0", "-1", "101", "200", "xyz"]:
            with self.subTest(invalid_q=invalid_q):
                with self.assertRaises(InvalidParamsError):
                    parse_params("jpeg", q_str=invalid_q)

    def test_effort_range_rejection(self):
        # 1..10 é válido
        parse_params("webp", effort_str="1")
        parse_params("webp", effort_str="10")

        # Fora de 1..10 rejeita
        for invalid_effort in ["0", "-1", "11", "99", "abc"]:
            with self.subTest(invalid_effort=invalid_effort):
                with self.assertRaises(InvalidParamsError):
                    parse_params("webp", effort_str=invalid_effort)

    def test_mode_rejection(self):
        parse_params("webp", mode_str="lossy")
        parse_params("webp", mode_str="lossless")

        for invalid_mode in ["none", "fast", "loss", "LOSSLESS_EXTREME"]:
            with self.subTest(invalid_mode=invalid_mode):
                with self.assertRaises(InvalidParamsError):
                    parse_params("webp", mode_str=invalid_mode)

    def test_avif_lossless_always_rejected(self):
        p = parse_params("avif", mode_str="lossless")
        pam = PamImage(10, 10, 3, "RGB", bytes(300))
        with self.assertRaises(UnsupportedFormatError):
            encode_image(pam, p)

    def test_dimension_limits(self):
        p_jpeg = parse_params("jpeg")
        pam_big_jpeg = PamImage(65536, 1, 3, "RGB", bytes(65536 * 3))
        with self.assertRaises(InvalidParamsError):
            encode_image(pam_big_jpeg, p_jpeg)

        p_webp = parse_params("webp")
        pam_big_webp = PamImage(16384, 1, 3, "RGB", bytes(16384 * 3))
        with self.assertRaises(InvalidParamsError):
            encode_image(pam_big_webp, p_webp)

    def test_animated_webp_detection(self):
        # Mock VP8X chunk com flag de animação (bit 1 de flags no offset 20)
        animated_header = bytearray(30)
        animated_header[0:4] = b"RIFF"
        animated_header[8:12] = b"WEBP"
        animated_header[12:16] = b"VP8X"
        animated_header[20] = 0x02  # animation flag
        self.assertTrue(is_animated_webp(bytes(animated_header)))

        static_header = bytearray(30)
        static_header[0:4] = b"RIFF"
        static_header[8:12] = b"WEBP"
        static_header[12:16] = b"VP8X"
        static_header[20] = 0x00
        self.assertFalse(is_animated_webp(bytes(static_header)))


class TestArenaCodecs(unittest.TestCase):
    def setUp(self):
        # Cria imagem pequena para roundtrips rápidos
        self.width = 16
        self.height = 16
        self.rgb_data = bytes([(x * y + c * 30) % 256 for y in range(self.height) for x in range(self.width) for c in range(3)])
        self.rgba_data = bytes([(x * y + c * 30) % 256 for y in range(self.height) for x in range(self.width) for c in range(4)])
        self.pam_rgb = PamImage(self.width, self.height, 3, "RGB", self.rgb_data)
        self.pam_rgba = PamImage(self.width, self.height, 4, "RGB_ALPHA", self.rgba_data)

    def test_pure_png_roundtrip_rgb(self):
        p = parse_params("png", impl_str="pure", effort_str="4")
        enc = encode_image(self.pam_rgb, p)
        dec = decode_image(enc, "png", impl_str="pure")
        self.assertEqual(dec.width, self.width)
        self.assertEqual(dec.height, self.height)
        self.assertEqual(dec.depth, 3)
        self.assertEqual(dec.data, self.rgb_data)

    def test_pure_png_roundtrip_rgba(self):
        p = parse_params("png", impl_str="pure", effort_str="2")
        enc = encode_image(self.pam_rgba, p)
        dec = decode_image(enc, "png", impl_str="pure")
        self.assertEqual(dec.width, self.width)
        self.assertEqual(dec.height, self.height)
        self.assertEqual(dec.depth, 4)
        self.assertEqual(dec.data, self.rgba_data)

    def test_pure_mode_rejects_other_formats(self):
        for fmt in ["jpeg", "webp", "avif", "jxl"]:
            with self.subTest(fmt=fmt):
                p = parse_params(fmt, impl_str="pure")
                with self.assertRaises(UnsupportedFormatError):
                    encode_image(self.pam_rgb, p)
                with self.assertRaises(UnsupportedFormatError):
                    decode_image(b"fake", fmt, impl_str="pure")

    def test_numpy_png_roundtrip(self):
        p = parse_params("png", impl_str="numpy", effort_str="4")
        enc = encode_image(self.pam_rgb, p)
        dec = decode_image(enc, "png", impl_str="numpy")
        self.assertEqual(dec.width, self.width)
        self.assertEqual(dec.height, self.height)
        self.assertEqual(dec.data, self.rgb_data)

    def test_pillow_roundtrip_all_formats(self):
        formats = [
            ("png", {}),
            ("jpeg", {"q_str": "80"}),
            ("webp", {"mode_str": "lossy", "q_str": "75"}),
            ("webp", {"mode_str": "lossless"}),
            ("avif", {"mode_str": "lossy", "q_str": "70"}),
            ("jxl", {"mode_str": "lossy", "q_str": "75"}),
            ("jxl", {"mode_str": "lossless"}),
        ]
        for fmt, opts in formats:
            with self.subTest(fmt=fmt, opts=opts):
                p = parse_params(fmt, impl_str="pillow", **opts)
                enc = encode_image(self.pam_rgb, p)
                dec = decode_image(enc, fmt, impl_str="pillow")
                self.assertEqual(dec.width, self.width)
                self.assertEqual(dec.height, self.height)


    def test_pillow_webp_lossless_keeps_rgb_under_transparent_pixels(self):
        # Lossless é igualdade byte a byte: o RGB sob alpha 0 também faz parte da imagem
        data = bytes(v for i in range(self.width * self.height) for v in (200, 100, 50, 0 if i % 2 else 255))
        pam = PamImage(self.width, self.height, 4, "RGB_ALPHA", data)
        enc = encode_image(pam, parse_params("webp", mode_str="lossless", impl_str="pillow"))
        self.assertEqual(decode_image(enc, "webp", impl_str="pillow").data, data)

    def test_pillow_jxl_lossless_is_exact(self):
        enc = encode_image(self.pam_rgb, parse_params("jxl", mode_str="lossless", impl_str="pillow"))
        self.assertEqual(decode_image(enc, "jxl", impl_str="pillow").data, self.rgb_data)

class TestArenaAnalyze(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gt_path = os.path.join(REPO_ROOT, "harness", "fixtures", "ground_truth.json")
        cls.fixtures_dir = os.path.join(REPO_ROOT, "harness", "fixtures", "synthetic")
        with open(cls.gt_path, "r", encoding="utf-8") as f:
            cls.ground_truth = json.load(f)

    def test_analyze_pure_all_ground_truth_fixtures(self):
        for fname, expected in self.ground_truth.items():
            with self.subTest(fixture=fname, impl="pure"):
                pam_path = os.path.join(self.fixtures_dir, fname)
                with open(pam_path, "rb") as f:
                    pam = parse_pam(f.read())
                actual = analyze_pure(pam)
                diffs = compare_result(actual, expected)
                self.assertEqual(diffs, [], f"Pure analyze divergence on {fname}: {diffs}")

    def test_analyze_numpy_all_ground_truth_fixtures(self):
        for fname, expected in self.ground_truth.items():
            with self.subTest(fixture=fname, impl="numpy"):
                pam_path = os.path.join(self.fixtures_dir, fname)
                with open(pam_path, "rb") as f:
                    pam = parse_pam(f.read())
                actual = analyze_numpy(pam)
                diffs = compare_result(actual, expected)
                self.assertEqual(diffs, [], f"NumPy analyze divergence on {fname}: {diffs}")


class TestArenaHTTPServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ArenaHTTPHandler)
        cls.port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health(self):
        req = urllib.request.Request(f"{self.base_url}/health", method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "ok")

    def test_run_analyze(self):
        pam = PamImage(8, 8, 3, "RGB", bytes([128] * 192))
        pam_bytes = encode_pam(pam)

        req = urllib.request.Request(
            f"{self.base_url}/run?op=analyze&impl=pure",
            data=pam_bytes,
            headers={"Content-Type": "image/x-netpbm-pam"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("X-Arena-Analyze-Ns", resp.headers)
            self.assertIn("X-Arena-Impl", resp.headers)
            body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body.get("width"), 8)
            self.assertEqual(body.get("height"), 8)

    def test_run_encode_decode(self):
        pam = PamImage(8, 8, 3, "RGB", bytes(range(192)))
        pam_bytes = encode_pam(pam)

        # 1. Encode PNG
        enc_req = urllib.request.Request(
            f"{self.base_url}/run?op=encode&format=png&impl=pure",
            data=pam_bytes,
            method="POST",
        )
        with urllib.request.urlopen(enc_req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("X-Arena-Encode-Ns", resp.headers)
            png_bytes = resp.read()

        # 2. Decode PNG
        dec_req = urllib.request.Request(
            f"{self.base_url}/run?op=decode&format=png&impl=pure",
            data=png_bytes,
            method="POST",
        )
        with urllib.request.urlopen(dec_req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("X-Arena-Decode-Ns", resp.headers)
            decoded_pam = parse_pam(resp.read())
            self.assertEqual(decoded_pam.width, 8)
            self.assertEqual(decoded_pam.data, pam.data)

    def test_run_body_too_large_413(self):
        # Envia payload com Content-Length simulando tamanho maior que ARENA_MAX_BODY_BYTES
        # Temporariamente sobrescreve a constante de limite para testar
        os.environ["ARENA_MAX_BODY_BYTES"] = "100"
        try:
            req = urllib.request.Request(
                f"{self.base_url}/run?op=analyze",
                data=bytes(200),
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req)
            self.assertEqual(cm.exception.code, 413)
        finally:
            os.environ.pop("ARENA_MAX_BODY_BYTES", None)

    def test_run_max_pixels_limit_rejected_400(self):
        huge_pam_hdr = (
            b"P7\n"
            b"WIDTH 50000\n"
            b"HEIGHT 50000\n"
            b"DEPTH 3\n"
            b"MAXVAL 255\n"
            b"TUPLTYPE RGB\n"
            b"ENDHDR\n"
        )
        req = urllib.request.Request(
            f"{self.base_url}/run?op=analyze",
            data=huge_pam_hdr,
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)

    def test_run_invalid_param_rejected_400(self):
        pam = PamImage(4, 4, 3, "RGB", bytes(48))
        pam_bytes = encode_pam(pam)
        req = urllib.request.Request(
            f"{self.base_url}/run?op=encode&format=png&q=150",
            data=pam_bytes,
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
