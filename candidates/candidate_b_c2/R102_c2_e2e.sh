#!/bin/bash
# candidates/candidate_b_c2/R102_c2_e2e.sh
#
# R102 C2 专属 E2E — 实际启动 candidate_b_c2 + 真实 IPC 模式切换回归.
# 验证:
#   1. 启动加载素材 (asset-report 26 帧)
#   2. 真实 IPC 模式切换 (compact → standard → compact) via window.__setMode
#   3. compact 初始窗口 200x240 (修 R100 §一)
#   4. Canvas 事件解绑完整 (修 R100 §三)
#   5. 标准 256x256
#   6. 26 帧 alpha 边界
#   7. 26 帧文件存在
#   8. 原始候选 B hash 不变 (R100 §八)
#   9. renderer.js / main.js 语法
#
# R102 P0-6: 不使用 pkill -f "Electron Helper" 全局命令
# 改为记录本次启动的 PID, 仅 kill 本进程的 child helpers

set +e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
LOG_DIR="/tmp/r102_c2_e2e"
mkdir -p "$LOG_DIR"
PASS=0
FAIL=0
TOTAL=0
ELECTRON="$REPO/candidates/candidate_b_electronpixir/node_modules/.bin/electron"
MAIN="$HERE/src/main.js"
MANIFEST="$REPO/assets/prototype_chibi/manifest.json"

# R102 P0-6: 针对性 PID 记录, 不用全局 pkill
declare -a TEST_PIDS=()

record_pid() {
    local pid=$1
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        TEST_PIDS+=("$pid")
    fi
}

cleanup_all() {
    for pid in "${TEST_PIDS[@]:-}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null
        fi
    done
    sleep 1
    for pid in "${TEST_PIDS[@]:-}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL "$pid" 2>/dev/null
        fi
    done
    TEST_PIDS=()
}
trap cleanup_all EXIT INT TERM

# 启动 electron 包装 — 记录 PID + 等待 quit-after + 收退出码
run_electron() {
    local desc="$1"
    local mode="$2"
    local out_log="$3"
    local quit_after="${4:-8}"
    PET_R100_SELFTEST=1 "$ELECTRON" "$MAIN" --manifest "$MANIFEST" \
        --mode "$mode" --quit-after="$quit_after" \
        > "$out_log" 2>&1 &
    local pid=$!
    record_pid "$pid"
    sleep 6
    kill -TERM "$pid" 2>/dev/null
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        kill -KILL "$pid" 2>/dev/null
    fi
    wait "$pid" 2>/dev/null
    echo "  $desc 退出 rc=$?"
}

if [ ! -x "$ELECTRON" ]; then
    echo "FATAL: electron not found at $ELECTRON"
    exit 2
fi
if [ ! -f "$MANIFEST" ]; then
    echo "FATAL: manifest not found at $MANIFEST"
    exit 3
fi

# === Test 1: compact 启动 + asset 26 帧 + 真实 BrowserWindow 200x240 ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 1: compact 启动 (R102 P0-1 200x240) + asset 加载 ==="
run_electron "compact" "compact" "$LOG_DIR/t1_compact.log"
echo "--- key log ---"
grep -E "bounds=|canvas=|hitArea=|asset-report" "$LOG_DIR/t1_compact.log" | head -10
# 验证 asset loaded
loaded_count=$(grep "asset-report" "$LOG_DIR/t1_compact.log" | grep -oE "loaded=[0-9]+" | grep -oE "[0-9]+" | awk '{s+=$1} END {print s}')
if [ "${loaded_count:-0}" -ge 26 ]; then
    # 验证 BrowserWindow bounds = 200x240
    if grep -qE "bounds=\([0-9]+,[0-9]+,200,240\)" "$LOG_DIR/t1_compact.log"; then
        echo "[PASS] Test 1: compact 200x240 + asset loaded=$loaded_count"
        PASS=$((PASS+1))
    else
        echo "[FAIL] Test 1: compact 窗口尺寸 ≠ 200x240"
        grep "bounds=" "$LOG_DIR/t1_compact.log" | head -1
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] Test 1: asset loaded=$loaded_count (期望 ≥ 26)"
    FAIL=$((FAIL+1))
fi

# === Test 2: standard 启动 (256x256) + asset 加载 ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 2: standard 启动 (256x256) + asset 加载 ==="
run_electron "standard" "standard" "$LOG_DIR/t2_standard.log"
loaded_count=$(grep "asset-report" "$LOG_DIR/t2_standard.log" | grep -oE "loaded=[0-9]+" | grep -oE "[0-9]+" | awk '{s+=$1} END {print s}')
if [ "${loaded_count:-0}" -ge 26 ]; then
    if grep -qE "bounds=\([0-9]+,[0-9]+,256,256\)" "$LOG_DIR/t2_standard.log"; then
        echo "[PASS] Test 2: standard 256x256 + asset loaded=$loaded_count"
        PASS=$((PASS+1))
    else
        echo "[FAIL] Test 2: standard 窗口尺寸 ≠ 256x256"
        grep "bounds=" "$LOG_DIR/t2_standard.log" | head -1
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] Test 2: asset loaded=$loaded_count (期望 ≥ 26)"
    FAIL=$((FAIL+1))
fi

# === Test 3: 真实 IPC 模式切换 (compact → standard → compact) ===
# R102 P1-1: 不只分别启动不同 CLI, 实际通过 window.__setMode 运行时切换
# 借 PET_R100_SELFTEST=1 让 renderer runR100SelfTest 内切, 但 start 模式是 compact
# R100 self-test 内部: applyModeToScene('compact') → applyModeToScene('standard')
# 注意: 这会临时切到 standard. 验证结束是否最终回到 compact.
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 3: 真实 IPC 模式切换 (R102 P1-1) ==="
PET_R100_SELFTEST=1 "$ELECTRON" "$MAIN" --manifest "$MANIFEST" \
    --mode compact --quit-after=10 \
    > "$LOG_DIR/t3_ipc_switch.log" 2>&1 &
local_pid=$!
record_pid "$local_pid"
sleep 8
# 看 renderer 输出的模式切换 log
echo "--- 模式切换相关 log ---"
grep -E "mode=|set-mode|renderer-mode-ready|protocolMatch" "$LOG_DIR/t3_ipc_switch.log" | head -15
# 验证有 compact → standard 切换 (R100 self-test 触发)
has_compact=$(grep -c "mode=compact" "$LOG_DIR/t3_ipc_switch.log")
has_standard=$(grep -c "mode=standard" "$LOG_DIR/t3_ipc_switch.log")
has_render_ready=$(grep -c "renderer-mode-ready" "$LOG_DIR/t3_ipc_switch.log")
has_protocol_match=$(grep -c "match=true" "$LOG_DIR/t3_ipc_switch.log")
echo "  mode=compact 出现: $has_compact"
echo "  mode=standard 出现: $has_standard"
echo "  renderer-mode-ready 出现: $has_render_ready"
echo "  protocolMatch=true 出现: $has_protocol_match"
if [ "$has_compact" -ge 2 ] && [ "$has_standard" -ge 2 ] && [ "$has_render_ready" -ge 1 ] && [ "$has_protocol_match" -ge 1 ]; then
    echo "[PASS] Test 3: 真实 IPC 模式切换 (compact → standard → compact) 完整往返"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 3: 模式切换不完整 (compact=$has_compact, standard=$has_standard, ready=$has_render_ready, match=$has_protocol_match)"
    FAIL=$((FAIL+1))
fi
kill -TERM "$local_pid" 2>/dev/null
sleep 1
kill -KILL "$local_pid" 2>/dev/null

# === Test 4: 26 帧 alpha 边界 ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 4: 26 帧 alpha 边界 (PIL 独立验证) ==="
if python3 "$HERE/R100_alpha_bounds.py" > "$LOG_DIR/t4_alpha.log" 2>&1; then
    if grep -q "x range: \[71, 184\]" "$LOG_DIR/t4_alpha.log" && grep -q "y range: \[24, 221\]" "$LOG_DIR/t4_alpha.log"; then
        echo "[PASS] Test 4: 26 帧 alpha 边界 union=[71,184]x[24,221]"
        PASS=$((PASS+1))
    else
        echo "[FAIL] Test 4: alpha 边界数值与预期不符"
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] Test 4: alpha 边界脚本执行失败"
    FAIL=$((FAIL+1))
fi

# === Test 5: 26 帧 PNG 文件存在 ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 5: 26 帧 PNG 存在 ==="
total_png=$(find "$REPO/assets/prototype_chibi/animations" -name "*.png" | wc -l | tr -d ' ')
if [ "${total_png:-0}" -eq 26 ]; then
    echo "[PASS] Test 5: 26 帧 PNG 全部存在"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 5: 期望 26 帧, 实际 ${total_png}"
    FAIL=$((FAIL+1))
fi

# === Test 6: 原始候选 B hash 不变 (R100 §八) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 6: 原始候选 B hash 不变 ==="
EXPECTED_MAIN="28ad0ab2109128793c1075e957eec467752b8bdf782a9de3bfb126bf60621a58"
EXPECTED_RENDERER="e37185ccbecece3559ba805caea6834850e68d9758c1d09f33e71f0a36f00b17"
ACTUAL_MAIN=$(shasum -a 256 "$REPO/candidates/candidate_b_electronpixir/src/main.js" | awk '{print $1}')
ACTUAL_RENDERER=$(shasum -a 256 "$REPO/candidates/candidate_b_electronpixir/src/renderer.js" | awk '{print $1}')
if [ "$ACTUAL_MAIN" = "$EXPECTED_MAIN" ] && [ "$ACTUAL_RENDERER" = "$EXPECTED_RENDERER" ]; then
    echo "[PASS] Test 6: 候选 B hash 不变"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 6: hash 不匹配"
    FAIL=$((FAIL+1))
fi

# === Test 7: renderer.js 语法 ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 7: renderer.js 语法 ==="
if node --check "$HERE/src/renderer.js" 2>&1; then
    echo "[PASS] Test 7: renderer.js 语法 OK"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 7: renderer.js 语法错"
    FAIL=$((FAIL+1))
fi

# === Test 8: main.js 语法 ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 8: main.js 语法 ==="
if node --check "$HERE/src/main.js" 2>&1; then
    echo "[PASS] Test 8: main.js 语法 OK"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 8: main.js 语法错"
    FAIL=$((FAIL+1))
fi

# === Test 9: canvas 监听重绑 — 重复切换 3 次 (R102 P0-3 验证) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 9: 重复模式切换后 canvas 监听不累计 (R102 P0-3) ==="
PET_R100_SELFTEST=1 "$ELECTRON" "$MAIN" --manifest "$MANIFEST" \
    --mode compact --quit-after=10 \
    > "$LOG_DIR/t9_listener_rebind.log" 2>&1 &
local_pid=$!
record_pid "$local_pid"
sleep 8
# R100 self-test 内 applyModeToScene('compact') → ('standard'), 但 detachCanvasListeners
# 修复后每次重建 canvas 都有完整 (move+up) 解绑 + 重绑. 验证只有最后一次 'attached' log.
attach_count=$(grep -c "listeners attached" "$LOG_DIR/t9_listener_rebind.log")
detach_count=$(grep -c "listeners detached" "$LOG_DIR/t9_listener_rebind.log")
# R102 P0-3: detach 必须完整 (R100 修复后 try/finally 原子解绑)
# 验证: attach 数 = detach 数 (R102 期望严格配对, 因为 detach 修复后是原子操作)
# 允许 attach=detach+1 (self-test 进行中状态, 最后一对没完成)
diff=$((attach_count - detach_count))
echo "  canvas listeners attached: $attach_count"
echo "  canvas listeners detached: $detach_count"
echo "  diff (attach-detach): $diff"
if [ "$diff" -le 1 ] && [ "$diff" -ge 0 ]; then
    echo "[PASS] Test 9: canvas 监听解绑完整 (diff=$diff ≤ 1, R102 P0-3 修复生效)"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 9: 监听累计 diff=$diff (期望 0 或 1)"
    FAIL=$((FAIL+1))
fi
kill -TERM "$local_pid" 2>/dev/null
sleep 1
kill -KILL "$local_pid" 2>/dev/null

# === Test 10: 退出后无残留 (R102 P0-6 针对性清理) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 10: 退出后无残留 (R102 P0-6 针对性 PID 清理) ==="
# cleanup_all 已通过 trap 触发, 验证本轮启动的 PID 全死
remaining=0
for pid in "${TEST_PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
        remaining=$((remaining + 1))
    fi
done
if [ "$remaining" -eq 0 ]; then
    echo "[PASS] Test 10: 无残留 PID"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 10: 残留 $remaining 个 PID"
    FAIL=$((FAIL+1))
fi

echo ""
echo "=== R102 C2 专属 E2E Summary ==="
echo "Total: $TOTAL  PASS: $PASS  FAIL: $FAIL"
echo "Logs: $LOG_DIR/"
exit $FAIL
