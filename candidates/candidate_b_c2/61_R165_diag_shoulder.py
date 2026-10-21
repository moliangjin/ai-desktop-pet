#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 9: 肩部区域差异归因 (新帧 / 旧帧 / 底图 / 各层)。"""
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

BASE = os.path.join(CAND, 'assets/character_R138/idle/idle_00_base.png')
NEW = os.path.join(CAND, 'assets/character_R158/cheer_heart_1.png')
OLD = '/tmp/r162_old/cheer_heart_1.png'

bn = rig.to_np(rig.load_rgba(BASE))
new = rig.to_np(rig.load_rgba(NEW))
old = rig.to_np(rig.load_rgba(OLD))
rigL = rig.build_arm(bn, 'L')
rigR = rig.build_arm(bn, 'R')

p = bake.POSES['cheer_heart'][1]
body = bn.copy()
layers, names = [], []
for side in ('L', 'R'):
    r = rigL if side == 'L' else rigR
    ang = p.get(side) or (0, 0, 0)
    b, _ = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'], fill_mask=r['upper'])
    body = b
    up, fo, hd, ball = rig.pose_arm(bn, r, ang)
    layers += [up, fo, hd, ball]
    names += [f'{side}.upper', f'{side}.fore', f'{side}.hand', f'{side}.ball']
comp = rig.compose(body, layers)

Y0, Y1, X0, X1 = 370, 470, 560, 700
reg = (slice(Y0, Y1), slice(X0, X1))


def ndiff(a, b):
    return int((np.abs(a[reg] - b[reg]).sum(axis=2) > 40).sum())


print(f'肩部区域(x{X0}-{X1}, y{Y0}-{Y1}) 与底图的差异像素数:')
print(f'  R165 新帧 : {ndiff(new, bn)}')
print(f'  R162 旧帧 : {ndiff(old, bn)}')
print(f'  身体层    : {ndiff(body, bn)}')
for nm, lay in zip(names, layers):
    print(f'  层 {nm:10s}: 该层不透明像素 {int((lay[reg][:, :, 3] > 40).sum())}')

print()
print('身体层在肩部与底图的差异区域:')
db = np.abs(body[reg] - bn[reg]).sum(axis=2)
ys, xs = np.nonzero(db > 40)
if len(ys):
    print(f'  y[{ys.min()+Y0},{ys.max()+Y0}] x[{xs.min()+X0},{xs.max()+X0}] n={len(ys)}')

# 逐点: 手臂掩膜 vs 上臂段
for side, rg in (('L', rigL), ('R', rigR)):
    up = rg['upper']
    print(f'  {side}.upper 在肩部区域覆盖 {int(up[Y0:Y1, X0:X1].sum())} px, '
          f'其中位于手臂掩膜内 {int((up & rg["arm"])[Y0:Y1, X0:X1].sum())} px')
    # teal 饰条像素位置
    t = rig.teal(bn) & (rg['arm'])
    ys, xs = np.nonzero(t)
    sel = (ys >= Y0) & (ys <= Y1)
    if sel.any():
        print(f'    {side} 手臂掩膜内的青色像素 y[{ys[sel].min()},{ys[sel].max()}] '
              f'x[{xs[sel].min()},{xs[sel].max()}] n={int(sel.sum())}')
        inup = up[ys[sel], xs[sel]]
        print(f'    其中落在 upper 段 {int(inup.sum())} px, 落在 fore 段 {int((rg["fore"][ys[sel], xs[sel]]).sum())} px')
