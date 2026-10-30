cmake_minimum_required(VERSION 3.21)
project(kwineventbridge LANGUAGES CXX)

# Compiled QML module for the Quickshell KWin event bridge (P0 #9 Intellihide).
#
# Build (from the repository root; see README.md in this directory for the
# full procedure, ABI requirements and fallback behavior):
#   cmake -S services/kwin/bridge -B /tmp/kwineventbridge-build -DCMAKE_BUILD_TYPE=Release
#   cmake --build /tmp/kwineventbridge-build -j4
#   cp /tmp/kwineventbridge-build/libkwineventbridgeplugin.so \
#      /tmp/kwineventbridge-build/libkwineventbridge.so \
#      services/kwin/bridge/
#
# Only sources, qmldir and qmltypes are committed. The compiled .so files are
# machine/Qt-build specific and stay out of git: each user (or packager)
# builds them locally. The qmldir registers the plugin as `optional`, so a
# checkout without built binaries still loads the QML module — the
# WindowService Loader for BridgeHost.qml reports an error, logs a warning
# and the shell keeps the snapshot-based sync path (graceful degradation).

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 6.6 REQUIRED COMPONENTS Qml DBus)

qt_add_qml_module(kwineventbridge
    URI KWinEventBridge
    VERSION 1.0
    SOURCES
        kwinbridge.h
        kwinbridge.cpp
)

target_link_libraries(kwineventbridge PRIVATE Qt6::Qml Qt6::DBus)

# The plugin must find its sibling backing library from whatever directory the
# committed artifacts are loaded from (Quickshell config checkout).
set_target_properties(kwineventbridgeplugin PROPERTIES
    BUILD_WITH_INSTALL_RPATH TRUE
    INSTALL_RPATH "$ORIGIN"
)
