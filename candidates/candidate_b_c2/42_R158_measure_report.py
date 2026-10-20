#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R158 交付报告用绝对数值测量 —— 打印每个新动作的实测指标, 供 QA 报告直接引用。

口径与 tests/r158_click_actions.test.js 完全一致 (同一套判据, 同一套阈值):
  · 面积中位数偏差  <15%   => 未发生整体水平压缩
  · 脚底中心位移    <24 px  => 未发生整体水平平移
  · 冠部(y=60)实心段宽度偏差 <15% => 未发生整体水平压缩 (第二重独立判据)

本脚本只读, 不写任何资产。
"""
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
MANIFEST = json.load(open(os.path.join(ASSETS, 'character_R141_manifest.json'), encoding='utf-8'))
LIB = MANIFEST['action_library']['actions']

BASE = 'character_R138/idle/idle_00_base.png'
R158_ACTIONS = ['cheer_wave', 'cheer_hands_up', 'cheer_heart', 'cheer_clap',
                'cheer_jump', 'cheer_tilt']
# R156 的几何形变动作 (R158 已下架) —— 作为"伪动作"对照基线一起打印
R156_FAKES = ['cheer_spin', 'cheer_sway']


def load(rel):
    return np.asarray(Image.open(os.path.join(ASSETS, rel)).convert('RGBA'))


def area_of(a):
    return int((a[:, :, 3] > 40).sum())


def feet_center(a):
    band = a[870:1000]
    m = band[:, :, 3] > 40
    if not m.any():
        return None
    xs = np.where(m)[1]
    return float(xs.mean())


def crown_row(a, y=60):
    row = a[y, :, 3] > 40
    if not row[512]:
        return None
    lo = 512
    while lo - 1 >= 0 and row[lo - 1]:
        lo -= 1
    hi = 512
    while hi + 1 < a.shape[1] and row[hi + 1]:
        hi += 1
    return hi - lo


def main():
    base = load(BASE)
    b_area = area_of(base)
    b_feet = feet_center(base)
    b_crown = crown_row(base)

    out = {
        'baseline': {
            'frame': BASE,
            'solid_area_px': b_area,
            'feet_center_x': round(b_feet, 2),
            'crown_row60_width_px': b_crown,
        },
        'thresholds': {
            'area_median_deviation_max_pct': 15.0,
            'feet_center_shift_max_px': 24,
            'crown_width_deviation_max_pct': 15.0,
        },
        'actions': {},
    }

    for act in R158_ACTIONS + R156_FAKES:
        frames = LIB.get(act, {}).get('frames', [])
        if not frames:
            continue
        areas = sorted(area_of(load(f)) for f in frames)
        med = areas[len(areas) // 2]
        area_dev = (med - b_area) / b_area * 100.0

        feet = [feet_center(load(f)) for f in frames]
        foot_shift = max(abs(fc - b_feet) for fc in feet if fc is not None)

        crowns = [crown_row(load(f)) for f in frames]
        crowns = [c for c in crowns if c]
        crown_dev = max(abs(c - b_crown) / b_crown * 100.0 for c in crowns) if crowns else None

        out['actions'][act] = {
            'round': 'R158' if act in R158_ACTIONS else 'R156(已下架)',
            'frames': [os.path.basename(f) for f in frames],
            'area_median_px': med,
            'area_median_deviation_pct': round(area_dev, 2),
            'area_verdict': 'PASS' if abs(area_dev) < 15 else 'FAIL(疑似整体压缩)',
            'feet_center_shift_max_px': round(foot_shift, 2),
            'feet_verdict': 'PASS' if foot_shift < 24 else 'FAIL(疑似整体平移)',
            'crown_width_deviation_max_pct': None if crown_dev is None else round(crown_dev, 2),
            'crown_verdict': ('PASS' if crown_dev is not None and crown_dev < 15
                              else ('FAIL(疑似整体压缩)' if crown_dev is not None else 'N/A')),
        }

    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
