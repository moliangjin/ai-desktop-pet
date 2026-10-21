#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 接触表: 把 18 帧按真实显示尺寸 (200x240) 拼成一张总览, 供肉眼判读。

用法: python3 59_R165_contact_sheet.py --dir assets/character_R158 --out /tmp/xxx.png
"""
import argparse
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--w', type=int, default=200)
    ap.add_argument('--h', type=int, default=240)
    ap.add_argument('--zoom', type=int, default=1)
    ap.add_argument('--label-h', type=int, default=16)
    ap.add_argument('--only', default=None, help='逗号分隔的动作名过滤')
    a = ap.parse_args()

    files = sorted(f for f in os.listdir(a.dir) if f.endswith('.png') and f.startswith('cheer_'))
    if a.only:
        keep = set(a.only.split(','))
        files = [f for f in files if f.rsplit('_', 1)[0] in keep]
    if not files:
        raise SystemExit('no frames')

    cols = 6
    rows = (len(files) + cols - 1) // cols
    cw, ch = a.w * a.zoom, (a.h + a.label_h) * a.zoom
    sheet = Image.new('RGBA', (cols * cw, rows * ch), (245, 245, 248, 255))
    d = ImageDraw.Draw(sheet)
    for i, fn in enumerate(files):
        im = Image.open(os.path.join(a.dir, fn)).convert('RGBA')
        # 运行时是等比缩放 + 贴底: 1024 -> 200x240
        im = im.resize((a.w, a.h), Image.LANCZOS)
        if a.zoom > 1:
            im = im.resize((a.w * a.zoom, a.h * a.zoom), Image.LANCZOS)
        # 棋盘底
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        sq = 10
        dd = ImageDraw.Draw(bg)
        for yy in range(0, im.height, sq):
            for xx in range(0, im.width, sq):
                if ((yy // sq) + (xx // sq)) % 2 == 0:
                    dd.rectangle([xx, yy, xx + sq - 1, yy + sq - 1], fill=(225, 228, 234, 255))
        bg.alpha_composite(im)
        cx = (i % cols) * cw
        cy = (i // cols) * ch
        sheet.alpha_composite(bg, (cx, cy))
        d.text((cx + 4, cy + a.h * a.zoom + 3), fn.replace('.png', ''), fill=(30, 30, 40, 255))
        d.rectangle([cx, cy, cx + cw - 1, cy + ch - 1], outline=(170, 175, 185, 255))
    sheet.save(a.out)
    print(f'{a.out}  {sheet.size}  frames={len(files)}')


if __name__ == '__main__':
    main()
