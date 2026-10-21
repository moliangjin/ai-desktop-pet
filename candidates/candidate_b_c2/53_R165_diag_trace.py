#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 3: 反向追踪"底图透明处的暗像素"在底图里的来源坐标。

对每个层级, 逆变换 dest -> src:
    fore: base_src = S + R(-a_s)·(E + R(-a_e)·(dest - E) - S)
    hand: base_src = S + R(-a_s)·(E + R(-a_e)·(W + R(-a_w)·(dest - W) - E) - S)
    upper:base_src = S + R(-a_s)·(dest - S)
(R = 屏幕顺时针旋转矩阵 [[c,-s],[s,c]]; 逆变换用 -θ)
"""
import importlib.util
import os
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')
BASE = os.path.join(R138, 'idle', 'idle_00_base.png')


def _mod(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


rig = _mod('r158_rig', os.path.join(CAND, '36_R158_arm_rig.py'))
bake = _mod('r158_bake', os.path.join(CAND, '37_R158_action_bake.py'))

base_np = rig.to_np(rig.load_rgba(BASE))
base_al = base_np[:, :, 3]
rigL = rig.build_arm(base_np, 'L')
rigR = rig.build_arm(base_np, 'R')


def Rmat(deg):
    th = np.deg2rad(deg)
    c, s = np.cos(th), np.sin(th)
    return np.array([[c, -s], [s, c]])


def inv(dest, pivot, deg):
    """dest -> src.

    rotate_rgba 的采样关系是: src = pivot + M(ang)·(dest - pivot)
    (因为它算的是 sx = px + dx*cos - dy*sin, dx/dy 取的是**目的**坐标)
    ⇒ 反查来源时要用 **同号** 的旋转, 不是 -ang。
    """
    d = np.asarray(dest, float) - np.asarray(pivot, float)
    return np.asarray(pivot, float) + Rmat(deg).dot(d)


def src_map(dest_x, dest_y, layer, S, E, W, ang):
    a_s, a_e, a_w = ang
    if layer == 'upper':
        p = inv([dest_x, dest_y], S, a_s)
    elif layer == 'fore':
        p1 = inv([dest_x, dest_y], S, a_s)
        p2 = inv(p1, E, a_e)
        p = p2
    else:  # hand
        p1 = inv([dest_x, dest_y], S, a_s)
        p2 = inv(p1, E, a_e)
        p3 = inv(p2, W, a_w)
        p = p3
    return p


DARK = 110
for action, poses in bake.POSES.items():
    if action not in ('cheer_heart', 'cheer_clap'):
        continue
    for i, p in enumerate(poses):
        body = base_np.copy()
        layers, names = [], []
        for side in ('L', 'R'):
            r = rigL if side == 'L' else rigR
            ang = p.get(side) or (0, 0, 0)
            b, _ = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'], fill_mask=r['upper'])
            body = b
            up, fo, hd, ball = rig.pose_arm(base_np, r, ang)
            layers += [up, fo, hd, ball]
            names += [f'{side}.upper', f'{side}.fore', f'{side}.hand', f'{side}.ball']
        comp = rig.compose(body, layers)
        bad = (base_al == 0) & (comp[:, :, 3] > 200) & (rig.lum(comp) < DARK)
        if not bad.any():
            continue
        ys, xs = np.nonzero(bad)
        print(f'\n### {action}_{i}: {len(ys)} 个"底图透明处暗像素"')
        for nm, lay in zip(names, layers):
            m = (lay[:, :, 3] > 200) & (rig.lum(lay) < DARK) & bad
            if not m.any():
                continue
            side = nm[0]
            ang = p.get(side) or (0, 0, 0)
            r = rigR if side == 'R' else rigL
            S, E, W = r['S'], r['E'], r['W']
            layer = nm.split('.')[1]
            my, mx = np.nonzero(m)
            srcs = []
            for yy, xx in zip(my, mx):
                sp = src_map(xx, yy, layer, S, E, W, ang)
                srcs.append((round(float(sp[0]), 1), round(float(sp[1]), 1)))
            c = Counter(srcs)
            print(f'  {nm}: {m.sum()} px')
            print(f'      底图来源坐标 top10: {c.most_common(10)}')
            # 取代表来源像素, 看底图那儿的 RGB/alpha
            for (sx, sy), n in c.most_common(4):
                ix, iy = int(round(sx)), int(round(sy))
                if 0 <= ix < 1024 and 0 <= iy < 1024:
                    px = base_np[iy, ix]
                    print(f'      底图({ix},{iy}) x{n}px  alpha={px[3]} rgb=({px[0]},{px[1]},{px[2]})')
