#include <opencv2/opencv.hpp>
#include <filesystem>
#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <cmath>

namespace fs = std::filesystem;

// Collect all .jpg paths in a directory, sorted numerically by filename stem
std::vector<fs::path> collectImages(const std::string& dir) {
    std::vector<fs::path> paths;
    for (const auto& entry : fs::directory_iterator(dir)) {
        if (entry.path().extension() == ".jpg")
            paths.push_back(entry.path());
    }
    std::sort(paths.begin(), paths.end(), [](const fs::path& a, const fs::path& b) {
        try { return std::stoi(a.stem()) < std::stoi(b.stem()); }
        catch (...) { return a.stem() < b.stem(); }
    });
    return paths;
}

// Preprocess: grayscale + CLAHE (contraste local) + Gaussian blur
cv::Mat preprocess(const cv::Mat& src) {
    cv::Mat gray, eq, blurred;
    cv::cvtColor(src, gray, cv::COLOR_BGR2GRAY);
    auto clahe = cv::createCLAHE(2.0, cv::Size(8, 8));
    clahe->apply(gray, eq);
    cv::GaussianBlur(eq, blurred, cv::Size(9, 9), 2.0);
    return blurred;
}

// Score a candidate circle: large radius is good, center near image center is good,
// center too close to image border is penalized. Returns negative if circle is rejected.
float scoreCircle(const cv::Vec3f& c, int rows, int cols) {
    float cx = c[0], cy = c[1], r = c[2];
    int shortSide = std::min(rows, cols);

    // Reject if center is within 10% of image edge
    float minMargin = shortSide * 0.10f;
    float distFromEdge = std::min({cx, (float)cols - cx, cy, (float)rows - cy});
    if (distFromEdge < minMargin) return -1.0f;

    // Prefer circles whose centers are closer to the image center
    float centerX = cols / 2.0f, centerY = rows / 2.0f;
    float maxDist = std::sqrt(centerX * centerX + centerY * centerY);
    float distToCenter = std::sqrt((cx - centerX) * (cx - centerX) +
                                   (cy - centerY) * (cy - centerY));
    float centralityFactor = 1.0f - 0.5f * (distToCenter / maxDist);

    return r * centralityFactor;
}

// Collect candidate circles from a single param set
std::vector<cv::Vec3f> runHough(const cv::Mat& prep, int rows, int cols,
                                 double dp, double param1, double param2) {
    int shortSide = std::min(rows, cols);
    int minR    = shortSide / 5;
    int maxR    = (int)(shortSide * 0.55f);
    int minDist = shortSide / 3;

    std::vector<cv::Vec3f> circles;
    cv::HoughCircles(prep, circles, cv::HOUGH_GRADIENT,
                     dp, minDist, param1, param2, minR, maxR);
    return circles;
}

// Find best circle across multiple parameter sets using scoring
bool detectBestCircle(const cv::Mat& prep, int rows, int cols, cv::Vec3f& best) {
    struct Params { double dp, param1, param2; };
    static const std::vector<Params> sets = {
        {1.2, 100, 30},   // A
        {1.0,  80, 25},   // B
        {1.5, 120, 45},   // C
        {1.2,  60, 18},   // D - max sensibilidade
        {1.0,  50, 15},   // E - maximo fallback
    };

    // Gather all candidates from all param sets
    std::vector<cv::Vec3f> allCircles;
    for (const auto& p : sets) {
        auto cs = runHough(prep, rows, cols, p.dp, p.param1, p.param2);
        allCircles.insert(allCircles.end(), cs.begin(), cs.end());
    }
    if (allCircles.empty()) return false;

    // Pick the highest-scoring circle that passes the border filter
    float bestScore = -2.0f;
    bool found = false;
    for (const auto& c : allCircles) {
        float s = scoreCircle(c, rows, cols);
        if (s > bestScore) {
            bestScore = s;
            best = c;
            found = true;
        }
    }

    // If all candidates were near the border, fall back to largest radius globally
    if (bestScore < 0) {
        best = *std::max_element(allCircles.begin(), allCircles.end(),
            [](const cv::Vec3f& a, const cv::Vec3f& b){ return a[2] < b[2]; });
        return true; // flagged as partial by caller via bestScore
    }

    return found;
}

// Draw circle and center on a copy of src
cv::Mat drawResult(const cv::Mat& src, const cv::Vec3f& c, bool detected) {
    cv::Mat out = src.clone();
    if (detected) {
        cv::Point center(cvRound(c[0]), cvRound(c[1]));
        int radius = cvRound(c[2]);
        cv::circle(out, center, radius, cv::Scalar(0, 255, 0), 3);
        cv::circle(out, center, 4,      cv::Scalar(0, 0, 255), -1);
    }
    return out;
}

// Check if the best circle passes the interior test (used to tag partial detections)
bool isInteriorCircle(const cv::Vec3f& c, int rows, int cols) {
    return scoreCircle(c, rows, cols) >= 0;
}

int main(int argc, char** argv) {
    std::string inputDir  = "sel_data";
    std::string outputDir = "output";
    if (argc >= 2) inputDir  = argv[1];
    if (argc >= 3) outputDir = argv[2];

    fs::create_directories(outputDir);

    auto images = collectImages(inputDir);
    std::cout << "Imagens encontradas: " << images.size() << "\n\n";

    int total = 0, nDetected = 0, nPartial = 0, nFailed = 0;

    for (const auto& imgPath : images) {
        cv::Mat src = cv::imread(imgPath.string());
        if (src.empty()) {
            std::cerr << "Erro ao ler: " << imgPath << "\n";
            continue;
        }

        cv::Mat prep = preprocess(src);

        cv::Vec3f best;
        bool found = detectBestCircle(prep, src.rows, src.cols, best);
        bool interior = found && isInteriorCircle(best, src.rows, src.cols);

        std::string stem    = imgPath.stem().string();
        std::string outPath = outputDir + "/" + stem + ".jpg";

        cv::Mat result = drawResult(src, best, found);
        cv::imwrite(outPath, result);

        if (!found) {
            std::cout << "[FALHA ] " << stem << ".jpg | nenhum circulo\n";
            ++nFailed;
        } else if (!interior) {
            std::cout << "[PARCIAL] " << stem << ".jpg"
                      << " | centro=(" << cvRound(best[0]) << "," << cvRound(best[1]) << ")"
                      << " | raio=" << cvRound(best[2]) << " (borda)\n";
            ++nPartial;
        } else {
            std::cout << "[OK    ] " << stem << ".jpg"
                      << " | centro=(" << cvRound(best[0]) << "," << cvRound(best[1]) << ")"
                      << " | raio=" << cvRound(best[2]) << "\n";
            ++nDetected;
        }
        ++total;
    }

    std::cout << "\n=== RESUMO ===\n";
    std::cout << "Detectado corretamente : " << nDetected << "\n";
    std::cout << "Detectado parcialmente  : " << nPartial  << "\n";
    std::cout << "Nao detectado           : " << nFailed   << "\n";
    std::cout << "Total                   : " << total     << "\n";
    std::cout << "Resultados em: " << outputDir << "/\n";
    return 0;
}
