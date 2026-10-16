#!/bin/bash
# candidates/candidate_b_c2/C2_Mac人工验收.command
#
# V0.0 R100 — C2 紧凑窗口 Mac 真机人工验收入口.
#
# 启动 candidate_b_c2 隔离版本.
# 默认 compact 模式 (200x240) 启动, 验收 10 项.
# 可选 standard 模式 (256x256).
#
# 不调用任何系统鼠标注入工具.
# 不请求辅助功能 / 屏幕录制权限.
# 不修改用户系统隐私设置.
# 不开启 SIP, 不绕过 macOS TCC.
# 不需要 DevTools.
#
# 退出: Cmd+Q 或关闭按钮.
# 日志: stdout + /tmp/r100_c2_mac_acceptance_*.log.
# 退出码: 0=正常, 1=启动失败, 2=参数错, 3=manifest 缺失, 4=electron 缺失, 5=asset 加载全失败

set +e
cd "$(dirname "$0")"
LOG="/tmp/r100_c2_mac_acceptance_$(date +%s).log"

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

# R100 §七 修复: 不需要 DevTools — 默认模式切换通过 set-mode IPC 走完整协议
# 但 __setMode 仍可用 — 在 Console 中用

echo "==========================================" | tee -a "$LOG"
echo " R100 C2 Mac 真机人工验收" | tee -a "$LOG"
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
echo "    __setMode('compact')   - 切到 200x240" | tee -a "$LOG"
echo "    __setMode('standard')  - 切到 256x256" | tee -a "$LOG"
echo "  切换会等待 main ack 完成才返回" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " 启动中..." | tee -a "$LOG"
echo "-------------------------------------------" | tee -a "$LOG"

# R100: 启动时设 PET_R100_SELFTEST 让 renderer 跑自测
# 退出码: electron 进程退出码
# 30 分钟兜底防止忘记关闭
PET_R100_SELFTEST=1 "$ELECTRON" "$(pwd)/src/main.js" \
    --manifest "$MANIFEST" \
    --mode "$MODE" \
    --quit-after=1800 \
    2>&1 | tee -a "$LOG"

RC=$?
echo "-------------------------------------------" | tee -a "$LOG"
echo "[C2_Mac人工验收] 退出 rc=$RC" | tee -a "$LOG"

# R100 §七: 退出后清理进程, 确认无残留
pkill -f "candidate_b_c2/src/main.js" 2>/dev/null
sleep 1
remaining=$(pgrep -f "candidate_b_c2/src/main.js" 2>/dev/null | wc -l | tr -d ' ')
if [ "${remaining:-0}" -gt 0 ]; then
    echo "[C2_Mac人工验收] WARN: 残留 ${remaining} 个 electron 进程, 已 kill" | tee -a "$LOG"
    pkill -9 -f "candidate_b_c2/src/main.js" 2>/dev/null
fi

# R100 §七: 检查 asset 加载日志
if grep -q "loaded=0 failed=" "$LOG"; then
    if grep -q "all 26 frames failed" "$LOG" 2>/dev/null; then
        echo "[C2_Mac人工验收] FATAL: asset 加载全失败, 拒绝宣布 PASS" | tee -a "$LOG"
        exit 5
    fi
fi

# R100 §七: 显示 R100 self-test 结果
if grep -q "R100 self-test.*PASS" "$LOG"; then
    echo "[C2_Mac人工验收] R100 self-test: PASS" | tee -a "$LOG"
fi
if grep -q "R100 self-test.*FAIL" "$LOG"; then
    echo "[C2_Mac人工验收] R100 self-test: FAIL" | tee -a "$LOG"
fi

echo "[C2_Mac人工验收] 完整日志: $LOG"
exit $RC
