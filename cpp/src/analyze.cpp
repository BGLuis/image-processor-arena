#include "analyze.hpp"

#include <cmath>
#include <numeric>
#include <algorithm>
#include <unordered_set>
#include <charconv>
#include <sstream>
#include <cinttypes>

namespace arena {

static const std::string BLURHASH_CHARS =
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~";

static inline uint8_t clamp255(int v) {
    if (v < 0) return 0;
    if (v > 255) return 255;
    return static_cast<uint8_t>(v);
}

static inline double round6(double val) {
    return std::round(val * 1e6) / 1e6;
}

static inline int gcd(int a, int b) {
    while (b != 0) {
        int t = b;
        b = a % b;
        a = t;
    }
    return a;
}

static std::string format_num(double v) {
    char buf[64];
    auto [ptr, ec] = std::to_chars(buf, buf + sizeof(buf), v);
    return std::string(buf, ptr);
}

static double srgb_to_linear(uint8_t value) {
    double v = static_cast<double>(value) / 255.0;
    if (v <= 0.04045) {
        return v / 12.92;
    }
    return std::pow((v + 0.055) / 1.055, 2.4);
}

static int linear_to_srgb(double value) {
    double v = std::max(0.0, std::min(1.0, value));
    if (v <= 0.0031308) {
        return static_cast<int>(v * 12.92 * 255.0 + 0.5);
    }
    return static_cast<int>((1.055 * std::pow(v, 1.0 / 2.4) - 0.055) * 255.0 + 0.5);
}

static double sign_pow(double val, double exp) {
    return std::copysign(std::pow(std::abs(val), exp), val);
}

static std::string encode_base83(int value, int length) {
    int divisor = 1;
    for (int i = 0; i < length - 1; ++i) {
        divisor *= 83;
    }
    std::string res;
    res.reserve(length);
    for (int i = 0; i < length; ++i) {
        int digit = (value / divisor) % 83;
        divisor /= 83;
        res += BLURHASH_CHARS[digit];
    }
    return res;
}

std::string compute_phash(const std::vector<uint8_t>& y_pixels, int width, int height) {
    // 1. Continuous area-average resize to 32x32
    double I[32][32] = {{0.0}};
    double sw = static_cast<double>(width) / 32.0;
    double sh = static_cast<double>(height) / 32.0;

    for (int v = 0; v < 32; ++v) {
        double y0 = static_cast<double>(v) * sh;
        double y1 = static_cast<double>(v + 1) * sh;
        int syMin = static_cast<int>(std::floor(y0));
        int syMax = static_cast<int>(std::ceil(y1));
        if (syMax > height) syMax = height;

        for (int u = 0; u < 32; ++u) {
            double x0 = static_cast<double>(u) * sw;
            double x1 = static_cast<double>(u + 1) * sw;
            int sxMin = static_cast<int>(std::floor(x0));
            int sxMax = static_cast<int>(std::ceil(x1));
            if (sxMax > width) sxMax = width;

            double total = 0.0;
            double totalWeight = 0.0;
            for (int py = syMin; py < syMax; ++py) {
                double wy = std::max(0.0, std::min(static_cast<double>(py) + 1.0, y1) - std::max(static_cast<double>(py), y0));
                int rowOff = py * width;
                for (int px = sxMin; px < sxMax; ++px) {
                    double wx = std::max(0.0, std::min(static_cast<double>(px) + 1.0, x1) - std::max(static_cast<double>(px), x0));
                    double w = wx * wy;
                    total += static_cast<double>(y_pixels[rowOff + px]) * w;
                    totalWeight += w;
                }
            }
            if (totalWeight > 0.0) {
                I[v][u] = total / totalWeight;
            }
        }
    }

    // 2. 2D DCT-II for 8x8 low-frequency submatrix
    double cosTab[8][32];
    for (int k = 0; k < 8; ++k) {
        for (int n = 0; n < 32; ++n) {
            cosTab[k][n] = std::cos(M_PI * static_cast<double>(2 * n + 1) * static_cast<double>(k) / 64.0);
        }
    }

    double D[8][8] = {{0.0}};
    for (int v = 0; v < 8; ++v) {
        for (int u = 0; u < 8; ++u) {
            double s = 0.0;
            for (int y = 0; y < 32; ++y) {
                double cosY = cosTab[v][y];
                for (int x = 0; x < 32; ++x) {
                    double cosX = cosTab[u][x];
                    s += I[y][x] * cosX * cosY;
                }
            }
            if (std::abs(s) < 1e-6) {
                s = 0.0;
            }
            D[v][u] = s;
        }
    }

    // 3. Exclude DC (0,0) -> C[0,0] = 0.0
    double coeffs[64];
    int idx = 0;
    for (int v = 0; v < 8; ++v) {
        for (int u = 0; u < 8; ++u) {
            if (u == 0 && v == 0) {
                coeffs[idx] = 0.0;
            } else {
                coeffs[idx] = D[v][u];
            }
            idx++;
        }
    }

    // 4. Median of the 64 coefficients
    double sortedCoeffs[64];
    std::copy(coeffs, coeffs + 64, sortedCoeffs);
    std::sort(sortedCoeffs, sortedCoeffs + 64);
    double median = (sortedCoeffs[31] + sortedCoeffs[32]) / 2.0;

    // 5. Construct 64-bit hash (MSB at index 0)
    uint64_t hashVal = 0;
    for (int i = 0; i < 64; ++i) {
        if (coeffs[i] > median) {
            hashVal |= (1ULL << (63 - i));
        }
    }

    char hexBuf[32];
    std::snprintf(hexBuf, sizeof(hexBuf), "%016" PRIx64, hashVal);
    return std::string(hexBuf);
}

std::string compute_blurhash(const std::vector<uint8_t>& r_pixels,
                             const std::vector<uint8_t>& g_pixels,
                             const std::vector<uint8_t>& b_pixels,
                             int width, int height,
                             int x_comp, int y_comp) {
    double linear[256];
    for (int v = 0; v < 256; ++v) {
        linear[v] = srgb_to_linear(static_cast<uint8_t>(v));
    }

    std::vector<std::vector<double>> cosX(x_comp, std::vector<double>(width));
    for (int k = 0; k < x_comp; ++k) {
        for (int n = 0; n < width; ++n) {
            cosX[k][n] = std::cos(M_PI * static_cast<double>(k * n) / static_cast<double>(width));
        }
    }

    std::vector<std::vector<double>> cosY(y_comp, std::vector<double>(height));
    for (int k = 0; k < y_comp; ++k) {
        for (int n = 0; n < height; ++n) {
            cosY[k][n] = std::cos(M_PI * static_cast<double>(k * n) / static_cast<double>(height));
        }
    }

    struct Factor { double r, g, b; };
    std::vector<std::vector<Factor>> factors(y_comp, std::vector<Factor>(x_comp));

    for (int y = 0; y < y_comp; ++y) {
        for (int x = 0; x < x_comp; ++x) {
            double norm = (x == 0 && y == 0) ? 1.0 : 2.0;
            double rAcc = 0.0, gAcc = 0.0, bAcc = 0.0;
            for (int py = 0; py < height; ++py) {
                double cy = cosY[y][py];
                int rowOff = py * width;
                for (int px = 0; px < width; ++px) {
                    double basis = cosX[x][px] * cy;
                    int pidx = rowOff + px;
                    rAcc += basis * linear[r_pixels[pidx]];
                    gAcc += basis * linear[g_pixels[pidx]];
                    bAcc += basis * linear[b_pixels[pidx]];
                }
            }
            double scale = norm / static_cast<double>(width * height);
            factors[y][x] = Factor{rAcc * scale, gAcc * scale, bAcc * scale};
        }
    }

    Factor dc = factors[0][0];
    std::vector<Factor> ac;
    ac.reserve(x_comp * y_comp - 1);
    for (int y = 0; y < y_comp; ++y) {
        for (int x = 0; x < x_comp; ++x) {
            if (x != 0 || y != 0) {
                ac.push_back(factors[y][x]);
            }
        }
    }

    int sizeFlag = (x_comp - 1) + (y_comp - 1) * 9;
    std::string res = encode_base83(sizeFlag, 1);

    double maxVal = 1.0;
    if (!ac.empty()) {
        double actualMax = 0.0;
        for (const auto& comp : ac) {
            actualMax = std::max(actualMax, std::abs(comp.r));
            actualMax = std::max(actualMax, std::abs(comp.g));
            actualMax = std::max(actualMax, std::abs(comp.b));
        }
        int quantMax = static_cast<int>(std::floor(actualMax * 166.0 - 0.5));
        if (quantMax < 0) quantMax = 0;
        else if (quantMax > 82) quantMax = 82;
        maxVal = static_cast<double>(quantMax + 1) / 166.0;
        res += encode_base83(quantMax, 1);
    } else {
        res += encode_base83(0, 1);
    }

    // DC component (24-bit sRGB)
    int dcR = linear_to_srgb(dc.r);
    int dcG = linear_to_srgb(dc.g);
    int dcB = linear_to_srgb(dc.b);
    int dcVal = (dcR << 16) + (dcG << 8) + dcB;
    res += encode_base83(dcVal, 4);

    // AC components
    for (const auto& comp : ac) {
        int qr = static_cast<int>(std::floor(sign_pow(comp.r / maxVal, 0.5) * 9.0 + 9.5));
        if (qr < 0) qr = 0; else if (qr > 18) qr = 18;

        int qg = static_cast<int>(std::floor(sign_pow(comp.g / maxVal, 0.5) * 9.0 + 9.5));
        if (qg < 0) qg = 0; else if (qg > 18) qg = 18;

        int qb = static_cast<int>(std::floor(sign_pow(comp.b / maxVal, 0.5) * 9.0 + 9.5));
        if (qb < 0) qb = 0; else if (qb > 18) qb = 18;

        res += encode_base83(qr * 361 + qg * 19 + qb, 2);
    }

    return res;
}

AnalyzeResult analyze_image(const PamImage& img) {
    int width = img.width;
    int height = img.height;
    int depth = img.depth;
    size_t numPixels = static_cast<size_t>(width) * height;
    double nF = static_cast<double>(numPixels);

    std::vector<uint8_t> rList(numPixels);
    std::vector<uint8_t> gList(numPixels);
    std::vector<uint8_t> bList(numPixels);
    std::vector<uint8_t> aList(numPixels, 255);

    const uint8_t* raster = img.data.data();
    if (depth == 3) {
        for (size_t i = 0; i < numPixels; ++i) {
            size_t off = i * 3;
            rList[i] = raster[off];
            gList[i] = raster[off + 1];
            bList[i] = raster[off + 2];
        }
    } else if (depth == 4) {
        for (size_t i = 0; i < numPixels; ++i) {
            size_t off = i * 4;
            rList[i] = raster[off];
            gList[i] = raster[off + 1];
            bList[i] = raster[off + 2];
            aList[i] = raster[off + 3];
        }
    }

    // 1. Aspect Ratio
    int g = gcd(width, height);
    AspectRatio aspectRatio;
    aspectRatio.str = std::to_string(width / g) + ":" + std::to_string(height / g);
    aspectRatio.val = static_cast<double>(width) / static_cast<double>(height);

    // 2. Block Alignment for b in {8, 16, 64, 256}
    auto compute_block = [&](int b) -> BlockInfo {
        int fullW = (width / b) * b;
        int fullH = (height / b) * b;
        int partialPix = static_cast<int>(numPixels) - (fullW * fullH);
        return BlockInfo{
            width % b,
            height % b,
            partialPix,
            static_cast<double>(partialPix) / nF
        };
    };

    BlockAlignment blockAlignment{
        compute_block(8),
        compute_block(16),
        compute_block(64),
        compute_block(256)
    };

    // 3. BT.601 integer conversion to Y, Cb, Cr
    std::vector<uint8_t> yList(numPixels);
    std::vector<uint8_t> cbList(numPixels);
    std::vector<uint8_t> crList(numPixels);

    int64_t sumY = 0;
    int64_t sumR = 0, sumG = 0, sumB = 0;

    for (size_t i = 0; i < numPixels; ++i) {
        int r = rList[i];
        int gc = gList[i];
        int b = bList[i];

        sumR += r;
        sumG += gc;
        sumB += b;

        int yVal = (77 * r + 150 * gc + 29 * b + 128) >> 8;
        int cbVal = (((-43 * r - 85 * gc + 128 * b + 128) >> 8) + 128);
        int crVal = (((128 * r - 107 * gc - 21 * b + 128) >> 8) + 128);

        uint8_t y = clamp255(yVal);
        uint8_t cb = clamp255(cbVal);
        uint8_t cr = clamp255(crVal);

        yList[i] = y;
        cbList[i] = cb;
        crList[i] = cr;
        sumY += y;
    }

    double meanY = static_cast<double>(sumY) / nF;

    // 4. Shannon Entropy of Y
    int histY[256] = {0};
    for (uint8_t yv : yList) {
        histY[yv]++;
    }
    double entropyY = 0.0;
    for (int cnt : histY) {
        if (cnt > 0) {
            double p = static_cast<double>(cnt) / nF;
            entropyY -= p * std::log2(p);
        }
    }

    // 5. Horizontal Residual Entropy of Y
    double entropyResidualY = 0.0;
    if (width > 1) {
        int diffCounts[511] = {0};
        double totalDiffs = static_cast<double>((width - 1) * height);
        for (int yIdx = 0; yIdx < height; ++yIdx) {
            int rowOff = yIdx * width;
            for (int xIdx = 1; xIdx < width; ++xIdx) {
                int diff = static_cast<int>(yList[rowOff + xIdx]) - static_cast<int>(yList[rowOff + xIdx - 1]);
                diffCounts[diff + 255]++;
            }
        }
        for (int cnt : diffCounts) {
            if (cnt > 0) {
                double p = static_cast<double>(cnt) / totalDiffs;
                entropyResidualY -= p * std::log2(p);
            }
        }
    }

    // 6. Sobel, SI, Gradient Energy, Laplacian Variance, and Chroma Gradient
    double spatialInformation = 0.0;
    double gradientEnergy = 0.0;
    double laplacianVariance = 0.0;
    double chromaGradientEnergy = 0.0;
    double chromaGradientRatio = 0.0;

    int nValid = (width - 2) * (height - 2);
    if (width > 2 && height > 2) {
        std::vector<double> sobelMList(nValid);
        std::vector<double> laplacianList(nValid);

        double sumSobelM = 0.0;
        double sumMagSq = 0.0;
        double sumLap = 0.0;
        double sumMagSqCb = 0.0;
        double sumMagSqCr = 0.0;

        int vIdx = 0;
        for (int yIdx = 1; yIdx < height - 1; ++yIdx) {
            int yPrev = (yIdx - 1) * width;
            int yCurr = yIdx * width;
            int yNext = (yIdx + 1) * width;

            for (int xIdx = 1; xIdx < width - 1; ++xIdx) {
                // Y Sobel
                int gx = (static_cast<int>(yList[yPrev + xIdx + 1]) + 2 * static_cast<int>(yList[yCurr + xIdx + 1]) + static_cast<int>(yList[yNext + xIdx + 1])) -
                         (static_cast<int>(yList[yPrev + xIdx - 1]) + 2 * static_cast<int>(yList[yCurr + xIdx - 1]) + static_cast<int>(yList[yNext + xIdx - 1]));
                int gy = (static_cast<int>(yList[yNext + xIdx - 1]) + 2 * static_cast<int>(yList[yNext + xIdx]) + static_cast<int>(yList[yNext + xIdx + 1])) -
                         (static_cast<int>(yList[yPrev + xIdx - 1]) + 2 * static_cast<int>(yList[yPrev + xIdx]) + static_cast<int>(yList[yPrev + xIdx + 1]));

                double magSq = static_cast<double>(gx * gx + gy * gy);
                double mag = std::sqrt(magSq);
                sobelMList[vIdx] = mag;
                sumSobelM += mag;
                sumMagSq += magSq;

                // 4-neighbor Laplacian
                int lap = static_cast<int>(yList[yCurr + xIdx + 1]) +
                          static_cast<int>(yList[yCurr + xIdx - 1]) +
                          static_cast<int>(yList[yNext + xIdx]) +
                          static_cast<int>(yList[yPrev + xIdx]) -
                          4 * static_cast<int>(yList[yCurr + xIdx]);
                double lapF = static_cast<double>(lap);
                laplacianList[vIdx] = lapF;
                sumLap += lapF;

                // Cb Sobel
                int gxCb = (static_cast<int>(cbList[yPrev + xIdx + 1]) + 2 * static_cast<int>(cbList[yCurr + xIdx + 1]) + static_cast<int>(cbList[yNext + xIdx + 1])) -
                           (static_cast<int>(cbList[yPrev + xIdx - 1]) + 2 * static_cast<int>(cbList[yCurr + xIdx - 1]) + static_cast<int>(cbList[yNext + xIdx - 1]));
                int gyCb = (static_cast<int>(cbList[yNext + xIdx - 1]) + 2 * static_cast<int>(cbList[yNext + xIdx]) + static_cast<int>(cbList[yNext + xIdx + 1])) -
                           (static_cast<int>(cbList[yPrev + xIdx - 1]) + 2 * static_cast<int>(cbList[yPrev + xIdx]) + static_cast<int>(cbList[yPrev + xIdx + 1]));
                sumMagSqCb += static_cast<double>(gxCb * gxCb + gyCb * gyCb);

                // Cr Sobel
                int gxCr = (static_cast<int>(crList[yPrev + xIdx + 1]) + 2 * static_cast<int>(crList[yCurr + xIdx + 1]) + static_cast<int>(crList[yNext + xIdx + 1])) -
                           (static_cast<int>(crList[yPrev + xIdx - 1]) + 2 * static_cast<int>(crList[yCurr + xIdx - 1]) + static_cast<int>(crList[yNext + xIdx - 1]));
                int gyCr = (static_cast<int>(crList[yNext + xIdx - 1]) + 2 * static_cast<int>(crList[yNext + xIdx]) + static_cast<int>(crList[yNext + xIdx + 1])) -
                           (static_cast<int>(crList[yPrev + xIdx - 1]) + 2 * static_cast<int>(crList[yPrev + xIdx]) + static_cast<int>(crList[yPrev + xIdx + 1]));
                sumMagSqCr += static_cast<double>(gxCr * gxCr + gyCr * gyCr);

                vIdx++;
            }
        }

        double nV = static_cast<double>(nValid);
        double meanM = sumSobelM / nV;
        double varM = 0.0;
        for (double m : sobelMList) {
            double diff = m - meanM;
            varM += diff * diff;
        }
        spatialInformation = std::sqrt(varM / nV);
        gradientEnergy = sumMagSq / nV;

        double meanLap = sumLap / nV;
        double varLap = 0.0;
        for (double l : laplacianList) {
            double diff = l - meanLap;
            varLap += diff * diff;
        }
        laplacianVariance = varLap / nV;

        double chromaGeCb = sumMagSqCb / nV;
        double chromaGeCr = sumMagSqCr / nV;
        chromaGradientEnergy = chromaGeCb + chromaGeCr;
        if (gradientEnergy > 0.0) {
            chromaGradientRatio = chromaGradientEnergy / gradientEnergy;
        }
    }

    // 7. Color Variance
    double meanR = static_cast<double>(sumR) / nF;
    double meanG = static_cast<double>(sumG) / nF;
    double meanB = static_cast<double>(sumB) / nF;

    double varR = 0.0, varG = 0.0, varB = 0.0;
    for (size_t i = 0; i < numPixels; ++i) {
        double dr = static_cast<double>(rList[i]) - meanR;
        double dg = static_cast<double>(gList[i]) - meanG;
        double db = static_cast<double>(bList[i]) - meanB;
        varR += dr * dr;
        varG += dg * dg;
        varB += db * db;
    }
    varR /= nF;
    varG /= nF;
    varB /= nF;
    double varSum = varR + varG + varB;

    // 8. Unique Colors
    size_t initCap = std::min<size_t>(numPixels, 65536);
    std::unordered_set<uint32_t> uniqueSet;
    uniqueSet.reserve(initCap);
    for (size_t i = 0; i < numPixels; ++i) {
        uint32_t key = (static_cast<uint32_t>(rList[i]) << 24) |
                       (static_cast<uint32_t>(gList[i]) << 16) |
                       (static_cast<uint32_t>(bList[i]) << 8) |
                       static_cast<uint32_t>(aList[i]);
        uniqueSet.insert(key);
    }
    int uniqueColors = static_cast<int>(uniqueSet.size());

    // 9. Alpha Metrics
    bool hasAlpha = (depth == 4);
    double alphaSparsity = 0.0;
    double alphaBinarity = 1.0;
    if (hasAlpha) {
        int zeroCnt = 0;
        int binCnt = 0;
        for (uint8_t a : aList) {
            if (a == 0) zeroCnt++;
            if (a == 0 || a == 255) binCnt++;
        }
        alphaSparsity = static_cast<double>(zeroCnt) / nF;
        alphaBinarity = static_cast<double>(binCnt) / nF;
    }

    // 10. Adequacy 4:2:0 - 2x2 Roundtrip MSE
    double sumSqErrCb = 0.0, sumSqErrCr = 0.0;
    for (int by = 0; by < height; by += 2) {
        for (int bx = 0; bx < width; bx += 2) {
            uint8_t bCb[4];
            uint8_t bCr[4];
            int k = 0;
            for (int dy = 0; dy < 2; ++dy) {
                int py = by + dy;
                if (py >= height) continue;
                int rowOff = py * width;
                for (int dx = 0; dx < 2; ++dx) {
                    int px = bx + dx;
                    if (px >= width) continue;
                    bCb[k] = cbList[rowOff + px];
                    bCr[k] = crList[rowOff + px];
                    k++;
                }
            }
            if (k > 0) {
                double sumCb = 0.0, sumCr = 0.0;
                for (int i = 0; i < k; ++i) {
                    sumCb += static_cast<double>(bCb[i]);
                    sumCr += static_cast<double>(bCr[i]);
                }
                double avgCb = sumCb / static_cast<double>(k);
                double avgCr = sumCr / static_cast<double>(k);
                for (int i = 0; i < k; ++i) {
                    double dCb = static_cast<double>(bCb[i]) - avgCb;
                    double dCr = static_cast<double>(bCr[i]) - avgCr;
                    sumSqErrCb += dCb * dCb;
                    sumSqErrCr += dCr * dCr;
                }
            }
        }
    }
    double mseCb = sumSqErrCb / nF;
    double mseCr = sumSqErrCr / nF;
    double mseChroma = (mseCb + mseCr) / 2.0;

    // 11. Flat Area Fraction (8x8 blocks with Var(Y) < 16.0)
    int blocksX = width / 8;
    int blocksY = height / 8;
    int totalCompleteBlocks = blocksX * blocksY;
    double flatArea = 1.0;
    if (totalCompleteBlocks > 0) {
        int flatBlocksCount = 0;
        for (int by = 0; by < blocksY; ++by) {
            for (int bx = 0; bx < blocksX; ++bx) {
                int sumBlockY = 0;
                for (int dy = 0; dy < 8; ++dy) {
                    int rowOff = (by * 8 + dy) * width;
                    int bStart = bx * 8;
                    for (int dx = 0; dx < 8; ++dx) {
                        sumBlockY += static_cast<int>(yList[rowOff + bStart + dx]);
                    }
                }
                double blockMean = static_cast<double>(sumBlockY) / 64.0;
                double blockVar = 0.0;
                for (int dy = 0; dy < 8; ++dy) {
                    int rowOff = (by * 8 + dy) * width;
                    int bStart = bx * 8;
                    for (int dx = 0; dx < 8; ++dx) {
                        double diff = static_cast<double>(yList[rowOff + bStart + dx]) - blockMean;
                        blockVar += diff * diff;
                    }
                }
                blockVar /= 64.0;
                if (blockVar < 16.0) {
                    flatBlocksCount++;
                }
            }
        }
        flatArea = static_cast<double>(flatBlocksCount) / static_cast<double>(totalCompleteBlocks);
    }

    // 12. Dominant Color (12-bit RGB histogram)
    int hist12bit[4096] = {0};
    for (size_t i = 0; i < numPixels; ++i) {
        int r4 = rList[i] >> 4;
        int g4 = gList[i] >> 4;
        int b4 = bList[i] >> 4;
        int bidx = (r4 << 8) | (g4 << 4) | b4;
        hist12bit[bidx]++;
    }
    int dominantBin = 0;
    int maxCount = -1;
    for (int idx = 0; idx < 4096; ++idx) {
        if (hist12bit[idx] > maxCount) {
            maxCount = hist12bit[idx];
            dominantBin = idx;
        }
    }
    int r4Dom = (dominantBin >> 8) & 0xF;
    int g4Dom = (dominantBin >> 4) & 0xF;
    int b4Dom = dominantBin & 0xF;
    DominantColor dominantColor;
    dominantColor.dominant_rgb[0] = r4Dom * 17;
    dominantColor.dominant_rgb[1] = g4Dom * 17;
    dominantColor.dominant_rgb[2] = b4Dom * 17;
    dominantColor.dominant_bin = dominantBin;
    dominantColor.mean_rgb[0] = round6(meanR);
    dominantColor.mean_rgb[1] = round6(meanG);
    dominantColor.mean_rgb[2] = round6(meanB);

    // 13. pHash 64-bit
    std::string phashStr = compute_phash(yList, width, height);

    // 14. BlurHash
    std::string blurhashStr = compute_blurhash(rList, gList, bList, width, height, 4, 3);

    AnalyzeResult res;
    res.width = width;
    res.height = height;
    res.aspect_ratio = aspectRatio;
    res.block_alignment = blockAlignment;
    res.mean_y = round6(meanY);
    res.entropy_y = round6(entropyY);
    res.entropy_residual_y = round6(entropyResidualY);
    res.spatial_information = round6(spatialInformation);
    res.gradient_energy = round6(gradientEnergy);
    res.laplacian_variance = round6(laplacianVariance);
    res.color_variance = ColorVariance{round6(varR), round6(varG), round6(varB), round6(varSum)};
    res.unique_colors = uniqueColors;
    res.alpha = AlphaMetrics{hasAlpha, round6(alphaSparsity), round6(alphaBinarity)};
    res.adequacy_420 = Adequacy420{
        round6(chromaGradientEnergy),
        round6(chromaGradientRatio),
        round6(mseCb),
        round6(mseCr),
        round6(mseChroma)
    };
    res.flat_area = round6(flatArea);
    res.dominant_color = dominantColor;
    res.phash = phashStr;
    res.blurhash = blurhashStr;

    return res;
}

std::string AnalyzeResult::to_json(bool pretty) const {
    std::ostringstream ss;
    std::string nl = pretty ? "\n" : "";
    std::string i1 = pretty ? "  " : "";
    std::string i2 = pretty ? "    " : "";
    std::string i3 = pretty ? "      " : "";
    std::string sp = pretty ? " " : "";

    auto fmt_block = [&](const BlockInfo& b) -> std::string {
        std::ostringstream bs;
        bs << "{" << nl
           << i3 << "\"w_mod\":" << sp << b.w_mod << "," << nl
           << i3 << "\"h_mod\":" << sp << b.h_mod << "," << nl
           << i3 << "\"partial_pixels\":" << sp << b.partial_pixels << "," << nl
           << i3 << "\"partial_pct\":" << sp << format_num(b.partial_pct) << nl
           << i2 << "}";
        return bs.str();
    };

    ss << "{" << nl
       << i1 << "\"width\":" << sp << width << "," << nl
       << i1 << "\"height\":" << sp << height << "," << nl
       << i1 << "\"aspect_ratio\":" << sp << "{" << nl
       << i2 << "\"str\":" << sp << "\"" << aspect_ratio.str << "\"," << nl
       << i2 << "\"float\":" << sp << format_num(aspect_ratio.val) << nl
       << i1 << "}," << nl
       << i1 << "\"block_alignment\":" << sp << "{" << nl
       << i2 << "\"b8\":" << sp << fmt_block(block_alignment.b8) << "," << nl
       << i2 << "\"b16\":" << sp << fmt_block(block_alignment.b16) << "," << nl
       << i2 << "\"b64\":" << sp << fmt_block(block_alignment.b64) << "," << nl
       << i2 << "\"b256\":" << sp << fmt_block(block_alignment.b256) << nl
       << i1 << "}," << nl
       << i1 << "\"mean_y\":" << sp << format_num(mean_y) << "," << nl
       << i1 << "\"entropy_y\":" << sp << format_num(entropy_y) << "," << nl
       << i1 << "\"entropy_residual_y\":" << sp << format_num(entropy_residual_y) << "," << nl
       << i1 << "\"spatial_information\":" << sp << format_num(spatial_information) << "," << nl
       << i1 << "\"gradient_energy\":" << sp << format_num(gradient_energy) << "," << nl
       << i1 << "\"laplacian_variance\":" << sp << format_num(laplacian_variance) << "," << nl
       << i1 << "\"color_variance\":" << sp << "{" << nl
       << i2 << "\"var_r\":" << sp << format_num(color_variance.var_r) << "," << nl
       << i2 << "\"var_g\":" << sp << format_num(color_variance.var_g) << "," << nl
       << i2 << "\"var_b\":" << sp << format_num(color_variance.var_b) << "," << nl
       << i2 << "\"var_sum\":" << sp << format_num(color_variance.var_sum) << nl
       << i1 << "}," << nl
       << i1 << "\"unique_colors\":" << sp << unique_colors << "," << nl
       << i1 << "\"alpha\":" << sp << "{" << nl
       << i2 << "\"has_alpha\":" << sp << (alpha.has_alpha ? "true" : "false") << "," << nl
       << i2 << "\"sparsity\":" << sp << format_num(alpha.sparsity) << "," << nl
       << i2 << "\"binarity\":" << sp << format_num(alpha.binarity) << nl
       << i1 << "}," << nl
       << i1 << "\"adequacy_420\":" << sp << "{" << nl
       << i2 << "\"chroma_gradient_energy\":" << sp << format_num(adequacy_420.chroma_gradient_energy) << "," << nl
       << i2 << "\"chroma_gradient_ratio\":" << sp << format_num(adequacy_420.chroma_gradient_ratio) << "," << nl
       << i2 << "\"mse_cb\":" << sp << format_num(adequacy_420.mse_cb) << "," << nl
       << i2 << "\"mse_cr\":" << sp << format_num(adequacy_420.mse_cr) << "," << nl
       << i2 << "\"mse_chroma\":" << sp << format_num(adequacy_420.mse_chroma) << nl
       << i1 << "}," << nl
       << i1 << "\"flat_area\":" << sp << format_num(flat_area) << "," << nl
       << i1 << "\"dominant_color\":" << sp << "{" << nl
       << i2 << "\"dominant_rgb\":" << sp << "[" << dominant_color.dominant_rgb[0] << "," << sp
                                                  << dominant_color.dominant_rgb[1] << "," << sp
                                                  << dominant_color.dominant_rgb[2] << "]," << nl
       << i2 << "\"dominant_bin\":" << sp << dominant_color.dominant_bin << "," << nl
       << i2 << "\"mean_rgb\":" << sp << "[" << format_num(dominant_color.mean_rgb[0]) << "," << sp
                                              << format_num(dominant_color.mean_rgb[1]) << "," << sp
                                              << format_num(dominant_color.mean_rgb[2]) << "]" << nl
       << i1 << "}," << nl
       << i1 << "\"phash\":" << sp << "\"" << phash << "\"," << nl
       << i1 << "\"blurhash\":" << sp << "\"" << blurhash << "\"" << nl
       << "}";

    return ss.str();
}

} // namespace arena
