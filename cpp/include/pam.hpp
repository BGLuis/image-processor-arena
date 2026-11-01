#pragma once

#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>
#include <memory>

namespace arena {

class PamImage {
public:
    int width = 0;
    int height = 0;
    int depth = 0;       // 3 for RGB, 4 for RGB_ALPHA
    int maxval = 255;    // Fixed to 255
    std::string tupltype; // "RGB" or "RGB_ALPHA"
    std::vector<uint8_t> data; // row-major raster data (width * height * depth bytes)

    PamImage() = default;
    PamImage(int w, int h, int d, std::vector<uint8_t> pix, const std::string& type = "")
        : width(w), height(h), depth(d), maxval(255), tupltype(type.empty() ? (d == 4 ? "RGB_ALPHA" : "RGB") : type), data(std::move(pix)) {}

    static int get_max_pixels();
    static size_t get_max_body_bytes();

    static std::unique_ptr<PamImage> decode(const uint8_t* buffer, size_t size, int max_pixels = 0, std::string* err = nullptr);
    static std::unique_ptr<PamImage> from_file(const std::string& filepath, int max_pixels = 0, std::string* err = nullptr);

    std::vector<uint8_t> encode() const;
    bool to_file(const std::string& filepath, std::string* err = nullptr) const;

    std::vector<uint8_t> to_rgb_bytes() const;
    std::vector<uint8_t> to_rgba_bytes() const;
};

} // namespace arena
