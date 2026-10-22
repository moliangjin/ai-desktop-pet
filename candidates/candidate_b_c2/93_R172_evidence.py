#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R172 证据制作 —— 修复前后对比 / 完整坐姿截图 / 办公动态 GIF。

诚实说明 (沿用 R158/R170 的口径):
  · GIF 里的像素 = **真实 Electron 运行时** `webContents.capturePage` 的像素, 未做任何重绘;
  · GIF 的帧时长 = 该场景**实际采集间隔** (办公场景 280ms), 播放速度与真实运行时一致;
  · 前后对比图里的"修复前"用 **R170 交付版真实素材** (character_R156/work_1.png +
    R167 的 5 个办公道具), 用**同一套、与运行时一致**的合成算法渲染;
  · 标题层是后加的说明文字, 不改变角色像素。

输入:
  --preview-dir  真实 Electron 采集目录 (含 preview_meta.json)
输出:
  --out-gifs     evidence_r172_gifs/
  --out-compare  evidence_r172_compare/
"""
import argparse
import copy
import importlib.util
import json
import os

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

# R170 交付版 (修复前) 的办公场景
BEFORE_SCENE = {
    'floor_tex_y': 1001,
    'back': ['prop_chair', 'prop_desk_surface', 'prop_keyboard'],
    'front': ['prop_desk', 'prop_screen_glow'],
}
BEFORE_FRAMES = ['character_R156/work_1.png', 'character_R156/work_2.png']


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
    """放大 + 顶部标题条。"""
    z = im.resize((im.size[0] * zoom, im.size[1] * zoom), Image.LANCZOS)
    out = Image.new('RGB', (z.size[0] + pad * 2, z.size[1] + pad * 2 + 22), (255, 255, 255))
    d = ImageDraw.Draw(out)
    d.text((pad, pad), text, fill=TEXT, font=g158.cjk_font(13))
    out.paste(z, (pad, pad + 22))
    d.rectangle([0, 0, out.size[0] - 1, out.size[1] - 1], outline=(214, 218, 228), width=1)
    return out


def side_by_side(a, b, title_a, title_b, out_path, zoom=3, crop=None):
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
    d.text((12, 8), f'R172 办公场景 修复前 / 修复后  ({zoom}x)', fill=ACCENT,
           font=g158.cjk_font(15))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview-dir', default='evidence_r172_preview')
    ap.add_argument('--out-gifs', default='evidence_r172_gifs')
    ap.add_argument('--out-compare', default='evidence_r172_compare')
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
        side_by_side(before, after, f'修复前 (R170 交付版, 下半身被剪 / 电脑只有背板)',
                     f'修复后 (R172: 完整坐姿 + 3/4 显示器 + 可见屏幕内容)',
                     os.path.join(cd, f'办公场景_R170版_vs_R172_{w}x{h}.png'), zoom=3)

    # 腿脚 / 屏幕 关键区域放大
    before = render(bm, 'work', 200, 240)
    after = render(m, 'work', 200, 240)
    side_by_side(before, after, '修复前: 腿脚被剪掉 / 只有一块深灰背板',
                 '修复后: 小腿+靴子完整 / 屏幕有蓝白界面',
                 os.path.join(cd, '办公场景_腿脚与屏幕_放大前后对比.png'),
                 zoom=5, crop=(45, 95, 185, 240))

    # 桌面 + 双手放大
    side_by_side(before, after, '修复前: 台面从腰部露出, 键盘在 back 层被大腿挡死',
                 '修复后: 桌面/键盘/双手在角色帧内, 双手真正压在键盘上',
                 os.path.join(cd, '办公场景_桌面双手_放大前后对比.png'),
                 zoom=5, crop=(45, 125, 160, 185))

    # 完整坐姿截图 (交付用)
    for (w, h) in ((200, 240), (256, 256)):
        after = render(m, 'work', w, h)
        after.save(os.path.join(cd, f'办公场景_完整坐姿_{w}x{h}.png'))
        print(f'  📷 {os.path.join(cd, f"办公场景_完整坐姿_{w}x{h}.png")}')

    # ---------- 真实 Electron GIF ----------
    ims = scene_gif(args.preview_dir, 'lib_work',
                    os.path.join(gd, 'R172_scene_work.gif'), 280)
    if ims:
        # 真实帧总览 (放大)
        picks = [ims[0], ims[len(ims) // 2], ims[-1]]
        ow = sum(i.size[0] for i in picks) + 24
        oh = max(i.size[1] for i in picks) + 26
        out = Image.new('RGB', (ow, oh), (255, 255, 255))
        d = ImageDraw.Draw(out)
        d.text((8, 6), 'R172 办公场景 —— 真实 Electron 运行帧 (200x240 窗口, 2x 放大)',
               fill=ACCENT, font=g158.cjk_font(13))
        x = 8
        for i in picks:
            out.paste(i, (x, 22))
            x += i.size[0] + 8
        out.save(os.path.join(gd, 'R172_work_overview.png'))
        print(f'  📷 {os.path.join(gd, "R172_work_overview.png")}')

        # 真实帧 vs 脚本预览 (证明预览器与运行时一致)
        real = Image.open(json.load(open(os.path.join(args.preview_dir,
                'preview_meta.json'), encoding='utf-8'))['lib_work'][0]['file'])
        real = real.convert('RGBA')
        bg = Image.new('RGBA', real.size, BG + (255,))
        bg.alpha_composite(real)
        prev = render(m, 'work', real.size[0], real.size[1])
        side_by_side(bg.convert('RGB'), prev,
                     '真实 Electron capturePage 截屏',
                     '脚本合成预览 (45_R165_scene_preview.py)',
                     os.path.join(cd, '办公场景_真机帧_vs_脚本预览.png'), zoom=3)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
