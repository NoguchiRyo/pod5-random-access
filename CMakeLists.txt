cmake_minimum_required(VERSION 3.18)
project(pod5_test CXX)

set(POD5_BUILD_PYTHON OFF CACHE BOOL "Don't build Python bindings")
set(POD5_BUILD_TOOLS OFF CACHE BOOL "Don't build command line tools")
set(POD5_BUILD_EXAMPLES OFF CACHE BOOL "Don't build examples")
set(CPACK_GENERATOR "" CACHE STRING "Disable CPack")  # 追加

if(WIN32)
  set(Python3_FIND_REGISTRY NEVER)
  set(Python_FIND_REGISTRY NEVER)
endif()

add_subdirectory(${CMAKE_SOURCE_DIR}/extern/pybind11)

set(POD5_SUBMODULE_DIR ${CMAKE_SOURCE_DIR}/extern/pod5-file-format)


set(POD5_VERSION_MAJOR 0)
set(POD5_VERSION_MINOR 3)
set(POD5_VERSION_PATCH 27)
set(POD5_VERSION "${POD5_VERSION_MAJOR}.${POD5_VERSION_MINOR}.${POD5_VERSION_PATCH}")

message(STATUS "Creating POD5Version.cmake...")
file(MAKE_DIRECTORY ${POD5_SUBMODULE_DIR}/cmake)
file(WRITE ${POD5_SUBMODULE_DIR}/cmake/POD5Version.cmake
"# Pod5 version information
set(POD5_VERSION_MAJOR ${POD5_VERSION_MAJOR})
set(POD5_VERSION_MINOR ${POD5_VERSION_MINOR})
set(POD5_VERSION_PATCH ${POD5_VERSION_PATCH})
set(POD5_VERSION \"\${POD5_VERSION_MAJOR}.\${POD5_VERSION_MINOR}.\${POD5_VERSION_PATCH}\")
set(POD5_VERSION_STRING \"v\${POD5_VERSION}\")
message(STATUS \"Pod5 version: \${POD5_VERSION}\")
")
set(VERSION_H_DIR "${CMAKE_BINARY_DIR}/extern/pod5-file-format/c++/pod5_format")
set(VERSION_H_FILE "${VERSION_H_DIR}/version.h")

file(MAKE_DIRECTORY ${VERSION_H_DIR})

set(POD5_INCLUDE_DIR ${POD5_SUBMODULE_DIR}/c++/pod5_format/include)
add_subdirectory(${POD5_SUBMODULE_DIR} EXCLUDE_FROM_ALL)
file(WRITE ${VERSION_H_FILE}
"#pragma once
#include <cstdint>
#include <string>

namespace pod5 {
    std::uint16_t const Pod5MajorVersion = ${POD5_VERSION_MAJOR};
    std::uint16_t const Pod5MinorVersion = ${POD5_VERSION_MINOR};
    std::uint16_t const Pod5RevVersion = ${POD5_VERSION_PATCH};
    std::string const Pod5Version = \"${POD5_VERSION}\";
}
")
message(STATUS "Generated version.h: ${VERSION_H_FILE}")
set(POD5_TARGET pod5_format)

add_subdirectory(src)
