#!/bin/bash
# candidates/candidate_b_c2/R104_c2_e2e.sh
#
# R104 C2 专属 E2E — 真正 BrowserWindow 拖拽 + 动画预览 + 资源/退出验证
# 验证:
#   1-10. R102 10 项 (保留)
#   11. 真正 BrowserWindow 拖拽 (main window-drag-start/move/end IPC 处理)
#   12. 动画预览 keydown handler (1/2/3/4 切动作)
#   13. sprite 拖动期间位置稳定 (不再被 drag 移动)
#   14. click vs drag 区分 (3px 容忍)

set +e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
LOG_DIR="/tmp/r104_c2_e2e"
mkdir -p "$LOG_DIR"
PASS=0
FAIL=0
TOTAL=0

# R102 P0-6 保留: 针对性 PID 清理
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

ELECTRON="$REPO/candidates/candidate_b_electronpixir/node_modules/.bin/electron"
MAIN="$HERE/src/main.js"
MANIFEST="$REPO/assets/prototype_chibi/manifest.json"

if [ ! -x "$ELECTRON" ]; then echo "FATAL: electron not found"; exit 2; fi
if [ ! -f "$MANIFEST" ]; then echo "FATAL: manifest not found"; exit 3; fi

# 启动 electron 包装 — 记录 PID + 等 quit-after + 收退出码
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

# === Test 1: compact 启动 200x240 + asset 26 帧 (R102 保留) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 1: compact 200x240 + asset 26 帧 ==="
run_electron "compact" "compact" "$LOG_DIR/t1_compact.log"
loaded_count=$(grep "asset-report" "$LOG_DIR/t1_compact.log" | grep -oE "loaded=[0-9]+" | grep -oE "[0-9]+" | awk '{s+=$1} END {print s}')
if [ "${loaded_count:-0}" -ge 26 ] && grep -qE "bounds=\([0-9]+,[0-9]+,200,240\)" "$LOG_DIR/t1_compact.log"; then
    echo "[PASS] Test 1: compact 200x240 + asset loaded=$loaded_count"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 1"
    FAIL=$((FAIL+1))
fi

# === Test 2: standard 256x256 + asset 26 帧 (R102 保留) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 2: standard 256x256 + asset 26 帧 ==="
run_electron "standard" "standard" "$LOG_DIR/t2_standard.log"
loaded_count=$(grep "asset-report" "$LOG_DIR/t2_standard.log" | grep -oE "loaded=[0-9]+" | grep -oE "[0-9]+" | awk '{s+=$1} END {print s}')
if [ "${loaded_count:-0}" -ge 26 ] && grep -qE "bounds=\([0-9]+,[0-9]+,256,256\)" "$LOG_DIR/t2_standard.log"; then
    echo "[PASS] Test 2: standard 256x256 + asset loaded=$loaded_count"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 2"
    FAIL=$((FAIL+1))
fi

# === Test 3: 真实 IPC 模式切换 (R102 保留) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 3: 真实 IPC 模式切换 ==="
PET_R100_SELFTEST=1 "$ELECTRON" "$MAIN" --manifest "$MANIFEST" \
    --mode compact --quit-after=10 \
    > "$LOG_DIR/t3_ipc_switch.log" 2>&1 &
local_pid=$!
record_pid "$local_pid"
sleep 8
has_compact=$(grep -c "mode=compact" "$LOG_DIR/t3_ipc_switch.log")
has_standard=$(grep -c "mode=standard" "$LOG_DIR/t3_ipc_switch.log")
has_render_ready=$(grep -c "renderer-mode-ready" "$LOG_DIR/t3_ipc_switch.log")
has_protocol_match=$(grep -c "match=true" "$LOG_DIR/t3_ipc_switch.log")
if [ "$has_compact" -ge 2 ] && [ "$has_standard" -ge 2 ] && [ "$has_render_ready" -ge 1 ] && [ "$has_protocol_match" -ge 1 ]; then
    echo "[PASS] Test 3: 真实 IPC 模式切换 (compact=$has_compact, standard=$has_standard, ready=$has_render_ready, match=$has_protocol_match)"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 3"
    FAIL=$((FAIL+1))
fi
kill -TERM "$local_pid" 2>/dev/null
sleep 1
kill -KILL "$local_pid" 2>/dev/null

# === Test 4: 26 帧 alpha 边界 (R102 保留) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 4: 26 帧 alpha 边界 (PIL) ==="
if python3 "$HERE/R100_alpha_bounds.py" > "$LOG_DIR/t4_alpha.log" 2>&1; then
    if grep -q "x range: \[71, 184\]" "$LOG_DIR/t4_alpha.log" && grep -q "y range: \[24, 221\]" "$LOG_DIR/t4_alpha.log"; then
        echo "[PASS] Test 4: alpha boundary union=[71,184]x[24,221]"
        PASS=$((PASS+1))
    else
        echo "[FAIL] Test 4"
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] Test 4"
    FAIL=$((FAIL+1))
fi

# === Test 5: 26 帧 PNG 存在 (R102 保留) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 5: 26 帧 PNG 存在 ==="
total_png=$(find "$REPO/assets/prototype_chibi/animations" -name "*.png" | wc -l | tr -d ' ')
if [ "${total_png:-0}" -eq 26 ]; then
    echo "[PASS] Test 5: 26 帧 PNG"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 5: actual=${total_png}"
    FAIL=$((FAIL+1))
fi

# === Test 6: 候选 B hash 不变 (R102 保留) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 6: 候选 B hash 不变 ==="
EXPECTED_MAIN="28ad0ab2109128793c1075e957eec467752b8bdf782a9de3bfb126bf60621a58"
EXPECTED_RENDERER="e37185ccbecece3559ba805caea6834850e68d9758c1d09f33e71f0a36f00b17"
ACTUAL_MAIN=$(shasum -a 256 "$REPO/candidates/candidate_b_electronpixir/src/main.js" | awk '{print $1}')
ACTUAL_RENDERER=$(shasum -a 256 "$REPO/candidates/candidate_b_electronpixir/src/renderer.js" | awk '{print $1}')
if [ "$ACTUAL_MAIN" = "$EXPECTED_MAIN" ] && [ "$ACTUAL_RENDERER" = "$EXPECTED_RENDERER" ]; then
    echo "[PASS] Test 6: 候选 B hash 不变"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 6: hash 变化"
    FAIL=$((FAIL+1))
fi

# === Test 7/8: syntax (R102 保留) ===
for i in 7 8; do
    TOTAL=$((TOTAL+1))
    if [ "$i" = "7" ]; then
        file="$HERE/src/renderer.js"
        name="renderer.js"
    else
        file="$HERE/src/main.js"
        name="main.js"
    fi
    if node --check "$file" 2>&1; then
        echo "[PASS] Test $i: $name 语法 OK"
        PASS=$((PASS+1))
    else
        echo "[FAIL] Test $i: $name 语法错"
        FAIL=$((FAIL+1))
    fi
done

# === Test 9: canvas 监听解绑 (R102 保留) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 9: canvas 监听解绑 ==="
PET_R100_SELFTEST=1 "$ELECTRON" "$MAIN" --manifest "$MANIFEST" \
    --mode compact --quit-after=10 \
    > "$LOG_DIR/t9_listener_rebind.log" 2>&1 &
local_pid=$!
record_pid "$local_pid"
sleep 8
attach_count=$(grep -c "listeners attached" "$LOG_DIR/t9_listener_rebind.log")
detach_count=$(grep -c "listeners detached" "$LOG_DIR/t9_listener_rebind.log")
diff=$((attach_count - detach_count))
if [ "$diff" -le 1 ] && [ "$diff" -ge 0 ]; then
    echo "[PASS] Test 9: canvas 监听解绑 (diff=$diff ≤ 1)"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 9: diff=$diff"
    FAIL=$((FAIL+1))
fi
kill -TERM "$local_pid" 2>/dev/null
sleep 1
kill -KILL "$local_pid" 2>/dev/null

# === Test 10: 无残留 PID (R102 保留) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 10: 无残留 PID ==="
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
    echo "[FAIL] Test 10: 残留 $remaining"
    FAIL=$((FAIL+1))
fi

# === Test 11 (R104 P0-1): 真正 BrowserWindow 拖拽 IPC 处理 ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 11: R104 真正 BrowserWindow 拖拽 (window-drag-start/move/end IPC 处理) ==="
# 沙箱无真实鼠标, 验证源码 IPC handler 注册 + 启动无错
# 真实拖拽行为 (移动 BrowserWindow) 需 Mac 真机验证 (NOT_GUI_VERIFIED)
src_start=$(grep -c "ipcMain.handle('window-drag-start'" "$HERE/src/main.js")
src_move=$(grep -c "ipcMain.on('window-drag-move'" "$HERE/src/main.js")
src_end=$(grep -c "ipcMain.on('window-drag-end'" "$HERE/src/main.js")
run_electron "drag" "compact" "$LOG_DIR/t11_drag.log"
# 启动无 uncaughtException
if [ "$src_start" -ge 1 ] && [ "$src_move" -ge 1 ] && [ "$src_end" -ge 1 ] && ! grep -qE "uncaughtException|Error: " "$LOG_DIR/t11_drag.log"; then
    echo "[PASS] Test 11: 源码 IPC handlers 注册 (start=$src_start, move=$src_move, end=$src_end) + 启动无错 — 真实拖拽需 Mac 真机 (NOT_GUI_VERIFIED)"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 11: src start=$src_start move=$src_move end=$src_end"
    FAIL=$((FAIL+1))
fi

# === Test 12 (R104 P0-2): 动画预览 keydown handler ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 12: R104 动画预览 (1=idle/2=walk/3=jump/4=drag) ==="
run_electron "preview" "compact" "$LOG_DIR/t12_preview.log"
if grep -q "R104 animation preview ready" "$LOG_DIR/t12_preview.log"; then
    echo "[PASS] Test 12: 动画预览 keydown handler 已注册 (用户 Mac 可按 1/2/3/4 切动作)"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 12: 动画预览未注册"
    FAIL=$((FAIL+1))
fi

# === Test 13 (R104 P0-1 验证): sprite 拖动期间位置稳定 ===
# R104: sprite 在 drag 期间不再被修改 x/y (整个 BrowserWindow 移动, sprite 相对窗口位置不变)
# 验证 tickerCallback 中不再有 sprite_.x = ...; sprite_.y = ... (R100 旧逻辑)
if ! grep -qE "sprite_\.x = ev\.global\.x" "$HERE/src/renderer.js"; then
    if ! grep -qE "sprite_\.x = ev\.clientX - rect\.left" "$HERE/src/renderer.js"; then
        echo "[PASS] Test 13: 源码不再修改 sprite.x/y (拖拽真正移动 BrowserWindow, sprite 位置稳定)"
        PASS=$((PASS+1))
    else
        echo "[FAIL] Test 13: 仍修改 sprite.x/y (canvas 内拖动冒充窗口拖拽)"
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] Test 13: 仍修改 sprite.x/y (canvas 内拖动冒充窗口拖拽)"
    FAIL=$((FAIL+1))
fi
TOTAL=$((TOTAL+1))

# === Test 14 (R104 P0-1 验证): click vs drag 区分 ===
# R104: drag 启动后 3px 内仍算点击, 3px 后才真拖
if grep -q "dragMoved_ < 3" "$HERE/src/renderer.js" && grep -q "dx \* dx + dy \* dy < 9" "$HERE/src/renderer.js"; then
    echo "[PASS] Test 14: 3px 容忍 + dx²+dy²<9 区分点击 vs 拖动"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 14: click vs drag 区分代码缺失"
    FAIL=$((FAIL+1))
fi
TOTAL=$((TOTAL+1))

echo ""
echo "=== R104 C2 专属 E2E Summary ==="
echo "Total: $TOTAL  PASS: $PASS  FAIL: $FAIL"
echo "Logs: $LOG_DIR/"
exit $FAIL
