#!/bin/bash
# 候选 A 一键启动（构建好的二进制）— 真前台用户双击 .command 调用此脚本
set -e
DST="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
LOG="$DST/evidence/build_logs/candidate_a_user_click.log"
PERF="$DST/evidence/perf_samples/candidate_a_user_click.csv"
mkdir -p "$(dirname "$LOG")" "$(dirname "$PERF")"

echo "[候选 A 启动] 时间: $(date)" > "$LOG"
echo "[候选 A 启动] 路径: $DST/_app_bundle/PetCandidateA.app" >> "$LOG"

# 移除可能存在的旧进程
pkill -f "PetCandidateA" 2>/dev/null || true
sleep 1

# 用 macOS 标准的 open 命令启动 .app（这样 Dock 图标、菜单栏都会出现）
open -a "$DST/_app_bundle/PetCandidateA.app" --args \
  --manifest "$DST/assets/prototype_chibi/manifest.json" \
  --size 256 --x 800 --y 400 \
  --perf-out "$PERF"
# 30 秒后自动退出（供用户在此期间观察 + 截图）
sleep 30
# 优雅退出
osascript -e 'tell application "Pet A Test" to quit' 2>/dev/null || \
  pkill -f PetCandidateA
sleep 1
echo "[候选 A 退出] 时间: $(date)" >> "$LOG"
echo ""
echo "=== 候选 A 完成 ==="
echo "日志: $LOG"
echo "性能 CSV: $PERF"
echo "请到 GitHub 仓库查看 TEST_EVIDENCE_MATRIX.csv 是否需要更新你的肉眼判断"
