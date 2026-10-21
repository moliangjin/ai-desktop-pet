#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 12: (a) 鼓掌帧胸区肤色块分解 (找出脖子块); (b) 衣身左缘描边连续性断点定位。"""
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


def groups(a, X0, Y0, X1, Y1, minpx=150):
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
            if n >= minpx:
                out.append(dict(n=n, lo=lo + X0, hi=hi + X0, y0=y0 + Y0, y1=y1 + Y0))
    out.sort(key=lambda d: d['lo'])
    return out


print('=== (a) 鼓掌三帧 胸区肤色块 (盒 380-660 / 300-560) ===')
for i in range(3):
    a = load(os.path.join(NEW, f'cheer_clap_{i}.png'))
    g = groups(a, 380, 300, 660, 560)
    print(f'  clap_{i}: {len(g)} 块')
    for d in g:
        print(f'      n={d["n"]:5d} x[{d["lo"]},{d["hi"]}] y[{d["y0"]},{d["y1"]}]')

print()
print('=== (a2) 同一盒但排除"脸/脖子"(含 y<400 的块) ===')
for i in range(3):
    a = load(os.path.join(NEW, f'cheer_clap_{i}.png'))
    g = [d for d in groups(a, 380, 300, 660, 560) if d['y0'] >= 400]
    gap = 0.0
    if len(g) >= 2:
        gap = max(0.0, g[-1]['lo'] - g[0]['hi'])
    print(f'  clap_{i}: {len(g)} 块 (排除 y<400) gap={gap:.1f} '
          f'{[(d["n"], d["lo"], d["hi"], d["y0"], d["y1"]) for d in g]}')

print()
print('=== (b) 衣身左缘描边连续性: cheer_heart_0 每行最左实心像素附近暗像素数 ===')
a = load(os.path.join(NEW, 'cheer_heart_0.png'))
h, w = a.shape[:2]
X0, X1 = 300, 512
rows = []
for y in range(350, 586):
    lmo = -1
    for x in range(X0, X1):
        if a[y, x, 3] > 40:
            lmo = x
            break
    if lmo < 0:
        rows.append((y, -1, 0))
        continue
    dark = 0
    for x in range(lmo, min(lmo + 7, w)):
        i = (y * w + x) * 4
        lum = 0.299 * a[y, x, 0] + 0.587 * a[y, x, 1] + 0.114 * a[y, x, 2]
        if lum < 130:
            dark += 1
    rows.append((y, lmo, dark))
gaps = [(y, lmo, d) for y, lmo, d in rows if d < 2]
# 连续段
segs = []
cur = []
for y, lmo, d in gaps:
    if cur and y == cur[-1][0] + 1:
        cur.append((y, lmo, d))
    else:
        if cur:
            segs.append(cur)
        cur = [(y, lmo, d)]
if cur:
    segs.append(cur)
segs.sort(key=len, reverse=True)
print(f'  最长断点段: {len(segs[0])} 行 → y[{segs[0][0][0]},{segs[0][-1][0]}]')
for sgm in segs[:4]:
    print(f'      y[{sgm[0][0]},{sgm[-1][0]}] 长度 {len(sgm)}  最左实心像素 x≈{sgm[0][1]}')
print(f'  底图同区域对照:')
b = load(os.path.join(CAND, 'assets/character_R138/idle/idle_00_base.png'))
for y in range(segs[0][0][0] - 2, segs[0][0][0] + 3):
    lmo = -1
    for x in range(X0, X1):
        if b[y, x, 3] > 40:
            lmo = x
            break
    vals = []
    for x in range(lmo, min(lmo + 8, w)):
        i = (y * w + x) * 4
        lum = 0.299 * b[y, x, 0] + 0.587 * b[y, x, 1] + 0.114 * b[y, x, 2]
        vals.append(f'{int(lum):3d}')
    print(f'      y={y} lmo={lmo} 底图亮度: {" ".join(vals)}')
