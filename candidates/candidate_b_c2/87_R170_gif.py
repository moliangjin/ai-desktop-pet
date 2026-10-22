#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R170 可观看 GIF / 总览图 —— 从**真实 Electron 采集**的帧合成。

诚实说明 (沿用 R158 的口径):
  · GIF 里的像素 = 真实运行时 `webContents.capturePage` 的像素, 未做任何重绘
  · 每个 GIF 的帧时长 = 该场景**实际采集间隔**, 播放速度与真实运行时一致
  · 标题层是后加的说明文字, 不改变角色像素

输入: evidence_r170_preview/ (真实采集) + preview_meta.json
输出: evidence_r170_gifs/
    · R170_scene_eat_fruit.gif  吃水果完整动作 (伸手拿 → 举到嘴边 → 咬 → 嚼 → 满足)
    · R170_scene_work.gif       电脑办公打字
    · R170_eat_fruit_overview.png  吃水果 5 帧逐帧总览 (放大)
    · R170_work_overview.png      办公打字 2 帧对比 (放大)
    · R170_scenes_overview.png   两场景并排总览

用法: python3 87_R170_gif.py --preview-dir evidence_r170_preview --out-dir evidence_r170_gifs
"""
import argparse
import importlib.util
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE

_spec = importlib.util.spec_from_file_location(
    'g158', os.path.join(CAND, '40_R158_preview_gif.py'))
g158 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g158)

ACCENT = (216, 62, 92, 255)
TEXT = (24, 26, 36, 255)


def cjk_font(size=13):
    return g158.cjk_font(size)


def zoom_tile(im, k=3):
    """放大一帧 (保持像素, 用 NEAREST 免得糊)。"""
    return im.resize((im.size[0] * k, im.size[1] * k), Image.NEAREST)


def scene_overview(meta, out_dir, scene, label, n=5, k=3, name=None):
    """取该场景里差异最大的 n 帧做总览 (真实采集像素)。"""
    fr = g158.load_scene(meta, scene)
    if not fr:
        print(f'  ⚠️  {scene}: 无采集帧, 跳过')
        return None
    base = fr[0][0]
    scored = []
    for idx, (im, _dx, _wx) in enumerate(fr):
        d = sum(abs(a - b) for a, b in zip(im.tobytes(), base.tobytes())) \
            / (im.size[0] * im.size[1] * 4)
        scored.append((d, idx, im))
    scored.sort(key=lambda t: -t[0])
    picks = [t[2] for t in scored[:n]]
    picks.sort(key=lambda im: sum(abs(a - b) for a, b in zip(im.tobytes(), base.tobytes())))
    tw, th = picks[0].size
    cw, ch = tw * k + 12, th * k + 26
    sheet = Image.new('RGB', (cw * len(picks) + 12, ch + 34), (252, 252, 254))
    d = ImageDraw.Draw(sheet)
    d.text((8, 6), label, fill=ACCENT, font=cjk_font(14))
    for c, im in enumerate(picks):
        x = 8 + c * cw
        sheet.paste(zoom_tile(im, k).convert('RGB'), (x, 32))
        d.rectangle([x - 1, 31, x + tw * k, 31 + th * k], outline=(150, 160, 180))
    p = os.path.join(out_dir, name or f'R170_{scene}_overview.png')
    sheet.save(p)
    print(f'  ✅ {os.path.basename(p)}  ({len(picks)} 帧 ×{k} 放大)')
    return p


def two_scenes_sheet(meta, out_dir):
    """办公 + 吃水果 并排总览 (真实采集像素)。"""
    a = g158.load_scene(meta, 'scene_work')
    b = g158.load_scene(meta, 'scene_eat_fruit')
    if not a or not b:
        print('  ⚠️  缺 scene_work / scene_eat_fruit 采集帧, 跳过两场景总览')
        return None
    picks = [a[0][0], a[len(a) // 2][0], b[0][0], b[len(b) // 2][0]]
    labels = ['办公 · 起始', '办公 · 打字中', '吃水果 · 起始', '吃水果 · 咬一口']
    k = 2
    tw, th = picks[0].size
    cw, ch = tw * k + 12, th * k + 24
    sheet = Image.new('RGB', (cw * len(picks) + 12, ch + 34), (252, 252, 254))
    d = ImageDraw.Draw(sheet)
    d.text((8, 6), 'R170 两个新场景 — 真实 Electron 运行采集像素 (200×240 窗口)',
           fill=ACCENT, font=cjk_font(14))
    for c, im in enumerate(picks):
        x = 8 + c * cw
        sheet.paste(zoom_tile(im, k).convert('RGB'), (x, 32))
        d.text((x + 2, 32 + th * k + 4), labels[c], fill=(110, 116, 132), font=cjk_font(11))
    p = os.path.join(out_dir, 'R170_scenes_overview.png')
    sheet.save(p)
    print(f'  ✅ {os.path.basename(p)}')
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview-dir', default='evidence_r170_preview')
    ap.add_argument('--out-dir', default='evidence_r170_gifs')
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    meta = g158.load_meta(args.preview_dir)
    print('R170 GIF / 总览图产出:')

    # 吃水果: 5 帧一循环, 采集间隔 160ms
    g158.make_gif(meta, args.out_dir, 'scene_eat_fruit',
                  'R170 吃水果 eat_fruit (伸手拿水果 → 送到嘴边 → 低头咬一口 → 咀嚼 → 满足地笑)',
                  160, prefix='R170')
    # 办公: 2 帧一循环, 采集间隔 280ms
    g158.make_gif(meta, args.out_dir, 'scene_work',
                  'R170 电脑办公 work (坐在电脑前双手打字)', 280, prefix='R170')

    scene_overview(meta, args.out_dir, 'scene_eat_fruit',
                   'R170 吃水果 5 帧逐帧 (真实运行采集)', n=5, k=3,
                   name='R170_eat_fruit_overview.png')
    scene_overview(meta, args.out_dir, 'scene_work',
                   'R170 办公打字 2 帧 (真实运行采集)', n=2, k=3,
                   name='R170_work_overview.png')
    two_scenes_sheet(meta, args.out_dir)


if __name__ == '__main__':
    main()
