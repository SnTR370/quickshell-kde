cmake_minimum_required(VERSION 3.21)
project(kwineventbridge LANGUAGES CXX)

# Compiled QML module for the Quickshell KWin event bridge (P0 #9 Intellihide).
#
# Build (from anywhere, artifacts are copied back into this directory):
#   cmake -S services/kwin/bridge -B /tmp/kwineventbridge-build
#   cmake --build /tmp/kwineventbridge-build
#   cp /tmp/kwineventbridge-build/libkwineventbridgeplugin.so \
#      /tmp/kwineventbridge-build/qmldir services/kwin/bridge/
#
# The built plugin, qmldir and qmltypes are committed so ordinary KDE users
# get the event-driven Intellihide without a toolchain. If the binary does not
# match the local Qt/ABI, the Quickshell Loader fails gracefully and the shell
# falls back to the snapshot-based sync path.

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
