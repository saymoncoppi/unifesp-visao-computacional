#include "image_utils.h"

#include <iostream>
#include <string>

int main(int argc, char** argv) {
    try {
        const std::string imagePath = argc > 1 ? argv[1] : "imagem.jpg";
        const cv::Mat original = vc::loadImageOrThrow(imagePath, cv::IMREAD_COLOR);
        const cv::Mat gray = vc::toGray(original);

        const auto savedPath = vc::saveImage(gray, "ex02_escala_cinza.png");

        vc::printImageInfo(original, "Imagem original");
        vc::printImageInfo(gray, "Imagem em escala de cinza");
        vc::showImage("ex02 - original", original);
        vc::showImage("ex02 - escala de cinza", gray);

        std::cout << "Imagem em cinza salva em: " << savedPath << '\n';
        std::cout << "Pressione qualquer tecla em uma das janelas para encerrar o exercicio 2.\n";
        vc::waitForKey();
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "Erro no ex02: " << exception.what() << '\n';
        return 1;
    }
}