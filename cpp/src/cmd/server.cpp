#include "http_server.hpp"
#include <iostream>
#include <cstdlib>
#include <string>

int main(int argc, char* argv[]) {
    int port = 8082;
    const char* env_port = std::getenv("PORT");
    if (env_port && *env_port) {
        port = std::atoi(env_port);
    }

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--port" && i + 1 < argc) {
            port = std::atoi(argv[++i]);
        }
    }

    arena::HttpServer server(port);
    server.start();
    return 0;
}
