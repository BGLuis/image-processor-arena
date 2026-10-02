// rust/tests/quality.rs
// Round-trip sobre as imagens do corpus, com os mesmos critérios do engine Go
// (go/internal/codec/quality_test.go): lossless exato e PSNR mínimo nos formatos lossy.

use arena_rust::codec::{self, CodecMode, EncodeParams, ImageFormat};
use arena_rust::pam::PamImage;
use std::path::PathBuf;

const CORPUS: [&str; 4] = ["photo", "screenshot", "illustration", "alpha"];

/// PSNR RGB mínimo em q=75, effort=4. No corpus os piores valores medidos são ~38 dB para photo
/// e ~29 dB para as outras classes em qualquer engine; os pisos deixam 2-3 dB de folga para
/// atualizações das bibliotecas e ainda reprovam um encoder que grava a imagem errada.
fn min_psnr(name: &str) -> f64 {
    if name == "photo" {
        35.0
    } else {
        27.0
    }
}

/// jxl-oxide 0.12.6 (mesmo com o guard de rust/vendor/jxl-modular) não decodifica JXL lossy com
/// canal alpha em imagens de vários grupos (> 256 px) a partir de JXL effort 2, embora o libjxl e
/// o gen2brain/jxl decodifiquem o mesmo arquivo. O caso fica fora da checagem de PSNR abaixo e o
/// teste `jxl_lossy_alpha_decode_defect_is_still_present` avisa quando o upstream corrigir.
fn known_decoder_defect(format: ImageFormat, name: &str) -> bool {
    format == ImageFormat::Jxl && name == "alpha"
}

fn load(name: &str) -> PamImage {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("harness/fixtures/corpus")
        .join(format!("{name}.pam"));
    let bytes = std::fs::read(&path).unwrap_or_else(|e| panic!("{path:?}: {e}"));
    PamImage::parse(&bytes).expect("PAM do corpus")
}

fn params(format: ImageFormat, mode: CodecMode, quality: u8) -> EncodeParams {
    EncodeParams {
        format,
        mode,
        quality,
        effort: 4,
    }
}

/// PSNR RGB sobre os pixels totalmente opacos do original; um encoder pode mudar a cor sob a
/// transparência. Imagens idênticas dão infinito.
fn rgb_psnr(want: &PamImage, got: &PamImage) -> f64 {
    let (wd, gd) = (want.depth as usize, got.depth as usize);
    let (mut sum, mut n) = (0.0f64, 0usize);
    for i in 0..want.pixel_count() {
        if wd == 4 && want.data[i * 4 + 3] != 255 {
            continue;
        }
        for c in 0..3 {
            let d = f64::from(want.data[i * wd + c]) - f64::from(got.data[i * gd + c]);
            sum += d * d;
            n += 1;
        }
    }
    if sum == 0.0 || n == 0 {
        f64::INFINITY
    } else {
        10.0 * (255.0 * 255.0 / (sum / n as f64)).log10()
    }
}

/// Canais RGB (e alpha, quando os dois lados têm) que diferem; depth 4 com alpha opaco pode
/// voltar como depth 3.
fn channel_diffs(want: &PamImage, got: &PamImage) -> usize {
    assert_eq!((want.width, want.height), (got.width, got.height));
    let (wd, gd) = (want.depth as usize, got.depth as usize);
    let mut diffs = 0;
    for i in 0..want.pixel_count() {
        for c in 0..3 {
            diffs += usize::from(want.data[i * wd + c] != got.data[i * gd + c]);
        }
        let wa = if wd == 4 { want.data[i * 4 + 3] } else { 255 };
        let ga = if gd == 4 { got.data[i * 4 + 3] } else { 255 };
        diffs += usize::from(wa != ga);
    }
    diffs
}

fn roundtrip(img: &PamImage, p: &EncodeParams) -> (Vec<u8>, PamImage) {
    let encoded = codec::encode(img, p).unwrap_or_else(|e| panic!("{:?}: {e}", p.format));
    let decoded =
        codec::decode(&encoded, p.format).unwrap_or_else(|e| panic!("{:?}: {e}", p.format));
    assert_eq!(
        (decoded.width, decoded.height),
        (img.width, img.height),
        "{:?}",
        p.format
    );
    (encoded, decoded)
}

#[test]
fn lossless_roundtrip_is_pixel_exact_on_the_corpus() {
    for format in [ImageFormat::Png, ImageFormat::Webp, ImageFormat::Jxl] {
        for name in CORPUS {
            let img = load(name);
            let (_, decoded) = roundtrip(&img, &params(format, CodecMode::Lossless, 100));
            assert_eq!(
                channel_diffs(&img, &decoded),
                0,
                "{format:?} lossless divergiu em {name}"
            );
        }
    }
}

#[test]
fn lossy_roundtrip_meets_the_psnr_floor_on_the_corpus() {
    for format in [
        ImageFormat::Jpeg,
        ImageFormat::Webp,
        ImageFormat::Avif,
        ImageFormat::Jxl,
    ] {
        for name in CORPUS {
            if known_decoder_defect(format, name) {
                continue;
            }
            let img = load(name);
            let (_, decoded) = roundtrip(&img, &params(format, CodecMode::Lossy, 75));

            let psnr = rgb_psnr(&img, &decoded);
            assert!(
                psnr >= min_psnr(name),
                "{format:?} {name}: PSNR {psnr:.2} dB abaixo do piso de {} dB",
                min_psnr(name)
            );

            // JPEG não tem alpha; todo outro formato lossy deve preservá-lo.
            let want_depth = if name != "alpha" || format == ImageFormat::Jpeg {
                3
            } else {
                4
            };
            assert_eq!(decoded.depth, want_depth, "{format:?} {name}: depth");
        }
    }
}

/// Um parâmetro de qualidade ignorado ou invertido é um defeito silencioso do benchmark:
/// tamanho e PSNR precisam crescer com q.
#[test]
fn lossy_quality_grows_with_q() {
    let img = load("photo");
    for format in [
        ImageFormat::Jpeg,
        ImageFormat::Webp,
        ImageFormat::Avif,
        ImageFormat::Jxl,
    ] {
        let (low_bytes, low) = roundtrip(&img, &params(format, CodecMode::Lossy, 30));
        let (high_bytes, high) = roundtrip(&img, &params(format, CodecMode::Lossy, 90));
        let (low_psnr, high_psnr) = (rgb_psnr(&img, &low), rgb_psnr(&img, &high));
        assert!(
            high_psnr >= low_psnr + 3.0,
            "{format:?}: PSNR q=90 {high_psnr:.2} dB não passa q=30 {low_psnr:.2} dB em 3 dB"
        );
        assert!(
            high_bytes.len() > low_bytes.len(),
            "{format:?}: q=90 gravou {} B e q=30 gravou {} B",
            high_bytes.len(),
            low_bytes.len()
        );
    }
}

/// Canário do defeito do jxl-oxide descrito em `known_decoder_defect`. Se este teste falhar, o
/// decoder foi corrigido: remova a exceção e este teste (e veja a issue de remoção do vendor).
#[test]
fn jxl_lossy_alpha_decode_defect_is_still_present() {
    let img = load("alpha");
    let p = params(ImageFormat::Jxl, CodecMode::Lossy, 75);
    let encoded = codec::encode(&img, &p).expect("o encode funciona");
    assert!(
        codec::decode(&encoded, ImageFormat::Jxl).is_err(),
        "jxl-oxide passou a decodificar JXL lossy com alpha: remova known_decoder_defect"
    );
}
