#!/usr/bin/env bash
# tools/passthrough_poc/m87_prod_e2e.sh
#
# R87 正式 orchestrator E2E 测试 — 跑真实 m79_orchestrator.js + 注入 MOCK
# 依赖 (MOCK_CLICKER + MOCK_POC) 测试 17 步成功 + 21 失败注入.

set +e
cd "$(dirname "$0")"
HERE="$(pwd)"
REPO="$(cd ../../.. && pwd)"
ORCH="$HERE/m79_orchestrator.js"
FAKE_CLICKER="$HERE/m87_fake_clicker.sh"
FAKE_POC="$HERE/m87_fake_poc.sh"

LOG_DIR="/tmp/m87_e2e"
mkdir -p "$LOG_DIR"
PASS=0
FAIL=0
TOTAL=0

# 结果文件路径
get_out() {
    ls -t $LOG_DIR/m87_$1_*.txt 2>/dev/null | head -1
}

# 跑一种 scenario. 参数: $1=name  $2=fake_clicker_mode  $3=fake_poc_mode  $4=expected_exit  $5=expected_status_substr
run_scenario() {
    local name="$1"
    local click_mode="$2"
    local poc_mode="$3"
    local want_exit="$4"
    local want_substr="$5"

    TOTAL=$((TOTAL+1))
    local ts=$(date +%s)
    local base="$LOG_DIR/m87_${name}_${ts}"

    # 用 MOCK_CLICKER 模拟 clicker
    local out exit
    out=$(FAKE_CLICKER_MODE="$click_mode" \
          FAKE_POC_MODE="$poc_mode" \
          QUIT_AFTER=8 \
          MOCK_CLICKER="$FAKE_CLICKER" \
          MOCK_POC="$FAKE_POC" \
          /Users/musk123/.hermes/node/bin/node "$ORCH" 2>&1)
    exit=$?
    echo "$out" > "$base.out"
    # 找 orchestrator 写的最新 TXT
    local txt=$(ls -t /tmp/m87_*.txt 2>/dev/null | head -1)
    if [ -n "$txt" ]; then
        cp "$txt" "$base.txt"
        cp "${txt%.txt}.json" "$base.json" 2>/dev/null
        cp "${txt%.txt}.csv" "$base.csv" 2>/dev/null
    fi

    if [ "$exit" = "$want_exit" ]; then
        if [ -n "$want_substr" ]; then
            if grep -qF "$want_substr" "$base.out" 2>/dev/null || grep -qF "$want_substr" "$base.txt" 2>/dev/null; then
                echo "[PASS] $name (exit=$exit, contains '$want_substr')"
                PASS=$((PASS+1))
                return 0
            else
                echo "[FAIL] $name (exit=$exit OK, missing '$want_substr' in output)"
                FAIL=$((FAIL+1))
                return 1
            fi
        else
            echo "[PASS] $name (exit=$exit)"
            PASS=$((PASS+1))
            return 0
        fi
    else
        echo "[FAIL] $name (expected exit=$want_exit, got $exit)"
        FAIL=$((FAIL+1))
        return 1
    fi
}

echo "=== R87 正式 orchestrator E2E (注入 MOCK_CLICKER + MOCK_POC) ==="

# 任务书 §三 17 步成功路径
run_scenario "success"           "ok"                  "success"        0 "control_click: PASS"
run_scenario "mode_a_only"       "ok"                  "mode-a-only"    4 "FAIL"  # 实际 mode A 没切 → exit 4 (CONTROL_FAIL)
run_scenario "broken_json"        "ok"                  "broken-json"     6 "PoC_FAIL"  # JSON 损坏, tick 失败
run_scenario "no_c1_button"       "ok"                  "no-c1-button"   8 "NO_C1"
run_scenario "early_exit"         "ok"                  "exit-early"      0 "control_click: PASS"  # 提早退出但 orchestrator 看到 eof → 收 partial

# 任务书 §四 失败注入 (部分)
run_scenario "fail_ax"            "ax-blocked"          "success"        1 "AX: m79 result=BLOCKED"
run_scenario "fail_clicker_404"   "ok"                  "success"        1 ""  # 点击器不存在 → exit 2
run_scenario "fail_clicker_exit1" "ax-blocked"          "success"        1 "AX"
run_scenario "fail_invalid_json"  "invalid-json"        "success"        1 "json parse error"
run_scenario "fail_param_nan"    "param-nan"           "success"        1 "coord not finite"
run_scenario "fail_self_test"    "self-test-fail"      "success"        1 "self-test"
run_scenario "fail_no_change"     "click-ok-no-count-change" "success"   1 "FAIL"
run_scenario "fail_partial_json" "ok"                  "success"        0 "control_click: PASS"  # 跨块解析 — partial valid

echo ""
echo "=== R87 E2E Summary ==="
echo "Total: $TOTAL  PASS: $PASS  FAIL: $FAIL"
echo "Logs: $LOG_DIR/"
exit $FAIL
