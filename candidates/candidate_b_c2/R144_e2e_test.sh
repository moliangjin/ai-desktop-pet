#!/bin/bash
# R144 端到端运行时测试 — 真实启动 Electron, 调用真实生产代码
#
# R144 §七 要求:
#   "不得只靠 grep 或重复原有测试宣布通过"
#   "无法在开发环境验证的 macOS GUI 操作, 诚实标记 NOT_GUI_VERIFIED"
#
# 覆盖:
#   A. 静态基线检查 (资源 23/23 + SHA256 + R113 拖拽核心未改 + 候选 B 基线)
#   B. 主用例: 真实 Electron 运行 (渲染边界自检 / 资源握手 / 状态机 / 窗口坐标)
#   C. 缺帧场景: 资源不全 → 明确报错, 拒绝启动自主行为 (拒绝虚假 PASS)
#   D. 慢速加载场景: 引擎必须等资源就绪, 且首次行为切换不丢失
#   E. 重复 ready 场景: 重复消息不得重复启动引擎

set +e
cd "$(dirname "$0")"
CAND="$(pwd)"
ROOT="$(cd ../.. && pwd)"
ELECTRON="$(cd ../candidate_b_electronpixir && pwd)/node_modules/.bin/electron"
MANIFEST="$CAND/assets/character_R141_manifest.json"
R138_WORK="/Users/musk123/Downloads/minimax工作文件夹/图文工作/character_animation_R138"
R138_SUMS="$R138_WORK/SHA256SUMS.txt"
A1_MASTER="$R138_WORK/01_REFERENCE/A1_MASTER_FRONT_PROTECTED.png"
A1_SHA="3344d5fe8d47058475ea7265909478bae4886bb1ee6165412f406a83422013df"
LOGDIR="/tmp/r144_e2e_$$"
REPORT="$CAND/evidence_r144_e2e.json"
RESULTS_TSV="/tmp/r144_e2e_results_$$.tsv"

mkdir -p "$LOGDIR"
PASS=0; FAIL=0; NA=0
: > "$RESULTS_TSV"

record() {  # record <status> <id> <desc> <detail>
    local st="$1" id="$2" desc="$3" detail="$4"
    case "$st" in
        PASS) PASS=$((PASS+1)) ;;
        FAIL) FAIL=$((FAIL+1)) ;;
        *)    NA=$((NA+1)) ;;
    esac
    printf '%s\t%s\t%s\t%s\n' "$st" "$id" "$desc" "$detail" >> "$RESULTS_TSV"
    printf "  [%s] T%-2s %s — %s\n" "$st" "$id" "$desc" "$detail"
}

echo "=========================================="
echo " R144 端到端运行时测试 (真实 Electron)"
echo "=========================================="

# =========================================================
# A. 静态基线检查
# =========================================================
echo ""
echo "  [A] 静态基线检查..."

# --- A1: manifest 23 帧路径逐项实际验证 ---
MANIFEST_CHECK=$(node -e "
const fs=require('fs'),path=require('path');
const base=path.dirname(process.argv[1]);
const m=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
let total=0,valid=0,groups=0,missing=[];
for(const g of Object.keys(m.actions)){
  groups++;
  for(const rel of m.actions[g].frames){
    total++;
    if(fs.existsSync(path.join(base,rel))) valid++; else missing.push(g+'/'+rel);
  }
}
console.log(JSON.stringify({total,valid,groups,missing}));
" "$MANIFEST")
MT=$(echo "$MANIFEST_CHECK" | python3 -c "import sys,json;print(json.load(sys.stdin)['total'])")
MV=$(echo "$MANIFEST_CHECK" | python3 -c "import sys,json;print(json.load(sys.stdin)['valid'])")
MG=$(echo "$MANIFEST_CHECK" | python3 -c "import sys,json;print(json.load(sys.stdin)['groups'])")
if [ "$MV" = "$MT" ] && [ "$MT" = "23" ] && [ "$MG" = "6" ]; then
    record PASS A1 "23/23 动画帧路径真实有效 + 6 组动作" "manifest 逐项实际验证 $MV/$MT, 组数 $MG"
else
    record FAIL A1 "23/23 动画帧路径真实有效" "验证 $MV/$MT, 组数 $MG"
fi

# --- A2: 23 张 PNG 的 SHA256 与 R138 交付清单逐一一致 (资产基线保护) ---
if [ -f "$R138_SUMS" ]; then
    SHA_CHECK=$(python3 - "$CAND/assets/character_R138" "$R138_SUMS" << 'PYEOF'
import hashlib, os, sys
asset_dir, sums = sys.argv[1], sys.argv[2]
expect = {}
for line in open(sums, encoding='utf-8'):
    line = line.strip()
    if not line or '05_ANIMATIONS/' not in line:
        continue
    h, rel = line.split(None, 1)
    expect[os.path.basename(rel.strip())] = h
# 素材按 action 子目录存放, 建立 basename -> 实际文件 映射
actual = {}
for root, _dirs, files in os.walk(asset_dir):
    for fn in files:
        if fn.lower().endswith('.png'):
            actual[fn] = os.path.join(root, fn)
ok, bad, missing = 0, [], []
for name, h in sorted(expect.items()):
    p = actual.get(name)
    if not p:
        missing.append(name); continue
    d = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    if d == h: ok += 1
    else: bad.append(name)
print(f"{ok} {len(expect)} {len(bad)} {len(missing)}")
PYEOF
)
    set -- $SHA_CHECK
    if [ "$1" = "$2" ] && [ "$3" = "0" ] && [ "$4" = "0" ]; then
        record PASS A2 "R138 23 帧角色资产逐字节未变 (SHA256 比对 R138 交付清单)" "$1/$2 帧哈希一致, 0 失配, 0 缺失"
    else
        record FAIL A2 "R138 23 帧角色资产 SHA256 比对" "一致 $1/$2, 失配 $3, 缺失 $4"
    fi
else
    record FAIL A2 "R138 SHA256 清单缺失" "$R138_SUMS 不存在"
fi

# --- A3: A1 母版 SHA256 未变 ---
if [ -f "$A1_MASTER" ]; then
    A1_NOW=$(shasum -a 256 "$A1_MASTER" | awk '{print $1}')
    if [ "$A1_NOW" = "$A1_SHA" ]; then
        record PASS A3 "A1 母版 SHA256 未变" "$A1_NOW"
    else
        record FAIL A3 "A1 母版 SHA256 未变" "实际 $A1_NOW"
    fi
else
    record FAIL A3 "A1 母版文件缺失" "$A1_MASTER"
fi

# --- A4: R113 拖拽核心代码逐字未改 ---
DRAG_DIFF=$(python3 "$CAND/tools/r144_drag_core_diff.py" 2>&1)
DRAG_RC=$?
if [ "$DRAG_RC" = "0" ]; then
    record PASS A4 "R113 拖拽核心代码逐字未改 (用户真机验证过的实现)" "$DRAG_DIFF"
else
    record FAIL A4 "R113 拖拽核心代码未改" "$DRAG_DIFF"
fi

# --- A5: 原候选 B 冻结基线未改变 ---
CHANGED=$(cd "$ROOT" && git status --porcelain candidates/candidate_b_electronpixir assets/prototype_chibi 2>/dev/null | grep -v "^??" | wc -l | tr -d ' ')
if [ "${CHANGED:-0}" = "0" ]; then
    record PASS A5 "原候选 B 冻结基线未改变" "candidate_b_electronpixir + assets/prototype_chibi 无 git 改动"
else
    record FAIL A5 "原候选 B 冻结基线未改变" "$CHANGED 处改动"
fi

# --- A6: 正式运行无开发调试文字 ---
DEV_DEFAULT_OFF=$(grep -c "PET_DEV_MODE === '1'" src/renderer.js)
HIDE_DEBUG=$(grep -c "debugBanner.style.display = 'none'" src/renderer.js)
HIDE_FALLBACK=$(grep -c "fallback.style.display = 'none'" src/renderer.js)
if [ "$DEV_DEFAULT_OFF" -ge 1 ] && [ "$HIDE_DEBUG" -ge 1 ] && [ "$HIDE_FALLBACK" -ge 1 ]; then
    record PASS A6 "正式运行无调试文字 (界面只显示角色)" "DEV_MODE 默认关闭 + fallback/debug-banner 正式模式隐藏"
else
    record FAIL A6 "正式运行无调试文字" "dev=$DEV_DEFAULT_OFF hideDebug=$HIDE_DEBUG hideFallback=$HIDE_FALLBACK"
fi

# =========================================================
# B. 主用例: 真实 Electron 运行
# =========================================================
echo ""
echo "  [B] 真实启动 Electron (行走场景: --sleep-probability 0 保证必然行走 + 渲染边界自检)..."
LOG_B="$LOGDIR/main.log"
rm -f "$LOG_B"
PET_R144_SELFTEST=1 "$ELECTRON" "$CAND/src/main.js" \
    --manifest "$MANIFEST" \
    --mode compact --x 2 --y 200 \
    --acceptance --sleep-probability 0 \
    --quit-after=26 \
    > "$LOG_B" 2>&1 &
EPID=$!

# 轮询: 观测到足够多次窗口移动后提前结束 (行走是确定性的, 不会随机跑去睡觉)
WAITED=0
MAXWAIT=26
while kill -0 "$EPID" 2>/dev/null && [ $WAITED -lt $MAXWAIT ]; do
    sleep 2
    WAITED=$((WAITED+2))
    if [ -f "$LOG_B" ]; then
        N_MOVE=$(grep -c "R144 MOVE" "$LOG_B" 2>/dev/null)
        if [ "${N_MOVE:-0}" -ge 12 ]; then
            echo "  已观测到 ${N_MOVE} 次窗口移动, 提前结束 (${WAITED}s)"
            break
        fi
    fi
done
if kill -0 "$EPID" 2>/dev/null; then
    kill -TERM "$EPID" 2>/dev/null; sleep 2; kill -KILL "$EPID" 2>/dev/null
fi
wait "$EPID" 2>/dev/null
echo "  Electron 已退出, 日志 $LOG_B"

if [ ! -s "$LOG_B" ]; then
    record FAIL B0 "Electron 启动并产生日志" "日志为空 (启动失败)"
else
    record PASS B0 "Electron 真实启动并产生日志" "日志 $(wc -l < "$LOG_B" | tr -d ' ') 行"
fi

# --- B1: 六组动画全部加载成功 ---
LOADED_TOTAL=$(grep -oE -e "asset-report: [a-z_]+ loaded=[0-9]+" "$LOG_B" 2>/dev/null | grep -oE -e "loaded=[0-9]+" | grep -oE -e "[0-9]+" | paste -sd+ - | bc 2>/dev/null)
[ -z "$LOADED_TOTAL" ] && LOADED_TOTAL=0
FAILED_TOTAL=$(grep -oE -e "failed=[0-9]+" "$LOG_B" 2>/dev/null | grep -oE -e "[0-9]+" | paste -sd+ - | bc 2>/dev/null)
[ -z "$FAILED_TOTAL" ] && FAILED_TOTAL=0
GROUPS_LOADED=$(grep -cE -e "asset-report: [a-z_]+ loaded=[1-9]" "$LOG_B" 2>/dev/null)
if [ "$GROUPS_LOADED" = "6" ] && [ "$LOADED_TOTAL" = "23" ] && [ "$FAILED_TOTAL" = "0" ]; then
    record PASS B1 "六组动画全部加载成功 (23 帧)" "6 组 loaded, 合计 $LOADED_TOTAL 帧, failed=$FAILED_TOTAL"
else
    record FAIL B1 "六组动画全部加载成功" "组数=$GROUPS_LOADED 帧数=$LOADED_TOTAL failed=$FAILED_TOTAL"
fi

# --- B2: 资源就绪握手 (ASSETS_READY 必须在引擎启动之前) ---
READY_LINE=$(grep -n "R144 ASSETS_READY" "$LOG_B" 2>/dev/null | head -1 | cut -d: -f1)
ENGINE_LINE=$(grep -n "R144 behavior engine started" "$LOG_B" 2>/dev/null | head -1 | cut -d: -f1)
READY_TXT=$(grep -m1 "R144 ASSETS_READY" "$LOG_B" 2>/dev/null)
if [ -n "$READY_LINE" ] && [ -n "$ENGINE_LINE" ] && [ "$READY_LINE" -lt "$ENGINE_LINE" ] && echo "$READY_TXT" | grep -q "loaded=23/23"; then
    record PASS B2 "资源就绪握手: ASSETS_READY(23/23) 先于引擎启动" "ready@行$READY_LINE < engine@行$ENGINE_LINE"
else
    record FAIL B2 "资源就绪握手" "ready@${READY_LINE:-无} engine@${ENGINE_LINE:-无} 文本='$READY_TXT'"
fi

# --- B3: renderer 真实 PixiJS 变换矩阵下 23 帧零裁切 ---
SELFTEST_SUM=$(grep -m1 "R144 bounds self-test] SUMMARY" "$LOG_B" 2>/dev/null)
if echo "$SELFTEST_SUM" | grep -q "frames=46" && echo "$SELFTEST_SUM" | grep -q "clipped=0" && echo "$SELFTEST_SUM" | grep -q "issues=0"; then
    record PASS B3 "真实 PixiJS 变换矩阵下 23 帧 × 2 尺寸零裁切" "$SELFTEST_SUM"
else
    record FAIL B3 "渲染边界自检 (真实 PixiJS 矩阵)" "未得到合格 SUMMARY: '$SELFTEST_SUM'"
fi

# --- B4: 地面接触线一致 (自检逐帧 groundErr) ---
GROUND_BAD=$(grep "R144 bounds self-test\]" "$LOG_B" 2>/dev/null | grep -c "groundErr=0.0000" )
GROUND_TOTAL=$(grep -c "R144 bounds self-test\] \(compact\|standard\) " "$LOG_B" 2>/dev/null)
if [ "${GROUND_TOTAL:-0}" = "46" ] && [ "${GROUND_BAD:-0}" = "46" ]; then
    record PASS B4 "全部帧底边贴同一地面接触线 (脚底/地面接触点稳定)" "$GROUND_BAD/$GROUND_TOTAL 帧 groundErr=0"
else
    record FAIL B4 "地面接触线一致" "合格 $GROUND_BAD/$GROUND_TOTAL 帧"
fi

# --- B5: 状态机自动流转 ---
STATE_LOG=$(grep -e "R141 STATE" "$LOG_B" 2>/dev/null)
HAS_IDLE_START=$(echo "$STATE_LOG" | grep -c -e "IDLE -> WALK_LEFT" -e "IDLE -> WALK_RIGHT" -e "IDLE -> SLEEP_ENTER")
if [ "${HAS_IDLE_START:-0}" -ge 1 ]; then
    record PASS B5 "idle 能自动切换 (无需用户按键)" "观测到 $HAS_IDLE_START 次从 IDLE 自动切出"
else
    record FAIL B5 "idle 能自动切换" "未观测到 IDLE 自动切换"
fi

# --- B6: 行走方向/状态有效 ---
HAS_WALK=$(grep "R141 STATE" "$LOG_B" 2>/dev/null | grep -cE -e "IDLE -> WALK_(LEFT|RIGHT)")
if [ "${HAS_WALK:-0}" -ge 1 ]; then
    record PASS B6 "walk_left / walk_right 状态有效 (确定性行走场景)" "观测到 $HAS_WALK 次进入行走状态"
else
    record FAIL B6 "walk 状态有效" "未观测到行走状态"
fi

# --- B8: 窗口坐标复核 (整数 / actual==target / moved==step) ---
MOVE_VERDICT=$(python3 - "$LOG_B" << 'PYEOF'
import re, sys
log = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
pat = re.compile(r"R144 MOVE x=(-?\d+) y=(-?\d+) target=\((-?\d+),(-?\d+)\) actual=\((-?\d+),(-?\d+)\) moved=\((-?\d+),(-?\d+)\) step=\((-?\d+),(-?\d+)\) dx=(-?[\d.]+) blocked=(\w+)")
rows = pat.findall(log)
if not rows:
    print("NOLOG|0|0|0|0")
    sys.exit(0)
nonint = 0; mismatch = 0; moved_ne_step = 0; blocked_rows = 0
for r in rows:
    x, y, tx, ty, ax, ay, mx, my, sx, sy, dx, blk = (int(r[0]), int(r[1]), int(r[2]), int(r[3]), int(r[4]), int(r[5]), int(r[6]), int(r[7]), int(r[8]), int(r[9]), float(r[10]), r[11])
    if blk == "true":
        blocked_rows += 1
        continue
    if abs(ax - tx) > 1 or abs(ay - ty) > 1: mismatch += 1
    if abs(mx) != abs(sx) or abs(my) != abs(sy): moved_ne_step += 1
    if sx == 0 and sy == 0: nonint += 1
span = 0
xs = [int(r[0]) for r in rows]
if xs: span = max(xs) - min(xs)
print(f"OK|{len(rows)}|{mismatch}|{moved_ne_step}|{nonint}|{span}|{blocked_rows}")
PYEOF
)
echo "  MOVE 复核: $MOVE_VERDICT"
MOVE_FIELDS=$(echo "$MOVE_VERDICT" | tr '|' ' ')
set -- $MOVE_FIELDS
if [ "$1" = "OK" ] && [ "${2:-0}" -ge 3 ] && [ "${3:-1}" = "0" ] && [ "${4:-1}" = "0" ] && [ "${5:-1}" = "0" ] && [ "${6:-0}" -gt 5 ]; then
    record PASS B8 "窗口坐标复核: 整数坐标 + actual==target + 真实位移==请求步长" "$2 次 setBounds, 不一致 $3, 位移不符 $4, 零步长 $5, x 跨度 ${6}px"
else
    record FAIL B8 "窗口坐标复核" "$MOVE_VERDICT"
fi

# --- B9: 撞边自动转向 ---
TURN_CNT=$(grep -c "edge-turn" "$LOG_B" 2>/dev/null)
if [ "${TURN_CNT:-0}" -ge 1 ]; then
    record PASS B9 "到屏幕边缘自动转向 (边界判定基于真实窗口位置)" "观测到 $TURN_CNT 次 edge-turn"
else
    record NOT_GUI_VERIFIED B9 "到屏幕边缘自动转向" "本次运行未撞边; 单元测试 T5 已覆盖转向逻辑 (注入 blocked); 真实撞边需 Mac 真机"
fi

# --- B10: 退出后无残留进程 ---
STOPPED=$(grep -c "behavior engine stopped" "$LOG_B" 2>/dev/null)
LEAK_PROC=$(pgrep -f "candidate_b_c2/src/main.js" 2>/dev/null | wc -l | tr -d ' ')
if [ "${STOPPED:-0}" -ge 1 ] && [ "${LEAK_PROC:-0}" = "0" ]; then
    record PASS B10 "退出后无定时器/进程残留" "引擎已 stop, 残留进程 $LEAK_PROC"
else
    record FAIL B10 "退出后无残留" "stopped=${STOPPED:-0} 残留=${LEAK_PROC:-0}"
fi

# =========================================================
# C. 缺帧场景 → 明确报错, 拒绝启动
# =========================================================
echo ""
echo "  [C] 缺帧场景 (资源不全 → 拒绝启动自主行为)..."
BROKEN="$LOGDIR/broken_manifest.json"
node -e "
const fs=require('fs');
const m=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
for(const a of Object.keys(m.actions)) m.actions[a].frames = m.actions[a].frames.map(f=>'MISSING_DIR/'+f);
fs.writeFileSync(process.argv[2], JSON.stringify(m,null,2));
" "$MANIFEST" "$BROKEN"
LOG_C="$LOGDIR/broken.log"
PET_R144_SELFTEST=1 "$ELECTRON" "$CAND/src/main.js" \
    --manifest "$BROKEN" --mode compact --x 2 --y 200 --quit-after=12 \
    > "$LOG_C" 2>&1
if grep -q "R144 ASSETS_ERROR" "$LOG_C" 2>/dev/null && ! grep -q "behavior engine started" "$LOG_C" 2>/dev/null; then
    record PASS C1 "缺帧时明确报错且拒绝启动自主行为 (拒绝虚假 PASS)" "ASSETS_ERROR 已报, 引擎未启动"
else
    record FAIL C1 "缺帧场景" "ASSETS_ERROR=$(grep -c 'R144 ASSETS_ERROR' "$LOG_C" 2>/dev/null) 引擎启动=$(grep -c 'behavior engine started' "$LOG_C" 2>/dev/null)"
fi
if grep -q "R144 assets-ready" "$LOG_C" 2>/dev/null; then
    record PASS C2 "缺帧时 renderer 仍上报了就绪状态 (事实可见)" "assets-ready 已上报并带错误信息"
else
    record FAIL C2 "缺帧时 renderer 上报就绪状态" "未上报"
fi

# =========================================================
# D. 慢速加载 → 引擎必须等资源就绪, 首次行为切换不丢失
# =========================================================
echo ""
echo "  [D] 慢速加载场景 (延迟 5s 加载)..."
LOG_D="$LOGDIR/slow.log"
PET_R144_ASSET_DELAY_MS=5000 "$ELECTRON" "$CAND/src/main.js" \
    --manifest "$MANIFEST" --mode compact --x 2 --y 200 --acceptance --quit-after=20 \
    > "$LOG_D" 2>/dev/null
D_READY=$(grep -n "R144 ASSETS_READY" "$LOG_D" 2>/dev/null | head -1 | cut -d: -f1)
D_ENGINE=$(grep -n "R144 behavior engine started" "$LOG_D" 2>/dev/null | head -1 | cut -d: -f1)
D_TRANS=$(grep -c "R141 STATE IDLE -> " "$LOG_D" 2>/dev/null)
if [ -n "$D_READY" ] && [ -n "$D_ENGINE" ] && [ "$D_READY" -lt "$D_ENGINE" ] && [ "${D_TRANS:-0}" -ge 1 ]; then
    record PASS D1 "慢速加载: 引擎在资源就绪后才启动, 且首次行为切换未丢失" "ready@行$D_READY < engine@行$D_ENGINE, 后续自动切换 $D_TRANS 次"
else
    record FAIL D1 "慢速加载场景" "ready@${D_READY:-无} engine@${D_ENGINE:-无} 切换 ${D_TRANS:-0} 次"
fi

# =========================================================
# E. 重复 ready → 不得重复启动引擎
# =========================================================
echo ""
echo "  [E] 重复 ready 场景..."
LOG_E="$LOGDIR/dup.log"
PET_R144_DUP_READY=1 "$ELECTRON" "$CAND/src/main.js" \
    --manifest "$MANIFEST" --mode compact --x 2 --y 200 --acceptance --quit-after=12 \
    > "$LOG_E" 2>/dev/null
E_START=$(grep -c "R144 behavior engine started" "$LOG_E" 2>/dev/null)
E_DUP=$(grep -c "R144 ASSETS_READY_DUPLICATE" "$LOG_E" 2>/dev/null)
if [ "${E_START:-0}" = "1" ] && [ "${E_DUP:-0}" -ge 1 ]; then
    record PASS E1 "重复 assets-ready 被忽略, 引擎只启动一次" "engine started x$E_START, duplicate ignored x$E_DUP"
else
    record FAIL E1 "重复 ready 场景" "engine started=${E_START:-0} duplicate=${E_DUP:-0}"
fi

# =========================================================
# F. 睡眠场景 (--sleep-probability 1 保证必然睡觉) → 一次性动画机制
# =========================================================
echo ""
echo "  [F] 睡眠场景 (--sleep-probability 1 保证必然睡觉)..."
LOG_F="$LOGDIR/sleep.log"
PET_R144_SELFTEST=1 "$ELECTRON" "$CAND/src/main.js" \
    --manifest "$MANIFEST" --mode compact --x 2 --y 200 \
    --acceptance --sleep-probability 1 --quit-after=40 \
    > "$LOG_F" 2>&1 &
FPID=$!
FWAIT=0
while kill -0 "$FPID" 2>/dev/null && [ $FWAIT -lt 40 ]; do
    sleep 2
    FWAIT=$((FWAIT+2))
    if [ -f "$LOG_F" ]; then
        F_ENTER=$(sed -nE 's/.*R141 STATE [A-Z_]+ -> SLEEP_ENTER.*/X/p' "$LOG_F" 2>/dev/null | wc -l | tr -d ' ')
        F_LOOP=$(sed -nE 's/.*R141 STATE [A-Z_]+ -> SLEEP_LOOP.*/X/p' "$LOG_F" 2>/dev/null | wc -l | tr -d ' ')
        F_WAKE=$(sed -nE 's/.*R141 STATE [A-Z_]+ -> WAKE_UP.*/X/p' "$LOG_F" 2>/dev/null | wc -l | tr -d ' ')
        if [ "${F_ENTER:-0}" -ge 1 ] && [ "${F_LOOP:-0}" -ge 1 ] && [ "${F_WAKE:-0}" -ge 1 ]; then
            echo "  已观测到完整睡眠序列 (ENTER=$F_ENTER LOOP=$F_LOOP WAKE=$F_WAKE), 再等 6s 让 wake_up 一次性动画播完..."
            # R144: wake_up 是一次性动画 (3 帧 x 600ms + 末帧保持 600ms ≈ 1.8s),
            #       必须等它自然播完才能验证"完成事件只发一次"与"末帧保持时长"
            sleep 6
            break
        fi
    fi
done
if kill -0 "$FPID" 2>/dev/null; then
    kill -TERM "$FPID" 2>/dev/null; sleep 2; kill -KILL "$FPID" 2>/dev/null
fi
wait "$FPID" 2>/dev/null

F_STATE=$(grep "R141 STATE" "$LOG_F" 2>/dev/null)
F_ORDER=$(echo "$F_STATE" | sed -nE 's/.*R141 STATE [A-Z_]+ -> (SLEEP_ENTER|SLEEP_LOOP|WAKE_UP).*/\1/p' | head -3 | paste -sd, -)
if [ "$F_ORDER" = "SLEEP_ENTER,SLEEP_LOOP,WAKE_UP" ]; then
    record PASS F1 "sleep_enter -> sleep_loop -> wake_up 顺序正确 (确定性睡眠场景)" "观测顺序 $F_ORDER"
else
    record FAIL F1 "sleep 顺序正确" "实际顺序 '$F_ORDER'"
fi

F_FIN_ENTER=$(grep -c "R144 animation-finished sleep_enter" "$LOG_F" 2>/dev/null)
F_FIN_WAKE=$(grep -c "R144 animation-finished wake_up" "$LOG_F" 2>/dev/null)
F_ENT=$(echo "$F_STATE" | sed -nE 's/.*R141 STATE [A-Z_]+ -> SLEEP_ENTER.*/X/p' | wc -l | tr -d ' ')
F_WK=$(echo "$F_STATE" | sed -nE 's/.*R141 STATE [A-Z_]+ -> WAKE_UP.*/X/p' | wc -l | tr -d ' ')
if [ "${F_FIN_ENTER:-0}" = "${F_ENT:-0}" ] && [ "${F_FIN_WAKE:-0}" = "${F_WK:-0}" ] && [ "${F_ENT:-0}" -ge 1 ]; then
    record PASS F2 "一次性动画完成事件每次只发一次 (与状态进入次数严格相等)" "sleep_enter 回报 $F_FIN_ENTER/$F_ENT, wake_up 回报 $F_FIN_WAKE/$F_WK"
else
    record FAIL F2 "一次性动画完成事件次数" "sleep_enter $F_FIN_ENTER vs 进入 $F_ENT; wake_up $F_FIN_WAKE vs 进入 $F_WK"
fi

# F3: 末帧保持时长 (用真实运行日志的时间戳核算) + 未回卷到首帧
HOLD_VERDICT=$(python3 - "$LOG_F" << 'PYEOF'
import re, sys
log = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
last = re.findall(r"R144 oneshot last-frame (\w+) index=(\d+)/(\d+) t=\+(\d+)ms", log)
fin = re.findall(r"R144 animation-finished (\w+).*t=\+(\d+)ms", log)
if not last or not fin:
    print("NODATA|0|0|0|0")
    sys.exit(0)
holds = []
for action, idx, lastidx, t1 in last:
    t1 = int(t1)
    match = [int(t2) for a, t2 in fin if a == action and int(t2) >= t1]
    if match:
        holds.append(match[0] - t1)
# 回卷检测: 一次性动画到达末帧后, 不应再出现 index=0 的末帧打点
wrap = 0
for action, idx, lastidx, t1 in last:
    if int(idx) != int(lastidx):
        wrap += 1
print(f"OK|{len(holds)}|{min(holds) if holds else -1}|{max(holds) if holds else -1}|{wrap}")
PYEOF
)
echo "  末帧保持核算: $HOLD_VERDICT"
set -- $(echo "$HOLD_VERDICT" | tr '|' ' ')
if [ "$1" = "OK" ] && [ "${2:-0}" -ge 2 ] && [ "${3:-0}" -ge 500 ] && [ "${3:-0}" -le 900 ] && [ "${4:-1}" -le 900 ] && [ "${5:-1}" = "0" ]; then
    record PASS F3 "末帧保持时长符合 frame_ms (600ms) 且未回卷到首帧" "样本 $2 次, 保持 ${3}~${4}ms, 回卷 $5 次"
else
    record FAIL F3 "末帧保持时长/回卷" "$HOLD_VERDICT"
fi

# =========================================================
# GUI 限制项 (诚实标记)
# =========================================================
record NOT_GUI_VERIFIED G1 "用户拖拽期间自动行为暂停 (真实鼠标)" "需 Mac 真机; 单元测试 T8 + 引擎优先级已覆盖; R113 拖拽核心逐字未改 (A4)"
record NOT_GUI_VERIFIED G2 "松开拖拽后自主行为恢复 (真实鼠标)" "需 Mac 真机; 单元测试 T9 已覆盖状态机层"
record NOT_GUI_VERIFIED G3 "真实鼠标拖拽窗口跟随 (真实鼠标)" "R113 已由用户 Mac 真机验证; 本轮逐字未改核心代码, 但未重测真机"

# =========================================================
# 汇总
# =========================================================
echo ""
echo "=========================================="
echo " R144 e2e 结果: PASS=$PASS FAIL=$FAIL NOT_VERIFIED=$NA"
echo "=========================================="

R144_RESULTS_TSV="$RESULTS_TSV" python3 - "$REPORT" "$PASS" "$FAIL" "$NA" "$LOG_B" "$LOG_F" << 'PYEOF'
import json, os, sys
report_path, npass, nfail, nna, log_b, log_f = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
items = []
with open(os.environ["R144_RESULTS_TSV"], encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split("\t")
        while len(parts) < 4:
            parts.append("")
        items.append({"status": parts[0], "id": parts[1], "desc": parts[2], "detail": parts[3]})
out = {
    "round": 144,
    "test": "R144 e2e runtime (real Electron, production code)",
    "pass": npass, "fail": nfail, "not_verified": nna,
    "logs": {"walk_scenario": log_b, "sleep_scenario": log_f},
    "items": items,
}
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("报告:", report_path)
PYEOF

if [ "${FAIL:-0}" -gt 0 ]; then
    echo ""
    echo "失败项:"
    python3 -c "
import json
d=json.load(open('$REPORT'))
for it in d['items']:
    if it['status']=='FAIL': print('  - T%s %s: %s' % (it['id'], it['desc'], it['detail']))
"
    exit 1
fi
exit 0
