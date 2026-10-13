#!/bin/bash
# tools/passthrough_poc/穿透技术验证.command
#
# V0.0 R62 图形化 PoC 入口 (任务书 §六)
#
# 1. 不需要用户输入环境变量。
# 2. 明确展示当前模式。
# 3. 明确展示上层和下层窗口。
# 4. 显示角色点击和下层按钮点击计数。
# 5. 明确标识预期结果。
# 6. 未实现的模式禁止被标为测试通过 (任务书 §六 第 6 条)。
# 7. 支持自动生成对应测试结果。
# 8. 不重构已有 PetAcceptor 业务界面。
#
# R62: PoC 模式 C 提供两条实现路径,让用户选
#   C1: main process 20Hz polling + setIgnoreMouseEvents 状态机
#   C2: 缩小窗口到 sprite bbox (macOS transparent 默认 forward)

set +e
DST="$(cd "$(dirname "$0")/../.." && git rev-parse --show-toplevel 2>/dev/null)"
cd "$DST/candidates/candidate_b_electronpixir"

clear
echo "=========================================="
echo "  R62 穿透 PoC 模式选择"
echo "=========================================="
echo "  请选择模式 (1-4):"
echo "    1. A — 完全拦截 (控制实验) setIgnoreMouseEvents(false)"
echo "    2. B — 完全穿透 (控制实验) setIgnoreMouseEvents(true)"
echo "    3. C Path 1 — 区域选择 (main 20Hz polling + setIgnore)"
echo "    4. C Path 3 — 区域选择 (缩小窗口到 sprite bbox)"
echo "    5. 退出"
echo "=========================================="
echo ""

choose_mode() {
    local n
    while true; do
        read -r -p "选择 (1-5): " n
        case "$n" in
            1) echo "A"; return;;
            2) echo "B"; return;;
            3) echo "C1"; return;;
            4) echo "C3"; return;;
            5) exit 0;;
            *) echo "请输入 1, 2, 3, 4 或 5";;
        esac
    done
}

MODE=$(choose_mode)
echo ""
case "$MODE" in
    A)  EXP="A";  DESC="完全拦截 — 上层收全部 click, 下层 0 click";;
    B)  EXP="B";  DESC="完全穿透 — 上层 0 click, 下层收全部 click";;
    C1) EXP="C";  POC_PATH="1"; DESC="区域选择 Path 1 — main 进程 20Hz polling + setIgnore";;
    C3) EXP="C";  POC_PATH="3"; DESC="区域选择 Path 3 — 缩小窗口到 sprite bbox";;
esac

# 重新读 path 设置
if [ "$MODE" = "C1" ] || [ "$MODE" = "C3" ]; then
    POC_MODE="C"
    if [ "$MODE" = "C1" ]; then POC_PATH="1"; else POC_PATH="3"; fi
    if [ -n "$POC_PATH" ]; then export POC_PATH; fi
    EXP="C"
fi
export POC_MODE
[ -n "$POC_PATH" ] && export POC_PATH || unset POC_PATH

QUIT_AFTER="${POC_QUIT_AFTER:-45}"

echo "=========================================="
echo " R62 PoC 启动"
echo "  mode:     $POC_MODE"
[ -n "$POC_PATH" ] && echo "  path:     $POC_PATH"
echo "  描述:     $DESC"
echo "  预期:     $DESC"
echo "  quit-after: ${QUIT_AFTER}s"
echo "=========================================="
echo ""
echo "  - 上层透明窗口将自动弹出"
echo "  - 下层探针窗口将自动弹出"
echo "  - 60s 后自动退出,或关闭窗口自动写结果"
echo ""
echo "  - 结果文件:"
echo "      /tmp/passthrough_poc_result.txt"
echo "      /tmp/passthrough_poc_result.json"
echo "      /tmp/passthrough_poc_result.csv"
echo "=========================================="

POC_QUIT_AFTER="$QUIT_AFTER" ./node_modules/.bin/electron "$DST/tools/passthrough_poc/main.js"

echo ""
echo "[run_poc] PoC exited. Result:"
[ -f /tmp/passthrough_poc_result.txt ] && cat /tmp/passthrough_poc_result.txt
echo ""
echo "[run_poc] 任务书 §六第 6 条:未实现的模式禁止被标为测试通过。"
echo "[run_poc] Mode A/B 仅是控制实验;Mode C 真实验证需 Mac 前台 click。"
