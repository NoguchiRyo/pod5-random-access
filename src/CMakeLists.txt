
set(PYBIND11_FINDPYTHON ON)
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

set(PYTHON_MODULE_INSTALL_DIR  pod5_random_access)

install(TARGETS pod5_random_access_pybind
    DESTINATION ${PYTHON_MODULE_INSTALL_DIR}
    RUNTIME DESTINATION ${PYTHON_MODULE_INSTALL_DIR}
    LIBRARY DESTINATION ${PYTHON_MODULE_INSTALL_DIR}
)

if(WIN32)
  install(CODE "
        file(GLOB DLLS
            \"${CMAKE_BINARY_DIR}/Debug/bin/*.dll\"
            \"${CMAKE_BINARY_DIR}/Release/bin/*.dll\"
            \"${CMAKE_BINARY_DIR}/*.dll\"
        )
        if(DLLS)
            file(COPY \${DLLS} DESTINATION \"pod5_random_access\")
            message(STATUS \"Copied DLLs: \${DLLS}\")
        endif()
    ")
endif()
