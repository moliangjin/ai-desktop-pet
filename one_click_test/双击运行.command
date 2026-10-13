#!/bin/bash
# 双击运行.command — V0.0 R56 验收主控
#
# R56 策略调整:
#   - 默认只测试候选 B（Electron + PixiJS）
#   - 候选 A 已 PAUSED;保留 A 独立入口 _run_candidate_a.command
#   - 不允许用户再次测 A 4 策略方向
#   - 不允许无关重构 PetAcceptor 图形验收界面
#
# 候选 B 重点测试:
#   1. 启动 + 26 帧加载
#   2. 鼠标在角色本体点击 (PASS/FAIL)
#   3. 鼠标拖动角色跟随 (PASS/FAIL)
#   4. 鼠标在透明区点击探针按钮 +1 (PASS/FAIL)
#   5. 鼠标从透明回到角色再点击 (验证恢复)
#   6. 拖动后角色位置正确 (收尾)
#   7. 窗口焦点 + 虚拟桌面 (PASS/FAIL/NOT_TESTED)

set +e
DST="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DST" || { echo "FAIL: cannot cd to $DST"; exit 1; }

ACCEPTOR="$DST/test_window/PetAcceptor/build/PetAcceptor.app/Contents/MacOS/PetAcceptor"
[ -x "$ACCEPTOR" ] || bash "$DST/test_window/PetAcceptor/build.sh" || { echo "FAIL: PetAcceptor build failed"; exit 2; }

# R56 RUN_ID 隔离
RUN_TS=$(date +%Y%m%d_%H%M%S)
RUN_ID="r56_${RUN_TS}"
LOG_DIR="$DST/evidence/acceptor_runs/${RUN_ID}"
mkdir -p "$LOG_DIR"

GIT_COMMIT=$(cd "$DST" && git rev-parse HEAD 2>/dev/null | head -c 7)
GIT_TAG=$(cd "$DST" && git describe --tags --abbrev=0 2>/dev/null)
GIT_BRANCH=$(cd "$DST" && git branch --show-current 2>/dev/null)
[ -z "$GIT_COMMIT" ] && GIT_COMMIT="uncommitted"

CSV="$LOG_DIR/user_visual_report.csv"
TXT="$LOG_DIR/user_visual_report.txt"

cat > "$TXT" <<HEAD
==========================================
  AI 桌宠 V0.0 — R56 图形化验收报告 (候选 B)
==========================================
  RUN_ID: $RUN_ID
  仓库: $DST
  分支: $GIT_BRANCH  Commit: $GIT_COMMIT  Tag: $GIT_TAG
  时间: $(date)
  工具: PetAcceptor (AppKit GUI, NSApplicationActivationPolicyAccessory) — R47
  候选 B 流程: Electron + PixiJS 启动 (默认关闭 R54 setIgnoreMouseEvents 状态机)
              → PetAcceptor 等待用户鼠标操作 7+1 项 → ■ 结束测试
  候选 A: PAUSED (本轮不测试;独立入口: 见 _run_candidate_a.command)
HEAD

python3 -c "
import csv
with open('$CSV', 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerow(['tested_at','candidate','version','commit','bundle_id','launch_status','launch_ok','overall','launch','display','animation','click','drag','transparent','window_focus','multidisplay','notes','result_path','build_log_path','runtime_log_path'])
"

# ===========================================================================
# 阶段 1: 候选 B (Electron + PixiJS)
# ===========================================================================
echo "==========================================" | tee -a "$TXT"
echo " 阶段 1/1: 候选 B (Electron + PixiJS)" | tee -a "$TXT"
echo " RUN_ID=$RUN_ID" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"

B_RESULT=$(bash "$DST/one_click_test/run_pet_acceptor_b.sh" 2>&1 | tail -1)
echo "候选 B result JSON: $B_RESULT" | tee -a "$TXT"

# 写 CSV (1 行 — 候选 B)
if [ -n "$B_RESULT" ] && [ -f "$B_RESULT" ]; then
    python3 "$DST/one_click_test/csv_builder.py" "$B_RESULT" "$CSV"
fi

pkill -f "ClickThroughProbe" 2>/dev/null
pkill -f "Electron.*candidates/candidate_b" 2>/dev/null
sleep 1

# ===========================================================================
# 阶段 2: 校验 + 汇总
# ===========================================================================
echo "" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"
echo " CSV 校验 + 候选 B 汇总" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"

python3 - "$CSV" >> "$TXT" <<'PY'
import csv, sys, os
fp = sys.argv[1]
if not os.path.exists(fp):
    print("CSV missing"); sys.exit(1)
with open(fp) as f:
    rows = list(csv.reader(f))
header = rows[0]
data = rows[1:]
EXPECTED = len(header)
print(f"schema: header cols={EXPECTED}")
ok_schema = all(len(r) == EXPECTED for r in data)
print(f"  schema OK = {ok_schema}")
ok_business = len(data) == 1 and (data and data[0][1] == 'candidate_b')
print(f"  business (exactly 1 row, candidate_b) = {ok_business}")
if ok_schema and ok_business:
    print("ALL OK")
else:
    sys.exit(1)
PY

B_OVERALL=$(python3 -c "
import json
try: print(json.load(open('$B_RESULT'))['overall'])
except Exception: print('NOT_TESTED')
")

{
    echo ""
    echo "=========================================="
    echo " 最终汇总 (候选 B)"
    echo "=========================================="
    echo ""
    echo "## 候选 B 整体判定"
    printf "%-15s %-12s\n" "CANDIDATE" "OVERALL"
    printf "%-15s %-12s\n" "candidate_b" "$B_OVERALL"
    echo ""
    echo "## CSV ($(basename "$CSV"))"
    cat "$CSV"
} | tee -a "$TXT"

echo ""
echo "==========================================" | tee -a "$TXT"
echo " RUN_ID=$RUN_ID 完成" | tee -a "$TXT"
echo "" | tee -a "$TXT"
echo "请把以下两份文件回传 MiniMax:" | tee -a "$TXT"
echo "   $CSV" | tee -a "$TXT"
echo "   $TXT" | tee -a "$TXT"
echo "原始 result JSON 在: $LOG_DIR" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"
echo "$CSV"
echo "$TXT"
