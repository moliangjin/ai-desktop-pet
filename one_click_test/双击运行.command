#!/bin/bash
# 双击运行.command — V0.0 R47 验收主控 (run_id 隔离版)
#
# 每次运行生成独立 run_id，证据全部归档在 evidence/acceptor_runs/<run_id>/ 目录内。
# 本轮 CSV 含且仅含本轮 A、B 两条数据；历史数据另存为 .csv.HISTORY。
set +e
DST="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DST" || { echo "FAIL: cannot cd to $DST"; exit 1; }

ACCEPTOR="$DST/test_window/PetAcceptor/build/PetAcceptor.app/Contents/MacOS/PetAcceptor"
[ -x "$ACCEPTOR" ] || bash "$DST/test_window/PetAcceptor/build.sh" || { echo "FAIL: PetAcceptor build failed"; exit 2; }

# R47：每轮独立 run_id 目录
RUN_TS=$(date +%Y%m%d_%H%M%S)
RUN_ID="r47_${RUN_TS}"
LOG_DIR="$DST/evidence/acceptor_runs/${RUN_ID}"
mkdir -p "$LOG_DIR"

GIT_COMMIT=$(cd "$DST" && git rev-parse HEAD 2>/dev/null | head -c 7)
GIT_TAG=$(cd "$DST" && git describe --tags --abbrev=0 2>/dev/null)
GIT_BRANCH=$(cd "$DST" && git branch --show-current 2>/dev/null)
[ -z "$GIT_COMMIT" ] && GIT_COMMIT="uncommitted"

# 本轮 CSV / TXT：只含本轮 A+B，不混入历史
CSV="$LOG_DIR/user_visual_report.csv"
TXT="$LOG_DIR/user_visual_report.txt"

cat > "$TXT" <<HEAD
==========================================
  AI 桌宠 V0.0 — R47 图形化验收报告
==========================================
  RUN_ID: $RUN_ID
  仓库: $DST
  分支: $GIT_BRANCH  Commit: $GIT_COMMIT  Tag: $GIT_TAG
  时间: $(date)
  工具: PetAcceptor (AppKit GUI, NSApplicationActivationPolicyAccessory)
  流程: PetCandidate 启动 → ps 检测 → --launch-status 传参 → GUI 等用户操作
        → ■ 结束测试 → 自动写 result JSON → csv_builder → 本轮 CSV

HEAD

# 写 CSV header
python3 "$DST/one_click_test/csv_builder.py" /dev/null "$CSV" 2>/dev/null || true
python3 -c "
import csv
with open('$CSV', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['tested_at','candidate','version','commit','bundle_id','launch_status','launch_ok','overall','launch','display','animation','click','drag','transparent','window_focus','multidisplay','notes','result_path','build_log_path','runtime_log_path'])
"

# ===========================================================================
# 阶段 1: 候选 A
# ===========================================================================
echo "" >> "$TXT"
echo "==========================================" | tee -a "$TXT"
echo " 阶段 1/2: 候选 A（AppKit + Objective-C）" | tee -a "$TXT"
echo " RUN_ID=$RUN_ID" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"

# 调用启动脚本 — 它返回 result 路径，**必须**等 PetAcceptor 真正退出（用户点■ OR 关窗被拦截）
A_RESULT=$(bash "$DST/one_click_test/run_pet_acceptor_a.sh" 2>&1 | tail -1)
echo "候选 A result JSON: $A_RESULT" | tee -a "$TXT"

# 写 CSV（只 append 本轮 A 一行；用 build_csv_row.py）
if [ -n "$A_RESULT" ] && [ -f "$A_RESULT" ]; then
    python3 "$DST/one_click_test/csv_builder.py" "$A_RESULT" "$CSV"
fi

# 清理探针 + A
pkill -f "ClickThroughProbe" 2>/dev/null
sleep 1
osascript -e 'tell application "Pet A Test" to quit' 2>/dev/null

# ===========================================================================
# 阶段 2: 候选 B
# ===========================================================================
echo "" >> "$TXT"
echo "==========================================" | tee -a "$TXT"
echo " 阶段 2/2: 候选 B（Electron + PixiJS）" | tee -a "$TXT"
echo " RUN_ID=$RUN_ID" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"

B_RESULT=$(bash "$DST/one_click_test/run_pet_acceptor_b.sh" 2>&1 | tail -1)
echo "候选 B result JSON: $B_RESULT" | tee -a "$TXT"

if [ -n "$B_RESULT" ] && [ -f "$B_RESULT" ]; then
    python3 "$DST/one_click_test/csv_builder.py" "$B_RESULT" "$CSV"
fi

pkill -f "ClickThroughProbe" 2>/dev/null
pkill -f "Electron.*candidates/candidate_b" 2>/dev/null
sleep 1

# ===========================================================================
# 阶段 3: 校验 + 汇总
# ===========================================================================
echo "" >> "$TXT"
echo "==========================================" | tee -a "$TXT"
echo " CSV 校验 + A/B 对比" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"

# 业务校验：必须只有 2 数据行，A 一次，B 一次，不重复
python3 - "$CSV" >> "$TXT" <<'PY'
import csv, sys, os
fp = sys.argv[1]
if not os.path.exists(fp):
    print("BUSINESS VALIDATION FAIL — CSV missing")
    sys.exit(1)
with open(fp) as f:
    rows = list(csv.reader(f))
header = rows[0]
data = rows[1:]
EXPECTED_FIELDS = len(header)
print(f"schema: header cols={EXPECTED_FIELDS}")
ok_schema = all(len(r) == EXPECTED_FIELDS for r in data)
print(f"  schema ALL OK = {ok_schema}")
# 业务校验
candidates = [r[1] for r in data] if data else []
unique_cands = set(candidates)
print(f"  data rows={len(data)}, unique candidates={len(unique_cands)} ({sorted(unique_cands)})")
ok_business = (len(data) == 2 and unique_cands == {"candidate_a", "candidate_b"})
print(f"  business check (exactly 2 rows, A+B) = {ok_business}")
if ok_schema and ok_business:
    print("ALL OK")
else:
    print("VALIDATION FAILED")
    sys.exit(1)
PY

# A/B 对比
A_OVERALL=$(python3 -c "
import json
try:
    d = json.load(open('$A_RESULT'))
    print(d.get('overall', 'NOT_TESTED'))
except Exception: print('NOT_TESTED')
")
B_OVERALL=$(python3 -c "
import json
try:
    d = json.load(open('$B_RESULT'))
    print(d.get('overall', 'NOT_TESTED'))
except Exception: print('NOT_TESTED')
")

{
    echo ""
    echo "=========================================="
    echo " 最终汇总"
    echo "=========================================="
    echo ""
    echo "## A/B 对比"
    printf "%-15s %-12s\n" "CANDIDATE" "OVERALL"
    printf "%-15s %-12s\n" "candidate_a" "$A_OVERALL"
    printf "%-15s %-12s\n" "candidate_b" "$B_OVERALL"
    echo ""
    echo "## CSV ($(basename "$CSV"))"
    cat "$CSV"
} | tee -a "$TXT"

# 提示用户回传
echo ""
echo "==========================================" | tee -a "$TXT"
echo " RUN_ID=$RUN_ID 完成" | tee -a "$TXT"
echo "" | tee -a "$TXT"
echo "请把以下两份文件回传 MiniMax：" | tee -a "$TXT"
echo "   $CSV" | tee -a "$TXT"
echo "   $TXT" | tee -a "$TXT"
echo "" | tee -a "$TXT"
echo "本轮的全部 result JSON、runtime log 都在：" | tee -a "$TXT"
echo "   $LOG_DIR" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"
echo "$CSV"
echo "$TXT"
