#!/bin/bash
# T09: Resource interface test.
# Replace manifest actions' frame list and verify engine still loads + plays
# without source changes.
set -euo pipefail
ROOT="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
SRC="$ROOT/assets/prototype_chibi"

# Place the replacement manifest next to the assets directory so its
# relative paths (animations/walk/000.png) resolve correctly.
DST="$SRC/manifest_t09_test.json"
python3 - "$SRC/manifest.json" "$DST" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
m = json.load(open(src))
# swap: idle now points at walk's frames; walk points at idle's
m['actions']['idle']['frames'] = [
    "animations/walk/000.png",
    "animations/walk/002.png",
    "animations/walk/004.png",
    "animations/walk/006.png",
]
m['actions']['walk']['frames'] = [
    "animations/idle/000.png",
    "animations/idle/001.png",
    "animations/idle/002.png",
    "animations/idle/003.png",
    "animations/idle/004.png",
    "animations/idle/005.png",
]
m['actions']['idle']['fps'] = 6
m['actions']['walk']['fps'] = 8
json.dump(m, open(dst, 'w'), indent=2)
print(f"rebuilt manifest -> {dst}")
PY

EXT="$ROOT/candidates/candidate_a_appkit"
LOG="$ROOT/evidence/build_logs/candidate_a_t09.log"
PERF="$ROOT/evidence/perf_samples/candidate_a_t09.csv"

set +e
"$EXT/build/PetCandidateA" \
    --manifest "$DST" \
    --size 256 --x 600 --y 600 \
    --perf-out "$PERF" \
    --quit-after 4 > "$LOG" 2>&1
RC=$?
set -e

# Restore original manifest to keep assets dir clean.
rm -f "$DST"

# Verify both swapped frame lists loaded with their new counts.
if [ "$RC" -eq 0 ] && grep -q "action=idle loaded=4/4" "$LOG" && grep -q "action=walk loaded=6/6" "$LOG"; then
    echo "[T09] PASS — engine loaded swapped frame lists without code change."
    echo "       evidence: $LOG"
    exit 0
fi
echo "[T09] FAIL — manifest swap did not load expected frame counts (rc=$RC)."
echo "       evidence: $LOG"
exit 1
