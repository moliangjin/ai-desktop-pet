#!/usr/bin/env bash
# tools/passthrough_poc/m88_arg_smoke.sh
#
# R88 独立参数 smoke 测试 — 替代 m87_native_arg_test.c
# (R87 的 c 程序需要 AX 权限 + c compiler, 沙箱跑不了; 此 shell 测试在 MOCK 模式下
#  验证 clicker 参数边界处理: NaN / Inf / 缺参 / 单数 args / 非数字 / 越界 / 选项冲突)
#
# 退出码规则 (与 m79_native_click 一致):
#   exit 0 = OK / SELFTEST_OK
#   exit 10 = FAIL
#   exit 11 = BLOCKED
#   exit 64 = usage (无参数)
#   其它   = 参数错误 (期望非 0)
#
# 用 fake_clicker 模拟; 真 m79_native_click 由用户 Mac 前台独立验证.

set +e
HERE="$(cd "$(dirname "$0")" && pwd)"
CLICKER="$HERE/m87_fake_clicker.sh"
PASS=0
FAIL=0
TOTAL=0

check() {
    local desc="$1" expected_rc="$2" want_substr="$3" mode="$4" shift_count="$5"
    TOTAL=$((TOTAL+1))
    local out rc
    if [ -n "$mode" ]; then
        out=$(FAKE_CLICKER_MODE="$mode" "$CLICKER" $shift_count 2>&1)
        rc=$?
    else
        out=$("$CLICKER" $shift_count 2>&1)
        rc=$?
    fi
    if [ "$rc" = "$expected_rc" ]; then
        if [ -z "$want_substr" ] || echo "$out" | grep -qF "$want_substr"; then
            echo "[PASS] $desc  rc=$rc"
            PASS=$((PASS+1))
            return
        fi
    fi
    echo "[FAIL] $desc  rc=$rc (want $expected_rc)  out=$out"
    FAIL=$((FAIL+1))
}

echo "=== R88 fake_clicker 参数边界 smoke 测试 ==="

# === 用例 1: 无参数 ===
check "no args → rc=0 ok mode default" 0 "result\":\"OK" "ok" ""
check "no args → 默认 mode 返回 OK + 默认坐标 0/0" 0 '"x":0,"y":0' "ok" ""

# === 用例 2: 正常坐标 ===
check "valid 100 200 → rc=0 OK" 0 '"x":100,"y":200' "ok" "100 200"
check "valid -50 30 → rc=0 OK 负数" 0 '"x":-50,"y":30' "ok" "-50 30"

# === 用例 3: 非数字 / NaN-like ===
check "abc 100 → 非数字, fake_clicker X 不匹配数字保持 0" 0 '"x":0,"y":100' "ok" "abc 100"
check "abc xyz → 双非数字 → X=0 Y=0" 0 '"x":0,"y":0' "ok" "abc xyz"

# === 用例 4: 选项参数 (注: fake 在 ok mode 下 --ax-check 不被识别, 走 click 路径) ===
check "--ax-check ok mode → fake 把它当 click 调用, 输出 OK click 标记" 0 'MOCK_CLICK_POSTED' "ok" "--ax-check"
check "--ax-check ax-check-ok mode → rc=0 accessibility_granted" 0 'accessibility_granted' "ax-check-ok" "--ax-check"
check "--ax-check ax-blocked mode → rc=11 BLOCKED" 11 "BLOCKED" "ax-blocked" "--ax-check"
check "--self-test self-test-ok mode → rc=0 SELFTEST_OK" 0 'SELFTEST_OK' "self-test-ok" "--self-test"
check "--self-test self-test-fail mode → rc=10 FAIL" 10 "FAIL" "self-test-fail" "--self-test"

# === 用例 5: 参数缺失 (单数 / 零数 args 后 click 模式) ===
check "1 个 arg (100) → rc=0 OK (默认 Y=0)" 0 '"x":100,"y":0' "ok" "100"

# === 用例 6: 大量 args (奇数) ===
check "3 args (1 2 3) → rc=0 OK (取前两个)" 0 '"x":1,"y":2' "ok" "1 2 3"

# === 用例 7: 显式 NaN / Inf via fake mode ===
check "param-nan → rc=10 FAIL 'coord not finite'" 10 "coord not finite" "param-nan" "nan 0"
check "param-nan → rc=10 FAIL 'coord not finite' inf" 10 "coord not finite" "param-nan" "inf 0"

# === 用例 8: invalid-json ===
check "invalid-json → rc=0 但 stdout 非 JSON" 0 "this is not json" "invalid-json" ""

# === 用例 9: crash ===
check "crash → rc=99" 99 "" "crash" ""

# === 用例 10: ax-ok-self-test-fail 状态机 ===
rm -f /tmp/m87_fake_clicker_state
check "ax-ok-self-test-fail 第一次 → rc=0 OK" 0 "accessibility_granted" "ax-ok-self-test-fail" "--ax-check"
check "ax-ok-self-test-fail 第二次 → rc=10 FAIL" 10 "self-test forced" "ax-ok-self-test-fail" "--self-test"

# === 用例 11: click-ok-no-count-change ===
check "click-ok-no-count-change → rc=0 OK no change marker" 0 "MOCK_CLICK_POSTED_NO_CHANGE" "click-ok-no-count-change" "100 200"

# === 用例 12: 多参数边界 (巨大坐标) ===
check "1e9 1e9 → 极大坐标 OK" 0 '"x":1000000000' "ok" "1000000000 1000000000"

echo ""
echo "=== R88 参数边界 smoke Summary ==="
echo "Total: $TOTAL  PASS: $PASS  FAIL: $FAIL"
echo "⚠️  这是在 MOCK 模式下用 fake_clicker 测的边界; 真 m79_native_click 必须用户 Mac 前台验证"
exit $FAIL
