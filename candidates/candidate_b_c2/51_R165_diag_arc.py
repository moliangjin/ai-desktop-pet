#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断: 右髋"虚线状残留描边"到底来自哪一层。

逐层渲染 (upper / fore / hand / ball / body), 找出"底图 alpha=0 但合成后不透明且暗"的像素
分别由哪一层贡献, 并打印该层的掩膜在该行的覆盖范围。
"""
import importlib.util
import os
import sys

import numpy as np
from PIL import Image

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

base_al = base_np[:, :, 3]
base_lum = rig.lum(base_np)

print('=== 底图 R 侧手臂掩膜逐行范围 (y: mask x-range | base alpha x-range | 外缘 | seam) ===')
for y in range(440, 500, 4):
    r = np.nonzero(rigR['arm'][y])[0]
    if len(r) == 0:
        print(f'  y={y}: (mask empty)')
        continue
    b = np.nonzero(base_al[y] > 40)[0]
    bx = (int(b.min()), int(b.max())) if len(b) else None
    edge = int(r.max())
    band = rig.seam_band(base_np, y, 'R', edge)
    print(f'  y={y}: mask x[{r.min()},{r.max()}] n={len(r)} | base_alpha_x={bx} '
          f'| outer_edge_R={rig._outer_edge_R(base_np, y, 1024 - int(np.nonzero(rigL["arm"][y])[0].min())) if len(np.nonzero(rigL["arm"][y])[0]) else None} '
          f'| seam={band} | mask 内 alpha=0 数={int((base_al[y, r.min():r.max()+1] == 0).sum())}')

print()
print('=== fore 段掩膜逐行 (y: fore x-range | base alpha=0 占比) ===')
for y in range(430, 520, 5):
    r = np.nonzero(rigR['fore'][y])[0]
    if len(r) == 0:
        print(f'  y={y}: (fore empty)')
        continue
    seg = base_al[y, r.min():r.max() + 1]
    print(f'  y={y}: fore x[{r.min()},{r.max()}] n={len(r)} | alpha=0 占比={float((seg == 0).mean()):.2f}')

print()
print('=== 逐 pose 分层: 谁贡献了"底图透明区里的不透明暗像素" ===')
DARK = 110
for action, poses in bake.POSES.items():
    for i, p in enumerate(poses):
        body = base_np.copy()
        layers = []
        names = []
        for side in ('L', 'R'):
            r = rigL if side == 'L' else rigR
            ang = p.get(side) or (0, 0, 0)
            b, _ = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'], fill_mask=r['upper'])
            body = b
            up, fo, hd, ball = rig.pose_arm(base_np, r, ang)
            layers += [up, fo, hd, ball]
            names += [f'{side}.upper', f'{side}.fore', f'{side}.hand', f'{side}.ball']
        composed = rig.compose(body, layers)
        # 底图透明 且 合成后不透明且暗
        bad = (base_al == 0) & (composed[:, :, 3] > 200) & (rig.lum(composed) < DARK)
        if not bad.any():
            continue
        ys, xs = np.nonzero(bad)
        # 归因
        contrib = {}
        for nm, lay in zip(names, layers):
            m = (lay[:, :, 3] > 200) & (rig.lum(lay) < DARK)
            c = int((m & bad).sum())
            if c:
                contrib[nm] = c
        # 按 x 聚类
        xu = sorted(set(xs.tolist()))
        groups = []
        s = p0 = xu[0]
        for v in xu[1:]:
            if v - p0 > 6:
                groups.append((s, p0))
                s = v
            p0 = v
        groups.append((s, p0))
        print(f'  {action}_{i}: 暗像素 {len(ys)} px | x 段={groups} | y 范围=[{ys.min()},{ys.max()}]')
        print(f'      归因: {contrib}')
