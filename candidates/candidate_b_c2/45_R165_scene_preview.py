#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 场景合成预览 —— 复刻运行时 (sprite_layout.computeLayout) 的缩放与地面行规则。

用途:
  · 在不启动 Electron 的情况下, 用**真实显示尺寸** (compact 200x240 / standard 256x256)
    预览 back 道具 → 角色 → front 道具 的最终合成效果, 用于 P0-2 / P0-3 的观感验收。
  · 缩放算法与 sprite_layout.js 的 computeUniformScaleWithSkew (skew=0) 一致;
    地面行按 manifest.props.scenes[scene].floor_tex_y 与角色帧的 ground_tex_y 处理。

用法:
    python3 45_R165_scene_preview.py --scene work --size 200x240 --out /tmp/x.png
    python3 45_R165_scene_preview.py --all --out-dir /tmp/r165_prev
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
MANIFEST = os.path.join(ASSETS, 'character_R141_manifest.json')
TEX = 1024

MARGIN = 4
ANCHOR_X = 0.5
ANCHOR_Y = 0.9


def alpha_bbox(path):
    im = Image.open(path).convert('RGBA')
    a = np.asarray(im)[:, :, 3]
    ys, xs = np.nonzero(a > 0)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def uniform_scale(entries, canvas_w, canvas_h, margin=MARGIN):
    """与 sprite_layout.computeUniformScaleWithSkew 一致 (skew 全 0)。"""
    half_w = canvas_w / 2 - margin
    avail_h = canvas_h - 2 * margin
    scale = float('inf')
    for (l, t, r, b) in entries:
        w, h = r - l, b - t
        if w <= 0 or h <= 0:
            continue
        scale = min(scale, avail_h / h)
        min_lx, max_lx = l - 512, r - 512
        if min_lx < 0:
            scale = min(scale, half_w / (-min_lx))
        if max_lx > 0:
            scale = min(scale, half_w / max_lx)
    return scale if scale != float('inf') else 1.0


def all_frame_paths(m):
    """收集 manifest 引用的全部角色帧 (相对 assets/ 的路径)。"""
    out = []

    def add(seq):
        for f in (seq or []):
            if isinstance(f, str):
                out.append(f)
            elif isinstance(f, dict) and 'file' in f:
                out.append(f['file'])

    for act in (m.get('actions') or {}).values():
        add(act.get('frames'))
    for act in ((m.get('action_library') or {}).get('actions') or {}).values():
        add(act.get('frames'))
    return out


def build_scale(m, canvas_w, canvas_h):
    ents = []
    for rel in all_frame_paths(m):
        p = os.path.join(ASSETS, rel)
        if not os.path.exists(p):
            continue
        bb = alpha_bbox(p)
        if bb:
            ents.append(tuple(bb))
    return uniform_scale(ents, canvas_w, canvas_h)


def compose(scene, canvas_w, canvas_h, m, frame_override=None, out_path=None,
            checker=True, extra_front=None, extra_back=None):
    """按 back → 角色 → front 顺序合成一个场景, 返回 PIL 图。"""
    props = m.get('props') or {}
    scenes = props.get('scenes') or {}
    lib = props.get('library') or {}
    sc = scenes.get(scene)
    if sc is None:
        raise SystemExit(f'❌ manifest 无场景 {scene}')

    if frame_override:
        char_rel = frame_override
    else:
        lib_acts = (m.get('action_library') or {}).get('actions') or {}
        core_acts = m.get('actions') or {}
        if scene in lib_acts:
            char_rel = lib_acts[scene]['frames'][0]
        elif scene in core_acts:
            char_rel = core_acts[scene]['frames'][0]
        else:
            raise SystemExit(f'❌ 找不到场景 {scene} 对应的角色帧')

    scale = build_scale(m, canvas_w, canvas_h)
    ground_y = canvas_h - MARGIN
    anchor_tex_y = ANCHOR_Y * TEX

    char_path = os.path.join(ASSETS, char_rel)
    cb = alpha_bbox(char_path)
    floor = sc.get('floor_tex_y', cb[3])
    # 角色帧的 ground_tex_y (manifest 声明) 优先
    lib_acts = (m.get('action_library') or {}).get('actions') or {}
    core_acts = m.get('actions') or {}
    g = lib_acts.get(scene, {}).get('ground_tex_y')
    if g is None:
        g = core_acts.get(scene, {}).get('ground_tex_y')
    char_ground = g if isinstance(g, (int, float)) else floor

    # 角色与道具共用同一套变换:
    #   screen_y = ground_y - (ground_row - anchor_tex_y) * scale  (角色)
    #   screen_y = ground_y - (floor    - anchor_tex_y) * scale  (道具, 场景地面行)
    def to_screen(img, ground_row):
        """把 1024 纹理图缩放并定位到 canvas (LANCZOS)。"""
        w = int(round(TEX * scale))
        im = img.resize((max(1, w), max(1, w)), Image.LANCZOS)
        arr = np.asarray(im).astype(np.float64)
        # 纹理行 tex_y 的屏幕 y:
        #   角色: y = ground_y - (tex_y - anchor_y*1024)*scale  -> 纹理底(1024) 在 ground_y - (1024-921.6)*scale
        #   道具: 令道具的地面行 floor 落在同一地面线上
        # 【R172 修正】地面行 (ground_row) 必须落在**地面线** ground_y 上,
        #   与运行时 sprite_layout.js 的 groundRowY 严格一致:
        #       sprite.y = groundY - (ground_row - anchor.y*TEX) * scale
        #       纹理行 r → 屏幕 y = sprite.y + (r - anchor.y*TEX) * scale
        #                = groundY - (ground_row - r) * scale
        #   ⇒ r = ground_row 时正好 = groundY。
        #   旧实现把 y_bottom 算成 sy + (TEX - ground_row)*scale, 等价于把
        #   "地面行" 当成 "纹理底行 1024", 于是整幅图**上移了
        #   (ground_row - anchor.y*TEX) * scale** (200×240 下 15.58px),
        #   预览图与真实 Electron 画面对不齐 (R172 目视复核时发现)。
        y_bottom = ground_y + (TEX - ground_row) * scale
        x_center = canvas_w / 2
        # 纹理列 512 的屏幕 x = canvas_w/2
        return arr, x_center, y_bottom, scale

    canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))

    def blit(img, ground_row):
        arr, x_center, y_bottom, sc_ = to_screen(img, ground_row)
        h, w = arr.shape[:2]
        left = int(round(x_center - 512 * sc_))
        top = int(round(y_bottom - h))
        # 目标区域
        dx0 = max(0, left); dy0 = max(0, top)
        dx1 = min(canvas_w, left + w); dy1 = min(canvas_h, top + h)
        if dx1 <= dx0 or dy1 <= dy0:
            return
        sx0 = dx0 - left; sy0 = dy0 - top
        sub = arr[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
        layer = Image.fromarray(np.clip(sub, 0, 255).astype(np.uint8), 'RGBA')
        canvas.alpha_composite(layer, (dx0, dy0))

    for p in (list(sc.get('back') or []) + list(extra_back or [])):
        blit(Image.open(os.path.join(ASSETS, lib[p]['file'])).convert('RGBA'), floor)
    blit(Image.open(char_path).convert('RGBA'), char_ground)
    for p in (list(sc.get('front') or []) + list(extra_front or [])):
        blit(Image.open(os.path.join(ASSETS, lib[p]['file'])).convert('RGBA'), floor)

    if checker:
        bg = Image.new('RGBA', (canvas_w, canvas_h), (250, 250, 252, 255))
        for y in range(0, canvas_h, 16):
            for x in range(0, canvas_w, 16):
                if ((x // 16) + (y // 16)) % 2 == 0:
                    bg.paste((232, 235, 242, 255), (x, y, x + 16, y + 16))
        bg.alpha_composite(canvas)
        canvas = bg
    if out_path:
        canvas.convert('RGB').save(out_path)
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scene', default='work')
    ap.add_argument('--size', default='200x240')
    ap.add_argument('--out', default=None)
    ap.add_argument('--frame', default=None, help='覆盖角色帧 (相对 assets/)')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--out-dir', default='/tmp/r165_prev')
    ap.add_argument('--no-checker', action='store_true')
    args = ap.parse_args()

    m = json.load(open(MANIFEST, encoding='utf-8'))
    w, h = (int(x) for x in args.size.lower().split('x'))

    if args.all:
        os.makedirs(args.out_dir, exist_ok=True)
        for sc in ('work', 'sleep_breath', 'sleep_loop', 'sit_rest', 'doze', 'cheer_heart'):
            try:
                p = os.path.join(args.out_dir, f'{sc}_{w}x{h}.png')
                compose(sc, w, h, m, out_path=p, checker=not args.no_checker)
                print(f'📷 {p}')
            except SystemExit as e:
                print(f'  ⚠️ {e}')
        return 0

    out = args.out or os.path.join('/tmp', f'{args.scene}_{w}x{h}.png')
    compose(args.scene, w, h, m, frame_override=args.frame, out_path=out,
            checker=not args.no_checker)
    print(f'📷 {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
