#!/usr/bin/env python3
"""R147 步态朝向预览器 — 把动画帧放在"移动中的地面"上, 直观看出是否与移动方向一致.

用法:
  python3 10_R147_gait_preview.py --out /tmp/gait.png
  python3 10_R147_gait_preview.py --out /tmp/gait.gif --anim walk_left

做法:
  - 每一帧按真实运行时缩放 (统一 scale) 画到一条地面线上
  - 帧与帧之间横向平移 STEP px, 模拟窗口按 walk_speed 移动
  - 可选施加水平错切 (shear), 模拟"朝向倾斜"方案
  - 背景画地面线与方向箭头, 让人一眼看出脚步与移动方向是否一致
"""

import os
import sys
import json
import math
import argparse

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, "assets", "character_R138")
MANIFEST = os.path.join(CAND, "assets", "character_R141_manifest.json")

SCALE = 0.196319          # 运行时统一缩放 (compact 200x240)
GROUND_Y = 236            # 运行时地面接触线
PIVOT_Y = 921.6           # 纹理坐标下的 pivot (anchor.y=0.9)


def load_frames(action):
    m = json.load(open(MANIFEST, encoding="utf-8"))
    out = []
    for rel in m["actions"][action]["frames"]:
        im = Image.open(os.path.join(os.path.dirname(MANIFEST), rel)).convert("RGBA")
        out.append(im)
    return out


def shear_x(im, k, pivot_y=PIVOT_Y):
    """水平错切: 底部(pivot)不动, 越往上横向位移越大。k<0 → 上身向左倾。"""
    if abs(k) < 1e-6:
        return im
    w, h = im.size
    # 输出画布略宽, 容纳位移
    pad = int(abs(k) * (h - pivot_y)) + 4
    out = Image.new("RGBA", (w + 2 * pad, h), (0, 0, 0, 0))
    px = out.load()
    src = im.load()
    for y in range(h):
        dx = k * (y - pivot_y)
        dxi = int(round(dx))
        for x in range(w):
            nx = x + dxi + pad
            if 0 <= nx < out.size[0]:
                px[nx, y] = src[x, y]
    return out


def render_strip(frames, step_px, shear_k, direction, label, cell_h=260):
    """把一循环按方向铺成一条带, 返回 PIL 图。"""
    imgs = []
    for im in frames:
        im = shear_x(im, shear_k)
        s = SCALE
        w = int(im.size[0] * s)
        h = int(im.size[1] * s)
        r = im.resize((w, h), Image.LANCZOS)
        imgs.append(r)
    n = len(imgs)
    width = int(sum(i.size[0] for i in imgs) + step_px * (n - 1) + 40)
    height = cell_h + 30
    sheet = Image.new("RGBA", (width, height), (248, 249, 252, 255))
    d = ImageDraw.Draw(sheet)
    # 地面线
    d.line([(0, GROUND_Y + 6), (width, GROUND_Y + 6)], fill=(150, 150, 160, 255), width=2)
    x = 20
    for i, im in enumerate(imgs):
        # 底边贴地面线
        y = GROUND_Y + 6 - im.size[1]
        sheet.alpha_composite(im, (x, y))
        # 脚底接触点
        d.ellipse([x + im.size[0] // 2 - 4, GROUND_Y + 2, x + im.size[0] // 2 + 4, GROUND_Y + 10],
                  fill=(220, 60, 60, 255))
        x += im.size[0] + step_px
    # 方向箭头
    if direction > 0:
        d.line([(20, 24), (width - 20, 24)], fill=(60, 120, 220, 255), width=3)
        d.polygon([(width - 20, 18), (width - 6, 24), (width - 20, 30)], fill=(60, 120, 220, 255))
    else:
        d.line([(20, 24), (width - 20, 24)], fill=(220, 120, 40, 255), width=3)
        d.polygon([(20, 18), (6, 24), (20, 30)], fill=(220, 120, 40, 255))
    d.text((8, 4), label, fill=(20, 20, 30, 255))
    return sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/r147_gait_preview.png")
    ap.add_argument("--anim", default=None, help="只输出某一动作的动图")
    ap.add_argument("--step", type=int, default=26, help="每帧横向位移(模拟窗口移动)")
    args = ap.parse_args()

    if args.anim:
        frames = load_frames(args.anim)
        step = args.step if args.anim == "walk_right" else -args.step
        imgs = []
        for im in frames:
            s = SCALE
            w, h = int(im.size[0] * s), int(im.size[1] * s)
            imgs.append(im.resize((w, h), Image.LANCZOS))
        imgs[0].save(args.out, save_all=True, append_images=imgs[1:],
                     duration=130, loop=0, disposal=2)
        print("GIF:", args.out)
        return 0

    rows = []
    wl = load_frames("walk_left")
    wr = load_frames("walk_right")

    rows.append(render_strip(wl, args.step, 0.0, 1, "A) walk_left 现状 — 窗口向右移动 (角色仍在向右倾)"))
    rows.append(render_strip(wr, args.step, 0.0, 1, "B) walk_right 现状 — 窗口向右移动"))
    rows.append(render_strip(wl, -args.step, 0.0, -1, "C) walk_left 现状 — 窗口向左移动 (角色仍向右倾 = 倒着走)"))
    rows.append(render_strip(wr, -args.step, 0.0, -1, "D) walk_right 现状 — 窗口向左移动 (倒着走)"))

    W = max(r.size[0] for r in rows)
    H = sum(r.size[1] for r in rows) + 10
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    y = 0
    for r in rows:
        sheet.paste(r.convert("RGB"), (0, y))
        y += r.size[1] + 2
    sheet.save(args.out)
    print("预览:", args.out, sheet.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
