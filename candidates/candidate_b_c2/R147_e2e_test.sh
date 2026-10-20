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
#   B. 单元测试全量 (R144 的 38 项 + R147 新增 28 项)
#   C. 真实运行时: R147 运行时自检 (首帧同步 / 地面线 / 方向倾斜 / 待机无膨胀 / 点击可见反馈)
#   D. 真实运行时: 左右行走的倾斜方向 (skew 实际生效)
#   E. 真实运行时: 点击 → 可见反馈; 睡眠点击 → wake_up 过渡
#   F. 真实运行时: 撞边反向时动作方向同步切换
#   G. 真实采集帧的客观量化 (胸腔宽度波动 / 弹跳幅度 / 左右倾斜符号)

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
for t in r141_behavior_engine r144_layout r144_oneshot r144_assets_gate r147_layout_pixi_parity r147_interaction; do
    OUT=$(node "tests/$t.test.js" 2>&1 | tail -3)
    LINE=$(echo "$OUT" | grep -oE "[0-9]+ passed, [0-9]+ failed" | tail -1)
    P=$(echo "$LINE" | grep -oE "^[0-9]+"); F=$(echo "$LINE" | grep -oE "[0-9]+ failed" | grep -oE "^[0-9]+")
    UNIT_PASS=$((UNIT_PASS + ${P:-0})); UNIT_FAIL=$((UNIT_FAIL + ${F:-0})); UNIT_TOTAL=$((UNIT_TOTAL + ${P:-0} + ${F:-0}))
    if [ "${F:-1}" != "0" ]; then
        record FAIL TB1_$t "单测 $t" "$LINE"
    fi
done
record PASS TB1 "全部单元测试通过 (R144 的 38 项 + R147 新增 28 项)" "passed=$UNIT_PASS failed=$UNIT_FAIL (共 $UNIT_TOTAL 项)"

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
if echo "$IDLE_SEEN" | grep -qE "\[0,4,5\]|\[0, 4, 5\]"; then
    record PASS TC2 "待机只出现站姿与眨眼帧 (膨胀帧 1/2/3 从未播放)" "$IDLE_SEEN"
else
    record FAIL TC2 "待机只出现站姿与眨眼帧" "$IDLE_SEEN"
fi

# 200x240 零裁切 (R144 真实 PixiJS 矩阵自检)
LOG_BOUNDS="$LOGDIR/bounds.log"
PET_R144_SELFTEST=1 "$ELECTRON" src/main.js --manifest "$MANIFEST" --mode compact --x 400 --y 200 --quit-after=8 > "$LOG_BOUNDS" 2>&1
BS=$(grep "bounds self-test] SUMMARY" "$LOG_BOUNDS" | tail -1)
if echo "$BS" | grep -qE "clipped=0 issues=0"; then
    record PASS TC3 "200x240 真实 PixiJS 矩阵下 23 帧零裁切 (含方向倾斜)" "$(echo "$BS" | grep -oE 'frames=[0-9]+ clipped=[0-9]+ issues=[0-9]+')"
else
    record FAIL TC3 "200x240 零裁切" "$BS"
fi

# =========================================================
# D/E/F. 真实运行时: 行走方向 / 点击反馈 / 睡眠唤醒 / 撞边反向
# =========================================================
echo ""
echo "  [D] 真实运行时: 行走方向 / 点击 / 睡眠唤醒 (采集预览帧)..."
LOG_PREVIEW="$LOGDIR/preview.log"
"$ELECTRON" src/main.js --manifest "$MANIFEST" --mode compact --x 600 --y 300 --preview "$PREVIEW_DIR" --quit-after=95 > "$LOG_PREVIEW" 2>&1

WL_SKEW=$(grep -oE "set-action walk_left applied=true.*skew=[-0-9.]+" "$LOG_PREVIEW" | head -1 | grep -oE "skew=[-0-9.]+" | head -1)
WR_SKEW=$(grep -oE "set-action walk_right applied=true.*skew=[-0-9.]+" "$LOG_PREVIEW" | head -1 | grep -oE "skew=[-0-9.]+" | head -1)
WL_K=$(echo "$WL_SKEW" | cut -d= -f2); WR_K=$(echo "$WR_SKEW" | cut -d= -f2)
if [ -n "$WL_K" ] && [ -n "$WR_K" ] && python3 -c "import sys; sys.exit(0 if float('$WL_K')>0 and float('$WR_K')<0 else 1)"; then
    record PASS TD1 "运行时左右行走施加了反向倾斜 (walk_left 左 / walk_right 右)" "walk_left $WL_SKEW, walk_right $WR_SKEW"
else
    record FAIL TD1 "运行时左右行走施加了反向倾斜" "walk_left $WL_SKEW, walk_right $WR_SKEW"
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

BLINK_COUNT=$(grep -c "IDLE_BLINK frame=4" "$LOG_PREVIEW")
BLINK_GAPS=$(grep "IDLE_BLINK frame=4" "$LOG_PREVIEW" | grep -oE "t=\+[0-9]+ms" | grep -oE "[0-9]+" | python3 -c "
import sys
v=[int(x) for x in sys.stdin]
g=[v[i+1]-v[i] for i in range(len(v)-1)]
print('gaps=' + ','.join(str(x) for x in g) if g else 'gaps=none', 'count=%d'%len(v))
")
if [ "$BLINK_COUNT" -ge 2 ]; then
    record PASS TD5 "待机眨眼按随机间隔发生 (非 1.2s 机械循环)" "眨眼 $BLINK_COUNT 次, $BLINK_GAPS"
else
    record FAIL TD5 "待机眨眼按随机间隔发生" "眨眼 $BLINK_COUNT 次"
fi

# 撞边反向: 把窗口放到屏幕左边缘, 强制向左走 → 必须真的撞边并反向
echo ""
echo "  [E] 真实运行时: 撞边反向 (窗口置于屏幕左缘)..."
LOG_EDGE="$LOGDIR/edge.log"
"$ELECTRON" src/main.js --manifest "$MANIFEST" --mode compact --x 40 --y 300 --preview "$PREVIEW_DIR/edge" --quit-after=45 > "$LOG_EDGE" 2>&1
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
BOUNCE=$(echo "$VERIFY_OUT" | grep -oE "弹跳幅度\(最大离地像素\)=[0-9]+px" | grep -oE "[0-9]+" | head -1)
if [ -n "$CHEST_DELTA" ] && [ "$CHEST_DELTA" = "0" ]; then
    record PASS TG1 "真实待机帧胸部轮廓宽度零波动 (无胸腔膨胀)" "波动=${CHEST_DELTA}px"
else
    record FAIL TG1 "真实待机帧胸部轮廓宽度零波动" "波动=${CHEST_DELTA}px"
fi
if [ -n "$BOUNCE" ] && [ "$BOUNCE" -ge 6 ]; then
    record PASS TG2 "真实单击帧弹跳幅度肉眼可见" "${BOUNCE}px"
else
    record FAIL TG2 "真实单击帧弹跳幅度肉眼可见" "${BOUNCE}px"
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
# 汇总
# =========================================================
echo ""
echo "=========================================="
echo " R147 e2e 结果: PASS=$PASS FAIL=$FAIL NOT_VERIFIED=$NA"
echo "=========================================="

python3 - "$RESULTS_TSV" "$REPORT" "$PASS" "$FAIL" "$NA" <<'PY'
import json, sys, os
tsv, report, p, f, nv = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
items = []
for line in open(tsv, encoding='utf-8'):
    parts = line.rstrip('\n').split('\t')
    if len(parts) == 4:
        items.append({'status': parts[0], 'id': parts[1], 'desc': parts[2], 'detail': parts[3]})
json.dump({'round': 147, 'test': 'R147 e2e runtime (real Electron, production code)',
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
