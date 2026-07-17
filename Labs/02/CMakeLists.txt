cmake_minimum_required(VERSION 3.10)
project(hough_plates)

set(CMAKE_CXX_STANDARD 17)

find_package(OpenCV REQUIRED)
include_directories(${OpenCV_INCLUDE_DIRS})

add_executable(hough_plates hough_plates.cpp)
target_link_libraries(hough_plates ${OpenCV_LIBS})
