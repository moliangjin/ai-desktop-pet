#!/bin/bash
# candidates/candidate_b_c2/C2_Mac人工验收.command
#
# V0.0 R141 — 自主行为桌宠 Mac 真机人工验收入口
#
# 本轮目标: 银白短发科技研究员第一次真正具备自主待机、行走、睡觉和醒来的能力.
#
# 启动内容:
#   - 正式角色 (R138 的 23 帧 RGBA PNG, 六组动画)
#   - 自主行为引擎 (IDLE / WALK_LEFT / WALK_RIGHT / SLEEP_ENTER / SLEEP_LOOP / WAKE_UP / DRAGGING)
#   - 紧凑窗口 200x240 (C2 授权方案)
#
# 不做:
#   - 不打开 DevTools
#   - 不在桌宠窗口内显示任何调试文字 (R141 §五: 正式运行只显示角色)
#   - 不调用系统鼠标注入工具
#   - 不请求辅助功能 / 屏幕录制权限
#   - 不使用全局 pkill 误杀其他应用 (只 kill 本次启动的 PID)
#   - 不修改用户系统隐私设置
#
# 用法:
#   双击运行            → 正式模式 (自然速度, 正式状态机参数)
#   ./C2_Mac人工验收.command fast  → 验收加速模式 (缩短等待时长, 状态机逻辑不变)
#   ./C2_Mac人工验收.command standard → 256x256 标准窗口
#
# 退出: Cmd+Q
# 日志: /tmp/r141_c2_mac_acceptance_<ts>.log
# 退出码: 0=正常退出 2=参数错 3=manifest缺失 4=electron缺失 10=资源全部加载失败

set +e
cd "$(dirname "$0")"
TS="$(date +%s)"
LOG="/tmp/r141_c2_mac_acceptance_${TS}.log"

MODE="compact"
ACCEPT="off"
for arg in "$@"; do
    case "$arg" in
        compact|standard) MODE="$arg" ;;
        fast|acceptance)  ACCEPT="on" ;;
        off|normal)       ACCEPT="off" ;;
        *) echo "用法: $0 [compact|standard] [fast|off]"; exit 2 ;;
    esac
done

# node_modules symlink 兜底
if [ ! -e node_modules ]; then
    if [ -d ../candidate_b_electronpixir/node_modules ]; then
        ln -sf ../candidate_b_electronpixir/node_modules node_modules
    else
        echo "[验收] FATAL: node_modules 不存在" | tee -a "$LOG"
        exit 1
    fi
fi

MANIFEST="$(cd assets && pwd)/character_R141_manifest.json"
if [ ! -f "$MANIFEST" ]; then
    echo "[验收] FATAL: manifest 不存在: $MANIFEST" | tee -a "$LOG"
    exit 3
fi

ELECTRON="$(cd ../candidate_b_electronpixir && pwd)/node_modules/.bin/electron"
if [ ! -x "$ELECTRON" ]; then
    echo "[验收] FATAL: electron 不存在: $ELECTRON" | tee -a "$LOG"
    exit 4
fi

ELECTRON_PID=""
cleanup_electron() {
    if [ -n "$ELECTRON_PID" ] && kill -0 "$ELECTRON_PID" 2>/dev/null; then
        kill -TERM "$ELECTRON_PID" 2>/dev/null
        sleep 1
        if kill -0 "$ELECTRON_PID" 2>/dev/null; then
            kill -KILL "$ELECTRON_PID" 2>/dev/null
        fi
    fi
}
trap cleanup_electron EXIT INT TERM

{
echo "=========================================================="
echo " R141 自主行为桌宠 — Mac 真机人工验收"
echo "=========================================================="
echo " 窗口模式:   $MODE (200x240 紧凑 / 256x256 标准)"
echo " 加速模式:   $ACCEPT   (fast 只缩短等待时长, 不改状态机逻辑)"
echo " 角色资源:   R138 23 帧 RGBA PNG (六组动画)"
echo " Manifest:   $MANIFEST"
echo " 日志文件:   $LOG"
echo ""
echo " 请在 60 秒内依次观察 (每项确认后再看下一项):"
echo ""
echo "  1. 桌宠出现          — 桌面上出现银白短发科技研究员, 窗口透明无白底"
echo "  2. 自主待机          — 角色自行呼吸 + 眨眼, 无需点击任何按键"
echo "  3. 自主行走          — 角色自己开始走, 且**桌面位置真的在移动**"
echo "  4. 自动转向          — 走到屏幕边缘后自己掉头, 继续走"
echo "  5. 自动休息睡觉      — 自己坐下躺下, 闭眼呼吸 (不会几秒就反复睡醒)"
echo "  6. 自动醒来          — 自己抬头坐起站回, 恢复待机"
echo "  7. 鼠标拖拽          — 按住拖动, 窗口跟随鼠标; 松开后过一会儿恢复自主活动"
echo "  8. 正常退出          — Cmd+Q 退出, 桌面无残留窗口"
echo ""
echo " 观察要点:"
echo "   · 桌宠窗口内不应出现任何调试文字/提示条/英文"
echo "   · 行走时角色在动 + 桌面位置也在动 (不是原地踏步)"
echo "   · 拖拽时桌面位置由你控制, 松手后角色会自己继续活动"
echo ""
echo " 启动中... (关闭窗口或 Cmd+Q 结束)"
echo "----------------------------------------------------------"
} | tee -a "$LOG"

# 正式模式不使用 --acceptance (不进入测试模式); fast 模式才启用
EXTRA=""
if [ "$ACCEPT" = "on" ]; then
    EXTRA="--acceptance"
fi

"$ELECTRON" "$(pwd)/src/main.js" \
    --manifest "$MANIFEST" \
    --mode "$MODE" \
    $EXTRA \
    --quit-after=1800 \
    >> "$LOG" 2>&1
ELECTRON_RC=$?

echo "----------------------------------------------------------" | tee -a "$LOG"
echo "[验收] 退出 rc=$ELECTRON_RC" | tee -a "$LOG"

# R141 §一-10: 资源加载失败必须明确 FAIL
if grep -qE "all [0-9]+ frames failed" "$LOG" 2>/dev/null; then
    echo "[验收] FATAL: 动画帧全部加载失败" | tee -a "$LOG"
    exit 10
fi
ZERO_LOADED=$(grep -cE -e "asset-report: [a-z_]+ loaded=0 failed=[0-9]+" "$LOG" 2>/dev/null)
if [ "${ZERO_LOADED:-0}" -ge 1 ]; then
    echo "[验收] FATAL: 有动作 loaded=0, 拒绝宣布准备 PASS" | tee -a "$LOG"
    exit 10
fi

# 行为引擎是否真的启动
if ! grep -q "behavior engine started" "$LOG" 2>/dev/null; then
    echo "[验收] FATAL: 自主行为引擎未启动" | tee -a "$LOG"
    exit 11
fi

# 汇总行为观测
echo "" | tee -a "$LOG"
echo " 行为观测汇总:" | tee -a "$LOG"
echo "   状态转移次数: $(grep -c -e 'R141 STATE' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   窗口移动次数: $(grep -c -e 'R141 MOVE' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   撞边转向次数: $(grep -c -e 'edge-turn' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   睡眠序列:     ENTER=$(grep -cE -e 'R141 STATE [A-Z_]+ -> SLEEP_ENTER' "$LOG" 2>/dev/null) LOOP=$(grep -cE -e 'R141 STATE [A-Z_]+ -> SLEEP_LOOP' "$LOG" 2>/dev/null) WAKE=$(grep -cE -e 'R141 STATE [A-Z_]+ -> WAKE_UP' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " 完整日志: $LOG" | tee -a "$LOG"

if [ "$ELECTRON_RC" -eq 0 ]; then
    echo "[验收] 正常退出" | tee -a "$LOG"
elif [ "$ELECTRON_RC" -ge 128 ]; then
    sig=$((ELECTRON_RC - 128))
    echo "[验收] Electron 被信号 $sig 终止" | tee -a "$LOG"
fi
exit $ELECTRON_RC
