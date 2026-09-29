// rust/src/bin/server.rs
// Servidor HTTP de alta performance para a arena de processamento de imagens.

use arena_rust::analyze::analyze;
use arena_rust::codec::{self, CodecMode, EncodeParams, ImageFormat};
use arena_rust::pam::PamImage;
use axum::{
    body::Bytes,
    extract::Query,
    http::{header, HeaderMap, HeaderName, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::{get, post},
    Router,
};
use serde::Deserialize;
use std::env;
use std::net::SocketAddr;
use std::str::FromStr;
use std::time::Instant;

#[derive(Debug, Deserialize)]
struct RunQuery {
    op: String,
    format: Option<String>,
    to: Option<String>,
    mode: Option<String>,
    q: Option<u8>,
    effort: Option<u8>,
}

#[tokio::main]
async fn main() {
    let port: u16 = env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8081);

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/run", post(run_handler));

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    println!("[*] Servidor Rust rodando em http://{}", addr);

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
    Query(params): Query<RunQuery>,
    body: Bytes,
) -> Result<Response, (StatusCode, String)> {
    let op = params.op.to_ascii_lowercase();

    match op.as_str() {
        "analyze" => {
            let t0 = Instant::now();
            let body_bytes = body.to_vec();

            let (result_json, analyze_ns) = tokio::task::spawn_blocking(move || {
                let pam = PamImage::parse(&body_bytes)
                    .map_err(|e| (StatusCode::BAD_REQUEST, format!("Erro de PAM: {e}")))?;
                let res = analyze(pam.width, pam.height, pam.depth, &pam.data);
                let json_str = serde_json::to_string(&res)
                    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("Erro JSON: {e}")))?;
                let elapsed = t0.elapsed().as_nanos();
                Ok::<_, (StatusCode, String)>((json_str, elapsed))
            })
            .await
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))??;

            let mut headers = HeaderMap::new();
            headers.insert(
                header::CONTENT_TYPE,
                HeaderValue::from_static("application/json"),
            );
            headers.insert(
                HeaderName::from_static("x-arena-analyze-ns"),
                HeaderValue::from_str(&analyze_ns.to_string()).unwrap(),
            );

            Ok((headers, result_json).into_response())
        }

        "encode" => {
            let format_str = params.format.ok_or_else(|| {
                (
                    StatusCode::BAD_REQUEST,
                    "Parâmetro 'format' obrigatório para op=encode".to_string(),
                )
            })?;
            let format = ImageFormat::from_str(&format_str)
                .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;

            let mode = match params.mode.as_deref() {
                Some(m) => {
                    CodecMode::from_str(m).map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?
                }
                None => CodecMode::Lossy,
            };

            let quality = params.q.unwrap_or(75);
            let effort = params.effort.unwrap_or(4);
            let encode_params = EncodeParams {
                format,
                mode,
                quality,
                effort,
            };

            let body_bytes = body.to_vec();
            let (out_bytes, encode_ns) = tokio::task::spawn_blocking(move || {
                let pam = PamImage::parse(&body_bytes)
                    .map_err(|e| (StatusCode::BAD_REQUEST, format!("Erro de PAM: {e}")))?;
                let t0 = Instant::now();
                let encoded = codec::encode(&pam, &encode_params).map_err(|e| {
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        format!("Erro encode: {e}"),
                    )
                })?;
                let elapsed = t0.elapsed().as_nanos();
                Ok::<_, (StatusCode, String)>((encoded, elapsed))
            })
            .await
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))??;

            let mut headers = HeaderMap::new();
            headers.insert(
                header::CONTENT_TYPE,
                HeaderValue::from_static(format.mime_type()),
            );
            headers.insert(
                HeaderName::from_static("x-arena-encode-ns"),
                HeaderValue::from_str(&encode_ns.to_string()).unwrap(),
            );

            Ok((headers, out_bytes).into_response())
        }

        "decode" => {
            let format_str = params.format.ok_or_else(|| {
                (
                    StatusCode::BAD_REQUEST,
                    "Parâmetro 'format' obrigatório para op=decode".to_string(),
                )
            })?;
            let format = ImageFormat::from_str(&format_str)
                .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;

            let body_bytes = body.to_vec();
            let (pam_bytes, decode_ns) = tokio::task::spawn_blocking(move || {
                let t0 = Instant::now();
                let pam = codec::decode(&body_bytes, format)
                    .map_err(|e| (StatusCode::BAD_REQUEST, format!("Erro decode: {e}")))?;
                let elapsed = t0.elapsed().as_nanos();
                Ok::<_, (StatusCode, String)>((pam.encode(), elapsed))
            })
            .await
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))??;

            let mut headers = HeaderMap::new();
            headers.insert(
                header::CONTENT_TYPE,
                HeaderValue::from_static("image/x-netpbm-pam"),
            );
            headers.insert(
                HeaderName::from_static("x-arena-decode-ns"),
                HeaderValue::from_str(&decode_ns.to_string()).unwrap(),
            );

            Ok((headers, pam_bytes).into_response())
        }

        "transcode" => {
            let from_str = params.format.ok_or_else(|| {
                (
                    StatusCode::BAD_REQUEST,
                    "Parâmetro 'format' (origem) obrigatório para op=transcode".to_string(),
                )
            })?;
            let to_str = params.to.ok_or_else(|| {
                (
                    StatusCode::BAD_REQUEST,
                    "Parâmetro 'to' (destino) obrigatório para op=transcode".to_string(),
                )
            })?;

            let from_format = ImageFormat::from_str(&from_str)
                .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
            let to_format = ImageFormat::from_str(&to_str)
                .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;

            let mode = match params.mode.as_deref() {
                Some(m) => {
                    CodecMode::from_str(m).map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?
                }
                None => CodecMode::Lossy,
            };

            let quality = params.q.unwrap_or(75);
            let effort = params.effort.unwrap_or(4);
            let encode_params = EncodeParams {
                format: to_format,
                mode,
                quality,
                effort,
            };

            let body_bytes = body.to_vec();
            let (out_bytes, decode_ns, encode_ns) = tokio::task::spawn_blocking(move || {
                codec::transcode(&body_bytes, from_format, &encode_params).map_err(|e| {
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        format!("Erro transcode: {e}"),
                    )
                })
            })
            .await
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))??;

            let mut headers = HeaderMap::new();
            headers.insert(
                header::CONTENT_TYPE,
                HeaderValue::from_static(to_format.mime_type()),
            );
            headers.insert(
                HeaderName::from_static("x-arena-decode-ns"),
                HeaderValue::from_str(&decode_ns.to_string()).unwrap(),
            );
            headers.insert(
                HeaderName::from_static("x-arena-encode-ns"),
                HeaderValue::from_str(&encode_ns.to_string()).unwrap(),
            );

            Ok((headers, out_bytes).into_response())
        }

        _ => Err((
            StatusCode::BAD_REQUEST,
            format!("Operação desconhecida: '{op}'. Esperado: analyze, encode, decode, transcode"),
        )),
    }
}
