#!/usr/bin/env python3
"""R144: 校验 R113 真机验证过的拖拽核心代码是否被逐字改动.

对比对象: R141 交付 commit (6e35231) 与当前工作区的 src/main.js.
判定范围: R113 拖拽核心 —— performDragMove / startDragPolling / stopDragPolling /
          stopDrag / window-drag-start / window-drag-move / window-drag-end /
          window-drag-cancel / browser-window-blur 兜底清理.
不判定范围: R141 新增的行为协调层 (behavior-drag-state) 与 R144 的窗口坐标复核
          (moveWindowBy) —— 这两处按 R144 要求本来就要改.

退出码 0 = 核心逐字未改; 1 = 有改动 (输出 diff 摘要).
"""

import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(CAND, "..", ".."))
REL = "candidates/candidate_b_c2/src/main.js"
BASE_COMMIT = "6e35231"

BLOCKS = [
    "function performDragMove()",
    "function startDragPolling()",
    "function stopDragPolling()",
    "function stopDrag()",
    "ipcMain.handle('window-drag-start'",
    "ipcMain.on('window-drag-move'",
    "ipcMain.on('window-drag-end'",
    "ipcMain.on('window-drag-cancel'",
    "app.on('browser-window-blur'",
]


def extract_block(text, marker):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if marker in line:
            start = i
            break
    if start is None:
        return None
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("}"):
            end = j
            break
    if end is None:
        return None
    return "\n".join(lines[start:end + 1])


def main():
    try:
        base = subprocess.run(
            ["git", "-C", ROOT, "show", f"{BASE_COMMIT}:{REL}"],
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        print(f"无法读取基线 commit {BASE_COMMIT}: {e.stderr.strip()}")
        return 2
    with open(os.path.join(CAND, "src", "main.js"), encoding="utf-8") as f:
        cur = f.read()

    changed = []
    missing = []
    checked = 0
    for marker in BLOCKS:
        b = extract_block(base, marker)
        c = extract_block(cur, marker)
        if b is None or c is None:
            missing.append(marker)
            continue
        checked += 1
        if b != c:
            changed.append(marker)
    if missing:
        print(f"抽取失败: {missing}")
        return 2
    if changed:
        print(f"R113 拖拽核心被改动: {changed}")
        for marker in changed:
            b = extract_block(base, marker)
            c = extract_block(cur, marker)
            import difflib
            d = list(difflib.unified_diff(b.splitlines(), c.splitlines(), lineterm="", n=1))
            for line in d[:20]:
                print("   ", line)
        return 1
    print(f"R113 拖拽核心 {checked}/{len(BLOCKS)} 个区块逐字未改 (对比 {BASE_COMMIT})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
