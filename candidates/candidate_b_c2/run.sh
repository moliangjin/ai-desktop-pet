#!/bin/bash
# Run candidate B-C2 (R141 自主行为桌宠) for N seconds (default 60).
# 正式模式: 自然速度, 正式状态机参数, 不进入测试模式.
set -euo pipefail
cd "$(dirname "$0")"
CAND="$(pwd)"
ROOT="$(cd ../.. && pwd)"
ELECTRON="$(cd ../candidate_b_electronpixir && pwd)/node_modules/.bin/electron"
MANIFEST="$CAND/assets/character_R141_manifest.json"
OUT="$ROOT/evidence/perf_samples/candidate_b_r141_perf.csv"
LOG="$ROOT/evidence/build_logs/candidate_b_r141_run.log"
SECS=${1:-60}
FAST=${2:-off}
mkdir -p "$(dirname "$OUT")" "$(dirname "$LOG")"

EXTRA=""
if [ "$FAST" = "fast" ]; then EXTRA="--acceptance"; fi

exec "$ELECTRON" "$CAND/src/main.js" \
    --manifest "$MANIFEST" \
    --mode compact --x 400 --y 300 \
    --perf-out "$OUT" \
    $EXTRA \
    --quit-after "$SECS" \
    >> "$LOG" 2>&1
