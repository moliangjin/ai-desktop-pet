#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R167 诊断: 精确测量坐姿帧 (sleep_enter_01_sit) 的手臂/手部几何。

目的: 决定"双手放键盘上"到底需要动多少几何。
输出:
  · 材质分类 (皮肤 / 白大褂 / 青色饰条 / 深蓝内衬 / 浅蓝裤 / 描边)
  · 逐行剪影范围 + 袖口(青色腕带)位置 + 肤色块位置
  · 手部 bbox / 质心
"""
import os
import sys
from collections import deque

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
SIT = os.path.join(CAND, 'assets', 'character_R138', 'sleep_enter', 'sleep_enter_01_sit.png')


def classify(a):
    """a: HxWx4 uint8 -> dict of boolean masks."""
    r = a[:, :, 0].astype(np.int16)
    g = a[:, :, 1].astype(np.int16)
    b = a[:, :, 2].astype(np.int16)
    al = a[:, :, 3]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    solid = al > 40
    skin = solid & (r > 195) & (g > 140) & (g < 205) & (b > 110) & (b < 185) & (r > b + 35)
    teal = solid & (b > r + 12) & (g > r + 5) & (b > 150) & (sat > 22)
    dark = solid & (mx < 120)
    navy = solid & (b > r + 10) & (mx < 110)
    white = solid & (mn > 196) & (sat < 26)
    pants = solid & (b > r + 12) & (mn > 150) & (mx < 240) & ~teal
    return dict(solid=solid, skin=skin, teal=teal, dark=dark, navy=navy,
                white=white, pants=pants)


def runs_of(mask_row):
    out = []
    s = None
    for x, v in enumerate(mask_row):
        if v and s is None:
            s = x
        elif (not v) and s is not None:
            out.append((s, x - 1))
            s = None
    if s is not None:
        out.append((s, len(mask_row) - 1))
    return out


def components(mask, min_px=50):
    m = mask.copy()
    H, W = m.shape
    seen = np.zeros_like(m)
    out = []
    ys, xs = np.nonzero(m)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)])
        seen[y0, x0] = True
        comp = []
        while q:
            y, x = q.popleft()
            comp.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
        if len(comp) >= min_px:
            arr = np.array(comp)
            out.append(dict(px=len(comp),
                            x0=int(arr[:, 1].min()), x1=int(arr[:, 1].max()),
                            y0=int(arr[:, 0].min()), y1=int(arr[:, 0].max()),
                            cx=float(arr[:, 1].mean()), cy=float(arr[:, 0].mean())))
    return sorted(out, key=lambda d: -d['px'])


def main():
    im = Image.open(SIT).convert('RGBA')
    a = np.asarray(im).copy()
    m = classify(a)
    print(f'素材: {SIT}  size={a.shape}')

    print('\n=== 材质像素统计 ===')
    for k in ('solid', 'skin', 'teal', 'dark', 'navy', 'white', 'pants'):
        print(f'  {k:8s} {int(m[k].sum()):8d}')

    print('\n=== 肤色连通块 (>=150 px) ===')
    for c in components(m['skin'], 150):
        print(f"  px={c['px']:6d} bbox x[{c['x0']},{c['x1']}] y[{c['y0']},{c['y1']}] "
              f"cen=({c['cx']:.0f},{c['cy']:.0f})")

    print('\n=== 青色腕带/饰条连通块 (>=60 px) ===')
    for c in components(m['teal'], 60)[:14]:
        print(f"  px={c['px']:6d} bbox x[{c['x0']},{c['x1']}] y[{c['y0']},{c['y1']}]")

    print('\n=== 逐行: 剪影范围 / 白大褂 / 肤色 / 青色 (y=360..680, 每 8 行) ===')
    for y in range(360, 681, 8):
        sol = np.nonzero(m['solid'][y])[0]
        if len(sol) == 0:
            print(f'  y={y:4d}  (空)')
            continue
        w = runs_of(m['white'][y])
        s = runs_of(m['skin'][y])
        t = runs_of(m['teal'][y])
        print(f'  y={y:4d} sil[{sol.min():4d},{sol.max():4d}] '
              f'white={w} skin={s} teal={t}')

    print('\n=== 坐姿关键行: 剪影左右缘 (每 4 行) ===')
    for y in range(330, 700, 4):
        sol = np.nonzero(m['solid'][y])[0]
        if len(sol) == 0:
            continue
        print(f'  y={y:4d} L={sol.min():4d} R={sol.max():4d}')


if __name__ == '__main__':
    sys.exit(main())
