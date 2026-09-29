// rust/src/bin/batch.rs
// CLI de execução batch para a arena de processamento de imagens.

use arena_rust::analyze::analyze;
use arena_rust::codec::{self, EncodeParams, ImageFormat};
use arena_rust::pam::PamImage;
use clap::Parser;
use std::fs;
use std::io::{self, Read, Write};
use std::process;
use std::str::FromStr;

#[derive(Parser, Debug)]
#[command(name = "arena-batch", about = "CLI Batch da Arena de Processamento de Imagens")]
struct Args {
    #[arg(long)]
    op: String,

    #[arg(long)]
    format: Option<String>,

    #[arg(long)]
    to: Option<String>,

    #[arg(long)]
    mode: Option<String>,

    #[arg(long)]
    q: Option<String>,

    #[arg(long)]
    effort: Option<String>,

    #[arg(long)]
    input: String,

    #[arg(long)]
    output: Option<String>,
}

fn read_input(path: &str) -> io::Result<Vec<u8>> {
    if path == "-" {
        let mut buffer = Vec::new();
        io::stdin().read_to_end(&mut buffer)?;
        Ok(buffer)
    } else {
        fs::read(path)
    }
}

fn write_output(path: Option<&str>, data: &[u8]) -> io::Result<()> {
    match path {
        Some(p) if p != "-" => fs::write(p, data),
        _ => {
            io::stdout().write_all(data)?;
            io::stdout().flush()
        }
    }
}

fn main() {
    let args = Args::parse();
    let op = args.op.to_ascii_lowercase();

    let input_bytes = match read_input(&args.input) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("[-] Erro ao ler arquivo de entrada '{}': {}", args.input, e);
            process::exit(1);
        }
    };

    match op.as_str() {
        "analyze" => {
            let pam = match PamImage::parse(&input_bytes) {
                Ok(p) => p,
                Err(e) => {
                    eprintln!("[-] Erro ao parsear PAM: {e}");
                    process::exit(1);
                }
            };
            let result = analyze(pam.width, pam.height, pam.depth, &pam.data);
            let json_str = match serde_json::to_string(&result) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("[-] Erro ao serializar JSON: {e}");
                    process::exit(1);
                }
            };

            if let Some(out_path) = args.output.as_deref() {
                if out_path != "-" {
                    if let Err(e) = fs::write(out_path, json_str.as_bytes()) {
                        eprintln!("[-] Erro ao escrever saída em '{out_path}': {e}");
                        process::exit(1);
                    }
                    return;
                }
            }
            println!("{json_str}");
        }

        "encode" => {
            let format_str = args.format.expect("Argumento '--format' obrigatório para op=encode");
            let params = EncodeParams::parse(&format_str, args.mode.as_deref(), args.q.as_deref(), args.effort.as_deref())
                .unwrap_or_else(|e| {
                    eprintln!("[-] {e}");
                    process::exit(1);
                });

            let pam = match PamImage::parse(&input_bytes) {
                Ok(p) => p,
                Err(e) => {
                    eprintln!("[-] Erro ao parsear PAM: {e}");
                    process::exit(1);
                }
            };

            let encoded = match codec::encode(&pam, &params) {
                Ok(bytes) => bytes,
                Err(e) => {
                    eprintln!("[-] Erro encode: {e}");
                    process::exit(1);
                }
            };

            if let Err(e) = write_output(args.output.as_deref(), &encoded) {
                eprintln!("[-] Erro ao escrever saída: {e}");
                process::exit(1);
            }
        }

        "decode" => {
            let format_str = args.format.expect("Argumento '--format' obrigatório para op=decode");
            let format = ImageFormat::from_str(&format_str).unwrap_or_else(|e| {
                eprintln!("[-] {e}");
                process::exit(1);
            });

            let pam = match codec::decode(&input_bytes, format) {
                Ok(p) => p,
                Err(e) => {
                    eprintln!("[-] Erro decode: {e}");
                    process::exit(1);
                }
            };

            let pam_bytes = pam.encode();
            if let Err(e) = write_output(args.output.as_deref(), &pam_bytes) {
                eprintln!("[-] Erro ao escrever saída: {e}");
                process::exit(1);
            }
        }

        "transcode" => {
            let from_str = args.format.expect("Argumento '--format' (origem) obrigatório para op=transcode");
            let to_str = args.to.expect("Argumento '--to' (destino) obrigatório para op=transcode");

            let from_format = ImageFormat::from_str(&from_str).unwrap_or_else(|e| {
                eprintln!("[-] {e}");
                process::exit(1);
            });
            let params = EncodeParams::parse(&to_str, args.mode.as_deref(), args.q.as_deref(), args.effort.as_deref())
                .unwrap_or_else(|e| {
                    eprintln!("[-] {e}");
                    process::exit(1);
                });

            let (out_bytes, _dec_ns, _enc_ns) = match codec::transcode(&input_bytes, from_format, &params) {
                Ok(res) => res,
                Err(e) => {
                    eprintln!("[-] Erro transcode: {e}");
                    process::exit(1);
                }
            };

            if let Err(e) = write_output(args.output.as_deref(), &out_bytes) {
                eprintln!("[-] Erro ao escrever saída: {e}");
                process::exit(1);
            }
        }

        _ => {
            eprintln!("[-] Operação desconhecida: '{op}'. Esperado: analyze, encode, decode, transcode");
            process::exit(1);
        }
    }
}
