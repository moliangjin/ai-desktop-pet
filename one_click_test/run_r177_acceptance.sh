#!/bin/bash
# R177 Mac 一键验收入口 (纯离线体验增强: 心情系统 / 控制菜单 / 设置面板 / 本地保存)
#
# 用法 (三种都行):
#   1) 在 Finder 里双击 "R177_验收入口.command"
#   2) 终端里执行: bash one_click_test/run_r177_acceptance.sh
#   3) 终端里执行: bash one_click_test/run_r177_acceptance.sh --only-auto   (只跑自动化, 不启动桌宠)
#
# 本脚本分三段:
#   [1/3] 自动化验收 —— 单元测试 (46 项新增) + 真实 Electron 运行时验证
#   [2/3] 启动真实桌宠 —— 请在桌面上右键角色, 逐条走下面的清单
#   [3/3] 人工确认清单 —— 看完把每条勾掉; 有问题直接告诉我
#
# 本轮**不含任何联网/AI 功能**, 所有设置与心情只写在这台电脑上。

set -u
cd "$(dirname "$0")"
REPO="$(cd .. && pwd)"
CAND="$REPO/candidates/candidate_b_c2"
ELECTRON="$REPO/candidates/candidate_b_electronpixir/node_modules/.bin/electron"
MANIFEST="$CAND/assets/character_R141_manifest.json"
LOG_DIR="$REPO/evidence/build_logs"
mkdir -p "$LOG_DIR"

ONLY_AUTO=0
for a in "$@"; do
  case "$a" in
    --only-auto) ONLY_AUTO=1 ;;
  esac
done

echo "=========================================================="
echo " R177 一键验收  (纯离线: 心情 / 控制菜单 / 设置面板 / 本地保存)"
echo " 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================================="

# ---------- [1/3] 自动化验收 ----------
echo ""
echo "[1/3] 自动化验收"
echo "----------------------------------------------------------"

echo "  · 单元测试 (新增 R177 三组)"
UNIT_FAIL=0
for t in r177_mood_engine r177_settings_store r177_menu_settings; do
  if node "$CAND/tests/$t.test.js" > "$LOG_DIR/r177_$t.log" 2>&1; then
    echo "      ✅ $t — $(tail -1 "$LOG_DIR/r177_$t.log")"
  else
    echo "      ❌ $t — 见 $LOG_DIR/r177_$t.log"
    UNIT_FAIL=1
  fi
done

echo "  · 真实 Electron 运行时验证 (菜单命令 / 设置落盘 / 重启恢复)"
if python3 "$CAND/100_R177_runtime_verify.py" > "$LOG_DIR/r177_runtime_verify.log" 2>&1; then
  echo "      ✅ $(tail -3 "$LOG_DIR/r177_runtime_verify.log" | head -1)"
  grep -E "PASS /" "$LOG_DIR/r177_runtime_verify.log" | tail -1 | sed 's/^/      /'
else
  echo "      ❌ 运行时验证未通过 — 见 $LOG_DIR/r177_runtime_verify.log"
  grep -E "^  - " "$LOG_DIR/r177_runtime_verify.log" | head -10 | sed 's/^/      /'
fi

if [ "$UNIT_FAIL" != "0" ]; then
  echo ""
  echo "⚠️  单元测试未通过, 已跳过桌宠启动 (避免给你看一个已知有问题的版本)。"
  exit 1
fi

if [ "$ONLY_AUTO" = "1" ]; then
  echo ""
  echo "只跑自动化模式结束。"
  exit 0
fi

# ---------- [2/3] 启动真实桌宠 ----------
echo ""
echo "[2/3] 启动真实桌宠 (窗口会出现在桌面上)"
echo "----------------------------------------------------------"
echo "  在桌面上找到角色, **右键点一下** → 会出现控制菜单:"
echo "    · 心情：xxx        (只读信息)"
echo "    · 睡觉 / 醒来 / 坐沙发休息 / 电脑办公 / 吃水果 / 随机可爱动作"
echo "    · 设置…           (打开设置面板)"
echo "    · 退出桌宠"
echo ""
echo "  提示: 左键拖动仍然可以移动她 (R113 拖拽核心保留)。"
echo "  看完后按 Ctrl+C 结束, 或用菜单里的\"退出桌宠\"。"
echo "----------------------------------------------------------"

"$ELECTRON" src/main.js \
  --manifest "$MANIFEST" \
  --mode compact --x 600 --y 300 \
  --perf-out "$LOG_DIR/r177_mac_accept_perf.csv" \
  --quit-after 900 2>&1 | tee "$LOG_DIR/r177_mac_accept.log"

# ---------- [3/3] 人工确认清单 ----------
echo ""
echo "[3/3] 人工确认清单 (在桌面上逐条试一遍)"
echo "----------------------------------------------------------"
cat <<'EOF'
  [ ] 1. 右键角色 → 菜单弹出, 里面只有 6 个动作 + 设置 + 退出 (没有调试项)
  [ ] 2. 菜单里点"电脑办公" → 她真的坐到电脑前办公 (不是弹一张图)
  [ ] 3. 菜单里点"吃水果" → 她真的拿出水果吃
  [ ] 4. 菜单里点"睡觉" → 她躺下、床和月亮出现
  [ ] 5. 菜单里点"醒来" → 她醒来回到站立
  [ ] 6. 菜单里点"坐沙发休息" → 沙发出现、她坐下
  [ ] 7. 菜单里点"随机可爱动作" → 她做一个站立小动作
  [ ] 8. 菜单里点"设置…" → 独立设置面板打开 (不遮挡桌宠)
  [ ] 9. 设置面板里拖"桌宠大小" → 桌宠立刻变大/变小, 位置不跳
  [ ]10. 设置面板里改"自主活动频率" → 她之后自己动的频率变了
  [ ]11. 设置面板里改"睡眠频率" → 她之后困/睡的频率变了
  [ ]12. 关掉"点击反馈" → 左键点她不再有动作回应 (睡眠中点击仍能唤醒)
  [ ]13. 重新打开"点击反馈" → 恢复
  [ ]14. "开机自动启动"开关可用 (macOS 会写入登录项, 去掉勾选即恢复)
  [ ]15. 完全退出程序再打开 → 大小/频率/点击反馈开关都还在, 心情也接着上次
  [ ]16. 右键没有把角色拖走 (左键拖动仍然正常)
EOF
echo ""
echo "有任意一条不通过, 把现象告诉我即可 (截图最好)。"
echo "完整日志: $LOG_DIR/r177_mac_accept.log"
