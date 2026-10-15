#!/usr/bin/env bash
# tools/passthrough_poc/m87_native_arg_build.sh
#
# R89 真编译 + 运行 m87_native_arg_test — 复用 m79_native_click.m 的 parse_double
#
# 编译时不调用 CGEventPost, 不需要 AX 权限.

set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="/tmp/m87_native_arg_test"
LOG="/tmp/m87_native_arg_test.log"

echo "=== R89 m87_native_arg_test 真编译 ==="

# 编译 — clang + objective-c, 链接 Foundation / ApplicationServices / CoreGraphics
clang -x objective-c -O0 "$HERE/m87_native_arg_test.c" \
    -framework Foundation \
    -framework ApplicationServices \
    -framework CoreGraphics \
    -o "$OUT" 2>&1 | tee "$LOG"

if [ ! -x "$OUT" ]; then
    echo "FAIL: compile failed"
    exit 1
fi

echo "--- 编译成功 ($OUT) ---"

# 运行
"$OUT"
RC=$?

echo "--- exit=$RC ---"
exit $RC
