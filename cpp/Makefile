CXX ?= g++
CLANGXX ?= clang++

CXXFLAGS_COMMON = -std=c++20 -Iinclude -I.
CXXFLAGS_NATIVE = -O3 -march=native
CXXFLAGS_PORTABLE = -O2 -fno-tree-vectorize -DARENA_PORTABLE

PKG_FLAGS = $(shell pkg-config --cflags --libs libpng16 libturbojpeg libwebp libjxl libjxl_threads dav1d zlib)
PTHREAD_FLAGS = -pthread

BIN_DIR = bin
BUILD_DIR = build

CORE_SRCS = src/pam.cpp src/analyze.cpp src/params.cpp src/codec.cpp
HTTP_SRCS = src/http_server.cpp
PORTABLE_SRCS = $(CORE_SRCS) vendor/lodepng/lodepng.cpp

# Binaries
TARGET_BATCH = $(BIN_DIR)/arena-batch
TARGET_SERVER = $(BIN_DIR)/arena-server
TARGET_BATCH_PORTABLE = $(BIN_DIR)/arena-batch-portable
TARGET_SERVER_PORTABLE = $(BIN_DIR)/arena-server-portable
TARGET_BATCH_CLANG = $(BIN_DIR)/arena-batch-clang
TARGET_SERVER_CLANG = $(BIN_DIR)/arena-server-clang

ALL_TARGETS = $(TARGET_BATCH) $(TARGET_SERVER) \
              $(TARGET_BATCH_PORTABLE) $(TARGET_SERVER_PORTABLE) \
              $(TARGET_BATCH_CLANG) $(TARGET_SERVER_CLANG)

.PHONY: all clean test

all: $(ALL_TARGETS)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

# 1. Accelerated GCC
$(TARGET_BATCH): $(CORE_SRCS) src/cmd/batch.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS_COMMON) $(CXXFLAGS_NATIVE) $(CORE_SRCS) src/cmd/batch.cpp $(PKG_FLAGS) $(PTHREAD_FLAGS) -o $@

$(TARGET_SERVER): $(CORE_SRCS) $(HTTP_SRCS) src/cmd/server.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS_COMMON) $(CXXFLAGS_NATIVE) $(CORE_SRCS) $(HTTP_SRCS) src/cmd/server.cpp $(PKG_FLAGS) $(PTHREAD_FLAGS) -o $@

# 2. Portable GCC
$(TARGET_BATCH_PORTABLE): $(PORTABLE_SRCS) src/cmd/batch.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS_COMMON) $(CXXFLAGS_PORTABLE) $(PORTABLE_SRCS) src/cmd/batch.cpp $(PTHREAD_FLAGS) -o $@

$(TARGET_SERVER_PORTABLE): $(PORTABLE_SRCS) $(HTTP_SRCS) src/cmd/server.cpp | $(BIN_DIR)
	$(CXX) $(CXXFLAGS_COMMON) $(CXXFLAGS_PORTABLE) $(PORTABLE_SRCS) $(HTTP_SRCS) src/cmd/server.cpp $(PTHREAD_FLAGS) -o $@

# 3. Accelerated Clang
$(TARGET_BATCH_CLANG): $(CORE_SRCS) src/cmd/batch.cpp | $(BIN_DIR)
	$(CLANGXX) $(CXXFLAGS_COMMON) $(CXXFLAGS_NATIVE) $(CORE_SRCS) src/cmd/batch.cpp $(PKG_FLAGS) $(PTHREAD_FLAGS) -o $@

$(TARGET_SERVER_CLANG): $(CORE_SRCS) $(HTTP_SRCS) src/cmd/server.cpp | $(BIN_DIR)
	$(CLANGXX) $(CXXFLAGS_COMMON) $(CXXFLAGS_NATIVE) $(CORE_SRCS) $(HTTP_SRCS) src/cmd/server.cpp $(PKG_FLAGS) $(PTHREAD_FLAGS) -o $@

clean:
	rm -rf $(BIN_DIR) $(BUILD_DIR)

test: all
	python3 tests/test_cpp.py
