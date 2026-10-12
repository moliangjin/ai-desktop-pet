#!/bin/bash
# T08 part: missing-asset recovery.
# Run candidate A against a manifest pointing at non-existent frames.
# Engine must continue without crashing and report failures.
set -euo pipefail
EXT="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/candidates/candidate_a_appkit"
ROOT="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
TMP="$ROOT/evidence/test_t08_missing"

mkdir -p "$TMP"
DST="$ROOT/assets/prototype_chibi/manifest_t08_missing_test.json"
python3 - "$ROOT/assets/prototype_chibi/manifest.json" "$DST" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
m = json.load(open(src))
m['actions']['idle']['frames'] = [
    "animations/missing/000.png",
    "animations/missing/001.png",
    "animations/idle/000.png",  # one valid frame so action still has >0 frames
]
m['actions']['walk']['frames'] = [
    "animations/walk/000.png",
]
m['actions']['jump']['frames'] = ["animations/jump/missing.png"]
m['actions']['drag']['frames'] = ["animations/drag/missing.png"]
json.dump(m, open(dst, 'w'), indent=2)
PY
TMP_MANIFEST="$DST"

LOG="$ROOT/evidence/build_logs/candidate_a_t08_missing.log"
PERF="$ROOT/evidence/perf_samples/candidate_a_t08_missing.csv"

set +e
"$EXT/build/PetCandidateA" \
    --manifest "$TMP_MANIFEST" \
    --size 256 --x 600 --y 600 \
    --perf-out "$PERF" \
    --quit-after 2 > "$LOG" 2>&1
RC=$?
set -e

rm -f "$TMP_MANIFEST"

if [ "$RC" -eq 0 ] && grep -q "load fail" "$LOG" && grep -q "terminating cleanly" "$LOG"; then
    echo "[T08 missing] PASS — engine reported missing files and exited cleanly."
    exit 0
fi
echo "[T08 missing] FAIL — see $LOG"
exit 1
