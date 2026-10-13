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
    e2e_double_run)
        # R47：同一程序连续跑两次 — 不污染
        run_pet_acceptor_simulated candidate_a com.test.petA all_pass | xargs -I{} python3 "$DST/one_click_test/csv_builder.py" {} "$CSV"
        run_pet_acceptor_simulated candidate_a com.test.petA all_pass | xargs -I{} python3 "$DST/one_click_test/csv_builder.py" {} "$CSV"
        ;;
    e2e_abort_user_closed)
        # R47：用户关闭窗口（≠ 主动点击■）
        cat > "$LOG_DIR/candidate_a_USER_CLOSED.json" <<JSON
{
  "candidate": "candidate_a","version": "V0.0","commit": "$GIT_COMMIT","bundle_id": "com.test.petA",
  "tested_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)","overall": "NOT_TESTED","launch_status": "LAUNCH_PASS","launch_ok": true,
  "termination_reason": "USER_CLOSED_WINDOW",
  "counts_pass": 0,"counts_fail": 0,"counts_not_tested": 8,"counts_disabled": 0,
  "items": [{"key":"launch","label":"1/8","status":"NOT_TESTED","notes":"启动完成 (ps 检测)"},{"key":"display","label":"2/8","status":"NOT_TESTED","notes":""},{"key":"animation","label":"3/8","status":"NOT_TESTED","notes":""},{"key":"click","label":"4/8","status":"NOT_TESTED","notes":""},{"key":"drag","label":"5/8","status":"NOT_TESTED","notes":""},{"key":"transparent","label":"6/8","status":"NOT_TESTED","notes":""},{"key":"window_focus","label":"7/8","status":"NOT_TESTED","notes":""},{"key":"multidisplay","label":"8/8","status":"DISABLED_SINGLE_DISPLAY","notes":""}]
}
JSON
        python3 "$DST/one_click_test/csv_builder.py" "$LOG_DIR/candidate_a_USER_CLOSED.json" "$CSV" > /dev/null
        ;;
    e2e_launch_status_mapping)
        # R47: launch_status 字段独立于 GUI 反馈
        for cand_launch in LAUNCH_PASS LAUNCH_FAIL; do
            cat > "$LOG_DIR/candidate_a_${cand_launch}.json" <<JSON
{
  "candidate": "candidate_a","version":"V0.0","commit":"$GIT_COMMIT","bundle_id":"com.test.petA",
  "tested_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","overall":"NOT_TESTED",
  "launch_status":"$cand_launch","launch_ok":$( [ "$cand_launch" = LAUNCH_PASS ] && echo true || echo false ),
  "termination_reason":"RUNNER_CRASH_SIGNAL",
  "counts_pass":0,"counts_fail":0,"counts_not_tested":7,"counts_disabled":1,
  "items":[]
}
JSON
            python3 "$DST/one_click_test/csv_builder.py" "$LOG_DIR/candidate_a_${cand_launch}.json" "$CSV" > /dev/null
        done
        ;;
    e2e_r51_incomplete)
        # R51: 模拟 r47_20261013_074739 实测 — 仅 launch=PASS, 其它 NOT_TESTED
        # 旧逻辑: PASS (bug);新逻辑: INCOMPLETE
        NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        cat > "$LOG_DIR/candidate_a_r51_incomplete.json" <<JSON
{
  "candidate": "candidate_a","version":"V0.0","commit":"$GIT_COMMIT","bundle_id":"com.test.petA",
  "tested_at":"$NOW","overall":"INCOMPLETE","launch_status":"LAUNCH_PASS","launch_ok":true,
  "termination_reason":"USER_CLICKED_END",
  "counts_pass":1,"counts_fail":0,"counts_not_tested":6,"counts_disabled":1,
  "items":[
    {"key":"launch","label":"1/8","status":"PASS","notes":"启动验证"},
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
        python3 "$DST/one_click_test/csv_builder.py" "$LOG_DIR/candidate_a_r51_incomplete.json" "$CSV" > /dev/null
        # 业务校验：CSV 这一行 overall == INCOMPLETE
        RC=0
        python3 "$DST/test_window/PetAcceptor/build/e2e_r51_check.py" "$CSV" "$LOG_DIR/candidate_a_r51_incomplete.json" >> "$TXT" 2>&1 || RC=$?
        if [ $RC -eq 0 ]; then
            echo "e2e_r51_incomplete: BUSINESS CHECK OK — overall=INCOMPLETE 实测特征一致" | tee -a "$TXT"
        else
            echo "e2e_r51_incomplete: BUSINESS CHECK FAIL (rc=$RC)" | tee -a "$TXT"
        fi
        ;;
    *)
        echo "usage: e2e_runner.sh [e2e_normal|e2e_a_fail|e2e_csv_audit|e2e_double_run|e2e_abort_user_closed|e2e_launch_status_mapping|e2e_r51_incomplete]"
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
EXPECTED = 20
print(f"header cols: {len(rows[0])} (expected {EXPECTED}) {'OK' if len(rows[0])==EXPECTED else 'FAIL'}")
print(f"data rows: {len(rows)-1}")
all_ok = True
ALLOWED = {'PASS','FAIL','NOT_TESTED','DISABLED_SINGLE_DISPLAY','INCOMPLETE','true','false'}
ALLOWED_LAUNCH = {'LAUNCH_PASS','LAUNCH_FAIL','GUI_NOT_TESTED'}
ALLOWED_OVERALL = {'PASS','FAIL','NOT_TESTED','INCOMPLETE',''}
for i, row in enumerate(rows[1:], start=2):
    if len(row) != EXPECTED:
        print(f"  row {i}: {len(row)} cols FAIL")
        all_ok = False
        continue
    # 列对应 csv_builder.py STABLE_FIELDS:
    # 0=tested_at, 1=candidate, 2=version, 3=commit, 4=bundle_id,
    # 5=launch_status, 6=launch_ok, 7=overall,
    # 8=launch, 9=display, 10=animation, 11=click, 12=drag, 13=transparent,
    # 14=window_focus, 15=multidisplay, 16=notes, ...
    if row[5] not in ALLOWED_LAUNCH:
        print(f"  row {i} launch_status={row[5]!r} NOT IN ENUM")
        all_ok = False
    # launch_ok (col 6) — 应是 'true'/'false'
    if row[6] not in ('true','false',''):
        print(f"  row {i} launch_ok={row[6]!r} NOT 'true'/'false'")
        all_ok = False
    # overall (col 7) — R51 加 INCOMPLETE 枚举校验
    if row[7] not in ALLOWED_OVERALL:
        print(f"  row {i} overall={row[7]!r} NOT IN ENUM")
        all_ok = False
    # 8 项 (col 8..15)
    for col_i, field_name in enumerate(['launch','display','animation','click','drag','transparent','window_focus','multidisplay']):
        v = row[col_i + 8]
        if v not in ALLOWED and v != '':
            print(f"  row {i} col[{field_name}]={v!r} NOT IN ENUM")
            all_ok = False
print("ALL OK" if all_ok else "SOME ROWS FAIL")
PY

echo ""
cat "$TXT"
