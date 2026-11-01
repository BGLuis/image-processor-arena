#pragma once

#include <string>
#include <cstdint>

namespace arena {

class HttpServer {
public:
    explicit HttpServer(int port);
    ~HttpServer();

    void start();
    void stop();

private:
    int port_;
    int server_fd_ = -1;
    bool running_ = false;
};

} // namespace arena
