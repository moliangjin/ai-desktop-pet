#!/bin/bash
# candidates/candidate_b_c2/C2_Mac人工验收.command
#
# V0.0 R156 — 点击互动扩展 + 场景道具 + 办公待机场景 (承接 R153/R148/R144/R141)
#
# 本轮目标: 在保持"桌宠小窗 + 透明背景"的前提下,
#   ① 点击反馈从固定 1 个动作扩成 6 个动作的**随机池** (每个都有开始/中间/结束);
#   ② 睡觉配床+月亮夜晚氛围, 坐下配小沙发;
#   ③ 新增"在电脑前办公"的待机场景 (转椅+小桌+笔记本+屏幕微光);
#   ④ 道具只在对应动作出现, 退出时一并消失, 绝不残留; 不挡脸; 角色身份不漂移。
#
# 启动内容:
#   - 正式角色 (R138 的 23 帧 RGBA PNG, 六组动画) + R153/R156 局部烘焙帧
#   - 自主行为引擎 (IDLE / WALK / GESTURE / SIT / DOZE / **WORK 办公** / SLEEP / WAKE / DRAGGING)
#   - 场景道具 (床/月亮/被子/小沙发/转椅/小桌+笔记本/屏幕微光, 程序化绘制)
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
#   ./C2_Mac人工验收.command work      → ★ R170 验收入口: 锁定"电脑办公"场景
#   ./C2_Mac人工验收.command eat_fruit → ★ R170 验收入口: 锁定"吃水果"场景
#     (上面两个是**验收专用入口**: 自主行为被暂停, 场景一直停在原地供你细看;
#      与"正式自主行为模式"完全分离, 不会随机跑掉)
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
DEMO_SCENE=""
for arg in "$@"; do
    case "$arg" in
        compact|standard) MODE="$arg" ;;
        fast|acceptance)  ACCEPT="on" ;;
        off|normal)       ACCEPT="off" ;;
        work)             DEMO_SCENE="work" ;;
        eat_fruit|eat)    DEMO_SCENE="eat_fruit" ;;
        *) echo "用法: $0 [compact|standard] [fast|off] [work|eat_fruit]"; exit 2 ;;
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
echo " R156 点击池 / 场景道具 / 办公待机 — Mac 真机人工验收"
echo "=========================================================="
echo " 窗口模式:   $MODE (200x240 紧凑 / 256x256 标准)"
echo " 加速模式:   $ACCEPT   (fast 只缩短等待时长, 不改状态机逻辑)"
echo " 场景锁定:   ${DEMO_SCENE:-<无, 走正式自主行为>}"
echo " 角色资源:   R138 23 帧 RGBA PNG + R153/R156/R170 局部烘焙帧"
echo " 场景道具:   床 / 月亮 / 被子 / 小沙发 / 转椅 / 小桌+笔记本 / 屏幕微光 / 小凳+果盘"
echo " Manifest:   $MANIFEST"
echo " 日志文件:   $LOG"
echo ""
echo " ┌──────────── 本轮 R158 重点看这 8 项 ────────────┐"
echo ""
echo "  A1. 点击反馈是【随机池】, 且这次是【真手势】"
echo "      → 连点 10 次左右, 应该看到 4~6 种不同的动作"
echo "        (真挥手 / 双臂欢呼 / 比心 / 鼓掌 / 开心跳跃 / 歪头眨眼)"
echo "      → 【不应该】连续两次点击出现同一个动作"
echo "      → 每个动作都能看清"开始→中间→结束", 不是一张定格图"
echo ""
echo "  A2. 【挥手】要看到手臂真的抬起来, 手在头旁边左右摆"
echo "      → 不是"手放在胸前", 也不是身体左右平移"
echo ""
echo "  A3. 【双臂欢呼】两条手臂都要举高成 V 字"
echo "      → R156 那一版"双臂抬起"不明显, 这版应该一眼看得出"
echo ""
echo "  A4. 【比心】双手在胸前合拢 + 胸口上方出现一颗爱心"
echo "      → 爱心是特效, 手指级心形在这么小的尺寸里读不出来 (已知边界)"
echo "      → 【不是】单手横在胸前 (R156 的老问题)"
echo ""
echo "  A5. 【鼓掌】双臂先张开再合拢, 开合两种剪影差别要明显"
echo ""
echo "  A6. 【跳跃】腾空那一下要看到双臂上扬 + 身体离地"
echo "      → 头顶留白只有约 11px (256 窗口), 离地幅度有限 (已知边界)"
echo "        → 可读性主要靠"蓄力压扁↔腾空伸展↔落地压缩"的剪影变化"
echo ""
echo "  A7. 【歪头眨眼】头要真的歪, 不能只是换了表情"
echo ""
echo "  A8. 手臂抬起后, 大褂边缘不能有【白块/黑边/鬼影】残留"
echo "      → 抬手的原位置应该露出完整的大褂, 不能缺一块或多一块"
echo "      → 角色整体轮廓仍然要像"同一个角色", 不能变形/变胖"
echo ""
echo " └──────────────────────────────────────────────────┘"
echo ""
echo "  R141/R144/R148/R153 基础项 (顺带确认没被本轮改坏):"
echo ""
echo "  1. 桌宠出现          — 银白短发科技研究员, 窗口透明无白底"
echo "  2. 自主待机          — 自行呼吸 + 眨眼, 无需点击"
echo "  3. 自主行走          — 角色自己走, 桌面位置真的在移动"
echo "  4. 自动转向          — 走到屏幕边缘后自己掉头"
echo "  5. 坐躺过渡          — 坐下→躺下→醒来是渐变, 不是瞬间切换"
echo "  6. 鼠标拖拽          — 按住拖动, 窗口跟随鼠标; 松手后恢复自主活动"
echo "  7. 正常退出          — Cmd+Q 退出, 桌面无残留窗口"
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
# R170: 验收专用入口 —— 锁定场景 + 暂停自主决策 (与正式自主行为完全分离)
if [ -n "$DEMO_SCENE" ]; then
    EXTRA="$EXTRA --demo-scene $DEMO_SCENE"
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

# R144 P0-3: 资源未就绪必须明确 FAIL (拒绝虚假 PASS)
if grep -q "R144 ASSETS_ERROR" "$LOG" 2>/dev/null; then
    echo "[验收] FATAL: 资源未就绪, 自主行为按设计未启动 (R144 ASSETS_ERROR)" | tee -a "$LOG"
    exit 10
fi
if ! grep -q "R144 ASSETS_READY" "$LOG" 2>/dev/null; then
    echo "[验收] FATAL: 未收到资源就绪握手" | tee -a "$LOG"
    exit 10
fi

# 汇总行为观测
echo "" | tee -a "$LOG"
echo " 行为观测汇总:" | tee -a "$LOG"
echo "   状态转移次数: $(grep -c -e 'R141 STATE' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   窗口移动次数: $(grep -c -e 'R14[14] MOVE' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   撞边转向次数: $(grep -c -e 'edge-turn' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   睡眠序列:     ENTER=$(grep -cE -e 'R141 STATE [A-Z_]+ -> SLEEP_ENTER' "$LOG" 2>/dev/null) LOOP=$(grep -cE -e 'R141 STATE [A-Z_]+ -> SLEEP_LOOP' "$LOG" 2>/dev/null) WAKE=$(grep -cE -e 'R141 STATE [A-Z_]+ -> WAKE_UP' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " R158 观测汇总 (本轮新功能):" | tee -a "$LOG"
echo "   点击动作种类: $(grep -oE 'R156 CLICK_REACTION start action=[a-z_]+' "$LOG" 2>/dev/null | grep -oE 'action=[a-z_]+' | sort -u | tr '\n' ' ')" | tee -a "$LOG"
echo "   爱心特效挂载: $(grep -c 'R156 PROPS action=cheer_heart scene=yes mounted=prop_heart' "$LOG" 2>/dev/null) 次" | tee -a "$LOG"
echo "   点击帧总数:   $(grep -c 'R156 PROPS action=cheer_heart' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " R170 观测汇总 (本轮: 恢复办公 + 新增吃水果):" | tee -a "$LOG"
echo "   办公场景次数: $(grep -cE -e 'R141 STATE [A-Z_]+ -> WORK' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   吃水果次数:   $(grep -cE -e 'R141 STATE [A-Z_]+ -> EAT_FRUIT' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   吃水果挂载:   $(grep -c 'R156 PROPS action=eat_fruit scene=yes' "$LOG" 2>/dev/null) 次" | tee -a "$LOG"
echo "   场景锁定:     $(grep -c 'R170 DEMO_SCENE' "$LOG" 2>/dev/null) (0 = 走正式自主行为)" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " R156 观测汇总 (上一轮, 顺带确认没被改坏):" | tee -a "$LOG"
echo "   办公待机次数: $(grep -cE -e 'R141 STATE [A-Z_]+ -> WORK' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   点击反馈次数: $(grep -c 'R156 CLICK_REACTION start' "$LOG" 2>/dev/null)" | tee -a "$LOG"
echo "   点击动作种类: $(grep -oE 'R156 CLICK_REACTION start action=[a-z_]+' "$LOG" 2>/dev/null | grep -oE 'action=[a-z_]+' | sort -u | tr '\n' ' ')" | tee -a "$LOG"
echo "   道具加载结果: $(grep -oE 'R156 props-asset-report .*' "$LOG" 2>/dev/null | tail -1)" | tee -a "$LOG"
echo "   道具挂载记录: $(grep -oE 'R156 PROPS action=[a-z_]+ scene=[a-z]+ mounted=[a-z_,]+' "$LOG" 2>/dev/null | sort -u | tr '\n' ' ')" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo " 完整日志: $LOG" | tee -a "$LOG"

if [ "$ELECTRON_RC" -eq 0 ]; then
    echo "[验收] 正常退出" | tee -a "$LOG"
elif [ "$ELECTRON_RC" -ge 128 ]; then
    sig=$((ELECTRON_RC - 128))
    echo "[验收] Electron 被信号 $sig 终止" | tee -a "$LOG"
fi
exit $ELECTRON_RC
