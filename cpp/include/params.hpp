#pragma once

#include <string>
#include <vector>

namespace arena {

constexpr int DEFAULT_Q = 75;
constexpr int MIN_Q = 1;
constexpr int MAX_Q = 100;

constexpr int DEFAULT_EFFORT = 4;
constexpr int MIN_EFFORT = 1;
constexpr int MAX_EFFORT = 10;

constexpr int JPEG_MAX_SIDE = 65535;
constexpr int WEBP_MAX_SIDE = 16383;

struct EncodeParams {
    std::string format;
    std::string mode = "lossy";
    int q = DEFAULT_Q;
    int effort = DEFAULT_EFFORT;
    std::string impl;

    static bool parse(const std::string& fmt,
                      const std::string& mode_str,
                      const std::string& q_str,
                      const std::string& effort_str,
                      const std::string& impl_str,
                      EncodeParams* out,
                      std::string* err = nullptr);
};

std::string normalize_format(const std::string& fmt);

int webp_method(int effort);
int jxl_effort(int effort);
double jxl_distance(int q);
int avif_speed(int effort);
int png_compression(int effort);

} // namespace arena
