#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 14: 肩区回填方案 A/B 对比 (200x240 真实尺寸)。

A = 现状: 平涂衣身色, 半径 46
B = 改为贴回底图原始像素 (含青色肩章), 半径 46
C = 平涂衣身色, 半径 32
"""
import importlib.util
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE


def _mod(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


rig = _mod('rig', os.path.join(CAND, '36_R158_arm_rig.py'))
bake = _mod('bake', os.path.join(CAND, '37_R158_action_bake.py'))
bn = rig.to_np(rig.load_rgba(os.path.join(CAND, 'assets/character_R138/idle/idle_00_base.png')))
rigL = rig.build_arm(bn, 'L')
rigR = rig.build_arm(bn, 'R')


def render(poses, mode, radius):
    body = bn.copy()
    layers = []
    for side in ('L', 'R'):
        r = rigL if side == 'L' else rigR
        ang = poses.get(side) or (0, 0, 0)
        fill = r['upper'] & rig.disc(bn.shape[:2], r['S'], radius)
        b, _ = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'], fill_mask=fill)
        if mode == 'B':
            # 肩区回填改为贴回底图原始像素 (含青色肩章)
            b = b.copy()
            for y in range(b.shape[0]):
                xs = np.nonzero(fill[y])[0]
                if len(xs) == 0:
                    continue
                lo, hi = int(xs.min()), int(xs.max())
                b[y, lo:hi + 1] = bn[y, lo:hi + 1]
        body = b
        up, fo, hd, ball = rig.pose_arm(bn, r, ang)
        layers += [up, fo, hd, ball]
    return rig.compose(body, layers)


def small(arr, w=200, h=240, zoom=2):
    im = rig.to_im(arr).resize((w, h), Image.LANCZOS)
    im = im.resize((w * zoom, h * zoom), Image.LANCZOS)
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    d = ImageDraw.Draw(bg)
    for yy in range(0, im.height, 20):
        for xx in range(0, im.width, 20):
            if ((yy // 20) + (xx // 20)) % 2 == 0:
                d.rectangle([xx, yy, xx + 19, yy + 19], fill=(226, 229, 235, 255))
    bg.alpha_composite(im)
    return bg


CASES = [('cheer_wave', 0), ('cheer_hands_up', 0), ('cheer_clap', 0)]
sheets = []
for tag, mode, radius in (('A 平涂R46', 'A', 46), ('B 原图R46', 'B', 46), ('C 平涂R32', 'C', 32)):
    row = []
    for act, i in CASES:
        arr = render(bake.POSES[act][i], mode, radius)
        row.append((f'{act}_{i}', small(arr)))
    sheets.append((tag, row))

cols = len(CASES)
W, H = 400, 480
sheet = Image.new('RGBA', (cols * W, len(sheets) * (H + 20)), (250, 250, 252, 255))
d = ImageDraw.Draw(sheet)
for ri, (tag, row) in enumerate(sheets):
    for ci, (nm, im) in enumerate(row):
        sheet.alpha_composite(im, (ci * W, ri * (H + 20) + 20))
    d.text((4, ri * (H + 20) + 4), f'{tag}: ' + ' | '.join(n for n, _ in row), fill=(20, 20, 30, 255))
sheet.save('/tmp/r165_diag2/shoulder_ab.png')
print('saved', sheet.size)
