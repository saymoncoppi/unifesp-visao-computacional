#include "image_utils.h"

#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace {

std::filesystem::path findProjectRoot() {
    auto current = std::filesystem::current_path();

    while (true) {
        if (std::filesystem::exists(current / "CMakeLists.txt")) {
            return current;
        }

        if (current == current.root_path()) {
            break;
        }

        current = current.parent_path();
    }

    return std::filesystem::current_path();
}

std::string matDepthToString(int depth) {
    switch (depth) {
        case CV_8U:
            return "CV_8U";
        case CV_8S:
            return "CV_8S";
        case CV_16U:
            return "CV_16U";
        case CV_16S:
            return "CV_16S";
        case CV_32S:
            return "CV_32S";
        case CV_32F:
            return "CV_32F";
        case CV_64F:
            return "CV_64F";
        default:
            return "desconhecido";
    }
}

}  // namespace

namespace vc {

std::filesystem::path resolveInputPath(const std::string& pathHint) {
    const auto root = findProjectRoot();
    const std::filesystem::path hinted(pathHint);
    std::vector<std::filesystem::path> candidates;

    if (hinted.is_absolute()) {
        candidates.push_back(hinted);
    } else {
        candidates.push_back(std::filesystem::current_path() / hinted);
        candidates.push_back(root / hinted);
        candidates.push_back(root / "imagem.jpg");
        candidates.push_back(std::filesystem::current_path() / "imagem.jpg");
    }

    for (const auto& candidate : candidates) {
        if (std::filesystem::exists(candidate)) {
            return std::filesystem::weakly_canonical(candidate);
        }
    }

    throw std::runtime_error(
        "Nao foi possivel localizar a imagem. Informe um caminho valido ou coloque 'imagem.jpg' na raiz do projeto.");
}

cv::Mat loadImageOrThrow(const std::string& pathHint, int flags) {
    const auto resolvedPath = resolveInputPath(pathHint);
    cv::Mat image = cv::imread(resolvedPath.string(), flags);

    if (image.empty()) {
        throw std::runtime_error("Falha ao carregar a imagem: " + resolvedPath.string());
    }

    return image;
}

cv::Mat toGray(const cv::Mat& image) {
    if (image.channels() == 1) {
        return image.clone();
    }

    cv::Mat gray;
    cv::cvtColor(image, gray, cv::COLOR_BGR2GRAY);
    return gray;
}

void printImageInfo(const cv::Mat& image, const std::string& label) {
    std::cout << label << '\n'
              << "  largura : " << image.cols << '\n'
              << "  altura  : " << image.rows << '\n'
              << "  canais  : " << image.channels() << '\n'
              << "  tipo    : " << matDepthToString(image.depth()) << "\n";
}

void showImage(const std::string& title, const cv::Mat& image) {
    try {
        cv::namedWindow(title, cv::WINDOW_AUTOSIZE);
        cv::imshow(title, image);
    } catch (const cv::Exception& exception) {
        std::cerr << "Aviso: nao foi possivel abrir a janela '" << title
                  << "'. Verifique se a sessao grafica local esta ativa.\nDetalhes: "
                  << exception.what() << '\n';
    }
}

void waitForKey(int delay) {
    try {
        cv::waitKey(delay);
    } catch (const cv::Exception& exception) {
        std::cerr << "Aviso: waitKey falhou. Detalhes: " << exception.what() << '\n';
    }
}

std::filesystem::path ensureOutputDirectory() {
    const auto outputDir = findProjectRoot() / "output";
    std::filesystem::create_directories(outputDir);
    return outputDir;
}

std::filesystem::path saveImage(const cv::Mat& image, const std::string& fileName) {
    const auto outputPath = ensureOutputDirectory() / fileName;

    if (!cv::imwrite(outputPath.string(), image)) {
        throw std::runtime_error("Falha ao salvar a imagem em: " + outputPath.string());
    }

    return outputPath;
}

}  // namespace vc