// rust/src/analyze/mod.rs
// Módulo de análise estatística e perceptual para op=analyze.

pub mod blurhash;
pub mod metrics;
pub mod phash;

pub use metrics::{
    analyze, Adequacy420, AlphaMetrics, AnalyzeResult, AspectRatio, BlockAlignment, BlockInfo,
    ColorVariance, DominantColor,
};

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pam::PamImage;
    use std::collections::HashMap;
    use std::fs;
    use std::path::PathBuf;

    fn get_fixtures_dir() -> PathBuf {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        manifest_dir.parent().unwrap().join("harness").join("fixtures")
    }

    #[test]
    fn test_ground_truth_all_fixtures() {
        let fixtures_dir = get_fixtures_dir();
        let gt_path = fixtures_dir.join("ground_truth.json");
        let synthetic_dir = fixtures_dir.join("synthetic");

        assert!(gt_path.exists(), "ground_truth.json não encontrado em {:?}", gt_path);
        let gt_content = fs::read_to_string(&gt_path).expect("Falha ao ler ground_truth.json");
        let ground_truth: HashMap<String, serde_json::Value> =
            serde_json::from_str(&gt_content).expect("Falha ao deserializar ground_truth.json");

        for (fname, expected) in ground_truth {
            let pam_path = synthetic_dir.join(&fname);
            assert!(pam_path.exists(), "Fixture não encontrada: {:?}", pam_path);

            let pam_bytes = fs::read(&pam_path).expect("Falha ao ler arquivo PAM");
            let pam = PamImage::parse(&pam_bytes).expect("Falha ao parsear PAM");

            let result = analyze(pam.width, pam.height, pam.depth, &pam.data);
            let actual_json = serde_json::to_value(&result).expect("Falha ao serializar resultado");

            // Validações exatas
            assert_eq!(
                actual_json["width"], expected["width"],
                "[{}] width divergente", fname
            );
            assert_eq!(
                actual_json["height"], expected["height"],
                "[{}] height divergente", fname
            );
            assert_eq!(
                actual_json["aspect_ratio"]["str"], expected["aspect_ratio"]["str"],
                "[{}] aspect_ratio.str divergente", fname
            );
            assert_eq!(
                actual_json["unique_colors"], expected["unique_colors"],
                "[{}] unique_colors divergente", fname
            );
            assert_eq!(
                actual_json["alpha"]["has_alpha"], expected["alpha"]["has_alpha"],
                "[{}] alpha.has_alpha divergente", fname
            );
            assert_eq!(
                actual_json["dominant_color"]["dominant_bin"],
                expected["dominant_color"]["dominant_bin"],
                "[{}] dominant_bin divergente", fname
            );
            assert_eq!(
                actual_json["dominant_color"]["dominant_rgb"],
                expected["dominant_color"]["dominant_rgb"],
                "[{}] dominant_rgb divergente", fname
            );
            assert_eq!(
                actual_json["phash"], expected["phash"],
                "[{}] phash divergente", fname
            );
            assert_eq!(
                actual_json["blurhash"], expected["blurhash"],
                "[{}] blurhash divergente", fname
            );

            // Validações de tolerância float
            let check_float = |path: &str, act: f64, exp: f64, eps: f64| {
                let diff = (act - exp).abs();
                assert!(
                    diff <= eps,
                    "[{}] {} divergente: obtido {}, esperado {}, diff={}, eps={}",
                    fname, path, act, exp, diff, eps
                );
            };

            check_float(
                "mean_y",
                actual_json["mean_y"].as_f64().unwrap(),
                expected["mean_y"].as_f64().unwrap(),
                1e-4,
            );
            check_float(
                "entropy_y",
                actual_json["entropy_y"].as_f64().unwrap(),
                expected["entropy_y"].as_f64().unwrap(),
                1e-4,
            );
            check_float(
                "entropy_residual_y",
                actual_json["entropy_residual_y"].as_f64().unwrap(),
                expected["entropy_residual_y"].as_f64().unwrap(),
                1e-4,
            );
            check_float(
                "spatial_information",
                actual_json["spatial_information"].as_f64().unwrap(),
                expected["spatial_information"].as_f64().unwrap(),
                1e-3,
            );
            check_float(
                "gradient_energy",
                actual_json["gradient_energy"].as_f64().unwrap(),
                expected["gradient_energy"].as_f64().unwrap(),
                1e-3,
            );
            check_float(
                "laplacian_variance",
                actual_json["laplacian_variance"].as_f64().unwrap(),
                expected["laplacian_variance"].as_f64().unwrap(),
                1e-3,
            );
            check_float(
                "color_variance.var_sum",
                actual_json["color_variance"]["var_sum"].as_f64().unwrap(),
                expected["color_variance"]["var_sum"].as_f64().unwrap(),
                1e-3,
            );
            check_float(
                "alpha.sparsity",
                actual_json["alpha"]["sparsity"].as_f64().unwrap(),
                expected["alpha"]["sparsity"].as_f64().unwrap(),
                1e-4,
            );
            check_float(
                "alpha.binarity",
                actual_json["alpha"]["binarity"].as_f64().unwrap(),
                expected["alpha"]["binarity"].as_f64().unwrap(),
                1e-4,
            );
            check_float(
                "adequacy_420.chroma_gradient_energy",
                actual_json["adequacy_420"]["chroma_gradient_energy"].as_f64().unwrap(),
                expected["adequacy_420"]["chroma_gradient_energy"].as_f64().unwrap(),
                1e-3,
            );
            check_float(
                "adequacy_420.mse_chroma",
                actual_json["adequacy_420"]["mse_chroma"].as_f64().unwrap(),
                expected["adequacy_420"]["mse_chroma"].as_f64().unwrap(),
                1e-3,
            );
            check_float(
                "flat_area",
                actual_json["flat_area"].as_f64().unwrap(),
                expected["flat_area"].as_f64().unwrap(),
                1e-4,
            );
        }
    }
}
