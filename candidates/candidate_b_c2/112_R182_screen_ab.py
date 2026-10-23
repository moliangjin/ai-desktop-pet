#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R182: 桌宠桌面启动器的**客观屏幕取证**。

为什么需要这个脚本:
  macOS 的 `screencapture` **抓不到透明 Electron 叠层**(Pixi 画布走 GPU layer),
  所以"截图里没有桌宠"≠"桌宠没显示"。本脚本改用 **A/B 对照**:
    A = 桌宠运行中时, 按 WindowServer 报告的真实窗口坐标截取该区域
    B = 关掉桌宠后, 截取**完全相同**的区域
  若 A ≠ B ⇒ 桌宠确实叠加显示在屏幕上 (差值即为角色像素)。

用法:
    python3 112_R182_screen_ab.py capture     # 截 A (桌宠运行中)
    python3 112_R182_screen_ab.py compare     # 截 B 并与 A 比对
"""
import subprocess
import sys

import numpy as np
from PIL import Image

SHOT_A = '/tmp/r182_screen_A.png'
SHOT_B = '/tmp/r182_screen_B.png'
META_A = '/tmp/r182_screen_A.json'


def electron_window():
    """从 WindowServer 拿 Electron 窗口的真实坐标。"""
    import Quartz
    wl = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID)
    for w in wl:
        if str(w.get('kCGWindowOwnerName', '')) == 'Electron':
            b = w.get('kCGWindowBounds')
            return {
                'id': w.get('kCGWindowNumber'),
                'x': int(b['X']), 'y': int(b['Y']),
                'w': int(b['Width']), 'h': int(b['Height']),
                'onscreen': bool(w.get('kCGWindowIsOnscreen')),
                'alpha': w.get('kCGWindowAlpha'),
                'layer': w.get('kCGWindowLayer'),
            }
    return None


def grab(rect, out):
    subprocess.run(['screencapture', '-x', '-R',
                    f"{rect['x']},{rect['y']},{rect['w']},{rect['h']}", out], check=False)
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'capture'

    if mode == 'compare':
        # 关掉桌宠后窗口已经没了 ⇒ 直接用 A 阶段存下的坐标截 B
        import json
        import os
        if not os.path.exists(SHOT_A) or not os.path.exists(META_A):
            print('[ab] 缺 A')
            return 2
        win_a = json.load(open(META_A))
        grab(win_a, SHOT_B)
        a = np.asarray(Image.open(SHOT_A).convert('RGB')).astype(np.int16)
        b = np.asarray(Image.open(SHOT_B).convert('RGB')).astype(np.int16)
        if a.shape != b.shape:
            print(f'[ab] 尺寸不一致 {a.shape} vs {b.shape}')
            return 1
        diff = np.abs(a - b).sum(axis=2)
        changed = int((diff > 12).sum())
        total = diff.size
        print(f'[ab] A={SHOT_A} B={SHOT_B} 尺寸 {a.shape}')
        print(f'[ab] 变化像素 {changed}/{total} ({changed / total * 100:.2f}%)  最大通道差 {int(diff.max())}')
        print('[ab] 判定:', '桌宠确实显示在屏幕上 (A≠B)' if changed > total * 0.005 else 'A≈B, 未检出叠加内容')
        return 0 if changed > total * 0.005 else 1

    win = electron_window()
    if not win:
        print('[ab] 没有找到 Electron 窗口')
        return 2
    print('[ab] 窗口:', win)

    if mode == 'capture':
        grab(win, SHOT_A)
        import json
        with open(META_A, 'w') as f:
            json.dump(win, f)
        im = Image.open(SHOT_A).convert('RGB')
        print(f'[ab] 已截 A -> {SHOT_A} {im.size}')
        return 0
    return 2


if __name__ == '__main__':
    import os
    sys.exit(main())
