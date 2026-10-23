#!/bin/bash
# ==============================================================
# R182: 把「AI桌宠」桌面启动图标装到用户桌面。
#
# 为什么不是符号链接:
#   实测**符号链接**在 macOS 桌面上拿不到网格槽位 —— Finder 报它的坐标是
#   {-1,-1} (即"没有位置"), 结果就是**桌面上根本看不到它**。
#   ⇒ 桌面这一份必须是**真 app bundle** (Finder 才会正常排位 + 画图标)。
#
# 为什么还要显式设置位置:
#   该机桌面是 `arrangeBy = dateAdded` 排序, 而桌面网格**溢出屏幕**
#   (实测有条目落在 y=1054, 屏幕只有 1080 高) —— 新增条目会被排到屏幕外。
#   `F_SETADDTIME`(改"添加日期") 在现代 macOS/APFS 上已失效 (EINVAL),
#   所以只能用 Finder API 显式给一个**可见**的空闲槽位。
#   实测: 设完之后 **Finder 完全重启** 坐标不变 ⇒ 已持久化。
#
# 为什么选 (1165,46) 这个槽位:
#   实测该机桌面网格 **只占 x=65~395 四列** (42 个桌面项里有 7 个外置磁盘图标
#   由 macOS 固定画在右上角, 报 {-1,-1} 属正常), 屏幕右侧 x>=505 完全空闲。
#   而 x=65~395 / y=46~538 这片区域**被两个已打开的 Finder 窗口整个盖住**
#   (实测窗口占位 x=8~928, y=46~538) —— 图标就算画了也看不见。
#   (1165,46) 同时满足: 空闲列 + 避开所有窗口 + 在屏幕内。
#   注: 设在空列的第 2 行 (如 1165,158) 时, Finder 重启会把图标归位到该列首行
#   (1165,46) —— 网格对空列只认首行, 所以这里直接写首行坐标。
#
# 用法:
#   bash 113_R182_install_desktop_icon.sh          # 安装 + 定位 + 持久化校验 + 冒烟
#   bash 113_R182_install_desktop_icon.sh --verify # 只做体检
# ==============================================================
set -u

CAND="$(cd "$(dirname "$0")" && pwd)"
# 仓库根 = candidate_b_c2 的上两级 (.../candidates/candidate_b_c2 -> 仓库根)
REPO="$(cd "$CAND/../.." && pwd)"
BUNDLE="$REPO/_app_bundle/AI桌宠.app"
DESKTOP="$HOME/Desktop"
TARGET="$DESKTOP/AI桌宠.app"
TRASH="/Users/musk123/.minimax/bin/mavis-trash"
LOG="$HOME/Library/Logs/AI桌宠/launcher.log"

# 空闲列 + 无遮挡的可见槽位 (详见文件头说明)
POS_X=1165
POS_Y=46

if [ "${1:-}" = "--verify" ]; then
    echo "=== 体检 ==="
    echo "桌面项: $TARGET"
    [ -d "$TARGET" ] && echo "  bundle 存在: ✅" || echo "  bundle 存在: ❌"
    [ -x "$TARGET/Contents/MacOS/AIPet" ] && echo "  启动器可执行: ✅" || echo "  启动器可执行: ❌"
    [ -f "$TARGET/Contents/Resources/AppIcon.icns" ] && echo "  图标在位: ✅" || echo "  图标在位: ❌"
    echo -n "  Finder 坐标: "
    osascript -e 'tell application "Finder" to get position of item "AI桌宠.app" of desktop' 2>&1 | head -1
    exit 0
fi

echo "=== ① 前置检查 ==="
for f in "$BUNDLE/Contents/Info.plist" "$BUNDLE/Contents/Resources/AppIcon.icns" "$BUNDLE/Contents/MacOS/AIPet"; do
    if [ ! -f "$f" ]; then
        echo "  ❌ 仓库内 bundle 不完整, 缺: $f"
        echo "     先跑: python3 110_R182_desktop_icon.py --variant B"
        exit 1
    fi
done
echo "  仓库 bundle 完整: ✅"

echo "=== ② 清理旧的桌面项 ==="
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
    if [ -x "$TRASH" ]; then
        "$TRASH" -- "$TARGET" >/dev/null 2>&1 && echo "  已移除旧桌面项(可恢复回收站)" \
            || echo "  ❌ 旧桌面项回收失败, 请手动处理: $TARGET"
    else
        echo "  ❌ 找不到 mavis-trash, 为安全起见不自动删除: $TARGET"
        exit 1
    fi
fi

echo "=== ③ 安装真 app bundle 到桌面 ==="
mkdir -p "$TARGET/Contents/MacOS" "$TARGET/Contents/Resources"
cp "$BUNDLE/Contents/Info.plist" "$TARGET/Contents/Info.plist"
cp "$BUNDLE/Contents/Resources/AppIcon.icns" "$TARGET/Contents/Resources/AppIcon.icns"
# 启动器只做委托: 真正的启动逻辑在仓库内那一份 (单一真身, 不重复维护)
cat > "$TARGET/Contents/MacOS/AIPet" <<SH
#!/bin/bash
# 桌面「AI桌宠」启动器 —— 委托给仓库内的正式启动器
exec "$BUNDLE/Contents/MacOS/AIPet" "\$@"
SH
chmod +x "$TARGET/Contents/MacOS/AIPet"
echo "  已安装: $TARGET"

echo "=== ④ 让 Finder 刷新并给它一个可见位置 ==="
osascript -e 'tell application "Finder" to update every item of desktop' >/dev/null 2>&1
sleep 1
osascript -e "tell application \"Finder\" to set position of item \"AI桌宠.app\" of desktop to {$POS_X, $POS_Y}" >/dev/null 2>&1
sleep 1
POS=$(osascript -e 'tell application "Finder" to get position of item "AI桌宠.app" of desktop' 2>&1 | head -1)
echo "  Finder 内存中的坐标: $POS"
case "$POS" in
    *"$POS_X, $POS_Y"*) echo "  已排进可见网格 ✅" ;;
    *) echo "  ⚠️ 坐标不是预期值, 期望 $POS_X,$POS_Y" ;;
esac

echo "=== ④b 落盘校验: 桌面图标坐标是写进 ~/Desktop/.DS_Store 的 Iloc 记录 ==="
echo "     (实测落盘延迟约 6 秒; 没落盘的话 Finder 一重启坐标就退回 {-1,-1}, 图标根本不画)"
DS="$DESKTOP/.DS_Store"
FLUSHED=0
for _ in $(seq 1 30); do
    if [ -f "$DS" ] && python3 - "$DS" <<'PY' 2>/dev/null
import sys
d = open(sys.argv[1], 'rb').read()
sys.exit(0 if 'AI桌宠.app'.encode('utf-16-be') in d else 1)
PY
    then
        FLUSHED=1; break
    fi
    sleep 2
done
if [ "$FLUSHED" = "1" ]; then
    echo "  .DS_Store 已写入 AI桌宠.app 的 Iloc 记录 ✅ (坐标已落盘)"
else
    echo "  ❌ .DS_Store 里没有 AI桌宠.app 的记录, 坐标没落盘 ⇒ 重启后图标会消失"
fi

echo "=== ④c 持久化校验: 完全重启 Finder 后坐标是否还在 ==="
killall Finder >/dev/null 2>&1
sleep 7
POS2=$(osascript -e 'tell application "Finder" to get position of item "AI桌宠.app" of desktop' 2>&1 | head -1)
echo "  Finder 重启后坐标: $POS2"
case "$POS2" in
    *"$POS_X, $POS_Y"*) echo "  重启后仍在原位 ✅ (已持久化)" ;;
    *) echo "  ❌ 重启后位置漂移 ⇒ 图标不会被画出来" ;;
esac

echo "=== ⑤ 冒烟: 跑一次桌面启动器 ==="
pkill -f "candidate_b_c2/src/main.js" 2>/dev/null
sleep 2
: > "$LOG"
"$TARGET/Contents/MacOS/AIPet" >/dev/null 2>&1
sleep 8
if grep -q "R144 ASSETS_READY" "$LOG" 2>/dev/null; then
    echo "  启动判据: ✅ 资源就绪 (R144 ASSETS_READY)"
    grep -m1 "R144 ASSETS_READY" "$LOG"
else
    echo "  启动判据: ❌ 未见 R144 ASSETS_READY, 见 $LOG"
    exit 1
fi
echo
echo "完成。桌面坐标 ($POS_X,$POS_Y) 处就是「AI桌宠」(菜单栏正下方、偏右)。"
