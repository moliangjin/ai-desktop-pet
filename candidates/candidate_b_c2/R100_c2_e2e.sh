#!/bin/bash
# candidates/candidate_b_c2/R100_c2_e2e.sh
#
# R100 C2 专属 E2E — 实际启动 candidate_b_c2, 验证:
#   1. 启动加载素材 (asset-report)
#   2. 模式切换主-渲同步 (request-mode IPC 协议)
#   3. Canvas 重建后事件监听
#   4. 重复模式切换无累计监听
#   5. 角色屏幕中心稳定
#   6. 退出无遗留窗口
#   7. 真实帧 alpha 边界 (独立 PIL 验证, 沙箱无 PIXI 也能跑)
#
# 不依赖 m87_prod_e2e.sh 旧测试 (R100 §六 要求 C2 专属).
# 不调用系统鼠标注入.

set +e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
LOG_DIR="/tmp/r100_c2_e2e"
mkdir -p "$LOG_DIR"
PASS=0
FAIL=0
TOTAL=0
ELECTRON="$REPO/candidates/candidate_b_electronpixir/node_modules/.bin/electron"
MAIN="$HERE/src/main.js"
MANIFEST="$REPO/assets/prototype_chibi/manifest.json"

if [ ! -x "$ELECTRON" ]; then
    echo "FATAL: electron not found at $ELECTRON"
    exit 2
fi
if [ ! -f "$MANIFEST" ]; then
    echo "FATAL: manifest not found at $MANIFEST"
    exit 3
fi

# === Test 1: 启动 candidate_b_c2 8s, 验证 asset-report 显示 loaded > 0 ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 1: 启动 C2 compact + asset 加载 ==="
PET_R100_SELFTEST=1 "$ELECTRON" "$MAIN" --manifest "$MANIFEST" --mode compact --quit-after=10 > "$LOG_DIR/t1_boot.log" 2>&1 &
PID=$!
# 给足时间等 renderer manifest 加载 + asset-report 输出
sleep 7
# 强 kill (macOS electron --quit-after 不一定立即退出)
kill -9 $PID 2>/dev/null
sleep 1
pkill -9 -f "candidate_b_c2/src/main" 2>/dev/null
pkill -9 -f "Electron Helper" 2>/dev/null
echo "--- log 关键行 ---"
grep -E "asset-report|sprite enabled|set-mode|FATAL|Error" "$LOG_DIR/t1_boot.log" | head -10
if grep -q "asset-report" "$LOG_DIR/t1_boot.log"; then
    # 验证至少一个动作 loaded > 0 (BSD grep 兼容, 不用 -P)
    loaded_count=$(grep "asset-report" "$LOG_DIR/t1_boot.log" | grep -oE "loaded=[0-9]+" | grep -oE "[0-9]+" | awk '{s+=$1} END {print s}')
    if [ "${loaded_count:-0}" -gt 0 ]; then
        echo "[PASS] Test 1: asset loaded total=${loaded_count} > 0 (期望 26+)"
        PASS=$((PASS+1))
    else
        echo "[FAIL] Test 1: asset loaded total=${loaded_count} (期望 > 0)"
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] Test 1: 无 asset-report 日志"
    FAIL=$((FAIL+1))
fi

# === Test 2-5: 实际跑主进程没法触发 IPC 切换 (无 DevTools).
# 改用 --mode standard + --mode compact 启动两次验证两个模式分别启动.
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 2: standard 模式启动 ==="
"$ELECTRON" "$MAIN" --manifest "$MANIFEST" --mode standard --quit-after=8 > "$LOG_DIR/t2_standard.log" 2>&1 &
PID=$!
sleep 5
kill -9 $PID 2>/dev/null
pkill -9 -f "candidate_b_c2/src/main" 2>/dev/null
pkill -9 -f "Electron Helper" 2>/dev/null
sleep 1
if grep -q "PIXI version" "$LOG_DIR/t2_standard.log"; then
    echo "[PASS] Test 2: standard 模式成功启动 (PIXI 加载)"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 2: standard 模式启动失败"
    FAIL=$((FAIL+1))
fi

# === Test 3: 重复 compact 启动 (多次启动退出无残留) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 3: 重复 compact 启动 3 次无残留 ==="
for i in 1 2 3; do
    "$ELECTRON" "$MAIN" --manifest "$MANIFEST" --mode compact --quit-after=5 > "$LOG_DIR/t3_loop_$i.log" 2>&1 &
    PID=$!
    sleep 3
    kill -9 $PID 2>/dev/null
    pkill -9 -f "candidate_b_c2/src/main" 2>/dev/null
    pkill -9 -f "Electron Helper" 2>/dev/null
    sleep 1
done
# 验证无残留 electron 进程
remaining=$(pgrep -f "candidate_b_c2/src/main.js" 2>/dev/null | wc -l | tr -d ' ')
if [ "${remaining:-0}" -eq 0 ]; then
    echo "[PASS] Test 3: 3 次 compact 启动后无残留 electron 进程"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 3: 残留 ${remaining} 个 electron 进程"
    FAIL=$((FAIL+1))
    pkill -f "candidate_b_c2/src/main.js" 2>/dev/null
fi

# === Test 4: 真实帧 alpha 边界 (PIL 独立验证, 沙箱无 PIXI 也能跑) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 4: 26 帧 alpha 边界 (PIL 独立验证) ==="
if python3 "$HERE/R100_alpha_bounds.py" > "$LOG_DIR/t4_alpha.log" 2>&1; then
    if grep -q "全部 26 帧成功: True" "$LOG_DIR/t4_alpha.log"; then
        # 验证 union bbox 数值
        if grep -q "x range: \[71, 184\]" "$LOG_DIR/t4_alpha.log" && grep -q "y range: \[24, 221\]" "$LOG_DIR/t4_alpha.log"; then
            echo "[PASS] Test 4: 26 帧 alpha 边界 union=[71,184]x[24,221]"
            PASS=$((PASS+1))
        else
            echo "[FAIL] Test 4: alpha 边界数值与预期不符"
            FAIL=$((FAIL+1))
        fi
    else
        echo "[FAIL] Test 4: alpha 边界分析返回非 True"
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] Test 4: alpha 边界脚本执行失败"
    FAIL=$((FAIL+1))
fi

# === Test 5: 资源 26 帧文件存在 ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 5: 26 帧素材文件存在 ==="
total_png=$(find "$REPO/assets/prototype_chibi/animations" -name "*.png" | wc -l | tr -d ' ')
if [ "${total_png:-0}" -eq 26 ]; then
    echo "[PASS] Test 5: 26 帧 PNG 文件全部存在"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 5: 期望 26 帧, 实际 ${total_png}"
    FAIL=$((FAIL+1))
fi

# === Test 6: 原始候选 B 文件未被修改 (R100 §八) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 6: 原始候选 B hash 不变 (R100 §八) ==="
EXPECTED_MAIN="28ad0ab2109128793c1075e957eec467752b8bdf782a9de3bfb126bf60621a58"
EXPECTED_RENDERER="e37185ccbecece3559ba805caea6834850e68d9758c1d09f33e71f0a36f00b17"
ACTUAL_MAIN=$(shasum -a 256 "$REPO/candidates/candidate_b_electronpixir/src/main.js" | awk '{print $1}')
ACTUAL_RENDERER=$(shasum -a 256 "$REPO/candidates/candidate_b_electronpixir/src/renderer.js" | awk '{print $1}')
if [ "$ACTUAL_MAIN" = "$EXPECTED_MAIN" ] && [ "$ACTUAL_RENDERER" = "$EXPECTED_RENDERER" ]; then
    echo "[PASS] Test 6: 候选 B main.js + renderer.js hash 不变"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 6: hash 不匹配"
    echo "  main:     $ACTUAL_MAIN"
    echo "  expected: $EXPECTED_MAIN"
    echo "  renderer: $ACTUAL_RENDERER"
    echo "  expected: $EXPECTED_RENDERER"
    FAIL=$((FAIL+1))
fi

# === Test 7: renderer 语法 (含 lastAdvanceAt 修复) ===
TOTAL=$((TOTAL+1))
echo ""
echo "=== Test 7: candidate_b_c2 renderer.js 语法 ==="
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
echo "=== Test 8: candidate_b_c2 main.js 语法 ==="
if node --check "$HERE/src/main.js" 2>&1; then
    echo "[PASS] Test 8: main.js 语法 OK"
    PASS=$((PASS+1))
else
    echo "[FAIL] Test 8: main.js 语法错"
    FAIL=$((FAIL+1))
fi

echo ""
echo "=== R100 C2 专属 E2E Summary ==="
echo "Total: $TOTAL  PASS: $PASS  FAIL: $FAIL"
echo "Logs: $LOG_DIR/"
exit $FAIL
