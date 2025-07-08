set(SOURCES
    py_pod5.cpp
    pod5_signal_index.cpp
)

pybind11_add_module(
    pod5_random_access_pybind
    ${SOURCES}
)

target_include_directories(pod5_random_access_pybind PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)


target_link_libraries(pod5_random_access_pybind PRIVATE
    pybind11::module
    ${POD5_TARGET}
)

set(PYTHON_MODULE_INSTALL_DIR "${CMAKE_SOURCE_DIR}/pod5_random_access")

message(STATUS "CMAKE_SOURCE_DIR: ${CMAKE_SOURCE_DIR}")
message(STATUS "PYTHON_MODULE_INSTALL_DIR: ${PYTHON_MODULE_INSTALL_DIR}")

install(TARGETS pod5_random_access_pybind
    DESTINATION ${PYTHON_MODULE_INSTALL_DIR}
    RUNTIME DESTINATION ${PYTHON_MODULE_INSTALL_DIR}
    LIBRARY DESTINATION ${PYTHON_MODULE_INSTALL_DIR}
)


if(WIN32)
  if(DEFINED VCPKG_TOOLCHAIN)
    set(VCPKG_INSTALLED_DIR "${VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}")

    set(REQUIRED_DLLS
            "arrow.dll"
            "brotlienc.dll"
            "brotlidec.dll"
            "bz2.dll"
            "lz4.dll"
            "snappy.dll"
            "zstd.dll"
            "zlib1.dll"
            "brotlicommon.dll"
        )

    install(CODE "
            set(REQUIRED_DLLS ${REQUIRED_DLLS})
            foreach(DLL_NAME IN LISTS REQUIRED_DLLS)
                set(DLL_PATH \"${VCPKG_INSTALLED_DIR}/bin/\${DLL_NAME}\")
                if(EXISTS \"\${DLL_PATH}\")
                    file(COPY \"\${DLL_PATH}\" DESTINATION \"${PYTHON_MODULE_INSTALL_DIR}\")
                    message(STATUS \"Copied required DLL: \${DLL_NAME}\")
                else()
                    message(STATUS \"Required DLL not found: \${DLL_NAME}\")
                endif()
            endforeach()
        ")
  endif()
endif()
