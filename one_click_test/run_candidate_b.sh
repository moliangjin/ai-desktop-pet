#!/bin/bash
# 候选 B 一键启动（Electron）— 真前台用户双击 .command 调用此脚本
set -e
DST="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
EXT_B="$DST/candidates/candidate_b_electronpixir"
LOG="$DST/evidence/build_logs/candidate_b_user_click.log"
PERF="$DST/evidence/perf_samples/candidate_b_user_click.csv"
mkdir -p "$(dirname "$LOG")" "$(dirname "$PERF")"

echo "[候选 B 启动] 时间: $(date)" > "$LOG"
cd "$EXT_B"

# 用 macOS 标准的 open 命令启动 .app
# 把 Electron 启动成 .app bundle：electron 提供 --app 参数
# 这里直接用 open -a 启动 .app（自动 dock 图标、菜单栏）
# 但我们没有 .app bundle，所以用 open 启动一个 Electron 进程
nohup ./node_modules/.bin/electron src/main.js \
  --manifest "$DST/assets/prototype_chibi/manifest.json" \
  --size 256 --x 800 --y 400 \
  --perf-out "$PERF" \
  --quit-after 30 > "$LOG" 2>&1 &
APP_PID=$!
echo "[候选 B pid]: $APP_PID" >> "$LOG"

# 等待 30 秒（候选 B 30 秒后自动 quit-after）
sleep 30
# 如果还没退出就强制结束
if kill -0 $APP_PID 2>/dev/null; then
    kill $APP_PID
fi
wait $APP_PID 2>/dev/null || true
echo "[候选 B 退出] 时间: $(date)" >> "$LOG"
echo ""
echo "=== 候选 B 完成 ==="
echo "日志: $LOG"
echo "性能 CSV: $PERF"
