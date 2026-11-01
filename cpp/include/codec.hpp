#pragma once

#include "pam.hpp"
#include "params.hpp"
#include <vector>
#include <string>
#include <memory>

namespace arena {

std::vector<uint8_t> encode_image(const PamImage& img, const EncodeParams& params, std::string* err = nullptr);

std::unique_ptr<PamImage> decode_image(const uint8_t* data, size_t size,
                                       const std::string& format,
                                       const std::string& impl = "",
                                       int max_pixels = 0,
                                       std::string* err = nullptr);

std::vector<uint8_t> transcode_image(const uint8_t* data, size_t size,
                                     const std::string& from_format,
                                     const std::string& to_format,
                                     const EncodeParams& to_params,
                                     const std::string& from_impl = "",
                                     int max_pixels = 0,
                                     std::string* err = nullptr);

const char* get_implementation_tier();

} // namespace arena
