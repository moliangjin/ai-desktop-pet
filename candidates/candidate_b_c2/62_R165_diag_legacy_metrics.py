#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 10: 量测旧测试 (r158 C5/C6, r162 R2-3/R2-4) 用到的几个量, 新素材实测值。

- skinCount(box)      : 盒内肤色像素数
- handGap(box)        : 盒内最左/最右两块手部肤色连通块之间的水平间距
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
NEW = os.path.join(CAND, 'assets/character_R158')
OLD = '/tmp/r162_old'
BASE = os.path.join(CAND, 'assets/character_R138/idle/idle_00_base.png')


def skin(a):
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 40) & (R > 200) & (G > 165) & (B < 228) & ((R - B) > 18)


def skin_count(a, x0, y0, x1, y1):
    return int(skin(a)[y0:y1, x0:x1].sum())


def hand_gap(a, X0=400, Y0=320, X1=640, Y1=500):
    s = skin(a)
    W, H = X1 - X0, Y1 - Y0
    on = s[Y0:Y1, X0:X1]
    seen = np.zeros_like(on, bool)
    comps = []
    for sy in range(H):
        for sx in range(W):
            if not on[sy, sx] or seen[sy, sx]:
                continue
            st = [(sy, sx)]
            seen[sy, sx] = True
            n, lo, hi = 0, 10 ** 9, -1
            while st:
                y, x = st.pop()
                n += 1
                lo = min(lo, x)
                hi = max(hi, x)
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < H and 0 <= nx < W and on[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            st.append((ny, nx))
            if n >= 150:
                comps.append((n, lo + X0, hi + X0, min(y for y, _ in []) or 0))
    if len(comps) < 2:
        return 0.0, len(comps), []
    comps.sort(key=lambda c: c[1])
    left = comps[0]
    right = comps[-1]
    if left[2] >= right[1]:
        return 0.0, len(comps), comps
    return float(right[1] - left[2]), len(comps), comps


def load(p):
    return np.asarray(Image.open(p).convert('RGBA')).astype(np.int32)


base = load(BASE)
print(f"基准 chest(450,400,580,520) 肤色 = {skin_count(base, 450, 400, 580, 520)}")
print(f"基准 chest(405,330,620,520) 肤色 = {skin_count(base, 405, 330, 620, 520)}")
print(f"基准 handGap(400,320,640,500) = {hand_gap(base)[0]}")
print()
for tag, d in (('R165', NEW), ('R162', OLD)):
    print(f'--- {tag} ---')
    for act in ('cheer_heart', 'cheer_clap'):
        for i in range(3):
            f = os.path.join(d, f'{act}_{i}.png')
            if not os.path.exists(f):
                continue
            a = load(f)
            g, ncomp, comps = hand_gap(a)
            print(f'  {act}_{i}: chest(450,400,580,520)={skin_count(a, 450, 400, 580, 520):5d} '
                  f'chest(405,330,620,520)={skin_count(a, 405, 330, 620, 520):5d} '
                  f'handGap={g:6.1f} (连通块 {ncomp})')
    print()
