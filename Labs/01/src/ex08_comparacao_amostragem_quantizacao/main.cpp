#include "image_utils.h"

#include <algorithm>
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
            quantized.at<std::uint8_t>(row, col) = static_cast<std::uint8_t>(std::lround(bucket * outputScale));
        }
    }

    return quantized;
}

cv::Mat addLabel(const cv::Mat& image, const std::string& label) {
    cv::Mat labeled;
    if (image.channels() == 1) {
        cv::cvtColor(image, labeled, cv::COLOR_GRAY2BGR);
    } else {
        labeled = image.clone();
    }

    cv::rectangle(labeled, cv::Rect(0, 0, labeled.cols, 36), cv::Scalar(0, 0, 0), cv::FILLED);
    cv::putText(labeled, label, cv::Point(10, 24), cv::FONT_HERSHEY_SIMPLEX, 0.7, cv::Scalar(0, 255, 255), 2);
    return labeled;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        std::string imagePath = "imagem.jpg";
        int reductionFactor = 4;
        int levels = 4;

        if (argc == 2) {
            imagePath = argv[1];
        } else if (argc == 3) {
            imagePath = argv[1];
            reductionFactor = std::max(1, std::stoi(argv[2]));
        } else if (argc >= 4) {
            imagePath = argv[1];
            reductionFactor = std::max(1, std::stoi(argv[2]));
            levels = std::max(2, std::stoi(argv[3]));
        }

        const cv::Mat gray = vc::loadImageOrThrow(imagePath, cv::IMREAD_GRAYSCALE);
        const cv::Mat quantizedOnly = quantizeImage(gray, levels);

        cv::Mat sampled;
        cv::resize(gray,
                   sampled,
                   cv::Size(std::max(1, gray.cols / reductionFactor), std::max(1, gray.rows / reductionFactor)),
                   0.0,
                   0.0,
                   cv::INTER_AREA);

        cv::Mat sampledRestored;
        cv::resize(sampled, sampledRestored, gray.size(), 0.0, 0.0, cv::INTER_NEAREST);

        const cv::Mat sampledAndQuantized = quantizeImage(sampledRestored, levels);

        const auto quantizedPath = vc::saveImage(quantizedOnly, "ex08_quantizada.png");
        const auto sampledPath = vc::saveImage(sampledRestored, "ex08_amostrada.png");
        const auto combinedPath = vc::saveImage(sampledAndQuantized, "ex08_amostrada_quantizada.png");

        cv::Mat topRow;
        cv::hconcat(std::vector<cv::Mat>{addLabel(gray, "Original"), addLabel(quantizedOnly, "Quantizada")}, topRow);

        cv::Mat bottomRow;
        cv::hconcat(std::vector<cv::Mat>{addLabel(sampledRestored, "Amostrada"),
                                         addLabel(sampledAndQuantized, "Amostrada + quantizada")},
                    bottomRow);

        cv::Mat panel;
        cv::vconcat(topRow, bottomRow, panel);
        const auto panelPath = vc::saveImage(panel, "ex08_painel_comparacao.png");

        std::cout << "Saida quantizada: " << quantizedPath << '\n';
        std::cout << "Saida amostrada: " << sampledPath << '\n';
        std::cout << "Saida amostrada + quantizada: " << combinedPath << '\n';
        std::cout << "Painel comparativo: " << panelPath << '\n';
        std::cout << "\nAnalise visual curta:\n";
        std::cout << "- Quantizacao reduz os niveis de intensidade e cria faixas tonais mais visiveis.\n";
        std::cout << "- Amostragem reduz detalhes espaciais, deixando bordas mais blocadas apos a reampliacao.\n";
        std::cout << "- A combinacao das duas tecnicas acumula perda tonal e perda espacial ao mesmo tempo.\n";

        vc::showImage("ex08 - comparacao", panel);
        vc::waitForKey();
        return 0;
    } catch (const std::exception& exception) {
        std::cerr << "Erro no ex08: " << exception.what() << '\n';
        return 1;
    }
}