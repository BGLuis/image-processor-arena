#include "pam.hpp"

#include <cstdlib>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>

namespace arena {

int PamImage::get_max_pixels() {
    const char* env = std::getenv("ARENA_MAX_PIXELS");
    if (env && *env) {
        int v = std::atoi(env);
        if (v > 0) return v;
    }
    return 40000000;
}

size_t PamImage::get_max_body_bytes() {
    const char* env = std::getenv("ARENA_MAX_BODY_BYTES");
    if (env && *env) {
        long long v = std::atoll(env);
        if (v > 0) return static_cast<size_t>(v);
    }
    return 268435456ULL; // 256 MiB
}

static std::string trim(const std::string& s) {
    auto start = std::find_if_not(s.begin(), s.end(), [](unsigned char ch) { return std::isspace(ch); });
    auto end = std::find_if_not(s.rbegin(), s.rend(), [](unsigned char ch) { return std::isspace(ch); }).base();
    return (start < end) ? std::string(start, end) : std::string();
}

std::unique_ptr<PamImage> PamImage::decode(const uint8_t* buffer, size_t size, int max_pixels, std::string* err) {
    if (max_pixels <= 0) max_pixels = get_max_pixels();

    if (!buffer || size < 8) {
        if (err) *err = "pam: invalid or empty buffer";
        return nullptr;
    }

    // Must start with "P7\n" or "P7\r\n"
    if (buffer[0] != 'P' || buffer[1] != '7') {
        if (err) *err = "pam: not a P7 file";
        return nullptr;
    }

    size_t pos = 2;
    int w = 0, h = 0, d = 0, maxv = 0;
    std::string tupl;
    bool found_end = false;

    // Parse ASCII header
    while (pos < size && !found_end) {
        // Skip whitespace/newlines
        while (pos < size && (buffer[pos] == '\r' || buffer[pos] == '\n')) {
            pos++;
        }
        if (pos >= size) break;

        // Read line
        size_t line_start = pos;
        while (pos < size && buffer[pos] != '\n') {
            pos++;
        }
        size_t line_end = pos;
        if (pos < size && buffer[pos] == '\n') {
            pos++;
        }

        std::string line(reinterpret_cast<const char*>(buffer + line_start), line_end - line_start);
        line = trim(line);
        if (line.empty() || line[0] == '#') continue;

        if (line == "ENDHDR") {
            found_end = true;
            break;
        }

        std::istringstream iss(line);
        std::string token;
        if (!(iss >> token)) continue;

        if (token == "WIDTH") {
            iss >> w;
        } else if (token == "HEIGHT") {
            iss >> h;
        } else if (token == "DEPTH") {
            iss >> d;
        } else if (token == "MAXVAL") {
            iss >> maxv;
        } else if (token == "TUPLTYPE") {
            iss >> tupl;
        }
    }

    if (!found_end) {
        if (err) *err = "pam: missing ENDHDR";
        return nullptr;
    }

    if (w <= 0 || h <= 0) {
        if (err) *err = "pam: missing or invalid dimensions";
        return nullptr;
    }
    if (maxv != 255) {
        if (err) *err = "pam: maxval=" + std::to_string(maxv) + " (only 255 supported)";
        return nullptr;
    }
    if (d != 3 && d != 4) {
        if (err) *err = "pam: depth=" + std::to_string(d) + " (only 3 or 4 supported)";
        return nullptr;
    }
    if (tupl.empty()) {
        tupl = (d == 4) ? "RGB_ALPHA" : "RGB";
    }

    // Bounds check against max_pixels: w > max_pixels / h avoids int overflow
    if (w > max_pixels / h) {
        if (err) *err = "pam: dimensions " + std::to_string(w) + "x" + std::to_string(h) + " exceed limit of " + std::to_string(max_pixels) + " pixels";
        return nullptr;
    }

    size_t expected_bytes = static_cast<size_t>(w) * static_cast<size_t>(h) * static_cast<size_t>(d);
    size_t available_bytes = size - pos;
    if (available_bytes < expected_bytes) {
        if (err) *err = "pam: truncated pixel data (available " + std::to_string(available_bytes) + ", expected " + std::to_string(expected_bytes) + ")";
        return nullptr;
    }

    std::vector<uint8_t> pix(buffer + pos, buffer + pos + expected_bytes);
    return std::make_unique<PamImage>(w, h, d, std::move(pix), tupl);
}

std::unique_ptr<PamImage> PamImage::from_file(const std::string& filepath, int max_pixels, std::string* err) {
    std::ifstream file(filepath, std::ios::binary | std::ios::ate);
    if (!file.is_open()) {
        if (err) *err = "Cannot open file: " + filepath;
        return nullptr;
    }
    std::streamsize size = file.tellg();
    file.seekg(0, std::ios::beg);

    std::vector<uint8_t> buffer(size);
    if (!file.read(reinterpret_cast<char*>(buffer.data()), size)) {
        if (err) *err = "Failed to read file: " + filepath;
        return nullptr;
    }

    return decode(buffer.data(), buffer.size(), max_pixels, err);
}

std::vector<uint8_t> PamImage::encode() const {
    std::ostringstream oss;
    oss << "P7\nWIDTH " << width
        << "\nHEIGHT " << height
        << "\nDEPTH " << depth
        << "\nMAXVAL 255"
        << "\nTUPLTYPE " << tupltype
        << "\nENDHDR\n";

    std::string header = oss.str();
    std::vector<uint8_t> out;
    out.reserve(header.size() + data.size());
    out.insert(out.end(), header.begin(), header.end());
    out.insert(out.end(), data.begin(), data.end());
    return out;
}

bool PamImage::to_file(const std::string& filepath, std::string* err) const {
    std::ofstream file(filepath, std::ios::binary);
    if (!file.is_open()) {
        if (err) *err = "Cannot open output file: " + filepath;
        return false;
    }
    std::vector<uint8_t> bytes = encode();
    file.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
    return file.good();
}

std::vector<uint8_t> PamImage::to_rgb_bytes() const {
    if (depth == 3) return data;
    size_t npix = static_cast<size_t>(width) * height;
    std::vector<uint8_t> rgb(npix * 3);
    for (size_t i = 0; i < npix; ++i) {
        rgb[i * 3 + 0] = data[i * 4 + 0];
        rgb[i * 3 + 1] = data[i * 4 + 1];
        rgb[i * 3 + 2] = data[i * 4 + 2];
    }
    return rgb;
}

std::vector<uint8_t> PamImage::to_rgba_bytes() const {
    if (depth == 4) return data;
    size_t npix = static_cast<size_t>(width) * height;
    std::vector<uint8_t> rgba(npix * 4);
    for (size_t i = 0; i < npix; ++i) {
        rgba[i * 4 + 0] = data[i * 3 + 0];
        rgba[i * 4 + 1] = data[i * 3 + 1];
        rgba[i * 4 + 2] = data[i * 3 + 2];
        rgba[i * 4 + 3] = 255;
    }
    return rgba;
}

} // namespace arena
