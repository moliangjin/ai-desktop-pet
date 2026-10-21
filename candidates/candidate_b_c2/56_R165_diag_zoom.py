#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 5: 放大看新 rig 下 R.fore 层 + 合成帧 + 底图对应区域。"""
import importlib.util
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')
BASE = os.path.join(R138, 'idle', 'idle_00_base.png')
OUT = '/tmp/r165_diag3'


def _mod(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


rig = _mod('r158_rig', os.path.join(CAND, '36_R158_arm_rig.py'))
bake = _mod('r158_bake', os.path.join(CAND, '37_R158_action_bake.py'))
os.makedirs(OUT, exist_ok=True)

base_np = rig.to_np(rig.load_rgba(BASE))
rigL = rig.build_arm(base_np, 'L')
rigR = rig.build_arm(base_np, 'R')

p = bake.POSES['cheer_heart'][0]
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


def save(arr, path, crop, zoom=4):
    im = rig.to_im(arr).crop(crop)
    im = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
    im.save(path)
    print('  saved', path, im.size)


save(comp, f'{OUT}/comp.png', (600, 400, 700, 500))
for nm, lay in zip(names, layers):
    if nm.startswith('R'):
        save(lay, f'{OUT}/lay_{nm.replace(".", "_")}.png', (600, 400, 700, 500))
save(base_np, f'{OUT}/base.png', (600, 400, 700, 500))
# 身体层
save(body, f'{OUT}/body.png', (600, 400, 700, 500))

print('\n=== 底图 x=610..625, y=420..436 的 RGB (找青色饰条暗边) ===')
for y in range(420, 437, 2):
    row = ' '.join(f'{base_np[y, x, 0]:3d}/{base_np[y, x, 1]:3d}/{base_np[y, x, 2]:3d}'
                   for x in range(610, 626))
    print(f'  y={y}: {row}')

print('\n=== R 侧掩膜逐行 (y: mask x-range | base alpha x-range) ===')
for y in range(400, 530, 10):
    xs = np.nonzero(rigR['arm'][y])[0]
    b = np.nonzero(base_np[y, :, 3] > 40)[0]
    if len(xs) == 0:
        continue
    print(f'  y={y}: mask x[{xs.min()},{xs.max()}] n={len(xs)} | base x[{b.min()},{b.max()}] '
          f'| seam={rig.seam_band(base_np, y, "R")}')
