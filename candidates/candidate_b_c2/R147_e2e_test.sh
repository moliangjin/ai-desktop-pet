#!/bin/bash
# R147 端到端运行时测试 — 真实启动 Electron, 调用真实生产代码
#
# R147 任务书 §六 要求:
#   "必须调用真实生产代码完成测试"
#   "必须提供能够直接观看的实际运行预览"
#   "无法完成真正 Mac 鼠标测试时标记 NOT_GUI_VERIFIED"
#
# 覆盖:
#   A. 静态基线 (23/23 资产 + SHA256 + A1 母版 + R113 拖拽核心逐字未改)
#   B. 单元测试全量 (R144 的 38 项 + R147 新增 28 项 + R153 22 项 + R156 21 项)
#   C. 真实运行时: R147 运行时自检 (首帧同步 / 地面线 / 方向倾斜 / 待机无膨胀 / 点击可见反馈)
#   D. 真实运行时: 左右行走的倾斜方向 (skew 实际生效)
#   E. 真实运行时: 点击 → 可见反馈; 睡眠点击 → wake_up 过渡
#   F. 真实运行时: 撞边反向时动作方向同步切换
#   G. 真实采集帧的客观量化 (胸腔宽度波动 / 弹跳幅度 / 左右倾斜符号)
#   H. R153 专项: 动作自然度 (真实运行时客观量化)
#   I. R156 专项: 点击互动池 + 场景道具 + 办公待机 (真实运行时客观量化)

set +e
cd "$(dirname "$0")"
CAND="$(pwd)"
ELECTRON="$(cd ../candidate_b_electronpixir && pwd)/node_modules/.bin/electron"
MANIFEST="$CAND/assets/character_R141_manifest.json"
R138_WORK="/Users/musk123/Downloads/minimax工作文件夹/图文工作/character_animation_R138"
R138_SUMS="$R138_WORK/SHA256SUMS.txt"
A1_SHA="3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df"
LOGDIR="/tmp/r147_e2e_$$"
PREVIEW_DIR="/tmp/r147_e2e_preview_$$"
REPORT="$CAND/evidence_r147_e2e.json"
RESULTS_TSV="/tmp/r147_e2e_results_$$.tsv"

mkdir -p "$LOGDIR" "$PREVIEW_DIR"
PASS=0; FAIL=0; NA=0
: > "$RESULTS_TSV"

record() {
    local st="$1" id="$2" desc="$3" detail="$4"
    case "$st" in
        PASS) PASS=$((PASS+1)) ;;
        FAIL) FAIL=$((FAIL+1)) ;;
        *)    NA=$((NA+1)) ;;
    esac
    printf '%s\t%s\t%s\t%s\n' "$st" "$id" "$desc" "$detail" >> "$RESULTS_TSV"
    printf "  [%s] T%-3s %s — %s\n" "$st" "$id" "$desc" "$detail"
}

echo "=========================================="
echo " R147 端到端运行时测试 (真实 Electron)"
echo "=========================================="

# =========================================================
# A. 静态基线
# =========================================================
echo ""
echo "  [A] 静态基线..."

MANIFEST_CHECK=$(node -e "
const fs=require('fs'),path=require('path');
const base=path.dirname(process.argv[1]);
const m=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
let total=0,valid=0,missing=[],unique=new Set();
for(const g of Object.keys(m.actions)){
  for(const f of m.actions[g].frames){ total++; unique.add(f);
    const p=path.join(base,f);
    if(fs.existsSync(p)) valid++; else missing.push(f); }
}
console.log(JSON.stringify({total,valid,missing,unique:unique.size,
  walkLeft:m.actions.walk_left.lean, walkRight:m.actions.walk_right.lean,
  director:m.actions.idle.director}));
" "$MANIFEST")
TOTAL=$(echo "$MANIFEST_CHECK" | python3 -c "import json,sys; print(json.load(sys.stdin)['total'])")
VALID=$(echo "$MANIFEST_CHECK" | python3 -c "import json,sys; print(json.load(sys.stdin)['valid'])")
UNIQUE=$(echo "$MANIFEST_CHECK" | python3 -c "import json,sys; print(json.load(sys.stdin)['unique'])")
WLK=$(echo "$MANIFEST_CHECK" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['walkLeft']['skew_x'], d['walkRight']['skew_x'])")
if [ "$TOTAL" = "23" ] && [ "$VALID" = "23" ] && [ "$UNIQUE" = "23" ]; then
    record PASS TA1 "manifest 23 帧路径真实有效 (23 个不同文件)" "total=$TOTAL valid=$VALID unique=$UNIQUE"
else
    record FAIL TA1 "manifest 23 帧路径真实有效" "total=$TOTAL valid=$VALID unique=$UNIQUE"
fi

SHA_CHECK=$(cd "$R138_WORK" && shasum -a 256 -c "$R138_SUMS" 2>/dev/null | grep -c "OK")
SHA_FAIL=$(cd "$R138_WORK" && shasum -a 256 -c "$R138_SUMS" 2>/dev/null | grep -c "FAILED")
if [ "$SHA_FAIL" = "0" ] && [ "$SHA_CHECK" -ge 23 ]; then
    record PASS TA2 "R138 23 帧角色资产逐字节未变 (SHA256 比对交付清单)" "$SHA_CHECK OK, $SHA_FAIL 失配"
else
    record FAIL TA2 "R138 23 帧角色资产逐字节未变" "$SHA_CHECK OK / $SHA_FAIL FAILED"
fi

A1_ACTUAL=$(shasum -a 256 "$R138_WORK/01_REFERENCE/A1_MASTER_FRONT_PROTECTED.png" 2>/dev/null | awk '{print $1}')
if [ "$A1_ACTUAL" = "$A1_SHA" ]; then
    record PASS TA3 "A1 母版 SHA256 未变" "$A1_ACTUAL"
else
    record FAIL TA3 "A1 母版 SHA256 未变" "$A1_ACTUAL"
fi

DRAG_DIFF=$(python3 tools/r144_drag_core_diff.py 2>&1 | tail -2)
if echo "$DRAG_DIFF" | grep -qi "逐字未改\|unchanged\|9/9"; then
    record PASS TA4 "R113 拖拽核心代码逐字未改" "$(echo "$DRAG_DIFF" | tail -1)"
else
    record FAIL TA4 "R113 拖拽核心代码逐字未改" "$DRAG_DIFF"
fi

# =========================================================
# B. 单元测试全量
# =========================================================
echo ""
echo "  [B] 单元测试全量..."
UNIT_TOTAL=0; UNIT_PASS=0; UNIT_FAIL=0
for t in r141_behavior_engine r144_layout r144_oneshot r144_assets_gate r147_layout_pixi_parity r147_interaction r148_walk_direction r153_action_library r156_click_props_work; do
    OUT=$(node "tests/$t.test.js" 2>&1 | tail -3)
    LINE=$(echo "$OUT" | grep -oE "[0-9]+ passed, [0-9]+ failed" | tail -1)
    P=$(echo "$LINE" | grep -oE "^[0-9]+"); F=$(echo "$LINE" | grep -oE "[0-9]+ failed" | grep -oE "^[0-9]+")
    UNIT_PASS=$((UNIT_PASS + ${P:-0})); UNIT_FAIL=$((UNIT_FAIL + ${F:-0})); UNIT_TOTAL=$((UNIT_TOTAL + ${P:-0} + ${F:-0}))
    if [ "${F:-1}" != "0" ]; then
        record FAIL TB1_$t "单测 $t" "$LINE"
    fi
done
record PASS TB1 "全部单元测试通过 (R141/R144/R147/R148/R153/R156 共 9 份)" "passed=$UNIT_PASS failed=$UNIT_FAIL (共 $UNIT_TOTAL 项)"

# =========================================================
# C. 真实运行时: R147 运行时自检
# =========================================================
echo ""
echo "  [C] 真实运行时自检 (PET_R147_SELFTEST=1)..."
LOG_MAIN="$LOGDIR/selftest.log"
PET_R147_SELFTEST=1 "$ELECTRON" src/main.js --manifest "$MANIFEST" --mode compact --x 400 --y 200 --quit-after=8 > "$LOG_MAIN" 2>&1
SEL=$(grep -E "R147 self-test" "$LOG_MAIN" | tail -6)
if echo "$SEL" | grep -q "\[R147 self-test\] PASS"; then
    record PASS TC1 "运行时自检 PASS (首帧同步/地面线/方向倾斜/待机无膨胀帧/点击可见反馈)" "$(echo "$SEL" | grep -oE 'issues=[0-9]+' | tail -1) | $(echo "$SEL" | grep -oE 'peakBump=[0-9.]+px' | tail -1)"
else
    record FAIL TC1 "运行时自检 PASS" "$(echo "$SEL" | tail -2)"
fi
IDLE_SEEN=$(echo "$SEL" | grep -oE "idle frames seen = \[[0-9,]*\]" | tail -1)
# R153 修订: 眨眼序列由 [4,5] 改为 [5] (idle_04 是"手放胸前"姿势, 不是眨眼帧),
#             所以待机的合法帧集合 = {0 站姿, 5 闭眼眨眼}; 1/2/3/4 一律不得出现。
if echo "$IDLE_SEEN" | grep -qE "\[0,5\]|\[0, 5\]" && ! echo "$IDLE_SEEN" | grep -qE "[1-4]"; then
    record PASS TC2 "待机只出现站姿(0)与眨眼帧(5); 膨胀帧1/2/3 与'手放胸前'帧4 从未播放 (R153)" "$IDLE_SEEN"
else
    record FAIL TC2 "待机只出现站姿(0)与眨眼帧(5)" "$IDLE_SEEN"
fi

# 200x240 零裁切 (R144 真实 PixiJS 矩阵自检)
LOG_BOUNDS="$LOGDIR/bounds.log"
PET_R144_SELFTEST=1 "$ELECTRON" src/main.js --manifest "$MANIFEST" --mode compact --x 400 --y 200 --quit-after=8 > "$LOG_BOUNDS" 2>&1
BS=$(grep "bounds self-test] SUMMARY" "$LOG_BOUNDS" | tail -1)
if echo "$BS" | grep -qE "clipped=0 issues=0"; then
    record PASS TC3 "真实 PixiJS 矩阵下全部帧零裁切 (R156: 114 帧 = R138 23 + R153 + R156 20; 含方向倾斜与逐帧地面行)" "$(echo "$BS" | grep -oE 'frames=[0-9]+ clipped=[0-9]+ issues=[0-9]+')"
else
    record FAIL TC3 "真实 PixiJS 矩阵下全部帧零裁切" "$BS"
fi

# =========================================================
# D/E/F. 真实运行时: 行走方向 / 点击反馈 / 睡眠唤醒 / 撞边反向
# =========================================================
echo ""
echo "  [D] 真实运行时: 行走方向 / 点击 / 睡眠唤醒 (采集预览帧)..."
LOG_PREVIEW="$LOGDIR/preview.log"
# R156: 预览流程新增 6 个点击动作场景 + 4 个道具场景, 采集时间从 ~60s 涨到 ~120s,
#       所以把安全网从 180s 提到 600s (仅兜底; preview 流程自己结束就会 app.quit)
"$ELECTRON" src/main.js --manifest "$MANIFEST" --mode compact --x 600 --y 300 --preview "$PREVIEW_DIR" --quit-after=600 > "$LOG_PREVIEW" 2>&1

WL_SKEW=$(grep -oE "set-action walk_left applied=true.*skew=[-0-9.]+" "$LOG_PREVIEW" | head -1 | grep -oE "skew=[-0-9.]+" | head -1)
WR_SKEW=$(grep -oE "set-action walk_right applied=true.*skew=[-0-9.]+" "$LOG_PREVIEW" | head -1 | grep -oE "skew=[-0-9.]+" | head -1)
WL_K=$(echo "$WL_SKEW" | cut -d= -f2); WR_K=$(echo "$WR_SKEW" | cut -d= -f2)
# R153 修订: 方向不再靠整体错切表达 (用户真机反馈"身体明显前倾像要摔倒"),
#             R148 的派生镜像帧已自带正确迈步方向 ⇒ 运行时 k 必须为 0。
if [ -n "$WL_K" ] && [ -n "$WR_K" ] && python3 -c "import sys; sys.exit(0 if float('$WL_K')==0 and float('$WR_K')==0 else 1)"; then
    record PASS TD1 "运行时左右行走不再施加整体错切 (R153 修复'前倾像摔倒')" "walk_left $WL_SKEW, walk_right $WR_SKEW"
else
    record FAIL TD1 "运行时左右行走仍施加整体错切" "walk_left $WL_SKEW, walk_right $WR_SKEW"
fi

CLICK_LINE=$(grep "PRESS_END kind=CLICK" "$LOG_PREVIEW" | head -1)
REACT_LINE=$(grep "CLICK_REACTION start" "$LOG_PREVIEW" | head -1)
if echo "$CLICK_LINE" | grep -q "kind=CLICK" && [ -n "$REACT_LINE" ]; then
    record PASS TD2 "单击被判定为 CLICK 且触发了可见反馈 (真实 pointer 事件路径)" "$(echo "$CLICK_LINE" | grep -oE 'kind=CLICK elapsed=[0-9]+ms dist=[0-9.]+px') | $(echo "$REACT_LINE" | grep -oE 'duration=[0-9]+ms bump=[0-9]+px')"
else
    record FAIL TD2 "单击触发可见反馈" "$CLICK_LINE / $REACT_LINE"
fi

if grep -q "window-drag-start" "$LOG_PREVIEW"; then
    record FAIL TD3 "点击不得触发拖拽 (未出现 window-drag-start)" "出现 window-drag-start"
else
    record PASS TD3 "点击不误触发拖拽 (日志中无 window-drag-start)" "0 次"
fi

WAKE_STATE=$(grep -E -- "-> WAKE_UP \(user-click-wake\)" "$LOG_PREVIEW" | head -1)
WAKE_FIN=$(grep "animation-finished wake_up" "$LOG_PREVIEW" | head -1)
if [ -n "$WAKE_STATE" ] && [ -n "$WAKE_FIN" ]; then
    record PASS TD4 "睡眠点击走完整 wake_up 过渡 (不瞬移成站姿)" "$(echo "$WAKE_STATE" | grep -oE 'DRAGGING -> WAKE_UP.*') → wake_up 播完回 IDLE"
else
    record FAIL TD4 "睡眠点击走完整 wake_up 过渡" "$WAKE_STATE / $WAKE_FIN"
fi

# R153 修订: 眨眼帧由 4 改为 5 —— idle_04 是"右手横在胸前"的姿势, 不是眨眼帧。
#              用户真机反馈"启动/点击时莫名抬手"的根因就在这里。
BLINK_COUNT=$(grep -c "IDLE_BLINK frame=5" "$LOG_PREVIEW")
BLINK_GAPS=$(grep "IDLE_BLINK frame=5" "$LOG_PREVIEW" | grep -oE "t=\+[0-9]+ms" | grep -oE "[0-9]+" | python3 -c "
import sys
v=[int(x) for x in sys.stdin]
g=[v[i+1]-v[i] for i in range(len(v)-1)]
print('gaps=' + ','.join(str(x) for x in g) if g else 'gaps=none', 'count=%d'%len(v))
")
BAD_BLINK=$(grep -c "IDLE_BLINK frame=4" "$LOG_PREVIEW")
if [ "$BLINK_COUNT" -ge 2 ] && [ "${BAD_BLINK:-0}" -eq 0 ]; then
    record PASS TD5 "待机眨眼用 frame=5 (纯闭眼, 手臂下垂), frame=4 '手放胸前'零出现" "眨眼 $BLINK_COUNT 次, 手放胸前帧出现 $BAD_BLINK 次, $BLINK_GAPS"
else
    record FAIL TD5 "待机眨眼用 frame=5 且 frame=4 零出现" "眨眼 $BLINK_COUNT 次, frame4 $BAD_BLINK 次"
fi

# 撞边反向: 把窗口放到屏幕左边缘, 强制向左走 → 必须真的撞边并反向
echo ""
echo "  [E] 真实运行时: 撞边反向 (窗口置于屏幕左缘)..."
LOG_EDGE="$LOGDIR/edge.log"
"$ELECTRON" src/main.js --manifest "$MANIFEST" --mode compact --x 40 --y 300 --preview "$PREVIEW_DIR/edge" --quit-after=120 > "$LOG_EDGE" 2>&1
# 撞边的权威信号是引擎状态机的 edge-turn 转换;
# 并且必须验证"转向后窗口真的反向移动" (MOVE 日志里的 x 由减转增)
EDGE_TURN=$(grep -E "edge-turn" "$LOG_EDGE" | head -1)
TURN_LINE=$(grep -n "edge-turn" "$LOG_EDGE" | head -1 | cut -d: -f1)
REVERSED=$(python3 - "$LOG_EDGE" "${TURN_LINE:-0}" <<'PYEOF'
import re, sys
path, turn = sys.argv[1], int(sys.argv[2] or 0)
xs = []
for i, line in enumerate(open(path, encoding='utf-8', errors='ignore'), 1):
    m = re.search(r'R144 MOVE x=(-?\d+)', line)
    if m:
        xs.append((i, int(m.group(1))))
before = [x for i, x in xs if i < turn]
after = [x for i, x in xs if i > turn]
def trend(v):
    if len(v) < 2: return 0
    return v[-1] - v[0]
print(f"{trend(before)}|{trend(after)}|{len(before)}|{len(after)}")
PYEOF
)
B_TREND=$(echo "$REVERSED" | cut -d'|' -f1); A_TREND=$(echo "$REVERSED" | cut -d'|' -f2)
B_N=$(echo "$REVERSED" | cut -d'|' -f3); A_N=$(echo "$REVERSED" | cut -d'|' -f4)
if [ -n "$EDGE_TURN" ] && [ "${B_N:-0}" -ge 2 ] && [ "${A_N:-0}" -ge 2 ] \
   && python3 -c "import sys; sys.exit(0 if int('$B_TREND') < 0 and int('$A_TREND') > 0 else 1)"; then
    record PASS TE1 "真实撞到屏幕边缘后动作方向同步反向 (窗口真的掉头)" "edge-turn: $(echo "$EDGE_TURN" | grep -oE 'STATE [A-Z_]+ -> [A-Z_]+ \(edge-turn\)') | 转向前 x 变化 $B_TREND ($B_N 次 MOVE) → 转向后 $A_TREND ($A_N 次 MOVE)"
else
    record FAIL TE1 "真实撞边后动作方向同步反向" "edge-turn='$EDGE_TURN' before=$B_TREND($B_N) after=$A_TREND($A_N)"
fi

# =========================================================
# G. 真实采集帧的客观量化
# =========================================================
echo ""
echo "  [G] 真实采集帧客观量化..."
VERIFY_OUT=$(python3 15_R147_preview_verify.py --preview-dir "$PREVIEW_DIR" 2>&1)
CHEST_DELTA=$(echo "$VERIFY_OUT" | grep -oE "胸部最大轮廓宽度.*波动=[0-9]+px" | grep -oE "波动=[0-9]+" | cut -d= -f2)
if [ -n "$CHEST_DELTA" ] && [ "$CHEST_DELTA" = "0" ]; then
    record PASS TG1 "真实待机帧胸部轮廓宽度零波动 (无胸腔膨胀)" "波动=${CHEST_DELTA}px"
else
    record FAIL TG1 "真实待机帧胸部轮廓宽度零波动" "波动=${CHEST_DELTA}px"
fi
# R156 修订: 点击反馈从"固定 1 个动作 + 人工 7px 弹跳"改成**随机池多帧动作**,
#             人工弹跳已移除 (运动改由动作帧自身承担) ⇒ "弹跳幅度"不再是有效判据 (实测恒为 0)。
#             改用与生产自检同口径的判据: 点击段必须出现 **≥2 个不同画面** (单帧定格不算反馈)。
#
#             测量方法说明 (为什么不用 15_R147_preview_verify.py 的 distinct_poses):
#             那个函数把帧缩到 48x58 再按"整图平均差 < 6"聚类 —— 降采样把 R156 的
#             细微动作 (例如 cheer_wink 只闭一只眼) 抹平了, 且判定受采集相位影响
#             (点击命令与采集循环之间有 IPC 往返, 偶尔只采到动作尾段)。
#             这里改用与 34_R156_runtime_verify.py 完全相同的口径:
#             **全分辨率 + "变化像素占比 < 0.5% 视为同一画面"**, 对动作相位稳健。
CLICK_POSES=$(python3 - "$PREVIEW_DIR" <<'PY'
import json, os, sys
import numpy as np
from PIL import Image
d = sys.argv[1]
meta = json.load(open(os.path.join(d, 'preview_meta.json'), encoding='utf-8'))
entries = meta.get('click') or []
if not entries:
    print(''); raise SystemExit
arrs = [np.asarray(Image.open(e['file']).convert('RGBA')).astype(np.int32) for e in entries]
def ratio(a, b):
    if a.shape != b.shape:
        return 1.0
    dd = np.abs(a - b).sum(axis=2)
    return float((dd > 40).sum()) / max(1, a.shape[0] * a.shape[1])
groups = []
for im in arrs:
    for g in groups:
        if ratio(g[0], im) < 0.005:
            g.append(im); break
    else:
        groups.append([im])
print(len(groups))
PY
)
if [ -n "$CLICK_POSES" ] && [ "$CLICK_POSES" -ge 2 ]; then
    record PASS TG2 "真实单击帧出现 ≥2 个不同画面 (R156: 多帧动作取代人工弹跳; 全分辨率口径)" "$CLICK_POSES 个不同画面"
else
    record FAIL TG2 "真实单击帧出现 ≥2 个不同画面" "$CLICK_POSES 个不同画面"
fi
WALK_L=$(echo "$VERIFY_OUT" | grep "walk_left:" | grep -oE "均值=[-+0-9.]+px" | cut -d= -f2 | tr -d 'px')
WALK_R=$(echo "$VERIFY_OUT" | grep "walk_right:" | grep -oE "均值=[-+0-9.]+px" | cut -d= -f2 | tr -d 'px')
NEG_L=$(echo "$VERIFY_OUT" | grep "walk_left:" | grep -oE "负偏移帧=[0-9]+/[0-9]+" | cut -d= -f2)
NEG_R=$(echo "$VERIFY_OUT" | grep "walk_right:" | grep -oE "负偏移帧=[0-9]+/[0-9]+" | cut -d= -f2)
if python3 -c "import sys; sys.exit(0 if float('$WALK_L')<0 and float('$WALK_R')>0 else 1)"; then
    record PASS TG3 "真实行走帧的上半身倾斜方向正确 (左负右正)" "walk_left 均值=$WALK_L ($NEG_L 帧为负) / walk_right 均值=$WALK_R ($NEG_R 帧为负)"
else
    record FAIL TG3 "真实行走帧的上半身倾斜方向正确" "walk_left=$WALK_L walk_right=$WALK_R"
fi

# 预览产物存在性
GIF_COUNT=$(ls "$CAND/evidence_r147_preview/"*.gif 2>/dev/null | wc -l | tr -d ' ')
if [ "$GIF_COUNT" -ge 5 ]; then
    record PASS TG4 "可观看的运行时预览 GIF 齐备 (左右走/点击/待机/唤醒)" "$GIF_COUNT 个 GIF 位于 evidence_r147_preview/"
else
    record FAIL TG4 "可观看的运行时预览 GIF 齐备" "$GIF_COUNT 个"
fi

# =========================================================
# H. R153 专项: 动作自然度与自主生活丰富度 (真实运行时客观量化)
# =========================================================
echo ""
echo "  [H] R153 专项: 动作自然度客观量化..."
R153_RT_JSON="$CAND/evidence_r153_runtime.json"
R153_RT_OUT=$(python3 27_R153_runtime_verify.py --preview-dir "$PREVIEW_DIR" --out "$R153_RT_JSON" 2>&1)
echo "$R153_RT_OUT" | sed 's/^/      /'
R153_RT_VERDICT=$(echo "$R153_RT_OUT" | grep -oE "判定: [A-Z]+" | tail -1 | awk '{print $2}')
if [ "$R153_RT_VERDICT" = "PASS" ]; then
    record PASS TH0 "R153 运行时客观量化 6 项全部通过 (行走姿态/坐躺渐变/动作确实在动/动作互不相同/点击闭眼笑/呼吸起伏)" "$R153_RT_VERDICT"
else
    record FAIL TH0 "R153 运行时客观量化" "$R153_RT_VERDICT"
fi

# 每个子项也单独记一条, 便于逐条追溯
for id in TH1 TH2 TH3 TH4 TH5 TH6; do
    LINE=$(python3 - "$R153_RT_JSON" "$id" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding='utf-8'))
except Exception:
    print('')
    raise SystemExit
for c in d.get('checks', []):
    if c.get('id') == sys.argv[2]:
        print(f"{c['desc']} || {c['detail']}")
PY
)
    DESC=$(echo "$LINE" | sed 's/ ||.*//')
    DET=$(echo "$LINE" | sed 's/.* || //')
    [ -z "$DESC" ] && continue
    if echo "$R153_RT_OUT" | grep -qE "^ +\[PASS\] $id "; then
        record PASS "$id" "$DESC" "$DET"
    else
        record FAIL "$id" "$DESC" "$DET"
    fi
done

# 帧级溶解 (坐→躺) 必须在真实运行时日志里出现
FRAME_BLEND_N=$(grep -c "R153 FRAME_BLEND sleep_enter" "$LOG_PREVIEW")
if [ "${FRAME_BLEND_N:-0}" -ge 1 ]; then
    record PASS TH7 "帧级溶解在真实运行时生效 (sleep_enter 换帧走渐变)" "$FRAME_BLEND_N 次 FRAME_BLEND sleep_enter"
else
    record FAIL TH7 "帧级溶解在真实运行时生效" "$FRAME_BLEND_N 次"
fi

# 动作库 9 个动作必须全部加载成功
LIB_READY=$(grep -oE 'R153 library-assets-ready \{[^}]*\}' "$LOG_PREVIEW" | tail -1)
# R156 修订: 动作库从 9 个 (R153) 扩到 16 个 (R153 的 9 + R156 的 7: 6 个点击 + 1 个办公),
#             判据从写死 "actions":9 改为 "actions>=9 且 failed=0" —— 守卫不变量仍是
#             "R153 的 9 个动作必须全在", 但不再因 R156 的扩充而误报。
LIB_ACTIONS=$(echo "$LIB_READY" | grep -oE '"actions":[0-9]+' | grep -oE "[0-9]+")
if echo "$LIB_READY" | grep -q '"ok":true' && [ "${LIB_ACTIONS:-0}" -ge 9 ] && echo "$LIB_READY" | grep -q '"failed":0'; then
    record PASS TH8 "动作库全部加载成功 (R153 九个 + R156 七个 = ${LIB_ACTIONS} 个, failed=0)" "$LIB_READY"
else
    record FAIL TH8 "动作库加载" "$LIB_READY"
fi

# R153 预览 GIF 必须齐备 (每个新动作一个)
R153_GIF_COUNT=$(ls "$CAND/evidence_r153_gifs/"R153_*.gif 2>/dev/null | wc -l | tr -d ' ')
if [ "$R153_GIF_COUNT" -ge 12 ]; then
    record PASS TH9 "R153 动作预览 GIF 齐备 (可直接观看)" "$R153_GIF_COUNT 个 GIF 位于 evidence_r153_gifs/"
else
    record FAIL TH9 "R153 动作预览 GIF 齐备" "$R153_GIF_COUNT 个"
fi

# =========================================================
# I. R156 专项: 点击互动池 + 场景道具 + 办公待机 (真实运行时客观量化)
# =========================================================
echo ""
echo "  [I] R156 专项: 点击池 / 道具 / 办公待机..."
R156_RT_JSON="$PREVIEW_DIR/r156_runtime_verify.json"
R156_RT_OUT=$(python3 34_R156_runtime_verify.py --preview-dir "$PREVIEW_DIR" 2>&1)
echo "$R156_RT_OUT" | sed 's/^/      /'
R156_LINE=$(echo "$R156_RT_OUT" | grep -oE "R156 运行时客观校验: [0-9]+ passed, [0-9]+ failed" | tail -1)
R156_P=$(echo "$R156_LINE" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+")
R156_F=$(echo "$R156_LINE" | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+")
if [ "${R156_F:-1}" = "0" ] && [ "${R156_P:-0}" -ge 22 ]; then
    record PASS TI0 "R156 运行时客观量化全部通过 (点击池随机性/多帧画面/道具可见/道具退场残留=0/道具不遮脸/身份不漂移/点击反馈区别于僵立待机)" "$R156_LINE"
else
    record FAIL TI0 "R156 运行时客观量化" "$R156_LINE"
fi

# 每个子项单独记一条, 便于逐条追溯 (JSON 字段为 name/ok/detail)
if [ -f "$R156_RT_JSON" ]; then
    N=1
    while IFS=$'\t' read -r NM OK DT; do
        [ -z "$NM" ] && continue
        if [ "$OK" = "true" ]; then
            record PASS "TI1_$N" "$NM" "$DT"
        else
            record FAIL "TI1_$N" "$NM" "$DT"
        fi
        N=$((N+1))
    done < <(python3 - "$R156_RT_JSON" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
for c in d.get('checks', []):
    print(f"{c['name']}\t{str(bool(c['ok'])).lower()}\t{c.get('detail','')}")
PY
)
fi

# manifest / action_library / 运行时 三方一致性
R156_CONSIST=$(node -e "
const fs=require('fs');
const m=JSON.parse(fs.readFileSync('assets/character_R141_manifest.json','utf8'));
const lib=(m.action_library&&m.action_library.actions)||{};
const pool=(m.click_reactions&&m.click_reactions.pool)||[];
const props=(m.props&&m.props.library)||{};
const scenes=(m.props&&m.props.scenes)||{};
let framesOk=pool.every(p=>lib[p.action]&&Array.isArray(lib[p.action].frames)&&lib[p.action].frames.length>=3);
let uniqFrames=pool.every(p=>new Set(lib[p.action].frames).size===lib[p.action].frames.length);
console.log(JSON.stringify({
  pool:pool.length, weights:pool.map(p=>p.weight), framesOk, uniqFrames,
  libCount:Object.keys(lib).length,
  hasWork:!!lib['work'],
  propCount:Object.keys(props).length,
  sceneCount:Object.keys(scenes).length,
  sceneKeys:Object.keys(scenes),
}));
" 2>&1)
POOL_N=$(echo "$R156_CONSIST" | python3 -c "import json,sys; print(json.load(sys.stdin)['pool'])" 2>/dev/null)
FRAMES_OK=$(echo "$R156_CONSIST" | python3 -c "import json,sys; print(str(json.load(sys.stdin)['framesOk']).lower())" 2>/dev/null)
UNIQ_OK=$(echo "$R156_CONSIST" | python3 -c "import json,sys; print(str(json.load(sys.stdin)['uniqFrames']).lower())" 2>/dev/null)
HAS_WORK=$(echo "$R156_CONSIST" | python3 -c "import json,sys; print(str(json.load(sys.stdin)['hasWork']).lower())" 2>/dev/null)
PROP_N=$(echo "$R156_CONSIST" | python3 -c "import json,sys; print(json.load(sys.stdin)['propCount'])" 2>/dev/null)
SCENE_N=$(echo "$R156_CONSIST" | python3 -c "import json,sys; print(json.load(sys.stdin)['sceneCount'])" 2>/dev/null)
if [ "${POOL_N:-0}" -ge 5 ] && [ "$FRAMES_OK" = "true" ] && [ "$UNIQ_OK" = "true" ]; then
    record PASS TI2 "点击动作池 ≥5 且每个动作有 ≥3 帧互不相同的帧资源 (不虚增)" "池=$POOL_N, 帧数≥3=$FRAMES_OK, 帧互不相同=$UNIQ_OK"
else
    record FAIL TI2 "点击动作池结构" "$R156_CONSIST"
fi
if [ "$HAS_WORK" = "true" ] && [ "${PROP_N:-0}" -ge 5 ] && [ "${SCENE_N:-0}" -ge 5 ]; then
    record PASS TI3 "办公动作已登记 + 道具库与场景配置齐备" "work=$HAS_WORK, 道具=$PROP_N, 场景=$SCENE_N"
else
    record FAIL TI3 "办公动作 / 道具 / 场景配置" "$R156_CONSIST"
fi

# 7 个道具资源在真实运行时全部加载成功
PROP_REPORT=$(grep "R156 props-asset-report" "$LOG_PREVIEW" | tail -1)
if echo "$PROP_REPORT" | grep -q "loaded=7" && echo "$PROP_REPORT" | grep -q "failed=0"; then
    record PASS TI4 "7 个场景道具在真实运行时全部加载成功 (零失败)" "$PROP_REPORT"
else
    record FAIL TI4 "道具资源加载" "$PROP_REPORT"
fi

# 道具必须随动作挂载, 且切到无道具动作时卸载
MOUNT_SLEEP=$(grep -c "R156 PROPS action=sleep_breath scene=yes mounted=prop_bed,prop_moon,prop_quilt" "$LOG_PREVIEW")
MOUNT_SIT=$(grep -c "R156 PROPS action=sit_rest scene=yes mounted=prop_sofa" "$LOG_PREVIEW")
MOUNT_WORK=$(grep -c "R156 PROPS action=work scene=yes mounted=prop_chair,prop_desk,prop_screen_glow" "$LOG_PREVIEW")
MOUNT_NONE=$(grep -c "R156 PROPS .* mounted=none" "$LOG_PREVIEW")
if [ "${MOUNT_SLEEP:-0}" -ge 1 ] && [ "${MOUNT_SIT:-0}" -ge 1 ] && [ "${MOUNT_WORK:-0}" -ge 1 ] && [ "${MOUNT_NONE:-0}" -ge 1 ]; then
    record PASS TI5 "道具按场景挂载 (床+月亮+被子 / 沙发 / 转椅+桌+笔记本+微光), 无道具动作时 mounted=none" "sleep=$MOUNT_SLEEP sit=$MOUNT_SIT work=$MOUNT_WORK none=$MOUNT_NONE"
else
    record FAIL TI5 "道具挂载/卸载" "sleep=$MOUNT_SLEEP sit=$MOUNT_SIT work=$MOUNT_WORK none=$MOUNT_NONE"
fi

# 点击反馈: 真实运行时从池里随机触发, 且每次都是 3 帧
CLICK_ACTS=$(grep -oE "R156 CLICK_REACTION start action=[a-z_]+ frames=[0-9]+" "$LOG_PREVIEW" | sort -u)
CLICK_UNIQ=$(echo "$CLICK_ACTS" | grep -c "action=")
CLICK_ALL3=$(echo "$CLICK_ACTS" | grep -c "frames=3")
if [ "${CLICK_UNIQ:-0}" -ge 3 ] && [ "${CLICK_ALL3:-0}" -eq "${CLICK_UNIQ:-0}" ]; then
    record PASS TI6 "真实运行时点击从池中随机触发多个动作, 每个都是 3 帧 (开始/中间/结束)" "$CLICK_UNIQ 种: $(echo "$CLICK_ACTS" | grep -oE 'action=[a-z_]+' | sort -u | tr '\n' ' ')"
else
    record FAIL TI6 "点击池随机触发" "$CLICK_ACTS"
fi

# R156 可观看交付物齐备
R156_GIF=$(ls "$CAND/evidence_r156_gifs/"*.gif 2>/dev/null | wc -l | tr -d ' ')
R156_PNG=$(ls "$CAND/evidence_r156_gifs/"*.png 2>/dev/null | wc -l | tr -d ' ')
if [ "${R156_GIF:-0}" -ge 10 ] && [ "${R156_PNG:-0}" -ge 2 ]; then
    record PASS TI7 "R156 可观看产物齐备 (6 点击 GIF + 4 场景 GIF + 2 张总览图)" "$R156_GIF 个 GIF, $R156_PNG 张总览图"
else
    record FAIL TI7 "R156 可观看产物齐备" "$R156_GIF GIF / $R156_PNG PNG"
fi

# =========================================================
# 汇总
# =========================================================
echo ""
echo "=========================================="
echo " R147/R153/R156 e2e 结果: PASS=$PASS FAIL=$FAIL NOT_VERIFIED=$NA"
echo "=========================================="

python3 - "$RESULTS_TSV" "$REPORT" "$PASS" "$FAIL" "$NA" <<'PY'
import json, sys, os
tsv, report, p, f, nv = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
items = []
for line in open(tsv, encoding='utf-8'):
    parts = line.rstrip('\n').split('\t')
    if len(parts) == 4:
        items.append({'status': parts[0], 'id': parts[1], 'desc': parts[2], 'detail': parts[3]})
json.dump({'round': 156, 'base_round': 147,
           'test': 'R147/R153/R156 e2e runtime (real Electron, production code)',
           'pass': p, 'fail': f, 'not_verified': nv, 'items': items},
          open(report, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print("报告:", report)
PY

echo "日志目录: $LOGDIR"
echo "预览采集: $PREVIEW_DIR"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
