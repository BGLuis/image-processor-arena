#include "codec.hpp"
#include "pam.hpp"
#include "params.hpp"

#include <iostream>
#include <sstream>
#include <cstring>
#include <unistd.h>
#include <sys/wait.h>

#ifdef ARENA_PORTABLE
#if __has_include("vendor/lodepng/lodepng.h")
#include "vendor/lodepng/lodepng.h"
#elif __has_include("cpp/vendor/lodepng/lodepng.h")
#include "cpp/vendor/lodepng/lodepng.h"
#else
#include "lodepng.h"
#endif
#else
#include <png.h>
#include <turbojpeg.h>
#include <webp/encode.h>
#include <webp/decode.h>
#include <jxl/encode.h>
#include <jxl/decode.h>
#include <jxl/thread_parallel_runner.h>
#endif

namespace arena {

const char* get_implementation_tier() {
#ifdef ARENA_PORTABLE
    return "cpp:portable:gcc:pure-c";
#elif defined(__clang__)
    return "cpp:accelerated:clang:native-libs";
#else
    return "cpp:accelerated:gcc:native-libs";
#endif
}

#ifndef ARENA_PORTABLE

// Memory I/O helpers for libpng
struct PngMemWriter {
    std::vector<uint8_t>* out;
};
static void png_write_fn(png_structp png_ptr, png_bytep data, png_size_t length) {
    auto* mw = reinterpret_cast<PngMemWriter*>(png_get_io_ptr(png_ptr));
    mw->out->insert(mw->out->end(), data, data + length);
}
static void png_flush_fn(png_structp) {}

struct PngMemReader {
    const uint8_t* data;
    size_t size;
    size_t offset;
};
static void png_read_fn(png_structp png_ptr, png_bytep outBytes, png_size_t byteCountToRead) {
    auto* mr = reinterpret_cast<PngMemReader*>(png_get_io_ptr(png_ptr));
    if (mr->offset + byteCountToRead > mr->size) {
        png_error(png_ptr, "Read Error");
        return;
    }
    std::memcpy(outBytes, mr->data + mr->offset, byteCountToRead);
    mr->offset += byteCountToRead;
}

// Subprocess pipe helper for AVIF encode/decode
static bool run_python_pipe(const std::string& script,
                            const uint8_t* in_data, size_t in_size,
                            std::vector<uint8_t>* out_data,
                            std::string* err) {
    int in_pipe[2];
    int out_pipe[2];
    if (pipe(in_pipe) != 0 || pipe(out_pipe) != 0) {
        if (err) *err = "pipe creation failed";
        return false;
    }

    pid_t pid = fork();
    if (pid < 0) {
        if (err) *err = "fork failed";
        close(in_pipe[0]); close(in_pipe[1]);
        close(out_pipe[0]); close(out_pipe[1]);
        return false;
    }

    if (pid == 0) {
        // Child process
        close(in_pipe[1]);
        close(out_pipe[0]);
        dup2(in_pipe[0], STDIN_FILENO);
        dup2(out_pipe[1], STDOUT_FILENO);
        close(in_pipe[0]);
        close(out_pipe[1]);

        execlp("python3", "python3", "-c", script.c_str(), nullptr);
        _exit(127);
    }

    // Parent process
    close(in_pipe[0]);
    close(out_pipe[1]);

    // Write input data in chunks
    size_t written = 0;
    while (written < in_size) {
        ssize_t nw = write(in_pipe[1], in_data + written, in_size - written);
        if (nw <= 0) break;
        written += nw;
    }
    close(in_pipe[1]);

    // Read output data
    out_data->clear();
    char buf[65536];
    ssize_t nr;
    while ((nr = read(out_pipe[0], buf, sizeof(buf))) > 0) {
        out_data->insert(out_data->end(), buf, buf + nr);
    }
    close(out_pipe[0]);

    int status = 0;
    waitpid(pid, &status, 0);
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        if (err) *err = "python helper failed with exit code " + std::to_string(WEXITSTATUS(status));
        return false;
    }
    return true;
}

#endif // !ARENA_PORTABLE

std::vector<uint8_t> encode_image(const PamImage& img, const EncodeParams& params, std::string* err) {
    std::string fmt = normalize_format(params.format);

#ifdef ARENA_PORTABLE
    if (fmt != "png") {
        if (err) *err = "format " + fmt + " not supported in portable mode (only png)";
        return {};
    }
    std::vector<unsigned char> png_out;
    LodePNGColorType colortype = (img.depth == 4) ? LCT_RGBA : LCT_RGB;
    unsigned e = lodepng::encode(png_out, img.data, img.width, img.height, colortype, 8);
    if (e != 0) {
        if (err) *err = std::string("lodepng encode error: ") + lodepng_error_text(e);
        return {};
    }
    return std::vector<uint8_t>(png_out.begin(), png_out.end());
#else
    if (fmt == "png") {
        std::vector<uint8_t> png_buf;
        png_structp png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
        if (!png_ptr) {
            if (err) *err = "png_create_write_struct failed";
            return {};
        }
        png_infop info_ptr = png_create_info_struct(png_ptr);
        if (!info_ptr) {
            png_destroy_write_struct(&png_ptr, nullptr);
            if (err) *err = "png_create_info_struct failed";
            return {};
        }

        if (setjmp(png_jmpbuf(png_ptr))) {
            png_destroy_write_struct(&png_ptr, &info_ptr);
            if (err) *err = "libpng write error";
            return {};
        }

        PngMemWriter mw{&png_buf};
        png_set_write_fn(png_ptr, &mw, png_write_fn, png_flush_fn);
        int color_type = (img.depth == 4) ? PNG_COLOR_TYPE_RGBA : PNG_COLOR_TYPE_RGB;
        png_set_IHDR(png_ptr, info_ptr, img.width, img.height, 8, color_type,
                     PNG_INTERLACE_NONE, PNG_COMPRESSION_TYPE_DEFAULT, PNG_FILTER_TYPE_DEFAULT);
        png_set_compression_level(png_ptr, png_compression(params.effort));
        png_write_info(png_ptr, info_ptr);

        size_t row_stride = static_cast<size_t>(img.width) * img.depth;
        std::vector<png_bytep> rows(img.height);
        for (int y = 0; y < img.height; ++y) {
            rows[y] = const_cast<png_bytep>(img.data.data() + y * row_stride);
        }
        png_write_image(png_ptr, rows.data());
        png_write_end(png_ptr, nullptr);
        png_destroy_write_struct(&png_ptr, &info_ptr);
        return png_buf;
    }
    else if (fmt == "jpeg") {
        if (img.width > JPEG_MAX_SIDE || img.height > JPEG_MAX_SIDE) {
            if (err) *err = "JPEG side exceeds max 65535";
            return {};
        }
        tjhandle tj = tjInitCompress();
        if (!tj) {
            if (err) *err = "tjInitCompress failed";
            return {};
        }
        unsigned char* jpeg_buf = nullptr;
        unsigned long jpeg_size = 0;
        int pf = (img.depth == 4) ? TJPF_RGBA : TJPF_RGB;
        int status = tjCompress2(tj, const_cast<unsigned char*>(img.data.data()),
                                 img.width, 0, img.height, pf,
                                 &jpeg_buf, &jpeg_size,
                                 TJSAMP_420, params.q, TJFLAG_FASTDCT);
        if (status != 0) {
            if (err) *err = std::string("tjCompress2 failed: ") + tjGetErrorStr2(tj);
            tjDestroy(tj);
            return {};
        }
        std::vector<uint8_t> out(jpeg_buf, jpeg_buf + jpeg_size);
        tjFree(jpeg_buf);
        tjDestroy(tj);
        return out;
    }
    else if (fmt == "webp") {
        if (img.width > WEBP_MAX_SIDE || img.height > WEBP_MAX_SIDE) {
            if (err) *err = "WebP side exceeds max 16383";
            return {};
        }
        if (params.mode == "lossless") {
            uint8_t* output = nullptr;
            size_t out_size = 0;
            if (img.depth == 4) {
                out_size = WebPEncodeLosslessRGBA(img.data.data(), img.width, img.height, img.width * 4, &output);
            } else {
                out_size = WebPEncodeLosslessRGB(img.data.data(), img.width, img.height, img.width * 3, &output);
            }
            if (out_size == 0 || !output) {
                if (err) *err = "WebP lossless encode failed";
                return {};
            }
            std::vector<uint8_t> out(output, output + out_size);
            WebPFree(output);
            return out;
        } else {
            WebPConfig config;
            WebPConfigInit(&config);
            config.quality = static_cast<float>(params.q);
            config.method = webp_method(params.effort);

            WebPPicture pic;
            WebPPictureInit(&pic);
            pic.width = img.width;
            pic.height = img.height;
            pic.use_argb = 1;
            if (img.depth == 4) {
                WebPPictureImportRGBA(&pic, img.data.data(), img.width * 4);
            } else {
                WebPPictureImportRGB(&pic, img.data.data(), img.width * 3);
            }

            WebPMemoryWriter writer;
            WebPMemoryWriterInit(&writer);
            pic.writer = WebPMemoryWrite;
            pic.custom_ptr = &writer;

            int ok = WebPEncode(&config, &pic);
            WebPPictureFree(&pic);
            if (!ok) {
                WebPMemoryWriterClear(&writer);
                if (err) *err = "WebP lossy encode failed";
                return {};
            }
            std::vector<uint8_t> out(writer.mem, writer.mem + writer.size);
            WebPMemoryWriterClear(&writer);
            return out;
        }
    }
    else if (fmt == "jxl") {
        JxlEncoder* enc = JxlEncoderCreate(nullptr);
        void* runner = JxlThreadParallelRunnerCreate(nullptr, JxlThreadParallelRunnerDefaultNumWorkerThreads());
        JxlEncoderSetParallelRunner(enc, JxlThreadParallelRunner, runner);

        JxlPixelFormat pixel_format = {
            static_cast<uint32_t>(img.depth),
            JXL_TYPE_UINT8,
            JXL_LITTLE_ENDIAN,
            0
        };

        JxlBasicInfo basic_info;
        JxlEncoderInitBasicInfo(&basic_info);
        basic_info.xsize = img.width;
        basic_info.ysize = img.height;
        basic_info.bits_per_sample = 8;
        basic_info.num_color_channels = 3;
        basic_info.alpha_bits = (img.depth == 4) ? 8 : 0;
        basic_info.uses_original_profile = JXL_FALSE;

        if (JXL_ENC_SUCCESS != JxlEncoderSetBasicInfo(enc, &basic_info)) {
            JxlEncoderDestroy(enc);
            JxlThreadParallelRunnerDestroy(runner);
            if (err) *err = "JxlEncoderSetBasicInfo failed";
            return {};
        }

        JxlColorEncoding color_encoding;
        JxlColorEncodingSetToSRGB(&color_encoding, JXL_FALSE);
        if (JXL_ENC_SUCCESS != JxlEncoderSetColorEncoding(enc, &color_encoding)) {
            JxlEncoderDestroy(enc);
            JxlThreadParallelRunnerDestroy(runner);
            if (err) *err = "JxlEncoderSetColorEncoding failed";
            return {};
        }

        JxlEncoderFrameSettings* settings = JxlEncoderFrameSettingsCreate(enc, nullptr);
        int effort_val = jxl_effort(params.effort);
        JxlEncoderFrameSettingsSetOption(settings, JXL_ENC_FRAME_SETTING_EFFORT, effort_val);

        if (params.mode == "lossless") {
            JxlEncoderSetFrameLossless(settings, JXL_TRUE);
        } else {
            double distance = jxl_distance(params.q);
            JxlEncoderSetFrameDistance(settings, distance);
        }

        if (JXL_ENC_SUCCESS != JxlEncoderAddImageFrame(settings, &pixel_format, img.data.data(), img.data.size())) {
            JxlEncoderDestroy(enc);
            JxlThreadParallelRunnerDestroy(runner);
            if (err) *err = "JxlEncoderAddImageFrame failed";
            return {};
        }
        JxlEncoderCloseInput(enc);

        std::vector<uint8_t> compressed(65536);
        uint8_t* next_out = compressed.data();
        size_t avail_out = compressed.size();
        JxlEncoderStatus status = JXL_ENC_NEED_MORE_OUTPUT;

        while (status == JXL_ENC_NEED_MORE_OUTPUT) {
            status = JxlEncoderProcessOutput(enc, &next_out, &avail_out);
            if (status == JXL_ENC_NEED_MORE_OUTPUT) {
                size_t offset = next_out - compressed.data();
                compressed.resize(compressed.size() * 2);
                next_out = compressed.data() + offset;
                avail_out = compressed.size() - offset;
            }
        }
        size_t final_size = next_out - compressed.data();
        compressed.resize(final_size);

        JxlEncoderDestroy(enc);
        JxlThreadParallelRunnerDestroy(runner);
        return compressed;
    }
    else if (fmt == "avif") {
        if (params.mode == "lossless") {
            if (err) *err = "avif lossless is not supported";
            return {};
        }
        // Encode via Pillow
        std::vector<uint8_t> pam_bytes = img.encode();
        std::vector<uint8_t> avif_out;
        std::string script =
            "import sys, io\n"
            "from PIL import Image\n"
            "data = sys.stdin.buffer.read()\n"
            "hdr_end = data.find(b'ENDHDR\\n')\n"
            "if hdr_end == -1: sys.exit(1)\n"
            "raw = data[hdr_end + 7:]\n"
            "lines = data[:hdr_end].decode('ascii').splitlines()\n"
            "w, h, d = 0, 0, 3\n"
            "for l in lines:\n"
            "    parts = l.strip().split()\n"
            "    if len(parts) >= 2:\n"
            "        if parts[0] == 'WIDTH': w = int(parts[1])\n"
            "        elif parts[0] == 'HEIGHT': h = int(parts[1])\n"
            "        elif parts[0] == 'DEPTH': d = int(parts[1])\n"
            "mode = 'RGBA' if d == 4 else 'RGB'\n"
            "im = Image.frombytes(mode, (w, h), raw)\n"
            "out = io.BytesIO()\n"
            "im.save(out, format='AVIF', quality=" + std::to_string(params.q) + ")\n"
            "sys.stdout.buffer.write(out.getvalue())\n";

        if (!run_python_pipe(script, pam_bytes.data(), pam_bytes.size(), &avif_out, err)) {
            return {};
        }
        return avif_out;
    }
    else {
        if (err) *err = "unsupported format: " + fmt;
        return {};
    }
#endif
}

std::unique_ptr<PamImage> decode_image(const uint8_t* data, size_t size,
                                       const std::string& format,
                                       const std::string& impl,
                                       int max_pixels,
                                       std::string* err) {
    if (max_pixels <= 0) max_pixels = PamImage::get_max_pixels();
    std::string fmt = normalize_format(format);

#ifdef ARENA_PORTABLE
    if (fmt != "png") {
        if (err) *err = "format " + fmt + " not supported in portable mode (only png)";
        return nullptr;
    }
    lodepng::State state;
    unsigned w = 0, h = 0;
    unsigned e = lodepng_inspect(&w, &h, &state, data, size);
    if (e != 0) {
        if (err) *err = std::string("lodepng inspect error: ") + lodepng_error_text(e);
        return nullptr;
    }
    if (static_cast<int>(w) > max_pixels / static_cast<int>(h)) {
        if (err) *err = "image exceeds max pixels limit";
        return nullptr;
    }

    bool has_alpha = (state.info_png.color.colortype == LCT_RGBA ||
                      state.info_png.color.colortype == LCT_GREY_ALPHA ||
                      state.info_png.color.key_defined);
    int depth = has_alpha ? 4 : 3;
    LodePNGColorType target_color = has_alpha ? LCT_RGBA : LCT_RGB;

    std::vector<unsigned char> out_pixels;
    if (state.info_png.color.bitdepth == 16) {
        state.info_raw.bitdepth = 16;
        state.info_raw.colortype = target_color;
        e = lodepng::decode(out_pixels, w, h, state, data, size);
        if (e != 0) {
            if (err) *err = std::string("lodepng decode 16-bit error: ") + lodepng_error_text(e);
            return nullptr;
        }
        std::vector<uint8_t> out8;
        out8.reserve(out_pixels.size() / 2);
        for (size_t i = 0; i < out_pixels.size(); i += 2) {
            uint16_t val = (static_cast<uint16_t>(out_pixels[i]) << 8) | out_pixels[i + 1];
            out8.push_back(static_cast<uint8_t>((val + 128) / 257));
        }
        return std::make_unique<PamImage>(w, h, depth, std::move(out8));
    } else {
        e = lodepng::decode(out_pixels, w, h, data, size, target_color, 8);
        if (e != 0) {
            if (err) *err = std::string("lodepng decode error: ") + lodepng_error_text(e);
            return nullptr;
        }
        return std::make_unique<PamImage>(w, h, depth, std::vector<uint8_t>(out_pixels.begin(), out_pixels.end()));
    }
#else
    if (fmt == "png") {
        png_structp png_ptr = png_create_read_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
        if (!png_ptr) {
            if (err) *err = "png_create_read_struct failed";
            return nullptr;
        }
        png_infop info_ptr = png_create_info_struct(png_ptr);
        if (!info_ptr) {
            png_destroy_read_struct(&png_ptr, nullptr, nullptr);
            if (err) *err = "png_create_info_struct failed";
            return nullptr;
        }

        if (setjmp(png_jmpbuf(png_ptr))) {
            png_destroy_read_struct(&png_ptr, &info_ptr, nullptr);
            if (err) *err = "libpng decode error";
            return nullptr;
        }

        PngMemReader mr{data, size, 0};
        png_set_read_fn(png_ptr, &mr, png_read_fn);
        png_read_info(png_ptr, info_ptr);

        png_uint_32 w, h;
        int bit_depth, color_type;
        png_get_IHDR(png_ptr, info_ptr, &w, &h, &bit_depth, &color_type, nullptr, nullptr, nullptr);

        if (static_cast<int>(w) > max_pixels / static_cast<int>(h)) {
            png_destroy_read_struct(&png_ptr, &info_ptr, nullptr);
            if (err) *err = "image exceeds max pixels limit";
            return nullptr;
        }

        if (color_type == PNG_COLOR_TYPE_PALETTE) {
            png_set_palette_to_rgb(png_ptr);
        }
        if (color_type == PNG_COLOR_TYPE_GRAY && bit_depth < 8) {
            png_set_expand_gray_1_2_4_to_8(png_ptr);
        }
        if (png_get_valid(png_ptr, info_ptr, PNG_INFO_tRNS)) {
            png_set_tRNS_to_alpha(png_ptr);
        }
        if (color_type == PNG_COLOR_TYPE_GRAY || color_type == PNG_COLOR_TYPE_GRAY_ALPHA) {
            png_set_gray_to_rgb(png_ptr);
        }
        png_read_update_info(png_ptr, info_ptr);

        color_type = png_get_color_type(png_ptr, info_ptr);
        int depth = (color_type & PNG_COLOR_MASK_ALPHA) ? 4 : 3;

        size_t rowbytes = png_get_rowbytes(png_ptr, info_ptr);
        std::vector<uint8_t> raw_image(rowbytes * h);
        std::vector<png_bytep> rows(h);
        for (png_uint_32 y = 0; y < h; ++y) {
            rows[y] = raw_image.data() + y * rowbytes;
        }
        png_read_image(png_ptr, rows.data());

        std::vector<uint8_t> final_pixels;
        if (bit_depth == 16) {
            final_pixels.reserve(raw_image.size() / 2);
            for (size_t i = 0; i < raw_image.size(); i += 2) {
                uint16_t v = (static_cast<uint16_t>(raw_image[i]) << 8) | raw_image[i + 1];
                final_pixels.push_back(static_cast<uint8_t>((v + 128) / 257));
            }
        } else {
            final_pixels = std::move(raw_image);
        }

        png_destroy_read_struct(&png_ptr, &info_ptr, nullptr);
        return std::make_unique<PamImage>(w, h, depth, std::move(final_pixels));
    }
    else if (fmt == "jpeg") {
        tjhandle tj = tjInitDecompress();
        if (!tj) {
            if (err) *err = "tjInitDecompress failed";
            return nullptr;
        }
        int w = 0, h = 0, subsamp = 0, cs = 0;
        int status = tjDecompressHeader3(tj, const_cast<unsigned char*>(data), size, &w, &h, &subsamp, &cs);
        if (status != 0) {
            if (err) *err = std::string("tjDecompressHeader3 failed: ") + tjGetErrorStr2(tj);
            tjDestroy(tj);
            return nullptr;
        }
        if (w > max_pixels / h) {
            tjDestroy(tj);
            if (err) *err = "image exceeds max pixels limit";
            return nullptr;
        }

        std::vector<uint8_t> rgb(static_cast<size_t>(w) * h * 3);
        status = tjDecompress2(tj, const_cast<unsigned char*>(data), size,
                               rgb.data(), w, 0, h, TJPF_RGB, 0);
        if (status != 0) {
            if (err) *err = std::string("tjDecompress2 failed: ") + tjGetErrorStr2(tj);
            tjDestroy(tj);
            return nullptr;
        }
        tjDestroy(tj);
        return std::make_unique<PamImage>(w, h, 3, std::move(rgb));
    }
    else if (fmt == "webp") {
        WebPBitstreamFeatures features;
        if (WebPGetFeatures(data, size, &features) != VP8_STATUS_OK) {
            if (err) *err = "WebPGetFeatures failed";
            return nullptr;
        }
        if (features.has_animation) {
            if (err) *err = "WebP animado não é suportado";
            return nullptr;
        }
        if (features.width > WEBP_MAX_SIDE || features.height > WEBP_MAX_SIDE) {
            if (err) *err = "WebP side exceeds max 16383";
            return nullptr;
        }
        if (features.width > max_pixels / features.height) {
            if (err) *err = "image exceeds max pixels limit";
            return nullptr;
        }

        int w = 0, h = 0;
        uint8_t* decoded = nullptr;
        int depth = features.has_alpha ? 4 : 3;
        if (features.has_alpha) {
            decoded = WebPDecodeRGBA(data, size, &w, &h);
        } else {
            decoded = WebPDecodeRGB(data, size, &w, &h);
        }
        if (!decoded) {
            if (err) *err = "WebP decode failed";
            return nullptr;
        }

        size_t total = static_cast<size_t>(w) * h * depth;
        std::vector<uint8_t> pixels(decoded, decoded + total);
        WebPFree(decoded);
        return std::make_unique<PamImage>(w, h, depth, std::move(pixels));
    }
    else if (fmt == "jxl") {
        JxlDecoder* dec = JxlDecoderCreate(nullptr);
        if (JXL_DEC_SUCCESS != JxlDecoderSubscribeEvents(dec, JXL_DEC_BASIC_INFO | JXL_DEC_FULL_IMAGE)) {
            JxlDecoderDestroy(dec);
            if (err) *err = "JxlDecoderSubscribeEvents failed";
            return nullptr;
        }
        JxlDecoderSetInput(dec, data, size);

        std::vector<uint8_t> decoded_pixels;
        uint32_t dec_w = 0, dec_h = 0;
        int dec_channels = 3;

        for (;;) {
            JxlDecoderStatus dec_status = JxlDecoderProcessInput(dec);
            if (dec_status == JXL_DEC_ERROR) {
                JxlDecoderDestroy(dec);
                if (err) *err = "JXL decoder error";
                return nullptr;
            } else if (dec_status == JXL_DEC_NEED_MORE_INPUT) {
                break;
            } else if (dec_status == JXL_DEC_BASIC_INFO) {
                JxlBasicInfo dec_info;
                JxlDecoderGetBasicInfo(dec, &dec_info);
                dec_w = dec_info.xsize;
                dec_h = dec_info.ysize;
                if (static_cast<int>(dec_w) > max_pixels / static_cast<int>(dec_h)) {
                    JxlDecoderDestroy(dec);
                    if (err) *err = "image exceeds max pixels limit";
                    return nullptr;
                }
                dec_channels = (dec_info.alpha_bits > 0) ? 4 : 3;
            } else if (dec_status == JXL_DEC_NEED_IMAGE_OUT_BUFFER) {
                size_t buffer_size = 0;
                JxlPixelFormat dec_format = {static_cast<uint32_t>(dec_channels), JXL_TYPE_UINT8, JXL_LITTLE_ENDIAN, 0};
                if (JXL_DEC_SUCCESS != JxlDecoderImageOutBufferSize(dec, &dec_format, &buffer_size)) {
                    JxlDecoderDestroy(dec);
                    if (err) *err = "JxlDecoderImageOutBufferSize failed";
                    return nullptr;
                }
                decoded_pixels.resize(buffer_size);
                if (JXL_DEC_SUCCESS != JxlDecoderSetImageOutBuffer(dec, &dec_format, decoded_pixels.data(), decoded_pixels.size())) {
                    JxlDecoderDestroy(dec);
                    if (err) *err = "JxlDecoderSetImageOutBuffer failed";
                    return nullptr;
                }
            } else if (dec_status == JXL_DEC_FULL_IMAGE || dec_status == JXL_DEC_SUCCESS) {
                break;
            }
        }
        JxlDecoderDestroy(dec);

        if (decoded_pixels.empty() || dec_w == 0 || dec_h == 0) {
            if (err) *err = "JXL decoding yielded no image";
            return nullptr;
        }

        return std::make_unique<PamImage>(dec_w, dec_h, dec_channels, std::move(decoded_pixels));
    }
    else if (fmt == "avif") {
        std::vector<uint8_t> pam_out;
        std::string script =
            "import sys, io\n"
            "from PIL import Image\n"
            "data = sys.stdin.buffer.read()\n"
            "try:\n"
            "    im = Image.open(io.BytesIO(data))\n"
            "    if im.mode not in ('RGB', 'RGBA'):\n"
            "        im = im.convert('RGBA' if 'A' in im.mode else 'RGB')\n"
            "    w, h = im.size\n"
            "    d = 4 if im.mode == 'RGBA' else 3\n"
            "    tupl = 'RGB_ALPHA' if d == 4 else 'RGB'\n"
            "    raw = im.tobytes()\n"
            "    hdr = f'P7\\nWIDTH {w}\\nHEIGHT {h}\\nDEPTH {d}\\nMAXVAL 255\\nTUPLTYPE {tupl}\\nENDHDR\\n'.encode('ascii')\n"
            "    sys.stdout.buffer.write(hdr + raw)\n"
            "except Exception as e:\n"
            "    sys.stderr.write(str(e))\n"
            "    sys.exit(1)\n";

        if (!run_python_pipe(script, data, size, &pam_out, err)) {
            return nullptr;
        }
        return PamImage::decode(pam_out.data(), pam_out.size(), max_pixels, err);
    }
    else {
        if (err) *err = "unsupported decode format: " + fmt;
        return nullptr;
    }
#endif
}

std::vector<uint8_t> transcode_image(const uint8_t* data, size_t size,
                                     const std::string& from_format,
                                     const std::string& to_format,
                                     const EncodeParams& to_params,
                                     const std::string& from_impl,
                                     int max_pixels,
                                     std::string* err) {
    auto pam_img = decode_image(data, size, from_format, from_impl, max_pixels, err);
    if (!pam_img) return {};
    return encode_image(*pam_img, to_params, err);
}

} // namespace arena
