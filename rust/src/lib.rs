// rust/src/lib.rs
// Clippy mais novo sugere `as_chunks` no lugar de `chunks_exact`; o toolchain fixado em
// rust-toolchain.toml ainda não conhece o lint, e `unknown_lints` evita o aviso lá.
#![allow(unknown_lints)]
#![allow(clippy::chunks_exact_to_as_chunks)]

pub mod analyze;
pub mod codec;
pub mod limits;
pub mod pam;
