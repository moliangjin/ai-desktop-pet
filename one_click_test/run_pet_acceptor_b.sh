#!/bin/bash
# one_click_test/run_pet_acceptor_b.sh
#
# 启动候选 B (Electron + PixiJS) + PetAcceptor 图形验收窗口
set -e
DST="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
BUNDLE="$DST/candidates/candidate_b_electronpixir/build/PetCandidateB.app"
ACCEPTOR="$DST/test_window/PetAcceptor/build/PetAcceptor.app/Contents/MacOS/PetAcceptor"
PROBE="$DST/test_window/ClickThroughProbe/build/ClickThroughProbe.app/Contents/MacOS/ClickThroughProbe"

LOG_DIR="$DST/evidence/acceptor_runs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_ID="candidate_b_${TIMESTAMP}"
LOG="$LOG_DIR/${RUN_ID}.log"
RUNTIME_LOG="$LOG_DIR/${RUN_ID}_runtime.log"
RESULT="$LOG_DIR/${RUN_ID}_result.json"

GIT_COMMIT=$(cd "$DST" && git log --oneline -1 2>/dev/null | head -1 | cut -d' ' -f1)
if [ -z "$GIT_COMMIT" ]; then GIT_COMMIT="uncommitted"; fi

# --- 1. 启动探针 ---
pkill -f "ClickThroughProbe" 2>/dev/null || true
sleep 1
"$PROBE" </dev/null >/dev/null 2>&1 &
PROBE_PID=$!
sleep 2
echo "[run_pet_acceptor_b] probe PID=$PROBE_PID" >> "$LOG"

# --- 2. 启动候选 B ---
pkill -f "Electron.*candidates/candidate_b" 2>/dev/null || true
sleep 1
# B 用的是 raw node + electron，不是 .app bundle；直接调入口脚本
B_ENTRY="$DST/candidates/candidate_b_electronpixir/src/main.js"
echo "" > "$RUNTIME_LOG"

if [ ! -f "$B_ENTRY" ]; then
    cat > "$RESULT" <<JSON
{
  "candidate": "candidate_b",
  "version": "V0.0",
  "commit": "$GIT_COMMIT",
  "bundle_id": "com.test.petB",
  "tested_at": "$(date +%Y-%m-%dT%H:%M:%S+08:00)",
  "overall": "FAIL",
  "counts_pass": 0,
  "counts_fail": 1,
  "counts_not_tested": 7,
  "counts_disabled": 0,
  "launch_ok": false,
  "items": [
    {"key":"launch","label":"1/8 启动验证","status":"FAIL","notes":"$B_ENTRY 缺失;R45 候选 B 入口未就绪"},
    {"key":"display","label":"2/8 显示方向","status":"NOT_TESTED","notes":""},
    {"key":"animation","label":"3/8 动画表现","status":"NOT_TESTED","notes":""},
    {"key":"click","label":"4/8 点击反馈","status":"NOT_TESTED","notes":""},
    {"key":"drag","label":"5/8 拖动同步","status":"NOT_TESTED","notes":""},
    {"key":"transparent","label":"6/8 透明区穿透","status":"NOT_TESTED","notes":""},
    {"key":"window_focus","label":"7/8 焦点与置顶","status":"NOT_TESTED","notes":""},
    {"key":"multidisplay","label":"8/8 多显示器","status":"DISABLED_SINGLE_DISPLAY","notes":""}
  ]
}
JSON
    pkill -f "ClickThroughProbe" 2>/dev/null || true
    echo "$RESULT"
    exit 0
fi

cd "$DST/candidates/candidate_b_electronpixir"
(
    exec ./node_modules/.bin/electron "$B_ENTRY" \
        --manifest "$DST/assets/prototype_chibi/manifest.json" \
        --size 256 --x 1100 --y 600 \
        --quit-after 600 \
        < /dev/null \
        >> "$RUNTIME_LOG" 2>&1
) &
CAND_PID=$!
echo "[run_pet_acceptor_b] candidate B PID=$CAND_PID" >> "$LOG"
sleep 6

if ! ps -p $CAND_PID > /dev/null; then
    cat > "$RESULT" <<JSON
{
  "candidate": "candidate_b",
  "version": "V0.0",
  "commit": "$GIT_COMMIT",
  "bundle_id": "com.test.petB",
  "tested_at": "$(date +%Y-%m-%dT%H:%M:%S+08:00)",
  "overall": "FAIL",
  "counts_pass": 0,
  "counts_fail": 1,
  "counts_not_tested": 7,
  "counts_disabled": 0,
  "launch_ok": false,
  "items": [
    {"key":"launch","label":"1/8 启动验证","status":"FAIL","notes":"Electron 进程在 6 秒内退出;详细诊断见 $RUNTIME_LOG"},
    {"key":"display","label":"2/8 显示方向","status":"NOT_TESTED","notes":""},
    {"key":"animation","label":"3/8 动画表现","status":"NOT_TESTED","notes":""},
    {"key":"click","label":"4/8 点击反馈","status":"NOT_TESTED","notes":""},
    {"key":"drag","label":"5/8 拖动同步","status":"NOT_TESTED","notes":""},
    {"key":"transparent","label":"6/8 透明区穿透","status":"NOT_TESTED","notes":""},
    {"key":"window_focus","label":"7/8 焦点与置顶","status":"NOT_TESTED","notes":""},
    {"key":"multidisplay","label":"8/8 多显示器","status":"DISABLED_SINGLE_DISPLAY","notes":""}
  ]
}
JSON
    pkill -f "ClickThroughProbe" 2>/dev/null || true
    echo "$RESULT"
    exit 0
fi

# --- 3. 启动 PetAcceptor ---
(
    exec "$ACCEPTOR" \
        --candidate candidate_b \
        --version V0.0 \
        --commit "$GIT_COMMIT" \
        --bundle-id com.test.petB \
        --result-out "$RESULT" \
        < /dev/null
) &
ACC_PID=$!
echo "[run_pet_acceptor_b] PetAcceptor PID=$ACC_PID" >> "$LOG"
wait $ACC_PID
ACC_RC=$?
echo "[run_pet_acceptor_b] PetAcceptor exit=$ACC_RC" >> "$LOG"

# --- 4. 清理 ---
pkill -f "Electron.*candidates/candidate_b" 2>/dev/null || true
pkill -f "ClickThroughProbe" 2>/dev/null || true
sleep 1

if [ -f "$RESULT" ]; then
    echo "$RESULT"
else
    echo '{"candidate":"candidate_b","overall":"NOT_TESTED","items":[]}' > "$RESULT"
    echo "$RESULT"
fi
