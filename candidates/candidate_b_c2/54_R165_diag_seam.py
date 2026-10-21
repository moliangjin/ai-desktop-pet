#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 诊断 4: 量测两侧"衣身接缝暗带"的逐行连续暗段, 决定从手臂掩膜里剔除的宽度。"""
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
lum = rig.lum(base_np)
al = base_np[:, :, 3]
dark = (lum < rig.SEAM_DARK) & (al > 40)


def runs_of(row_mask):
    out, s0 = [], None
    for x in range(row_mask.shape[0]):
        if row_mask[x] and s0 is None:
            s0 = x
        elif (not row_mask[x]) and s0 is not None:
            out.append((s0, x - 1))
            s0 = None
    if s0 is not None:
        out.append((s0, row_mask.shape[0] - 1))
    return out


rigL = rig.build_arm(base_np, 'L')
rigR = rig.build_arm(base_np, 'R')

for side, rigx in (('L', rigL), ('R', rigR)):
    print(f'\n=== {side} 侧: 掩膜外缘 → 接缝暗段 (逐行) ===')
    print(f'{"y":>5} {"mask边":>7} {"暗段(外→内)":>28} {"接缝段宽":>8}  掩膜内是否含缝')
    for y in range(376, 600, 6):
        xs = np.nonzero(rigx['arm'][y])[0]
        if len(xs) == 0:
            continue
        edge = int(xs.min()) if side == 'L' else int(xs.max())
        rs = [r for r in runs_of(dark[y]) if r[1] > edge - 90 and r[0] < edge + 90]
        band = rig.seam_band(base_np, y, side, edge)
        if side == 'L':
            rs = [r for r in rs if r[1] <= 460]
            rs = sorted(rs, key=lambda r: -r[1])[:3]
        else:
            rs = [r for r in rs if r[0] >= 570]
            rs = sorted(rs, key=lambda r: r[0])[:3]
        w = (band[1] - band[0] + 1) if band else 0
        print(f'{y:>5} {edge:>7} {str(rs):>28} {w:>8}  band={band}')
