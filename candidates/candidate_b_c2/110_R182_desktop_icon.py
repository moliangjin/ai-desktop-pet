#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R182: 生成「AI桌宠」桌面启动图标 (macOS .icns)。

硬约束 (本轮需求第 4/5 条):
  · 只**读取**现有角色素材, 绝不修改原图 (assets/character_R138/idle/idle_00_base.png 原样保留)
  · 只做「裁切 / 缩放 / 合成背景 / 加投影」, **不生成新角色形象** ——
    五官、发型、发色、瞳色、服装、配色一律沿用原素材, 保证角色辨识度
  · 输出 1024x1024 **满幅方图** (不预先画圆角) —— macOS 自 Big Sur 起会替 bundle
    里的图标自动套圆角遮罩, 自己再画一遍会变成「双层圆角」

用法:
    python3 110_R182_desktop_icon.py                 # 用选定底色生成正式图标 + .icns
    python3 110_R182_desktop_icon.py --variant A|B|C # 指定底色
    python3 110_R182_desktop_icon.py --preview        # 额外产出三色对比图供肉眼挑选
"""

import argparse
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

CAND = os.path.dirname(os.path.abspath(__file__))
# 仓库根 = candidate_b_c2 的上两级 (.../candidates/candidate_b_c2 -> 仓库根)
REPO = os.path.dirname(os.path.dirname(CAND))

SRC = os.path.join(CAND, 'assets', 'character_R138', 'idle', 'idle_00_base.png')
BUNDLE_RES = os.path.join(REPO, '_app_bundle', 'AI桌宠.app', 'Contents', 'Resources')
# 图标母版放证据目录 (bundle 里只保留运行时需要的 .icns)
ICON_PNG = os.path.join(CAND, 'evidence_r182', 'AppIcon_1024.png')
ICON_ICNS = os.path.join(BUNDLE_RES, 'AppIcon.icns')
PREVIEW_DIR = os.path.join(CAND, 'evidence_r182')

CANVAS = 1024

# bust 裁切框 (源图 1024x1024 坐标)。
#   依据 alpha bbox (329,37,704,987) 与实际形象: 头顶 y=37, 下巴 y≈305, 肩线 y≈360,
#   胸口 "Q" 徽标 y≈395 —— 所以切到 y=600 能保住「头 + 肩 + 上胸」, 小尺寸下脸最清楚。
CROP_BOX = (318, 28, 716, 600)
CROP_SCALE = 1.55
CHAR_TOP = 68

# 三种底色方案 (源色 / 目标色)
VARIANTS = {
    # A: 浅色冰蓝 —— 贴合「银白 + 冰蓝」气质, 但白大褂在浅底上边缘发虚
    'A': dict(top=(244, 250, 254), bottom=(176, 214, 236), halo=(255, 255, 255), halo_a=0.55, shadow_a=0.30),
    # B: 中蓝 + 头部白色光晕 —— 白大褂与银发都能压出轮廓, 小尺寸可读性最好
    'B': dict(top=(214, 237, 250), bottom=(122, 175, 210), halo=(255, 255, 255), halo_a=0.75, shadow_a=0.40),
    # C: 深蓝 —— 剪影最强, 但偏离角色本身的浅色调
    'C': dict(top=(92, 142, 178), bottom=(34, 70, 100), halo=(210, 240, 255), halo_a=0.70, shadow_a=0.55),
}


def diag_gradient(c_top, c_bottom):
    """左上 -> 右下的线性渐变 (numpy 直接算, 避免逐像素 python 循环)。"""
    y, x = np.mgrid[0:CANVAS, 0:CANVAS]
    t = (x / (CANVAS - 1) * 0.55 + y / (CANVAS - 1) * 0.45)[..., None]
    top = np.array(c_top, dtype=np.float64)[None, None, :]
    bot = np.array(c_bottom, dtype=np.float64)[None, None, :]
    rgb = top * (1 - t) + bot * t
    out = np.concatenate([rgb, np.full((CANVAS, CANVAS, 1), 255.0)], axis=2)
    return Image.fromarray(out.astype(np.uint8), 'RGBA')


def radial_halo(center, radius, color, peak_alpha):
    """头部背后的柔光晕 (椭圆衰减), 让头和深色底之间有呼吸感。"""
    y, x = np.mgrid[0:CANVAS, 0:CANVAS]
    d = np.sqrt(((x - center[0]) / (radius * 1.05)) ** 2 + ((y - center[1]) / radius) ** 2)
    a = np.clip(1.0 - d, 0.0, 1.0) ** 1.7 * peak_alpha
    layer = np.zeros((CANVAS, CANVAS, 4), dtype=np.float64)
    layer[..., 0] = color[0]
    layer[..., 1] = color[1]
    layer[..., 2] = color[2]
    layer[..., 3] = a * 255.0
    return Image.fromarray(layer.astype(np.uint8), 'RGBA')


def build_icon(variant):
    """合成一张 1024x1024 图标。返回 (RGBA 图, 角色在画布上的 bbox)。"""
    cfg = VARIANTS[variant]

    if not os.path.exists(SRC):
        sys.exit(f'[icon] FATAL: 角色素材不存在: {SRC}')

    # ---------- ① 读取 + bust 裁切 (原图只读, 不写回) ----------
    base = Image.open(SRC).convert('RGBA')
    crop = base.crop(CROP_BOX)
    crop = crop.resize((round(crop.width * CROP_SCALE), round(crop.height * CROP_SCALE)), Image.LANCZOS)

    # ---------- ② 背景 ----------
    canvas = diag_gradient(cfg['top'], cfg['bottom'])
    # 头/脸中心 (裁切放大后的经验坐标)
    halo_center = (CANVAS // 2, 250)
    canvas = Image.alpha_composite(canvas, radial_halo(halo_center, 400, cfg['halo'], cfg['halo_a']))

    ox = (CANVAS - crop.width) // 2
    oy = CHAR_TOP

    # ---------- ③ 角色投影 (alpha 模糊后下移, 不吃角色本身的颜色) ----------
    alpha = crop.getchannel('A')
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(20)).point(lambda v: int(v * cfg['shadow_a']))
    shadow_mask = Image.new('L', canvas.size, 0)
    shadow_mask.paste(shadow_alpha, (ox, oy + 12))
    shadow = Image.new('RGBA', canvas.size, (28, 52, 74, 0))
    shadow.putalpha(shadow_mask)
    canvas = Image.alpha_composite(canvas, shadow)

    # ---------- ④ 贴角色 (source-over, 保留原素材颜色) ----------
    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    layer.paste(crop, (ox, oy), crop)
    canvas = Image.alpha_composite(canvas, layer)

    bbox = (ox, oy, ox + crop.width, oy + crop.height)
    return canvas, bbox


def save_icns(png_path, icns_path):
    """用 sips 生成标准 iconset, 再用 iconutil 合成 .icns。

    iconset 是**中间产物**, 放临时目录并用完即删 —— 不能留在 bundle 的
    Resources 里 (那是运行时资源目录, 塞构建中间物属于脏)。
    """
    import shutil
    import tempfile
    iconset = os.path.join(tempfile.mkdtemp(prefix='r182_iconset_'), 'AppIcon.iconset')
    os.makedirs(iconset, exist_ok=True)
    specs = [
        ('icon_16x16.png', 16), ('icon_16x16@2x.png', 32),
        ('icon_32x32.png', 32), ('icon_32x32@2x.png', 64),
        ('icon_128x128.png', 128), ('icon_128x128@2x.png', 256),
        ('icon_256x256.png', 256), ('icon_256x256@2x.png', 512),
        ('icon_512x512.png', 512), ('icon_512x512@2x.png', 1024),
    ]
    try:
        for name, px in specs:
            out = os.path.join(iconset, name)
            subprocess.run(['sips', '-z', str(px), str(px), png_path, '--out', out],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', icns_path], check=True)
    finally:
        shutil.rmtree(os.path.dirname(iconset), ignore_errors=True)
    return icns_path


def contact_sheet(images, path, cell=340, pad=18, label_h=34):
    """把多张图拼成对比图, 方便肉眼挑底色。"""
    from PIL import ImageDraw
    n = len(images)
    w = pad + n * (cell + pad)
    h = pad + cell + pad + label_h
    sheet = Image.new('RGB', (w, h), (238, 240, 244))
    draw = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(images):
        x = pad + i * (cell + pad)
        tile = im.convert('RGB').resize((cell, cell), Image.LANCZOS)
        sheet.paste(tile, (x, pad))
        draw.text((x + 6, pad + cell + 8), f'variant {name}', fill=(40, 46, 54))
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='B', choices=list(VARIANTS.keys()))
    ap.add_argument('--preview', action='store_true')
    args = ap.parse_args()

    if args.preview:
        os.makedirs(PREVIEW_DIR, exist_ok=True)
        made = []
        for key in VARIANTS:
            im, bbox = build_icon(key)
            p = os.path.join(PREVIEW_DIR, f'icon_variant_{key}.png')
            im.save(p)
            made.append((key, im))
            print(f'[icon] variant {key} -> {p} char_bbox={bbox}')
        # 小尺寸可读性对照 (把 1024 缩到 64 再放大回 340, 模拟 Dock/Finder 小图标)
        small = []
        for key, im in made:
            s = im.resize((64, 64), Image.LANCZOS).resize((340, 340), Image.NEAREST)
            small.append((key, s))
        contact_sheet(small, os.path.join(PREVIEW_DIR, 'icon_variants_small.png'))
        print(f'[icon] 对比图 -> {os.path.join(PREVIEW_DIR, "icon_variants_small.png")}')
        return

    os.makedirs(BUNDLE_RES, exist_ok=True)
    im, bbox = build_icon(args.variant)
    im.save(ICON_PNG)
    print(f'[icon] 1024 PNG -> {ICON_PNG} char_bbox={bbox}')
    save_icns(ICON_PNG, ICON_ICNS)
    print(f'[icon] ICNS     -> {ICON_ICNS} ({os.path.getsize(ICON_ICNS)} 字节)')


if __name__ == '__main__':
    main()
