#!/usr/bin/env bash
# tools/passthrough_poc/m78_build.sh
#
# 编译 Objective-C GUI 测试器, 绕开 Swift 编译障碍。
# 编译: clang (macOS 自带) + ApplicationServices 框架 + Foundation 框架
#
# 在用户本地 Mac 跑:
#   cd tools/passthrough_poc
#   ./m78_build.sh
#   ./build/m78_gui_test_runner

set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# Locate clang.
if ! command -v clang >/dev/null 2>&1; then
    echo "clang not found. Install Xcode Command Line Tools:"
    echo "  xcode-select --install"
    exit 2
fi

mkdir -p build
echo "compiling m78_gui_test_runner.m ..."
clang -fobjc-arc -O2 \
    -framework Foundation -framework ApplicationServices -framework AppKit -framework CoreGraphics \
    m78_gui_test_runner.m -o build/m78_gui_test_runner
ls -la build/m78_gui_test_runner
echo ""
echo "DONE. Run with:"
echo "  ./build/m78_gui_test_runner"
echo ""
echo "Before running, grant Accessibility to Terminal.app (or whichever app"
echo "you'll run this from) in System Settings → Privacy & Security → Accessibility."
