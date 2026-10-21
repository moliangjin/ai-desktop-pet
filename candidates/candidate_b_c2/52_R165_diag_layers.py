#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 2: 把 R 侧各层单独渲染成图, 肉眼看那条暗弧长什么样。"""
import importlib.util
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')
BASE = os.path.join(R138, 'idle', 'idle_00_base.png')
OUT = '/tmp/r165_diag'


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


def checker(shape, sq=16):
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W]
    c = (((yy // sq) + (xx // sq)) % 2).astype(np.uint8)
    rgb = np.where(c[..., None] == 0, 90, 140).astype(np.int32)
    out = np.zeros((H, W, 4), np.int32)
    out[..., 0] = rgb[..., 0]
    out[..., 1] = rgb[..., 1]
    out[..., 2] = rgb[..., 2]
    out[..., 3] = 255
    return out


def save(arr, path, crop=None, zoom=3):
    im = rig.to_im(arr)
    if crop:
        im = im.crop(crop)
    im = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
    im.save(path)
    print('  saved', path, im.size)


X0, Y0, X1, Y1 = 590, 370, 700, 500

# 1) 底图
save(base_np, f'{OUT}/00_base.png', (X0, Y0, X1, Y1))
# 1b) 底图 alpha 通道 (把剪影看清楚)
al = base_np.copy()
al[..., 0] = al[..., 3]
al[..., 1] = al[..., 3]
al[..., 2] = al[..., 3]
al[..., 3] = 255
save(al, f'{OUT}/01_base_alpha.png', (X0, Y0, X1, Y1))

# 2) 各层掩膜
for nm, m in (('upper', rigR['upper']), ('fore', rigR['fore']), ('hand', rigR['hand']),
              ('ball', rigR['ball']), ('arm', rigR['arm'])):
    lay = np.zeros_like(base_np)
    lay[..., 3] = np.where(m, 255, 0)
    save(lay, f'{OUT}/02_mask_{nm}.png', (X0, Y0, X1, Y1))

# 3) cheer_heart_0 各层实拍
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
save(comp, f'{OUT}/03_composed_full.png', (X0, Y0, X1, Y1))
for nm, lay in zip(names, layers):
    save(lay, f'{OUT}/04_layer_{nm.replace(".", "_")}.png', (X0, Y0, X1, Y1))

# 4) 底图原始像素值: R 侧外缘一带
print('\n=== 底图 R 侧 y=460 一行 x=615..680 的 (alpha, lum, RGB) ===')
for x in range(615, 681):
    a = base_np[460, x]
    print(f'  x={x}: alpha={a[3]:3d} rgb=({a[0]:3d},{a[1]:3d},{a[2]:3d}) lum={rig.lum(base_np[460, x]):6.1f}')
