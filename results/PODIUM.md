# 🏆 Pódio da Arena: Go Puro × Rust Puro

**Modo de Execução**: `HTTP`  
**Métrica primária**: codec (servidor, X-Arena-*-Ns)  
**Iterações por teste**: 7 medidas (+ 3 warmup); tempos como mediana [p25-p75]  
**Data da Coleta**: 2026-09-29 01:35:46

## Notas de Medição

- Métrica primária: tempo de codec reportado pelo servidor nos headers X-Arena-*-Ns (transcode = decode + encode). A coluna de parede do cliente inclui rede, PAM e serialização.
- op=analyze: os servidores cronometram trechos diferentes (Rust inclui parse do PAM e serialização JSON; Go mede só a análise), então o tempo de analyze não é comparável entre Go e Rust (issue #7).

## 🥇 Classificação Geral

Vitórias em tempo de codec (empate estatístico quando os intervalos p25-p75 se sobrepõem):

- Go Puro: 11/34 (32.4%)
- Rust Puro: 23/34 (67.6%)
- Empates estatísticos: 0/34 (0.0%)

## 📊 Tabela Completa de Resultados

Parâmetros (arena.toml `[params]`): q=75, effort=4, mode padrão `lossy`. Go/Rust acima de 1 significa saída maior no Go; o tempo só é comparável junto do tamanho.

| Tarefa / Operação | Go codec (ms) | Go MP/s | Rust codec (ms) | Rust MP/s | Go parede cliente (ms) | Rust parede cliente (ms) | Go (bytes) | Rust (bytes) | Go/Rust | 🥇 Vencedor (codec) | Vantagem |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Analyze [photo.pam] † | 73.64 [73.37-79.49] | 3.56 | 159.08 [158.09-160.85] | 1.65 | 75.93 | 160.84 | 0 | 0 | - | Go | **2.16x** |
| Analyze [screenshot.pam] † | 67.37 [65.64-69.64] | 3.89 | 151.16 [148.11-154.31] | 1.73 | 68.80 | 153.30 | 0 | 0 | - | Go | **2.24x** |
| Analyze [illustration.pam] † | 62.16 [61.83-63.76] | 4.22 | 145.54 [144.95-145.80] | 1.80 | 64.90 | 146.89 | 0 | 0 | - | Go | **2.34x** |
| Analyze [alpha.pam] † | 52.84 [52.57-54.79] | 4.96 | 96.10 [95.66-96.26] | 2.73 | 55.04 | 97.96 | 0 | 0 | - | Go | **1.82x** |
| Encode PNG [photo.pam] | 12.83 [12.46-13.32] | 20.44 | 49.17 [49.04-49.65] | 5.33 | 14.34 | 50.97 | 171296 | 167611 | 1.02x | Go | **3.83x** |
| Encode PNG [screenshot.pam] | 4.07 [3.97-4.88] | 64.36 | 1.50 [1.47-2.25] | 175.11 | 5.62 | 2.92 | 7687 | 3804 | 2.02x | Rust | **2.72x** |
| Encode PNG [illustration.pam] | 5.68 [5.52-5.89] | 46.12 | 1.89 [1.87-2.01] | 138.90 | 7.30 | 3.43 | 8910 | 5517 | 1.62x | Rust | **3.01x** |
| Encode PNG [alpha.pam] | 5.58 [5.28-6.54] | 47.01 | 3.20 [3.12-3.47] | 81.94 | 7.45 | 4.92 | 14825 | 10690 | 1.39x | Rust | **1.74x** |
| Encode JPEG [photo.pam] | 4.25 [4.23-4.49] | 61.75 | 1.49 [1.48-1.51] | 176.09 | 5.61 | 3.08 | 18501 | 18575 | 1.00x | Rust | **2.85x** |
| Encode JPEG [screenshot.pam] | 3.87 [3.74-4.19] | 67.82 | 1.62 [1.61-1.66] | 161.78 | 5.53 | 3.10 | 55900 | 56551 | 0.99x | Rust | **2.39x** |
| Encode JPEG [illustration.pam] | 3.08 [2.97-3.99] | 85.08 | 1.46 [1.42-1.58] | 179.19 | 4.86 | 3.01 | 16992 | 17470 | 0.97x | Rust | **2.11x** |
| Encode WebP Lossy [photo.pam] | 30.86 [30.83-31.59] | 8.49 | 14.10 [14.01-14.35] | 18.60 | 32.83 | 15.66 | 11456 | 9438 | 1.21x | Rust | **2.19x** |
| Encode WebP Lossless [photo.pam] | 66.68 [65.96-66.94] | 3.93 | 2.06 [2.02-2.12] | 127.15 | 68.14 | 3.55 | 146178 | 172622 | 0.85x | Rust | **32.34x** |
| Encode WebP Lossy [screenshot.pam] | 34.67 [34.55-34.87] | 7.56 | 14.44 [14.33-14.62] | 18.16 | 36.24 | 15.96 | 23106 | 15082 | 1.53x | Rust | **2.40x** |
| Encode WebP Lossless [screenshot.pam] | 55.11 [54.88-55.54] | 4.76 | 0.62 [0.61-0.63] | 421.66 | 56.71 | 1.93 | 1342 | 2866 | 0.47x | Rust | **88.65x** |
| Encode WebP Lossy [illustration.pam] | 29.84 [29.19-30.76] | 8.78 | 10.99 [10.88-11.08] | 23.86 | 31.40 | 12.94 | 11864 | 9386 | 1.26x | Rust | **2.72x** |
| Encode WebP Lossless [illustration.pam] | 58.26 [56.93-58.45] | 4.50 | 0.72 [0.71-0.75] | 363.81 | 59.79 | 2.32 | 2602 | 12226 | 0.21x | Rust | **80.86x** |
| Encode WebP Lossy [alpha.pam] | 40.19 [39.68-40.55] | 6.52 | 10.75 [10.67-10.87] | 24.39 | 42.08 | 12.60 | 18670 | 9276 | 2.01x | Rust | **3.74x** |
| Encode WebP Lossless [alpha.pam] | 53.84 [53.68-54.43] | 4.87 | 0.72 [0.69-0.73] | 366.27 | 55.29 | 2.23 | 7940 | 9910 | 0.80x | Rust | **75.22x** |
| Encode AVIF Lossy [photo.pam] | 80.33 [79.09-80.75] | 3.26 | 136.41 [130.35-137.89] | 1.92 | 81.79 | 137.86 | 10788 | 15174 | 0.71x | Go | **1.70x** |
| Encode AVIF Lossy [screenshot.pam] | 106.20 [105.70-107.20] | 2.47 | 142.20 [135.31-143.64] | 1.84 | 108.31 | 143.60 | 38247 | 29138 | 1.31x | Go | **1.34x** |
| Encode JXL Lossy [photo.pam] | 39.90 [39.37-40.22] | 6.57 | 10.03 [9.84-10.55] | 26.14 | 41.46 | 11.66 | 11961 | 10765 | 1.11x | Rust | **3.98x** |
| Encode JXL Lossless [photo.pam] | 155.27 [151.64-156.35] | 1.69 | 20.63 [20.51-21.85] | 12.71 | 156.86 | 22.23 | 139516 | 171924 | 0.81x | Rust | **7.53x** |
| Encode JXL Lossy [screenshot.pam] | 59.65 [57.38-61.44] | 4.39 | 15.97 [15.65-16.97] | 16.42 | 61.16 | 17.43 | 30793 | 33987 | 0.91x | Rust | **3.74x** |
| Encode JXL Lossless [screenshot.pam] | 118.03 [117.34-119.88] | 2.22 | 14.16 [14.00-14.38] | 18.51 | 119.66 | 15.55 | 4522 | 6998 | 0.65x | Rust | **8.34x** |
| Decode PNG [photo.png] | 12.03 [11.99-12.20] | 21.79 | 1.52 [1.48-1.59] | 172.78 | 13.70 | 2.87 | 786495 | 786495 | 1.00x | Rust | **7.93x** |
| Decode JPEG [photo.jpg] | 11.16 [10.72-12.69] | 23.48 | 0.64 [0.61-0.66] | 411.87 | 12.65 | 1.64 | 786495 | 786495 | 1.00x | Rust | **17.54x** |
| Decode WebP [photo.webp] | 11.95 [11.87-12.23] | 21.94 | 2.15 [2.13-2.48] | 121.70 | 13.23 | 3.77 | 786495 | 786495 | 1.00x | Rust | **5.55x** |
| Decode AVIF [photo.avif] | 3.37 [3.23-3.75] | 77.81 | 9.32 [8.91-10.48] | 28.12 | 4.70 | 10.77 | 786495 | 786495 | 1.00x | Go | **2.77x** |
| Decode JXL [photo.jxl] | 10.18 [10.08-11.29] | 25.75 | 13.07 [12.84-13.57] | 20.06 | 12.05 | 14.78 | 786495 | 786495 | 1.00x | Go | **1.28x** |
| Transcode PNG -> WebP | 45.20 [43.35-46.93] | 5.80 | 15.71 [15.55-15.97] | 16.68 | 46.85 | 16.99 | 11456 | 9438 | 1.21x | Rust | **2.88x** |
| Transcode PNG -> AVIF | 92.08 [91.80-93.33] | 2.85 | 134.97 [134.32-139.35] | 1.94 | 93.32 | 136.19 | 10788 | 15174 | 0.71x | Go | **1.47x** |
| Transcode JPEG -> WebP | 42.73 [42.16-42.85] | 6.14 | 15.67 [15.17-15.74] | 16.72 | 43.71 | 16.68 | 12624 | 9842 | 1.28x | Rust | **2.73x** |
| Transcode JXL -> PNG | 22.93 [21.82-23.67] | 11.43 | 62.70 [62.21-64.31] | 4.18 | 23.88 | 63.93 | 178784 | 175387 | 1.02x | Go | **2.73x** |

† op=analyze: os servidores cronometram trechos diferentes (Rust inclui parse do PAM e serialização JSON; Go mede só a análise), então o tempo de analyze não é comparável entre Go e Rust (issue #7).
