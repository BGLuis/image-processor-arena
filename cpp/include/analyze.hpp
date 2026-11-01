#pragma once

#include "pam.hpp"
#include <string>

namespace arena {

struct BlockInfo {
    int w_mod = 0;
    int h_mod = 0;
    int partial_pixels = 0;
    double partial_pct = 0.0;
};

struct BlockAlignment {
    BlockInfo b8;
    BlockInfo b16;
    BlockInfo b64;
    BlockInfo b256;
};

struct ColorVariance {
    double var_r = 0.0;
    double var_g = 0.0;
    double var_b = 0.0;
    double var_sum = 0.0;
};

struct AlphaMetrics {
    bool has_alpha = false;
    double sparsity = 0.0;
    double binarity = 1.0;
};

struct Adequacy420 {
    double chroma_gradient_energy = 0.0;
    double chroma_gradient_ratio = 0.0;
    double mse_cb = 0.0;
    double mse_cr = 0.0;
    double mse_chroma = 0.0;
};

struct DominantColor {
    int dominant_rgb[3] = {0, 0, 0};
    int dominant_bin = 0;
    double mean_rgb[3] = {0.0, 0.0, 0.0};
};

struct AspectRatio {
    std::string str;
    double val = 0.0;
};

struct AnalyzeResult {
    int width = 0;
    int height = 0;
    AspectRatio aspect_ratio;
    BlockAlignment block_alignment;
    double mean_y = 0.0;
    double entropy_y = 0.0;
    double entropy_residual_y = 0.0;
    double spatial_information = 0.0;
    double gradient_energy = 0.0;
    double laplacian_variance = 0.0;
    ColorVariance color_variance;
    int unique_colors = 0;
    AlphaMetrics alpha;
    Adequacy420 adequacy_420;
    double flat_area = 0.0;
    DominantColor dominant_color;
    std::string phash;
    std::string blurhash;

    std::string to_json(bool pretty = true) const;
};

AnalyzeResult analyze_image(const PamImage& img);

std::string compute_phash(const std::vector<uint8_t>& y_pixels, int width, int height);
std::string compute_blurhash(const std::vector<uint8_t>& r_pixels,
                             const std::vector<uint8_t>& g_pixels,
                             const std::vector<uint8_t>& b_pixels,
                             int width, int height,
                             int x_comp = 4, int y_comp = 3);

} // namespace arena
