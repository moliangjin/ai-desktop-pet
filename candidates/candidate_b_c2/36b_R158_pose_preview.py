#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R158 手臂骨架 — 摆姿迭代脚本 (看图调参用)。

直接指定三个关节角 (肩/肘/腕), 增量角, 正=屏幕顺时针。
  画面左臂向上外抬 → 肩角用**负角** (-45 ~ -130)
  画面右臂向上外抬 → 肩角用**正角** (+45 ~ +130)

输出 /tmp/r158_iter.png —— 全部按真实显示尺度 (compact 200x240) 放大 3 倍。
"""
import os
import sys
import importlib.util

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("rig", os.path.join(HERE, '36_R158_arm_rig.py'))
rig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rig)

BASE = os.path.join(HERE, 'assets', 'character_R138', 'idle', 'idle_00_base.png')

CANVAS_W, CANVAS_H = 200, 240
SCALE = 0.196319
ANCHOR_X, ANCHOR_Y = 0.5, 0.9
GROUND_Y = CANVAS_H - 4
TEX = 1024
H_TEX, W_TEX = 1024, 1024
BOTTOM = 987


def to_screen(arr, scale=SCALE):
    H, W = arr.shape[:2]
    ys, xs = np.mgrid[0:H, 0:W]
    sx = np.round(CANVAS_W / 2 + scale * (xs - ANCHOR_X * TEX)).astype(int)
    sy = np.round(GROUND_Y + scale * (ys - BOTTOM)).astype(int)
    ok = (sx >= 0) & (sx < CANVAS_W) & (sy >= 0) & (sy < CANVAS_H)
    out = np.zeros((CANVAS_H, CANVAS_W, 4), np.int32)
    out[:, :, 3] = 255
    out[:, :, 0:3] = 24
    oy, ox = sy[ok], sx[ok]
    oa = arr[ys[ok], xs[ok], :].astype(np.float32)
    sa = oa[:, 3:4] / 255.0
    for c in range(3):
        out[oy, ox, c] = (24 * (1 - sa[:, 0]) + oa[:, c] * sa[:, 0]).astype(np.int32)
    out[oy, ox, 3] = 255
    return out


def render_pose(a, rigL, rigR, poses, fill_ratio=None):
    body = a.copy()
    layers = []
    for side, ang in poses.items():
        if ang is None:
            continue
        r = rigL if side == 'L' else rigR
        b, fill = rig.restore_body(body, r['arm'], side)
        body = b
        up, fo, hd = rig.pose_arm(a, r, ang)
        layers += [up, fo, hd]
    return rig.compose(body, layers)


def main():
    a = rig.to_np(rig.load_rgba(BASE))
    rigL = rig.build_arm(a, 'L')
    rigR = rig.build_arm(a, 'R')

    cases = [
        ('原图', {}),
        ('L肩-60', {'L': (-60, 0, 0)}),
        ('L肩-90', {'L': (-90, 0, 0)}),
        ('L肩-120', {'L': (-120, 0, 0)}),
        ('L肩-120肘-25腕20', {'L': (-120, -25, 20)}),
        ('R肩+120', {'R': (120, 0, 0)}),
        ('双肩∓120', {'L': (-120, 0, 0), 'R': (120, 0, 0)}),
        ('双手胸前', {'L': (-40, -55, -15), 'R': (40, 55, 15)}),
    ]
    cols = 2
    rows = []
    X0, Y0, X1, Y1 = 300, 330, 520, 690
    for title, poses in cases:
        out = render_pose(a, rigL, rigR, poses)
        scr = to_screen(out)
        scr_big = np.array(Image.fromarray(scr.astype(np.uint8)).resize(
            (CANVAS_W * 3, CANVAS_H * 3), Image.LANCZOS))
        # 纹理尺度躯干特写 (看衣身还原质量)
        bp = np.zeros((H_TEX, W_TEX, 4), np.int32)
        bp[:, :, 3] = 255
        bp[:, :, 0:3] = 24
        al = out[:, :, 3:4].astype(np.float32) / 255.0
        for c in range(3):
            bp[:, :, c] = (24 * (1 - al[:, :, 0]) + out[:, :, c] * al[:, :, 0]).astype(np.int32)
        crop = np.array(Image.fromarray(bp[Y0:Y1, X0:X1].astype(np.uint8)).resize(
            ((X1 - X0) * 2, (Y1 - Y0) * 2), Image.LANCZOS))
        rows.append((title, scr_big, crop))

    sw, sh = rows[0][1].shape[1], rows[0][1].shape[0]
    cw2, ch2 = rows[0][2].shape[1], rows[0][2].shape[0]
    nrows = (len(rows) + cols - 1) // cols
    rowh = max(sh, ch2)
    cellw = sw + cw2 + 24
    sheet = np.zeros((nrows * (rowh + 16), cols * cellw, 4), np.int32)
    sheet[:, :, 3] = 255
    sheet[:, :, 0:3] = 40
    for i, (title, scr, crop) in enumerate(rows):
        r0, c0 = (i // cols) * (rowh + 16), (i % cols) * cellw
        sheet[r0:r0 + sh, c0:c0 + sw] = scr
        sheet[r0:r0 + ch2, c0 + sw + 12:c0 + sw + 12 + cw2] = crop
    Image.fromarray(sheet.astype(np.uint8)).convert('RGB').save('/tmp/r158_iter.png')
    print('saved', sheet.shape)
    for t, _, _c in rows:
        print(' ', t)


if __name__ == '__main__':
    main()
