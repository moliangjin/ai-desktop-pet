#!/bin/bash
# 候选 A 一键启动（构建好的二进制）— 真前台用户双击 .command 调用此脚本
# V0.0 第 38 轮修订：移除内部 quit-after，由外层 .command 在用户测试完成后 kill
set -e
DST="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
LOG="$DST/evidence/build_logs/candidate_a_user_click.log"
PERF="$DST/evidence/perf_samples/candidate_a_user_click.csv"
mkdir -p "$(dirname "$LOG")" "$(dirname "$PERF")"

echo "[候选 A 启动] 时间: $(date)" > "$LOG"
echo "[候选 A 启动] 路径: $DST/_app_bundle/PetCandidateA.app" >> "$LOG"
pkill -f "PetCandidateA" 2>/dev/null || true
sleep 1
open -a "$DST/_app_bundle/PetCandidateA.app" --args \
  --manifest "$DST/assets/prototype_chibi/manifest.json" \
  --size 256 --x 600 --y 600 \
  --perf-out "$PERF" \
  --quit-after 600
