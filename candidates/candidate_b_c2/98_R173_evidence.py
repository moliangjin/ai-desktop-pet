#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R173 证据制作 —— 修复前后对比 / 完整坐姿截图 / 透视示意图 / 办公打字 GIF。

诚实说明 (沿用 R158/R170/R172 的口径):
  · GIF 里的像素 = **真实 Electron 运行时** `webContents.capturePage` 的像素, 未做任何重绘;
  · GIF 的帧时长 = 该场景**实际采集间隔**, 播放速度与真实运行时一致;
  · 前后对比图里的"修复前"用 **R172 交付版真实素材**
    (character_R172/work_1.png + R172 的 chair/monitor 道具), 用**同一套、
    与运行时一致**的合成算法渲染;
  · 标题层与示意图的箭头/标注是后加的说明, 不改变角色像素。

输入:
  --preview-dir  真实 Electron 采集目录 (含 preview_meta.json)
输出:
  --out-gifs     evidence_r173_gifs/
  --out-compare  evidence_r173_compare/
"""
import argparse
import copy
import importlib.util
import json
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
MANIFEST = os.path.join(ASSETS, 'character_R141_manifest.json')

_spec = importlib.util.spec_from_file_location(
    'prev', os.path.join(CAND, '45_R165_scene_preview.py'))
_prev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_prev)

_spec2 = importlib.util.spec_from_file_location(
    'g158', os.path.join(CAND, '40_R158_preview_gif.py'))
g158 = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(g158)

ACCENT = (216, 62, 92, 255)
TEXT = (24, 26, 36, 255)
BG = (248, 249, 252)

# R172 交付版 (修复前) 的办公场景
BEFORE_SCENE = {
    'floor_tex_y': 1001,
    'back': ['prop_office_chair'],
    'front': ['prop_office_monitor'],
}
BEFORE_FRAMES = ['character_R172/work_1.png', 'character_R172/work_2.png']

# R173 的关键几何 (1024 纹理空间, 与 95_ 烘焙脚本同口径)
SCREEN_QUAD = [(195, 395), (330, 315), (372, 630), (215, 570)]
KEY_QUAD = [(330, 566), (548, 600), (532, 656), (312, 616)]
GROUND_Y = 1001
MARGIN = 4


def before_manifest(m):
    b = copy.deepcopy(m)
    b['props']['scenes']['work'] = dict(BEFORE_SCENE)
    b['action_library']['actions']['work']['frames'] = list(BEFORE_FRAMES)
    b['action_library']['actions']['work']['ground_tex_y'] = 1001
    return b


def render(m, scene, w, h, frame=None):
    canvas = _prev.compose(scene, w, h, m, frame_override=frame, checker=False)
    bg = Image.new('RGBA', canvas.size, BG + (255,))
    bg.alpha_composite(canvas)
    return bg.convert('RGB')


def label_tile(im, text, zoom=3, pad=10):
    z = im.resize((im.size[0] * zoom, im.size[1] * zoom), Image.LANCZOS)
    out = Image.new('RGB', (z.size[0] + pad * 2, z.size[1] + pad * 2 + 22), (255, 255, 255))
    d = ImageDraw.Draw(out)
    d.text((pad, pad), text, fill=TEXT, font=g158.cjk_font(13))
    out.paste(z, (pad, pad + 22))
    d.rectangle([0, 0, out.size[0] - 1, out.size[1] - 1], outline=(214, 218, 228), width=1)
    return out


def side_by_side(a, b, title_a, title_b, out_path, zoom=3, crop=None, header=None):
    ta, tb = a, b
    if crop:
        ta = a.crop(crop)
        tb = b.crop(crop)
    la = label_tile(ta, title_a, zoom)
    lb = label_tile(tb, title_b, zoom)
    w = la.size[0] + lb.size[0] + 24
    h = max(la.size[1], lb.size[1]) + 34
    out = Image.new('RGB', (w, h), (255, 255, 255))
    d = ImageDraw.Draw(out)
    d.text((12, 8), header or f'R173 办公场景 修复前 / 修复后  ({zoom}x)',
           fill=ACCENT, font=g158.cjk_font(15))
    out.paste(la, (8, 30))
    out.paste(lb, (la.size[0] + 16, 30))
    out.save(out_path)
    print(f'  📷 {out_path}')


def scene_gif(preview_dir, scene, out_path, interval_ms, max_frames=None, zoom=2):
    meta = json.load(open(os.path.join(preview_dir, 'preview_meta.json'), encoding='utf-8'))
    frames = meta.get(scene) or []
    if not frames:
        print(f'  ⚠️  {scene}: 无采集帧')
        return None
    if max_frames:
        frames = frames[:max_frames]
    ims = []
    for rec in frames:
        im = Image.open(rec['file']).convert('RGBA')
        bg = Image.new('RGBA', im.size, BG + (255,))
        bg.alpha_composite(im)
        ims.append(bg.convert('RGB').resize((im.size[0] * zoom, im.size[1] * zoom),
                                            Image.LANCZOS))
    ims[0].save(out_path, save_all=True, append_images=ims[1:],
                duration=interval_ms, loop=0, disposal=2)
    print(f'  🎞️ {out_path}  ({len(ims)} 帧, {interval_ms}ms/帧)')
    return ims


# ---------------------------------------------------------------- 透视示意图
def perspective_diagram(m, out_path, w=200, h=240, zoom=4):
    """显示器朝向 / 人物视线 / 键盘位置 示意 (画在真实合成画面上)。"""
    base = render(m, 'work', w, h)
    canvas = base.resize((w * zoom, h * zoom), Image.LANCZOS)
    d = ImageDraw.Draw(canvas, 'RGBA')
    sc = _prev.build_scale(m, w, h)
    ground_y = h - MARGIN

    def to_canvas(p):
        return (w / 2 + (p[0] - 512) * sc, ground_y - (GROUND_Y - p[1]) * sc)

    def poly(quad, color, width=2, fill=None):
        pts = [to_canvas(p) for p in quad]
        pts = [(x * zoom, y * zoom) for x, y in pts]
        if fill:
            d.polygon(pts, fill=fill)
        d.line(list(pts) + [pts[0]], fill=color, width=width)

    font = g158.cjk_font(13)
    font_s = g158.cjk_font(11)

    # 屏幕四边形 (橙)
    poly(SCREEN_QUAD, (236, 138, 30, 255), 3, (236, 138, 30, 26))
    # 键盘四边形 (绿)
    poly(KEY_QUAD, (28, 150, 92, 255), 3, (28, 150, 92, 30))

    # 屏幕朝向箭头: 从屏幕中心指向"角色"方向 (右)
    sc_c = to_canvas((sum(p[0] for p in SCREEN_QUAD) / 4,
                      sum(p[1] for p in SCREEN_QUAD) / 4))
    arrow_from = (sc_c[0] * zoom, sc_c[1] * zoom)
    arrow_to = (arrow_from[0] + 62, arrow_from[1] - 6)
    d.line([arrow_from, arrow_to], fill=(236, 138, 30, 255), width=4)
    d.polygon([(arrow_to[0] + 10, arrow_to[1]),
               (arrow_to[0] - 6, arrow_to[1] - 6),
               (arrow_to[0] - 6, arrow_to[1] + 6)], fill=(236, 138, 30, 255))
    d.text((arrow_to[0] - 34, arrow_to[1] - 26), '屏幕正面朝向角色',
           fill=(176, 96, 12, 255), font=font_s)

    # 视线箭头: 从角色眼睛指向屏幕
    eye = to_canvas((505, 205))
    gaze_to = to_canvas((300, 380))
    d.line([(eye[0] * zoom, eye[1] * zoom), (gaze_to[0] * zoom, gaze_to[1] * zoom)],
           fill=(216, 62, 92, 255), width=4)
    d.polygon([(gaze_to[0] * zoom, gaze_to[1] * zoom),
               (gaze_to[0] * zoom + 11, gaze_to[1] * zoom - 4),
               (gaze_to[0] * zoom + 7, gaze_to[1] * zoom + 9)],
              fill=(216, 62, 92, 255))
    d.text((eye[0] * zoom - 6, eye[1] * zoom - 30), '视线',
           fill=(216, 62, 92, 255), font=font_s)

    # 标注
    d.text((10, 8), 'R173 办公场景 —— 显示器朝向 / 人物视线 / 键盘位置 示意',
           fill=ACCENT, font=font)
    d.text((10, 30), '橙 = 显示器屏幕四边形 (远侧边更矮 ⇒ 被透视压缩, 不是正对观众)',
           fill=(176, 96, 12, 255), font=font_s)
    d.text((10, 48), '绿 = 键盘 (桌面远端, 双手压在其上)',
           fill=(20, 110, 68, 255), font=font_s)
    d.text((10, 66), '红 = 头部朝向 (3/4 侧身) 的视线方向',
           fill=(216, 62, 92, 255), font=font_s)

    pad = 12
    out = Image.new('RGB', (canvas.size[0] + pad * 2, canvas.size[1] + pad * 2 + 26),
                    (255, 255, 255))
    dd = ImageDraw.Draw(out)
    dd.text((pad, 4), 'R173 透视示意图 (标注为后加说明, 角色像素未改动)',
            fill=ACCENT, font=g158.cjk_font(13))
    out.paste(canvas, (pad, pad + 26))
    dd.rectangle([0, 0, out.size[0] - 1, out.size[1] - 1], outline=(214, 218, 228), width=1)
    out.save(out_path)
    print(f'  📷 {out_path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview-dir', default='evidence_r173_preview')
    ap.add_argument('--out-gifs', default='evidence_r173_gifs')
    ap.add_argument('--out-compare', default='evidence_r173_compare')
    args = ap.parse_args()
    gd = os.path.join(CAND, args.out_gifs)
    cd = os.path.join(CAND, args.out_compare)
    os.makedirs(gd, exist_ok=True)
    os.makedirs(cd, exist_ok=True)

    m = json.load(open(MANIFEST, encoding='utf-8'))
    bm = before_manifest(m)

    # ---------- 修复前后对比 ----------
    for (w, h) in ((200, 240), (256, 256)):
        before = render(bm, 'work', w, h)
        after = render(m, 'work', w, h)
        side_by_side(before, after,
                     '修复前 (R172 交付版: 显示器正对观众, 人物坐在屏幕背面)',
                     '修复后 (R173: 3/4 侧身 + 斜置显示器 + 屏幕朝向角色)',
                     os.path.join(cd, f'办公场景_R172版_vs_R173_{w}x{h}.png'), zoom=3)

    before = render(bm, 'work', 200, 240)
    after = render(m, 'work', 200, 240)

    # 显示器 + 双手 放大对比
    side_by_side(before, after,
                 '修复前: 屏幕正面朝观众, 与人物朝向矛盾',
                 '修复后: 屏幕斜向角色, 观众从侧面看到屏内容',
                 os.path.join(cd, '办公场景_显示器朝向_放大前后对比.png'),
                 zoom=5, crop=(20, 88, 95, 180),
                 header='R173 显示器朝向 修复前 / 修复后  (5x)')

    # 双手 + 键盘 放大对比
    side_by_side(before, after,
                 '修复前: 手在键盘后层, 被键盘/桌面压住',
                 '修复后: 手压在键盘之上, 手掌与指尖都可见',
                 os.path.join(cd, '办公场景_双手与键盘_放大前后对比.png'),
                 zoom=6, crop=(55, 120, 155, 185),
                 header='R173 双手与键盘 修复前 / 修复后  (6x)')

    # 完整坐姿截图 (交付用)
    for (w, h) in ((200, 240), (256, 256)):
        after = render(m, 'work', w, h)
        after.save(os.path.join(cd, f'办公场景_完整坐姿_{w}x{h}.png'))
        print(f'  📷 {os.path.join(cd, f"办公场景_完整坐姿_{w}x{h}.png")}')

    # ---------- 透视示意图 ----------
    perspective_diagram(m, os.path.join(cd, '办公场景_透视示意图_显示器朝向与视线.png'))

    # ---------- 真实 Electron GIF ----------
    ims = scene_gif(args.preview_dir, 'lib_work',
                    os.path.join(gd, 'R173_scene_work.gif'), 280)
    if ims:
        picks = [ims[0], ims[len(ims) // 2], ims[-1]]
        ow = sum(i.size[0] for i in picks) + 24
        oh = max(i.size[1] for i in picks) + 26
        out = Image.new('RGB', (ow, oh), (255, 255, 255))
        d = ImageDraw.Draw(out)
        d.text((8, 6), 'R173 办公场景 —— 真实 Electron 运行帧 (200x240 窗口, 2x 放大)',
               fill=ACCENT, font=g158.cjk_font(13))
        x = 8
        for i, p in enumerate(picks):
            out.paste(p, (x, 24))
            x += p.size[0] + 8
        out.save(os.path.join(gd, 'R173_work_overview.png'))
        print(f'  📷 {os.path.join(gd, "R173_work_overview.png")}')

    print(f'✅ 证据已生成: {gd} / {cd}')


if __name__ == '__main__':
    main()
