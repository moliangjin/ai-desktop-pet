#!/bin/bash
# candidates/candidate_b_c2/C2_Mac人工验收.command
#
# V0.0 R102 — C2 紧凑窗口 Mac 真机人工验收入口.
#
# 启动 candidate_b_c2 隔离版本.
# 默认 compact 模式 (200x240) 启动, 验收 10 项.
#
# 不调用任何系统鼠标注入工具.
# 不请求辅助功能 / 屏幕录制权限.
# 不修改用户系统隐私设置.
# 不开启 SIP, 不绕过 macOS TCC.
# 不需要 DevTools.
# 不在用户模式运行会改变显示模式的内部自检 (R102 P0-2).
# 不使用全局 pkill 误杀其他应用 (R102 P0-6).
#
# 退出: Cmd+Q 或关闭按钮.
# 日志: /tmp/r102_c2_mac_acceptance_<ts>.log.
# 退出码:
#   0  = 正常退出 (用户 Cmd+Q 或 --quit-after 超时)
#   2  = 参数错
#   3  = manifest 缺失
#   4  = electron 缺失
#   10 = 资源加载全部失败
#   130+ = electron 实际退出码

set +e
cd "$(dirname "$0")"
LOG="/tmp/r102_c2_mac_acceptance_$(date +%s).log"

# 节点模块若未建立 symlink, 自动建立
if [ ! -e node_modules ]; then
    if [ -d ../candidate_b_electronpixir/node_modules ]; then
        ln -sf ../candidate_b_electronpixir/node_modules node_modules
    else
        echo "[C2_Mac人工验收] FATAL: node_modules 不存在, 请先 cd 到候选 B 目录跑 npm install" | tee -a "$LOG"
        exit 1
    fi
fi

# 解析参数
MODE="${1:-compact}"
case "$MODE" in
    compact|standard) ;;
    *)
        echo "用法: $0 [compact|standard]"
        echo "  compact  (默认) - 200x240 紧凑窗口, 减少桌面遮挡 27%"
        echo "  standard        - 256x256 标准窗口 (R60 基线)"
        exit 2
        ;;
esac

# Manifest 路径
MANIFEST="$(cd ../../assets/prototype_chibi && pwd)/manifest.json"
if [ ! -f "$MANIFEST" ]; then
    echo "[C2_Mac人工验收] FATAL: manifest 不存在: $MANIFEST" | tee -a "$LOG"
    exit 3
fi

# Electron binary
ELECTRON="$(cd ../candidate_b_electronpixir && pwd)/node_modules/.bin/electron"
if [ ! -x "$ELECTRON" ]; then
    echo "[C2_Mac人工验收] FATAL: electron 不存在: $ELECTRON" | tee -a "$LOG"
    exit 4
fi

# R102 P0-4: 准备变量保留 Electron 真实退出码
ELECTRON_PID=""

# R102 P0-6: 针对性进程清理 — 仅 kill 本次启动的 Electron PID
# 不使用 pkill -f "Electron Helper" 等全局命令
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

echo "==========================================" | tee -a "$LOG"
echo " R102 C2 Mac 真机人工验收" | tee -a "$LOG"
echo "==========================================" | tee -a "$LOG"
echo "  模式:        $MODE" | tee -a "$LOG"
echo "  Manifest:    $MANIFEST" | tee -a "$LOG"
echo "  Electron:    $ELECTRON" | tee -a "$LOG"
echo "  日志文件:    $LOG" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " 验收 10 项 (请逐一确认):" | tee -a "$LOG"
echo "  1. 桌宠正常启动 (无窗口/控制台错误)" | tee -a "$LOG"
echo "  2. 角色完整显示 (无裁切, 含 jump 跳起)" | tee -a "$LOG"
echo "  3. 待机动画流畅" | tee -a "$LOG"
echo "  4. 行走/跳跃/拖拽动画不裁切" | tee -a "$LOG"
echo "  5. 单击角色有响应 (触发 drag 动作)" | tee -a "$LOG"
echo "  6. 拖拽桌宠正常 (无跳跃/无卡死)" | tee -a "$LOG"
echo "  7. 多次拖拽后位置正确" | tee -a "$LOG"
echo "  8. 释放鼠标后不继续跟随" | tee -a "$LOG"
echo "  9. 桌宠外侧点击 Finder 等普通应用时不会受到超出紧凑窗口范围的遮挡" | tee -a "$LOG"
echo " 10. Cmd+Q 正常退出, 不残留窗口" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " 模式切换 (高级):" | tee -a "$LOG"
echo "  按 Cmd+Option+I 打开 DevTools, 在 Console 输入:" | tee -a "$LOG"
echo "    await __setMode('compact')   - 切到 200x240" | tee -a "$LOG"
echo "    await __setMode('standard')  - 切到 256x256" | tee -a "$LOG"
echo "  切换会等待 main ack 完成才返回" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " 启动中..." | tee -a "$LOG"
echo "-------------------------------------------" | tee -a "$LOG"

# R102 P0-2: 不设置 PET_R100_SELFTEST — 防止自检污染用户当前 mode
# R102 P0-4: 用 PIPESTATUS[0] 保留 Electron 真实退出码 (避免 pipe 传 tee 改 $?)
# R102 P0-5: --quit-after=<value> 形式 (R102 任务书验证)
"$ELECTRON" "$(pwd)/src/main.js" \
    --manifest "$MANIFEST" \
    --mode "$MODE" \
    --quit-after=1800 \
    > "$LOG" 2>&1
ELECTRON_RC=$?

# R102 P0-4: 直接取 Electron 真实退出码 (不再 pipe 到 tee 改 $?)
echo "-------------------------------------------" | tee -a "$LOG"
echo "[C2_Mac人工验收] 退出 rc=$ELECTRON_RC" | tee -a "$LOG"

# R102 §一-10: 资源加载失败必须明确 FAIL
if grep -q "all 26 frames failed" "$LOG" 2>/dev/null; then
    echo "[C2_Mac人工验收] FATAL: 26 帧全部加载失败" | tee -a "$LOG"
    exit 10
fi
# 单独检查 (R100 §七 之后)
if grep -qE "asset-report.*loaded=0 failed=[0-9]+" "$LOG" 2>/dev/null; then
    zero_loaded=$(grep -cE "asset-report.*loaded=0 failed=[0-9]+" "$LOG")
    if [ "$zero_loaded" -ge 4 ]; then
        echo "[C2_Mac人工验收] FATAL: 至少 4 个动作 asset loaded=0, 拒绝宣布准备 PASS" | tee -a "$LOG"
        exit 10
    fi
fi

# 退出码映射
#   0      = 正常 (用户 Cmd+Q)
#   130+   = SIGINT/SIGTERM (用户强制)
#   137    = SIGKILL (timeout kill)
#   其它   = 异常
if [ "$ELECTRON_RC" -eq 0 ]; then
    echo "[C2_Mac人工验收] 正常退出" | tee -a "$LOG"
elif [ "$ELECTRON_RC" -ge 128 ]; then
    sig=$((ELECTRON_RC - 128))
    echo "[C2_Mac人工验收] Electron 被信号 $sig 终止" | tee -a "$LOG"
fi

echo "[C2_Mac人工验收] 完整日志: $LOG"
exit $ELECTRON_RC
