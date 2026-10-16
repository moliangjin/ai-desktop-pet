#!/bin/bash
# Run candidate B (Electron + PixiJS) for N seconds (default 6).
set -euo pipefail
ROOT="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
EXT="$ROOT/candidates/candidate_b_electronpixir"
MANIFEST="$ROOT/assets/prototype_chibi/manifest.json"
OUT="$ROOT/evidence/perf_samples/candidate_b_perf_run.csv"
LOG="$ROOT/evidence/build_logs/candidate_b_run_user.log"
SECS=${1:-6}
mkdir -p "$(dirname "$OUT")" "$(dirname "$LOG")"
cd "$EXT"
exec ./node_modules/.bin/electron src/main.js \
    --manifest "$MANIFEST" \
    --size 256 --x 600 --y 600 \
    --perf-out "$OUT" \
    --quit-after "$SECS"
