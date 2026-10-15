#!/usr/bin/env bash
# tools/passthrough_poc/m87_prod_e2e.sh
#
# R89 正式 orchestrator E2E — 跑真实 m79_orchestrator.js + 注入 MOCK 依赖.
#
# 设计原则:
#   1. MOCK 注入是测试专用 (env 变量), 生产默认真实 binary (Mavis 内存记录红线)
#   2. 事件驱动计数: fake_clicker 写 sentinel → fake_poc 按几何判定 +1 → orchestrator 严格 ===
#   3. 失败注入必须真触发: ENOENT 真用不存在路径, ax-blocked 真被 mode 拦截
#   4. 不许用 MOCK_GTE 凑 PASS — 每条 case 必须真测对应失败模式

set +e
cd "$(dirname "$0")"
HERE="$(pwd)"
ORCH="$HERE/m79_orchestrator.js"
FAKE_CLICKER="$HERE/m87_fake_clicker.sh"
FAKE_POC="$HERE/m87_fake_poc.js"
LOG_DIR="/tmp/m87_e2e"
mkdir -p "$LOG_DIR"
PASS=0
FAIL=0
TOTAL=0
NON_REAL=0  # MOCK 妥协 / 不真测的 case 计数

# 结果文件路径
get_out() {
    ls -t $LOG_DIR/m87_$1_*.txt 2>/dev/null | head -1
}

# 跑一种 scenario.
# 参数: $1=name $2=fake_clicker_mode $3=fake_poc_mode $4=expected_exit $5=expected_status_substr
#       $6=optional expected_stage (R92 §五 严格断言: 实际 stage 来自 JSON notes 末尾)
#       $7=optional MOCK_CLICKER_PATH (默认 = FAKE_CLICKER)
#       $8=optional extra_env (如 MOCK_POC_NO_MODE_SWITCH=true)
run_scenario() {
    local name="$1"
    local click_mode="$2"
    local poc_mode="$3"
    local want_exit="$4"
    local want_substr="$5"
    local want_stage="${6:-}"
    local clicker_path="${7:-$FAKE_CLICKER}"
    local extra_env="$8"

    TOTAL=$((TOTAL+1))
    local ts=$(date +%s)
    local base="$LOG_DIR/m87_${name}_${ts}"

    # 用 MOCK_CLICKER 模拟 clicker
    local out exit
    out=$(FAKE_CLICKER_MODE="$click_mode" \
          FAKE_POC_MODE="$poc_mode" \
          QUIT_AFTER=20 \
          MOCK_CLICKER="$clicker_path" \
          MOCK_POC="$FAKE_POC" \
          $extra_env \
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
        # R92 §五: 严格 stage 断言
        if [ -f "$base.json" ]; then
            local actual_stage=$(python3 -c "import json; d=json.load(open('$base.json')); notes=d.get('notes', []); print(notes[-1] if notes else '?')" 2>/dev/null || echo "parse_err")
            if [ -n "$want_stage" ] && [ "$actual_stage" != "$want_stage" ]; then
                echo "[FAIL] $name (exit=$exit OK, but stage mismatch: expected='$want_stage' actual='$actual_stage')"
                FAIL=$((FAIL+1))
                return 1
            fi
        fi
        if [ -n "$want_substr" ]; then
            if grep -qF "$want_substr" "$base.out" 2>/dev/null || grep -qF "$want_substr" "$base.txt" 2>/dev/null; then
                echo "[PASS] $name (exit=$exit, contains '$want_substr', stage=$actual_stage)"
                PASS=$((PASS+1))
                return 0
            else
                echo "[FAIL] $name (exit=$exit OK, missing '$want_substr' in output)"
                FAIL=$((FAIL+1))
                return 1
            fi
        else
            echo "[PASS] $name (exit=$exit, stage=$actual_stage)"
            PASS=$((PASS+1))
            return 0
        fi
    else
        echo "[FAIL] $name (expected exit=$want_exit, got $exit)"
        FAIL=$((FAIL+1))
        return 1
    fi
}

echo "=== R89 正式 orchestrator E2E (事件驱动 MOCK 注入) ==="
echo ""

# ============================================================
# §三 17 步成功路径 (R89 P1-1)
# ============================================================
echo "--- §三 17 步成功路径 ---"
run_scenario "success"          "ok"  "success"  0 "control_click: PASS" "stage=OK"
# 真实失败路径 (R89 P0-1): 点击器文件不存在 → 任何阶段 clickJson ENOENT 都报 CLICKER_NOT_FOUND
run_scenario "fail_clicker_404" "ok"  "success" 1 "CLICKER_NOT_FOUND" "stage=AX" "/tmp/m87_no_such_clicker_$$_$(date +%N)"
# 真实失败路径 (R89 P0-2): click OK 但 PoC 计数不变 (clicker 不写 sentinel)
# click-ok-no-count-change 不写 sentinel → fake_poc success 模式不切 C1 → mode-switch FAIL exit=4
# (想测 gold-count 失败需要切 C1, 改用 ignore-clicks 模式让 fake_poc 切 C1 但不 +1)
run_scenario "fail_no_change"   "click-ok-no-count-change" "success" 4 "FAIL" "stage=mode-switch"
# 真实失败路径 (R89 P1-4 情形 E): click 到错目标 (fake_poc 收 sentinel 但几何判定 none → 计数不变)
# click_mode=ok 让 clicker 写真实坐标 (切 C1), fake_poc wrong-target 模式故意 +1 到 probe (错) → gold count FAIL exit=5
run_scenario "wrong_target"     "ok"  "wrong-target" 5 "FAIL" "stage=gold-count"
# 真实失败路径 (R89 P1-4 情形 D): click 执行器返回 FAIL
run_scenario "click_fail"       "click-fail" "success" 5 "FAIL" "stage=C1-click"
# R89 P0-2 完整测试: click-signal-no-count + ignore-clicks → 切 C1 但 +0 → gold-count FAIL exit=5
run_scenario "no_count_after_switch" "click-signal-no-count" "ignore-clicks" 5 "FAIL" "stage=gold-count"

# ============================================================
# §三 异常场景
# ============================================================
echo ""
echo "--- §三 异常场景 ---"
run_scenario "mode_a_only"      "ok"  "mode-a-only" 4 "FAIL" "stage=mode-switch"
run_scenario "broken_json"      "ok"  "broken-json" 6 "no tick in 8s" "stage=PoC"
run_scenario "no_c1_button"     "ok"  "no-c1-button" 8 "C1 button rect not in tick" "stage=C1-rect"
run_scenario "early_exit"       "ok"  "exit-early" 4 "mode did not switch" "stage=mode-switch"  # R90: fake_poc 提前退出 → orchestrator 收不到 C1 tick → mode-switch FAIL
run_scenario "ignore_clicks"    "ok"  "ignore-clicks" 5 "FAIL" "stage=gold-count"

# ============================================================
# §四 失败注入 (R89 P1-2)
# ============================================================
echo ""
echo "--- §四 失败注入 ---"
run_scenario "fail_ax"            "ax-blocked"          "success"        1 "AX:" "stage=AX"
run_scenario "fail_clicker_exit1" "ax-blocked"          "success"        1 "AX:" "stage=AX"
run_scenario "fail_invalid_json"  "invalid-json"        "success"        1 "json parse error" "stage=AX"
run_scenario "fail_param_nan"     "param-nan"           "success"        1 "coord not finite" "stage=AX"
run_scenario "fail_self_test"     "ax-ok-self-test-fail" "success"        1 "self-test:" "stage=self-test"
run_scenario "fail_crash"         "crash"               "success"        1 "AX:" "stage=AX"  # crash 在 AX 阶段 exit=99 → orchestrator 报 AX fail

echo ""
echo "=== R89 E2E Summary ==="
echo "Total: $TOTAL  PASS: $PASS  FAIL: $FAIL"
echo "Logs: $LOG_DIR/"
exit $FAIL
