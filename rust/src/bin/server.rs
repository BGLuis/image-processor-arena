// rust/src/bin/server.rs
// Servidor HTTP de alta performance para a arena de processamento de imagens.

use arena_rust::analyze::analyze;
use arena_rust::codec::{self, EncodeParams, ImageFormat};
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
    q: Option<String>,
    effort: Option<String>,
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
            let encode_params = EncodeParams::parse(
                &format_str,
                params.mode.as_deref(),
                params.q.as_deref(),
                params.effort.as_deref(),
            )
            .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
            let format = encode_params.format;

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
            let encode_params = EncodeParams::parse(
                &to_str,
                params.mode.as_deref(),
                params.q.as_deref(),
                params.effort.as_deref(),
            )
            .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
            let to_format = encode_params.format;

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

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::to_bytes;

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

    async fn encoded_bytes(q: RunQuery) -> Vec<u8> {
        let response = run_handler(Query(q), sample_pam())
            .await
            .expect("requisição válida");
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
            let encode = run_handler(
                Query(query("encode", "webp", &[(key, value)])),
                sample_pam(),
            )
            .await;
            assert_eq!(
                encode.unwrap_err().0,
                StatusCode::BAD_REQUEST,
                "encode {key}={value}"
            );

            let transcode = run_handler(
                Query(query("transcode", "png", &[("to", "webp"), (key, value)])),
                Bytes::from(png.clone()),
            )
            .await;
            assert_eq!(
                transcode.unwrap_err().0,
                StatusCode::BAD_REQUEST,
                "transcode {key}={value}"
            );
        }

        let unknown_format = run_handler(Query(query("encode", "bmp", &[])), sample_pam()).await;
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
}
