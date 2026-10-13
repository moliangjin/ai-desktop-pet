#!/bin/bash
# tools/passthrough_poc/自动验收.command
#
# V0.0 R78 一键入口 (任务书 §四)
#
# 用户在 Mac 前台双击即可完成:
#   1. 检查编译器 (clang)
#   2. 编译 m78 Objective-C 测试器
#   3. 提示最少必要授权
#   4. 跑测试器
#   5. 输出 TXT/JSON/CSV 结果
#
# 不需要用户输入多条命令。

set +e
DST="$(cd "$(dirname "$0")/../.." && git rev-parse --show-toplevel)"
cd "$DST/tools/passthrough_poc"

clear
echo "=========================================="
echo " R78 一键自动验收 (Objective-C 路线)"
echo "=========================================="
echo ""

# 1) 检查编译器
echo "[1/4] 检查编译器 (clang)..."
if ! command -v clang >/dev/null 2>&1; then
    echo "  ✗ clang 不在 PATH"
    echo "  修复: xcode-select --install"
    echo "  (这是 macOS 自带的命令行工具)"
    exit 2
fi
CLANG_VER=$(clang --version | head -1)
echo "  ✓ $CLANG_VER"

# 2) 编译测试器
echo ""
echo "[2/4] 编译 Objective-C 测试器..."
bash ./m78_build.sh 2>&1 | tail -8
if [ ! -x ./build/m78_gui_test_runner ]; then
    echo ""
    echo "  ✗ 编译失败, 无法继续"
    echo "  完整编译错误已存到 tools/passthrough_poc/m78_build.log"
    exit 3
fi
echo "  ✓ ./build/m78_gui_test_runner 就绪"

# 3) 提示最少必要授权
echo ""
echo "[3/4] 准备授权 (本次运行前需要):"
echo "  - 系统设置 → 隐私与安全 → 辅助功能 → 勾选 Terminal.app"
echo "  - (CGEventPost 鼠标事件, 不需要 Input Monitoring)"
echo "  - 若已经授权, 直接回车继续; 若未授权, 先去授权再回来"
read -r -p "  按回车继续: "

# 4) 跑测试器
echo ""
echo "[4/4] 启动测试 (R78 真实系统 mouse, 3 窗口 PoC, 3 cycles, 自动写结果)..."
echo "  预计 30-60 秒, 中间会把 PoC 跑起来并发送 6+ 次真实 click"
echo "  按 ⌘C 可中止"
echo ""
./build/m78_gui_test_runner
RC=$?

echo ""
echo "=========================================="
echo " R78 完成 (exit=$RC)"
echo " 结果文件在 /tmp/m78_<run_id>.{txt,json,csv,log}"
ls -la /tmp/m78_*.{txt,json,csv,log} 2>/dev/null | head -5
echo "=========================================="
echo ""
echo "请回传 m78_<run_id>.{txt,json,csv} 给 MiniMax 即可。"
