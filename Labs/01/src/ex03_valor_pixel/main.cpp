#include "image_utils.h"

#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

int parseInt(const char* value, const std::string& label) {
    try {
        return std::stoi(value);
    } catch (const std::exception&) {
        throw std::runtime_error("Valor invalido para " + label + ": " + value);
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        std::string imagePath = "imagem.jpg";
        int x = -1;
        int y = -1;

        if (argc == 3) {
            x = parseInt(argv[1], "x");
            y = parseInt(argv[2], "y");
        } else if (argc >= 4) {
            imagePath = argv[1];
            x = parseInt(argv[2], "x");
            y = parseInt(argv[3], "y");
        } else {
            std::cout << "Informe as coordenadas x e y do pixel (coluna linha): ";
            std::cin >> x >> y;
        }

        const cv::Mat gray = vc::loadImageOrThrow(imagePath, cv::IMREAD_GRAYSCALE);

        if (x < 0 || y < 0 || x >= gray.cols || y >= gray.rows) {
            std::cerr << "Coordenadas fora da faixa. Limites validos: x em [0, " << gray.cols - 1
                      << "] e y em [0, " << gray.rows - 1 << "].\n";
            return 1;
        }

        const auto pixelValue = static_cast<int>(gray.at<std::uint8_t>(y, x));

        cv::Mat preview;
        cv::cvtColor(gray, preview, cv::COLOR_GRAY2BGR);
        cv::circle(preview, cv::Point(x, y), 6, cv::Scalar(0, 0, 255), 2);

        const auto savedPath = vc::saveImage(preview, "ex03_pixel_destacado.png");

        std::cout << "Pixel em (x=" << x << ", y=" << y << ") = " << pixelValue << '\n';
        std::cout << "Visualizacao salva em: " << savedPath << '\n';

        vc::showImage("ex03 - pixel destacado", preview);
        vc::waitForKey();
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "Erro no ex03: " << exception.what() << '\n';
        return 1;
    }
}