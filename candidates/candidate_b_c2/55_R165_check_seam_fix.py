#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 快速验证: 修复后单帧渲染 + 游离暗弧计数 + 裁切图。"""
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
OUT = '/tmp/r165_diag2'


def _mod(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


rig = _mod('r158_rig', os.path.join(CAND, '36_R158_arm_rig.py'))
bake = _mod('r158_bake', os.path.join(CAND, '37_R158_action_bake.py'))
os.makedirs(OUT, exist_ok=True)

base_np = rig.to_np(rig.load_rgba(BASE))
base_al = base_np[:, :, 3]
rigL = rig.build_arm(base_np, 'L')
rigR = rig.build_arm(base_np, 'R')

print('=== 掩膜体检 ===')
for nm, rg in (('L', rigL), ('R', rigR)):
    for seg in ('upper', 'fore', 'hand'):
        m = rg[seg]
        ys, xs = np.nonzero(m)
        if len(ys) == 0:
            print(f'  {nm}.{seg}: 空')
            continue
        inside = int((base_al[m] > 40).sum())
        print(f'  {nm}.{seg}: {m.sum():6d} px  bbox x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}] '
              f'| 其中底图不透明 {inside} ({inside * 100 // max(1, m.sum())}%)')

print()
print('=== 各帧: 底图透明处的暗像素 (接缝线被搬运的残留) ===')
DARK = 110
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
        bad = (base_al == 0) & (comp[:, :, 3] > 200) & (rig.lum(comp) < DARK)
        ys, xs = np.nonzero(bad)
        # 归因
        contrib = {}
        nmz = []
        for side in ('L', 'R'):
            nmz += [f'{side}.upper', f'{side}.fore', f'{side}.hand', f'{side}.ball']
        for nm, lay in zip(nmz, layers):
            m = (lay[:, :, 3] > 200) & (rig.lum(lay) < DARK) & bad
            c = int(m.sum())
            if c:
                contrib[nm] = c
        seg = ''
        if len(xs):
            seg = f' x段={[(int(xs.min()), int(xs.max()))]} y段=[{int(ys.min())},{int(ys.max())}]'
        print(f'  {action}_{i}: {bad.sum():5d} px{seg}  {contrib}')
        if action == 'cheer_heart' and i == 0:
            im = rig.to_im(comp).crop((560, 360, 720, 520)).resize((480, 480), Image.NEAREST)
            im.save(f'{OUT}/heart0_hip.png')
            im2 = rig.to_im(comp).resize((512, 512), Image.LANCZOS)
            im2.save(f'{OUT}/heart0_full.png')
