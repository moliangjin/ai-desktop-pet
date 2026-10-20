#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R156 场景道具烘焙器 (v2) — 程序化绘制"小场景"道具 (不依赖任何外部素材/AI 生图)。

为什么程序化而不是生图:
  · 任务书禁止"像换了一个人/陌生场景插画风", 也禁止充值 i2i;
  · 道具只需要简洁的 Q 版几何体, 程序化矢量能保证**与角色同一坐标系**,
    从而让"角色躺在床上/坐在沙发上"这类接触关系可以精确控制;
  · 全部可复算 (跑一次即得到完全相同的 PNG)。

坐标系约定 (关键):
  道具 PNG = 1024x1024 RGBA, 与角色帧**同一纹理坐标系**。
  渲染时道具 sprite 与角色 sprite 共享 position / anchor / scale,
  因此"道具落地"= 画到该姿态的地面纹理 y。
  每个道具都显式声明自己的 `floor_tex_y` (道具的底 = 该场景的地面行),
  写进 props_report.json, 渲染器据此把道具底边对齐到屏幕地面线。

v2 相比 v1 的修正 (实测发现的三个真问题):
  1) v1 的 `soft_shadow` 是"整张图模糊后偏移", 落影把道具的 alpha bbox
     向外撑出 40+ 纹理 px → 道具在 200px 窗口里被裁掉 (床底超出画布 5.4px)。
     ⇒ v2 改用**显式边界的地面椭圆落影**, bbox 完全可控。
  2) v1 的床/沙发/转椅/桌子 底边各差几像素, 统一改成"形状底 = floor-16,
     落影补到 floor", 保证 bbox 底边**精确等于** floor_tex_y。
  3) v1 的转椅底盘是个亮椭圆, 画在角色前面时读作"地上一摊水"。
     ⇒ v2 转椅底盘改暗改小, 且转椅整体放 back 层 (在角色身后)。
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
OUT = os.path.join(CAND, 'assets', 'character_R156')

S = 1024  # 纹理边长

# ---------- 调色板 (与角色统一) ----------
WOOD = (226, 208, 180, 255)
WOOD_D = (198, 176, 146, 255)
MATTRESS = (226, 236, 246, 255)
MATTRESS_D = (196, 214, 233, 255)
PILLOW = (248, 251, 255, 255)
PILLOW_D = (214, 228, 242, 255)
QUILT = (196, 218, 240, 255)
QUILT_D = (166, 194, 224, 255)
SOFA_BACK = (204, 222, 238, 255)
SOFA_BACK_D = (172, 196, 220, 255)
SOFA_SEAT = (228, 238, 248, 255)
SOFA_SEAT_D = (196, 216, 234, 255)
METAL = (206, 216, 228, 255)
METAL_D = (168, 182, 198, 255)
SCREEN = (58, 78, 106, 255)
SCREEN_D = (38, 54, 78, 255)
MOON = (253, 243, 208, 255)
STAR = (240, 236, 214, 255)


def canvas():
    return Image.new('RGBA', (S, S), (0, 0, 0, 0))


def clip_bottom(img, row):
    """把 row 以下的 alpha 清零 —— 保证道具的 bbox 底边**精确等于**地面行。

    落影是模糊渐变, 直接截断会在地面线处留下一条硬边; 但地面线本来就是
    桌宠窗口的"地面", 影子在那里收掉反而更自然, 同时保证 bbox 可控。
    """
    a = img.split()[3]
    new_a = Image.new('L', img.size, 0)
    new_a.paste(a.crop((0, 0, img.size[0], row)), (0, 0))
    img.putalpha(new_a)
    return img


def ground_shadow(img, x0, x1, y_top, y_bottom, alpha=70, blur=9):
    """显式边界的地面椭圆落影 —— 不会把道具的 bbox 向外撑破。"""
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.ellipse([x0, y_top, x1, y_bottom], fill=(40, 52, 70, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.alpha_composite(sh)
    out.alpha_composite(img)
    return out


def save(img, name, floor_tex_y, report):
    path = os.path.join(OUT, name)
    img.save(path)
    bb = img.getbbox()
    report['props'][name] = {'bbox': list(bb) if bb else None,
                              'floor_tex_y': floor_tex_y}
    print(f"  ✅ {name:24s} bbox={bb} floor={floor_tex_y}")
    return path


# ======================================================================
# 1. 小床 (躺姿用; 场景地面纹理 y = 818)
# ======================================================================
def make_bed():
    img = canvas()
    d = ImageDraw.Draw(img)
    # 床腿
    for x0 in (108, 318, 664, 872):
        d.rounded_rectangle([x0, 742, x0 + 44, 802], radius=15, fill=WOOD, outline=WOOD_D, width=4)
    # 底部横梁
    d.rounded_rectangle([100, 768, 924, 802], radius=13, fill=WOOD, outline=WOOD_D, width=4)
    # 床头板 (在角色头后面, 只从左侧露出)
    d.rounded_rectangle([44, 424, 100, 742], radius=22, fill=WOOD, outline=WOOD_D, width=4)
    # 床垫 (薄一点, 别让床比角色还高)
    d.rounded_rectangle([44, 632, 962, 748], radius=32, fill=MATTRESS, outline=MATTRESS_D, width=5)
    d.rounded_rectangle([44, 700, 962, 746], radius=24, fill=MATTRESS_D, outline=None)
    # 枕头 (承托头部: 头在纹理 x 49~384 / y 330~470)
    d.ellipse([40, 424, 372, 600], fill=PILLOW, outline=PILLOW_D, width=5)
    d.ellipse([76, 450, 338, 566], fill=(255, 255, 255, 190))
    img = ground_shadow(img, 96, 930, 786, 818, alpha=64, blur=8)
    return clip_bottom(img, 818)


# ======================================================================
# 2. 被子 (front 层; 盖住身体右半 + 腿, 不遮脸)
# ======================================================================
def make_quilt():
    img = canvas()
    d = ImageDraw.Draw(img)
    pts = [(486, 516), (716, 494), (902, 526), (980, 598), (972, 676), (760, 700), (520, 698), (470, 612)]
    d.polygon(pts, fill=QUILT, outline=QUILT_D)
    for (x0, y0, x1, y1) in ((560, 526, 604, 690), (700, 512, 744, 692), (840, 536, 878, 684)):
        d.line([(x0, y0), (x1, y1)], fill=QUILT_D, width=5)
    d.line([(492, 596), (975, 610)], fill=QUILT_D, width=5)
    mask = Image.new('L', img.size, 0)
    md = ImageDraw.Draw(mask)
    md.polygon(pts, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(6))
    img.putalpha(Image.composite(img.split()[3], Image.new('L', img.size, 0), mask))
    return img


# ======================================================================
# 3. 月亮 + 星星 (back 层; 夜空氛围, 画布上部)
# ======================================================================
def make_moon():
    img = canvas()
    d = ImageDraw.Draw(img)
    m = Image.new('L', (S, S), 0)
    md = ImageDraw.Draw(m)
    md.ellipse([700, 56, 838, 194], fill=255)
    md.ellipse([740, 26, 878, 164], fill=0)
    moon = Image.new('RGBA', (S, S), MOON)
    moon.putalpha(m)
    img.alpha_composite(moon)
    # 月晕 (很小范围, 不做大块背景)
    glow = Image.new('RGBA', (S, S), (253, 240, 190, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([662, 18, 884, 232], fill=(253, 240, 190, 34))
    glow = glow.filter(ImageFilter.GaussianBlur(34))
    img.alpha_composite(glow)
    # 小星星 (限制在 x 70~900, 避免出画布)
    for (cx, cy, r) in ((150, 92, 13), (286, 46, 9), (430, 120, 11), (576, 62, 8),
                        (662, 176, 10), (236, 206, 9), (498, 232, 8), (872, 262, 9),
                        (96, 268, 8), (372, 300, 7), (830, 128, 7)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=STAR)
    return img


# ======================================================================
# 4. 小沙发 (坐姿用; 场景地面纹理 y = 1001)
# ======================================================================
def make_sofa():
    """低矮豆袋沙发: 没有细高腿, 坐垫厚实直接落地 —— 读作"可爱小沙发"而不是高脚凳。"""
    img = canvas()
    d = ImageDraw.Draw(img)
    # 靠背 (在角色身后, 从两侧露出)
    d.rounded_rectangle([292, 368, 772, 700], radius=64, fill=SOFA_BACK, outline=SOFA_BACK_D, width=5)
    d.rounded_rectangle([330, 410, 734, 664], radius=48, fill=(222, 234, 246, 255), outline=None)
    # 厚坐垫 (直接落地; 角色臀部会微微陷入)
    d.rounded_rectangle([258, 626, 806, 985], radius=60, fill=SOFA_SEAT, outline=SOFA_SEAT_D, width=5)
    # 坐垫顶面高光 + 一条缝线, 避免像一块白板
    d.rounded_rectangle([286, 640, 778, 716], radius=44, fill=(240, 247, 253, 255), outline=None)
    d.line([(300, 742), (764, 742)], fill=SOFA_SEAT_D, width=5)
    # 两端微微翘起 (包裹感)
    for x0 in (258, 742):
        d.ellipse([x0, 660, x0 + 64, 880], fill=SOFA_SEAT, outline=SOFA_SEAT_D, width=4)
    img = ground_shadow(img, 268, 796, 972, 1001, alpha=58, blur=8)
    return clip_bottom(img, 1001)


# ======================================================================
# 5. 办公转椅 (坐姿用; back 层, 在角色身后)
# ======================================================================
def make_chair():
    """办公转椅: 靠背宽到能在笔记本两侧露出, 底盘压暗 (避免读成"地上一摊水")。"""
    img = canvas()
    d = ImageDraw.Draw(img)
    # 底盘 (压暗 + 压小, 只在椅脚两侧露出一小条)
    d.ellipse([432, 952, 606, 998], fill=(176, 190, 208, 255), outline=METAL_D, width=4)
    d.ellipse([466, 958, 572, 990], fill=(206, 216, 228, 255), outline=None)
    # 支柱
    d.rounded_rectangle([498, 758, 540, 964], radius=15, fill=METAL, outline=METAL_D, width=4)
    # 靠背 (比笔记本宽, 两侧各露出一条)
    d.rounded_rectangle([332, 392, 712, 700], radius=54, fill=SOFA_BACK, outline=SOFA_BACK_D, width=5)
    d.rounded_rectangle([366, 428, 678, 664], radius=42, fill=(226, 236, 248, 255), outline=None)
    # 坐垫
    d.rounded_rectangle([336, 686, 708, 762], radius=30, fill=SOFA_SEAT, outline=SOFA_SEAT_D, width=5)
    d.rounded_rectangle([360, 698, 684, 730], radius=22, fill=(240, 247, 253, 255), outline=None)
    img = ground_shadow(img, 420, 620, 976, 1001, alpha=52, blur=9)
    return clip_bottom(img, 1001)


# ======================================================================
# 6. 小桌子 + 笔记本电脑 (front 层; 场景地面纹理 y = 1001)
#    画法: 观众视角看到笔记本屏幕正面, 角色从屏幕后面探出上半身 —— 这是 Q 版
#          "在电脑前办公" 最明确、也最不遮脸的信号。
#    整体右移 44px: 让角色的上半身正好落在屏幕中线上 (角色前倾后头在 x≈600)。
# ======================================================================
def make_desk():
    img = canvas()
    d = ImageDraw.Draw(img)
    ox = 44
    for x0 in (312, 672):
        d.rounded_rectangle([x0 + ox, 736, x0 + 46 + ox, 985], radius=16, fill=WOOD, outline=WOOD_D, width=4)
    d.rounded_rectangle([286 + ox, 698, 744 + ox, 742], radius=16, fill=WOOD, outline=WOOD_D, width=4)
    d.rounded_rectangle([356 + ox, 676, 674 + ox, 702], radius=10, fill=METAL, outline=METAL_D, width=4)
    d.polygon([(394 + ox, 470), (636 + ox, 470), (652 + ox, 678), (378 + ox, 678)],
              fill=METAL, outline=METAL_D)
    d.polygon([(406 + ox, 484), (624 + ox, 484), (638 + ox, 664), (392 + ox, 664)],
              fill=SCREEN, outline=None)
    for (y, x0, x1) in ((508, 432, 596), (536, 432, 566), (564, 448, 610), (592, 432, 540), (620, 470, 600)):
        d.line([(x0 + ox, y), (x1 + ox, y)], fill=(126, 168, 206, 220), width=7)
    d.ellipse([500 + ox, 668, 516 + ox, 684], fill=(150, 206, 246, 255))
    img = ground_shadow(img, 330 + ox, 700 + ox, 968, 1001, alpha=54, blur=9)
    return clip_bottom(img, 1001)


# ======================================================================
# 7. 屏幕微光 (front 层; 叠在角色下半身, 淡淡一层)
# ======================================================================
def make_screen_glow():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    a = np.asarray(img).astype(np.float32)
    yy, xx = np.mgrid[0:S, 0:S]
    cx, cy = 560, 576
    r = np.sqrt(((xx - cx) / 250.0) ** 2 + ((yy - cy) / 210.0) ** 2)
    v = np.clip(1.0 - r, 0.0, 1.0) ** 1.7
    a[:, :, 0] = 120 * v
    a[:, :, 1] = 176 * v
    a[:, :, 2] = 240 * v
    a[:, :, 3] = 88 * v
    out = Image.fromarray(a.astype(np.uint8), 'RGBA')
    return out.filter(ImageFilter.GaussianBlur(10))


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {'round': 'R156', 'technique': '程序化矢量绘制 (无外部素材/无 AI 生图)',
           'coordinate_note': ('道具 PNG = 1024x1024, 与角色帧同一纹理坐标系; '
                               '渲染时与角色 sprite 共享 position/anchor/scale; '
                               '每个道具的 floor_tex_y = 道具底边 (= 该场景的地面纹理行), '
                               '渲染器把它对齐到屏幕地面线'),
           'z_order_note': ('back 层 = 月亮/床/沙发/转椅 (在角色身后); '
                            'front 层 = 被子/桌子+笔记本/屏幕微光 (在角色身前)'),
           'props': {}}
    print("R156 场景道具绘制 v2:")
    for fn, name, floor in (
            (make_bed, 'prop_bed.png', 818),
            (make_quilt, 'prop_quilt.png', None),
            (make_moon, 'prop_moon.png', None),
            (make_sofa, 'prop_sofa.png', 1001),
            (make_chair, 'prop_chair.png', 1001),
            (make_desk, 'prop_desk.png', 1001),
            (make_screen_glow, 'prop_screen_glow.png', None)):
        save(fn(), name, floor, rep)
    path = os.path.join(OUT, 'props_report.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"  📄 {path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
