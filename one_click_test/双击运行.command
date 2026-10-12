#!/bin/bash
# 候选 A 与 B 一键双击启动（中文）
# 准备：
#   1. macOS Sonoma 14.0+ (在 Mac mini M2 14.7.4 上测试过)
#   2. 不要 SSH 远程执行 — 必须在本机前台 Terminal 或 Finder 双击
# 操作：
#   - 双击此文件
#   - 若弹出"无法打开因为来自身份不明的开发者"，系统设置 → 隐私与安全性 → 仍要打开
#   - 选择"候选 A"或"候选 B"，按屏幕提示操作
#   - 每运行 30 秒后会输出日志与性能 CSV 到仓库
# 退出：脚本完成或 Ctrl+C 中断

set +e

DST="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DST" || { echo "FAIL: cannot cd to $DST"; exit 1; }

echo "=========================================="
echo "  AI 桌宠 V0.0 — 双击一键启动"
echo "  路径: $DST"
echo "=========================================="
echo ""
echo "本工具会按顺序执行："
echo "  1) 候选 A（Objective-C + AppKit，30 秒观察窗口）"
echo "  2) 候选 B（Electron + PixiJS，30 秒观察窗口）"
echo ""
echo "建议你在每个候选运行 30 秒内："
echo "  - 用肉眼判断：桌宠是否真的出现在屏幕上？"
echo "  - 用鼠标点击/拖动角色：是否有响应？"
echo "  - 检查菜单栏右上角是否出现 🐾 状态项"
echo ""
echo "是否开始？(y/N)"
read -n 1 -r ans
echo ""
if [[ ! "$ans" =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "=== 阶段 1/2: 候选 A ==="
bash "$DST/one_click_test/run_candidate_a.sh"
RC_A=$?
echo "  候选 A 退出码: $RC_A"

echo ""
echo "=== 阶段 2/2: 候选 B ==="
bash "$DST/one_click_test/run_candidate_b.sh"
RC_B=$?
echo "  候选 B 退出码: $RC_B"

echo ""
echo "=========================================="
echo "  两个候选都已完成 30 秒运行"
echo "=========================================="
echo ""
echo "请你目视确认："
echo "  A) 候选 A 运行时，是否看到桌宠？  [y/n/skip]"
read -n 1 -r visA; echo
echo "  B) 候选 B 运行时，是否看到桌宠？  [y/n/skip]"
read -n 1 -r visB; echo
echo "  C) 候选 A 鼠标点击/拖动响应？       [y/n/skip]"
read -n 1 -r clickA; echo
echo "  D) 候选 B 鼠标点击/拖动响应？       [y/n/skip]"
read -n 1 -r clickB; echo

REPORT="$DST/evidence/build_logs/user_visual_report.txt"
{
    echo "用户肉眼验证结果（V0.0 阶段）"
    echo "时间: $(date)"
    echo ""
    echo "A) 候选 A 桌宠可见: $visA"
    echo "B) 候选 B 桌宠可见: $visB"
    echo "C) 候选 A 鼠标响应: $clickA"
    echo "D) 候选 B 鼠标响应: $clickB"
} > "$REPORT"
echo ""
echo "验证结果已写入: $REPORT"
echo "请将本文件回传给 MiniMax 用于完善 TEST_EVIDENCE_MATRIX.csv"
