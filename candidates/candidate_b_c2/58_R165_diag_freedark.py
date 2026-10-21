#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 8: "游离暗像素"判据 —— 暗像素若周围 3px 内没有任何"非暗实心像素", 就是残影。"""
import importlib.util
import os

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
rigL = rig.build_arm(base_np, 'L')
rigR = rig.build_arm(base_np, 'R')


def dilate(mask, r):
    out = mask.copy()
    for _ in range(r):
        o = out.copy()
        o[1:, :] |= out[:-1, :]
        o[:-1, :] |= out[1:, :]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


def free_dark(img, dist=3, dark_thr=120, solid_thr=128):
    solid = img[:, :, 3] > solid_thr
    dark = solid & (rig.lum(img) < dark_thr)
    bright = solid & (rig.lum(img) >= dark_thr)
    near = dilate(bright, dist)
    return dark & ~near


def clusters(mask, gap=8):
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return []
    pts = sorted(zip(ys.tolist(), xs.tolist()))
    groups, cur = [], [pts[0]]
    for p in pts[1:]:
        if p[0] - cur[-1][0] > gap or p[1] - cur[-1][1] > gap:
            groups.append(cur)
            cur = [p]
        else:
            cur.append(p)
    groups.append(cur)
    out = []
    for g in groups:
        gy = [q[0] for q in g]
        gx = [q[1] for q in g]
        out.append((len(g), min(gy), max(gy), min(gx), max(gx)))
    return out


print('=== 各帧游离暗像素 (阈值: 周围 3px 内无任何非暗实心像素) ===')
for action, poses in bake.POSES.items():
    for i, p in enumerate(poses):
        body = base_np.copy()
        layers = []
        for side in ('L', 'R'):
            r = rigL if side == 'L' else rigR
            ang = p.get(side) or (0, 0, 0)
            b, _ = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'], fill_mask=r['upper'])
            body = b
            up, fo, hd, ball = rig.pose_arm(base_np, r, ang)
            layers += [up, fo, hd, ball]
        comp = rig.compose(body, layers)
        fd = free_dark(comp)
        cl = clusters(fd)
        cl.sort(reverse=True)
        top = ' | '.join(f'n={c[0]} y[{c[1]},{c[2]}] x[{c[3]},{c[4]}]' for c in cl[:4])
        print(f'  {action}_{i}: {int(fd.sum()):5d} px  簇={len(cl)}  {top}')

# 单独看身体层
print('\n=== cheer_heart_0 身体层自身的游离暗像素 (= 留在衣身上的残影) ===')
body = base_np.copy()
for side in ('L', 'R'):
    r = rigL if side == 'L' else rigR
    b, _ = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'], fill_mask=r['upper'])
    body = b
fd = free_dark(body)
for c in sorted(clusters(fd), reverse=True)[:8]:
    print(f'  n={c[0]} y[{c[1]},{c[2]}] x[{c[3]},{c[4]}]')
print(f'  合计 {int(fd.sum())} px')
