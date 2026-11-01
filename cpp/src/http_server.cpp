#include "http_server.hpp"
#include "pam.hpp"
#include "analyze.hpp"
#include "codec.hpp"
#include "params.hpp"

#include <iostream>
#include <sstream>
#include <vector>
#include <string>
#include <map>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <chrono>
#include <cstring>
#include <algorithm>
#include <cctype>

#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>

namespace arena {

static std::string url_decode(const std::string& in) {
    std::string out;
    out.reserve(in.size());
    for (size_t i = 0; i < in.size(); ++i) {
        if (in[i] == '%' && i + 2 < in.size()) {
            int h1 = in[i + 1], h2 = in[i + 2];
            auto from_hex = [](int c) -> int {
                if (c >= '0' && c <= '9') return c - '0';
                if (c >= 'a' && c <= 'f') return c - 'a' + 10;
                if (c >= 'A' && c <= 'F') return c - 'A' + 10;
                return 0;
            };
            out += static_cast<char>((from_hex(h1) << 4) | from_hex(h2));
            i += 2;
        } else if (in[i] == '+') {
            out += ' ';
        } else {
            out += in[i];
        }
    }
    return out;
}

static std::map<std::string, std::string> parse_query(const std::string& qs) {
    std::map<std::string, std::string> params;
    size_t pos = 0;
    while (pos < qs.size()) {
        size_t next_amp = qs.find('&', pos);
        if (next_amp == std::string::npos) next_amp = qs.size();
        std::string part = qs.substr(pos, next_amp - pos);
        pos = next_amp + 1;
        if (part.empty()) continue;

        size_t eq = part.find('=');
        if (eq == std::string::npos) {
            params[url_decode(part)] = "";
        } else {
            params[url_decode(part.substr(0, eq))] = url_decode(part.substr(eq + 1));
        }
    }
    return params;
}

static std::string mime_for_format(const std::string& fmt) {
    std::string f = normalize_format(fmt);
    if (f == "png") return "image/png";
    if (f == "jpeg") return "image/jpeg";
    if (f == "webp") return "image/webp";
    if (f == "avif") return "image/avif";
    if (f == "jxl") return "image/jxl";
    return "application/octet-stream";
}

static void send_response(int fd, int status, const std::string& status_text,
                          const std::map<std::string, std::string>& headers,
                          const uint8_t* body, size_t body_len) {
    std::ostringstream oss;
    oss << "HTTP/1.1 " << status << " " << status_text << "\r\n";
    for (const auto& [k, v] : headers) {
        oss << k << ": " << v << "\r\n";
    }
    oss << "Content-Length: " << body_len << "\r\n";
    oss << "Connection: close\r\n\r\n";

    std::string head = oss.str();
    write(fd, head.data(), head.size());
    if (body && body_len > 0) {
        size_t sent = 0;
        while (sent < body_len) {
            ssize_t nw = write(fd, body + sent, body_len - sent);
            if (nw <= 0) break;
            sent += nw;
        }
    }
}

static void send_error(int fd, int status, const std::string& msg) {
    std::map<std::string, std::string> h;
    h["Content-Type"] = "text/plain";
    send_response(fd, status, (status == 413 ? "Payload Too Large" : (status == 400 ? "Bad Request" : "Error")),
                  h, reinterpret_cast<const uint8_t*>(msg.data()), msg.size());
}

static void handle_client(int client_fd) {
    std::vector<uint8_t> recv_buf;
    recv_buf.reserve(8192);
    char buf[4096];

    size_t max_body = PamImage::get_max_body_bytes();
    int max_pixels = PamImage::get_max_pixels();

    // Read header
    size_t header_end = std::string::npos;
    while (header_end == std::string::npos) {
        ssize_t nr = read(client_fd, buf, sizeof(buf));
        if (nr <= 0) {
            close(client_fd);
            return;
        }
        recv_buf.insert(recv_buf.end(), buf, buf + nr);
        std::string s(recv_buf.begin(), recv_buf.end());
        header_end = s.find("\r\n\r\n");
        if (header_end == std::string::npos) {
            header_end = s.find("\n\n");
            if (header_end != std::string::npos) header_end += 2;
        } else {
            header_end += 4;
        }
        if (recv_buf.size() > 65536) {
            send_error(client_fd, 400, "Header too large");
            close(client_fd);
            return;
        }
    }

    std::string header_str(recv_buf.begin(), recv_buf.begin() + header_end);
    std::istringstream hss(header_str);
    std::string method, raw_path, version;
    if (!(hss >> method >> raw_path >> version)) {
        send_error(client_fd, 400, "Invalid HTTP request line");
        close(client_fd);
        return;
    }

    size_t content_length = 0;
    std::string line;
    std::getline(hss, line); // finish request line
    while (std::getline(hss, line) && !line.empty()) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        size_t colon = line.find(':');
        if (colon != std::string::npos) {
            std::string key = line.substr(0, colon);
            std::string val = line.substr(colon + 1);
            std::transform(key.begin(), key.end(), key.begin(), [](unsigned char c) { return std::tolower(c); });
            while (!val.empty() && std::isspace(static_cast<unsigned char>(val.front()))) val.erase(val.begin());
            if (key == "content-length") {
                try {
                    content_length = std::stoull(val);
                } catch (...) {
                    content_length = 0;
                }
            }
        }
    }

    // Check payload limits
    if (content_length > max_body) {
        // Drain incoming body so client finishes sending and receives the 413 response cleanly
        size_t drained = recv_buf.size() - header_end;
        while (drained < content_length) {
            size_t need = content_length - drained;
            size_t chunk = std::min(need, sizeof(buf));
            ssize_t nr = read(client_fd, buf, chunk);
            if (nr <= 0) break;
            drained += nr;
        }
        send_error(client_fd, 413, "Payload Too Large");
        close(client_fd);
        return;
    }

    // Read remaining body
    std::vector<uint8_t> body(recv_buf.begin() + header_end, recv_buf.end());
    while (body.size() < content_length) {
        size_t need = content_length - body.size();
        size_t chunk = std::min(need, sizeof(buf));
        ssize_t nr = read(client_fd, buf, chunk);
        if (nr <= 0) break;
        body.insert(body.end(), buf, buf + nr);
    }

    std::string path = raw_path;
    std::string query;
    size_t qpos = raw_path.find('?');
    if (qpos != std::string::npos) {
        path = raw_path.substr(0, qpos);
        query = raw_path.substr(qpos + 1);
    }

    if (path == "/health") {
        if (method != "GET") {
            send_error(client_fd, 405, "Method Not Allowed");
        } else {
            std::string resp = "{\"status\":\"ok\"}";
            std::map<std::string, std::string> h;
            h["Content-Type"] = "application/json";
            send_response(client_fd, 200, "OK", h, reinterpret_cast<const uint8_t*>(resp.data()), resp.size());
        }
        close(client_fd);
        return;
    }

    if (path == "/run") {
        if (method != "POST") {
            send_error(client_fd, 405, "Method Not Allowed");
            close(client_fd);
            return;
        }

        auto qm = parse_query(query);
        std::string op = qm["op"];
        if (op.empty()) {
            send_error(client_fd, 400, "Missing 'op' parameter");
            close(client_fd);
            return;
        }

        std::string format = qm["format"];
        std::string to = qm["to"];
        std::string mode = qm["mode"];
        std::string q_str = qm["q"];
        std::string effort_str = qm["effort"];
        std::string impl = qm["impl"];
        std::string from_impl = qm["from_impl"];
        if (from_impl.empty()) from_impl = impl;
        std::string to_impl = qm["to_impl"];
        if (to_impl.empty()) to_impl = impl;

        const char* impl_tier = get_implementation_tier();

        if (op == "analyze") {
            std::string err;
            auto pam_img = PamImage::decode(body.data(), body.size(), max_pixels, &err);
            if (!pam_img) {
                send_error(client_fd, 400, "Invalid PAM input: " + err);
                close(client_fd);
                return;
            }

            auto start = std::chrono::steady_clock::now();
            AnalyzeResult res = analyze_image(*pam_img);
            auto end = std::chrono::steady_clock::now();
            int64_t ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();

            std::string json_str = res.to_json(false);
            std::map<std::string, std::string> h;
            h["Content-Type"] = "application/json";
            h["X-Arena-Analyze-Ns"] = std::to_string(ns);
            h["X-Arena-Impl"] = impl_tier;
            send_response(client_fd, 200, "OK", h, reinterpret_cast<const uint8_t*>(json_str.data()), json_str.size());
        }
        else if (op == "encode") {
            if (format.empty()) {
                send_error(client_fd, 400, "Missing 'format' parameter");
                close(client_fd);
                return;
            }
            EncodeParams params;
            std::string err;
            if (!EncodeParams::parse(format, mode, q_str, effort_str, to_impl, &params, &err)) {
                send_error(client_fd, 400, err);
                close(client_fd);
                return;
            }

            auto pam_img = PamImage::decode(body.data(), body.size(), max_pixels, &err);
            if (!pam_img) {
                send_error(client_fd, 400, "Invalid PAM input: " + err);
                close(client_fd);
                return;
            }

            auto start = std::chrono::steady_clock::now();
            std::vector<uint8_t> encoded = encode_image(*pam_img, params, &err);
            auto end = std::chrono::steady_clock::now();
            int64_t ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();

            if (encoded.empty() && !err.empty()) {
                send_error(client_fd, 400, "Encode error: " + err);
                close(client_fd);
                return;
            }

            std::map<std::string, std::string> h;
            h["Content-Type"] = mime_for_format(params.format);
            h["X-Arena-Encode-Ns"] = std::to_string(ns);
            h["X-Arena-Impl"] = impl_tier;
            send_response(client_fd, 200, "OK", h, encoded.data(), encoded.size());
        }
        else if (op == "decode") {
            if (format.empty()) {
                send_error(client_fd, 400, "Missing 'format' parameter");
                close(client_fd);
                return;
            }
            std::string err;
            auto start = std::chrono::steady_clock::now();
            auto pam_img = decode_image(body.data(), body.size(), format, from_impl, max_pixels, &err);
            auto end = std::chrono::steady_clock::now();
            int64_t ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();

            if (!pam_img) {
                send_error(client_fd, 400, "Decode error: " + err);
                close(client_fd);
                return;
            }

            std::vector<uint8_t> pam_bytes = pam_img->encode();
            std::map<std::string, std::string> h;
            h["Content-Type"] = "image/x-netpbm-pam";
            h["X-Arena-Decode-Ns"] = std::to_string(ns);
            h["X-Arena-Impl"] = impl_tier;
            send_response(client_fd, 200, "OK", h, pam_bytes.data(), pam_bytes.size());
        }
        else if (op == "transcode") {
            if (format.empty() || to.empty()) {
                send_error(client_fd, 400, "Missing 'format' or 'to' parameter");
                close(client_fd);
                return;
            }
            EncodeParams params;
            std::string err;
            if (!EncodeParams::parse(to, mode, q_str, effort_str, to_impl, &params, &err)) {
                send_error(client_fd, 400, err);
                close(client_fd);
                return;
            }

            auto start_dec = std::chrono::steady_clock::now();
            auto pam_img = decode_image(body.data(), body.size(), format, from_impl, max_pixels, &err);
            auto end_dec = std::chrono::steady_clock::now();
            int64_t dec_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end_dec - start_dec).count();

            if (!pam_img) {
                send_error(client_fd, 400, "Decode error: " + err);
                close(client_fd);
                return;
            }

            auto start_enc = std::chrono::steady_clock::now();
            std::vector<uint8_t> encoded = encode_image(*pam_img, params, &err);
            auto end_enc = std::chrono::steady_clock::now();
            int64_t enc_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end_enc - start_enc).count();

            if (encoded.empty() && !err.empty()) {
                send_error(client_fd, 400, "Encode error: " + err);
                close(client_fd);
                return;
            }

            std::map<std::string, std::string> h;
            h["Content-Type"] = mime_for_format(params.format);
            h["X-Arena-Decode-Ns"] = std::to_string(dec_ns);
            h["X-Arena-Encode-Ns"] = std::to_string(enc_ns);
            h["X-Arena-Impl"] = impl_tier;
            send_response(client_fd, 200, "OK", h, encoded.data(), encoded.size());
        }
        else {
            send_error(client_fd, 400, "Unknown op: " + op);
        }
        close(client_fd);
        return;
    }

    send_error(client_fd, 404, "Not Found");
    close(client_fd);
}

HttpServer::HttpServer(int port) : port_(port) {}

HttpServer::~HttpServer() {
    stop();
}

void HttpServer::start() {
    server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd_ < 0) {
        std::cerr << "Failed to create socket" << std::endl;
        return;
    }

    int opt = 1;
    setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr;
    std::memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port_);

    if (bind(server_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        std::cerr << "Failed to bind to port " << port_ << std::endl;
        close(server_fd_);
        server_fd_ = -1;
        return;
    }

    if (listen(server_fd_, 128) < 0) {
        std::cerr << "Failed to listen on socket" << std::endl;
        close(server_fd_);
        server_fd_ = -1;
        return;
    }

    running_ = true;
    std::cout << "[arena-server] C++ server listening on port " << port_
              << " (" << get_implementation_tier() << ")" << std::endl;

    // Worker thread pool
    unsigned int num_threads = std::max(4u, std::thread::hardware_concurrency());
    std::queue<int> task_queue;
    std::mutex queue_mutex;
    std::condition_variable cv;
    std::vector<std::thread> workers;

    for (unsigned int i = 0; i < num_threads; ++i) {
        workers.emplace_back([&]() {
            while (true) {
                int client_fd = -1;
                {
                    std::unique_lock<std::mutex> lock(queue_mutex);
                    cv.wait(lock, [&]() { return !running_ || !task_queue.empty(); });
                    if (!running_ && task_queue.empty()) return;
                    client_fd = task_queue.front();
                    task_queue.pop();
                }
                if (client_fd >= 0) {
                    handle_client(client_fd);
                }
            }
        });
    }

    while (running_) {
        sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        int client_fd = accept(server_fd_, reinterpret_cast<sockaddr*>(&client_addr), &client_len);
        if (client_fd < 0) {
            if (!running_) break;
            continue;
        }

        {
            std::lock_guard<std::mutex> lock(queue_mutex);
            task_queue.push(client_fd);
        }
        cv.notify_one();
    }

    {
        std::lock_guard<std::mutex> lock(queue_mutex);
        running_ = false;
    }
    cv.notify_all();
    for (auto& w : workers) {
        if (w.joinable()) w.join();
    }
}

void HttpServer::stop() {
    running_ = false;
    if (server_fd_ >= 0) {
        close(server_fd_);
        server_fd_ = -1;
    }
}

} // namespace arena
