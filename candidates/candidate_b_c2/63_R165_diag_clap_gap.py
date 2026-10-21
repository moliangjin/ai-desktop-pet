#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 11: 找真正能让"两掌分开"的鼓掌参数 + 量测各动作的包围盒宽度。"""
import importlib.util
import os

import numpy as np
from PIL import Image

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


def skin(a):
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 40) & (R > 200) & (G > 165) & (B < 228) & ((R - B) > 18)


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
                comps.append((n, lo + X0, hi + X0))
    if len(comps) < 2:
        return 0.0, comps
    comps.sort(key=lambda c: c[1])
    left, right = comps[0], comps[-1]
    if left[2] >= right[1]:
        return 0.0, comps
    return float(right[1] - left[2]), comps


def render(poses):
    body = bn.copy()
    layers = []
    for side in ('L', 'R'):
        r = rigL if side == 'L' else rigR
        ang = poses.get(side) or (0, 0, 0)
        b, _ = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'], fill_mask=r['upper'])
        body = b
        up, fo, hd, ball = rig.pose_arm(bn, r, ang)
        layers += [up, fo, hd, ball]
    return rig.compose(body, layers)


print('=== 鼓掌参数扫描: 两掌间距 (旧判据盒 x400-640 / y320-500, 需 >=40px) ===')
best = []
for a_s in (16, 22, 28, 34, 40, 46):
    for a_e in (88, 96, 104, 112, 120):
        poses = dict(L=(-a_s, a_e, 0), R=(a_s, -a_e, 0))
        g, comps = hand_gap(render(poses))
        if g > 0 or a_e in (96, 120):
            print(f'  a_s=±{a_s:3d} a_e=±{a_e:3d}  gap={g:6.1f}  连通块={len(comps)} '
                  f'{[(c[0], c[1], c[2]) for c in comps]}')
        if g >= 40:
            best.append((a_s, a_e, g))
print(f'  ⇒ 满足 gap>=40 的候选: {best[:12]}')

print()
print('=== 各动作包围盒宽度 (用于 C1 "无整体水平压缩") ===')


def bbox_of(a):
    al = a[:, :, 3] > 40
    ys, xs = np.nonzero(al)
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


bb = bbox_of(bn)
print(f'  基准帧 bbox x[{bb[0]},{bb[1]}] 宽 {bb[1]-bb[0]}')
for act in bake.POSES:
    for i in range(3):
        f = os.path.join(CAND, f'assets/character_R158/{act}_{i}.png')
        a = rig.to_np(rig.load_rgba(f))
        b = bbox_of(a)
        w = b[1] - b[0]
        print(f'  {act}_{i}: bbox x[{b[0]},{b[1]}] 宽 {w} 偏差 {(w/(bb[1]-bb[0])-1)*100:+.1f}%')
