"""Testes unitários do harness (sem pytest): python3 -m unittest discover harness/tests

Os testes que precisam do decoder de referência são pulados quando o Pillow não está instalado;
no CI ele é instalado a partir de harness/requirements.txt."""

import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, HARNESS)

import arena_load as load  # noqa: E402
import arena_quality as quality  # noqa: E402
import benchmark_arena as bench  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CORPUS = os.path.join(HARNESS, "fixtures", "corpus")
HAS_PILLOW = quality.Image is not None


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def stats(median, p25=None, p75=None):
    return {"median": median, "p25": median if p25 is None else p25, "p75": median if p75 is None else p75}


def fake_result(op, go_ms, rust_ms, winner):
    return {
        "op": op,
        "metric": "wall_ms",
        "go": {"wall_ms": stats(go_ms)},
        "rust": {"wall_ms": stats(rust_ms)},
        "winner": winner,
    }


class ScoreboardTests(unittest.TestCase):
    def test_overlapping_quartiles_are_a_tie(self):
        go, rust = stats(10, 9, 12), stats(11, 10, 13)
        self.assertEqual(bench.decide_winner(go, rust)[0], "Empate")
        # a regra é simétrica: a ordem dos argumentos não muda o veredito
        self.assertEqual(bench.decide_winner(rust, go)[0], "Empate")

    def test_separated_quartiles_have_a_winner_and_a_speedup(self):
        winner, speedup = bench.decide_winner(stats(10, 9, 11), stats(20, 19, 21))
        self.assertEqual(winner, "Go")
        self.assertAlmostEqual(speedup, 2.0)
        self.assertEqual(bench.decide_winner(stats(20, 19, 21), stats(10, 9, 11))[0], "Rust")

    def test_geometric_mean_weighs_magnitude_not_count(self):
        # Rust vence 2 tarefas por 2x e o Go 1 por 10x: a contagem diz Rust, a razão diz o contrário.
        results = [
            fake_result("encode", 20, 10, "Rust"),
            fake_result("encode", 20, 10, "Rust"),
            fake_result("encode", 10, 100, "Go"),
        ]
        row = bench.per_operation(results)[-1]
        self.assertEqual((row["go_wins"], row["rust_wins"]), (1, 2))
        self.assertLess(row["geomean_go_over_rust"], 1.0)  # Go mais rápido no agregado
        self.assertAlmostEqual(row["geomean_go_over_rust"], (2 * 2 * 0.1) ** (1 / 3))

    def test_per_operation_groups_and_totals(self):
        results = [
            fake_result("analyze", 40, 10, "Rust"),
            fake_result("decode", 10, 10, "Empate"),
            fake_result("decode", 30, 10, "Rust"),
        ]
        rows = {r["op"]: r for r in bench.per_operation(results)}
        self.assertEqual(rows["analyze"]["tasks"], 1)
        self.assertEqual(rows["decode"]["ties"], 1)
        self.assertEqual(rows["total"]["tasks"], 3)
        self.assertAlmostEqual(rows["decode"]["geomean_go_over_rust"], (1 * 3) ** 0.5)

    def test_describe_ratio(self):
        self.assertEqual(bench.describe_ratio(2.0), "Rust 2.00x mais rápido")
        self.assertEqual(bench.describe_ratio(0.5), "Go 2.00x mais rápido")
        self.assertEqual(bench.describe_ratio(1.001), "equivalentes")
        self.assertEqual(bench.describe_ratio(None), "-")


class PamTests(unittest.TestCase):
    def test_reads_the_corpus_header(self):
        self.assertEqual(bench.read_pam_dims(os.path.join(CORPUS, "photo.pam")), (512, 512, 3))
        self.assertEqual(bench.read_pam_dims(os.path.join(CORPUS, "alpha.pam"))[2], 4)

    def test_invalid_header_is_an_error_not_512x512(self):
        with tempfile.NamedTemporaryFile(suffix=".pam") as f:
            f.write(b"not a pam file")
            f.flush()
            with self.assertRaises(ValueError):
                bench.read_pam_dims(f.name)

    def test_missing_field_is_reported(self):
        with self.assertRaisesRegex(ValueError, "HEIGHT"):
            quality.parse_pam_header(b"P7\nWIDTH 2\nDEPTH 3\nMAXVAL 255\nENDHDR\n")

    def test_truncated_raster_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "truncado"):
            quality.parse_pam(b"P7\nWIDTH 2\nHEIGHT 2\nDEPTH 3\nMAXVAL 255\nENDHDR\n" + b"\x00" * 5)


class MatchingQTests(unittest.TestCase):
    def test_finds_the_smallest_q_that_reaches_the_target(self):
        psnr = lambda q: 20 + q / 5  # noqa: E731  crescente: q=50 dá 30 dB
        self.assertEqual(quality.find_matching_q(psnr, 30.0), 50)
        self.assertEqual(quality.find_matching_q(psnr, 30.1), 51)

    def test_target_out_of_reach_returns_the_bounds(self):
        psnr = lambda q: 20 + q / 5  # noqa: E731
        self.assertEqual(quality.find_matching_q(psnr, 99.0), 100)
        self.assertEqual(quality.find_matching_q(psnr, 1.0), 1)

    def test_each_q_is_evaluated_once_and_the_search_is_logarithmic(self):
        calls = []

        def psnr(q):
            calls.append(q)
            return 20 + q / 5

        quality.find_matching_q(psnr, 33.0)
        self.assertEqual(len(calls), len(set(calls)))
        self.assertLessEqual(len(calls), 9)


class LoadTests(unittest.TestCase):
    def sample(self):
        with open(os.path.join(DATA, "oha_1.16_sample.json")) as f:
            return f.read()

    def test_parses_a_real_oha_report(self):
        s = load.parse_oha_json(self.sample())
        self.assertEqual((s.requests, s.ok_requests), (40, 40))
        self.assertAlmostEqual(s.success_rate, 1.0)
        self.assertAlmostEqual(s.requests_per_sec, 167.3778, places=3)
        # o JSON do oha traz segundos; o harness reporta ms
        self.assertAlmostEqual(s.p50_ms, 21.497707, places=4)
        self.assertAlmostEqual(s.p95_ms, 37.084596, places=4)
        self.assertAlmostEqual(s.p99_ms, 44.433306, places=4)
        self.assertLess(s.p50_ms, s.p95_ms)
        self.assertLessEqual(s.p95_ms, s.p99_ms)

    def test_deadline_aborts_are_not_server_failures(self):
        doc = json.loads(self.sample())
        doc["errorDistribution"] = {"aborted due to deadline": 4}
        s = load.parse_oha_json(json.dumps(doc))
        self.assertEqual(s.aborted_at_deadline, 4)
        self.assertEqual(s.errors, {})
        self.assertEqual(s.success_rate, 1.0)

    def test_real_errors_and_non_2xx_lower_the_success_rate(self):
        doc = json.loads(self.sample())
        doc["statusCodeDistribution"] = {"200": 30, "400": 8}
        doc["errorDistribution"] = {"connection reset": 2}
        s = load.parse_oha_json(json.dumps(doc))
        self.assertEqual((s.requests, s.ok_requests), (40, 30))
        self.assertAlmostEqual(s.success_rate, 0.75)

    def test_unexpected_output_raises(self):
        for text in ("", "{}", '{"summary": {}}', "not json"):
            with self.assertRaises(load.LoadError):
                load.parse_oha_json(text)

    def test_command_line(self):
        cmd = load.oha_command("http://x/run?op=analyze", "/tmp/body", 5, 8, oha_bin="oha")
        self.assertEqual(cmd[0], "oha")
        for flag, value in (("-z", "5s"), ("-c", "8"), ("-m", "POST"), ("-D", "/tmp/body")):
            self.assertEqual(cmd[cmd.index(flag) + 1], value)
        self.assertIn("--no-tui", cmd)
        self.assertEqual(cmd[-1], "http://x/run?op=analyze")


@unittest.skipUnless(HAS_PILLOW, "Pillow não instalado")
class ReferenceMetricTests(unittest.TestCase):
    def solid(self, rgb, mode="RGB"):
        img = quality.Image.new("RGB", (4, 4), rgb)
        return img.convert(mode)

    def test_psnr_of_a_one_level_error(self):
        psnr = quality.rgb_psnr(self.solid((10, 20, 30)), self.solid((10, 20, 31)))
        self.assertAlmostEqual(psnr, 10 * __import__("math").log10(255 * 255 * 3), places=2)

    def test_identical_images_have_infinite_psnr(self):
        self.assertEqual(quality.rgb_psnr(self.solid((1, 2, 3)), self.solid((1, 2, 3))), float("inf"))

    def test_exact_match_sees_rgb_differences_even_when_alpha_is_equal(self):
        # Regressão: o getbbox() padrão do Pillow olha só o alpha em RGBA e dava "idêntico" para tudo.
        a = self.solid((10, 20, 30), "RGBA")
        b = self.solid((10, 20, 31), "RGBA")
        self.assertTrue(quality.exact_match(a, a.copy()))
        self.assertFalse(quality.exact_match(a, b))

    def test_exact_match_compares_alpha_and_treats_missing_alpha_as_opaque(self):
        opaque = self.solid((10, 20, 30), "RGBA")
        translucent = opaque.copy()
        translucent.putalpha(128)
        self.assertFalse(quality.exact_match(opaque, translucent))
        self.assertTrue(quality.exact_match(opaque, self.solid((10, 20, 30))))

    def test_psnr_ignores_transparent_pixels(self):
        want = self.solid((10, 20, 30), "RGBA")
        got = self.solid((200, 200, 200), "RGBA")
        want.putpixel((0, 0), (10, 20, 30, 255))
        got.putpixel((0, 0), (10, 20, 30, 255))
        for x in range(4):
            for y in range(4):
                if (x, y) != (0, 0):
                    want.putpixel((x, y), (10, 20, 30, 0))  # transparente: a cor não conta
        self.assertEqual(quality.rgb_psnr(want, got), float("inf"))

    def test_dimension_mismatch_is_a_validation_error(self):
        with self.assertRaises(quality.ValidationError):
            quality.rgb_psnr(self.solid((0, 0, 0)), quality.Image.new("RGB", (5, 4)))

    def test_reference_decode_rejects_the_wrong_format(self):
        import io

        buf = io.BytesIO()
        self.solid((1, 2, 3)).save(buf, "PNG")
        self.assertEqual(quality.reference_decode("png", buf.getvalue()).size, (4, 4))
        with self.assertRaises(quality.ValidationError):
            quality.reference_decode("jpeg", buf.getvalue())
        with self.assertRaises(quality.ValidationError):
            quality.reference_decode("png", b"garbage")


FAKE_ENGINE = textwrap.dedent(
    """\
    #!{python}
    # Engine falso: grava em --output o arquivo indicado por FAKE_OUTPUT_<KEY>, ignorando a entrada.
    import os, shutil, sys
    args = sys.argv[1:]
    if args[args.index("--op") + 1] == "analyze" or "--output" not in args:
        sys.exit(0)
    shutil.copyfile(os.environ["FAKE_OUTPUT"], args[args.index("--output") + 1])
    """
)


@unittest.skipUnless(HAS_PILLOW, "Pillow não instalado")
class ValidationFlowTests(unittest.TestCase):
    """O harness só aceita um tempo depois de validar a saída: um engine que grava a imagem errada
    tem de virar falha, não vitória."""

    def make_engine(self, directory, name, output_path):
        path = os.path.join(directory, name)
        with open(path, "w") as f:
            f.write(FAKE_ENGINE.format(python=sys.executable))
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        # o FAKE_OUTPUT é fixado no próprio script para que cada engine grave um arquivo diferente
        with open(path) as f:
            body = f.read().replace('os.environ["FAKE_OUTPUT"]', repr(output_path))
        with open(path, "w") as f:
            f.write(body)
        return path

    def benchmark(self, directory, good_path, bad_path):
        b = bench.ArenaBenchmark(
            mode="batch",
            go_bin=self.make_engine(directory, "go", good_path),
            rust_bin=self.make_engine(directory, "rust", bad_path),
            corpus_dir=CORPUS,
            warmup=0,
            equal_quality=False,
            tmp_dir=directory,
        )
        b.startup_ms = {k: bench.summarize([1.0] * 5) for k in ("go", "rust")}
        return b

    def png_of(self, directory, name, pam_name, tweak=False):
        img = quality.pam_to_image(quality.parse_pam(read_bytes(os.path.join(CORPUS, pam_name))))
        if tweak:
            img.putpixel((3, 3), (255 - img.getpixel((3, 3))[0], 0, 0))
        path = os.path.join(directory, name)
        img.save(path, "PNG")
        return path

    def test_a_lossless_output_that_differs_by_one_pixel_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            good = self.png_of(d, "good.png", "photo.pam")
            bad = self.png_of(d, "bad.png", "photo.pam", tweak=True)
            b = self.benchmark(d, good, bad)
            task = bench.Task("Encode PNG [photo.pam]", "encode", "png", "lossless", os.path.join(CORPUS, "photo.pam"))
            with self.assertRaises(bench.TaskFailure) as ctx:
                b.benchmark_task(task)
            self.assertEqual(ctx.exception.engine, "rust")
            self.assertIn("recusada", ctx.exception.message)

    def test_a_lossy_output_of_the_wrong_picture_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            good = self.png_of(d, "good.png", "photo.pam")
            other = os.path.join(d, "other.png")
            quality.pam_to_image(quality.parse_pam(read_bytes(os.path.join(CORPUS, "screenshot.pam")))).save(other, "PNG")
            b = self.benchmark(d, good, other)
            # JPEG pedido, mas o engine falso devolve PNG: o decoder de referência recusa o formato
            task = bench.Task("Encode JPEG [photo.pam]", "encode", "jpeg", "lossy", os.path.join(CORPUS, "photo.pam"))
            with self.assertRaises(bench.TaskFailure):
                b.benchmark_task(task)

    def test_correct_outputs_are_accepted_and_report_exact(self):
        with tempfile.TemporaryDirectory() as d:
            good = self.png_of(d, "good.png", "photo.pam")
            b = self.benchmark(d, good, good)
            task = bench.Task("Encode PNG [photo.pam]", "encode", "png", "lossless", os.path.join(CORPUS, "photo.pam"))
            result = b.benchmark_task(task)
            self.assertTrue(result["go"]["quality"]["exact"])
            self.assertTrue(result["rust"]["quality"]["validated"])


class FailureReportingTests(unittest.TestCase):
    def make(self):
        b = bench.ArenaBenchmark(validate=False, equal_quality=False)
        b.results = []
        return b

    def test_failures_reach_the_json_and_markdown_reports(self):
        b = self.make()
        b.record_failure("Encode AVIF Lossy [photo.pam]", bench.TaskFailure("rust", "saída recusada: PSNR 12.00 dB | baixo"))
        with tempfile.TemporaryDirectory() as d:
            b.export_reports(d)
            with open(os.path.join(d, "benchmark_results.json")) as f:
                report = json.load(f)
            with open(os.path.join(d, "PODIUM.md")) as f:
                markdown = f.read()
        self.assertEqual(report["failures"][0]["engine"], "rust")
        self.assertIn("Falhas", markdown)
        self.assertIn("Encode AVIF Lossy [photo.pam]", markdown)
        self.assertIn("PSNR 12.00 dB \\| baixo", markdown)  # o pipe é escapado para não quebrar a tabela

    def test_exit_code_is_nonzero_when_a_task_failed(self):
        def fake_suite(self_):
            self_.record_failure("Decode JXL [photo.jxl]", bench.TaskFailure("go", "boom"))
            self_.results = []
            return []

        with tempfile.TemporaryDirectory() as d, mock.patch.object(bench.ArenaBenchmark, "run_suite", fake_suite):
            argv = ["benchmark_arena.py", "--no-validate", "--output-dir", d]
            with mock.patch.object(sys, "argv", argv):
                self.assertEqual(bench.main(), 1)
            with mock.patch.object(sys, "argv", argv + ["--allow-failures"]):
                self.assertEqual(bench.main(), 0)


class TmpDirTests(unittest.TestCase):
    def test_explicit_env_wins_then_tmpfs_then_default(self):
        with tempfile.TemporaryDirectory() as tmpfs:
            arena = {"benchmarks": {"tmpfs_path": tmpfs}}
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ARENA_TMPDIR", None)
                self.assertEqual(bench.default_tmp_dir(arena), tmpfs)
                self.assertIsNone(bench.default_tmp_dir({"benchmarks": {"tmpfs_path": "/definitely/not/here"}}))
            with mock.patch.dict(os.environ, {"ARENA_TMPDIR": "/somewhere"}):
                self.assertEqual(bench.default_tmp_dir(arena), "/somewhere")


if __name__ == "__main__":
    unittest.main()
