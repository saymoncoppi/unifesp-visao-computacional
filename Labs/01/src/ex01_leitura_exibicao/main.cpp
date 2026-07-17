#include "image_utils.h"

#include <iostream>
#include <string>

int main(int argc, char** argv) {
    try {
        const std::string imagePath = argc > 1 ? argv[1] : "imagem.jpg";
        const cv::Mat image = vc::loadImageOrThrow(imagePath, cv::IMREAD_COLOR);

        vc::printImageInfo(image, "Imagem original");
        vc::showImage("ex01 - imagem original", image);

        std::cout << "Pressione qualquer tecla na janela para encerrar o exercicio 1.\n";
        vc::waitForKey();
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "Erro no ex01: " << exception.what() << '\n';
        return 1;
    }
}