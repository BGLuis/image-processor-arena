# 🏆 Pódio da Arena: Go Puro × Rust Puro

**Modo de Execução**: `BATCH`  
**Iterações por teste**: 3 (+ 1 warmup)  
**Data da Coleta**: 2026-09-29 00:10:01

## 🥇 Classificação Geral

- 🥇 **1º Lugar: Rust Puro** (25/36 vitórias - 69.4%)
- 🥈 **2º Lugar: Go Puro** (11/36 vitórias - 30.6%)

## 📊 Tabela Completa de Resultados

| Tarefa / Operação | Go (tempo) | Go Throughput | Rust (tempo) | Rust Throughput | 🥇 Vencedor | Vantagem |
|---|---|---|---|---|---|---|
| Analyze [photo.pam] | 104.68 ms | 2.50 MP/s | 154.32 ms | 1.70 MP/s | 🐹 Go | **1.47x** |
| Analyze [screenshot.pam] | 103.97 ms | 2.52 MP/s | 152.55 ms | 1.72 MP/s | 🐹 Go | **1.47x** |
| Analyze [illustration.pam] | 105.37 ms | 2.49 MP/s | 144.99 ms | 1.81 MP/s | 🐹 Go | **1.38x** |
| Analyze [alpha.pam] | 90.04 ms | 2.91 MP/s | 101.94 ms | 2.57 MP/s | 🐹 Go | **1.13x** |
| Encode PNG [photo.pam] | 48.03 ms | 5.46 MP/s | 51.81 ms | 5.06 MP/s | 🐹 Go | **1.08x** |
| Encode PNG [screenshot.pam] | 37.97 ms | 6.90 MP/s | 3.18 ms | 82.55 MP/s | 🦀 Rust | **11.96x** |
| Encode PNG [illustration.pam] | 44.27 ms | 5.92 MP/s | 8.28 ms | 31.66 MP/s | 🦀 Rust | **5.35x** |
| Encode PNG [alpha.pam] | 42.99 ms | 6.10 MP/s | 5.63 ms | 46.55 MP/s | 🦀 Rust | **7.63x** |
| Encode JPEG [photo.pam] | 44.83 ms | 5.85 MP/s | 4.85 ms | 54.01 MP/s | 🦀 Rust | **9.24x** |
| Encode JPEG [screenshot.pam] | 42.63 ms | 6.15 MP/s | 4.94 ms | 53.11 MP/s | 🦀 Rust | **8.64x** |
| Encode JPEG [illustration.pam] | 41.70 ms | 6.29 MP/s | 4.83 ms | 54.26 MP/s | 🦀 Rust | **8.63x** |
| Encode WebP Lossy [photo.pam] | 61.78 ms | 4.24 MP/s | 19.66 ms | 13.33 MP/s | 🦀 Rust | **3.14x** |
| Encode WebP Lossless [photo.pam] | 106.15 ms | 2.47 MP/s | 4.35 ms | 60.20 MP/s | 🦀 Rust | **24.38x** |
| Encode WebP Lossy [screenshot.pam] | 60.56 ms | 4.33 MP/s | 22.06 ms | 11.89 MP/s | 🦀 Rust | **2.75x** |
| Encode WebP Lossless [screenshot.pam] | 90.79 ms | 2.89 MP/s | 6.58 ms | 39.83 MP/s | 🦀 Rust | **13.80x** |
| Encode WebP Lossy [illustration.pam] | 55.35 ms | 4.74 MP/s | 20.35 ms | 12.88 MP/s | 🦀 Rust | **2.72x** |
| Encode WebP Lossless [illustration.pam] | 96.64 ms | 2.71 MP/s | 3.84 ms | 68.19 MP/s | 🦀 Rust | **25.14x** |
| Encode WebP Lossy [alpha.pam] | 166.46 ms | 1.57 MP/s | 18.65 ms | 14.05 MP/s | 🦀 Rust | **8.92x** |
| Encode WebP Lossless [alpha.pam] | 87.78 ms | 2.99 MP/s | 2.99 ms | 87.69 MP/s | 🦀 Rust | **29.36x** |
| Encode AVIF Lossy [photo.pam] | 212.69 ms | 1.23 MP/s | 496.39 ms | 0.53 MP/s | 🐹 Go | **2.33x** |
| Encode AVIF Lossless [photo.pam] | 71.14 ms | 3.68 MP/s | 1573.53 ms | 0.17 MP/s | 🐹 Go | **22.12x** |
| Encode AVIF Lossy [screenshot.pam] | 256.59 ms | 1.02 MP/s | 520.49 ms | 0.50 MP/s | 🐹 Go | **2.03x** |
| Encode AVIF Lossless [screenshot.pam] | 106.85 ms | 2.45 MP/s | 993.75 ms | 0.26 MP/s | 🐹 Go | **9.30x** |
| Encode JXL Lossy [photo.pam] | 77.78 ms | 3.37 MP/s | 17.10 ms | 15.33 MP/s | 🦀 Rust | **4.55x** |
| Encode JXL Lossless [photo.pam] | 189.47 ms | 1.38 MP/s | 30.00 ms | 8.74 MP/s | 🦀 Rust | **6.32x** |
| Encode JXL Lossy [screenshot.pam] | 107.43 ms | 2.44 MP/s | 24.51 ms | 10.69 MP/s | 🦀 Rust | **4.38x** |
| Encode JXL Lossless [screenshot.pam] | 153.30 ms | 1.71 MP/s | 21.59 ms | 12.14 MP/s | 🦀 Rust | **7.10x** |
| Decode PNG [photo.png] | 47.82 ms | 5.48 MP/s | 4.59 ms | 57.05 MP/s | 🦀 Rust | **10.41x** |
| Decode JPEG [photo.jpg] | 47.77 ms | 5.49 MP/s | 3.05 ms | 86.01 MP/s | 🦀 Rust | **15.67x** |
| Decode WebP [photo.webp] | 46.60 ms | 5.63 MP/s | 6.16 ms | 42.58 MP/s | 🦀 Rust | **7.57x** |
| Decode AVIF [photo.avif] | 40.34 ms | 6.50 MP/s | 18.32 ms | 14.31 MP/s | 🦀 Rust | **2.20x** |
| Decode JXL [photo.jxl] | 42.38 ms | 6.19 MP/s | 18.53 ms | 14.15 MP/s | 🦀 Rust | **2.29x** |
| Transcode PNG -> WebP | 63.52 ms | 4.13 MP/s | 19.51 ms | 13.43 MP/s | 🦀 Rust | **3.26x** |
| Transcode PNG -> AVIF | 221.88 ms | 1.18 MP/s | 504.28 ms | 0.52 MP/s | 🐹 Go | **2.27x** |
| Transcode JPEG -> WebP | 72.57 ms | 3.61 MP/s | 21.11 ms | 12.42 MP/s | 🦀 Rust | **3.44x** |
| Transcode JXL -> PNG | 56.29 ms | 4.66 MP/s | 75.53 ms | 3.47 MP/s | 🐹 Go | **1.34x** |
