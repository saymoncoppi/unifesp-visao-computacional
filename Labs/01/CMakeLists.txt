cmake_minimum_required(VERSION 3.16)

project(execicios_opencv LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(OpenCV REQUIRED COMPONENTS core imgproc highgui imgcodecs)

message(STATUS "OpenCV version: ${OpenCV_VERSION}")

add_library(common_image_utils STATIC
    src/common/image_utils.cpp
)

target_include_directories(common_image_utils
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/src/common
        ${OpenCV_INCLUDE_DIRS}
)

target_link_libraries(common_image_utils
    PUBLIC
        ${OpenCV_LIBS}
)

function(add_exercise target source_file)
    add_executable(${target} ${source_file})
    target_link_libraries(${target} PRIVATE common_image_utils ${OpenCV_LIBS})
    target_include_directories(${target} PRIVATE ${OpenCV_INCLUDE_DIRS})
endfunction()

add_exercise(ex01_leitura_exibicao src/ex01_leitura_exibicao/main.cpp)
add_exercise(ex02_escala_cinza src/ex02_escala_cinza/main.cpp)
add_exercise(ex03_valor_pixel src/ex03_valor_pixel/main.cpp)
add_exercise(ex04_negativo src/ex04_negativo/main.cpp)
add_exercise(ex05_binarizacao src/ex05_binarizacao/main.cpp)
add_exercise(ex06_quantizacao src/ex06_quantizacao/main.cpp)
add_exercise(ex07_reducao_resolucao src/ex07_reducao_resolucao/main.cpp)
add_exercise(ex08_comparacao_amostragem_quantizacao src/ex08_comparacao_amostragem_quantizacao/main.cpp)