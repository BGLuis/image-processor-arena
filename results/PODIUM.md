# 🏆 Pódio da Arena: Go Puro × Rust Puro

**Modo de Execução**: `HTTP`  
**Tier de Execução**: `ACCELERATED`  
**Métrica primária**: codec (servidor, X-Arena-*-Ns)  
**Iterações por teste**: 5 medidas (+ 2 warmup); tempos como mediana [p25-p75]  
**Máquina**: 12th Gen Intel(R) Core(TM) i5-12600K (16 CPUs lógicas), Linux-7.2.11-arch1-1-x86_64-with-glibc2.44  
**Data da Coleta**: 2026-11-01 01:31:32

## Notas de Medição

- Métrica primária: tempo de codec reportado pelo servidor nos headers X-Arena-*-Ns (transcode = decode + encode; analyze = só a análise nos dois servidores). A coluna de parede do cliente inclui rede, PAM e serialização. Requisições sequenciais em conexão persistente.
- Regra de empate (a mesma no console, no Markdown e no JSON): há empate estatístico quando os intervalos p25-p75 das duas medianas se sobrepõem; só vale como vitória uma diferença fora deles.
- Razão geométrica = média geométrica de (tempo do Go ÷ tempo do Rust) sobre as tarefas; acima de 1 o Rust é mais rápido, abaixo de 1 o Go. Ela pondera a magnitude, que a contagem de vitórias ignora.
- Cada saída é decodificada por um decoder de referência (Pillow/libjxl/libavif) antes de o tempo ser aceito; lossless exige igualdade exata e lossy um PSNR mínimo por classe de imagem. PSNR RGB sobre os pixels opacos do original. O tempo só é comparável junto do tamanho e da qualidade.

## 📋 Matriz de Suporte por Operação

| Operação | Suporte em Go | Suporte em Rust |
|---|---|---|
| analyze | ✅ Suportado | ✅ Suportado |
| encode | ✅ Suportado | ✅ Suportado |
| decode | ✅ Suportado | ✅ Suportado |
| transcode | ✅ Suportado | ✅ Suportado |
| resize | ✅ Suportado | ✅ Suportado |
| filter | ✅ Suportado | ✅ Suportado |
| seam_carving | ✅ Suportado | ❌ Não suportado |

## 🥇 Classificação Geral

**Razão geométrica Go/Rust (tempo): 2.90x** (Rust 2.90x mais rápido).

Vitórias em tempo de codec (empate estatístico quando os intervalos p25-p75 se sobrepõem):

- Go Puro: 5/34 (14.7%)
- Rust Puro: 26/34 (76.5%)
- Empates estatísticos: 3/34 (8.8%)

## 🧮 Por Operação

| Operação | Tarefas | Go | Rust | Empates | Razão geométrica Go/Rust | Leitura |
|---|---|---|---|---|---|---|
| analyze | 4 | 0 | 4 | 0 | 1.53x | Rust 1.53x mais rápido |
| encode | 21 | 2 | 17 | 2 | 4.45x | Rust 4.45x mais rápido |
| decode | 5 | 1 | 3 | 1 | 1.75x | Rust 1.75x mais rápido |
| transcode | 4 | 2 | 2 | 0 | 1.11x | Rust 1.11x mais rápido |
| total | 34 | 5 | 26 | 3 | 2.90x | Rust 2.90x mais rápido |

## 📊 Tabela Completa de Resultados

Parâmetros (arena.toml `[params]`): q=75, effort=4, mode padrão `lossy`. Go/Rust acima de 1 significa saída maior no Go; o tempo só é comparável junto do tamanho e da qualidade (PSNR RGB contra o original, decodificado pela referência; `exato` = idêntico bit a bit).

| Tarefa / Operação | Go codec (ms) | Go MP/s | Rust codec (ms) | Rust MP/s | Go parede cliente (ms) | Rust parede cliente (ms) | Go (bytes) | Rust (bytes) | Go/Rust | PSNR Go | PSNR Rust | 🥇 Vencedor (codec) | Vantagem |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Analyze [photo.pam] | 15.41 [14.61-17.20] | 17.01 | 11.12 [10.92-11.46] | 23.58 | 16.26 | 11.71 | 0 | 0 | - | - | - | Rust | **1.39x** |
| Analyze [screenshot.pam] | 15.28 [14.78-18.63] | 17.16 | 10.85 [10.75-11.02] | 24.15 | 15.87 | 11.65 | 0 | 0 | - | - | - | Rust | **1.41x** |
| Analyze [illustration.pam] | 21.59 [15.50-28.97] | 12.14 | 10.89 [10.77-11.11] | 24.06 | 22.66 | 11.63 | 0 | 0 | - | - | - | Rust | **1.98x** |
| Analyze [alpha.pam] | 15.80 [14.04-23.30] | 16.59 | 11.04 [11.00-11.11] | 23.74 | 16.64 | 12.04 | 0 | 0 | - | - | - | Rust | **1.43x** |
| Encode PNG [photo.pam] | 12.80 [12.71-13.52] | 20.48 | 48.03 [47.92-48.18] | 5.46 | 13.73 | 48.60 | 171296 | 167611 | 1.02x | exato | exato | Go | **3.75x** |
| Encode PNG [screenshot.pam] | 4.48 [3.90-5.15] | 58.56 | 1.96 [1.56-2.52] | 133.52 | 5.00 | 2.38 | 7687 | 3804 | 2.02x | exato | exato | Rust | **2.28x** |
| Encode PNG [illustration.pam] | 6.65 [6.26-6.68] | 39.45 | 2.24 [1.74-3.04] | 116.86 | 7.20 | 2.61 | 8910 | 5517 | 1.62x | exato | exato | Rust | **2.96x** |
| Encode PNG [alpha.pam] | 9.06 [7.00-9.40] | 28.94 | 3.39 [3.02-3.41] | 77.26 | 10.24 | 3.79 | 14825 | 10690 | 1.39x | exato | exato | Rust | **2.67x** |
| Encode JPEG [photo.pam] | 7.28 [5.92-8.59] | 36.03 | 1.90 [1.55-2.49] | 137.76 | 8.26 | 2.27 | 18501 | 18575 | 1.00x | 38.45 dB | 38.18 dB | Rust | **3.82x** |
| Encode JPEG [screenshot.pam] | 4.35 [4.24-4.39] | 60.21 | 1.99 [1.68-2.14] | 131.55 | 5.20 | 2.35 | 55900 | 56551 | 0.99x | 30.69 dB | 29.82 dB | Rust | **2.18x** |
| Encode JPEG [illustration.pam] | 3.53 [2.76-3.99] | 74.34 | 2.44 [2.35-2.79] | 107.45 | 4.49 | 3.05 | 16992 | 17470 | 0.97x | 31.19 dB | 31.01 dB | Empate | **1.45x** |
| Encode WebP Lossy [photo.pam] | 41.82 [32.85-57.33] | 6.27 | 13.84 [13.82-13.87] | 18.94 | 42.58 | 14.37 | 11456 | 9438 | 1.21x | 37.96 dB | 38.89 dB | Rust | **3.02x** |
| Encode WebP Lossless [photo.pam] | 71.98 [67.72-73.45] | 3.64 | 2.32 [2.28-2.73] | 112.94 | 72.60 | 2.92 | 146160 | 172622 | 0.85x | exato | exato | Rust | **31.01x** |
| Encode WebP Lossy [screenshot.pam] | 34.15 [33.86-34.28] | 7.68 | 14.11 [13.85-14.13] | 18.58 | 34.82 | 14.67 | 23106 | 15082 | 1.53x | 32.17 dB | 32.45 dB | Rust | **2.42x** |
| Encode WebP Lossless [screenshot.pam] | 55.18 [54.65-59.07] | 4.75 | 0.64 [0.64-0.66] | 409.03 | 56.02 | 0.95 | 1324 | 2866 | 0.46x | exato | exato | Rust | **86.10x** |
| Encode WebP Lossy [illustration.pam] | 28.44 [28.42-30.28] | 9.22 | 11.07 [11.03-11.54] | 23.67 | 29.29 | 11.68 | 11864 | 9386 | 1.26x | 31.75 dB | 31.68 dB | Rust | **2.57x** |
| Encode WebP Lossless [illustration.pam] | 55.12 [54.67-56.51] | 4.76 | 0.86 [0.70-0.90] | 304.93 | 55.70 | 1.09 | 2584 | 12226 | 0.21x | exato | exato | Rust | **64.11x** |
| Encode WebP Lossy [alpha.pam] | 42.75 [39.58-42.93] | 6.13 | 12.02 [10.23-13.06] | 21.82 | 43.46 | 12.61 | 18670 | 9276 | 2.01x | 30.68 dB | 30.86 dB | Rust | **3.56x** |
| Encode WebP Lossless [alpha.pam] | 54.25 [53.43-54.32] | 4.83 | 0.73 [0.68-0.75] | 361.30 | 54.95 | 1.01 | 7922 | 9910 | 0.80x | exato | exato | Rust | **74.77x** |
| Encode AVIF Lossy [photo.pam] | 79.76 [78.54-79.81] | 3.29 | 101.30 [101.01-108.48] | 2.59 | 80.52 | 101.82 | 10788 | 15174 | 0.71x | 41.48 dB | 46.77 dB | Go | **1.27x** |
| Encode AVIF Lossy [screenshot.pam] | 102.59 [102.18-105.23] | 2.56 | 109.40 [103.08-117.76] | 2.40 | 103.27 | 109.96 | 38247 | 29138 | 1.31x | 33.06 dB | 45.25 dB | Empate | **1.07x** |
| Encode JXL Lossy [photo.pam] | 40.95 [40.42-47.92] | 6.40 | 9.41 [9.40-9.43] | 27.85 | 42.04 | 9.91 | 11961 | 10765 | 1.11x | 38.25 dB | 39.41 dB | Rust | **4.35x** |
| Encode JXL Lossless [photo.pam] | 155.05 [154.41-155.80] | 1.69 | 20.76 [20.76-21.08] | 12.63 | 155.80 | 21.53 | 139516 | 171924 | 0.81x | exato | exato | Rust | **7.47x** |
| Encode JXL Lossy [screenshot.pam] | 60.96 [59.73-64.87] | 4.30 | 14.81 [14.48-14.87] | 17.70 | 61.88 | 15.41 | 30793 | 33987 | 0.91x | 31.83 dB | 31.85 dB | Rust | **4.12x** |
| Encode JXL Lossless [screenshot.pam] | 117.95 [117.90-125.69] | 2.22 | 14.21 [13.83-14.28] | 18.44 | 118.79 | 14.72 | 4522 | 6998 | 0.65x | exato | exato | Rust | **8.30x** |
| Decode PNG [photo.png] | 7.08 [6.68-7.46] | 37.05 | 1.45 [1.43-1.77] | 180.62 | 7.69 | 1.74 | 786495 | 786495 | 1.00x | exato | exato | Rust | **4.88x** |
| Decode JPEG [photo.jpg] | 2.81 [2.80-2.82] | 93.14 | 0.86 [0.81-1.33] | 304.49 | 3.27 | 1.10 | 786495 | 786495 | 1.00x | 46.87 dB | 55.53 dB | Rust | **3.27x** |
| Decode WEBP [photo.webp] | 17.51 [15.20-18.06] | 14.97 | 2.05 [2.04-2.10] | 127.84 | 18.17 | 2.39 | 786495 | 786495 | 1.00x | exato | exato | Rust | **8.54x** |
| Decode AVIF [photo.avif] | 4.21 [4.12-4.62] | 62.25 | 31.66 [26.29-36.51] | 8.28 | 4.65 | 32.87 | 786495 | 786495 | 1.00x | 53.91 dB | 53.91 dB | Go | **7.52x** |
| Decode JXL [photo.jxl] | 11.39 [10.03-16.22] | 23.02 | 12.51 [12.49-12.55] | 20.95 | 11.98 | 13.01 | 786495 | 786495 | 1.00x | 54.24 dB | 54.23 dB | Empate | **1.10x** |
| Transcode PNG -> WebP | 35.35 [35.28-35.56] | 7.42 | 15.66 [15.43-18.14] | 16.74 | 35.90 | 16.01 | 11456 | 9438 | 1.21x | 37.96 dB | 38.89 dB | Rust | **2.26x** |
| Transcode PNG -> AVIF | 82.27 [81.95-86.73] | 3.19 | 108.13 [99.58-111.66] | 2.42 | 82.96 | 108.51 | 10788 | 15174 | 0.71x | 41.48 dB | 46.77 dB | Go | **1.31x** |
| Transcode JPEG -> WebP | 33.57 [32.89-34.17] | 7.81 | 14.64 [14.60-14.66] | 17.91 | 33.91 | 14.92 | 12624 | 9842 | 1.28x | 38.96 dB | 39.70 dB | Rust | **2.29x** |
| Transcode JXL -> PNG | 23.82 [23.66-23.84] | 11.01 | 62.34 [62.17-62.89] | 4.20 | 24.22 | 62.77 | 178784 | 175387 | 1.02x | 54.24 dB | 54.23 dB | Go | **2.62x** |

## ⚖️ Comparação a Qualidade Equivalente (AVIF e JXL lossy)

O mesmo `q` não dá a mesma qualidade nos dois engines (o gav1d grava AVIF 4:2:0 e o ravif 4:4:4; os mapeamentos de `q` são nativos de cada biblioteca). Alvo = PSNR do Go no `q` padrão; o Rust usa o menor `q` que alcança esse PSNR. Tamanho e tempo abaixo são medidos nesses `q`.

| Tarefa | Alvo (dB) | Go q | Rust q | PSNR Go | PSNR Rust | Go (bytes) | Rust (bytes) | Go/Rust | Go tempo (ms) | Rust tempo (ms) | 🥇 Vencedor | Vantagem |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Encode AVIF Lossy [photo.pam] | 41.48 | 75 | 46 | 41.482 | 41.734 | 10788 | 7371 | 1.46x | 79.44 [77.27-81.67] | 165.08 [162.49-165.85] | Go | **2.08x** |
| Encode AVIF Lossy [screenshot.pam] | 33.06 | 75 | 36 | 33.058 | 33.191 | 38247 | 12050 | 3.17x | 101.69 [100.71-101.72] | 79.83 [79.81-80.90] | Rust | **1.27x** |
| Encode JXL Lossy [photo.pam] | 38.25 | 75 | 66 | 38.254 | 38.293 | 11961 | 9328 | 1.28x | 41.95 [41.60-44.07] | 9.12 [8.86-12.23] | Rust | **4.60x** |
| Encode JXL Lossy [screenshot.pam] | 31.83 | 75 | 71 | 31.833 | 31.906 | 30793 | 32453 | 0.95x | 58.99 [58.87-63.28] | 14.61 [14.52-14.93] | Rust | **4.04x** |
