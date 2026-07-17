#pragma once

#include <opencv2/opencv.hpp>

#include <filesystem>
#include <string>

namespace vc {

std::filesystem::path resolveInputPath(const std::string& pathHint);
cv::Mat loadImageOrThrow(const std::string& pathHint, int flags = cv::IMREAD_COLOR);
cv::Mat toGray(const cv::Mat& image);

void printImageInfo(const cv::Mat& image, const std::string& label = "Imagem");
void showImage(const std::string& title, const cv::Mat& image);
void waitForKey(int delay = 0);

std::filesystem::path ensureOutputDirectory();
std::filesystem::path saveImage(const cv::Mat& image, const std::string& fileName);

}  // namespace vc