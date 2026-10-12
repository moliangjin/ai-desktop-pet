#!/bin/bash
# 候选 A 与 B 一键双击启动（V0.0 第 39 轮修订）
#
# 改进点：
# 1. 启动前先开 ClickThroughProbe 探针窗口（含可点击按钮）验证穿透
# 2. 每个候选验证后追加 1 项 T05 焦点/置顶/Spaces 检查（4 项 → 5 项）
# 3. T06 多显示器保持 NOT_TESTED（本机单屏环境）
# 4. 用户做出 4 个分项（visible/click/drag/transparent）后，要求 5/6/7 三项
#    也给出答案或 skip；
# 5. 30s timeout 默认 skip 保持不变（避免长时间堵塞）
set +e

DST="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DST" || { echo "FAIL: cannot cd to $DST"; exit 1; }

PROBE="$DST/test_window/ClickThroughProbe/build/ClickThroughProbe.app/Contents/MacOS/ClickThroughProbe"
if [ ! -x "$PROBE" ]; then
    echo "构建 ClickThroughProbe..."
    bash "$DST/test_window/ClickThroughProbe/build.sh"
fi

TXT="$DST/evidence/build_logs/user_visual_report.txt"
CSV="$DST/evidence/build_logs/user_visual_report.csv"
GIT_COMMIT=$(cd "$DST" && git log --oneline -1 2>/dev/null | head -1 | cut -d' ' -f1)
GIT_TAG=$(cd "$DST" && git describe --tags --abbrev=0 2>/dev/null)
GIT_BRANCH=$(cd "$DST" && git branch --show-current 2>/dev/null)
if [ -z "$GIT_COMMIT" ]; then GIT_COMMIT="uncommitted"; fi

cat > "$TXT" <<HEAD
==========================================
  AI 桌宠 V0.0 — 用户肉眼验证报告
==========================================
  仓库: $DST
  分支: $GIT_BRANCH  Commit: $GIT_COMMIT  Tag: $GIT_TAG
  时间: $(date)

  提示：T06 多显示器本机未配置双屏 → 自动 NOT_TESTED
HEAD

cat > "$CSV" <<HEAD
test_id,candidate,visible,click,drag,transparent_passthrough,t05_focus_top_spaces,t06_multidisplay,commit,tested_at
HEAD

wait_user() {
    local prompt="$1"
    local timeout="${2:-180}"
    echo ""
    echo ">>> $prompt"
    echo "  输入 next = 继续；yes/no = 记入验证；skip = NOT_TESTED（按回车 = 30s 后 timeout=skip）"
    local ans=""
    local deadline=$((SECONDS + timeout))
    while [ $SECONDS -lt $deadline ]; do
        if read -t 30 -n 1 -r ans; then
            echo
            break
        fi
        echo "（30 秒无输入自动 timeout）"
    done
    case "$ans" in
        y|Y|yes|YES) echo "yes" ;;
        n|N|no|NO) echo "no" ;;
        next|NEXT) echo "next" ;;
        *) echo "skip" ;;
    esac
}

kill_processes() {
    osascript -e 'tell application "Pet A Test" to quit' 2>/dev/null
    osascript -e 'tell application "Pet B Test" to quit' 2>/dev/null
    pkill -f "Electron.*src/main.js" 2>/dev/null
    pkill -f "ClickThroughProbe" 2>/dev/null
    sleep 1
}

# 启动探针窗口（独立 AppKit app，全程不退出直到本工具结束）
echo ""
echo "=========================================="
echo " 准备阶段：启动 ClickThroughProbe 探针窗口"
echo "=========================================="
echo "  探针窗口 360x180，含一个 '点这里测试穿透' 按钮"
echo "  每点击一下，按钮上方的 '已点击次数' 会 +1"
echo "  如果桌宠透明区穿透失败，按钮点击会被拦截（数字不变）"
echo ""
"$PROBE" > /tmp/click_through_probe.log 2>&1 &
PROBE_PID=$!
sleep 2
if ! ps -p $PROBE_PID > /dev/null; then
    echo "FAIL: ClickThroughProbe 没起来，cat /tmp/click_through_probe.log:"
    cat /tmp/click_through_probe.log
    exit 2
fi
echo "探针已启动 PID=$PROBE_PID"
echo ""

# ===== 候选 A =====
echo "=========================================="
echo "=== 阶段 1/2: 候选 A (AppKit) ==="
echo "=========================================="
echo "提示：候选 A 启动后 256x256 桌宠应出现在 (600, 600) 附近"
echo "      Finder 中可看 app 名为 'Pet A Test'"
echo "      状态栏（屏幕顶部右上角）应有 🐾 状态项"
echo ""
bash "$DST/one_click_test/run_candidate_a.sh" &
A_PID=$!
sleep 4
echo "候选 A 已启动 4 秒。开始 7 项分项验证"
echo ""

V_A=$(wait_user "1/7 候选 A 是否在桌面上肉眼可见？")
C_A=$(wait_user "2/7 鼠标点击角色是否有响应（拖拽姿势/动作切换）？")
D_A=$(wait_user "3/7 鼠标按住角色拖动到屏幕不同位置，是否跟随？")
T_A=$(wait_user "4/7 点击角色周围的透明区域（或点击探针按钮），能否让下层应用响应？")
S_A=$(wait_user "5/7 T05 焦点/置顶/Spaces：(a) 点击桌宠头部，候选 A 应抢到焦点  (b) ⌃←→ 切换 Spaces，桌宠是否跟随？")
MULTI_A=skip   # T06 单屏环境，固定 NOT_TESTED

case "$V_A" in yes|no|skip) ;; *) V_A=skip ;; esac
case "$C_A" in yes|no|skip) ;; *) C_A=skip ;; esac
case "$D_A" in yes|no|skip) ;; *) D_A=skip ;; esac
case "$T_A" in yes|no|skip) ;; *) T_A=skip ;; esac
case "$S_A" in yes|no|skip) ;; *) S_A=skip ;; esac

echo ""
echo "已记录候选 A 验证: visible=$V_A click=$C_A drag=$D_A transparent=$T_A t05_focus=$S_A t06_multidisplay=$MULTI_A"
echo "candidate_a,${V_A},${C_A},${D_A},${T_A},${S_A},${MULTI_A},${GIT_COMMIT},$(date -u +%FT%TZ)" >> "$CSV"
cat >> "$TXT" <<EOT

【候选 A (AppKit)】
  visible: $V_A
  click: $C_A
  drag: $D_A
  transparent_passthrough: $T_A
  t05_focus_top_spaces: $S_A
  t06_multidisplay: $MULTI_A  # 单屏环境固定 NOT_TESTED
EOT

kill_processes
sleep 2

# ===== 候选 B =====
echo ""
echo "=========================================="
echo "=== 阶段 2/2: 候选 B (Electron) ==="
echo "=========================================="
echo "提示：候选 B 启动后 256x256 桌宠应出现在 (600, 600) 附近"
echo "      状态栏应出现 Electron 菜单图标"
echo ""
bash "$DST/one_click_test/run_candidate_b.sh" &
B_PID=$!
sleep 6
echo "候选 B 已启动 6 秒。开始 7 项分项验证"
echo ""

V_B=$(wait_user "1/7 候选 B 是否在桌面上肉眼可见？")
C_B=$(wait_user "2/7 鼠标点击角色是否有响应？")
D_B=$(wait_user "3/7 鼠标按住角色拖动，是否跟随？")
T_B=$(wait_user "4/7 点击透明区域（或点击探针按钮）能否让下层应用响应？")
S_B=$(wait_user "5/7 T05 焦点/置顶/Spaces：(a) 点击桌宠头部，候选 B 应抢到焦点 (b) 切换 Spaces 桌宠是否跟随？")
MULTI_B=skip

case "$V_B" in yes|no|skip) ;; *) V_B=skip ;; esac
case "$C_B" in yes|no|skip) ;; *) C_B=skip ;; esac
case "$D_B" in yes|no|skip) ;; *) D_B=skip ;; esac
case "$T_B" in yes|no|skip) ;; *) T_B=skip ;; esac
case "$S_B" in yes|no|skip) ;; *) S_B=skip ;; esac

echo ""
echo "已记录候选 B 验证: visible=$V_B click=$C_B drag=$D_B transparent=$T_B t05_focus=$S_B t06_multidisplay=$MULTI_B"
echo "candidate_b,${V_B},${C_B},${D_B},${T_B},${S_B},${MULTI_B},${GIT_COMMIT},$(date -u +%FT%TZ)" >> "$CSV"
cat >> "$TXT" <<EOT

【候选 B (Electron)】
  visible: $V_B
  click: $C_B
  drag: $D_B
  transparent_passthrough: $T_B
  t05_focus_top_spaces: $S_B
  t06_multidisplay: $MULTI_B  # 单屏环境固定 NOT_TESTED
EOT

kill_processes
sleep 1

# ===== 最终汇总 =====
cat >> "$TXT" <<EOT

==========================================
  汇总（机器可读 CSV: $CSV）
==========================================
EOT
cat "$CSV" >> "$TXT"
cat "$CSV"

echo ""
echo "=========================================="
echo " 验证完成。请把以下文件回传 MiniMax："
echo "   $TXT"
echo "   $CSV"
echo "=========================================="
echo "$TXT"
echo "$CSV"
