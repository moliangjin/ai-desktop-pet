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
echo " R156 点击池 / 场景道具 / 办公待机 — Mac 真机人工验收"
echo "=========================================================="
echo " 窗口模式:   $MODE (200x240 紧凑 / 256x256 标准)"
echo " 加速模式:   $ACCEPT   (fast 只缩短等待时长, 不改状态机逻辑)"
echo " 角色资源:   R138 23 帧 RGBA PNG + R153/R156 局部烘焙帧"
echo " 场景道具:   床 / 月亮 / 被子 / 小沙发 / 转椅 / 小桌+笔记本 / 屏幕微光"
echo " Manifest:   $MANIFEST"
echo " 日志文件:   $LOG"
echo ""
echo " ┌──────────── 本轮 R156 重点看这 8 项 ────────────┐"
echo ""
echo "  A1. 点击反馈是【随机池】, 不是每次都一样"
echo "      → 连点 10 次左右, 应该看到 4~6 种不同的动作"
echo "        (比心 / 开心小跳 / 原地转身 / 歪头眨眼 / 双手小庆祝 / 开心摇摆)"
echo "      → 【不应该】连续两次点击出现同一个动作"
echo "      → 每个动作都能看清"开始→中间→结束", 不是一张定格图"
echo ""
echo "  A2. 睡觉场景: 有【床】+【月亮夜晚氛围】+【被子】"
echo "      → 角色躺在床上, 身上盖被子, 画面不挡脸"
echo ""
echo "  A3. 坐下场景: 有【小沙发】"
echo "      → 角色坐在沙发上, 屁股和沙发接触自然, 【不能悬空】, 沙发不能笨重"
echo ""
echo "  A4. 办公待机场景: 【转椅 + 小桌子 + 笔记本电脑 + 屏幕微光】"
echo "      → 角色从笔记本屏幕后面探出上半身, 像在看屏幕"
echo "      → 【不是】换了一个人: 银白短发 / 冰蓝眼睛 / 白大褂都必须保持"
echo ""
echo "  A5. 道具【不残留】"
echo "      → 睡觉醒来 / 站起来 / 开始走动之后, 床+月亮+被子 必须一起消失"
echo "      → 办公结束离开后, 转椅+桌子+笔记本 必须一起消失"
echo ""
echo "  A6. 道具【不挡脸】"
echo "      → 任何场景下, 脸和眼睛都必须清楚可见"
echo ""
echo "  A7. 桌宠透明感没被破坏"
echo "      → 窗口仍然是【透明背景】的小窗, 不是一张大插画"
echo "      → 道具只在小范围内, 不喧宾夺主"
echo ""
echo "  A8. 跳跃离地幅度有限 (已知边界, 不用报 bug)"
echo "      → 头顶留白只有约 11px (256 窗口), 跳起来离地不明显"
echo "        → 可读性主要靠"压扁↔伸展↔落地"的剪影变化"
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
echo " R156 观测汇总 (本轮新功能):" | tee -a "$LOG"
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
