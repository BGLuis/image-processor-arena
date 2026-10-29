# 📊 Scorecard de Maturidade: Ecossistemas Go Puro × Rust Puro

**Data da Geração**: 2026-10-29 02:38:56  
**Tier Ativo**: `ACCELERATED`  
**Metodologia**: Auditoria de contratos, inspeção de pureza e execução comparativa multi-biblioteca.

## 1. 📋 Matriz de Capacidades por Formato e Operação

| Formato / Operação | Suporte Go | Implementação Go | Suporte Rust | Implementação Rust | Maturidade Geral |
|---|---|---|---|---|---|
| **PNG Encode** | ✅ Sim | `image/png` (stdlib) | ✅ Sim | `png 0.18.1` | Produção |
| **PNG Decode** | ✅ Sim | `image/png` (stdlib) | ✅ Sim | `png 0.18.1` | Produção |
| **JPEG Encode** | ✅ Sim | `image/jpeg` (stdlib) | ✅ Sim | `jpeg-encoder 0.7.1` | Produção |
| **JPEG Decode** | ✅ Sim | `image/jpeg` (stdlib) | ✅ Sim | `zune-jpeg 0.5.16-rc2` | Produção |
| **WebP Lossy Encode** | ✅ Sim | `deepteams/webp` / `gowebp` | ✅ Sim | `zenwebp 0.4.4` | Produção |
| **WebP Lossless Encode**| ✅ Sim | `gowebp` | ✅ Sim | `image-webp 0.2.4` | Produção |
| **WebP Decode** | ✅ Sim | `x/image/webp` / `gowebp` | ✅ Sim | `image-webp 0.2.4` | Produção |
| **AVIF Lossy Encode** | ✅ Sim | `gen2brain/gav1d/avif` | ✅ Sim | `ravif 0.13.0` | Estável |
| **AVIF Lossless Encode**| ❌ Não | Não suportado puro | ❌ Não | Não suportado puro | Ausente em ambos |
| **AVIF Decode** | ✅ Sim | `gen2brain/gav1d/avif` | ✅ Sim | `zenavif 0.1.6` / `rav1d` | Estável |
| **JXL Lossy Encode** | ✅ Sim | `gen2brain/jxl` | ✅ Sim | `jxl-encoder 0.3.1` | Estável |
| **JXL Lossless Encode**| ✅ Sim | `gen2brain/jxl` | ✅ Sim | `jxl-encoder 0.3.1` | Estável |
| **JXL Decode** | ✅ Sim | `gen2brain/jxl` | ✅ Sim | `jxl-oxide 0.12.6` | Estável |
| **Analyze** (16 métricas)| ✅ Sim | `internal/analyze` (puro) | ✅ Sim | `arena-rust::analyze` (puro) | Produção |
| **Resize (Lanczos3)** | ✅ Sim | `x/image/draw`, `imaging` | ✅ Sim | `fast_image_resize`, `image` | Produção |
| **Filtros de Convolução**| ✅ Sim | `disintegration/imaging` | ✅ Sim | `imageproc` | Produção |
| **Content-Aware Seam Carving** | ✅ Sim | `esimov/caire` | ⚠️ Não | Ausência de equivalente puro | Parcial (Go exclusivo) |

## 2. ⚖️ Análise de Risco de Licenciamento (MIT vs AGPL)

A arena avalia formalmente a conformidade jurídica das dependências dos dois ecossistemas:

### 2.1 Ecossistema Go

| Componente / Dependência | Licença | Tipo | Impacto / Risco |
|---|---|---|---|
| `image/*` (stdlib) | BSD-3-Clause | Permissiva | Uso livre irrestrito |
| `golang.org/x/image` | BSD-3-Clause | Permissiva | Uso livre irrestrito |
| `github.com/deepteams/webp` | MIT | Permissiva | Uso livre comercial |
| `github.com/KarpelesLab/gowebp` | BSD-2-Clause | Permissiva | Uso livre comercial |
| `github.com/gen2brain/gav1d` | BSD-3-Clause | Permissiva | Uso livre comercial |
| `github.com/gen2brain/jxl` | BSD-3-Clause | Permissiva | Uso livre comercial |
| `github.com/disintegration/imaging` | MIT | Permissiva | Uso livre comercial |
| `github.com/esimov/caire` | MIT | Permissiva | Uso livre comercial |

**Diagnóstico Go**: 100% permissivo (MIT e BSD). Risco nulo de contaminação copyleft para código proprietário, distribuição binária ou software como serviço (SaaS).

### 2.2 Ecossistema Rust

| Componente / Crate | Licença | Tipo | Impacto / Risco |
|---|---|---|---|
| `png` | MIT / Apache-2.0 | Permissiva | Uso livre comercial |
| `jpeg-encoder` | MIT / Apache-2.0 | Permissiva | Uso livre comercial |
| `zune-jpeg` | Apache-2.0 / MIT / Zlib | Permissiva | Uso livre comercial |
| `image-webp` | MIT / Apache-2.0 | Permissiva | Uso livre comercial |
| `ravif` | BSD-3-Clause | Permissiva | Uso livre comercial |
| `rav1d` | BSD-3-Clause | Permissiva | Uso livre comercial |
| `jxl-encoder` | MIT / Apache-2.0 | Permissiva | Uso livre comercial |
| `jxl-oxide` | MIT / Apache-2.0 | Permissiva | Uso livre comercial |
| `fast_image_resize` | MIT / Apache-2.0 | Permissiva | Uso livre comercial |
| `imageproc` | MIT | Permissiva | Uso livre comercial |
| `zenwebp 0.4.4` | **AGPL-3.0-only** | **Copyleft Forte** | Obrigatoriedade de abertura de código para serviços em rede |
| `zenavif 0.1.6` | **AGPL-3.0-only** | **Copyleft Forte** | Obrigatoriedade de abertura de código para serviços em rede |

**Diagnóstico Rust**: As crates `zenwebp` e `zenavif` exigem licenciamento derivado **AGPL-3.0** nos binários distribuídos. Conforme a **Seção 13 da AGPL-3.0**, operadores que hospedam a API em rede comercial ou SaaS são obrigados a disponibilizar o código fonte integral do serviço a todos os usuários da rede. Para ambientes que proíbem AGPL, deve-se utilizar o codec `image-webp` e substituir `zenavif` por pipelines estritamente permissivos.

## 3. 🛡️ Resiliência contra Arquivos Corrompidos e Fuzzing

| Cenário de Falha / Teste | Comportamento Go | Comportamento Rust | Veredito de Segurança |
|---|---|---|---|
| **Header PAM truncado / inválido** | Rejeição HTTP 400 antes de alocar pixels | Rejeição HTTP 400 antes de alocar pixels | ✅ Ambos seguros contra OOM |
| **Dimensões Monstruosas (> 40 MP)** | Rejeição HTTP 400 sem alocação | Rejeição HTTP 400 sem alocação | ✅ Proteção contra pixel bomb |
| **Payload binário corrompido (Decode)**| Retorno HTTP 400 (Client Error) | Retorno HTTP 400 (Client Error) | ✅ Sem panics ou crashes |
| **Payload com canal inválido em Transcode**| Retorno HTTP 400 tratado | Retorno HTTP 400 tratado | ✅ Tratamento estrito |
| **Memory Safety / Buffer Overflow** | Bounds-checked em runtime + GC | Memory-safe em compilação (sem UB) | ✅ Livre de vulnerabilidades C/C++ |
| **Tratamento de Panics Inesperados** | `recover()` no middleware HTTP | `catch_unwind` em tarefas assíncronas | ✅ Servidor permanece operacional |


## 4. 🏗️ Tiers de Pureza e Maturidade Arquitetural

- **Tier 1: Portável (`--tier=portable`)**: Código 100% puro e portável sem código assembly (`.s`) em dependências externas nem CGO/FFI. Em Go utiliza `-tags "noasm portable"` (ativando o encoder puro `gowebp`). Em Rust utiliza exclusivamente crates compiláveis para qualquer arquitetura ou WebAssembly.

- **Tier 2: Acelerado (`--tier=accelerated`)**: Código 100% puro (sem CGO/FFI), permitindo aceleração SIMD nativa do ecossistema (`deepteams/webp` com assembly em Go; `fast_image_resize` com AVX2/SSE4.1 em Rust).

- **Tier 3: Híbrido (`--tier=hybrid`)**: Extensões com bindings CGO/FFI para bibliotecas de sistema C/C++ (libvips, libjpeg-turbo, libwebp).

