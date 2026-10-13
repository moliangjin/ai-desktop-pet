#!/bin/bash
# tools/passthrough_poc/穿透技术验证.command
#
# V0.0 R61 — 一键 PoC 运行器 (任务书 §五 强制)
#
# 必读:
#   双击本文件即可启动 PoC;无需开多个终端或手动跑 Electron 命令。
#   PoC 默认 mode=A (完全拦截,控制实验)。用户可在 60 秒内:
#     - 点击金球 / 透明角 / 绿方块 / 红方块
#     - 观察两个窗口各自的 click 计数
#     - 关闭窗口时 PoC 自动写结果到 /tmp/passthrough_poc_result.{txt,json,csv}
#
# 切换 mode (默认 A):
#   POC_MODE=A bash 穿透技术验证.command     # 完全拦截 (控制)
#   POC_MODE=B bash 穿透技术验证.command     # 完全穿透 (控制)
#   POC_MODE=C bash 穿透技术验证.command     # 区域选择 (任务书目标)

set +e
cd "$(dirname "$0")/../.."  # 仓库根
DST="$(git rev-parse --show-toplevel 2>/dev/null)"
cd "$DST/candidates/candidate_b_electronpixir"

MODE="${POC_MODE:-A}"
case "$MODE" in
    A) MODE_DESC="完全拦截 (控制实验) - 期望: top 接收 click, under 0 click";;
    B) MODE_DESC="完全穿透 (控制实验) - 期望: under 接收 click, top 0 click";;
    C) MODE_DESC="区域选择性 (任务书 §四 目标) - 期望: top 收 sprite, under 收透明区";;
    *) MODE_DESC="未知 mode $MODE (默认 A)"; MODE=A;;
esac

echo "=========================================="
echo " R61 穿透 PoC 启动"
echo "  mode: $MODE"
echo "  desc: $MODE_DESC"
echo "=========================================="
echo "  - 上层透明窗口将自动弹出 (256x256, 始终置顶)"
echo "  - 下层探针窗口将自动弹出 (360x180, 普通置顶)"
echo "  - 60 秒后自动退出,或关闭窗口自动写结果"
echo "  - 结果文件:"
echo "      /tmp/passthrough_poc_result.txt"
echo "      /tmp/passthrough_poc_result.json"
echo "      /tmp/passthrough_poc_result.csv"
echo ""
echo "  切换 mode:"
echo "      POC_MODE=B bash $0   # 完全穿透"
echo "      POC_MODE=C bash $0   # 区域选择"
echo "=========================================="

POC_MODE="$MODE" ./node_modules/.bin/electron "$DST/tools/passthrough_poc/main.js"

echo ""
echo "[run_poc] PoC exited. Results:"
[ -f /tmp/passthrough_poc_result.txt ] && cat /tmp/passthrough_poc_result.txt
echo ""
echo "[run_poc] CSV: /tmp/passthrough_poc_result.csv"
[ -f /tmp/passthrough_poc_result.csv ] && cat /tmp/passthrough_poc_result.csv
echo ""
echo "[run_poc] 任务书 §五明确: 模式 A/B 是控制实验;只有模式 C 满足真实需求。"
echo "[run_poc] 当前 macOS 14 + Electron 33 的 PIXI v7 hit-test 行为仍需用户前台验证。"
