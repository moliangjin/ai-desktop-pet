#!/usr/bin/env bash
# test_window/PetAcceptor/e2e_runner.sh
#
# 端到端模拟 .command：launch 检测 + PetAcceptor + csv_builder
# 不弹窗 — 直接喂 self-test 结果给 CSV builder，验证流水线 (not UI)。
#
# 三种场景：
#   1) e2e_normal      — 候选 A+B 都 all_pass，CSV 累计 2 行 + AB 汇总都 PASS
#   2) e2e_a_fail      — 候选 A launch_fail，CSV 1 FAIL 1 PASS；汇总 AB 对比
#   3) e2e_csv_audit   — 校验最终 CSV 每个 cell 在枚举内、每行字段数
set +e
DST="$(cd "$(dirname "$0")" && git rev-parse --show-toplevel 2>/dev/null)"
OUT="$DST/test_window/PetAcceptor/build/PetAcceptor.app/Contents/MacOS/PetAcceptor"
LOG_DIR="$DST/test_window/PetAcceptor/build/e2e"
mkdir -p "$LOG_DIR"

GIT_COMMIT="$(git -C "$DST" rev-parse HEAD 2>/dev/null | head -c 7)"
[ -z "$GIT_COMMIT" ] && GIT_COMMIT="uncommitted"

run_pet_acceptor_simulated() {
    local candidate="$1"   # candidate_a / candidate_b
    local bundle_id="$2"
    local self_test="$3"   # all_pass / launch_fail_a / ...
    local result="$LOG_DIR/${candidate}_${self_test}_result.json"
    "$OUT" \
        --candidate "$candidate" \
        --version "V0.0" \
        --commit "$GIT_COMMIT" \
        --bundle-id "$bundle_id" \
        --result-out "$result" \
        --self-test "$self_test" \
        > "$LOG_DIR/${candidate}_${self_test}.log" 2>&1
    sleep 1
    if [ ! -f "$result" ]; then
        # 模拟"启动失败"：手写一份 launch_fail 占位 JSON
        cat > "$result" <<JSON
{"candidate":"$candidate","version":"V0.0","commit":"$GIT_COMMIT","bundle_id":"$bundle_id","tested_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","overall":"FAIL","counts_pass":0,"counts_fail":1,"counts_not_tested":7,"counts_disabled":1,"launch_ok":false,"items":[{"key":"launch","label":"1/8 启动验证","status":"FAIL","notes":"e2e 模拟启动失败"},{"key":"display","label":"2/8","status":"NOT_TESTED","notes":""},{"key":"animation","label":"3/8","status":"NOT_TESTED","notes":""},{"key":"click","label":"4/8","status":"NOT_TESTED","notes":""},{"key":"drag","label":"5/8","status":"NOT_TESTED","notes":""},{"key":"transparent","label":"6/8","status":"NOT_TESTED","notes":""},{"key":"window_focus","label":"7/8","status":"NOT_TESTED","notes":""},{"key":"multidisplay","label":"8/8","status":"DISABLED_SINGLE_DISPLAY","notes":""}]}
JSON
    fi
    echo "$result"
}

SCENARIO="${1:-e2e_normal}"
CSV="$LOG_DIR/user_visual_report_${SCENARIO}.csv"
TXT="$LOG_DIR/user_visual_report_${SCENARIO}.txt"
: > "$CSV"

case "$SCENARIO" in
    e2e_normal)
        run_pet_acceptor_simulated candidate_a com.test.petA all_pass | xargs -I{} python3 "$DST/one_click_test/csv_builder.py" {} "$CSV"
        run_pet_acceptor_simulated candidate_b com.test.petB all_pass | xargs -I{} python3 "$DST/one_click_test/csv_builder.py" {} "$CSV"
        ;;
    e2e_a_fail)
        run_pet_acceptor_simulated candidate_a com.test.petA launch_fail_a | xargs -I{} python3 "$DST/one_click_test/csv_builder.py" {} "$CSV"
        run_pet_acceptor_simulated candidate_b com.test.petB all_pass | xargs -I{} python3 "$DST/one_click_test/csv_builder.py" {} "$CSV"
        ;;
    e2e_csv_audit)
        run_pet_acceptor_simulated candidate_a com.test.petA all_pass | xargs -I{} python3 "$DST/one_click_test/csv_builder.py" {} "$CSV"
        run_pet_acceptor_simulated candidate_b com.test.petB mixed | xargs -I{} python3 "$DST/one_click_test/csv_builder.py" {} "$CSV"
        run_pet_acceptor_simulated candidate_a com.test.petA abort_midway | xargs -I{} python3 "$DST/one_click_test/csv_builder.py" {} "$CSV"
        ;;
    *)
        echo "usage: e2e_runner.sh [e2e_normal|e2e_a_fail|e2e_csv_audit]"
        exit 2
        ;;
esac

# CSV 严格校验
{
    echo "=========================================="
    echo " 端到端模拟 — $SCENARIO"
    echo " Commit: $GIT_COMMIT"
    echo " CSV: $CSV"
    echo "=========================================="
    cat "$CSV"
    echo ""
    echo "=========================================="
    echo " 表头字段数 + 每行字段数 + 状态枚举"
    echo "=========================================="
} > "$TXT"

python3 - "$CSV" >> "$TXT" <<'PY'
import sys, csv
fp = sys.argv[1]
with open(fp) as f:
    reader = csv.reader(f)
    rows = list(reader)
if not rows:
    print("EMPTY CSV"); sys.exit(1)
EXPECTED = 19
print(f"header cols: {len(rows[0])} (expected {EXPECTED}) {'OK' if len(rows[0])==EXPECTED else 'FAIL'}")
print(f"data rows: {len(rows)-1}")
all_ok = True
ALLOWED = {'PASS','FAIL','NOT_TESTED','DISABLED_SINGLE_DISPLAY','true','false'}
for i, row in enumerate(rows[1:], start=2):
    if len(row) != EXPECTED:
        print(f"  row {i}: {len(row)} cols FAIL")
        all_ok = False
        continue
    for col_i, field_name in enumerate(['tested_at','candidate','version','commit','bundle_id','launch_ok','overall','launch','display','animation','click','drag','transparent','window_focus','multidisplay']):
        v = row[col_i]
        if field_name in ('overall',) or field_name in {'launch','display','animation','click','drag','transparent','window_focus','multidisplay'}:
            if v not in ALLOWED and v != '':
                print(f"  row {i} col[{field_name}]={v!r} NOT IN ENUM")
                all_ok = False
print("ALL OK" if all_ok else "SOME ROWS FAIL")
PY

echo ""
cat "$TXT"
