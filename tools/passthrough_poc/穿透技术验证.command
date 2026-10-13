#!/bin/bash
# tools/passthrough_poc/穿透技术验证.command
#
# V0.0 R64 图形化 PoC 入口 (任务书 §五)
#
# - 不需要 env var 输入。
# - 单次启动同窗口,通过顶部 [A][B][C1][C2] 按钮切换 mode。
# - 每次切换 mode 自动写独立结果文件:
#     /tmp/passthrough_poc_<run_id>_<mode>.{txt,json,csv}
# - 超时统一 90s (R64 修复 R62 45s/60s 不一致)
# - 任务书 §六 第 6 条:未实现的功能禁止被标为测试通过
# - 任务书 §七 Path 3 重新命名为 COMPACT_WINDOW_FALLBACK (不是真穿透)

set +e
DST="$(cd "$(dirname "$0")/../.." && git rev-parse --show-toplevel 2>/dev/null)"
cd "$DST/candidates/candidate_b_electronpixir"

# 可选:先跑 self-test 验证状态机 math (任务书 §四)
echo "=========================================="
echo " R64 穿透 PoC (单次启动 + 按钮切换 mode)"
echo "=========================================="
echo ""
echo " 启动中...窗口弹出后,顶部有 [A][B][C1][C2] 4 个按钮。"
echo " 用户流程:"
echo "   1. 在候选 B 顶层窗口(透明)点金球+透明角"
echo "   2. 点击 [A] → 验证 A: 顶层收 click, 探针 0"
echo "   3. 点击 [B] → 验证 B: 顶层 0, 探针收 click"
echo "   4. 点击 [C1] → 验证 C1: 顶层 main 20Hz polling"
echo "   5. 点击 [C2] → 验证 C2: 100x100 紧凑窗口 (FALLBACK)"
echo ""
echo " 每个 mode 切换会自动写独立结果文件(按 run_id + mode)。"
echo " 超时 90s 后自动退出。"
echo ""

# Run self-test first
POC_SELFTEST=1 ./node_modules/.bin/electron "$DST/tools/passthrough_poc/main.js" 2>&1 | grep -E "self-test|state machine|error" | head -10

# Run real PoC
POC_QUIT_AFTER=90 ./node_modules/.bin/electron "$DST/tools/passthrough_poc/main.js"

echo ""
echo "[run_poc] PoC exited. Result files:"
ls -la /tmp/passthrough_poc_*.{txt,json,csv} 2>&1 | tail -10
echo ""
echo "=========================================="
echo " 任务书 §六 第 6 条:未实现的功能禁止被标为测试通过。"
echo " Mode A/B 仅是控制实验;Mode C1/C2 真实验证需 Mac 前台 click。"
echo "=========================================="
