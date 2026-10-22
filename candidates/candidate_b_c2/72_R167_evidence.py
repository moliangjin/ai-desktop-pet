#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R167 证据产出 —— 办公打字 / 睡眠被子 两项的修复前后对比 (真实显示尺寸)。

产物 (默认写到 图文工作/R167_修复证据/):
  1. 办公场景 修复前后对比  (200x240 + 256x256 + 手部放大)
  2. 睡眠场景 修复前后对比  (200x240 + 256x256 + 被子放大)
  3. 打字动作两帧对比      (work_1 按键 / work_2 抬起, 200x240 + 放大)
  4. 点击动作池 18 帧逐帧总览 (沿用 R165 成果, 确认未被本轮改动)

"前" = R162/R165 交付的旧素材 (/tmp/r165_before), "后" = R167 当前素材。
"""
import argparse
import importlib.util
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R156 = os.path.join(ASSETS, 'character_R156')
R153 = os.path.join(ASSETS, 'character_R153')
BEFORE_DIR = '/tmp/r167_before'   # R165 交付版 (从 git HEAD 取出) = 本轮的"修复前"
OUTDIR = '/Users/musk123/Downloads/minimax工作文件夹/图文工作/R167_修复证据'

_spec = importlib.util.spec_from_file_location(
    'prev', os.path.join(CAND, '45_R165_scene_preview.py'))
prev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prev)


def font(sz):
    for p in ('/System/Library/Fonts/PingFang.ttc',
              '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def checker(w, h, step=16):
    bg = Image.new('RGBA', (w, h), (250, 250, 252, 255))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, step):
        for x in range(0, w, step):
            if ((x // step) + (y // step)) % 2 == 0:
                d.rectangle([x, y, x + step - 1, y + step - 1], fill=(232, 235, 242, 255))
    return bg


def render(props, char_rel, w, h, floor):
    """按给定道具列表渲染一个场景 (back → 角色 → front)。"""
    import json
    m = json.load(open(os.path.join(ASSETS, 'character_R141_manifest.json'),
                       encoding='utf-8'))
    scene = 'work' if floor == 1001 else 'sleep_breath'
    lib = (m.get('props') or {}).get('library') or {}
    sc = m['props']['scenes'][scene]
    orig_b, orig_f = list(sc.get('back') or []), list(sc.get('front') or [])
    orig_lib = dict(lib)
    try:
        for name, real in props:
            lib[name] = {'file': os.path.abspath(real)}
        sc['back'] = [n for n, _ in props if n.endswith('_b')]
        sc['front'] = [n for n, _ in props if n.endswith('_f')]
        _cr = char_rel if os.path.isabs(char_rel) else os.path.join(ASSETS, char_rel)
        out = prev.compose(scene, w, h, m, frame_override=_cr,
                           out_path=None, checker=False)
    finally:
        m['props']['library'] = orig_lib
        m['props']['scenes'][scene]['back'] = orig_b
        m['props']['scenes'][scene]['front'] = orig_f
    bg = checker(w, h)
    bg.alpha_composite(out)
    return bg.convert('RGB')


def pair(before, after, title, out_path, zoom=3, crop=None):
    """左右并排的"修复前 / 修复后"对比图。"""
    if crop:
        before = before.crop(crop)
        after = after.crop(crop)
    W = before.width + after.width + 16
    H = max(before.height, after.height)
    canvas = Image.new('RGB', (W, H + 26), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    d.text((6, 6), title, fill=(20, 20, 30), font=font(13))
    canvas.paste(before, (0, 26))
    canvas.paste(after, (before.width + 16, 26))
    d.rectangle([0, 26, before.width - 1, 25 + before.height], outline=(200, 60, 60))
    d.rectangle([before.width + 16, 26, W - 1, 25 + after.height], outline=(60, 150, 80))
    canvas = canvas.resize((canvas.width * zoom, canvas.height * zoom), Image.LANCZOS)
    canvas.save(out_path)
    print(f'  📷 {out_path}  {canvas.size}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=OUTDIR)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    od = args.out_dir

    # ---------------- 办公场景 ----------------
    before_work = render(
        [('prop_chair_b', os.path.join(BEFORE_DIR, 'prop_chair.png')),
         ('prop_desk_surface_b', os.path.join(BEFORE_DIR, 'prop_desk_surface.png')),
         ('prop_desk_f', os.path.join(BEFORE_DIR, 'prop_desk.png')),
         ('prop_screen_glow_f', os.path.join(BEFORE_DIR, 'prop_screen_glow.png'))],
        os.path.relpath(os.path.join(BEFORE_DIR, 'work_1.png'), ASSETS), 200, 240, 1001)
    after_work = render(
        [('prop_chair_b', os.path.join(R156, 'prop_chair.png')),
         ('prop_desk_surface_b', os.path.join(R156, 'prop_desk_surface.png')),
         ('prop_keyboard_b', os.path.join(R156, 'prop_keyboard.png')),
         ('prop_desk_f', os.path.join(R156, 'prop_desk.png')),
         ('prop_screen_glow_f', os.path.join(R156, 'prop_screen_glow.png'))],
        'character_R156/work_1.png', 200, 240, 1001)
    pair(before_work, after_work, '办公场景 修复前(R165 交付版) | 修复后(R167)  200x240',
         os.path.join(od, '办公场景_修复前后_200x240.png'))

    # 桌面 + 双手放大 (判定"手是否真的压在键盘上"的关键区域)
    pair(before_work, after_work, '办公场景 桌面/双手放大  修复前(R165) | 修复后(R167)',
         os.path.join(od, '办公场景_双手放大_前后对比.png'), zoom=5, crop=(30, 120, 175, 170))

    # 256x256
    bw2 = render([('prop_chair_b', os.path.join(BEFORE_DIR, 'prop_chair.png')),
                  ('prop_desk_surface_b', os.path.join(BEFORE_DIR, 'prop_desk_surface.png')),
                  ('prop_desk_f', os.path.join(BEFORE_DIR, 'prop_desk.png')),
                  ('prop_screen_glow_f', os.path.join(BEFORE_DIR, 'prop_screen_glow.png'))],
                 os.path.relpath(os.path.join(BEFORE_DIR, 'work_1.png'), ASSETS), 256, 256, 1001)
    aw2 = render([('prop_chair_b', os.path.join(R156, 'prop_chair.png')),
                  ('prop_desk_surface_b', os.path.join(R156, 'prop_desk_surface.png')),
                  ('prop_keyboard_b', os.path.join(R156, 'prop_keyboard.png')),
                  ('prop_desk_f', os.path.join(R156, 'prop_desk.png')),
                  ('prop_screen_glow_f', os.path.join(R156, 'prop_screen_glow.png'))],
                 'character_R156/work_1.png', 256, 256, 1001)
    pair(bw2, aw2, '办公场景 修复前(R165 交付版) | 修复后(R167)  256x256',
         os.path.join(od, '办公场景_修复前后_256x256.png'))

    # ---------------- 打字动作两帧 ----------------
    w1 = render([('prop_chair_b', os.path.join(R156, 'prop_chair.png')),
                 ('prop_desk_surface_b', os.path.join(R156, 'prop_desk_surface.png')),
                 ('prop_keyboard_b', os.path.join(R156, 'prop_keyboard.png')),
                 ('prop_desk_f', os.path.join(R156, 'prop_desk.png')),
                 ('prop_screen_glow_f', os.path.join(R156, 'prop_screen_glow.png'))],
                'character_R156/work_1.png', 200, 240, 1001)
    w2 = render([('prop_chair_b', os.path.join(R156, 'prop_chair.png')),
                 ('prop_desk_surface_b', os.path.join(R156, 'prop_desk_surface.png')),
                 ('prop_keyboard_b', os.path.join(R156, 'prop_keyboard.png')),
                 ('prop_desk_f', os.path.join(R156, 'prop_desk.png')),
                 ('prop_screen_glow_f', os.path.join(R156, 'prop_screen_glow.png'))],
                'character_R156/work_2.png', 200, 240, 1001)
    pair(w1, w2, '打字动作 work_1(手指按下) | work_2(手指抬起)  200x240',
         os.path.join(od, '办公场景_打字动作两帧_200x240.png'))
    pair(w1, w2, '打字动作 双手放大  按下 | 抬起',
         os.path.join(od, '办公场景_打字动作_双手放大.png'), zoom=6, crop=(45, 130, 130, 165))

    # ---------------- 睡眠场景 ----------------
    before_sleep = render(
        [('prop_bed_b', os.path.join(BEFORE_DIR, 'prop_bed.png')),
         ('prop_moon_b', os.path.join(BEFORE_DIR, 'prop_moon.png')),
         ('prop_quilt_f', os.path.join(BEFORE_DIR, 'prop_quilt.png'))],
        'character_R153/sleep_breath_in.png', 200, 240, 818)
    after_sleep = render(
        [('prop_bed_b', os.path.join(R156, 'prop_bed.png')),
         ('prop_moon_b', os.path.join(R156, 'prop_moon.png')),
         ('prop_quilt_f', os.path.join(R156, 'prop_quilt.png'))],
        'character_R153/sleep_breath_in.png', 200, 240, 818)
    pair(before_sleep, after_sleep, '睡眠场景 修复前(R165 灰蓝硬壳) | 修复后(R167 浅蓝蓬松)  200x240',
         os.path.join(od, '睡眠场景_修复前后_200x240.png'))
    pair(before_sleep, after_sleep, '睡眠场景 被子/床放大  修复前 | 修复后',
         os.path.join(od, '睡眠场景_被子床放大_前后对比.png'), zoom=5, crop=(0, 110, 200, 240))

    bs2 = render([('prop_bed_b', os.path.join(BEFORE_DIR, 'prop_bed.png')),
                  ('prop_moon_b', os.path.join(BEFORE_DIR, 'prop_moon.png')),
                  ('prop_quilt_f', os.path.join(BEFORE_DIR, 'prop_quilt.png'))],
                 'character_R153/sleep_breath_in.png', 256, 256, 818)
    as2 = render([('prop_bed_b', os.path.join(R156, 'prop_bed.png')),
                  ('prop_moon_b', os.path.join(R156, 'prop_moon.png')),
                  ('prop_quilt_f', os.path.join(R156, 'prop_quilt.png'))],
                 'character_R153/sleep_breath_in.png', 256, 256, 818)
    pair(bs2, as2, '睡眠场景 修复前 | 修复后  256x256',
         os.path.join(od, '睡眠场景_修复前后_256x256.png'))

    # ---------------- 点击动作池逐帧总览 (确认本轮没动点击动作) ----------------
    imgs = []
    for a in ('cheer_wave', 'cheer_hands_up', 'cheer_heart',
              'cheer_clap', 'cheer_jump', 'cheer_tilt'):
        for i in range(3):
            im = Image.open(os.path.join(ASSETS, 'character_R158', f'{a}_{i}.png')).convert('RGBA')
            imgs.append((f'{a}_{i}', im.resize((200, 240), Image.LANCZOS)))
    cols, rows = 6, 3
    sheet = Image.new('RGB', (cols * 200, rows * 240), (250, 250, 252))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(imgs):
        bg = checker(200, 240)
        bg.alpha_composite(im)
        bg = bg.convert('RGB')
        sheet.paste(bg, ((i % cols) * 200, (i // cols) * 240))
        d.text(((i % cols) * 200 + 4, (i // cols) * 240 + 4), name,
               fill=(40, 40, 60), font=font(11))
    p = os.path.join(od, '点击动作池_逐帧总览_R167_200x240.png')
    sheet.save(p)
    print(f'  📷 {p}  {sheet.size}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
