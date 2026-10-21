#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 13: (a) 回填范围修正后的衣身左缘断点; (b) 比心/鼓掌六帧的手部块统计。"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
NEW = os.path.join(CAND, 'assets/character_R158')


def load(p):
    return np.asarray(Image.open(p).convert('RGBA')).astype(np.int32)


def skin(a):
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 40) & (R > 200) & (G > 165) & (B < 228) & ((R - B) > 18)


def groups(a, X0=380, Y0=300, X1=660, Y1=560, minpx=150, ymin=400):
    s = skin(a)
    W, H = X1 - X0, Y1 - Y0
    on = s[Y0:Y1, X0:X1]
    seen = np.zeros_like(on, bool)
    out = []
    for sy in range(H):
        for sx in range(W):
            if not on[sy, sx] or seen[sy, sx]:
                continue
            st = [(sy, sx)]
            seen[sy, sx] = True
            n, lo, hi, y0, y1 = 0, 10 ** 9, -1, 10 ** 9, -1
            while st:
                y, x = st.pop()
                n += 1
                lo = min(lo, x); hi = max(hi, x)
                y0 = min(y0, y); y1 = max(y1, y)
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < H and 0 <= nx < W and on[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            st.append((ny, nx))
            if n >= minpx and y0 + Y0 >= ymin:
                out.append(dict(n=n, lo=lo + X0, hi=hi + X0, y0=y0 + Y0, y1=y1 + Y0))
    out.sort(key=lambda d: d['lo'])
    return out


print('=== (a) 左衣身边缘描边连续性 (cheer_heart_0, 补fill后) ===')
a = load(os.path.join(NEW, 'cheer_heart_0.png'))
h, w = a.shape[:2]
X0, X1 = 300, 512
flags = []
for y in range(350, 586):
    lmo = -1
    for x in range(X0, X1):
        if a[y, x, 3] > 40:
            lmo = x
            break
    if lmo < 0:
        flags.append((y, -1, 0))
        continue
    dark = 0
    for x in range(lmo, min(lmo + 7, w)):
        i = (y * w + x) * 4
        lum = 0.299 * a[y, x, 0] + 0.587 * a[y, x, 1] + 0.114 * a[y, x, 2]
        if lum < 130:
            dark += 1
    flags.append((y, lmo, dark))
segs, cur = [], []
for y, lmo, d in flags:
    bad = d < 2
    if cur and y == cur[-1][0] + 1 and (cur[-1][2] < 2) == bad:
        cur.append((y, lmo, d))
    else:
        if cur:
            segs.append(cur)
        cur = [(y, lmo, d)]
if cur:
    segs.append(cur)
segs.sort(key=len, reverse=True)
for sg in segs[:4]:
    print(f'  断点段 y[{sg[0][0]},{sg[-1][0]}] 长度 {len(sg)}  最左实心 x≈{sg[0][1]}')
for y in range(435, 445):
    lmo = -1
    for x in range(X0, X1):
        if a[y, x, 3] > 40:
            lmo = x
            break
    vals = []
    for x in range(lmo, min(lmo + 8, w)):
        i = (y * w + x) * 4
        lum = 0.299 * a[y, x, 0] + 0.587 * a[y, x, 1] + 0.114 * a[y, x, 2]
        vals.append(f'{int(lum):3d}')
    print(f'    y={y} lmo={lmo} 亮度: {" ".join(vals)}')

print()
print('=== (b) 比心 / 鼓掌 六帧的手部块统计 ===')
for act in ('cheer_heart', 'cheer_clap'):
    for i in range(3):
        a = load(os.path.join(NEW, f'{act}_{i}.png'))
        g = groups(a)
        gap = max(0.0, g[-1]['lo'] - g[0]['hi']) if len(g) >= 2 else 0.0
        span = (g[-1]['hi'] - g[0]['lo']) if g else 0
        ytop = min(d['y0'] for d in g) if g else 0
        ybot = max(d['y1'] for d in g) if g else 0
        cy = sum((d['y0'] + d['y1']) / 2 * d['n'] for d in g) / max(1, sum(d['n'] for d in g))
        print(f'  {act}_{i}: {len(g)} 块 gap={gap:5.1f} span={span:4d} y[{ytop},{ybot}] 质心y={cy:.0f} '
              f'{[(d["n"], d["lo"], d["hi"], d["y0"], d["y1"]) for d in g]}')
