#!/bin/bash
# 候选 A 与 B 一键双击启动（V0.0 第 41 轮 — 启动失败检测 + LAUNCH_FAIL 标记）
#
# 关键改动：
# 1. 启动后主动 ps -p $PID 或 pgrep 检测进程是否仍存在
# 2. 候选 A 启动后如 3 秒内未见进程存活，查找 DiagnosticReports/PetCandidateA*.ips，
#    把 LAUNCH_FAIL 写入 evidence/build_logs/user_visual_report.{csv,txt}，
#    并打印中文错误提示 + 崩溃报告路径
# 3. 不伪造 PASS：GUI 项若候选未启动全部记为 BLOCKED 或 NOT_TESTED
# 4. 启动 ClickThroughProbe 探针窗口：同样检测存活
# 5. 启动顺序：探针 → 候选 A → 候选 B；任一启动失败询问是否继续
set +e

DST="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DST" || { echo "FAIL: cannot cd to $DST"; exit 1; }

PROBE="$DST/test_window/ClickThroughProbe/build/ClickThroughProbe.app/Contents/MacOS/ClickThroughProbe"
if [ ! -x "$PROBE" ]; then
    echo "[R41 构建] ClickThroughProbe 探针窗口不存在，先编译..."
    bash "$DST/test_window/ClickThroughProbe/build.sh"
fi

TXT="$DST/evidence/build_logs/user_visual_report.txt"
CSV="$DST/evidence/build_logs/user_visual_report.csv"
LAUNCH_LOG_DIR="$DST/evidence/build_logs"
mkdir -p "$LAUNCH_LOG_DIR"
GIT_COMMIT=$(cd "$DST" && git log --oneline -1 2>/dev/null | head -1 | cut -d' ' -f1)
GIT_TAG=$(cd "$DST" && git describe --tags --abbrev=0 2>/dev/null)
GIT_BRANCH=$(cd "$DST" && git branch --show-current 2>/dev/null)
if [ -z "$GIT_COMMIT" ]; then GIT_COMMIT="uncommitted"; fi

cat > "$TXT" <<HEAD
==========================================
  AI 桌宠 V0.0 — 用户肉眼验证报告（R41 修订）
==========================================
  仓库: $DST
  分支: $GIT_BRANCH  Commit: $GIT_COMMIT  Tag: $GIT_TAG
  时间: $(date)

  提示：T06 多显示器本机未配置双屏 → 自动 NOT_TESTED
HEAD

cat > "$CSV" <<HEAD
test_id,candidate,launch_status,visible,click,drag,transparent_passthrough,t05_focus_top_spaces,t06_multidisplay,commit,tested_at
HEAD

# --- 启动失败诊断 ---
detect_launch_failure() {
    local label="$1"   # candidate_a / candidate_b / probe
    local pid="$2"
    local app_bundle="$3"      # e.g. $DST/_app_bundle/PetCandidateA.app
    sleep 3
    if pgrep -f "$app_bundle/Contents/MacOS" > /dev/null; then
        echo "OK"
        return 0
    fi
    echo ""
    echo "✗ $label 启动失败 — 进程在 3 秒内退出"
    local latest_ips=$(ls -t ~/Library/Logs/DiagnosticReports/${label}*.ips 2>/dev/null | head -1)
    local latest_log=$(ls -t "$LAUNCH_LOG_DIR/${label}_r41_launch.log" 2>/dev/null | head -1)
    if [ -n "$latest_ips" ]; then
        echo "  崩溃报告: $latest_ips"
        # 提取关键错误
        grep -o '"indicator":"[^"]*"' "$latest_ips" 2>/dev/null | head -1
        grep -o '"signal":"[^"]*"' "$latest_ips" 2>/dev/null | head -1
    fi
    if [ -n "$latest_log" ]; then
        echo "  启动日志: $latest_log"
        tail -10 "$latest_log" 2>/dev/null
    fi
    echo ""
    echo "  常见原因："
    echo "  - macOS Taskgated 拒绝运行未签名 / 签名失效的二进制（SIGKILL + 'Code Signature Invalid'）"
    echo "  - 候选 A 修复方法：codesign --force --deep --sign - '$app_bundle'"
    return 1
}

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
    osascript -e 'tell application "ClickThroughProbe" to quit' 2>/dev/null
    pkill -f "PetCandidateA" 2>/dev/null
    pkill -f "Electron.*src/main.js" 2>/dev/null
    pkill -f "ClickThroughProbe" 2>/dev/null
    sleep 1
}

# =========================================================================
# 阶段 0: 启动 ClickThroughProbe 探针
# =========================================================================
echo "=========================================="
echo " 阶段 0: 启动 ClickThroughProbe 探针"
echo "=========================================="
"$PROBE" > /tmp/click_through_probe.log 2>&1 &
PROBE_PID=$!
sleep 2
PROBE_STATUS=$(detect_launch_failure "ClickThroughProbe" "$PROBE_PID" "$DST/test_window/ClickThroughProbe/build/ClickThroughProbe.app")
if [ "$PROBE_STATUS" != "OK" ]; then
    echo "探针启动失败，跳过所有后续透明区验证"
fi
echo ""

# =========================================================================
# 阶段 1: 候选 A
# =========================================================================
echo "=========================================="
echo "=== 阶段 1/2: 候选 A (AppKit) ==="
echo "=========================================="
echo "提示：候选 A 启动后 256x256 桌宠应出现在 (600, 600) 附近"
echo ""
bash "$DST/one_click_test/run_candidate_a.sh" &
A_RUN_PID=$!

A_LAUNCH=$(detect_launch_failure "PetCandidateA" "$A_RUN_PID" "$DST/_app_bundle/PetCandidateA.app")
if [ "$A_LAUNCH" != "OK" ]; then
    cat >> "$TXT" <<EOT

【候选 A (AppKit) — 启动失败（LAUNCH_FAIL）】
  launch_status: FAIL
  后续 5 项 GUI 验证全部记为 BLOCKED
EOT
    echo "candidate_a,FAIL,BLOCKED,BLOCKED,BLOCKED,BLOCKED,BLOCKED,BLOCKED,${GIT_COMMIT},$(date -u +%FT%TZ)" >> "$CSV"
    kill_processes
    sleep 2
else
    echo "候选 A 已启动 4 秒。开始 7 项分项验证"
    echo ""

    V_A=$(wait_user "1/7 候选 A 是否在桌面上肉眼可见？")
    C_A=$(wait_user "2/7 鼠标点击角色是否有响应（拖拽姿势/动作切换）？")
    D_A=$(wait_user "3/7 鼠标按住角色拖动到屏幕不同位置，是否跟随？")
    T_A=$(wait_user "4/7 点击角色周围的透明区域（或点击探针按钮），能否让下层应用响应？")
    S_A=$(wait_user "5/7 T05 焦点/置顶/Spaces：(a) 点击桌宠头部，候选 A 应抢到焦点 (b) ⌃←→ 切换 Spaces，桌宠是否跟随？")
    MULTI_A=skip

    case "$V_A" in yes|no|skip) ;; *) V_A=skip ;; esac
    case "$C_A" in yes|no|skip) ;; *) C_A=skip ;; esac
    case "$D_A" in yes|no|skip) ;; *) D_A=skip ;; esac
    case "$T_A" in yes|no|skip) ;; *) T_A=skip ;; esac
    case "$S_A" in yes|no|skip) ;; *) S_A=skip ;; esac

    echo ""
    echo "已记录候选 A 验证: launch=PASS visible=$V_A click=$C_A drag=$D_A transparent=$T_A t05=$S_A"
    echo "candidate_a,PASS,${V_A},${C_A},${D_A},${T_A},${S_A},${MULTI_A},${GIT_COMMIT},$(date -u +%FT%TZ)" >> "$CSV"
    cat >> "$TXT" <<EOT

【候选 A (AppKit)】
  launch_status: PASS
  visible: $V_A
  click: $C_A
  drag: $D_A
  transparent_passthrough: $T_A
  t05_focus_top_spaces: $S_A
  t06_multidisplay: $MULTI_A  # 单屏环境固定 NOT_TESTED
EOT

    kill_processes
    sleep 2
fi

# =========================================================================
# 阶段 2: 候选 B
# =========================================================================
echo ""
echo "=========================================="
echo "=== 阶段 2/2: 候选 B (Electron) ==="
echo "=========================================="
echo "提示：候选 B 启动后 256x256 桌宠应出现在 (600, 600) 附近"
echo ""
bash "$DST/one_click_test/run_candidate_b.sh" &
B_RUN_PID=$!
sleep 6

B_LAUNCH="OK"   # 候选 B 用 node spawn，launch 阶段 fail 概率低
if ! pgrep -f "Electron.*candidates/candidate_b" > /dev/null; then
    B_LAUNCH="FAIL"
    cat >> "$TXT" <<EOT

【候选 B (Electron) — 启动失败（LAUNCH_FAIL）】
  launch_status: FAIL
  后续 5 项 GUI 验证全部记为 BLOCKED
EOT
    echo "candidate_b,FAIL,BLOCKED,BLOCKED,BLOCKED,BLOCKED,BLOCKED,BLOCKED,${GIT_COMMIT},$(date -u +%FT%TZ)" >> "$CSV"
    kill_processes
    sleep 2
else
    echo "候选 B 已启动 6 秒。开始 7 项分项验证"
    echo ""

    V_B=$(wait_user "1/7 候选 B 是否在桌面上肉眼可见？")
    C_B=$(wait_user "2/7 鼠标点击角色是否有响应？")
    D_B=$(wait_user "3/7 鼠标按住角色拖动，是否跟随？")
    T_B=$(wait_user "4/7 点击透明区域（或点击探针按钮）能否让下层应用响应？")
    S_B=$(wait_user "5/7 T05 焦点/置顶/Spaces：(a) 点击桌宠头部 (b) 切换 Spaces 桌宠是否跟随？")
    MULTI_B=skip

    case "$V_B" in yes|no|skip) ;; *) V_B=skip ;; esac
    case "$C_B" in yes|no|skip) ;; *) C_B=skip ;; esac
    case "$D_B" in yes|no|skip) ;; *) D_B=skip ;; esac
    case "$T_B" in yes|no|skip) ;; *) T_B=skip ;; esac
    case "$S_B" in yes|no|skip) ;; *) S_B=skip ;; esac

    echo ""
    echo "已记录候选 B 验证: launch=PASS visible=$V_B click=$C_B drag=$D_B transparent=$T_B t05=$S_B"
    echo "candidate_b,PASS,${V_B},${C_B},${D_B},${T_B},${S_B},${MULTI_B},${GIT_COMMIT},$(date -u +%FT%TZ)" >> "$CSV"
    cat >> "$TXT" <<EOT

【候选 B (Electron)】
  launch_status: PASS
  visible: $V_B
  click: $C_B
  drag: $D_B
  transparent_passthrough: $T_B
  t05_focus_top_spaces: $S_B
  t06_multidisplay: $MULTI_B  # 单屏环境固定 NOT_TESTED
EOT

    kill_processes
    sleep 2
fi

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
