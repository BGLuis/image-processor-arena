"""Testes da bateria multi-implementação (benchmark_matrix.py) e do formato longo do dashboard
(scripts/prepare_dashboard_data.py): python3 -m unittest discover harness/tests"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HARNESS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, HARNESS)

import arena_quality as quality  # noqa: E402
import benchmark_arena as bench  # noqa: E402
import benchmark_matrix as matrix  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "prepare_dashboard_data", os.path.join(HARNESS, "..", "scripts", "prepare_dashboard_data.py")
)
prepare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prepare)


def make_bench():
    return bench.ArenaBenchmark(mode="http", validate=False, equal_quality=False)


def ok_stats(median):
    return {"wall_ms": {"median": median}, "codec_ms": {"median": median, "p25": median, "p75": median}, "out_bytes": 10}


class ErrorClassificationTests(unittest.TestCase):
    def test_client_errors_and_not_implemented_mean_unsupported(self):
        for status in (400, 415, 422, 501):
            self.assertEqual(matrix.classify_error(RuntimeError(f"HTTP {status}: formato")), "unsupported")

    def test_server_errors_and_network_failures_are_failures(self):
        for exc in (RuntimeError("HTTP 500: panic"), ConnectionRefusedError("recusada"), RuntimeError("HTTP 503: x")):
            self.assertEqual(matrix.classify_error(exc), "failed")

    def test_html_error_pages_collapse_to_one_line(self):
        page = "HTTP 400: <!DOCTYPE HTML><html><head><style>p {}</style></head><body><p>Message: avif</p></body></html>"
        self.assertEqual(matrix.short_error(RuntimeError(page)), "HTTP 400: Message: avif")


class MeasureTaskTests(unittest.TestCase):
    def setUp(self):
        self.bench = make_bench()
        self.engine = bench.Engine("x", "", "http://127.0.0.1:1/run")
        self.task = bench.Task("Encode PNG", "encode", "png", "lossless", "in.pam")

    def test_an_output_refused_by_validation_is_a_failure_not_a_time(self):
        with mock.patch.object(self.bench, "measure_engine", return_value=(ok_stats(1.0), b"x")), \
             mock.patch.object(self.bench, "validate_output", side_effect=quality.ValidationError("PSNR baixo")):
            res = matrix.measure_task(self.bench, self.engine, self.task, b"")
        self.assertEqual(res["status"], "failed")
        self.assertNotIn("codec_ms", res)

    def test_a_validated_output_keeps_its_stats(self):
        with mock.patch.object(self.bench, "measure_engine", return_value=(ok_stats(2.0), b"x")), \
             mock.patch.object(self.bench, "validate_output", return_value={"validated": True}):
            res = matrix.measure_task(self.bench, self.engine, self.task, b"")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["codec_ms"]["median"], 2.0)

    def test_an_unsupported_task_is_not_validated(self):
        validate = mock.Mock()
        with mock.patch.object(self.bench, "measure_engine", side_effect=RuntimeError("HTTP 400: jxl")), \
             mock.patch.object(self.bench, "validate_output", validate):
            res = matrix.measure_task(self.bench, self.engine, self.task, b"")
        self.assertEqual(res["status"], "unsupported")
        validate.assert_not_called()


class ServerFailureTests(unittest.TestCase):
    def test_a_variant_whose_server_dies_fails_every_task(self):
        b = make_bench()
        variant = matrix.Variant("go", "accelerated", "go", "quebrada", ("/bin/false",))
        with tempfile.TemporaryDirectory() as logs:
            rows, measured = matrix.run_matrix(b, [variant], logs)
        self.assertEqual(len(rows), len(b.build_tasks()))
        self.assertTrue(all(r["status"] == "failed" for r in rows))
        self.assertEqual(len(measured), 1)

    def test_a_variant_without_binary_is_skipped(self):
        variant = matrix.Variant("go", "accelerated", "go", "ausente", ("go/bin/nao-existe",))
        with tempfile.TemporaryDirectory() as logs:
            rows, measured = matrix.run_matrix(make_bench(), [variant], logs)
        self.assertEqual((rows, measured), ([], []))


class LongFormatTests(unittest.TestCase):
    def row(self, task_id, impl, median, status="ok"):
        r = {"task_id": task_id, "task": f"t{task_id}", "op": "encode", "format": "png", "mode": "lossless",
             "image": "photo.pam", "mp": 1.0, "impl_id": impl, "language": impl.split(":")[0], "tier": "accelerated",
             "toolchain": "1", "lib": "x", "status": status}
        if status == "ok":
            r.update({"codec_ms": {"median": median, "p25": median, "p75": median}, "out_bytes": 5,
                      "quality": {"psnr_db": None}})
        return r

    def long_format(self, rows):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"metadata": {}, "results": rows}, f)
        try:
            return prepare.long_format(f.name)
        finally:
            os.unlink(f.name)

    def test_time_is_relative_to_the_fastest_supporting_implementation(self):
        out = self.long_format([
            self.row(1, "go:a", 4.0), self.row(1, "rust:a", 2.0), self.row(1, "python:a", 0.5, status="unsupported"),
        ])
        by_impl = {r["impl_id"]: r for r in out}
        self.assertEqual(set(by_impl), {"go:a", "rust:a"})
        self.assertEqual(by_impl["rust:a"]["rel_time"], 1.0)
        self.assertEqual(by_impl["go:a"]["rel_time"], 2.0)
        self.assertEqual((by_impl["rust:a"]["task_rank"], by_impl["go:a"]["task_rank"]), (1, 2))

    def test_failed_measurements_never_win(self):
        out = self.long_format([self.row(1, "cpp:a", 0.1, status="failed"), self.row(1, "go:a", 3.0)])
        self.assertEqual([(r["impl_id"], r["task_rank"]) for r in out], [("go:a", 1)])

    def test_each_task_is_ranked_independently(self):
        out = self.long_format([
            self.row(1, "go:a", 1.0), self.row(1, "rust:a", 2.0),
            self.row(2, "go:a", 9.0), self.row(2, "rust:a", 3.0),
        ])
        winners = {r["task_id"]: r["impl_id"] for r in out if r["task_rank"] == 1}
        self.assertEqual(winners, {1: "go:a", 2: "rust:a"})


if __name__ == "__main__":
    unittest.main()
