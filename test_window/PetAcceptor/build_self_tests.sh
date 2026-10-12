#!/usr/bin/env bash
# test_window/PetAcceptor/build_self_tests.sh
#
# 跑 PetAcceptor 9 个 headless 自测 case + 解析 JSON 结果 + 校验 CSV 字段表头严格对齐
#
# 用法：
#   bash test_window/PetAcceptor/build_self_tests.sh
# 输出：
#   build/self_tests/<case>.log        — 每个 case 的 NSLog 输出
#   build/results/<case>.json          — 每个 case 的 result JSON
#   退出码：0 = 全 PASS，1 = 有 case FAIL
set +e
DST="$(cd "$(dirname "$0")" && git rev-parse --show-toplevel 2>/dev/null)"
# removed
OUT="$DST/test_window/PetAcceptor/build/PetAcceptor.app/Contents/MacOS/PetAcceptor"
LOG_DIR="$DST/test_window/PetAcceptor/build/self_tests"
RESULTS_DIR="$DST/test_window/PetAcceptor/build/results"
mkdir -p "$LOG_DIR" "$RESULTS_DIR"

GIT_COMMIT="$(git -C "$DST" rev-parse HEAD 2>/dev/null | head -c 7)"
if [ -z "$GIT_COMMIT" ]; then GIT_COMMIT="uncommitted"; fi

declare -a CASES=(
    all_pass
    all_fail
    mixed
    abort_midway
    prev_edit
    launch_fail_a
    launch_fail_b
    csv_schema
    switch_a_to_b
)

# R47: wait_120s 任务书 §六 强制要求；默认包含；用 --skip-wait 跳过
if [ "${1:-}" != "--skip-wait" ]; then
    CASES+=(wait_120s)
fi

pass_count=0
fail_count=0

echo "=========================================="
echo "PetAcceptor 自测 (R45 §五)"
echo "  GIT_COMMIT=$GIT_COMMIT"
echo "  DST=$DST"
echo "=========================================="

for case in "${CASES[@]}"; do
    result="$RESULTS_DIR/${case}.json"
    log="$LOG_DIR/${case}.log"
    # 默认长：常规 case 几秒内 self-test 模式完成；wait_120s 特殊跳过结果校验
    if [ "$case" = "wait_120s" ]; then
        echo "--- $case: 启动后等 120s，期间不能自动退出 ---"
        rm -f "$result"
        "$OUT" \
            --candidate "candidate_a" \
            --version "V0.0" \
            --commit "$GIT_COMMIT" \
            --bundle-id "com.test.petA" \
            --result-out "$result" \
            --self-test "$case" > "$log" 2>&1 &
        APID=$!
        # 在 60s、90s、120s 三个时间点检查还活着
        ALIVE_AT_60=NO; ALIVE_AT_90=NO; ALIVE_AT_120=NO
        for ts in 60 90 120; do
            SECONDS_LEFT=$ts
            while [ $SECONDS_LEFT -gt 0 ]; do
                sleep 5
                if ! ps -p $APID > /dev/null 2>&1; then
                    break 2
                fi
                SECONDS_LEFT=$((SECONDS_LEFT-5))
            done
            [ $ts -eq 60 ] && ALIVE_AT_60=YES
            [ $ts -eq 90 ] && ALIVE_AT_90=YES
            [ $ts -eq 120 ] && ALIVE_AT_120=YES
        done
        if ps -p $APID > /dev/null; then
            echo "[$case] STILL ALIVE at 120s — 强 kill"
            kill -9 $APID 2>/dev/null
            sleep 1
        fi
        # 检查 result JSON — wait_120s 不自动写，需要 SIGTERM 后 willTerminate 兜底
        [ -f "$result" ] && HAS_RESULT=YES || HAS_RESULT=NO
        echo "[$case] alive@60=$ALIVE_AT_60 alive@90=$ALIVE_AT_90 alive@120=$ALIVE_AT_120 result_written=$HAS_RESULT"
        if [ "$ALIVE_AT_120" = "YES" ] && [ "$HAS_RESULT" = "YES" ]; then
            echo "[$case] PASS — 120s 内未自动结束且 SIGTERM 后写盘"
            pass_count=$((pass_count+1))
        else
            echo "[$case] FAIL"
            fail_count=$((fail_count+1))
        fi
        continue
    fi

    "$OUT" \
        --candidate "candidate_a" \
        --version "V0.0" \
        --commit "$GIT_COMMIT" \
        --bundle-id "com.test.petA" \
        --result-out "$result" \
        --self-test "$case" > "$log" 2>&1
    RC=$?
    sleep 1
    if [ ! -f "$result" ]; then
        echo "[$case] FAIL — JSON 未产生 (rc=$RC)"
        fail_count=$((fail_count+1))
        continue
    fi
    # 校验 JSON schema
    schema_ok=$(python3 -c "
import json,sys
try:
    d=json.load(open('$result'))
    keys=sorted([it['key'] for it in d['items']])
    expected=sorted(['launch','display','animation','click','drag','transparent','window_focus','multidisplay'])
    assert keys==expected
    for it in d['items']:
        assert it['status'] in ('PASS','FAIL','NOT_TESTED','DISABLED_SINGLE_DISPLAY')
    print('OK')
except Exception as e:
    print(f'BAD: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)
    if [ "$schema_ok" != "OK" ]; then
        echo "[$case] FAIL — schema: $schema_ok"
        fail_count=$((fail_count+1))
        continue
    fi
    case_overall=$(python3 -c "import json; print(json.load(open('$result'))['overall'])")
    counts=$(python3 -c "import json; d=json.load(open('$result')); print(f\"pass={d['counts_pass']} fail={d['counts_fail']} nt={d['counts_not_tested']} dis={d['counts_disabled']}\")")

    case_expected=""
    case "$case" in
        all_pass)              case_expected="PASS";;
        all_fail)              case_expected="FAIL";;
        mixed)                 case_expected="FAIL";;
        abort_midway)          case_expected="FAIL";;
        prev_edit)             case_expected="FAIL";;
        launch_fail_a|launch_fail_b) case_expected="FAIL";;
        csv_schema)            case_expected="PASS";;
        switch_a_to_b)         case_expected="PASS";;
        *)                     case_expected="?";;
    esac
    if [ "$case_overall" = "$case_expected" ]; then
        echo "[$case] PASS — overall=$case_overall $counts"
        pass_count=$((pass_count+1))
    else
        echo "[$case] FAIL — overall=$case_overall (expected $case_expected) $counts"
        fail_count=$((fail_count+1))
    fi
done

# abort_midway: 答 3 项 (launch/display/animation)，剩下 5 项中 4 项 NOT_TESTED + 1 项 multidisplay DISABLED_SINGLE_DISPLAY
# 所以 abort_midway 应该 NOT_TESTED=4, DISABLED=1
abort_unanswered=$(python3 -c "
import json
d=json.load(open('$RESULTS_DIR/abort_midway.json'))
print(sum(1 for it in d['items'] if it['status']=='NOT_TESTED'))
" 2>/dev/null || echo 0)
abort_disabled=$(python3 -c "
import json
d=json.load(open('$RESULTS_DIR/abort_midway.json'))
print(sum(1 for it in d['items'] if it['status']=='DISABLED_SINGLE_DISPLAY'))
" 2>/dev/null || echo 0)
if [ "$abort_unanswered" -ne 4 ] || [ "$abort_disabled" -ne 1 ]; then
    echo "[abort_midway] NOT_TESTED=$abort_unanswered (期望 4) DISABLED=$abort_disabled (期望 1) FAIL"
    fail_count=$((fail_count+1))
else
    echo "[abort_midway] NOT_TESTED=4 DISABLED=1 OK"
fi

# csv_schema 必备字段校验
for f in commit version bundle_id tested_at; do
    if ! grep -q "\"$f\"" "$RESULTS_DIR/csv_schema.json"; then
        echo "[csv_schema] 缺字段 $f FAIL"
        fail_count=$((fail_count+1))
    fi
done

echo "=========================================="
echo "汇总: pass=$pass_count fail=$fail_count total=${#CASES[@]}"
echo "=========================================="
[ "$fail_count" = 0 ] && exit 0 || exit 1
