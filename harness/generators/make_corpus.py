#!/usr/bin/env python3
"""
make_corpus.py - Gerador de Corpus Representativo para o image-processor-arena.

Gera as 4 classes canônicas de imagens do projeto no formato Netpbm PAM P7:
1. photo: Cena fotográfica contínua com gradientes e texturas de alta frequência.
2. screenshot: Interface gráfica de usuário com grandes áreas planas e bordas nítidas.
3. illustration: Arte vetorial/ilustração gráfica com paleta discreta e formas geométricas.
4. alpha: Elemento gráfico com canal Alpha contendo transparência total, semitransparência e opacidade.

Gera também referências codificadas (.png, .jpg, .webp, .avif, .jxl): com as ferramentas CLI
(cjxl, cwebp, avifenc) quando existirem, senão com o Pillow (harness/requirements.txt).

Corpus grande (--large): as mesmas quatro classes em 2048x2048 (4,19 MP) em harness/fixtures/corpus-large,
fora do git (.gitignore). Os arquivos do corpus padrão têm 0,26 MP, e nessa escala custos fixos (startup,
init de pacotes) pesam mais que o codec; com 4 MP o throughput em MP/s é mais representativo (issue #17).
A geração leva cerca de 15 s. Use com o benchmark:

    python3 harness/generators/make_corpus.py --large
    python3 harness/benchmark_arena.py --mode http --corpus-dir harness/fixtures/corpus-large
"""

import os
import sys
import math
import struct
import zlib
import shutil
import subprocess
import argparse
from typing import Tuple, List

DEFAULT_SIDE = 512
LARGE_SIDE = 2048  # 2048 x 2048 = 4,19 MP


# ---------------------------------------------------------------------------
# Escritor PAM P7
# ---------------------------------------------------------------------------
def write_pam(filepath: str, width: int, height: int, depth: int, tupltype: str, data: bytes) -> None:
    header = (
        f"P7\n"
        f"WIDTH {width}\n"
        f"HEIGHT {height}\n"
        f"DEPTH {depth}\n"
        f"MAXVAL 255\n"
        f"TUPLTYPE {tupltype}\n"
        f"ENDHDR\n"
    ).encode("ascii")
    with open(filepath, "wb") as f:
        f.write(header)
        f.write(data)


# ---------------------------------------------------------------------------
# Escritor PNG puro (stdlib Python zlib + struct)
# ---------------------------------------------------------------------------
def write_png(filepath: str, width: int, height: int, raw_bytes: bytes, has_alpha: bool = False) -> None:
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + chunk_type
            + data
            + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    channels = 4 if has_alpha else 3
    color_type = 6 if has_alpha else 2
    raw_stride = width * channels
    lines = []
    for y in range(height):
        lines.append(b"\x00" + raw_bytes[y * raw_stride : (y + 1) * raw_stride])
    compressed = zlib.compress(b"".join(lines), 9)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    png_data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    with open(filepath, "wb") as f:
        f.write(png_data)


# ---------------------------------------------------------------------------
# Geradores Procedurais de Classes
# ---------------------------------------------------------------------------

def generate_photo(width: int, height: int) -> bytes:
    """Gera uma cena fotográfica realista (céu, sol, montanhas, terreno e texturas multifrequenciais)."""
    buf = bytearray(width * height * 3)
    sun_x = width * 0.72
    sun_y = height * 0.28
    sun_radius = min(width, height) * 0.12

    for y in range(height):
        ny = y / float(height)
        row_off = y * width * 3

        for x in range(width):
            nx = x / float(width)
            pix_off = row_off + x * 3

            # Montanhas / terreno (duas camadas senoidais)
            h_layer1 = 0.52 + 0.12 * math.sin(nx * 7.5 + 0.4) + 0.05 * math.sin(nx * 19.3)
            h_layer2 = 0.68 + 0.10 * math.sin(nx * 11.2 + 1.8) + 0.04 * math.cos(nx * 27.1)

            if ny < h_layer1:
                # Céu: gradiente azul-celeste para alaranjado perto do horizonte
                sky_t = ny / h_layer1
                r = int(70 + 130 * sky_t)
                g = int(120 + 70 * sky_t)
                b = int(210 - 60 * sky_t)

                # Brilho solar com difusão
                dist_sun = math.hypot(x - sun_x, y - sun_y)
                if dist_sun < sun_radius * 2.5:
                    flare = max(0.0, 1.0 - (dist_sun / (sun_radius * 2.5)))
                    flare = flare * flare
                    r = min(255, int(r + 170 * flare))
                    g = min(255, int(g + 140 * flare))
                    b = min(255, int(b + 90 * flare))

                # Nuvens suaves
                cloud = math.sin(nx * 14.0 + ny * 6.0) * math.cos(nx * 9.0 - ny * 11.0)
                if cloud > 0.35:
                    cf = (cloud - 0.35) * 0.9
                    r = min(255, int(r * (1.0 - cf) + 245 * cf))
                    g = min(255, int(g * (1.0 - cf) + 245 * cf))
                    b = min(255, int(b * (1.0 - cf) + 250 * cf))

            elif ny < h_layer2:
                # Montanhas ao fundo (tons azulados/arroxeados atmosféricos)
                t_m = (ny - h_layer1) / (h_layer2 - h_layer1)
                r = int(90 + 30 * t_m + 15 * math.sin(nx * 40))
                g = int(85 + 40 * t_m + 12 * math.cos(nx * 45))
                b = int(130 + 20 * t_m + 10 * math.sin(nx * 33))

            else:
                # Terreno/floresta em primeiro plano (verdes e ocres com textura)
                t_f = (ny - h_layer2) / (1.0 - h_layer2)
                tex = 18 * math.sin(nx * 85.0 + ny * 65.0) + 12 * math.cos(nx * 160.0)
                r = max(0, min(255, int(45 + 50 * t_f + tex)))
                g = max(0, min(255, int(95 + 45 * t_f + tex * 1.2)))
                b = max(0, min(255, int(35 + 25 * t_f + tex * 0.7)))

            buf[pix_off] = r
            buf[pix_off + 1] = g
            buf[pix_off + 2] = b

    return bytes(buf)


def generate_screenshot(width: int, height: int) -> bytes:
    """Gera uma interface gráfica de aplicação (Dark Mode IDE) com janelas, barras de menu e código."""
    buf = bytearray(width * height * 3)

    bg_main = (30, 30, 30)
    bg_sidebar = (37, 37, 38)
    bg_title = (45, 45, 48)
    bg_status = (0, 122, 204)
    line_num_color = (133, 133, 133)

    title_h = max(24, int(height * 0.04))
    status_h = max(20, int(height * 0.03))
    sidebar_w = max(60, int(width * 0.22))
    gutter_w = max(30, int(width * 0.06))

    for y in range(height):
        row_off = y * width * 3

        for x in range(width):
            pix_off = row_off + x * 3

            if y < title_h:
                # Barra de título
                if x < title_h * 3:
                    # Botões de janela (vermelho, amarelo, verde)
                    btn_idx = x // title_h
                    cx = (btn_idx + 0.5) * title_h
                    cy = title_h * 0.5
                    d = math.hypot(x - cx, y - cy)
                    if d < title_h * 0.22:
                        color = (255, 95, 86) if btn_idx == 0 else ((255, 189, 46) if btn_idx == 1 else (39, 201, 63))
                    else:
                        color = bg_title
                else:
                    color = bg_title

            elif y >= height - status_h:
                # Barra de status azul
                color = bg_status

            elif x < sidebar_w:
                # Barra lateral de arquivos
                # Linhas horizontais simulando lista de pastas
                line_idx = (y - title_h) // 22
                if (y - title_h) % 22 == 0:
                    color = (48, 48, 50)
                elif (x > 15 and x < 25) and ((y - title_h) % 22 in [6, 7, 8, 9, 10, 11, 12]):
                    # Ícone de pasta
                    color = (220, 180, 80)
                elif (x > 32 and x < sidebar_w - 20) and ((y - title_h) % 22 in [8, 9, 10]):
                    color = (200, 200, 200)
                else:
                    color = bg_sidebar

            elif x < sidebar_w + gutter_w:
                # Gutter / números de linha
                if x == sidebar_w + gutter_w - 1:
                    color = (55, 55, 60)
                elif (y - title_h) % 18 in [6, 7, 8, 9, 10]:
                    color = line_num_color
                else:
                    color = bg_main

            else:
                # Editor de código: blocos de tokens com realce de sintaxe
                line_idx = (y - title_h) // 18
                y_in_line = (y - title_h) % 18
                code_x = x - (sidebar_w + gutter_w + 16)

                if y_in_line in [5, 6, 7, 8, 9, 10, 11] and code_x > 0:
                    # Padrão pseudo-sintático
                    token_slot = (code_x // 45) + (line_idx * 7)
                    rem = code_x % 45
                    if rem < 36:
                        t_type = token_slot % 5
                        if t_type == 0:
                            color = (86, 156, 214)   # Azul palavra-chave
                        elif t_type == 1:
                            color = (220, 220, 170) # Amarelo função
                        elif t_type == 2:
                            color = (206, 145, 120) # Laranja string
                        elif t_type == 3:
                            color = (106, 153, 85)  # Verde comentário
                        else:
                            color = (156, 220, 254) # Ciano variável
                    else:
                        color = bg_main
                else:
                    color = bg_main

            buf[pix_off] = color[0]
            buf[pix_off + 1] = color[1]
            buf[pix_off + 2] = color[2]

    return bytes(buf)


def generate_illustration(width: int, height: int) -> bytes:
    """Gera uma ilustração vetorial com paleta flat design, formas geométricas nítidas e alta área plana."""
    buf = bytearray(width * height * 3)

    c_bg = (248, 246, 240)       # Bege claro
    c_sun = (255, 107, 107)      # Coral / Sol
    c_sea = (78, 205, 196)       # Turquesa
    c_dark = (41, 47, 54)        # Azul escuro
    c_gold = (255, 230, 109)     # Amarelo dourado

    cx = width * 0.5
    cy = height * 0.42
    r_sun = min(width, height) * 0.26

    for y in range(height):
        row_off = y * width * 3

        for x in range(width):
            pix_off = row_off + x * 3

            # Fundo padrão
            color = c_bg

            # Círculo central (Sol)
            d_center = math.hypot(x - cx, y - cy)
            if d_center < r_sun:
                color = c_sun
            elif d_center < r_sun * 1.35 and (x + y) % 16 < 4:
                # Raios geométricos concêntricos
                color = c_gold

            # Faixa ondulada estilo onda plana
            wave_y = height * 0.65 + math.sin(x / float(width) * 6.28 * 2) * (height * 0.05)
            if y > wave_y:
                color = c_sea

            # Elemento geométrico triangular em contraste
            tx0 = width * 0.2
            tx1 = width * 0.8
            if y > height * 0.78 and x > tx0 and x < tx1:
                if (x - tx0) / (tx1 - tx0) > (y - height * 0.78) / (height * 0.22):
                    color = c_dark

            buf[pix_off] = color[0]
            buf[pix_off + 1] = color[1]
            buf[pix_off + 2] = color[2]

    return bytes(buf)


def generate_alpha(width: int, height: int) -> bytes:
    """Gera um asset gráfico flutuante com canal Alpha completo (RGB_ALPHA)."""
    buf = bytearray(width * height * 4)

    card_x0 = width * 0.20
    card_x1 = width * 0.80
    card_y0 = height * 0.22
    card_y1 = height * 0.78
    corner_r = min(width, height) * 0.08

    shadow_blur = min(width, height) * 0.08
    badge_cx = width * 0.5
    badge_cy = height * 0.45
    badge_r = min(width, height) * 0.16

    for y in range(height):
        row_off = y * width * 4

        for x in range(width):
            pix_off = row_off + x * 4

            # Distância ao retângulo arredondado do cartão
            dx = max(0.0, max(card_x0 + corner_r - x, x - (card_x1 - corner_r)))
            dy = max(0.0, max(card_y0 + corner_r - y, y - (card_y1 - corner_r)))
            dist_card = math.hypot(dx, dy) - corner_r

            # Sombra projetada deslocada (+10px no eixo Y)
            s_dx = max(0.0, max(card_x0 + corner_r - x, x - (card_x1 - corner_r)))
            s_dy = max(0.0, max(card_y0 + 10 + corner_r - y, y - (card_y1 + 10 - corner_r)))
            dist_shadow = math.hypot(s_dx, s_dy) - corner_r

            if dist_card <= 0:
                # Interior do cartão arredondado (Branco/Cinza azulado com badge colorido)
                dist_badge = math.hypot(x - badge_cx, y - badge_cy)
                if dist_badge < badge_r:
                    # Emblema central roxo
                    r, g, b, a = 120, 80, 240, 255
                elif dist_badge < badge_r + 6:
                    # Borda do emblema dourada
                    r, g, b, a = 255, 200, 60, 255
                else:
                    # Superfície do cartão
                    grad = (y - card_y0) / (card_y1 - card_y0)
                    r = int(245 - 20 * grad)
                    g = int(248 - 18 * grad)
                    b = int(255 - 15 * grad)
                    a = 255
            elif dist_card < 1.0:
                # Anti-aliasing da borda do cartão
                alpha_edge = max(0, min(255, int((1.0 - dist_card) * 255)))
                r, g, b, a = 245, 248, 255, alpha_edge
            elif dist_shadow < shadow_blur:
                # Sombra suave exterior
                s_factor = max(0.0, 1.0 - (dist_shadow / shadow_blur))
                alpha_shadow = int(s_factor * s_factor * 120)
                r, g, b, a = 20, 20, 30, alpha_shadow
            else:
                # Fundo 100% transparente
                r, g, b, a = 0, 0, 0, 0

            buf[pix_off] = r
            buf[pix_off + 1] = g
            buf[pix_off + 2] = b
            buf[pix_off + 3] = a

    return bytes(buf)


# ---------------------------------------------------------------------------
# Encoders de Referência
# ---------------------------------------------------------------------------
def encode_reference_files(pam_path: str, base_name: str, out_dir: str, depth: int, width: int, height: int, raster: bytes) -> None:
    # 1. PNG (lossless de referência)
    png_path = os.path.join(out_dir, f"{base_name}.png")
    write_png(png_path, width, height, raster, has_alpha=(depth == 4))
    print(f"       -> Gerado PNG: {os.path.basename(png_path)} ({os.path.getsize(png_path)} bytes)")

    # 2-5. JXL, WebP e AVIF pelas ferramentas CLI; o que faltar, o Pillow gera. O JPEG de referência
    # vem do Pillow (a imagem alpha não tem JPEG: o formato não tem canal alpha).
    cli = [
        ("jxl", "cjxl", lambda b, o: [b, pam_path, o, "-e", "7", "-d", "1.0"]),
        ("webp", "cwebp", lambda b, o: [b, "-q", "80", pam_path, "-o", o]),
        ("avif", "avifenc", lambda b, o: [b, "-s", "6", "-q", "75", pam_path, o]),
    ]
    missing = []
    for ext, tool, make_cmd in cli:
        binary = shutil.which(tool)
        out_path = os.path.join(out_dir, f"{base_name}.{ext}")
        if not binary:
            missing.append(ext)
            continue
        try:
            subprocess.run(make_cmd(binary, out_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            print(f"       -> Gerado {ext.upper()} ({tool}): {os.path.basename(out_path)} ({os.path.getsize(out_path)} bytes)")
        except Exception as e:
            print(f"       [!] Erro ao invocar {tool}: {e}")
            missing.append(ext)

    encode_with_pillow(out_dir, base_name, depth, width, height, raster, missing + ([] if depth == 4 else ["jpg"]))


def encode_with_pillow(out_dir: str, base_name: str, depth: int, width: int, height: int, raster: bytes, wanted: List[str]) -> None:
    if not wanted:
        return
    try:
        from PIL import Image
    except ImportError:
        print(f"       [!] Sem ferramentas CLI nem Pillow: pulei {', '.join(wanted)} (pip install -r harness/requirements.txt)")
        return
    try:
        import pillow_jxl  # noqa: F401
    except ImportError:
        pass

    image = Image.frombytes("RGBA" if depth == 4 else "RGB", (width, height), raster)
    options = {
        "jpg": {"format": "JPEG", "quality": 80, "subsampling": "4:2:0"},
        "webp": {"format": "WEBP", "quality": 80},
        "avif": {"format": "AVIF", "quality": 75, "speed": 6},
        "jxl": {"format": "JXL", "quality": 90, "effort": 7},
    }
    for ext in wanted:
        out_path = os.path.join(out_dir, f"{base_name}.{ext}")
        try:
            image.save(out_path, **options[ext])
            print(f"       -> Gerado {ext.upper()} (Pillow): {os.path.basename(out_path)} ({os.path.getsize(out_path)} bytes)")
        except Exception as e:
            print(f"       [!] Pillow não gerou {ext}: {e}")


# ---------------------------------------------------------------------------
# Ponto de Entrada CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Gerador de corpus de imagens para o image-processor-arena.")
    parser.add_argument("--width", type=int, default=None, help="Largura das imagens em pixels (padrão: 512; 2048 com --large)")
    parser.add_argument("--height", type=int, default=None, help="Altura das imagens em pixels (padrão: 512; 2048 com --large)")
    parser.add_argument(
        "--large",
        action="store_true",
        help="Gera o corpus grande (2048x2048, 4,19 MP por classe) em harness/fixtures/corpus-large",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Diretório de saída (padrão: harness/fixtures/corpus, ou corpus-large com --large)",
    )
    args = parser.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    default_dir = "corpus-large" if args.large else "corpus"
    out_dir = args.out_dir or os.path.join(base_dir, "harness", "fixtures", default_dir)
    os.makedirs(out_dir, exist_ok=True)

    side = LARGE_SIDE if args.large else DEFAULT_SIDE
    w = args.width or side
    h = args.height or side
    print(f"[*] Gerando corpus de imagens ({w}x{h}) em: {out_dir}")

    generators = [
        ("photo", 3, "RGB", generate_photo),
        ("screenshot", 3, "RGB", generate_screenshot),
        ("illustration", 3, "RGB", generate_illustration),
        ("alpha", 4, "RGB_ALPHA", generate_alpha),
    ]

    for name, depth, tupltype, gen_fn in generators:
        print(f"[*] Gerando classe: {name} (depth={depth}, tupltype={tupltype})...")
        raster = gen_fn(w, h)
        pam_path = os.path.join(out_dir, f"{name}.pam")
        write_pam(pam_path, w, h, depth, tupltype, raster)
        print(f"    [+] Arquivo PAM gerado: {os.path.basename(pam_path)} ({len(raster)} bytes)")

        # Gera referências codificadas
        encode_reference_files(pam_path, name, out_dir, depth, w, h, raster)

    print(f"[+] Corpus gerado com sucesso em: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
