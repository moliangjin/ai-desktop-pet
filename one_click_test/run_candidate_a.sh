#!/bin/bash
# 候选 A 一键启动（构建好的二进制）— 真前台用户双击 .command 调用此脚本
# V0.0 第 38 轮修订：移除内部 quit-after，由外层 .command 在用户测试完成后 kill
# V0.0 R41: 启动前 codesign verify + 自动重签，避免 macOS Taskgated SIGKILL
set -e
DST="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
BUNDLE="$DST/_app_bundle/PetCandidateA.app"
LOG="$DST/evidence/build_logs/candidate_a_user_click.log"
PERF="$DST/evidence/build_logs/candidate_a_r41_launch.log"
PERF_CSV="$DST/evidence/perf_samples/candidate_a_user_click.csv"
mkdir -p "$(dirname "$LOG")" "$(dirname "$PERF")" "$(dirname "$PERF_CSV")"

exec 2> >(tee -a "$PERF" >&2)
echo "==========================================" | tee -a "$LOG"
echo "[候选 A 启动] 时间: $(date)" | tee -a "$LOG"
echo "[候选 A 启动] 路径: $BUNDLE" | tee -a "$LOG"

# === R41: 启动前 codesign 验证 ===
echo "[R41] codesign --verify $BUNDLE" | tee -a "$LOG"
VERIFY_OUT=$(codesign --verify --deep --strict --verbose=2 "$BUNDLE" 2>&1) || {
    echo "[R41] 签名验证失败: $VERIFY_OUT" | tee -a "$LOG"
    echo "[R41] 自动重新 adhoc 签名..." | tee -a "$LOG"
    codesign --force --deep --sign - "$BUNDLE" 2>&1 | tee -a "$LOG"
    codesign --verify --deep --strict --verbose=2 "$BUNDLE" 2>&1 | tee -a "$LOG"
}
codesign -dvv "$BUNDLE" 2>&1 | head -12 | tee -a "$LOG"

# 杀旧实例
pkill -f "PetCandidateA" 2>/dev/null || true
sleep 1

echo "[候选 A] open -a '$BUNDLE'" | tee -a "$LOG"
open -a "$BUNDLE" --args \
  --manifest "$DST/assets/prototype_chibi/manifest.json" \
  --size 256 --x 600 --y 600 \
  --perf-out "$PERF_CSV" \
  --quit-after 600

echo "[候选 A] open 指令已发；运行时 PID 由 .command 通过 pgrep 检测"
