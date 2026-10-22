#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R170 spike: 手臂 rig 能否直接跑在**坐姿**底图上 (为 eat_fruit 场景服务)。

背景:
  · R165 修好的 arm_rig (36_R158_arm_rig.py) 关节坐标 (shoulder/elbow/wrist) 是按
    **站立底图** character_R138/idle/idle_00_base.png 硬编码的;
  · 但 eat_fruit 要求角色**坐在小凳子上** ⇒ 底图是 sleep_enter_01_sit.png,
    手臂姿态完全不同 ⇒ 关节坐标必须重新给。

本 spike 做三件事:
  1) 在坐姿底图上 build_arm, 打印实际得到的关节 (S/E/W) 与掩膜面积;
  2) 用一组角度摆臂, 拼成对照图;
  3) 打印"如果关节坐标错了会怎样"的对比 —— 即用站立底图的关节 vs 坐姿自己的关节。

只读 + 只写 /tmp, 不碰任何资产。
"""
import importlib.util
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
sys.path.insert(0, HERE)


def _load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_rig = _load_mod('rig36', os.path.join(HERE, '36_R158_arm_rig.py'))

SIT = os.path.join(ASSETS, 'character_R138', 'sleep_enter', 'sleep_enter_01_sit.png')
IDLE = os.path.join(ASSETS, 'character_R138', 'idle', 'idle_00_base.png')


def to_np(im):
    return np.asarray(im.convert('RGBA')).copy()


def to_im(a):
    return Image.fromarray(a.astype(np.uint8), 'RGBA')


def main():
    sit = to_np(Image.open(SIT))
    print('坐姿底图 shape =', sit.shape)

    for side in ('L', 'R'):
        rig = _rig.build_arm(sit, side)
        print(f'--- {side} ---')
        print('  shoulder S =', rig['S'], ' elbow E =', rig['E'], ' wrist W =', rig['W'])
        for k in ('upper', 'fore', 'hand'):
            m = rig.get(k)
            print(f'  {k:6s} 像素 = {int(m.sum()) if m is not None else None}')
        print('  站立底图硬编码关节 =', {k: v for k, v in _rig.SIDES[side].items()
                                       if k in ('shoulder', 'elbow', 'wrist')})

    # 摆臂对照图: 6 组角度 (肩/肘/腕)
    rigL = _rig.build_arm(sit, 'L')
    rigR = _rig.build_arm(sit, 'R')
    angles = [
        (0, 0, 0),
        (0, -30, 0),
        (0, -60, 0),
        (0, -90, 0),
        (20, -70, 0),
        (30, -90, 0),
    ]
    tiles = []
    for ang in angles:
        body = sit.copy()
        layers = []
        for side in ('L', 'R'):
            r = rigL if side == 'L' else rigR
            a = ang if side == 'L' else (0, 0, 0)
            b, _fill = _rig.restore_body(body, r['arm'], side, cap_mask=r['nS'],
                                         fill_mask=r.get('fill'))
            body = b
            up, fo, hd, ball = _rig.pose_arm(sit, r, a)
            layers += [up, fo, hd, ball]
        out = _rig.compose(body, layers)
        tiles.append((ang, to_im(out)))

    # 拼成 3x2 对照图
    W, H = tiles[0][1].size
    sheet = Image.new('RGBA', (W * 3, H * 2), (255, 255, 255, 255))
    for i, (ang, im) in enumerate(tiles):
        sheet.paste(im, ((i % 3) * W, (i // 3) * H), im)
    sheet = sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)
    outp = '/tmp/r170_spike_sit_arm.png'
    sheet.save(outp)
    print('对照图已写出:', outp)
    for ang, _ in tiles:
        print('   角度', ang)


if __name__ == '__main__':
    main()
