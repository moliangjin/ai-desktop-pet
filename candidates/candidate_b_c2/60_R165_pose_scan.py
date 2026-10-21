#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 姿态扫描: 用新 rig 在 200x240 真实显示尺寸下渲染候选姿态, 供肉眼挑选。

用法: python3 60_R165_pose_scan.py --action heart --out /tmp/scan.png
"""
import argparse
import importlib.util
import os

import numpy as np
from PIL import Image, ImageDraw

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

SCANS = {
    'heart': [
        dict(L=(-6, 78, -14), R=(6, -78, 14)),
        dict(L=(0, 96, -14), R=(0, -96, 14)),
        dict(L=(0, 112, -14), R=(0, -112, 14)),
        dict(L=(0, 126, -14), R=(0, -126, 14)),
        dict(L=(-6, 112, -14), R=(6, -112, 14)),
        dict(L=(0, 100, -30), R=(0, -100, 30)),
        dict(L=(-10, 112, -10), R=(10, -112, 10)),
        dict(L=(0, 120, 0), R=(0, -120, 0)),
    ],
    'clap': [
        dict(L=(-40, 96, 0), R=(40, -96, 0)),
        dict(L=(-4, 124, 0), R=(4, -124, 0)),
        dict(L=(-32, 90, 0), R=(32, -90, 0)),
        dict(L=(-48, 96, 0), R=(48, -96, 0)),
        dict(L=(-40, 84, 0), R=(40, -84, 0)),
        dict(L=(-8, 112, 0), R=(8, -112, 0)),
        dict(L=(-56, 96, 0), R=(56, -96, 0)),
        dict(L=(-32, 84, 0), R=(32, -84, 0)),
    ],
    'wave': [
        dict(L=None, R=(130, 0, 0)),
        dict(L=None, R=(122, 0, 0)),
        dict(L=None, R=(114, 0, 0)),
        dict(L=None, R=(106, 0, 0)),
        dict(L=None, R=(130, 0, 20)),
        dict(L=None, R=(122, -8, 20)),
    ],
    'hands_up': [
        dict(L=(-118, 0, 0), R=(118, 0, 0)),
        dict(L=(-108, 0, 0), R=(108, 0, 0)),
        dict(L=(-98, 0, 0), R=(98, 0, 0)),
        dict(L=(-118, 0, 0), R=(112, 0, 0)),
        dict(L=(-90, 0, 0), R=(90, 0, 0)),
    ],
}


def render(poses):
    body = base_np.copy()
    layers = []
    for side in ('L', 'R'):
        r = rigL if side == 'L' else rigR
        ang = poses.get(side) or (0, 0, 0)
        b, _ = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'], fill_mask=r['upper'])
        body = b
        up, fo, hd, ball = rig.pose_arm(base_np, r, ang)
        layers += [up, fo, hd, ball]
    return rig.compose(body, layers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--action', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--w', type=int, default=200)
    ap.add_argument('--h', type=int, default=240)
    ap.add_argument('--crop', default=None, help='x0,y0,x1,y1 (1024 纹理坐标)')
    a = ap.parse_args()

    cands = SCANS[a.action]
    cols = min(4, len(cands))
    rows = (len(cands) + cols - 1) // cols
    W, H = a.w, a.h
    sheet = Image.new('RGBA', (cols * W, rows * (H + 18)), (250, 250, 252, 255))
    d = ImageDraw.Draw(sheet)
    for i, poses in enumerate(cands):
        arr = render(poses)
        im = rig.to_im(arr)
        if a.crop:
            x0, y0, x1, y1 = [int(v) for v in a.crop.split(',')]
            im = im.crop((x0, y0, x1, y1)).resize((W, H), Image.LANCZOS)
        else:
            im = im.resize((W, H), Image.LANCZOS)
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        dd = ImageDraw.Draw(bg)
        for yy in range(0, H, 10):
            for xx in range(0, W, 10):
                if ((yy // 10) + (xx // 10)) % 2 == 0:
                    dd.rectangle([xx, yy, xx + 9, yy + 9], fill=(226, 229, 235, 255))
        bg.alpha_composite(im)
        cx, cy = (i % cols) * W, (i // cols) * (H + 18)
        sheet.alpha_composite(bg, (cx, cy))
        d.text((cx + 3, cy + H + 4), str(poses), fill=(20, 20, 30, 255))
        d.rectangle([cx, cy, cx + W - 1, cy + H + 17], outline=(170, 175, 185, 255))
    sheet.save(a.out)
    print(f'{a.out} {sheet.size} n={len(cands)}')


if __name__ == '__main__':
    main()
