#!/usr/bin/env bash
# tools/passthrough_poc/m79_build.sh
#
# V0.0 R79 编译最简 Objective-C 鼠标事件执行器
# 不使用 Swift, 不用 Swift 工具链, 仅依赖 clang (macOS 自带)
#
# 必须成功: clang 退出码 0
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

if ! command -v clang >/dev/null 2>&1; then
    echo "FATAL: clang not found. Install Xcode Command Line Tools: xcode-select --install" >&2
    exit 1
fi

mkdir -p build
clang -O2 -framework Foundation -framework ApplicationServices -framework CoreGraphics \
    m79_native_click.m -o build/m79_native_click

echo "=== build artifact ==="
file build/m79_native_click
ls -la build/m79_native_click
test -x build/m79_native_click && echo "OK: executable exists" || echo "FATAL: not executable"
echo ""
echo "=== self-test (no mouse events) ==="
./build/m79_native_click --self-test
