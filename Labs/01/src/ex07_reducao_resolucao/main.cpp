#include "image_utils.h"

#include <algorithm>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    try {
        std::string imagePath = "imagem.jpg";
        int reductionFactor = 4;

        if (argc == 2) {
            imagePath = argv[1];
        } else if (argc >= 3) {
            imagePath = argv[1];
            reductionFactor = std::max(1, std::stoi(argv[2]));
        }

        const cv::Mat original = vc::loadImageOrThrow(imagePath, cv::IMREAD_COLOR);

        const int reducedWidth = std::max(1, original.cols / reductionFactor);
        const int reducedHeight = std::max(1, original.rows / reductionFactor);

        cv::Mat reduced;
        cv::resize(original, reduced, cv::Size(reducedWidth, reducedHeight), 0.0, 0.0, cv::INTER_AREA);

        cv::Mat restored;
        cv::resize(reduced, restored, original.size(), 0.0, 0.0, cv::INTER_NEAREST);

        const auto reducedPath = vc::saveImage(reduced, "ex07_reduzida.png");
        const auto restoredPath = vc::saveImage(restored, "ex07_reampliada.png");

        std::cout << "Fator de reducao: " << reductionFactor << '\n';
        std::cout << "Reducao: INTER_AREA\n";
        std::cout << "Reampliacao: INTER_NEAREST\n";
        std::cout << "Imagem reduzida salva em: " << reducedPath << '\n';
        std::cout << "Imagem reampliada salva em: " << restoredPath << '\n';

        vc::showImage("ex07 - original", original);
        vc::showImage("ex07 - reduzida", reduced);
        vc::showImage("ex07 - reampliada", restored);
        vc::waitForKey();
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "Erro no ex07: " << exception.what() << '\n';
        return 1;
    }
}