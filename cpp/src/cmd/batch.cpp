#include "pam.hpp"
#include "analyze.hpp"
#include "codec.hpp"
#include "params.hpp"

#include <iostream>
#include <fstream>
#include <vector>
#include <string>

using namespace arena;

static void print_usage(const char* prog) {
    std::cerr << "Usage: " << prog << " --op <analyze|encode|decode|transcode> [options]\n"
              << "Options:\n"
              << "  --input <path>       Input file path ('-' for stdin)\n"
              << "  --output <path>      Output file path ('-' for stdout)\n"
              << "  --format <fmt>       Image format (png, jpeg, webp, avif, jxl)\n"
              << "  --to <fmt>           Target format for transcode\n"
              << "  --mode <mode>        Compression mode (lossy, lossless)\n"
              << "  --q <1..100>         Quality (default 75)\n"
              << "  --effort <1..10>     Effort level (default 4)\n"
              << "  --impl <name>        Implementation name\n"
              << "  --from-impl <name>   Source implementation name\n"
              << "  --to-impl <name>     Target implementation name\n";
}

static std::vector<uint8_t> read_input(const std::string& input_path, std::string* err) {
    if (input_path.empty() || input_path == "-") {
        std::vector<uint8_t> buf;
        char chunk[16384];
        while (std::cin.read(chunk, sizeof(chunk)) || std::cin.gcount() > 0) {
            buf.insert(buf.end(), chunk, chunk + std::cin.gcount());
        }
        if (buf.empty()) {
            if (err) *err = "empty input from stdin";
        }
        return buf;
    } else {
        std::ifstream file(input_path, std::ios::binary | std::ios::ate);
        if (!file.is_open()) {
            if (err) *err = "failed to open input file: " + input_path;
            return {};
        }
        std::streamsize sz = file.tellg();
        file.seekg(0, std::ios::beg);
        std::vector<uint8_t> buf(sz);
        if (!file.read(reinterpret_cast<char*>(buf.data()), sz)) {
            if (err) *err = "failed to read input file: " + input_path;
            return {};
        }
        return buf;
    }
}

static bool write_output(const std::string& output_path, const uint8_t* data, size_t size, std::string* err) {
    if (output_path.empty() || output_path == "-") {
        std::cout.write(reinterpret_cast<const char*>(data), size);
        return std::cout.good();
    } else {
        std::ofstream file(output_path, std::ios::binary);
        if (!file.is_open()) {
            if (err) *err = "failed to open output file: " + output_path;
            return false;
        }
        file.write(reinterpret_cast<const char*>(data), size);
        return file.good();
    }
}

int main(int argc, char* argv[]) {
    std::string op, input_path, output_path;
    std::string format, to_format, mode;
    std::string q_str, effort_str, impl, from_impl, to_impl;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--op" && i + 1 < argc) { op = argv[++i]; }
        else if (arg == "--input" && i + 1 < argc) { input_path = argv[++i]; }
        else if (arg == "--output" && i + 1 < argc) { output_path = argv[++i]; }
        else if (arg == "--format" && i + 1 < argc) { format = argv[++i]; }
        else if (arg == "--to" && i + 1 < argc) { to_format = argv[++i]; }
        else if (arg == "--mode" && i + 1 < argc) { mode = argv[++i]; }
        else if (arg == "--q" && i + 1 < argc) { q_str = argv[++i]; }
        else if (arg == "--effort" && i + 1 < argc) { effort_str = argv[++i]; }
        else if (arg == "--impl" && i + 1 < argc) { impl = argv[++i]; }
        else if (arg == "--from-impl" && i + 1 < argc) { from_impl = argv[++i]; }
        else if (arg == "--to-impl" && i + 1 < argc) { to_impl = argv[++i]; }
        else if (arg == "-h" || arg == "--help") {
            print_usage(argv[0]);
            return 0;
        }
    }

    if (from_impl.empty()) from_impl = impl;
    if (to_impl.empty()) to_impl = impl;

    if (op.empty()) {
        std::cerr << "Error: --op flag is required (analyze, encode, decode, transcode)" << std::endl;
        return 1;
    }

    int max_pixels = PamImage::get_max_pixels();
    std::string err;
    std::vector<uint8_t> input_data = read_input(input_path, &err);
    if (input_data.empty()) {
        std::cerr << "Error: " << (err.empty() ? "empty input" : err) << std::endl;
        return 1;
    }

    if (op == "analyze") {
        auto pam_img = PamImage::decode(input_data.data(), input_data.size(), max_pixels, &err);
        if (!pam_img) {
            std::cerr << "Error decoding PAM input: " << err << std::endl;
            return 1;
        }
        AnalyzeResult res = analyze_image(*pam_img);
        std::string json_str = res.to_json(true);

        if (!output_path.empty() && output_path != "-") {
            if (!write_output(output_path, reinterpret_cast<const uint8_t*>(json_str.data()), json_str.size(), &err)) {
                std::cerr << "Error writing output file: " << err << std::endl;
                return 1;
            }
        }
        // Always write to stdout (required by verify_cross.py)
        std::cout << json_str << std::endl;
        return 0;
    }
    else if (op == "encode") {
        if (format.empty()) {
            std::cerr << "Error: --format is required for encode" << std::endl;
            return 1;
        }
        EncodeParams params;
        if (!EncodeParams::parse(format, mode, q_str, effort_str, to_impl, &params, &err)) {
            std::cerr << "Error: " << err << std::endl;
            return 1;
        }

        auto pam_img = PamImage::decode(input_data.data(), input_data.size(), max_pixels, &err);
        if (!pam_img) {
            std::cerr << "Error decoding PAM input: " << err << std::endl;
            return 1;
        }

        std::vector<uint8_t> encoded = encode_image(*pam_img, params, &err);
        if (encoded.empty() && !err.empty()) {
            std::cerr << "Error encoding: " << err << std::endl;
            return 1;
        }

        if (!write_output(output_path, encoded.data(), encoded.size(), &err)) {
            std::cerr << "Error writing output: " << err << std::endl;
            return 1;
        }
        return 0;
    }
    else if (op == "decode") {
        if (format.empty()) {
            // Infer from input filename extension
            if (!input_path.empty() && input_path != "-") {
                size_t dot = input_path.find_last_of('.');
                if (dot != std::string::npos) {
                    format = input_path.substr(dot + 1);
                }
            }
        }
        if (format.empty()) {
            std::cerr << "Error: --format is required for decode" << std::endl;
            return 1;
        }

        auto pam_img = decode_image(input_data.data(), input_data.size(), format, from_impl, max_pixels, &err);
        if (!pam_img) {
            std::cerr << "Error decoding: " << err << std::endl;
            return 1;
        }

        std::vector<uint8_t> pam_bytes = pam_img->encode();
        if (!write_output(output_path, pam_bytes.data(), pam_bytes.size(), &err)) {
            std::cerr << "Error writing output: " << err << std::endl;
            return 1;
        }
        return 0;
    }
    else if (op == "transcode") {
        if (format.empty() || to_format.empty()) {
            std::cerr << "Error: --format and --to are required for transcode" << std::endl;
            return 1;
        }
        EncodeParams params;
        if (!EncodeParams::parse(to_format, mode, q_str, effort_str, to_impl, &params, &err)) {
            std::cerr << "Error: " << err << std::endl;
            return 1;
        }

        auto pam_img = decode_image(input_data.data(), input_data.size(), format, from_impl, max_pixels, &err);
        if (!pam_img) {
            std::cerr << "Error decoding input: " << err << std::endl;
            return 1;
        }

        std::vector<uint8_t> encoded = encode_image(*pam_img, params, &err);
        if (encoded.empty() && !err.empty()) {
            std::cerr << "Error encoding transcode: " << err << std::endl;
            return 1;
        }

        if (!write_output(output_path, encoded.data(), encoded.size(), &err)) {
            std::cerr << "Error writing output: " << err << std::endl;
            return 1;
        }
        return 0;
    }
    else {
        std::cerr << "Error: unknown op: \"" << op << "\"" << std::endl;
        return 1;
    }
}
