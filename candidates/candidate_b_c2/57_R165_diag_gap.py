#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 6: 逐行量测"手臂掩膜外缘"与"底图剪影外缘"之间的缺口, 以及残留在衣身上的暗像素。"""
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
base_np = rig.to_np(rig.load_rgba(BASE))
al = base_np[:, :, 3]
lum = rig.lum(base_np)
rigL = rig.build_arm(base_np, 'L')
rigR = rig.build_arm(base_np, 'R')

for side, rg in (('L', rigL), ('R', rigR)):
    print(f'\n=== {side} 侧: 掩膜外缘 vs 底图剪影外缘 (缺口 = 残留在衣身上的描边) ===')
    tot_leftover = 0
    rows_with = 0
    for y in range(376, 597):
        xs = np.nonzero(rg['arm'][y])[0]
        if len(xs) == 0:
            continue
        if side == 'L':
            edge = int(xs.min())
            b = np.nonzero(al[y, :512] > 40)[0]
            bmax = int(b.min()) if len(b) else -1
            gap = edge - bmax
        else:
            edge = int(xs.max())
            b = np.nonzero(al[y, 512:] > 40)[0]
            bmax = (512 + int(b.max())) if len(b) else -1
            gap = bmax - edge
        if gap <= 0:
            continue
        # 缺口区里还剩多少暗像素 (这些就是会留在衣身上的描边)
        if side == 'L':
            seg = slice(max(0, edge - gap), edge)
        else:
            seg = slice(edge + 1, min(1024, edge + 1 + gap))
        d = int(((lum[y, seg] < 120) & (al[y, seg] > 40)).sum())
        tot_leftover += d
        if d:
            rows_with += 1
        if gap >= 3 or d:
            if gap >= 3:
                print(f'  y={y}: 掩膜边={edge} 剪影边={bmax} 缺口={gap} 缺口内暗像素={d}')
    print(f'  >>> {side} 侧合计残留暗像素 = {tot_leftover} (分布在 {rows_with} 行)')

print('\n=== R 侧 y=440 一行 x=620..645 明细 (查轮廓断口) ===')
for x in range(620, 646):
    a = base_np[440, x]
    print(f'  x={x}: alpha={a[3]:3d} rgb=({a[0]:3d},{a[1]:3d},{a[2]:3d}) lum={lum[440, x]:6.1f} '
          f'| in_arm={bool(rigR["arm"][440, x])}')
