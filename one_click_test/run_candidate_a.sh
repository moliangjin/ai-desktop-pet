#!/bin/bash
# 候选 A 一键启动（构建好的二进制）— 真前台用户双击 .command 调用此脚本
# V0.0 R41: 启动前 codesign verify + 自动重签
# V0.0 R43:
#   1. 把 PetCandidateA 的 NSLog 输出全部重定向到独立 log 文件（避免淹没
#      .command 的 read prompt）。
#   2. 移除之前 R41 的 `exec 2> >(tee -a ... >&2)` process substitution — 在
#      macOS bash 4 上有时会与 .command 的 heredoc/read 冲突导致 read 卡住。
set -e
DST="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
BUNDLE="$DST/_app_bundle/PetCandidateA.app"
LOG="$DST/evidence/build_logs/candidate_a_user_click.log"
PERF="$DST/evidence/build_logs/candidate_a_r41_launch.log"
PERF_CSV="$DST/evidence/perf_samples/candidate_a_user_click.csv"
RUNTIME_LOG="$DST/evidence/build_logs/candidate_a_runtime.log"
mkdir -p "$(dirname "$LOG")" "$(dirname "$PERF")" "$(dirname "$PERF_CSV")" "$(dirname "$RUNTIME_LOG")"

{
    echo "=========================================="
    echo "[候选 A 启动] 时间: $(date)"
    echo "[候选 A 启动] 路径: $BUNDLE"
} > "$LOG" 2>&1

# === R41: 启动前 codesign 验证 ===
echo "[R41] codesign --verify $BUNDLE"
VERIFY_OUT=$(codesign --verify --deep --strict --verbose=2 "$BUNDLE" 2>&1) || {
    echo "[R41] 签名验证失败: $VERIFY_OUT"
    echo "[R41] 自动重新 adhoc 签名..."
    codesign --force --deep --sign - "$BUNDLE" 2>&1
    codesign --verify --deep --strict --verbose=2 "$BUNDLE" 2>&1
}
codesign -dvv "$BUNDLE" 2>&1 | head -12

# 杀旧实例
pkill -f "PetCandidateA" 2>/dev/null || true
sleep 1

# === R43: 重定向候选 A 全部输出到独立 runtime.log，避免淹没 .command 的 prompt ===
R43_LOG_HEAD="# R43 candidate_a runtime log, started $(date)"
touch "$RUNTIME_LOG"
echo "$R43_LOG_HEAD" > "$RUNTIME_LOG"

# 直接调用二进制并把 stdout+stderr 都接到 RUNTIME_LOG
# .command 进程只需要 PID，不需要读它的输出
# R43: 同时把 stdin 重定向到 /dev/null 防止候选 A 偷走 .command 的 read 字符
(
    exec "$BUNDLE/Contents/MacOS/PetCandidateA" \
        --manifest "$DST/assets/prototype_chibi/manifest.json" \
        --size 256 --x 600 --y 600 \
        --perf-out "$PERF_CSV" \
        --quit-after 600 \
        < /dev/null \
        >> "$RUNTIME_LOG" 2>&1
) &
A_PID=$!

# 把 PID 输出到 stdout 给 .command 用 pgrep 检测（这是唯一需要给 .command 的信息）
echo "CANDIDATE_A_PID=$A_PID"
echo "[候选 A] PID=$A_PID 已启动；stdout/stderr -> $RUNTIME_LOG"
echo "[候选 A] 时间: $(date)" >> "$LOG"
