#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R153 烘焙帧接触表 (contact sheet) — 供人工肉眼复核。

输出两张图:
  evidence_r153_baked/contact_sheet.png     12 张烘焙帧 + 源底图, 全图缩小排列
  evidence_r153_baked/head_zoom.png         头部区域放大 (看局部变形是否自然)

这是**人工复核用**的产物, 判定依据仍是像素测量与测试, 不是"看着像"。
"""
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R153 = os.path.join(ASSETS, 'character_R153')
OUT = os.path.join(CAND, 'evidence_r153_baked')

# 头部区域 (纹理坐标) — 放大复核用
HEAD_BOX = (300, 20, 740, 350)


def fit(im, box_w, box_h):
    sc = min(box_w / im.width, box_h / im.height)
    return im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    report = json.load(open(os.path.join(R153, 'bake_report.json'), encoding='utf-8'))
    items = report['items']

    # ---------- 1. 全图接触表 ----------
    cols, cell = 6, 220
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cell, rows * (cell + 26)), (22, 23, 28))
    draw = ImageDraw.Draw(sheet)
    for i, it in enumerate(items):
        im = Image.open(os.path.join(R153, it['file'])).convert('RGBA')
        bg = Image.new('RGBA', im.size, (26, 28, 34, 255))
        comp = Image.alpha_composite(bg, im).convert('RGB')
        small = fit(comp, cell - 14, cell - 14)
        x0 = (i % cols) * cell + (cell - small.width) // 2
        y0 = (i // cols) * (cell + 26) + (cell - small.height) // 2
        sheet.paste(small, (x0, y0))
        draw.text(((i % cols) * cell + 6, (i // cols) * (cell + 26) + cell + 4),
                  it['file'], fill=(220, 224, 232))
    sheet_path = os.path.join(OUT, 'contact_sheet.png')
    sheet.save(sheet_path)

    # ---------- 2. 头部放大对比 ----------
    base = Image.open(os.path.join(ASSETS, 'character_R138', 'idle', 'idle_00_base.png')).convert('RGBA')
    zoom_items = [it for it in items
                  if it['file'] in ('head_tilt.png', 'head_tilt_other.png', 'head_nod.png',
                                    'head_nod_back.png', 'glance_left.png', 'glance_right.png',
                                    'happy.png', 'blink_half.png', 'blink_closed.png')]
    zcols, zcell = 5, 300
    zrows = (len(zoom_items) + 1 + zcols - 1) // zcols
    zsheet = Image.new('RGB', (zcols * zcell, zrows * (zcell + 24)), (22, 23, 28))
    zdraw = ImageDraw.Draw(zsheet)
    cells = [('base (源底图)', base)] + [(it['file'], Image.open(os.path.join(R153, it['file'])).convert('RGBA'))
                                        for it in zoom_items]
    for i, (label, im) in enumerate(cells):
        bg = Image.new('RGBA', im.size, (26, 28, 34, 255))
        comp = Image.alpha_composite(bg, im).convert('RGB').crop(HEAD_BOX)
        small = fit(comp, zcell - 12, zcell - 12)
        x0 = (i % zcols) * zcell + (zcell - small.width) // 2
        y0 = (i // zcols) * (zcell + 24) + (zcell - small.height) // 2
        zsheet.paste(small, (x0, y0))
        zdraw.text(((i % zcols) * zcell + 6, (i // zcols) * (zcell + 24) + zcell + 3),
                   label, fill=(220, 224, 232))
    zoom_path = os.path.join(OUT, 'head_zoom.png')
    zsheet.save(zoom_path)

    print(f'✅ {sheet_path}')
    print(f'✅ {zoom_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
