#!/usr/bin/env python3
"""
make_seam_carving_corpus.py - Gerador de Sub-Corpus Dedicado para Seam Carving.

Gera sub-corpus com dimensões reduzidas (400x300, ~0,12 MP) em harness/fixtures/seam_carving:
1. photo: Cena fotográfica contínua com gradientes e montanhas.
2. screenshot: Interface gráfica de usuário com grandes áreas planas e bordas nítidas.
3. illustration: Arte vetorial/geométrica com paleta discreta.

Dimensões reduzidas são necessárias para que algoritmos iterativos de seam carving
(com cálculo de gradiente de Sobel e remoção dinâmica de custo acumulado) executem
dentro dos limites aceitáveis de tempo de benchmark (issue #27).
"""

import os
import sys
import argparse

# Permite importar geradores de make_corpus
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_corpus import generate_photo, generate_screenshot, generate_illustration, write_pam

SEAM_WIDTH = 400
SEAM_HEIGHT = 300


def main() -> int:
    parser = argparse.ArgumentParser(description="Gerador de sub-corpus de seam carving (400x300).")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Diretório de saída (padrão: harness/fixtures/seam_carving)",
    )
    args = parser.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_dir = args.out_dir or os.path.join(base_dir, "harness", "fixtures", "seam_carving")
    os.makedirs(out_dir, exist_ok=True)

    w, h = SEAM_WIDTH, SEAM_HEIGHT
    print(f"[*] Gerando sub-corpus de seam carving ({w}x{h}) em: {out_dir}")

    generators = [
        ("photo", 3, "RGB", generate_photo),
        ("screenshot", 3, "RGB", generate_screenshot),
        ("illustration", 3, "RGB", generate_illustration),
    ]

    for name, depth, tupltype, gen_fn in generators:
        print(f"[*] Gerando classe: {name} ({w}x{h})...")
        raster = gen_fn(w, h)
        pam_path = os.path.join(out_dir, f"{name}.pam")
        write_pam(pam_path, w, h, depth, tupltype, raster)
        print(f"    [+] PAM gerado: {os.path.basename(pam_path)} ({len(raster)} bytes)")

    print(f"[+] Sub-corpus de seam carving gerado com sucesso em: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
