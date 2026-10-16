#!/bin/bash
# candidates/candidate_b_c2/C2_Mac人工验收.command
#
# V0.0 R98 — C2 紧凑窗口方案 Mac 真机人工验收入口.
#
# 启动 candidate_b_c2 (隔离版本, 原始候选 B 零修改).
# 不调用任何系统鼠标注入工具.
# 不请求辅助功能 / 屏幕录制权限.
# 不修改用户系统隐私设置.
# 不开启 SIP, 不绕过 macOS TCC.
#
# 模式:
#   --mode compact  (默认) 200x200 紧凑窗口, 减少桌面遮挡
#   --mode standard         256x256 标准窗口 (与 R60 输入基线一致)
#
# 退出: Cmd+Q 或关闭按钮.
# 日志: stdout 输出到 .command 弹出的 Terminal 窗口.
# 残留: 关闭后不遗留后台进程 (BrowserWindow 在 window-all-closed 时退出 app).

set +e
cd "$(dirname "$0")"

# 节点模块若未建立 symlink, 自动建立
if [ ! -e node_modules ]; then
    if [ -d ../candidate_b_electronpixir/node_modules ]; then
        ln -sf ../candidate_b_electronpixir/node_modules node_modules
    else
        echo "[C2_Mac人工验收] FATAL: node_modules 不存在, 请先 cd 到候选 B 目录跑 npm install"
        exit 1
    fi
fi

# 解析 --mode 参数
MODE="${1:-compact}"
case "$MODE" in
    compact|standard) ;;
    *)
        echo "用法: $0 [compact|standard]"
        echo "  compact  - 200x200 紧凑窗口 (默认, 减少桌面遮挡)"
        echo "  standard - 256x256 标准窗口 (与 R60 输入基线一致)"
        exit 2
        ;;
esac

# Manifest 路径 (R60 baseline 资源)
MANIFEST="$(cd ../../assets/prototype_chibi && pwd)/manifest.json"
if [ ! -f "$MANIFEST" ]; then
    echo "[C2_Mac人工验收] FATAL: manifest 不存在: $MANIFEST"
    exit 3
fi

# Electron binary
ELECTRON="$(cd ../candidate_b_electronpixir && pwd)/node_modules/.bin/electron"
if [ ! -x "$ELECTRON" ]; then
    echo "[C2_Mac人工验收] FATAL: electron 不存在: $ELECTRON"
    exit 4
fi

echo "=========================================="
echo " R98 C2 Mac 真机人工验收"
echo "=========================================="
echo "  模式:        $MODE"
echo "  Manifest:    $MANIFEST"
echo "  Electron:    $ELECTRON"
echo ""
echo " 验收项目 (请逐一确认):"
echo "  1. 桌宠正常启动 (无窗口/控制台错误)"
echo "  2. 角色完整显示 (无裁切)"
echo "  3. 待机动画流畅"
echo "  4. 行走/跳跃/拖拽动画不裁切"
echo "  5. 单击角色有响应"
echo "  6. 拖拽桌宠正常 (无跳跃/无卡死)"
echo "  7. 多次拖拽后位置正确"
echo "  8. 释放鼠标后不继续跟随"
echo "  9. 桌宠外侧点击桌面应用不受紧凑窗口外区域干扰 (C2 减小遮挡效果)"
echo " 10. Cmd+Q 正常退出, 不残留窗口"
echo ""
echo " 模式切换 (高级):"
echo "  在 DevTools 控制台输入 __setMode('compact') 或 __setMode('standard') 切换"
echo ""
echo " 启动中..."
echo "-------------------------------------------"

# 启动 (quit-after 30 分钟兜底, 防止忘记关闭)
"$ELECTRON" "$(pwd)/src/main.js" --manifest "$MANIFEST" --mode "$MODE" --quit-after=1800 2>&1

RC=$?
echo "-------------------------------------------"
echo "[C2_Mac人工验收] 退出 rc=$RC"
exit $RC
