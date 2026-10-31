cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(adpcm6_test)

# Embed the Phase 1 golden vectors (sim/codec/golden/*.bin) as C arrays at build time.
get_filename_component(GOLDEN_DIR ${CMAKE_CURRENT_LIST_DIR}/../../../sim/codec/golden ABSOLUTE)
set(GEN_H ${CMAKE_CURRENT_BINARY_DIR}/golden.h)

add_custom_command(
  OUTPUT ${GEN_H}
  COMMAND ${CMAKE_COMMAND} -DGOLDEN_DIR=${GOLDEN_DIR} -DGEN_H=${GEN_H}
          -P ${CMAKE_CURRENT_LIST_DIR}/gen_golden.cmake
  DEPENDS ${GOLDEN_DIR}/pcm_in.bin ${GOLDEN_DIR}/adpcm6_enc.bin ${GOLDEN_DIR}/adpcm6_dec.bin
          ${CMAKE_CURRENT_LIST_DIR}/gen_golden.cmake
  COMMENT "Embedding adpcm6 golden vectors")
add_custom_target(golden_header DEPENDS ${GEN_H})

target_sources(app PRIVATE src/main.c ../adpcm6.c)
target_include_directories(app PRIVATE .. ${CMAKE_CURRENT_BINARY_DIR})
add_dependencies(app golden_header)
