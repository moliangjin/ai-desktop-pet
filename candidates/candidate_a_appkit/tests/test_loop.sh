#!/bin/bash
# T08 part: 20× clean start/stop, verify no zombie processes.
set -euo pipefail
EXT="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/candidates/candidate_a_appkit"
ROOT="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
LOGDIR="$ROOT/evidence/build_logs/loop"
mkdir -p "$LOGDIR"

PASS=0
FAIL=0
for i in $(seq 1 20); do
    LOG="$LOGDIR/iter_$(printf %02d $i).log"
    "$EXT/build/PetCandidateA" \
        --manifest "$ROOT/assets/prototype_chibi/manifest.json" \
        --size 256 --x 600 --y 600 \
        --perf-out "$ROOT/evidence/perf_samples/loop_$i.csv" \
        --quit-after 1 > "$LOG" 2>&1 || FAIL=$((FAIL+1))
    if grep -q "terminating cleanly" "$LOG" && ! grep -q "FATAL" "$LOG"; then
        PASS=$((PASS+1))
    else
        FAIL=$((FAIL+1))
        echo "  iter $i log:"; tail -5 "$LOG" | sed 's/^/    /'
    fi
done

# Verify no zombies (PetCandidateA processes should be 0 right now)
sleep 1
ZOMBIES=$(pgrep -f PetCandidateA | wc -l | tr -d ' ')

echo "[T08 loop] pass=$PASS fail=$FAIL zombies=$ZOMBIES"
if [ "$FAIL" -eq 0 ] && [ "$ZOMBIES" -eq 0 ]; then
    echo "[T08] PASS — 20/20 clean exits, no zombie processes."
    exit 0
else
    echo "[T08] FAIL — $FAIL iterations failed, $ZOMBIES zombies remain."
    exit 1
fi
