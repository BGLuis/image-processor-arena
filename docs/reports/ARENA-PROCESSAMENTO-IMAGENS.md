# Arena de processamento de imagens — proposta para Go × Rust puros sob alta carga

| Campo | Valor |
|-------|-------|
| **Status** | ✅ Implementado (`go/`, `rust/`, `harness/`, `docker/`); este documento é a proposta original de 2026-09-28, atualizada em 2026-10-02 — **leia a seção 0 primeiro** |
| **Cobertura** | F0–F4 entregues; F5 parcial (servidores, `arena-batch`, runner `oha` e containers, sem coletor de cgroup nem `/metrics`); F6 parcial (tabelas e JSON, sem gráfico tempo × bytes); itens não implementados na seção 0.6 |
| **Esforço** | 17–22 dias-dev no escopo completo; 9–11 d no mínimo viável (estimativa original) |
| **Depende de** | — |
| **Atenção** | ⚠️ AVIF **lossless não existe** na arena (nenhuma biblioteca pura o implementa). O projeto é AGPL-3.0-or-later porque sete crates Rust são AGPL (seção 0.2) |

---

## 0. Atualização de 2026-10-02: o que mudou desde a proposta

As seções 1 a 8 abaixo são a proposta de 2026-09-28, escrita com o diretório vazio. O projeto foi
implementado e algumas decisões mudaram ou se mostraram inviáveis. Esta seção é a fonte de verdade
quando houver conflito com o restante do texto; os trechos que ficaram falsos estão marcados com
**[atualizado]**.

### 0.1 Estado atual

| Parte | Onde |
|---|---|
| Engine Go (servidor, `arena-batch`, codecs, `analyze`, PAM) | `go/cmd/`, `go/internal/` |
| Engine Rust (idem) | `rust/src/`, `rust/src/bin/`, testes de integração em `rust/tests/` |
| Contrato único de parâmetros e limites | `arena.toml` (`[params]`, `[limits]`) |
| Harness: benchmark, validação das saídas, qualidade, carga | `harness/benchmark_arena.py`, `arena_quality.py`, `arena_load.py` |
| Validação cruzada de `analyze` | `harness/verify_cross.py`, `harness/fixtures/ground_truth.json` |
| Resultados | [`results/PODIUM.md`](../../results/PODIUM.md) e `results/benchmark_results.json` |
| Decisões e rascunhos para projetos a montante | `docs/decisions/`, `docs/upstream/` |

### 0.2 Correções à proposta

| Tema | Proposta (seções 2 a 6) | Hoje | Evidência |
|---|---|---|---|
| **AVIF lossless** | Célula Go com `goavif` e célula Rust com `zenravif` + `quantizer = 0` (2.2) | **Não existe.** `mode=lossless` com `format=avif` é recusado (HTTP 400) nos dois engines e a tarefa não faz parte do benchmark. O `goavif` ignora `Options.Lossless` e o `gen2brain/gav1d/avif` sempre converte RGB para YCbCr BT.601 4:2:0; o `zenrav1e` força `base_q_idx >= 1`, então `quantizer 0` nunca ativa o modo lossless do AV1 | `go/internal/codec/codec.go:116`, `rust/src/codec/avif.rs:16`; testes `TestCodecAVIFLosslessIsRefused` e `test_avif_lossless_is_refused` |
| **Parâmetros e qualidade** | Bisseção por alvo SSIMULACRA2 por imagem (2.4) | Contrato único `q`/`effort`/`mode`, mapeado por codec (0.3), mais uma comparação a **qualidade equivalente em PSNR** para AVIF e JXL lossy. SSIMULACRA2 **não** foi implementado | `arena.toml` `[params]`; `harness/benchmark_arena.py:633` (`run_equal_quality`) |
| **O que é cronometrado em `analyze`** | Mesma função nas duas linguagens (2.9) | Passou a ser verdade em 2026-10-02 (issue #7): antes o servidor Rust cronometrava cópia do corpo, parse do PAM e JSON, e o Go só a análise; o BlurHash do Rust chamava `powf` por pixel | `rust/src/bin/server.rs` (`Plan::Analyze`), `rust/src/analyze/blurhash.rs` |
| **Validação das saídas** | Só os arquivos de referência de `decode` (2.6) | Toda saída de todo engine é decodificada por um decoder de referência (Pillow + libjxl + libavif) antes de o tempo valer: lossless exige igualdade exata, lossy um PSNR mínimo por classe; falha vira entrada na seção "Falhas" e código de saída 1 | `harness/benchmark_arena.py:451` (`validate_output`) |
| **Carga HTTP** | `oha` em saturação e a taxa fixa (2.10) | `--mode load` mede em **saturação** (p50/p95/p99 e req/s). A corrida a taxa fixa com `--latency-correction` **não** foi implementada | `harness/benchmark_arena.py:950`, `harness/arena_load.py` |
| **Versões** | `zenwebp` 0.4.5 (2.2) | `zenwebp` 0.4.4 | `rust/Cargo.toml:18` |
| **Limites e erros** | — | Corpo máximo (413), teto de pixels (400), validação antes do processamento, JPEG/WebP acima do limite do formato (400); o perfil release do Rust usa unwind | `arena.toml` `[limits]`; `go/cmd/server/main.go:165`; `rust/src/limits.rs`; `rust/src/bin/server.rs:48` |
| **Licença** | "Aceitar para *benchmark* local; decidir antes de publicar binários" (armadilhas, risco 5) | Decidido: **AGPL-3.0-or-later**. São **sete** os crates AGPL (`jxl-encoder`, `jxl-encoder-simd`, `rav1d-safe`, `zenavif`, `zenrav1e`, `zenravif`, `zenwebp`), permitidos por exceção nomeada em `rust/deny.toml` | `LICENSE`, `rust/deny.toml` |
| **WebP animado** | Não-objetivo (1) | Continua fora, e agora é **recusado** com erro nos dois engines (as bibliotecas compõem quadros de modos diferentes) | `go/internal/codec/codec.go` (`isAnimatedWebP`), `rust/src/codec/webp.rs` |

### 0.3 Contrato de parâmetros (`arena.toml`, `[params]`)

Os dois servidores e os dois `arena-batch` seguem a mesma tabela; valor fora da faixa é recusado (HTTP 400,
`arena-batch` com saída 1), nunca truncado, e valor ausente ou vazio seleciona o padrão. Testes em Go
(`go/internal/codec/params_test.go`) e em Rust (`rust/src/codec/params.rs`, `contract_matches_arena_toml`)
leem o `arena.toml` e falham se o código divergir.

| Parâmetro | Faixa | Padrão |
|---|---|---|
| `q` | inteiro 1..100 | 75 |
| `effort` | inteiro 1..10 (maior é mais lento e menor) | 4 |
| `mode` | `lossy` ou `lossless` | `lossy` (PNG é sempre lossless e ignora `mode`; JPEG é sempre lossy) |

`effort` 1..10 vira uma escala 0..6 pela tabela `effort_step = [0, 1, 1, 2, 3, 3, 4, 5, 5, 6]`: o `method` do
WebP lossy é o degrau, o `effort` do JXL é o degrau + 1 (1..7, a faixa nativa do Go; o encoder Rust tem
defeitos acima de 8, ver 0.5), o `speed` do AVIF é `11 - effort` (invertido) e o PNG usa três faixas
(1-2 mais rápido, 3-6 padrão, 7-10 melhor). `q` é nativo em JPEG e WebP, vira o índice de quantização AV1
`(100 - q) * 255 / 100` no AVIF (o Rust usa a curva inversa do `ravif` para chegar ao mesmo índice) e a
distância Butteraugli do `gen2brain/jxl` no JXL lossy. A tabela completa por codec está no
[README](../../README.md#-contrato-http-e-parâmetros). Os níveis são casados **por posição**, não por algoritmo.

### 0.4 Startup do processo × tempo de codec

Os dois números respondem perguntas diferentes e o benchmark os mantém separados:

- **Modo `http`** (a métrica primária do pódio): o tempo de codec vem dos *headers* `X-Arena-*-Ns` que o
  próprio servidor mede em volta da chamada do codec (`CODEC_TIME_HEADERS`, `harness/benchmark_arena.py:49`).
  O init de pacotes e a abertura do socket acontecem uma vez, na partida, fora de qualquer requisição medida.
  O tempo de parede do cliente (rede, PAM, JSON) é uma coluna à parte.
- **Modo `batch`**: cronometra o **processo inteiro**. O startup de cada binário é medido executando-o com
  entrada inválida (`measure_startup`, `harness/benchmark_arena.py:344`) e a coluna "líquido de startup" é a
  amostra menos a mediana do startup. Esse modo **não mede velocidade de codec**, e o relatório diz isso.
- **Por que importa:** o `init()` do `gen2brain/jxl` custa ~38 ms e 2,1 MB em todo processo Go
  (`GODEBUG=inittrace=1`; 40,5 ms de init no total), contra ~1,6 ms do startup do binário Rust. Em um corpus
  de 0,26 MP isso supera o tempo de codec da maioria das operações. A decisão de manter o custo e reportá-lo
  à parte está em [`docs/decisions/0001-go-jxl-init-cost.md`](../decisions/0001-go-jxl-init-cost.md), e o corpus
  grande (`make_corpus.py --large`, 4,19 MP) reduz o peso relativo do custo fixo.

### 0.5 Resultados e limites conhecidos

Os resultados vigentes estão em [`results/PODIUM.md`](../../results/PODIUM.md): modo `http`, tempo de codec do
servidor, mediana [p25-p75] sobre 10 iterações, PSNR RGB de cada tarefa lossy contra o original decodificado pela
referência, razão geométrica Go/Rust por operação e a comparação a qualidade equivalente de AVIF e JXL. O
`results/LOAD.md` (modo `load`) é gerado à parte. **Os números publicados foram coletados no ambiente descrito
no próprio arquivo e não substituem uma corrida no host isolado de 2.10** (CPU pinada, sem vizinhos).

**Coleta de 2026-10-02 09:57** (Intel Xeon 2,1 GHz, 4 CPUs lógicas, sem CPU pinada; modo `http`, 10 iterações
medidas + 3 de warmup; 34 tarefas, todas com a saída validada, **0 falhas**):

| Operação | Tarefas | Vitórias Go | Vitórias Rust | Empates | Razão geométrica Go/Rust | Leitura |
|---|---|---|---|---|---|---|
| analyze | 4 | 0 | 3 | 1 | 1,11 | Rust 1,11× mais rápido |
| encode | 21 | 3 | 18 | 0 | 4,14 | Rust 4,14× mais rápido |
| decode | 5 | 2 | 3 | 0 | 1,99 | Rust 1,99× mais rápido |
| transcode | 4 | 2 | 2 | 0 | 0,91 | Go 1,10× mais rápido |
| **total** | **34** | **7** | **26** | **1** | **2,67** | **Rust 2,67× mais rápido** |

A razão geométrica pondera a magnitude, que a contagem de vitórias ignora. Os tempos de `encode` e `decode`
comparam codecs de bibliotecas diferentes (2.3): medem o ecossistema, não a linguagem; só `analyze` roda o
mesmo algoritmo nas duas.

**A qualidade equivalente muda a leitura do AVIF.** No mesmo `q` o Rust gera PSNR bem acima do Go (o `gav1d`
grava 4:2:0 e o `ravif` 4:4:4). Alvo = PSNR do Go em `q` 75; o Rust usa o menor `q` que o alcança:

| Tarefa | Rust `q` | Bytes Go ÷ Rust | Tempo de codec a qualidade equivalente |
|---|---|---|---|
| AVIF lossy, photo | 46 | 1,46 | Go 3,63× mais rápido |
| AVIF lossy, screenshot | 36 | 3,17 | empate estatístico (1,07×) |
| JXL lossy, photo | 66 | 1,28 | Rust 4,32× mais rápido |
| JXL lossy, screenshot | 71 | 0,95 | Rust 3,93× mais rápido |

Ou seja: a q equivalente o AVIF do Rust escreve arquivos 1,5× a 3,2× menores, e o Go é mais rápido ou empata
na velocidade; comparar os dois ao mesmo `q` esconderia as duas coisas.

Limites que afetam a leitura: o `jxl-oxide` 0.12.6 não decodifica JXL lossy com alpha de vários grupos (o caso
está explícito em `rust/tests/quality.rs`); o `jxl-encoder` 0.3.1 escreve streams inválidos nos efforts 9 e 10
(por isso o contrato fica em 7); o AVIF do Go é 4:2:0 e o do Rust 4:4:4, então o mesmo `q` não é a mesma
qualidade; o `jxl-encoder` imprime `DIAG` em stderr em lossless no `effort` 10. Detalhes no README e em
`docs/upstream/README.md`.

### 0.6 Da proposta, não implementado

Coletor de cgroup (`collect_cgroup.py`), `/metrics` do Go, contador de alocação do Rust (`count-alloc`) e
`criterion`; calibração por SSIMULACRA2; as corridas a taxa fixa com `--latency-correction`; o tier
*portável* da matriz (o modo `--portable` de `check-purity-go.sh` existe, mas falha por limitação conhecida das
dependências); corpus de ~24 imagens com licença confirmada (o corpus são quatro imagens procedurais por
tamanho, `make_corpus.py`).

---

## 1. Estado atual — evidências **[histórico, 2026-09-28]**

O projeto não tem **nenhum** arquivo nem controle de versão:

```bash
ls -la /home/luis/Documents/hand-on/image-processor-arena
# → total 0 (só . e ..)
find . -maxdepth 3 -not -path './.git*'
# → .   (0 arquivos; não é repositório git)
```

Ambiente medido nesta sessão (2026-09-28), que é o host candidato às medições:

| Item | Valor | Origem |
|---|---|---|
| Go | `go1.27.1 linux/amd64` | `go version` |
| Rust | `rustc 1.97.1`, `cargo 1.97.1` | `rustc --version` |
| CPU | i5-12600K · CPUs 0–11 = 6 P-cores com HT (4,9 GHz) · CPUs 12–15 = 4 E-cores (3,6 GHz) | `lscpu -e=CPU,CORE,MAXMHZ` |
| Memória | 62 GiB total · **~4 GiB disponíveis** no momento da coleta | `free -h` |
| Ferramentas presentes | `docker`, `cjxl`, `avifenc`, `python3` 3.14.7 | `which` |
| Ferramentas ausentes | `hyperfine`, `ssimulacra2`, `butteraugli`, `cwebp`, `podman` | `which` → *not found* |

### Precedentes no código

Nenhum: não há código a reutilizar nem convenção a seguir (busca acima, 0 arquivos). Todas as
decisões da seção 2 se apoiam em documentação externa [Fn] ou ficam marcadas `[modelado]`.

### Correção do pedido

- **`jpg` e `jpeg` são o mesmo formato** (JFIF); só a extensão muda. A arena tem **5** formatos:
  PNG, JPEG, WebP, AVIF e JPEG XL.
- **"Primary color" e "dominant color" são a mesma métrica** na lista de `analyze`; a especificação
  (decisão 2.9) define uma só, com a cor média como subproduto.

### Não-objetivos

- Redimensionamento, filtros, recorte ou qualquer transformação além de codificar, decodificar,
  transcodificar e analisar.
- JPEG lossless, animação (APNG, WebP/AVIF animados), HDR e profundidade > 8 bits.
- GPU, outras linguagens nesta fase e otimizar os codecs de terceiros.
- Ranking de "qual linguagem é mais rápida" em encode/decode — ver decisão 2.3.

---

## 2. As 11 decisões de design

### 2.1 O que é "pura" e como impor

Proibido em qualquer tier: cgo, FFI, bibliotecas carregadas em tempo de execução (purego/dlopen),
C/WASM transpilado ou embutido, NASM/`cc` no *build*. Permitido: `unsafe` do Rust (não é FFI) e
assembly/SIMD escrito na própria linguagem, separado em dois tiers.

| Opção | O que é | Custo | Base | Veredito |
|---|---|---|---|---|
| Tier único "só código de alto nível" | Proíbe Go `.s` e intrínsecos Rust | Perde AVX2 dos melhores codecs Go | [F8] [F9] | Rejeitada: pune quem otimizou |
| Tier único "vale o toolchain" | Libera `.s` e `std::arch` | Esconde quanto vem de SIMD | [F13] [F26] | Rejeitada: resultado não é atribuível |
| **Dois tiers** | *portável* (Go `-tags noasm`, Rust sem SIMD manual) × *nativo* | Dobra a matriz | [F8] [F9] [F18] | **Recomendada** (decidida pelo usuário) |

Imposição mecânica, em CI, antes de qualquer benchmark:

- **Go:** *build* com `CGO_ENABLED=0`; `go list -deps -f '{{.ImportPath}} {{.CgoFiles}} {{.SFiles}}'`
  falha se algum pacote tiver `CgoFiles`, se aparecer `github.com/ebitengine/purego` ou
  `github.com/tetratelabs/wazero`, e — no tier portável — se algum pacote fora da stdlib tiver
  `SFiles`. `gen2brain/webp` é o motivo da regra: tenta a biblioteca dinâmica via purego e só
  depois cai no libwebp transpilado de WASM [F10].
- **Rust:** `cargo-deny` com `[bans] deny = ["cc", "cmake", "bindgen", "nasm-rs", "pkg-config"]` e
  `[bans.build] allow-build-scripts` restrito à lista revisada [F32]; o script também falha se
  `cargo metadata` listar pacote com campo `links`. Alocador global é o `System` — mimalloc e
  jemalloc chegam por crates `-sys` e ficam fora.

### 2.2 Matriz de codecs

Um codec por célula, fixado num manifesto (`arena.toml`) com versão; célula sem codec puro fica ❌ e
é publicada como lacuna, **nunca** preenchida com FFI. **[atualizado]** A célula AVIF lossless virou ❌ (0.2).

| Formato | Go — encode | Go — decode | Rust — encode | Rust — decode |
|---|---|---|---|---|
| PNG | `image/png`, níveis `BestSpeed`…`BestCompression` [F2] | `image/png` | `png` 0.18.1 [F12] | `png` 0.18.1 |
| JPEG | `image/jpeg`, só *baseline* 4:2:0, `Quality` 1–100 [F1] | `image/jpeg` | `jpeg-encoder` 0.7.1 [F13] | `zune-jpeg` 0.5.16-rc2 [F26] |
| WebP lossy | `deepteams/webp` [F5] | `deepteams/webp` | `zenwebp` 0.4.4 (AGPL) [F16] | `image-webp` 0.2.4 [F15] |
| WebP lossless | `KarpelesLab/gowebp` [F6] | idem | `image-webp` 0.2.4 [F15] | idem |
| AVIF lossy | `gen2brain/gav1d` — 8 bits, 4:2:0, *all-intra* [F8] | `gen2brain/gav1d` | `ravif` 0.13.0 sem `asm` [F17] | `rav1d` 1.1.0 sem `asm` [F23] |
| AVIF lossless **[atualizado]** | ❌ não existe: `goavif` ignora `Options.Lossless` e o `gav1d` converte para 4:2:0 [F7] | ❌ | ❌ não existe: `quantizer = 0` do `zenrav1e` nunca ativa o lossless do AV1 [F20] [F21] | ❌ |
| JPEG XL | `gen2brain/jxl`, VarDCT e Modular [F9] | `gen2brain/jxl` | `jxl-encoder` 0.3.1 (AGPL) [F22] | `jxl-oxide` 0.12.6 [F25] |

Rejeitadas, com o motivo:

- `gen2brain/webp`, `gen2brain/avif`, `gen2brain/jpegxl` — libwebp/libavif/libjxl em WASM ou
  wasm2go, com purego antes do *fallback* [F10] [F37].
- `f0reth/go-avif` — libavif via purego [F37]. `chai2010/webp` — cgo [F5].
  `Kagami/go-avif` — cgo sobre libaom `[modelado]`, não conferido nesta sessão.
- `image-webp` 0.2.4 para WebP lossy — a versão publicada só codifica lossless; o encoder lossy
  está no *branch* principal, sem *release* [F15] [F38].
- `ravif` para AVIF lossless — não existe: qualidade 100 só gera arquivo inchado [F19].
- `gen2brain/vpx` — codec VP8 recente e com *kernels* `amd64`, mas a página consultada não
  mostra um encoder WebP pronto para uso [F11]; reavaliar se `deepteams/webp` falhar em F1.
- `zenjpeg` 0.8.4 no lugar de `jpeg-encoder` — melhor relação tamanho/qualidade, mas AGPL e
  ~389K SLoC de dependências [F14]; fica como candidato de segunda rodada.

### 2.3 O que a arena compara de fato

Em `encode`, `decode` e `transcode` cada linguagem usa um codec **diferente**, escrito por outra
pessoa, com outro algoritmo de busca. O resultado mede o **ecossistema** de cada linguagem, não a
linguagem. O relatório de resultados precisa dizer isso no título de cada tabela. Só `analyze`
(decisão 2.9) compara algoritmo idêntico nas duas linguagens.

### 2.4 Iso-qualidade **[atualizado: implementado em PSNR, não em SSIMULACRA2; ver 0.2]**

| Opção | O que é | Custo | Base | Veredito |
|---|---|---|---|---|
| Parâmetro nominal fixo (`quality=75`) | Mesmo número em todos | 0 | — | Rejeitada: escalas não calibradas entre si [F13] |
| **Alvo SSIMULACRA2** | Bisseção do parâmetro por imagem até 70 e 90 | ~1 d de *harness* | [F29] | **Recomendada** |

70 é "alta qualidade" e 90 é "visualmente sem perdas" na escala da métrica [F29]. O *harness*
calibra uma vez por (codec, alvo, imagem), grava o parâmetro no manifesto e o envia em cada
requisição. Lossless não é calibrado: é validado por igualdade de pixels. O resultado de cada
célula é um **par (tempo, bytes) na mesma qualidade**, não um só número.

### 2.5 Contrato HTTP e flag de operação

Um endpoint, idêntico nas duas linguagens:

```text
POST /run?op=encode|decode|transcode|analyze&format=<fmt>&to=<fmt>&mode=lossy|lossless&q=<n>&effort=<n>
```

| `op` | Corpo | Resposta | Tempos devolvidos |
|---|---|---|---|
| `encode` | pixels crus (PAM, RGB ou RGBA 8 bits) | arquivo `format` | `X-Arena-Encode-Ns` |
| `decode` | arquivo `format` | PAM | `X-Arena-Decode-Ns` |
| `transcode` | arquivo `format` | arquivo `to` | `X-Arena-Decode-Ns` + `X-Arena-Encode-Ns` |
| `analyze` | PAM | JSON de métricas (2.9) | `X-Arena-Analyze-Ns` |

Os *headers* separam o tempo de codec do tempo de rede e de leitura do corpo. O *batch* CLI usa a
mesma flag (`--op`) e a mesma função interna. Concorrência: *pool* de *workers* igual ao número de
núcleos alocados, cada codec com uma *thread*; Go com `net/http`, Rust com `hyper` sobre `tokio` e
`spawn_blocking` limitado ao tamanho do *pool*.

### 2.6 Entrada de `decode` e `transcode`

Os arquivos decodificados são gerados **uma vez** por encoders de referência do *harness* (`cjxl` e
`avifenc` já estão no host; `cwebp` e um encoder JPEG de referência a instalar) e são os mesmos
para Go e Rust. Decodificar a saída do próprio encoder mediria o encoder junto. Validação: lossless
→ pixels idênticos ao decoder de referência; lossy → diferença máxima por canal dentro de tolerância
declarada, porque IDCT e *upsampling* de croma podem divergir legitimamente (tolerância
`[modelado]` até a primeira medição).

### 2.7 Inventário de métricas de desempenho

| Grupo | Métrica | Definição | Coleta |
|---|---|---|---|
| *Throughput* | MP/s | megapixels ÷ tempo da fase (por requisição) e ÷ *wall* da janela (agregado) | *headers* + *harness* |
| *Throughput* | MB/s de entrada | bytes crus (`encode`, `analyze`) ou comprimidos (`decode`) ÷ tempo | idem |
| *Throughput* | MB/s de saída | bytes comprimidos (`encode`) ou crus (`decode`) ÷ tempo; n/a em `analyze` | idem |
| *Throughput* | req/s | requisições com sucesso ÷ janela | `oha` [F30] |
| Latência | p50, p95, p99, p99.9 | chaves `p50`…`p99.9` do JSON | `oha` [F31] |
| CPU | usuário × sistema | `user_usec` × `system_usec` na janela; sistema alto denuncia `mmap`, I/O ou troca de contexto | `cpu.stat` [F33] |
| CPU | fator de utilização | tempo de CPU ÷ *wall*; ≈ 1 prova execução serial, ≈ N prova paralelismo | `cpu.stat` [F33] |
| CPU | *throttling* | `nr_throttled`, `throttled_usec`; > 0 invalida a janela | `cpu.stat` [F33] |
| Memória | pico do container | `memory.peak`, resetado por escrita no início da janela | cgroup v2 [F33] |
| Memória | RSS de pico do processo | `VmHWM` de `/proc/<pid>/status` | *harness* |
| Memória | composição e falhas | `memory.stat` `anon` × `file`; `memory.events` `oom_kill` | cgroup v2 [F33] |
| Alocação | Go: allocs/op, B/op | `testing.B` com `ReportAllocs`; no servidor `/gc/heap/allocs:bytes` e `:objects` | [F3] |
| Alocação | Rust: chamadas, bytes, pico vivo | `GlobalAlloc` contador envolvendo `System`, *build* `count-alloc` | [F34] |
| Normalizada | ms de CPU por imagem e por MP · MB de pico por *worker* · bytes por pixel | derivada | *harness* |

O cgroup é a fonte **primária** de CPU e memória porque é a mesma para as duas linguagens.
`docker stats` fica só como sanidade: é amostral e não dá pico exato.

O contador de alocação do Rust exige `unsafe impl GlobalAlloc` e não pode alocar nem entrar em
pânico dentro do alocador [F34]. Ele roda numa *build* separada porque os atômicos por alocação
mudam o tempo medido **[modelado]**; a corrida cronometrada usa o `System` puro.

### 2.8 O GC do Go faz parte do resultado

O GC é custo inerente da linguagem e entra no número publicado. Perfil principal: `GOGC` padrão
(100) e `GOMEMLIMIT` não definido, com os valores efetivos lidos de `/gc/gogc:percent` e
`/gc/gomemlimit:bytes` [F3] e gravados junto do resultado. `GOMAXPROCS` é fixado explicitamente no
número de CPUs do container e conferido em `/sched/gomaxprocs:threads` [F3] — o ajuste automático a
cgroups não foi conferido nesta sessão `[modelado]`.

Publicado por célula Go, a partir de `runtime/metrics` [F3]:

- `/sched/pauses/total/gc:seconds` — distribuição das pausas *stop-the-world*, cruzada com p99 e
  p99.9 da mesma janela para mostrar se a cauda vem do GC;
- `/cpu/classes/gc/total:cpu-seconds` — só como fração de `/cpu/classes/total:cpu-seconds`, porque a
  documentação diz que é superestimado e não comparável à CPU do sistema;
- `/gc/cycles/total:gc-cycles` e `/gc/heap/goal:bytes`.

Rejeitados: `GOGC=off`, descontar o tempo de GC e chamar `runtime.GC()` entre requisições — os três
publicariam um Go que não existe em produção.

### 2.9 `op=analyze` — uma especificação, duas implementações

Decidido pelo usuário: a extração de métricas de conteúdo é uma operação **medida sob carga**,
implementada em Go e Rust puros. Para a comparação ser de linguagem e não de biblioteca, as duas
implementações seguem `docs/analyze-spec.md`, escrita antes do código.

| Opção | O que é | Custo | Base | Veredito |
|---|---|---|---|---|
| Bibliotecas prontas (`goimagehash` × `image_hasher`) | pHash de cada ecossistema | 0,5 d | [F27] [F28] | Rejeitada: reamostragem e DCT diferentes → hashes diferentes |
| **Implementação à mão contra a spec** | Mesmo algoritmo, mesma aritmética | 4–5 d | [F35] [F36] | **Recomendada** |

Luma e croma usam aritmética **inteira** (`Y = (77R + 150G + 29B + 128) >> 8`, coeficientes BT.601
em ponto fixo) para que Go e Rust produzam bits idênticos; o que é inevitavelmente *float* tem
tolerância ε declarada na spec.

| Métrica | Definição fixada na spec | Saída |
|---|---|---|
| Largura, altura, proporção | cabeçalho PAM; `w/h` e fração reduzida por MDC | inteiros, *float*, `"16:9"` |
| Alinhamento a blocos | `w mod b`, `h mod b` e % de pixels em blocos parciais, b ∈ {8, 16, 64, 256} | inteiros, *float* |
| Luminância média | média de Y | *float* |
| Entropia de Shannon | histograma de Y com 256 *bins*; e entropia do resíduo horizontal `Y[x] − Y[x−1]` | bits/pixel |
| SI | desvio padrão da magnitude de Sobel sobre Y, sem a borda [F36] | *float* |
| Energia de gradiente | média de `Gx² + Gy²` (Sobel) e variância do Laplaciano de 4 vizinhos | *float* |
| Variância de cor | variância de R, G, B e soma | *float* |
| Cores únicas | contagem exata de valores RGBA de 32 bits | inteiro |
| Alpha | tem alpha; fração A = 0 (esparsidade); fração A ∈ {0, 255} (binaridade) | *bool*, *float* |
| Adequação a 4:2:0 | razão entre energia de gradiente de Cb/Cr e de Y; MSE de Cb/Cr após ida e volta 2×2 | *float* |
| Área plana | fração de blocos 8×8 com variância de Y < limiar T da spec | *float* |
| Cor dominante e média | moda do histograma RGB de 4 bits por canal (empate → menor índice); média RGB | RGB |
| blurHash | 4×3 componentes, DC convertido de sRGB para linear, base 83 [F35] | *string* |
| pHash | Y → 32×32 por média de área → DCT-II 2D → 8×8 sem o DC → bit = coef > mediana | 64 bits hex |

Os tamanhos de bloco da linha de alinhamento seguem as unidades dos codecs — 8 (DCT do JPEG e do
VarDCT), 16 (macrobloco VP8), 64 (superbloco AV1), 256 (grupo JXL) — por conhecimento prévio,
não conferido nesta sessão `[modelado]`. O limiar T da área plana também é `[modelado]` até a
calibração com o corpus.

### 2.10 Corpus e carga

- Quatro classes — foto, *screenshot*, gráfico/ilustração, imagem com alpha — em ~24 imagens de
  1–12 MP `[modelado]`, licença livre a confirmar antes de F1. Imagens com alpha ficam fora das
  células JPEG.
- *Batch* usa o corpus inteiro; carga HTTP usa **uma imagem representativa por classe**, porque
  o `oha` envia o mesmo corpo em todas as requisições de uma corrida (`-D <arquivo>`) [F30].
- Duas corridas por (célula, imagem): **saturação** (malha fechada, sem `-q`) dá o *throughput*
  máximo; **taxa fixa** a 80 % do máximo com `-q` e `--latency-correction` dá a latência sem
  *coordinated omission* [F30]. p99.9 só é publicado com ≥ 10.000 requisições na corrida.
- Isolamento: servidor em container com `--cpuset-cpus` nos P-cores (CPUs 0–11 pelo `lscpu`),
  gerador de carga nos E-cores (12–15), memória com limite fixo; corpus servido da memória.

### 2.11 O que não fazer

- Não aceitar codec em WASM "porque compila sem cgo" — é C por outro caminho [F10].
- Não comparar `quality=N` nominal entre encoders (2.4).
- Não misturar paralelismo interno do codec com *pool* de *workers*: `rayon` (`ravif`,
  `jxl-oxide`) e o paralelismo por linhas do `deepteams/webp` são desligados na arena principal
  [F5] [F17] [F25]; o paralelismo interno aparece só no perfil de escalabilidade (1 *worker*,
  *threads* do codec livres), onde o fator de utilização o mede.
- Não ligar o contador de alocação na corrida cronometrada (2.7).

---

## 3. Plano de implementação

| Fase | Conteúdo | Esforço |
|---|---|---|
| **F0** | Esqueleto `go/` e `rust/`, `arena.toml`, guardas de pureza (2.1) em CI com teste negativo | 1–1,5 d |
| **F1** | Corpus, arquivos de referência para `decode` (2.6), calibração SSIMULACRA2 (2.4), validadores | 2,5–3,5 d |
| **F2** | Go: `encode`/`decode`/`transcode` nas 7 linhas da matriz 2.2, microbenchmarks com `ReportAllocs` | 2,5–3,5 d |
| **F3** | Rust: idem, `criterion`, *build* `count-alloc` | 2,5–3,5 d |
| **F4** | `docs/analyze-spec.md`, imagens sintéticas com resposta conhecida, `analyze` em Go e Rust | 4–5 d |
| **F5** | Servidores HTTP e *batch* com `--op`, coletor cgroup, `/metrics` do Go, *runner* `oha`, containers | 2,5–3 d |
| **F6** | Agregação, tabelas por célula, gráfico tempo × bytes, publicação dos dados brutos | 1,5–2 d |

**Mínimo viável** — tier nativo, lossy + PNG, só HTTP, as quatro `op`, métricas de *throughput*,
latência, CPU e pico de memória: F0 + F1 (sem lossless) + F2/F3 parciais + F4 + F5 ≈ 9–11 d.
**Escopo completo:** F0–F6 ≈ 17–22 d.

Ordem importa: F0 primeiro faz a regra de pureza nascer como teste e barra codec proibido antes de
alguém medi-lo; F1 antes de F2–F4 porque os arquivos de referência e os parâmetros calibrados são
insumo das duas linguagens; F4 começa pela spec, e o código só depois que a spec tiver os casos
sintéticos com resposta esperada.

---

## 4. Armadilhas

| Armadilha | Mitigação |
|---|---|
| `rav1e` 0.8.1 traz `asm` (NASM + `cc`) por padrão, e `ravif` 0.13.0 liga `asm` por padrão [F17] [F18] | `ravif` com `default-features = false, features = ["threading"]` só se o *pool* precisar; o `cargo-deny` falha se `nasm-rs` voltar |
| `rav1d` 1.1.0 liga `asm` por padrão, com ~155K SLoC de assembly [F23] | `--no-default-features --features bitdepth_8,bitdepth_16`; tier nativo pode usar `rav1d-safe` (SIMD em Rust seguro, AGPL) [F24] |
| `gen2brain/*` de WebP/AVIF/JXL-libjxl tenta biblioteca dinâmica antes do *fallback* [F10] | Guarda de import de `purego` e `wazero` (2.1) |
| CPU híbrida: E-cores a 3,6 GHz × P-cores a 4,9 GHz | `--cpuset-cpus` fixo (2.10); nunca deixar o escalonador escolher |
| Só ~4 GiB livres no host no momento da coleta | Checar `free` antes de cada rodada; abortar se o limite do container não couber |
| `rayon` em `ravif`/`jxl-oxide` e paralelismo por linha em `deepteams/webp` [F5] [F25] | Desligar ou limitar a 1 *thread* na arena principal; conferir pelo fator de utilização ≈ *workers* |
| Stdlib Go só gera JPEG *baseline* 4:2:0 [F1]; `jpeg-encoder` tem *progressive* e Huffman otimizado [F13] | Configurar o Rust em *baseline* na célula comparável; *progressive* vira célula separada, ❌ no Go |
| `jpeg-encoder` com `simd` adiciona `unsafe` AVX2 [F13]; `zune-jpeg` usa intrínsecos no `x86` [F26] | Feature ligada só no tier nativo |
| Tier portável não é escalar: Go e Rust ainda autovetorizam, e dependências de *checksum*/*deflate* podem trazer SIMD sem chave `[modelado]` | Definir tier portável pela lista de chaves por codec; célula sem chave fica ⚠️ "portável parcial" |
| Licença AGPL de `zenwebp`, `zenravif`, `jxl-encoder`, `rav1d-safe` [F16] [F20] [F22] [F24] | **[atualizado]** Decidido: o projeto é AGPL-3.0-or-later; exceções nomeadas em `rust/deny.toml` (são sete crates, 0.2) |
| *Scavenger* do Go devolve memória com atraso: `memory.current` pós-carga engana `[modelado]` | Comparar só `memory.peak` resetado por janela [F33] |
| *Page cache* dos arquivos lidos infla `memory.peak` [F33] | Corpus em memória; separar `file` de `anon` em `memory.stat` |
| `/cpu/classes/*` do Go não é comparável à CPU do sistema [F3] | Usar só como proporção interna; CPU comparável vem do cgroup |
| Sem `--latency-correction`, a taxa fixa esconde a fila (*coordinated omission*) [F30] | Flag obrigatória no *runner* |
| blurHash exige sRGB → linear no DC [F35]; pHash muda com o filtro de reamostragem | Fixar as duas coisas na spec (2.9) |
| `GOEXPERIMENT=simd` (`simd/archsimd`) está fora da promessa de compatibilidade do Go 1 [F4] | Não usar em codec da arena até sair do experimento |

---

## 5. Verificação

Itens marcados `[x]` foram verificados em 2026-10-02 com a evidência indicada; os demais continuam como na
proposta, sem verificação nesta data.

**Guardas de pureza em CI (`scripts/check-purity-go.sh`, `scripts/check-purity-rust.sh`):**
- [ ] Adicionar `github.com/ebitengine/purego` ao `go.mod` faz a guarda Go falhar — guarda 2.1 e o
      comportamento de *fallback* documentado em [F10].
- [ ] Adicionar um crate com `build.rs` que usa `cc` faz o `cargo-deny` falhar — guarda 2.1 [F32].
- [ ] Tier portável: `go list -deps -tags noasm` sem `SFiles` fora da stdlib — guarda 2.1 [F8] [F9].

**Automatizável no host (`go test ./...`, `cargo test`):**
- [x] Lossless (PNG, WebP, JXL; **AVIF não existe**, 0.2): decodificar devolve pixels idênticos à entrada —
      guarda 2.2 e a ausência de lossless no `ravif` [F19]. Go: `TestLosslessRoundtripIsPixelExact`
      (`go/internal/codec/codec_test.go`); Rust: `lossless_roundtrip_is_pixel_exact_on_the_corpus`
      (`rust/tests/quality.rs`); e o harness valida cada saída contra a referência.
- [x] `decode` de cada arquivo de referência bate com o decoder de referência (exato em PNG, PSNR ≥ 40 dB nos
      demais) — guarda 2.6. `validate_output` em `harness/benchmark_arena.py`.
- [ ] Parâmetro calibrado reproduz SSIMULACRA2 no alvo ± 1 — guarda 2.4 [F29].
- [ ] Teste de contrato: as quatro `op` com os mesmos parâmetros são aceitas pelos dois servidores
      e `transcode` devolve os dois *headers* de fase — guarda 2.5.
- [x] `analyze` em imagem sólida: entropia 0, SI 0, 1 cor única, área plana 100 %, binaridade de
      alpha 100 % — guarda 2.9. Fixtures `solid_black.pam` e `solid_red.pam` em `ground_truth.json`
      (`verify_cross.py --mode batch --target all`: 16 de 16).
- [x] `analyze` em xadrez 1×1: SI e energia de gradiente iguais ao valor calculado à mão na spec — fixture
      `checkerboard_1x1.pam`, mesmo gabarito.
- [ ] blurHash das imagens de exemplo do repositório de referência igual à *string* publicada [F35].
- [x] Go × Rust: todas as métricas inteiras idênticas e as de *float* dentro de ε. Nas fixtures sintéticas pelo
      gabarito e no corpus de 4 MP diretamente (`verify_cross.py --mode compare`: 4 de 4).

**Desempenho — protocolo de `medicao-desempenho.md` (só no host de medição, pendente):**
- [ ] Saturação: `oha -c <2 × workers> -z 20s --output-format json -D <img.pam>` depois de 5 s de
      aquecimento descartado, n = 10 por (célula, imagem); publicar média ± desvio de MP/s e req/s.
- [ ] Taxa fixa a 80 % da saturação com `-q` e `--latency-correction` [F30]: p50/p95/p99 com n = 3
      corridas de 60 s (indicativo, n < 10 declarado); p99.9 só com ≥ 10.000 requisições.
- [ ] *Batch*: `hyperfine --warmup 3 --runs 10 --export-json` por `op` — mediana e p95.
- [ ] Microbenchmarks: `go test -bench -benchmem -count=10` + `benchstat`; `criterion` no Rust.
- [ ] Toda janela aceita tem `nr_throttled` = 0 e zero `oom_kill` [F33].
- [ ] Coletor validado: carga sintética de 2 núcleos por 10 s gera `usage_usec` ≈ 20 s (± 5 %).
- [ ] Σ `usage_usec` da janela ≥ Σ tempos de fase dos *headers*; a diferença é publicada como custo
      fora do codec (HTTP, GC, cópia).
- [ ] *Build* `count-alloc` conta exatamente 1 alocação num caso sintético que aloca um `Vec` —
      guarda 2.7 [F34].
- [ ] Go: `/gc/gogc:percent` = 100 e distribuição de pausas publicada ao lado de p99.9 — guarda 2.8 [F3].

---

## 6. Riscos

1. **O custo de rodar a matriz é maior que o de escrevê-la.** Tier nativo: 2 linguagens × ~29
   configurações (12 de `encode`, 12 de `decode`, 4 de `transcode`, 1 de `analyze`) × 4 imagens =
   232 combinações; saturação (10 × 20 s) + taxa fixa (3 × 60 s) ≈ 24–25 h de máquina dedicada
   **[modelado]**. Recomendação: protocolo completo só no tier nativo; tier portável só no *batch*.
2. **Codecs jovens podem invalidar células.** Vários candidatos Go são de 2026 e têm poucas
   estrelas; `gen2brain/gav1d` mostra 6 [F8]. Um defeito de conformidade vira célula ❌, não
   atraso — desde que a validação de F1 rode antes de qualquer medição.
3. **A leitura do resultado pode ser injusta com a linguagem.** Um codec Rust com anos de
   otimização contra um Go recém-escrito mede maturidade de ecossistema (2.3); só `analyze` isola a
   linguagem.
4. **`analyze` pode dominar o cronograma.** Sem a spec fechada, cada divergência Go × Rust vira
   discussão de algoritmo. É o maior item do plano (4–5 d) e a razão de a spec vir primeiro.
5. **Licença AGPL** restringe publicar binários da arena com os crates `zen*` e `jxl-encoder`
   [F16] [F22]; a alternativa MIT/Apache deixa WebP lossy e AVIF lossless sem codec Rust.
   **[atualizado]** Decidido em 2026-10-02: AGPL-3.0-or-later (seção 0.2); quem serve a arena em rede
   deve oferecer o código-fonte (AGPL, seção 13).
6. **Host compartilhado.** Com ~4 GiB livres na coleta, medições de memória no *desktop* de uso
   diário são frágeis; um host dedicado ou uma VM com recursos fixos elimina o risco.

---

## 7. Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `README.md` | **novo** — regras da arena, tiers, como rodar |
| `arena.toml` | **novo** — manifesto de codecs, versões, parâmetros calibrados por imagem |
| `docs/analyze-spec.md` | **novo** — especificação de `analyze` com casos sintéticos |
| `go/cmd/server/`, `go/cmd/batch/` | **novo** — servidor HTTP e CLI com `--op` |
| `go/internal/codec/`, `go/internal/analyze/`, `go/internal/pam/` | **novo** — adaptadores de codec, `analyze`, PAM |
| `go/**/*_test.go` | **novo** — contrato, lossless, `analyze`, benchmarks com `ReportAllocs` |
| `rust/Cargo.toml`, `rust/Cargo.lock`, `rust/deny.toml` | **novo** — dependências fixadas, regras de pureza |
| `rust/src/codec/`, `rust/src/analyze/`, `rust/src/pam.rs` | **novo** — equivalentes Rust |
| `rust/src/alloc_counter.rs` | **novo** — `GlobalAlloc` contador, atrás da feature `count-alloc` |
| `rust/benches/` | **novo** — `criterion` |
| `scripts/check-purity-go.sh`, `scripts/check-purity-rust.sh` | **novo** — guardas de CI |
| `harness/` | **novo** — corpus, calibração, `collect_cgroup.py`, *runner* `oha`, agregação |
| `docker/go.Dockerfile`, `docker/rust.Dockerfile` | **novo** — imagens de medição |
| `docs/reports/ARENA-PROCESSAMENTO-IMAGENS.md` | este relatório |

---

## 8. Fontes consultadas

| # | Fonte | Tipo | Versão | Consultada em | Sustenta |
|---|---|---|---|---|---|
| F1 | [pkg.go.dev — `image/jpeg`](https://pkg.go.dev/image/jpeg) | Doc oficial | go1.27.1 | 2026-09-28 | 2.2, armadilha JPEG |
| F2 | [pkg.go.dev — `image/png`](https://pkg.go.dev/image/png) | Doc oficial | go1.27.1 | 2026-09-28 | 2.2 |
| F3 | [pkg.go.dev — `runtime/metrics`](https://pkg.go.dev/runtime/metrics) | Doc oficial | go1.27.1 | 2026-09-28 | 2.7, 2.8, verificação |
| F4 | [Go 1.26 Release Notes — `simd/archsimd`](https://go.dev/doc/go1.26) | Doc oficial | 1.26 | 2026-09-28 | Armadilha `GOEXPERIMENT=simd` |
| F5 | [`deepteams/webp`](https://github.com/deepteams/webp) | Projeto de terceiros | `main` | 2026-09-28 | 2.2, 2.11, `chai2010/webp` é cgo |
| F6 | [`KarpelesLab/gowebp`](https://github.com/KarpelesLab/gowebp) | Projeto de terceiros | `main` | 2026-09-28 | 2.2 |
| F7 | [`KarpelesLab/goavif`](https://github.com/KarpelesLab/goavif) | Projeto de terceiros | `main` | 2026-09-28 | 2.2 (lossless, sem SIMD) |
| F8 | [`gen2brain/gav1d`](https://github.com/gen2brain/gav1d) | Projeto de terceiros | `main` | 2026-09-28 | 2.1, 2.2, risco 2 |
| F9 | [`gen2brain/jxl`](https://github.com/gen2brain/jxl) | Projeto de terceiros | `main` | 2026-09-28 | 2.1, 2.2 |
| F10 | [`gen2brain/webp`](https://github.com/gen2brain/webp) | Projeto de terceiros | `main` | 2026-09-28 | 2.1, 2.2 (rejeição), 2.11 |
| F11 | [pkg.go.dev — `gen2brain/vpx/vp8`](https://pkg.go.dev/github.com/gen2brain/vpx/vp8) | Doc oficial | v0.2.1 | 2026-09-28 | Seção 8 (candidato não adotado) |
| F12 | [lib.rs — `png`](https://lib.rs/crates/png) | Doc oficial | 0.18.1 | 2026-09-28 | 2.2 |
| F13 | [lib.rs — `jpeg-encoder`](https://lib.rs/crates/jpeg-encoder) | Doc oficial | 0.7.1 | 2026-09-28 | 2.1, 2.2, 2.4, armadilhas |
| F14 | [lib.rs — `zenjpeg`](https://lib.rs/crates/zenjpeg) | Doc oficial | 0.8.4 | 2026-09-28 | 2.2 (rejeição) |
| F15 | [crates.io — `image-webp`](https://crates.io/crates/image-webp) | Doc oficial | 0.2.4 | 2026-09-28 | 2.2 |
| F16 | [`imazen/zenwebp`](https://github.com/imazen/zenwebp) | Doc oficial | 0.4.5 | 2026-09-28 | 2.2, armadilha AGPL, risco 5 |
| F17 | [docs.rs — features do `ravif`](https://docs.rs/crate/ravif/latest/features) | Doc oficial | 0.13.0 | 2026-09-28 | 2.2, 2.11, armadilha `asm` |
| F18 | [`rust-av/rav1e`](https://github.com/rust-av/rav1e) + [features](https://docs.rs/crate/rav1e/latest/features) | Doc oficial | 0.8.1 | 2026-09-28 | 2.1, armadilha `asm` |
| F19 | [`kornelski/cavif-rs`](https://github.com/kornelski/cavif-rs) | Doc oficial | `main` | 2026-09-28 | 2.2 (sem lossless), verificação |
| F20 | [lib.rs — `zenravif`](https://lib.rs/crates/zenravif) | Doc oficial | 0.1.3 | 2026-09-28 | 2.2, armadilha AGPL |
| F21 | [`imazen/zenrav1e`](https://github.com/imazen/zenrav1e) | Doc oficial | `main` | 2026-09-28 | 2.2 (`asm` fora do padrão; lossless com `quantizer = 0`) |
| F22 | [lib.rs — `jxl-encoder`](https://lib.rs/crates/jxl-encoder) | Doc oficial | 0.3.1 | 2026-09-28 | 2.2, armadilha AGPL, risco 5 |
| F23 | [lib.rs — `rav1d`](https://lib.rs/crates/rav1d) | Doc oficial | 1.1.0 | 2026-09-28 | 2.2, armadilha `asm` |
| F24 | [`imazen/rav1d-safe`](https://github.com/imazen/rav1d-safe) | Doc oficial | `main` | 2026-09-28 | Armadilhas `asm` e AGPL |
| F25 | [lib.rs — `jxl-oxide`](https://lib.rs/crates/jxl-oxide) | Doc oficial | 0.12.6 | 2026-09-28 | 2.2, 2.11 |
| F26 | [lib.rs — `zune-jpeg`](https://lib.rs/crates/zune-jpeg) | Doc oficial | 0.5.16-rc2 | 2026-09-28 | 2.1, 2.2 |
| F27 | [lib.rs — `image_hasher`](https://lib.rs/crates/image_hasher) | Doc oficial | 3.1.1 | 2026-09-28 | 2.9 (rejeição) |
| F28 | [pkg.go.dev — `goimagehash`](https://pkg.go.dev/github.com/corona10/goimagehash) | Doc oficial | v1.1.0 | 2026-09-28 | 2.9 (rejeição) |
| F29 | [`cloudinary/ssimulacra2`](https://github.com/cloudinary/ssimulacra2) | Doc oficial | `main` | 2026-09-28 | 2.4, verificação |
| F30 | [`hatoo/oha`](https://github.com/hatoo/oha) | Doc oficial | `master` | 2026-09-28 | 2.7, 2.10, armadilha *coordinated omission* |
| F31 | [`oha` — `schema.json`](https://raw.githubusercontent.com/hatoo/oha/master/schema.json) | Doc oficial | `master` | 2026-09-28 | 2.7 (chaves de percentil) |
| F32 | [cargo-deny — `bans`](https://embarkstudios.github.io/cargo-deny/checks/bans/cfg.html) | Doc oficial | atual | 2026-09-28 | 2.1, verificação |
| F33 | [Linux — Control Group v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) | Doc oficial | atual | 2026-09-28 | 2.7, armadilhas de memória, verificação |
| F34 | [Rust std — `GlobalAlloc`](https://doc.rust-lang.org/std/alloc/trait.GlobalAlloc.html) | Doc oficial | 1.97 | 2026-09-28 | 2.7, verificação |
| F35 | [`woltapp/blurhash` — `Algorithm.md`](https://github.com/woltapp/blurhash/blob/master/Algorithm.md) | Doc oficial | `master` | 2026-09-28 | 2.9, verificação |
| F36 | [ITU-T P.910](https://www.itu.int/rec/T-REC-P.910) · [`slhck/siti`](https://github.com/slhck/siti) | Doc oficial | 10/2023 | 2026-09-28 | 2.9 (SI) |
| F37 | pkg.go.dev — [`gen2brain/avif`](https://pkg.go.dev/github.com/gen2brain/avif), [`gen2brain/jpegxl`](https://pkg.go.dev/github.com/gen2brain/jpegxl), [`f0reth/go-avif`](https://pkg.go.dev/github.com/f0reth/go-avif) | Doc oficial | atual | 2026-09-28 | 2.2 (rejeições) |
| F38 | [`vaam-apps/vaam-image-webp`](https://github.com/vaam-apps/vaam-image-webp) | Projeto de terceiros | `main` | 2026-09-28 | 2.2 (lossy do `image-webp` sem *release*) |

F4, F36 e F37 foram lidos só pelo resumo da busca, não pela página inteira. Não foram
consultados nesta sessão, e por isso seguem `[modelado]` ou pendentes: se o `gav1d` codifica
lossless; se o `deepteams/webp` permite limitar as *threads* internas; os níveis de *effort* do
`gen2brain/jxl`; se `zenwebp` e `jxl-encoder` permitem desligar o SIMD (condição do tier
portável); crates de blurHash em Go e Rust; a licença do corpus.

---

> **[atualizado]** A nota original ("nenhum item foi executado, o diretório está vazio") vale só para as seções
> 1 a 8 como estavam em 2026-09-28. O que foi executado, o que mudou e o que ficou de fora está na seção 0; a
> verificação da seção 5 está parcialmente automatizada (ver o estado de cada item ali).
