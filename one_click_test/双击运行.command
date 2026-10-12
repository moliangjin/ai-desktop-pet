#!/bin/bash
# 双击运行.command — V0.0 R45 验收主控
#
# 不再使用 terminal read y/n/skip（任务书 §二/§三）。
# 改为：启动候选 → 启动 PetAcceptor 图形验收窗口 → 用户鼠标点击 7 项
# 测试结果 → 用户关闭 PetAcceptor 后自动收集 JSON → 写统一 CSV
set +e
DST="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DST" || { echo "FAIL: cannot cd to $DST"; exit 1; }

# 验证 PetAcceptor 已构建
ACCEPTOR="$DST/test_window/PetAcceptor/build/PetAcceptor.app/Contents/MacOS/PetAcceptor"
[ -x "$ACCEPTOR" ] || bash "$DST/test_window/PetAcceptor/build.sh" || {
    echo "FAIL: PetAcceptor build failed"
    exit 2
}

LOG_DIR="$DST/evidence/acceptor_runs"
CSV="$DST/evidence/build_logs/user_visual_report.csv"
TXT="$DST/evidence/build_logs/user_visual_report.txt"
mkdir -p "$LOG_DIR" "$(dirname "$CSV")"
mkdir -p "$DST/evidence/build_logs"

GIT_COMMIT=$(cd "$DST" && git log --oneline -1 2>/dev/null | head -1 | cut -d' ' -f1)
GIT_TAG=$(cd "$DST" && git describe --tags --abbrev=0 2>/dev/null)
GIT_BRANCH=$(cd "$DST" && git branch --show-current 2>/dev/null)
[ -z "$GIT_COMMIT" ] && GIT_COMMIT="uncommitted"

# 初始化 CSV（保证 header 正确）
python3 "$DST/one_click_test/csv_builder.py" /dev/null "$CSV" 2>/dev/null || true
if ! head -1 "$CSV" 2>/dev/null | grep -q "tested_at,candidate"; then
    head -1 "$CSV" 2>/dev/null
    # 修复：Python csv_builder 我们让它 idempotent 写 header
    python3 -c "
import csv, sys
sys.path.insert(0, '$DST/one_click_test')
from csv_builder import STABLE_FIELDS
with open('$CSV', 'w', newline='', encoding='utf-8') as f:
    csv.DictWriter(f, fieldnames=STABLE_FIELDS).writeheader()
"
fi

cat > "$TXT" <<HEAD
==========================================
  AI 桌宠 V0.0 — R45 图形化验收报告
==========================================
  仓库: $DST
  分支: $GIT_BRANCH  Commit: $GIT_COMMIT  Tag: $GIT_TAG
  时间: $(date)
  工具: PetAcceptor（AppKit GUI）+ 自动 launch 检测
  本次测试: 候选 A 启动 + 候选 B 启动 → 自动收集 result JSON → CSV/TXT

HEAD

# ===========================================================================
# 阶段 1: 候选 A
# ===========================================================================
echo "==========================================" | tee -a "$TXT"
echo " 阶段 1/2: 候选 A（AppKit + Objective-C）" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"
echo "操作说明：" | tee -a "$TXT"
echo " 1. PetCandidateA.app 应该自动启动在桌面 (600, 600) 位置" | tee -a "$TXT"
echo " 2. 会出现 PetAcceptor 图形验收窗口（7 项 + 1 项单屏固定 disabled）" | tee -a "$TXT"
echo " 3. 鼠标点击 Pass/Fail/无法测试 → 下一项；点 ■ 结束测试" | tee -a "$TXT"
echo "" | tee -a "$TXT"

A_RESULT=$(bash "$DST/one_click_test/run_pet_acceptor_a.sh" 2>&1 | tail -1)
echo "候选 A result JSON: $A_RESULT" | tee -a "$TXT"

# 写 CSV (1 行)
if [ -n "$A_RESULT" ] && [ -f "$A_RESULT" ]; then
    python3 "$DST/one_click_test/csv_builder.py" "$A_RESULT" "$CSV"
    echo "候选 A 数据写入 CSV" | tee -a "$TXT"
else
    echo "候选 A result 缺失，写入 NOT_TESTED 占位" | tee -a "$TXT"
    cat > "$DST/evidence/acceptor_runs/missing_a_$(date +%H%M%S).json" <<JSON
{"candidate":"candidate_a","version":"V0.0","commit":"$GIT_COMMIT","bundle_id":"com.test.petA","tested_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","overall":"NOT_TESTED","counts_pass":0,"counts_fail":0,"counts_not_tested":8,"counts_disabled":0,"launch_ok":false,"items":[]}
JSON
    MISSING_A=$(ls "$DST/evidence/acceptor_runs"/missing_a_*.json | tail -1)
    python3 "$DST/one_click_test/csv_builder.py" "$MISSING_A" "$CSV"
fi

# 收集当前结果做 A/B 对比汇总
A_OVERALL=$(python3 -c "
import json
d = json.load(open('$A_RESULT'))
print(d.get('overall', 'NOT_TESTED'))
" 2>/dev/null || echo "NOT_TESTED")
echo "" | tee -a "$TXT"
echo "候选 A overall = $A_OVERALL" | tee -a "$TXT"

# 清理探针
pkill -f "ClickThroughProbe" 2>/dev/null
sleep 1
osascript -e 'tell application "Pet A Test" to quit' 2>/dev/null

# ===========================================================================
# 阶段 2: 候选 B
# ===========================================================================
echo "" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"
echo " 阶段 2/2: 候选 B（Electron + PixiJS）" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"

B_RESULT=$(bash "$DST/one_click_test/run_pet_acceptor_b.sh" 2>&1 | tail -1)
echo "候选 B result JSON: $B_RESULT" | tee -a "$TXT"

if [ -n "$B_RESULT" ] && [ -f "$B_RESULT" ]; then
    python3 "$DST/one_click_test/csv_builder.py" "$B_RESULT" "$CSV"
else
    MISSING_B="$DST/evidence/acceptor_runs/missing_b_$(date +%H%M%S).json"
    cat > "$MISSING_B" <<JSON
{"candidate":"candidate_b","version":"V0.0","commit":"$GIT_COMMIT","bundle_id":"com.test.petB","tested_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","overall":"NOT_TESTED","counts_pass":0,"counts_fail":0,"counts_not_tested":8,"counts_disabled":0,"launch_ok":false,"items":[]}
JSON
    python3 "$DST/one_click_test/csv_builder.py" "$MISSING_B" "$CSV"
fi

B_OVERALL=$(python3 -c "
import json
d = json.load(open('$B_RESULT'))
print(d.get('overall', 'NOT_TESTED'))
" 2>/dev/null || echo "NOT_TESTED")

pkill -f "ClickThroughProbe" 2>/dev/null
sleep 1
pkill -f "Electron.*candidates/candidate_b" 2>/dev/null
sleep 1

# ===========================================================================
# 阶段 3: 校验 + 汇总
# ===========================================================================
echo "" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"
echo " CSV 字段数 + 状态枚举校验" | tee -a "$TXT"
echo "==========================================" | tee -a "$TXT"

VALIDATE=$(python3 "$DST/one_click_test/csv_builder.py" "$A_RESULT" "$CSV" --validate 2>&1)
if [ -z "$VALIDATE" ]; then
    echo "✓ CSV schema 严格 19 字段" | tee -a "$TXT"
else
    echo "✗ CSV schema 错误: $VALIDATE" | tee -a "$TXT"
fi

# 中间汇总
{
    echo ""
    echo "=========================================="
    echo " 最终汇总（机器可读 CSV: $CSV）"
    echo "=========================================="
    cat "$CSV"
    echo ""
    echo "=========================================="
    echo " A/B 对比"
    echo "=========================================="
    printf "%-15s %-12s\n" "CANDIDATE" "OVERALL"
    printf "%-15s %-12s\n" "candidate_a" "$A_OVERALL"
    printf "%-15s %-12s\n" "candidate_b" "$B_OVERALL"
} | tee -a "$TXT"

echo ""
echo "=========================================="
echo " 验证完成。证据文件："
echo "   CSV: $CSV"
echo "   TXT: $TXT"
echo "   原始 result JSON: $DST/evidence/acceptor_runs/"
echo "=========================================="
