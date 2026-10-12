#!/bin/bash
# 候选 B 一键启动（Electron）— 真前台用户双击 .command 调用此脚本
# V0.0 第 38 轮修订：不自动退出，由外层 .command 在用户完成测试后 kill
set -e
DST="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
EXT_B="$DST/candidates/candidate_b_electronpixir"
LOG="$DST/evidence/build_logs/candidate_b_user_click.log"
PERF="$DST/evidence/perf_samples/candidate_b_user_click.csv"
mkdir -p "$(dirname "$LOG")" "$(dirname "$PERF")"

echo "[候选 B 启动] 时间: $(date)" > "$LOG"
cd "$EXT_B"
nohup ./node_modules/.bin/electron src/main.js \
  --manifest "$DST/assets/prototype_chibi/manifest.json" \
  --size 256 --x 600 --y 600 \
  --perf-out "$PERF" \
  --quit-after 600 > "$LOG" 2>&1 &
echo $! > /tmp/pet_b_pid_$$
