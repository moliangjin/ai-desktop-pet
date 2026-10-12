#!/bin/bash
# one_click_test/run_pet_acceptor_a.sh
#
# V0.0 R47：
#   1. 4秒 launch 存活检测 → 把结果作为 --launch-status LAUNCH_PASS/FAIL 传给 PetAcceptor
#   2. PetAcceptor 用 NSApplicationActivationPolicyAccessory（不再 Regular）
#   3. wait $ACC_PID 严格等用户操作；不做超时自动结束
#   4. 启动失败/launch_fail → 写 RESULT 但不再阻塞，直接退出
set -e
DST="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
BUNDLE="$DST/_app_bundle/PetCandidateA.app"
ACCEPTOR="$DST/test_window/PetAcceptor/build/PetAcceptor.app/Contents/MacOS/PetAcceptor"
PROBE="$DST/test_window/ClickThroughProbe/build/ClickThroughProbe.app/Contents/MacOS/ClickThroughProbe"

LOG_DIR="$DST/evidence/acceptor_runs"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_ID="candidate_a_${TIMESTAMP}"
LOG="$LOG_DIR/${RUN_ID}.log"
RUNTIME_LOG="$LOG_DIR/${RUN_ID}_runtime.log"
RESULT="$LOG_DIR/${RUN_ID}_result.json"

GIT_COMMIT=$(cd "$DST" && git rev-parse HEAD 2>/dev/null | head -c 7)
if [ -z "$GIT_COMMIT" ]; then GIT_COMMIT="uncommitted"; fi

{
    echo "[run_pet_acceptor_a] $(date)"
    echo "[run_pet_acceptor_a] bundle: $BUNDLE"
    echo "[run_pet_acceptor_a] commit: $GIT_COMMIT"
    echo "[run_pet_acceptor_a] RUN_ID=$RUN_ID"
} >> "$LOG"

# --- 1. 前置：启动探针窗口 ---
pkill -f "ClickThroughProbe" 2>/dev/null || true
sleep 1
"$PROBE" </dev/null >/dev/null 2>&1 &
PROBE_PID=$!
sleep 2
echo "[run_pet_acceptor_a] probe PID=$PROBE_PID" >> "$LOG"

# --- 2. 启动候选 A ---
pkill -f "PetCandidateA" 2>/dev/null || true
sleep 1
echo "" > "$RUNTIME_LOG"
(
    exec "$BUNDLE/Contents/MacOS/PetCandidateA" \
        --manifest "$DST/assets/prototype_chibi/manifest.json" \
        --size 256 --x 600 --y 600 \
        --perf-out "$DST/evidence/perf_samples/candidate_a_${TIMESTAMP}_perf.csv" \
        --quit-after 600 \
        < /dev/null \
        >> "$RUNTIME_LOG" 2>&1
) &
CAND_PID=$!
echo "[run_pet_acceptor_a] candidate A PID=$CAND_PID" >> "$LOG"
sleep 4

LAUNCH_STATUS="LAUNCH_PASS"
if ! ps -p $CAND_PID > /dev/null; then
    LAUNCH_STATUS="LAUNCH_FAIL"
    echo "[run_pet_acceptor_a] CANDIDATE_A_LAUNCH_FAIL PID=$CAND_PID 已退出" >> "$LOG"
fi

if [ "$LAUNCH_STATUS" = "LAUNCH_FAIL" ]; then
    # 启动失败 — 写 fail result, 不启动 PetAcceptor GUI（任务书 §四 区分 LAUNCH_FAIL vs GUI_NOT_TESTED）
    LAUNCH_OK="false"
    NOW="$(date +%Y-%m-%dT%H:%M:%S+08:00)"
    cat > "$RESULT" <<JSON
{
  "candidate": "candidate_a",
  "version": "V0.0",
  "commit": "$GIT_COMMIT",
  "bundle_id": "com.test.petA",
  "tested_at": "$NOW",
  "overall": "FAIL",
  "launch_status": "$LAUNCH_STATUS",
  "launch_ok": $LAUNCH_OK,
  "termination_reason": "RUNNER_LAUNCH_FAIL",
  "counts_pass": 0,
  "counts_fail": 1,
  "counts_not_tested": 7,
  "counts_disabled": 0,
  "items": [
    {"key":"launch","label":"1/8 启动验证","status":"FAIL","notes":"自动检测到进程在 4 秒内退出;详细诊断见 $RUNTIME_LOG"},
    {"key":"display","label":"2/8 显示方向","status":"NOT_TESTED","notes":"启动失败，连带所有后续项无法测试"},
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
    echo "$RESULT" | tee -a "$LOG"
    exit 0
fi

echo "[run_pet_acceptor_a] candidate A alive, launching PetAcceptor GUI" >> "$LOG"

# --- 3. 启动 PetAcceptor GUI（必须 wait 它退出，不做超时） ---
(
    exec "$ACCEPTOR" \
        --candidate candidate_a \
        --version V0.0 \
        --commit "$GIT_COMMIT" \
        --bundle-id com.test.petA \
        --launch-status "$LAUNCH_STATUS" \
        --result-out "$RESULT" \
        < /dev/null
) &
ACC_PID=$!
echo "[run_pet_acceptor_a] PetAcceptor PID=$ACC_PID launch=$LAUNCH_STATUS" >> "$LOG"

# 关键：wait PetAcceptor 退出（用户点■ END_TEST 才正常退出；关窗会被 applicationShouldTerminate 拦截）
wait $ACC_PID
ACC_RC=$?
echo "[run_pet_acceptor_a] PetAcceptor exit=$ACC_RC" >> "$LOG"

# --- 4. 清理 ---
pkill -f "PetCandidateA" 2>/dev/null || true
pkill -f "ClickThroughProbe" 2>/dev/null || true
sleep 1

# --- 5. 输出 result 路径供主控收集 ---
if [ -f "$RESULT" ]; then
    echo "[run_pet_acceptor_a] OK result=$RESULT" | tee -a "$LOG"
    echo "$RESULT"
else
    echo "[run_pet_acceptor_a] WARN result not produced; synthesizing minimal JSON" | tee -a "$LOG"
    NOW="$(date +%Y-%m-%dT%H:%M:%S+08:00)"
    cat > "$RESULT" <<JSON
{
  "candidate": "candidate_a","version":"V0.0","commit":"$GIT_COMMIT","bundle_id":"com.test.petA",
  "tested_at":"$NOW","overall":"NOT_TESTED","launch_status":"$LAUNCH_STATUS","launch_ok":true,
  "termination_reason":"RUNNER_NO_RESULT","counts_pass":0,"counts_fail":0,
  "counts_not_tested":8,"counts_disabled":0,"items":[]
}
JSON
    echo "$RESULT"
fi
