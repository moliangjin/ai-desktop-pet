#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R167 spike: 验证"桌面加深 + 剪掉下半身 + 键盘上桌"的重构能否在 200×240 成立。

只做可行性验证, 不是最终生成器。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
S = 1024
SIT = os.path.join(CAND, 'assets', 'character_R138', 'sleep_enter', 'sleep_enter_01_sit.png')

# 坐姿帧实测: 手臂保留区 (腕带 + 手), 来自 67 诊断
KEEP = [
    (368, 536, 446, 600),    # L 腕带
    (330, 556, 430, 650),    # L 手
    (492, 536, 566, 604),    # R 腕带
    (428, 554, 550, 650),    # R 手
]
CUT_Y = 592                 # 桌面远沿: 这条线以下的大腿/腿被剪掉


def erase_lower_body(im):
    a = np.asarray(im).copy()
    keep = np.zeros(a.shape[:2], bool)
    for (x0, y0, x1, y1) in KEEP:
        keep[y0:y1, x0:x1] = True
    # 手/腕带范围内的像素全部保留 (含描边)
    cut = np.zeros(a.shape[:2], bool)
    cut[CUT_Y:, :] = True
    kill = cut & ~keep
    a[kill] = 0
    return Image.fromarray(a, 'RGBA')


def make_desktop(desk_far=556, desk_near=672,
                 x_far=(318, 762), x_near=(278, 824)):
    """透视台面: 远沿窄、近沿宽 (俯视一点点)。"""
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    quad = [(x_far[0], desk_far), (x_far[1], desk_far),
            (x_near[1], desk_near), (x_near[0], desk_near)]
    d.polygon(quad, fill=(232, 216, 190, 255))
    # 顶面高光带 (远沿略亮)
    d.polygon([(x_far[0], desk_far), (x_far[1], desk_far),
               (x_far[1], desk_far + 16), (x_far[0], desk_far + 16)],
              fill=(244, 231, 208, 255))
    d.line([quad[0], quad[1]], fill=(120, 98, 72, 255), width=4)
    d.line([quad[3], quad[2]], fill=(120, 98, 72, 255), width=4)
    return im


def make_keyboard(y_top=572, y_bot=650, x_top=(352, 566), x_bot=(326, 596)):
    """透视键盘: 远沿窄近沿宽 + 键位网格。"""
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    quad = [(x_top[0], y_top), (x_top[1], y_top), (x_bot[1], y_bot), (x_bot[0], y_bot)]
    d.polygon(quad, fill=(205, 212, 224, 255), outline=(88, 98, 116, 255), width=3)
    rows = 4
    for i in range(rows):
        t0 = i / rows
        t1 = (i + 1) / rows
        y0 = y_top + (y_bot - y_top) * t0
        y1 = y_top + (y_bot - y_top) * t1
        d.line([(x_top[0] + (x_bot[0] - x_top[0]) * t0, y0),
                (x_top[1] + (x_bot[1] - x_top[1]) * t0, y0)],
               fill=(150, 160, 178, 255), width=2)
    # 键位竖线
    for i in range(1, 13):
        t = i / 13.0
        d.line([(x_top[0] + (x_bot[0] - x_top[0]) * t, y_top),
                (x_bot[0] + (x_bot[1] - x_bot[0]) * t, y_bot)],
               fill=(160, 170, 188, 255), width=2)
    return im


def main():
    import importlib.util
    spec = importlib.util.spec_from_file_location('sp', os.path.join(CAND, '45_R165_scene_preview.py'))
    sp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sp)
    import json
    m = json.load(open(os.path.join(CAND, 'assets', 'character_R141_manifest.json')))

    outdir = os.path.join(CAND, 'assets', 'character_R156')
    desk = make_desktop()
    desk.save('/tmp/spike_desk.png')
    kb = make_keyboard()
    kb.save('/tmp/spike_kb.png')

    lib = (m.get('props') or {}).get('library') or {}
    lib['prop_keyboard'] = {'file': 'character_R156/prop_keyboard.png'}
    lib['prop_desk_surface'] = {'file': 'character_R156/prop_desk_surface.png'}
    m['props']['library'] = lib
    m['props']['scenes']['work']['back'] = ['prop_chair', 'prop_desk_surface', 'prop_keyboard']
    m['props']['scenes']['work']['front'] = ['prop_desk']

    # 角色帧: 剪掉下半身
    sit = Image.open(SIT).convert('RGBA')
    cut = erase_lower_body(sit)
    cut.save('/tmp/spike_char.png')

    # 复用 45 脚本的 compose, 但角色帧换成剪过的
    char_rel = 'character_R156/work_1.png'
    cut.save(os.path.join(outdir, '_spike_work.png'))
    # 临时把 manifest 指向剪过的帧
    acts = ((m.get('action_library') or {}).get('actions')) or {}
    acts['work']['frames'] = ['character_R156/_spike_work.png']
    sp.compose('work', 200, 240, m, out_path='/tmp/r167_spike2.png')

    im = Image.open('/tmp/r167_spike2.png').convert('RGB')
    im.resize((600, 720), Image.LANCZOS).save('/tmp/r167_spike2_3x.png')
    im.crop((20, 80, 180, 180)).resize((160 * 5, 100 * 5), Image.LANCZOS).save('/tmp/r167_spike2_zoom.png')
    print('✅ /tmp/r167_spike2.png')


if __name__ == '__main__':
    main()
