#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 证据产出 —— 点击动作逐帧总览 + 办公/睡眠场景修复前后对比。

产物 (默认写到 图文工作/R165_修复证据/):
  1. 点击动作池 18 帧**真实显示尺寸**(200x240) 逐帧总览 (新素材)
  2. 同上 (R162 旧素材) —— 用于"修复前后"对照
  3. 逐动作前后对照条 (6 个动作)
  4. 办公场景 / 睡眠场景 修复前后对比 (200x240 + 256x256 + 1024 全分辨率)
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
MANIFEST = os.path.join(ASSETS, 'character_R141_manifest.json')
REPO = os.path.abspath(os.path.join(CAND, '..', '..'))
OUTDIR = '/Users/musk123/Downloads/minimax工作文件夹/图文工作/R165_修复证据'
BEFORE_DIR = '/tmp/r165_before'

_spec = importlib.util.spec_from_file_location('prev', os.path.join(CAND, '45_R165_scene_preview.py'))
prev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prev)

_spec2 = importlib.util.spec_from_file_location('bake', os.path.join(CAND, '37_R158_action_bake.py'))
bake = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(bake)

CLICK_ACTIONS = ['cheer_wave', 'cheer_hands_up', 'cheer_heart', 'cheer_clap',
                 'cheer_jump', 'cheer_tilt']


def font(sz):
    for p in ('/System/Library/Fonts/PingFang.ttc',
              '/System/Library/Fonts/Helvetica.ttc',
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


def render_frame(rel, w, h, m, ground_row=None):
    """把一张角色帧按运行时布局渲染到 w x h 画布 (含地面行/锚点)。"""
    scale = prev.build_scale(m, w, h)
    ground_y = h - prev.MARGIN
    ay = prev.ANCHOR_Y * prev.TEX
    if ground_row is None:
        ground_row = prev.alpha_bbox(os.path.join(ASSETS, rel))[3]
    img = Image.open(os.path.join(ASSETS, rel)).convert('RGBA')
    sw = max(1, int(round(prev.TEX * scale)))
    img = img.resize((sw, sw), Image.LANCZOS)
    left = int(round(w / 2 - 512 * scale))
    top = int(round(ground_y + (prev.TEX - ground_row) * scale - sw))
    canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    dx0, dy0 = max(0, left), max(0, top)
    dx1, dy1 = min(w, left + sw), min(h, top + sw)
    if dx1 > dx0 and dy1 > dy0:
        canvas.alpha_composite(img.crop((dx0 - left, dy0 - top, dx1 - left, dy1 - top)),
                               (dx0, dy0))
    out = checker(w, h)
    out.alpha_composite(canvas)
    return out.convert('RGB')


def extract_before():
    """从 git (R162 归档 commit) 取出旧素材, 作为"修复前"证据。"""
    os.makedirs(BEFORE_DIR, exist_ok=True)
    head = subprocess.check_output(['git', '-C', REPO, 'rev-parse', 'HEAD']).decode().strip()
    paths = []
    for a in CLICK_ACTIONS:
        for i in range(3):
            paths.append(f'candidates/candidate_b_c2/assets/character_R158/{a}_{i}.png')
    for i in (1, 2):
        paths.append(f'candidates/candidate_b_c2/assets/character_R156/work_{i}.png')
    got = []
    for p in paths:
        dst = os.path.join(BEFORE_DIR, os.path.basename(p))
        r = subprocess.run(['git', '-C', REPO, 'show', f'{head}:{p}'],
                           stdout=open(dst, 'wb'), stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            got.append(os.path.basename(p))
    # 旧道具: 用 worker 备份的 R162 版本
    oldprops = '/Users/musk123/Downloads/minimax工作文件夹/图文工作/R165_场景修复/old'
    if os.path.isdir(oldprops):
        for fn in os.listdir(oldprops):
            src = os.path.join(oldprops, fn)
            dst = os.path.join(BEFORE_DIR, fn)
            with open(src, 'rb') as fi, open(dst, 'wb') as fo:
                fo.write(fi.read())
            got.append(fn)
    print(f'  ✅ 取到 {len(got)} 个旧素材 (git {head[:8]}) → {BEFORE_DIR}')
    return got


def sheet(frames, w, h, out, cols, title, label_font=None):
    """frames = [(label, PIL.Image)] → 拼图。"""
    n = len(frames)
    rows = (n + cols - 1) // cols
    pad = 8
    head_h = 34 if title else 0
    W = cols * (w + pad) + pad
    H = rows * (h + pad) + pad + head_h
    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    f = label_font or font(13)
    if title:
        d.text((pad, 8), title, fill=(20, 20, 24), font=font(18))
    for i, (lab, im) in enumerate(frames):
        r, c = divmod(i, cols)
        x = pad + c * (w + pad)
        y = head_h + pad + r * (h + pad)
        canvas.paste(im, (x, y))
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=(200, 204, 212))
        d.text((x + 4, y + h + 1), lab, fill=(40, 40, 48), font=f)
    canvas.save(out)
    print(f'  📷 {out}  ({W}x{H})')
    return out


def compose_scene_with(props, char_rel, floor, w, h, m, ground_row=None):
    """用**指定的**道具/角色帧合成一个场景 (用于"修复前")。"""
    scale = prev.build_scale(m, w, h)
    ground_y = h - prev.MARGIN
    ay = prev.ANCHOR_Y * prev.TEX
    canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))

    def blit(path, ground_row_):
        img = Image.open(path).convert('RGBA')
        sw = max(1, int(round(prev.TEX * scale)))
        img = img.resize((sw, sw), Image.LANCZOS)
        left = int(round(w / 2 - 512 * scale))
        top = int(round(ground_y + (prev.TEX - ground_row_) * scale - sw))
        dx0, dy0 = max(0, left), max(0, top)
        dx1, dy1 = min(w, left + sw), min(h, top + sw)
        if dx1 > dx0 and dy1 > dy0:
            canvas.alpha_composite(img.crop((dx0 - left, dy0 - top, dx1 - left, dy1 - top)),
                                   (dx0, dy0))

    for p in props.get('back', []):
        blit(p, floor)
    blit(char_rel, ground_row if ground_row is not None else floor)
    for p in props.get('front', []):
        blit(p, floor)
    out = checker(w, h)
    out.alpha_composite(canvas)
    return out.convert('RGB')


def side_by_side(before, after, out, caption_before, caption_after, w=None, h=None):
    """左=修复前 右=修复后。"""
    bw, bh = before.size
    aw, ah = after.size
    W = bw + aw + 24
    H = max(bh, ah) + 30
    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    canvas.paste(before, (0, 26))
    canvas.paste(after, (bw + 24, 26))
    d.rectangle([0, 26, bw - 1, 26 + bh - 1], outline=(200, 204, 212))
    d.rectangle([bw + 24, 26, bw + 24 + aw - 1, 26 + ah - 1], outline=(200, 204, 212))
    d.text((2, 5), caption_before, fill=(170, 60, 60), font=font(14))
    d.text((bw + 26, 5), caption_after, fill=(40, 110, 70), font=font(14))
    canvas.save(out)
    print(f'  📷 {out}  ({W}x{H})')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=OUTDIR)
    ap.add_argument('--sizes', default='200x240,256x256')
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    m = json.load(open(MANIFEST, encoding='utf-8'))

    print('== 1. 取出修复前(R162)素材 ==')
    extract_before()

    # ---------- 2. 点击动作逐帧总览 (新 / 旧) ----------
    for tag, d in (('新素材', os.path.join(ASSETS, 'character_R158')), ('R162旧素材', BEFORE_DIR)):
        frames = []
        for a in CLICK_ACTIONS:
            for i in range(3):
                p = os.path.join(d, f'{a}_{i}.png')
                if not os.path.exists(p):
                    continue
                # 新素材在 assets/character_R158/ 下 (相对 ASSETS 渲染);
                # R162 旧素材是临时目录里的绝对路径 ⇒ 走 render_frame_abs
                if os.path.abspath(d).startswith(os.path.abspath(ASSETS)):
                    frames.append((f'{a}_{i}', render_frame(
                        os.path.join('character_R158', f'{a}_{i}.png'),
                        200, 240, m, ground_row=987)))
                else:
                    frames.append((f'{a}_{i}', render_frame_abs(p, 200, 240, m, 987)))
        sheet(frames, 200, 240,
              os.path.join(args.out_dir, f'点击动作池_逐帧总览_{tag}_200x240.png'),
              6, f'点击动作池 6 动作 × 3 帧 逐帧总览 ({tag}, 真实显示尺寸 200x240)')

    # ---------- 3. 逐动作前后对照 ----------
    for a in CLICK_ACTIONS:
        fb, fa = [], []
        for i in range(3):
            op = os.path.join(BEFORE_DIR, f'{a}_{i}.png')
            np_ = os.path.join(ASSETS, 'character_R158', f'{a}_{i}.png')
            if os.path.exists(op) and os.path.exists(np_):
                fb.append((f'{a}_{i}', render_frame_abs(op, 200, 240, m, 987)))
                fa.append((f'{a}_{i}', render_frame_abs(np_, 200, 240, m, 987)))
        if not fb:
            continue
        sheet(fb + fa, 200, 240,
              os.path.join(args.out_dir, f'点击动作_{a}_修复前后_200x240.png'),
              6, f'{a} 修复前(上排红框侧) / 修复后(下排)')

    # ---------- 4. 办公 / 睡眠场景 前后对比 ----------
    props = m['props']
    work_scene = props['scenes']['work']
    sleep_scene = props['scenes']['sleep_breath']
    old_work_props = {
        'back': [os.path.join(BEFORE_DIR, 'prop_chair.png')],
        'front': [os.path.join(BEFORE_DIR, 'prop_desk.png'),
                  os.path.join(BEFORE_DIR, 'prop_screen_glow.png')],
    }
    old_sleep_props = {
        'back': [os.path.join(BEFORE_DIR, 'prop_bed.png'),
                 os.path.join(BEFORE_DIR, 'prop_moon.png')],
        'front': [os.path.join(BEFORE_DIR, 'prop_quilt.png')],
    }
    for size in args.sizes.split(','):
        w, h = (int(x) for x in size.split('x'))
        # 办公
        before = compose_scene_with(
            old_work_props, os.path.join(BEFORE_DIR, 'work_1.png'), 1001, w, h, m, 1001)
        after = prev.compose('work', w, h, m, out_path=None, checker=True)
        side_by_side(before, after.convert('RGB'),
                     os.path.join(args.out_dir, f'办公场景_修复前后_{size}.png'),
                     f'修复前 (R162: 屏幕朝观众+实心桌裙+手在腿上)',
                     f'修复后 (R165: 屏幕朝角色+桌腿+双手压在台面上)')
        # 睡眠
        before = compose_scene_with(
            old_sleep_props, os.path.join(ASSETS, 'character_R153', 'sleep_breath_in.png'),
            818, w, h, m, 818)
        after = prev.compose('sleep_breath', w, h, m, out_path=None, checker=True)
        side_by_side(before, after.convert('RGB'),
                     os.path.join(args.out_dir, f'睡眠场景_修复前后_{size}.png'),
                     '修复前 (R162: 被子是硬网格直线+摆在旁边)',
                     '修复后 (R165: 被子沿身体轮廓+翻折亮边+柔化左缘)')
    return 0


def render_frame_abs(path, w, h, m, ground_row=None):
    """渲染绝对路径下的一张角色帧。"""
    scale = prev.build_scale(m, w, h)
    ground_y = h - prev.MARGIN
    if ground_row is None:
        ground_row = prev.alpha_bbox(path)[3]
    img = Image.open(path).convert('RGBA')
    sw = max(1, int(round(prev.TEX * scale)))
    img = img.resize((sw, sw), Image.LANCZOS)
    left = int(round(w / 2 - 512 * scale))
    top = int(round(ground_y + (prev.TEX - ground_row) * scale - sw))
    canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    dx0, dy0 = max(0, left), max(0, top)
    dx1, dy1 = min(w, left + sw), min(h, top + sw)
    if dx1 > dx0 and dy1 > dy0:
        canvas.alpha_composite(img.crop((dx0 - left, dy0 - top, dx1 - left, dy1 - top)),
                               (dx0, dy0))
    out = checker(w, h)
    out.alpha_composite(canvas)
    return out.convert('RGB')


if __name__ == '__main__':
    raise SystemExit(main())
