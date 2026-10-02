// rust/src/bin/server.rs
// Servidor HTTP de alta performance para a arena de processamento de imagens.

use arena_rust::analyze::analyze;
use arena_rust::codec::{self, CodecError, EncodeParams, ImageFormat};
use arena_rust::limits::{self, Limits};
use arena_rust::pam::{PamError, PamImage};
use axum::{
    body::Bytes,
    extract::{DefaultBodyLimit, Query, State},
    http::{header, HeaderMap, HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Router,
};
use serde::Deserialize;
use std::env;
use std::net::SocketAddr;
use std::process;
use std::str::FromStr;
use std::time::Instant;
use tokio::task::JoinError;

type HttpError = (StatusCode, String);

#[derive(Debug, Deserialize)]
struct RunQuery {
    op: String,
    format: Option<String>,
    to: Option<String>,
    mode: Option<String>,
    q: Option<String>,
    effort: Option<String>,
}

/// Requisição já conferida contra o contrato de parâmetros: nada inválido chega aos codecs.
enum Plan {
    Analyze,
    Encode(EncodeParams),
    Decode(ImageFormat),
    Transcode { from: ImageFormat, to: EncodeParams },
}

fn client_error(message: impl Into<String>) -> HttpError {
    (StatusCode::BAD_REQUEST, message.into())
}

fn plan(params: &RunQuery) -> Result<Plan, HttpError> {
    let op = params.op.to_ascii_lowercase();
    let mode = params.mode.as_deref();
    let q = params.q.as_deref();
    let effort = params.effort.as_deref();

    match op.as_str() {
        "analyze" => Ok(Plan::Analyze),

        "encode" => {
            let format = params
                .format
                .as_deref()
                .ok_or_else(|| client_error("Parâmetro 'format' obrigatório para op=encode"))?;
            let encode = EncodeParams::parse(format, mode, q, effort)
                .map_err(|e| client_error(e.to_string()))?;
            Ok(Plan::Encode(encode))
        }

        "decode" => {
            let format = params
                .format
                .as_deref()
                .ok_or_else(|| client_error("Parâmetro 'format' obrigatório para op=decode"))?;
            let format = ImageFormat::from_str(format).map_err(|e| client_error(e.to_string()))?;
            Ok(Plan::Decode(format))
        }

        "transcode" => {
            let from = params.format.as_deref().ok_or_else(|| {
                client_error("Parâmetro 'format' (origem) obrigatório para op=transcode")
            })?;
            let to = params.to.as_deref().ok_or_else(|| {
                client_error("Parâmetro 'to' (destino) obrigatório para op=transcode")
            })?;
            let from = ImageFormat::from_str(from).map_err(|e| client_error(e.to_string()))?;
            let to = EncodeParams::parse(to, mode, q, effort)
                .map_err(|e| client_error(e.to_string()))?;
            Ok(Plan::Transcode { from, to })
        }

        _ => Err(client_error(format!(
            "Operação desconhecida: '{op}'. Esperado: analyze, encode, decode, transcode"
        ))),
    }
}

fn pam_error(err: PamError) -> HttpError {
    client_error(format!("Erro de PAM: {err}"))
}

/// Formato, parâmetro, entrada fora do limite do formato e arquivo corrompido são erros do
/// cliente (400); só uma falha do próprio encoder vira 500.
fn codec_error(context: &str, err: CodecError) -> HttpError {
    let status = if err.is_client_error() {
        StatusCode::BAD_REQUEST
    } else {
        StatusCode::INTERNAL_SERVER_ERROR
    };
    (status, format!("{context}: {err}"))
}

/// Um panic dentro do `spawn_blocking` chega aqui como `JoinError`; o processo continua vivo
/// (o perfil release usa unwind) e o cliente recebe 500.
fn join_error(err: JoinError) -> HttpError {
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        format!("Falha interna ao processar a imagem: {err}"),
    )
}

fn response(
    content_type: &'static str,
    timings: &[(&'static str, u128)],
    body: Vec<u8>,
) -> Response {
    let mut headers = HeaderMap::new();
    headers.insert(header::CONTENT_TYPE, HeaderValue::from_static(content_type));
    for &(name, nanos) in timings {
        headers.insert(
            HeaderName::from_static(name),
            HeaderValue::from_str(&nanos.to_string()).expect("dígitos formam um header válido"),
        );
    }
    (headers, body).into_response()
}

pub fn build_app(limits: Limits) -> Router {
    Router::new()
        .route("/health", get(health_handler))
        .route("/run", post(run_handler))
        .layer(DefaultBodyLimit::max(limits.max_body_bytes))
        .with_state(limits)
}

#[tokio::main]
async fn main() {
    let limits = Limits::from_env().unwrap_or_else(|e| {
        eprintln!("[-] Configuração inválida: {e}");
        process::exit(2);
    });
    limits::set_max_pixels(limits.max_pixels);

    let port: u16 = env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8081);

    let app = build_app(limits);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    println!(
        "[*] Servidor Rust rodando em http://{} (corpo máx. {} B, máx. {} px)",
        addr, limits.max_body_bytes, limits.max_pixels
    );

    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("Falha ao vincular porta TCP");

    axum::serve(listener, app)
        .await
        .expect("Falha ao inicializar servidor HTTP");
}

async fn health_handler() -> impl IntoResponse {
    (
        [(header::CONTENT_TYPE, "application/json")],
        "{\"status\":\"ok\"}",
    )
}

async fn run_handler(
    State(limits): State<Limits>,
    Query(params): Query<RunQuery>,
    body: Bytes,
) -> Result<Response, HttpError> {
    let plan = plan(&params)?;
    if body.is_empty() {
        return Err(client_error("Corpo da requisição vazio"));
    }
    let max_pixels = limits.max_pixels;

    match plan {
        Plan::Analyze => {
            let (result_json, analyze_ns) = tokio::task::spawn_blocking(move || {
                let pam = PamImage::parse_with_limit(&body, max_pixels).map_err(pam_error)?;

                // O cronômetro cobre só a análise, como no servidor Go; o parse do PAM e a
                // serialização JSON ficam de fora nos dois.
                let t0 = Instant::now();
                let res = analyze(pam.width, pam.height, pam.depth, &pam.data);
                let elapsed = t0.elapsed().as_nanos();

                let json_str = serde_json::to_string(&res)
                    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("Erro JSON: {e}")))?;
                Ok::<_, HttpError>((json_str, elapsed))
            })
            .await
            .map_err(join_error)??;

            Ok(response(
                "application/json",
                &[("x-arena-analyze-ns", analyze_ns)],
                result_json.into_bytes(),
            ))
        }

        Plan::Encode(encode_params) => {
            let format = encode_params.format;
            let (out_bytes, encode_ns) = tokio::task::spawn_blocking(move || {
                let pam = PamImage::parse_with_limit(&body, max_pixels).map_err(pam_error)?;
                let t0 = Instant::now();
                let encoded = codec::encode(&pam, &encode_params)
                    .map_err(|e| codec_error("Erro encode", e))?;
                let elapsed = t0.elapsed().as_nanos();
                Ok::<_, HttpError>((encoded, elapsed))
            })
            .await
            .map_err(join_error)??;

            Ok(response(
                format.mime_type(),
                &[("x-arena-encode-ns", encode_ns)],
                out_bytes,
            ))
        }

        Plan::Decode(format) => {
            let (pam_bytes, decode_ns) = tokio::task::spawn_blocking(move || {
                let t0 = Instant::now();
                let pam =
                    codec::decode(&body, format).map_err(|e| codec_error("Erro decode", e))?;
                let elapsed = t0.elapsed().as_nanos();
                Ok::<_, HttpError>((pam.encode(), elapsed))
            })
            .await
            .map_err(join_error)??;

            Ok(response(
                "image/x-netpbm-pam",
                &[("x-arena-decode-ns", decode_ns)],
                pam_bytes,
            ))
        }

        Plan::Transcode { from, to } => {
            let to_format = to.format;
            let (out_bytes, decode_ns, encode_ns) = tokio::task::spawn_blocking(move || {
                codec::transcode(&body, from, &to).map_err(|e| codec_error("Erro transcode", e))
            })
            .await
            .map_err(join_error)??;

            Ok(response(
                to_format.mime_type(),
                &[
                    ("x-arena-decode-ns", decode_ns),
                    ("x-arena-encode-ns", encode_ns),
                ],
                out_bytes,
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::to_bytes;
    use std::net::SocketAddr;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::{TcpListener, TcpStream};

    fn sample_pam() -> Bytes {
        let data: Vec<u8> = (0..32 * 32 * 3).map(|i| (i % 251) as u8).collect();
        Bytes::from(PamImage::new_rgb(32, 32, data).unwrap().encode())
    }

    fn query(op: &str, format: &str, extra: &[(&str, &str)]) -> RunQuery {
        let mut q = RunQuery {
            op: op.to_string(),
            format: Some(format.to_string()),
            to: None,
            mode: None,
            q: None,
            effort: None,
        };
        for (key, value) in extra {
            let value = Some(value.to_string());
            match *key {
                "to" => q.to = value,
                "mode" => q.mode = value,
                "q" => q.q = value,
                "effort" => q.effort = value,
                other => panic!("chave desconhecida: {other}"),
            }
        }
        q
    }

    async fn run(q: RunQuery, body: Bytes) -> Result<Response, HttpError> {
        run_handler(State(Limits::default()), Query(q), body).await
    }

    async fn encoded_bytes(q: RunQuery) -> Vec<u8> {
        let response = run(q, sample_pam()).await.expect("requisição válida");
        to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap()
            .to_vec()
    }

    #[tokio::test]
    async fn rejects_params_outside_the_contract() {
        let bad_params = [
            ("q", "0"),
            ("q", "101"),
            ("q", "300"),
            ("q", "-1"),
            ("q", "abc"),
            ("effort", "0"),
            ("effort", "11"),
            ("effort", "fast"),
            ("mode", "near-lossless"),
        ];
        let png = encoded_bytes(query("encode", "png", &[])).await;
        for (key, value) in bad_params {
            let encode = run(query("encode", "webp", &[(key, value)]), sample_pam()).await;
            assert_eq!(
                encode.unwrap_err().0,
                StatusCode::BAD_REQUEST,
                "encode {key}={value}"
            );

            let transcode = run(
                query("transcode", "png", &[("to", "webp"), (key, value)]),
                Bytes::from(png.clone()),
            )
            .await;
            assert_eq!(
                transcode.unwrap_err().0,
                StatusCode::BAD_REQUEST,
                "transcode {key}={value}"
            );
        }

        let unknown_format = run(query("encode", "bmp", &[]), sample_pam()).await;
        assert_eq!(unknown_format.unwrap_err().0, StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn omitted_params_behave_as_the_contract_defaults() {
        for format in ["png", "jpeg", "webp", "jxl"] {
            let implicit = encoded_bytes(query("encode", format, &[])).await;
            let explicit = encoded_bytes(query(
                "encode",
                format,
                &[("mode", "lossy"), ("q", "75"), ("effort", "4")],
            ))
            .await;
            assert_eq!(implicit, explicit, "{format}");
        }
    }

    #[tokio::test]
    async fn empty_params_select_defaults() {
        let implicit = encoded_bytes(query("encode", "webp", &[])).await;
        let empty = encoded_bytes(query(
            "encode",
            "webp",
            &[("mode", ""), ("q", ""), ("effort", "")],
        ))
        .await;
        assert_eq!(implicit, empty);
    }

    #[tokio::test]
    async fn client_errors_are_never_500() {
        let png = encoded_bytes(query("encode", "png", &[])).await;
        let cases = [
            (
                "avif lossless encode",
                query("encode", "avif", &[("mode", "lossless")]),
                sample_pam(),
            ),
            (
                "avif lossless transcode",
                query("transcode", "png", &[("to", "avif"), ("mode", "lossless")]),
                Bytes::from(png.clone()),
            ),
            (
                "unknown decode format",
                query("decode", "bmp", &[]),
                Bytes::from(png.clone()),
            ),
            (
                "unknown transcode source",
                query("transcode", "bmp", &[("to", "png")]),
                Bytes::from(png.clone()),
            ),
            (
                "corrupt png in transcode",
                query("transcode", "png", &[("to", "webp")]),
                Bytes::from_static(b"not a png"),
            ),
            (
                "corrupt png in decode",
                query("decode", "png", &[]),
                Bytes::from_static(b"not a png"),
            ),
            ("unknown op", query("resize", "png", &[]), sample_pam()),
            ("empty body", query("analyze", "png", &[]), Bytes::new()),
        ];
        for (name, q, body) in cases {
            let err = run(q, body).await.unwrap_err();
            assert_eq!(err.0, StatusCode::BAD_REQUEST, "{name}: {}", err.1);
        }
    }

    #[tokio::test]
    async fn analyze_times_only_the_analysis() {
        let response = run(query("analyze", "png", &[]), sample_pam())
            .await
            .expect("requisição válida");
        let ns = response
            .headers()
            .get("x-arena-analyze-ns")
            .expect("header de tempo")
            .to_str()
            .unwrap()
            .parse::<u128>()
            .unwrap();
        assert!(ns > 0);
    }

    async fn serve(limits: Limits) -> SocketAddr {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            axum::serve(listener, build_app(limits)).await.unwrap();
        });
        addr
    }

    /// Requisição HTTP/1.1 crua: devolve o status e o corpo da resposta.
    async fn http(addr: SocketAddr, method: &str, target: &str, body: &[u8]) -> (u16, String) {
        let mut stream = TcpStream::connect(addr).await.unwrap();
        let head = format!(
            "{method} {target} HTTP/1.1\r\nHost: arena\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
            body.len()
        );
        stream.write_all(head.as_bytes()).await.unwrap();
        // O servidor pode responder (413) e fechar antes de consumir o corpo inteiro.
        let _ = stream.write_all(body).await;
        let mut raw = Vec::new();
        let _ = stream.read_to_end(&mut raw).await;

        let text = String::from_utf8_lossy(&raw).into_owned();
        let status = text
            .split_whitespace()
            .nth(1)
            .and_then(|s| s.parse().ok())
            .unwrap_or_else(|| panic!("resposta HTTP inválida: {text:?}"));
        let body = text.split_once("\r\n\r\n").map(|(_, b)| b).unwrap_or("");
        (status, body.to_string())
    }

    async fn assert_alive(addr: SocketAddr) {
        let (status, body) = http(addr, "GET", "/health", b"").await;
        assert_eq!((status, body.as_str()), (200, "{\"status\":\"ok\"}"));
    }

    fn rgb_pam(width: u32, height: u32) -> Vec<u8> {
        let data = vec![7u8; (width * height * 3) as usize];
        PamImage::new_rgb(width, height, data).unwrap().encode()
    }

    #[tokio::test]
    async fn jpeg_wider_than_65535_is_a_client_error_and_the_process_survives() {
        let addr = serve(Limits::default()).await;

        let (status, body) = http(
            addr,
            "POST",
            "/run?op=encode&format=jpeg",
            &rgb_pam(70_000, 1),
        )
        .await;
        assert_eq!(status, 400, "{body}");

        let (status, body) = http(
            addr,
            "POST",
            "/run?op=transcode&format=png&to=jpeg",
            b"not a png",
        )
        .await;
        assert_eq!(status, 400, "{body}");

        assert_alive(addr).await;
    }

    #[tokio::test]
    async fn webp_wider_than_16383_is_a_client_error() {
        let addr = serve(Limits::default()).await;
        for mode in ["lossy", "lossless"] {
            let target = format!("/run?op=encode&format=webp&mode={mode}");
            let (status, body) = http(addr, "POST", &target, &rgb_pam(16_384, 1)).await;
            assert_eq!(status, 400, "{mode}: {body}");
        }
        assert_alive(addr).await;
    }

    #[tokio::test]
    async fn pam_with_extreme_dimensions_is_refused_and_the_process_survives() {
        let addr = serve(Limits::default()).await;

        for (width, height) in [
            (100_000u64, 100_000u64),
            (u32::MAX as u64, u32::MAX as u64),
            (u32::MAX as u64, 1),
        ] {
            let pam = format!(
                "P7\nWIDTH {width}\nHEIGHT {height}\nDEPTH 4\nMAXVAL 255\nTUPLTYPE RGB_ALPHA\nENDHDR\n"
            );
            for op in ["analyze", "encode&format=png", "encode&format=jpeg"] {
                let (status, body) =
                    http(addr, "POST", &format!("/run?op={op}"), pam.as_bytes()).await;
                assert_eq!(status, 400, "{op} {width}x{height}: {body}");
            }
        }

        assert_alive(addr).await;
    }

    #[tokio::test]
    async fn body_above_the_limit_is_413_and_the_limit_is_inclusive() {
        let pam = rgb_pam(16, 16);
        let addr = serve(Limits {
            max_body_bytes: pam.len(),
            ..Limits::default()
        })
        .await;

        let (status, body) = http(addr, "POST", "/run?op=analyze", &pam).await;
        assert_eq!(status, 200, "{body}");

        let too_big = rgb_pam(32, 32);
        let (status, _) = http(addr, "POST", "/run?op=analyze", &too_big).await;
        assert_eq!(status, 413);

        assert_alive(addr).await;
    }

    #[tokio::test]
    async fn pixel_limit_applies_to_the_pam_body() {
        let addr = serve(Limits {
            max_pixels: 16 * 16 - 1,
            ..Limits::default()
        })
        .await;
        let (status, body) = http(addr, "POST", "/run?op=analyze", &rgb_pam(16, 16)).await;
        assert_eq!(status, 400, "{body}");
    }
}
