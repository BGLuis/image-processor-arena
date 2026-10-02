# Relatórios para os projetos a montante (rascunhos)

Defeitos encontrados nas dependências de JPEG XL, com arquivos de reprodução pequenos em
[`data/`](data/). **Nada aqui foi publicado**: abrir issues em repositórios de terceiros é decisão do
dono do projeto. Cada seção está pronta para ser colada numa issue; a primeira corresponde ao item
"abrir o bug upstream" da issue de remoção do `rust/vendor/jxl-modular` (#19).

Versões: `jxl-oxide` 0.12.6, `jxl-modular` 0.11.3 (vendorizado em `rust/vendor/`), `jxl-encoder` 0.3.1,
libjxl pelo `pillow-jxl-plugin` 1.3.8, `gen2brain/jxl` 0.2.0. Os arquivos foram decodificados com o
libjxl (referência), com o `gen2brain/jxl` e com o `jxl-oxide`; os resultados estão em cada seção.

---

## 1. `jxl-oxide`: `UnexpectedEof` quando o stream modular global não tem canais

**Título sugerido:** `Multi-group modular ANS: UnexpectedEof when the global modular stream has no channels`

**O que acontece.** O `jxl-oxide` 0.12.6 lê o estado ANS de 32 bits no início de todo stream modular,
inclusive o global quando todos os canais têm largura ou altura 0 (imagens com mais de 256 px, cujos canais
ficam todos nos grupos). O `jxl-encoder` 0.3.1 não escreve esse estado nesse caso (encode lossless com
`effort` ≥ 3 em imagens de 512×512), e o decode falha com
`Frame(Modular(Decoder(Bitstream(Io(UnexpectedEof)))))`. O `djxl`/libjxl, o `jxl-rs` e o `gen2brain/jxl`
decodificam os arquivos bit a bit.

**Contorno atual.** `rust/vendor/jxl-modular/src/image.rs`, em `decode_inner`: se todos os canais do stream
têm largura ou altura 0, retorna sem ler o estado ANS (3 linhas).

**Ainda não confirmado.** Se a especificação (ISO/IEC 18181-1) exige o estado ANS num stream sem canais; as
duas implementações de referência se comportam como se não exigisse. É a quinta pendência da issue #19.

**Reprodução.** Imagens `harness/fixtures/corpus/{photo,screenshot,illustration,alpha}.pam`, lossless com
`jxl_encoder::LosslessConfig::new().with_effort(3..=8)`. O teste
`test_lossless_roundtrip_is_exact_on_multi_group_images` (`rust/src/codec/jxl.rs`) é o teste de regressão do guard do vendor.

**Efforts 8 a 10 no caminho com o guard (item 4 da #19).** O `effort` 8 decodifica bit a bit em todas as
imagens, no `jxl-oxide` e no libjxl. Os efforts 9 e 10 **não são problema do decoder**: ver a seção 3.

---

## 2. `jxl-oxide`: `UnexpectedEof` em JXL lossy com canal alpha em imagens de vários grupos

**Título sugerido:** `Lossy VarDCT frame with a modular alpha channel: UnexpectedEof parsing a local modular header (512x512)`

**O que acontece.** Um frame VarDCT com canal alpha extra (RGBA 512×512, mais de um grupo) gerado pelo
`jxl-encoder` (`LossyConfig`, distância 2.35, `effort` ≥ 3) falha em `render_frame` com
`Frame(Modular(Decoder(Bitstream(Io(UnexpectedEof)))))`. Instrumentando o `jxl-modular`: o primeiro
`MaConfig::parse` (global) termina bem e o segundo, de um **cabeçalho modular local** (grupo), falha em
`Decoder::parse` do tree decoder, antes de qualquer chamada a `decode_inner`, então o guard
da seção 1 não se aplica. Com `effort` JXL 1 e 2 o arquivo decodifica; a falha começa no 3.

O **libjxl** (via Pillow) e o **`gen2brain/jxl`** decodificam o mesmo arquivo como RGBA 512×512; portanto o
stream é válido.

**Arquivo:** [`data/jxl-oxide-lossy-alpha-multigroup.jxl`](data/jxl-oxide-lossy-alpha-multigroup.jxl) (10,8 KB;
RGBA gerado de `harness/fixtures/corpus/alpha.pam`, `distance = 2.35`, JXL `effort` 3).

**Reprodução no repositório:** `cargo test --release --test quality jxl_lossy_alpha_decode_defect_is_still_present`
(passa enquanto o defeito existir; quando falhar, o decoder foi corrigido e a exceção `known_decoder_defect`
em `rust/tests/quality.rs` deve ser removida).

---

## 3. `jxl-encoder`: streams inválidos em `effort` 9 e 10 (lossless) e em `GrayAlpha8`

**Título sugerido:** `Lossless efforts 9 and 10 write streams libjxl rejects; GrayAlpha8 lossless is undecodable`

**3a. Efforts 9 e 10.** `LosslessConfig::new().with_effort(9 | 10)` em imagens 512×512 grava arquivos que o
**libjxl recusa** com `Generic Error` (photo e screenshot em 9 e 10; illustration em 10) e que o `jxl-oxide`
recusa com `UnexpectedEof`; só `illustration` no effort 9 é válida. Em `alpha` (RGBA) o encode **não termina em
180 s** nos efforts 9 e 10. O `effort` 8 funciona em todas as imagens. Tempo de encode medido: 1 a 3 s no 8,
3 a 7 s no 9 e no 10 quando termina. O contrato do projeto limita o JXL a `effort` 7 por isso
(`test_contract_never_reaches_the_broken_encoder_efforts`).

**Arquivo:** [`data/jxl-encoder-effort9-screenshot.jxl`](data/jxl-encoder-effort9-screenshot.jxl) (3 KB, screenshot
512×512, lossless, `effort` 9): libjxl `Generic Error`, `jxl-oxide` `UnexpectedEof`.

**3b. `PixelLayout::GrayAlpha8` lossless.** O stream gerado é recusado por **três** decoders: `jxl-oxide`
(`Frame(Bitstream(NonZeroPadding))` nos efforts 1 e 2, `IncompleteFrame` do 3 em diante), `gen2brain/jxl`
(`invalid bitstream`) e, portanto, não serve como fixture. O mesmo conteúdo como `Rgba8` com R = G = B funciona.
`PixelLayout::Gray8` está correto.

**Arquivo:** [`data/jxl-encoder-gray-alpha-lossless.jxl`](data/jxl-encoder-gray-alpha-lossless.jxl) (55 bytes,
4×4, `GrayAlpha8`, `effort` 3, pixels `(g, 255 - g/2)` com `g = i*17`).

**3c. Saída em stderr.** O caminho de árvore do modular escreve `DIAG ...` com `eprintln!` incondicional
(`src/modular/section.rs`), em lossless com `effort` 7 do encoder.

Repositório: https://github.com/imazen/jxl-encoder · Decoder: https://github.com/tirr-c/jxl-oxide
