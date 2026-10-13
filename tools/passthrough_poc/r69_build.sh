#!/usr/bin/env bash
# tools/passthrough_poc/r69_build.sh
#
# 编译 r69_gui_test_runner.swift 为独立二进制。
# 在用户 Mac 上运行, 不在 mavis shell 沙箱里跑。
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# Locate swiftc (Xcode CLT required on user Mac).
if ! command -v swiftc >/dev/null 2>&1; then
    echo "swiftc not found. Install Xcode Command Line Tools:"
    echo "  xcode-select --install"
    exit 2
fi

mkdir -p build
echo "compiling r69_gui_test_runner.swift ..."
swiftc -O r69_gui_test_runner.swift -o build/r69_gui_test_runner
ls -la build/r69_gui_test_runner
echo ""
echo "DONE. Run with:"
echo "  ./build/r69_gui_test_runner"
echo ""
echo "If Accessibility is not yet granted, the runner will print the"
echo "minimal grant instructions and exit cleanly."
