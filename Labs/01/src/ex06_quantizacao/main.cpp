#include "image_utils.h"

#include <array>
#include <cmath>
#include <iostream>
#include <string>

namespace {

cv::Mat quantizeImage(const cv::Mat& gray, int levels) {
    cv::Mat quantized(gray.rows, gray.cols, gray.type());
    const double bucketScale = static_cast<double>(levels) / 256.0;
    const double outputScale = levels > 1 ? 255.0 / static_cast<double>(levels - 1) : 0.0;

    for (int row = 0; row < gray.rows; ++row) {
        for (int col = 0; col < gray.cols; ++col) {
            const double value = static_cast<double>(gray.at<std::uint8_t>(row, col));
            const int bucket = std::min(levels - 1, static_cast<int>(std::floor(value * bucketScale)));
            const auto remapped = static_cast<std::uint8_t>(std::lround(bucket * outputScale));
            quantized.at<std::uint8_t>(row, col) = remapped;
        }
    }

    return quantized;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const std::string imagePath = argc > 1 ? argv[1] : "imagem.jpg";
        const cv::Mat gray = vc::loadImageOrThrow(imagePath, cv::IMREAD_GRAYSCALE);
        const std::array<int, 4> levelsList{128, 64, 16, 4};

        vc::showImage("ex06 - original em cinza", gray);

        for (int levels : levelsList) {
            const cv::Mat quantized = quantizeImage(gray, levels);
            const std::string fileName = "ex06_quantizacao_" + std::to_string(levels) + "_niveis.png";
            const auto savedPath = vc::saveImage(quantized, fileName);
            const std::string windowTitle = "ex06 - " + std::to_string(levels) + " niveis";

            vc::showImage(windowTitle, quantized);
            std::cout << levels << " niveis -> " << savedPath << '\n';
        }

        std::cout << "Quantizacao concluida. Pressione qualquer tecla para encerrar o exercicio 6.\n";
        vc::waitForKey();
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "Erro no ex06: " << exception.what() << '\n';
        return 1;
    }
}