#!/usr/bin/env python3
"""
test_cpp.py - Suite de testes de conformidade de contrato e codecs para C++.
"""

import os
import sys
import json
import time
import signal
import subprocess
import urllib.request
import urllib.error

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CPP_DIR = os.path.join(BASE_DIR, "cpp")
BIN_DIR = os.path.join(CPP_DIR, "bin")
SYNTHETIC_DIR = os.path.join(BASE_DIR, "harness", "fixtures", "synthetic")
CORPUS_DIR = os.path.join(BASE_DIR, "harness", "fixtures", "corpus")


def run_cmd(args, stdin=None, check=True):
    return subprocess.run(
        args,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def test_batch_analyze():
    print("[*] Testando op=analyze nos 3 binários batch...")
    sample_pam = os.path.join(SYNTHETIC_DIR, "solid_red.pam")
    assert os.path.exists(sample_pam), f"Fixture não encontrada: {sample_pam}"

    for bin_name in ["arena-batch", "arena-batch-portable", "arena-batch-clang"]:
        bin_path = os.path.join(BIN_DIR, bin_name)
        assert os.path.exists(bin_path), f"Binário não encontrado: {bin_path}"
        res = run_cmd([bin_path, "--op", "analyze", "--input", sample_pam])
        assert res.returncode == 0
        data = json.loads(res.stdout.decode("utf-8"))
        assert data["width"] == 64
        assert data["height"] == 64
        assert data["dominant_color"]["dominant_rgb"] == [255, 0, 0]
        assert data["phash"] == "0000000000000000"
        print(f"  [✓] {bin_name} op=analyze validado!")


def test_contract_rejections():
    print("[*] Testando rejeições de contrato (exit code 1)...")
    batch_bin = os.path.join(BIN_DIR, "arena-batch")
    sample_pam = os.path.join(SYNTHETIC_DIR, "solid_red.pam")

    # 1. q fora da faixa
    p = subprocess.run([batch_bin, "--op", "encode", "--format", "jpeg", "--q", "101", "--input", sample_pam],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode != 0, "Deveria rejeitar q=101"

    # 2. effort fora da faixa
    p = subprocess.run([batch_bin, "--op", "encode", "--format", "png", "--effort", "0", "--input", sample_pam],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode != 0, "Deveria rejeitar effort=0"

    # 3. avif lossless não suportado
    p = subprocess.run([batch_bin, "--op", "encode", "--format", "avif", "--mode", "lossless", "--input", sample_pam],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode != 0, "Deveria rejeitar avif lossless"

    # 4. modo inválido
    p = subprocess.run([batch_bin, "--op", "encode", "--format", "png", "--mode", "ultra", "--input", sample_pam],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode != 0, "Deveria rejeitar mode=ultra"

    print("  [✓] Todas as rejeições de contrato foram verificadas com sucesso!")


def test_portable_limitations():
    print("[*] Testando restrições do modo portável (sem bibliotecas externas)...")
    portable_bin = os.path.join(BIN_DIR, "arena-batch-portable")
    sample_pam = os.path.join(SYNTHETIC_DIR, "solid_red.pam")

    # Deve aceitar PNG
    p = subprocess.run([portable_bin, "--op", "encode", "--format", "png", "--input", sample_pam],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode == 0, f"Portable deveria suportar PNG encode: {p.stderr.decode('utf-8')}"

    # Deve rejeitar JPEG, WebP, JXL, AVIF no portable
    for fmt in ["jpeg", "webp", "jxl", "avif"]:
        p = subprocess.run([portable_bin, "--op", "encode", "--format", fmt, "--input", sample_pam],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert p.returncode != 0, f"Portable deveria rejeitar {fmt} encode"
    print("  [✓] Modo portável rejeita formatos externos e aceita PNG!")


def test_codecs_roundtrip():
    print("[*] Testando roundtrip de codecs (PNG, JPEG, WebP, JXL)...")
    batch_bin = os.path.join(BIN_DIR, "arena-batch")
    sample_pam = os.path.join(SYNTHETIC_DIR, "solid_red.pam")

    for fmt in ["png", "jpeg", "webp", "jxl"]:
        enc_res = run_cmd([batch_bin, "--op", "encode", "--format", fmt, "--input", sample_pam])
        assert len(enc_res.stdout) > 0, f"Encode {fmt} gerou 0 bytes"

        dec_res = run_cmd([batch_bin, "--op", "decode", "--format", fmt], stdin=enc_res.stdout)
        assert len(dec_res.stdout) > 0, f"Decode {fmt} gerou 0 bytes"
        assert dec_res.stdout.startswith(b"P7\n"), f"Decode {fmt} não retornou PAM P7 válido"
        print(f"  [✓] Codec {fmt.upper()} roundtrip OK ({len(enc_res.stdout)} bytes)")


def test_lossless_is_exact():
    print("[*] Testando que WebP e JXL lossless preservam todos os bytes (inclusive RGB sob alpha 0)...")
    width, height = 16, 16
    raster = bytes(v for i in range(width * height) for v in (200, 100, (i * 7) % 256, 0 if i % 2 else 255))
    pam = f"P7\nWIDTH {width}\nHEIGHT {height}\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n".encode() + raster
    for bin_name in ["arena-batch", "arena-batch-clang"]:
        batch_bin = os.path.join(BIN_DIR, bin_name)
        for fmt in ["webp", "jxl"]:
            enc = run_cmd([batch_bin, "--op", "encode", "--format", fmt, "--mode", "lossless"], stdin=pam).stdout
            dec = run_cmd([batch_bin, "--op", "decode", "--format", fmt], stdin=enc).stdout
            got = dec[dec.index(b"ENDHDR\n") + len(b"ENDHDR\n"):]
            assert got == raster, f"{bin_name} {fmt} lossless alterou a imagem"
            print(f"  [✓] {bin_name} {fmt.upper()} lossless exato")


def test_server():
    print("[*] Testando arena-server HTTP...")
    server_bin = os.path.join(BIN_DIR, "arena-server")
    port = 8899
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["ARENA_MAX_BODY_BYTES"] = "1048576"  # 1 MiB para teste de 413

    proc = subprocess.Popen([server_bin], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(0.5)

    try:
        # 1. GET /health
        req = urllib.request.Request(f"http://localhost:{port}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("status") == "ok"
            print("  [✓] GET /health -> 200 OK")

        # 2. POST /run?op=analyze
        sample_pam_bytes = open(os.path.join(SYNTHETIC_DIR, "solid_red.pam"), "rb").read()
        req = urllib.request.Request(
            f"http://localhost:{port}/run?op=analyze",
            data=sample_pam_bytes,
            headers={"Content-Type": "image/x-netpbm-pam"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            assert "X-Arena-Analyze-Ns" in resp.headers
            assert "X-Arena-Impl" in resp.headers
            data = json.loads(resp.read().decode("utf-8"))
            assert data["width"] == 64
            print("  [✓] POST /run?op=analyze -> 200 OK com telemetria")

        # 3. POST /run com parâmetro inválido -> 400
        try:
            req = urllib.request.Request(
                f"http://localhost:{port}/run?op=encode&format=jpeg&q=150",
                data=sample_pam_bytes,
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            assert False, "Deveria retornar 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            print("  [✓] POST /run q=150 -> 400 Bad Request")

        # 4. POST /run com payload > max_body_bytes -> 413
        try:
            big_payload = b"0" * (1048576 + 1024)
            req = urllib.request.Request(
                f"http://localhost:{port}/run?op=analyze",
                data=big_payload,
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            assert False, "Deveria retornar 413"
        except urllib.error.HTTPError as e:
            assert e.code == 413
            print("  [✓] POST /run excesso de bytes -> 413 Payload Too Large")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def main():
    print("=" * 60)
    print("Iniciando testes de conformidade C++ Arena")
    print("=" * 60)
    test_batch_analyze()
    test_contract_rejections()
    test_portable_limitations()
    test_codecs_roundtrip()
    test_lossless_is_exact()
    test_server()
    print("=" * 60)
    print("TODOS OS TESTES C++ PASSARAM COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    main()
