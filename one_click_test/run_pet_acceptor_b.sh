#!/bin/bash
# one_click_test/run_pet_acceptor_b.sh — 候选 B 版 (Electron + PixiJS)
set -e
DST="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
ACCEPTOR="$DST/test_window/PetAcceptor/build/PetAcceptor.app/Contents/MacOS/PetAcceptor"
PROBE="$DST/test_window/ClickThroughProbe/build/ClickThroughProbe.app/Contents/MacOS/ClickThroughProbe"

LOG_DIR="$DST/evidence/acceptor_runs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_ID="candidate_b_${TIMESTAMP}"
LOG="$LOG_DIR/${RUN_ID}.log"
RUNTIME_LOG="$LOG_DIR/${RUN_ID}_runtime.log"
RESULT="$LOG_DIR/${RUN_ID}_result.json"

GIT_COMMIT=$(cd "$DST" && git rev-parse HEAD 2>/dev/null | head -c 7)
if [ -z "$GIT_COMMIT" ]; then GIT_COMMIT="uncommitted"; fi

NOW="$(date +%Y-%m-%dT%H:%M:%S+08:00)"

write_launch_fail_result() {
    cat > "$RESULT" <<JSON
{
  "candidate": "candidate_b",
  "version": "V0.0",
  "commit": "$GIT_COMMIT",
  "bundle_id": "com.test.petB",
  "tested_at": "$NOW",
  "overall": "FAIL",
  "launch_status": "LAUNCH_FAIL",
  "launch_ok": false,
  "termination_reason": "RUNNER_LAUNCH_FAIL",
  "counts_pass": 0,
  "counts_fail": 1,
  "counts_not_tested": 7,
  "counts_disabled": 0,
  "items": [
    {"key":"launch","label":"1/8 启动验证","status":"FAIL","notes":"Electron 进程在 6 秒内退出;详细诊断见 $RUNTIME_LOG"},
    {"key":"display","label":"2/8","status":"NOT_TESTED","notes":""},
    {"key":"animation","label":"3/8","status":"NOT_TESTED","notes":""},
    {"key":"click","label":"4/8","status":"NOT_TESTED","notes":""},
    {"key":"drag","label":"5/8","status":"NOT_TESTED","notes":""},
    {"key":"transparent","label":"6/8","status":"NOT_TESTED","notes":""},
    {"key":"window_focus","label":"7/8","status":"NOT_TESTED","notes":""},
    {"key":"multidisplay","label":"8/8","status":"DISABLED_SINGLE_DISPLAY","notes":""}
  ]
}
JSON
}

# --- 启动探针（置于候选 B 矩形下层并保证重叠） ---
pkill -f "ClickThroughProbe" 2>/dev/null || true
sleep 1
"$PROBE" \
    --under-pet-x 1100 --under-pet-y 600 --under-pet-w 256 --under-pet-h 256 \
    --x 1160 --y 410 --w 360 --h 180 \
    </dev/null >/dev/null 2>&1 &
PROBE_PID=$!
sleep 2

# --- 启动候选 B ---
pkill -f "Electron.*candidates/candidate_b" 2>/dev/null || true
sleep 1
B_ENTRY="$DST/candidates/candidate_b_electronpixir/src/main.js"
echo "" > "$RUNTIME_LOG"

if [ ! -f "$B_ENTRY" ]; then
    write_launch_fail_result
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
sleep 6

LAUNCH_STATUS="LAUNCH_PASS"
if ! ps -p $CAND_PID > /dev/null; then
    LAUNCH_STATUS="LAUNCH_FAIL"
fi

if [ "$LAUNCH_STATUS" = "LAUNCH_FAIL" ]; then
    write_launch_fail_result
    pkill -f "ClickThroughProbe" 2>/dev/null || true
    echo "$RESULT"
    exit 0
fi

# --- 启动 PetAcceptor ---
(
    exec "$ACCEPTOR" \
        --candidate candidate_b \
        --version V0.0 \
        --commit "$GIT_COMMIT" \
        --bundle-id com.test.petB \
        --launch-status "$LAUNCH_STATUS" \
        --result-out "$RESULT" \
        < /dev/null
) &
ACC_PID=$!
echo "[run_pet_acceptor_b] PetAcceptor PID=$ACC_PID launch=$LAUNCH_STATUS" >> "$LOG"
wait $ACC_PID
ACC_RC=$?
echo "[run_pet_acceptor_b] PetAcceptor exit=$ACC_RC" >> "$LOG"

pkill -f "Electron.*candidates/candidate_b" 2>/dev/null || true
pkill -f "ClickThroughProbe" 2>/dev/null || true
sleep 1

if [ -f "$RESULT" ]; then
    echo "$RESULT"
else
    cat > "$RESULT" <<JSON
{
  "candidate": "candidate_b","version":"V0.0","commit":"$GIT_COMMIT","bundle_id":"com.test.petB",
  "tested_at":"$NOW","overall":"NOT_TESTED","launch_status":"$LAUNCH_STATUS","launch_ok":true,
  "termination_reason":"RUNNER_NO_RESULT","counts_pass":0,"counts_fail":0,
  "counts_not_tested":8,"counts_disabled":0,"items":[]
}
JSON
    echo "$RESULT"
fi
