# 🏆 Pódio da Arena: Go Puro × Rust Puro

**Modo de Execução**: `HTTP`  
**Métrica primária**: codec (servidor, X-Arena-*-Ns)  
**Iterações por teste**: 10 medidas (+ 3 warmup); tempos como mediana [p25-p75]  
**Máquina**: Intel(R) Xeon(R) Processor @ 2.10GHz (4 CPUs lógicas), Linux-6.18.44-fc-v51-x86_64-with-glibc2.39  
**Data da Coleta**: 2026-10-02 09:57:36

## Notas de Medição

- Métrica primária: tempo de codec reportado pelo servidor nos headers X-Arena-*-Ns (transcode = decode + encode; analyze = só a análise nos dois servidores). A coluna de parede do cliente inclui rede, PAM e serialização. Requisições sequenciais em conexão persistente.
- Regra de empate (a mesma no console, no Markdown e no JSON): há empate estatístico quando os intervalos p25-p75 das duas medianas se sobrepõem; só vale como vitória uma diferença fora deles.
- Razão geométrica = média geométrica de (tempo do Go ÷ tempo do Rust) sobre as tarefas; acima de 1 o Rust é mais rápido, abaixo de 1 o Go. Ela pondera a magnitude, que a contagem de vitórias ignora.
- Cada saída é decodificada por um decoder de referência (Pillow/libjxl/libavif) antes de o tempo ser aceito; lossless exige igualdade exata e lossy um PSNR mínimo por classe de imagem. PSNR RGB sobre os pixels opacos do original. O tempo só é comparável junto do tamanho e da qualidade.

## 🥇 Classificação Geral

**Razão geométrica Go/Rust (tempo): 2.67x** (Rust 2.67x mais rápido).

Vitórias em tempo de codec (empate estatístico quando os intervalos p25-p75 se sobrepõem):

- Go Puro: 7/34 (20.6%)
- Rust Puro: 26/34 (76.5%)
- Empates estatísticos: 1/34 (2.9%)

## 🧮 Por Operação

| Operação | Tarefas | Go | Rust | Empates | Razão geométrica Go/Rust | Leitura |
|---|---|---|---|---|---|---|
| analyze | 4 | 0 | 3 | 1 | 1.11x | Rust 1.11x mais rápido |
| encode | 21 | 3 | 18 | 0 | 4.14x | Rust 4.14x mais rápido |
| decode | 5 | 2 | 3 | 0 | 1.99x | Rust 1.99x mais rápido |
| transcode | 4 | 2 | 2 | 0 | 0.91x | Go 1.10x mais rápido |
| total | 34 | 7 | 26 | 1 | 2.67x | Rust 2.67x mais rápido |

## 📊 Tabela Completa de Resultados

Parâmetros (arena.toml `[params]`): q=75, effort=4, mode padrão `lossy`. Go/Rust acima de 1 significa saída maior no Go; o tempo só é comparável junto do tamanho e da qualidade (PSNR RGB contra o original, decodificado pela referência; `exato` = idêntico bit a bit).

| Tarefa / Operação | Go codec (ms) | Go MP/s | Rust codec (ms) | Rust MP/s | Go parede cliente (ms) | Rust parede cliente (ms) | Go (bytes) | Rust (bytes) | Go/Rust | PSNR Go | PSNR Rust | 🥇 Vencedor (codec) | Vantagem |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Analyze [photo.pam] | 18.94 [18.34-19.91] | 13.84 | 17.44 [16.76-18.09] | 15.03 | 21.25 | 18.51 | 0 | 0 | - | - | - | Rust | **1.09x** |
| Analyze [screenshot.pam] | 18.19 [17.98-18.46] | 14.41 | 16.62 [16.41-17.15] | 15.78 | 19.24 | 17.63 | 0 | 0 | - | - | - | Rust | **1.09x** |
| Analyze [illustration.pam] | 18.91 [18.01-20.30] | 13.86 | 17.80 [15.99-18.28] | 14.73 | 19.95 | 18.83 | 0 | 0 | - | - | - | Empate | **1.06x** |
| Analyze [alpha.pam] | 19.50 [18.37-20.57] | 13.45 | 16.08 [15.98-16.45] | 16.30 | 21.59 | 17.08 | 0 | 0 | - | - | - | Rust | **1.21x** |
| Encode PNG [photo.pam] | 16.73 [16.41-17.20] | 15.67 | 68.02 [66.66-68.65] | 3.85 | 18.05 | 69.10 | 171296 | 167611 | 1.02x | exato | exato | Go | **4.07x** |
| Encode PNG [screenshot.pam] | 5.23 [5.01-5.43] | 50.13 | 1.89 [1.88-1.92] | 138.53 | 7.82 | 2.63 | 7687 | 3804 | 2.02x | exato | exato | Rust | **2.76x** |
| Encode PNG [illustration.pam] | 7.36 [7.22-7.61] | 35.61 | 2.32 [2.31-2.34] | 112.86 | 8.57 | 2.99 | 8910 | 5517 | 1.62x | exato | exato | Rust | **3.17x** |
| Encode PNG [alpha.pam] | 7.25 [6.93-7.57] | 36.13 | 4.08 [4.03-4.18] | 64.24 | 8.50 | 4.95 | 14825 | 10690 | 1.39x | exato | exato | Rust | **1.78x** |
| Encode JPEG [photo.pam] | 6.23 [6.09-6.34] | 42.08 | 2.13 [1.91-2.18] | 123.25 | 6.92 | 2.93 | 18501 | 18575 | 1.00x | 38.45 dB | 38.18 dB | Rust | **2.93x** |
| Encode JPEG [screenshot.pam] | 5.19 [5.13-5.54] | 50.49 | 2.52 [2.47-2.59] | 103.91 | 5.91 | 3.41 | 55900 | 56551 | 0.99x | 30.69 dB | 29.82 dB | Rust | **2.06x** |
| Encode JPEG [illustration.pam] | 4.28 [4.21-4.82] | 61.26 | 1.83 [1.82-1.84] | 142.87 | 5.56 | 2.59 | 16992 | 17470 | 0.97x | 31.19 dB | 31.01 dB | Rust | **2.33x** |
| Encode WebP Lossy [photo.pam] | 45.92 [45.29-47.26] | 5.71 | 18.82 [18.56-19.47] | 13.93 | 47.45 | 19.94 | 11456 | 9438 | 1.21x | 37.96 dB | 38.89 dB | Rust | **2.44x** |
| Encode WebP Lossless [photo.pam] | 90.45 [89.15-96.88] | 2.90 | 2.85 [2.80-2.92] | 91.83 | 91.30 | 3.66 | 146178 | 172622 | 0.85x | exato | exato | Rust | **31.68x** |
| Encode WebP Lossy [screenshot.pam] | 50.79 [50.36-60.90] | 5.16 | 19.79 [19.63-20.34] | 13.25 | 54.05 | 20.67 | 23106 | 15082 | 1.53x | 32.17 dB | 32.45 dB | Rust | **2.57x** |
| Encode WebP Lossless [screenshot.pam] | 93.52 [83.38-96.27] | 2.80 | 1.04 [1.03-1.06] | 253.07 | 94.76 | 1.96 | 1342 | 2866 | 0.47x | exato | exato | Rust | **90.28x** |
| Encode WebP Lossy [illustration.pam] | 48.44 [46.87-50.27] | 5.41 | 16.84 [16.66-16.96] | 15.56 | 50.01 | 17.72 | 11864 | 9386 | 1.26x | 31.75 dB | 31.68 dB | Rust | **2.88x** |
| Encode WebP Lossless [illustration.pam] | 92.20 [88.19-94.78] | 2.84 | 1.09 [1.06-1.11] | 239.91 | 93.35 | 1.78 | 2602 | 12226 | 0.21x | exato | exato | Rust | **84.38x** |
| Encode WebP Lossy [alpha.pam] | 56.22 [53.81-57.30] | 4.66 | 14.24 [14.00-14.66] | 18.41 | 57.39 | 15.56 | 18670 | 9276 | 2.01x | 30.68 dB | 30.86 dB | Rust | **3.95x** |
| Encode WebP Lossless [alpha.pam] | 74.17 [71.54-75.05] | 3.53 | 0.93 [0.90-0.97] | 282.21 | 75.19 | 1.80 | 7940 | 9910 | 0.80x | exato | exato | Rust | **79.84x** |
| Encode AVIF Lossy [photo.pam] | 68.51 [66.39-72.14] | 3.83 | 245.53 [241.27-247.82] | 1.07 | 70.41 | 246.54 | 10788 | 14379 | 0.75x | 41.48 dB | 46.73 dB | Go | **3.58x** |
| Encode AVIF Lossy [screenshot.pam] | 104.95 [98.93-113.08] | 2.50 | 254.03 [252.96-261.78] | 1.03 | 108.04 | 255.01 | 38247 | 27173 | 1.41x | 33.06 dB | 45.28 dB | Go | **2.42x** |
| Encode JXL Lossy [photo.pam] | 48.61 [47.78-49.62] | 5.39 | 12.63 [12.52-13.16] | 20.75 | 49.62 | 13.35 | 11961 | 10765 | 1.11x | 38.25 dB | 39.41 dB | Rust | **3.85x** |
| Encode JXL Lossless [photo.pam] | 217.93 [213.14-220.98] | 1.20 | 28.20 [27.47-29.18] | 9.30 | 218.92 | 29.03 | 139516 | 171924 | 0.81x | exato | exato | Rust | **7.73x** |
| Encode JXL Lossy [screenshot.pam] | 76.40 [74.47-84.54] | 3.43 | 19.85 [19.72-20.13] | 13.21 | 77.82 | 20.95 | 30793 | 33987 | 0.91x | 31.83 dB | 31.85 dB | Rust | **3.85x** |
| Encode JXL Lossless [screenshot.pam] | 179.40 [172.74-186.09] | 1.46 | 18.90 [18.40-19.27] | 13.87 | 180.55 | 19.75 | 4522 | 6998 | 0.65x | exato | exato | Rust | **9.49x** |
| Decode PNG [photo.png] | 8.78 [8.09-10.53] | 29.87 | 2.30 [2.21-2.36] | 113.97 | 9.57 | 2.92 | 786495 | 786495 | 1.00x | exato | exato | Rust | **3.82x** |
| Decode JPEG [photo.jpg] | 6.13 [4.66-6.81] | 42.76 | 1.06 [0.98-1.08] | 247.51 | 7.56 | 1.59 | 786495 | 786495 | 1.00x | 46.87 dB | 55.53 dB | Rust | **5.79x** |
| Decode WEBP [photo.webp] | 18.14 [17.32-18.60] | 14.45 | 3.15 [3.05-3.46] | 83.29 | 18.77 | 3.70 | 786495 | 786495 | 1.00x | exato | exato | Rust | **5.76x** |
| Decode AVIF [photo.avif] | 5.54 [4.74-6.26] | 47.31 | 13.57 [12.24-14.54] | 19.32 | 6.23 | 14.20 | 786495 | 786495 | 1.00x | 53.91 dB | 53.91 dB | Go | **2.45x** |
| Decode JXL [photo.jxl] | 12.07 [11.24-12.75] | 21.72 | 19.85 [18.81-20.51] | 13.20 | 13.00 | 20.58 | 786495 | 786495 | 1.00x | 54.24 dB | 54.23 dB | Go | **1.65x** |
| Transcode PNG -> WebP | 49.60 [49.03-51.16] | 5.28 | 20.99 [20.85-21.17] | 12.49 | 50.49 | 21.59 | 11456 | 9438 | 1.21x | 37.96 dB | 38.89 dB | Rust | **2.36x** |
| Transcode PNG -> AVIF | 74.53 [72.72-76.19] | 3.52 | 239.42 [233.82-246.46] | 1.09 | 75.44 | 240.15 | 10788 | 14379 | 0.75x | 41.48 dB | 46.73 dB | Go | **3.21x** |
| Transcode JPEG -> WebP | 52.73 [51.42-53.18] | 4.97 | 21.71 [20.75-22.50] | 12.07 | 53.37 | 22.20 | 12624 | 9842 | 1.28x | 38.96 dB | 39.70 dB | Rust | **2.43x** |
| Transcode JXL -> PNG | 38.21 [36.65-39.38] | 6.86 | 100.02 [96.05-103.12] | 2.62 | 38.87 | 100.76 | 178784 | 175387 | 1.02x | 54.24 dB | 54.23 dB | Go | **2.62x** |

## ⚖️ Comparação a Qualidade Equivalente (AVIF e JXL lossy)

O mesmo `q` não dá a mesma qualidade nos dois engines (o gav1d grava AVIF 4:2:0 e o ravif 4:4:4; os mapeamentos de `q` são nativos de cada biblioteca). Alvo = PSNR do Go no `q` padrão; o Rust usa o menor `q` que alcança esse PSNR. Tamanho e tempo abaixo são medidos nesses `q`.

| Tarefa | Alvo (dB) | Go q | Rust q | PSNR Go | PSNR Rust | Go (bytes) | Rust (bytes) | Go/Rust | Go tempo (ms) | Rust tempo (ms) | 🥇 Vencedor | Vantagem |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Encode AVIF Lossy [photo.pam] | 41.48 | 75 | 46 | 41.482 | 41.734 | 10788 | 7371 | 1.46x | 66.79 [65.23-68.55] | 242.29 [226.96-261.94] | Go | **3.63x** |
| Encode AVIF Lossy [screenshot.pam] | 33.06 | 75 | 36 | 33.058 | 33.191 | 38247 | 12050 | 3.17x | 110.65 [106.39-115.01] | 118.81 [113.21-126.21] | Empate | **1.07x** |
| Encode JXL Lossy [photo.pam] | 38.25 | 75 | 66 | 38.254 | 38.293 | 11961 | 9328 | 1.28x | 50.64 [48.36-51.97] | 11.71 [11.65-11.91] | Rust | **4.32x** |
| Encode JXL Lossy [screenshot.pam] | 31.83 | 75 | 71 | 31.833 | 31.906 | 30793 | 32453 | 0.95x | 82.89 [81.32-87.73] | 21.11 [20.35-21.67] | Rust | **3.93x** |
