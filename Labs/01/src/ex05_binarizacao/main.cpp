#include "image_utils.h"

#include <algorithm>
#include <iostream>
#include <string>

namespace {

bool tryParseInt(const std::string& text, int& value) {
    try {
        std::size_t processed = 0;
        const int parsed = std::stoi(text, &processed);
        if (processed != text.size()) {
            return false;
        }
        value = parsed;
        return true;
    } catch (const std::exception&) {
        return false;
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        std::string imagePath = "imagem.jpg";
        int threshold = 128;

        if (argc == 2) {
            const std::string argument = argv[1];
            if (!tryParseInt(argument, threshold)) {
                imagePath = argument;
            }
        } else if (argc >= 3) {
            imagePath = argv[1];
            if (!tryParseInt(argv[2], threshold)) {
                throw std::runtime_error("Limiar invalido: " + std::string(argv[2]));
            }
        }

        threshold = std::clamp(threshold, 0, 255);

        const cv::Mat gray = vc::loadImageOrThrow(imagePath, cv::IMREAD_GRAYSCALE);
        cv::Mat binary(gray.rows, gray.cols, gray.type());

        for (int row = 0; row < gray.rows; ++row) {
            for (int col = 0; col < gray.cols; ++col) {
                const std::uint8_t value = gray.at<std::uint8_t>(row, col);
                binary.at<std::uint8_t>(row, col) = value >= threshold ? 255 : 0;
            }
        }

        const auto savedPath = vc::saveImage(binary, "ex05_binarizacao.png");

        std::cout << "Limiar utilizado: " << threshold << '\n';
        std::cout << "Imagem binarizada salva em: " << savedPath << '\n';

        vc::showImage("ex05 - original em cinza", gray);
        vc::showImage("ex05 - binarizacao", binary);
        vc::waitForKey();
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "Erro no ex05: " << exception.what() << '\n';
        return 1;
    }
}