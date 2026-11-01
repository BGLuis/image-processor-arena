#include "params.hpp"

#include <algorithm>
#include <cctype>
#include <sstream>

namespace arena {

static const int EFFORT_STEP[10] = {0, 1, 1, 2, 3, 3, 4, 5, 5, 6};

int webp_method(int effort) {
    int e = std::clamp(effort, MIN_EFFORT, MAX_EFFORT);
    return EFFORT_STEP[e - MIN_EFFORT];
}

int jxl_effort(int effort) {
    int e = std::clamp(effort, MIN_EFFORT, MAX_EFFORT);
    return EFFORT_STEP[e - MIN_EFFORT] + 1;
}

double jxl_distance(int q) {
    double qd = static_cast<double>(std::clamp(q, MIN_Q, MAX_Q));
    if (qd >= 30.0) {
        return 0.1 + (100.0 - qd) * 0.09;
    }
    return (53.0 / 3000.0) * qd * qd - (23.0 / 20.0) * qd + 25.0;
}

int avif_speed(int effort) {
    int e = std::clamp(effort, MIN_EFFORT, MAX_EFFORT);
    return MAX_EFFORT + MIN_EFFORT - e;
}

int png_compression(int effort) {
    if (effort <= 2) return 1;
    if (effort <= 6) return 6;
    return 9;
}

std::string normalize_format(const std::string& fmt) {
    std::string s = fmt;
    // Lowercase
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return std::tolower(c); });
    // Trim leading '.' or spaces
    size_t start = s.find_first_not_of(" .\t\r\n");
    if (start != std::string::npos) {
        size_t end = s.find_last_not_of(" \t\r\n");
        s = s.substr(start, end - start + 1);
    } else {
        s.clear();
    }
    if (s == "jpg") s = "jpeg";
    return s;
}

static bool parse_int_bounded(const std::string& name, const std::string& raw, int def, int lo, int hi, int* out, std::string* err) {
    if (raw.empty()) {
        *out = def;
        return true;
    }
    try {
        size_t idx = 0;
        int val = std::stoi(raw, &idx);
        if (idx != raw.size() || val < lo || val > hi) {
            if (err) *err = name + " must be an integer in " + std::to_string(lo) + ".." + std::to_string(hi) + ", got \"" + raw + "\"";
            return false;
        }
        *out = val;
        return true;
    } catch (...) {
        if (err) *err = name + " must be an integer in " + std::to_string(lo) + ".." + std::to_string(hi) + ", got \"" + raw + "\"";
        return false;
    }
}

bool EncodeParams::parse(const std::string& fmt,
                         const std::string& mode_str,
                         const std::string& q_str,
                         const std::string& effort_str,
                         const std::string& impl_str,
                         EncodeParams* out,
                         std::string* err) {
    std::string norm_fmt = normalize_format(fmt);
    if (norm_fmt != "png" && norm_fmt != "jpeg" && norm_fmt != "webp" && norm_fmt != "avif" && norm_fmt != "jxl") {
        if (err) *err = "unsupported format: \"" + fmt + "\"";
        return false;
    }

    std::string norm_mode = mode_str;
    std::transform(norm_mode.begin(), norm_mode.end(), norm_mode.begin(), [](unsigned char c) { return std::tolower(c); });
    if (norm_mode.empty()) {
        norm_mode = "lossy";
    } else if (norm_mode != "lossy" && norm_mode != "lossless") {
        if (err) *err = "mode must be \"lossy\" or \"lossless\", got \"" + mode_str + "\"";
        return false;
    }

    if (norm_fmt == "avif" && norm_mode == "lossless") {
        if (err) *err = "avif lossless is not supported";
        return false;
    }

    int q_val = DEFAULT_Q;
    if (!parse_int_bounded("q", q_str, DEFAULT_Q, MIN_Q, MAX_Q, &q_val, err)) {
        return false;
    }

    int effort_val = DEFAULT_EFFORT;
    if (!parse_int_bounded("effort", effort_str, DEFAULT_EFFORT, MIN_EFFORT, MAX_EFFORT, &effort_val, err)) {
        return false;
    }

    out->format = norm_fmt;
    out->mode = norm_mode;
    out->q = q_val;
    out->effort = effort_val;
    out->impl = impl_str;
    return true;
}

} // namespace arena
