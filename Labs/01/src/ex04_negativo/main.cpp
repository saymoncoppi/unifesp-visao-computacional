#include "image_utils.h"

#include <iostream>
#include <string>

int main(int argc, char** argv) {
    try {
        const std::string imagePath = argc > 1 ? argv[1] : "imagem.jpg";
        const cv::Mat gray = vc::loadImageOrThrow(imagePath, cv::IMREAD_GRAYSCALE);

        cv::Mat negative(gray.rows, gray.cols, gray.type());

        for (int row = 0; row < gray.rows; ++row) {
            for (int col = 0; col < gray.cols; ++col) {
                const std::uint8_t value = gray.at<std::uint8_t>(row, col);
                negative.at<std::uint8_t>(row, col) = static_cast<std::uint8_t>(255 - value);
            }
        }

        const auto savedPath = vc::saveImage(negative, "ex04_negativo.png");

        vc::showImage("ex04 - original em cinza", gray);
        vc::showImage("ex04 - negativo", negative);

        std::cout << "Negativo salvo em: " << savedPath << '\n';
        vc::waitForKey();
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "Erro no ex04: " << exception.what() << '\n';
        return 1;
    }
}