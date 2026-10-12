#!/bin/bash
# Run candidate A from project root.
# Usage: bash run.sh [seconds]
# Defaults to 5 seconds; pass N to run for N seconds then auto-quit.
set -euo pipefail
cd "$(dirname "$0")"

ROOT="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
MANIFEST="$ROOT/assets/prototype_chibi/manifest.json"
OUT="$ROOT/evidence/perf_samples/candidate_a_perf_run.csv"
LOG="$ROOT/evidence/build_logs/candidate_a_run_user.log"

if [ ! -x ./build/PetCandidateA ]; then
    echo "[run.sh] build first: bash build.sh"
    exit 2
fi

SECS=${1:-5}
mkdir -p "$(dirname "$OUT")" "$(dirname "$LOG")"
exec ./build/PetCandidateA \
    --manifest "$MANIFEST" \
    --size 256 --x 600 --y 600 \
    --perf-out "$OUT" \
    --quit-after "$SECS"
