#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R170 生活场景 **EAT_FRUIT** —— 场景道具烘焙器 (小圆凳 + 小边桌果盘)。

道具与角色帧共用**同一套 1024x1024 纹理坐标系** (渲染时与角色 sprite 共享
position / anchor / scale), 所以这里画的位置就是运行时看到的相对位置。

角色坐姿底图 character_R138/sleep_enter/sleep_enter_01_sit.png 的实测:
  · 整体 alpha bbox  = x 338~720, y 38~1001
  · 髋/臀           ≈ y 640~670   ⇒ 小圆凳的坐垫顶面落在 y ≈ 655
  · 膝              ≈ y 700~760
  · 靴底/地面       ≈ y 1000
  · 脸/五官         x 427~627, y 176~310  ⇒ 道具**绝不能**进这个框
  · 画面左手(拿水果) 掌缘 x ≈ 348~425, y ≈ 567~638

产出:
  assets/character_R156/prop_stool.png       小圆凳 (back 层, 垫+矮腿)
  assets/character_R156/prop_fruit_table.png  小边桌 + 浅色果盘 + 2~3 个水果
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
R156 = os.path.join(ASSETS, 'character_R156')
OUT = R156

TEX = 1024
SS = 4          # 超采样倍数 (抗锯齿)

# ---- 配色 (蓝白科技系, 与 A1 母版一致) ----
WHITE = (247, 251, 255, 255)
WHITE2 = (226, 238, 247, 255)
SHADE = (196, 214, 230, 255)
TEAL = (122, 198, 214, 255)
TEAL_D = (76, 156, 176, 255)
TEAL_L = (176, 226, 236, 255)
INK = (10, 14, 34, 255)
INK2 = (26, 34, 58, 255)
RED = (226, 84, 88, 255)
RED_D = (168, 48, 58, 255)
RED_L = (255, 176, 172, 255)
GREEN = (96, 184, 132, 255)
GREEN_D = (56, 140, 100, 255)
GOLD = (240, 196, 92, 255)
GOLD_D = (198, 150, 52, 255)


def canvas():
    return Image.new('RGBA', (TEX * 1, TEX * 1), (0, 0, 0, 0))


def S(v):
    """纹理坐标 → 超采样画布坐标"""
    return int(round(v * SS))


def rr(dr, box, r, **kw):
    dr.rounded_rectangle([S(box[0]), S(box[1]), S(box[2]), S(box[3])],
                         radius=S(r), **kw)


def el(dr, box, **kw):
    dr.ellipse([S(box[0]), S(box[1]), S(box[2]), S(box[3])], **kw)


def poly(dr, pts, **kw):
    dr.polygon([(S(x), S(y)) for x, y in pts], **kw)


def down(img):
    return img.resize((TEX, TEX), Image.LANCZOS)


def outline(img, width=3, rgb=INK):
    """给非透明区域加一圈描边 (角色素材是统一的粗描边风格)。"""
    a = np.asarray(img.getchannel('A'))
    band = a.copy()
    for _ in range(width * SS // 2):
        o = band.copy()
        o[1:, :] |= band[:-1, :]
        o[:-1, :] |= band[1:, :]
        o[:, 1:] |= band[:, :-1]
        o[:, :-1] |= band[:, 1:]
        band = o
    ring = (band > 0) & (a == 0)
    arr = np.asarray(img).copy()
    arr[ring] = [rgb[0], rgb[1], rgb[2], 255]
    return Image.fromarray(arr, 'RGBA')


def soft_shadow(img, blur=10, alpha=70, dy=6):
    """在道具下方压一层柔和的落地阴影 (可选)。"""
    a = np.asarray(img.getchannel('A'))
    sh = Image.fromarray(a).filter(ImageFilter.GaussianBlur(radius=blur * SS // 2))
    sh = sh.point(lambda v: int(v * alpha / 255))
    canvas = Image.new('RGBA', img.size, (0, 0, 0, 0))
    canvas.paste((120, 140, 165, 255), (0, 0), sh)
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.alpha_composite(canvas, (0, S(dy)))
    out.alpha_composite(img)
    return out


# ===========================================================================
# 小圆凳 (back 层) —— 角色坐在上面
# ===========================================================================
def draw_stool():
    """小圆凳: 椭圆坐垫 (青白) + 3 条矮腿 + 一圈横撑。

    坐垫顶面 y=655 (角色臀部下缘), 坐垫厚 34, 腿落到地面 y=990。
    """
    img = Image.new('RGBA', (TEX * SS, TEX * SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)

    seat_cx = 500
    seat_cy = 672
    seat_rx = 122
    seat_ry = 40
    leg_bottom = 986

    # --- 三条腿 (先画, 会被坐垫盖住上端) ---
    for dx0, dx1 in ((-86, -58), (58, 86), (-14, 14)):
        top_x = seat_cx + dx0 * 0.5
        bot_x = seat_cx + dx0
        poly(dr, [(top_x + dx1 * 0.5 - 9, seat_cy + 10),
                  (top_x + dx1 * 0.5 + 9, seat_cy + 10),
                  (bot_x + 11, leg_bottom),
                  (bot_x - 11, leg_bottom)], fill=WHITE2, outline=INK, width=2 * SS)
        # 腿上的青色饰条
        poly(dr, [(top_x + dx1 * 0.5 + 2, seat_cy + 52),
                  (top_x + dx1 * 0.5 + 7, seat_cy + 52),
                  (bot_x + 6, leg_bottom - 44),
                  (bot_x + 1, leg_bottom - 44)], fill=TEAL)

    # --- 横撑圈 ---
    dr.arc([S(seat_cx - 104), S(seat_cy + 150), S(seat_cx + 104), S(seat_cy + 196)],
           0, 180, fill=INK2, width=3 * SS)
    dr.arc([S(seat_cx - 100), S(seat_cx and seat_cy + 154), S(seat_cx + 100), S(seat_cy + 192)],
           0, 180, fill=TEAL_D, width=2 * SS)

    # --- 坐垫侧壁 (深一点的青白) ---
    el(dr, (seat_cx - seat_rx, seat_cy - 6, seat_cx + seat_rx, seat_cy + 46),
       fill=WHITE2, outline=INK, width=3 * SS)
    # --- 坐垫顶面 ---
    el(dr, (seat_cx - seat_rx, seat_cy - 40, seat_cx + seat_rx, seat_cy + 12),
       fill=WHITE, outline=INK, width=3 * SS)
    # 坐垫中心的青色内圈 (科技系细节)
    el(dr, (seat_cx - 58, seat_cy - 26, seat_cx + 58, seat_cy - 2),
       fill=TEAL_L, outline=TEAL_D, width=2 * SS)

    img = down(img)
    img = outline(img, 2)
    return img


# ===========================================================================
# 小边桌 + 果盘 (back 层)
# ===========================================================================
def draw_apple(dr, cx, cy, r, tilt=0.0):
    """在超采样画布上画一颗小苹果 (果盘里用的)。"""
    el(dr, (cx - r, cy - r * 0.94, cx + r, cy + r * 0.94), fill=RED, outline=INK, width=2 * SS)
    el(dr, (cx - r * 0.82, cy + r * 0.18, cx + r * 0.78, cy + r * 0.86), fill=RED_D)
    el(dr, (cx - r * 0.62, cy - r * 0.66, cx - r * 0.16, cy - r * 0.14), fill=RED_L)
    poly(dr, [(cx - 3, cy - r * 0.86), (cx + 3, cy - r * 0.9),
              (cx + 4, cy - r * 1.3), (cx - 2, cy - r * 1.26)], fill=(96, 62, 44, 255))
    el(dr, (cx + 2, cy - r * 1.34, cx + r * 0.72, cy - r * 0.96),
       fill=GREEN, outline=INK, width=2 * SS)


def draw_strawberry(dr, cx, cy, r):
    el(dr, (cx - r, cy - r * 0.92, cx + r, cy + r * 0.92), fill=RED, outline=INK, width=2 * SS)
    el(dr, (cx - r * 0.8, cy + r * 0.1, cx + r * 0.76, cy + r * 0.82), fill=RED_D)
    poly(dr, [(cx - r, cy - r * 0.5), (cx + r, cy - r * 0.5), (cx, cy - r * 1.16)],
          fill=GREEN, outline=INK, width=2 * SS)


def draw_fruit_table():
    """小边桌: 圆角浅色桌面 + 一根细腿 + 浅色果盘 + 3 个水果。

    桌面 y 596~648 (x 196~356), 桌腿从桌面正中落到地面 y=990;
    果盘中心 (272, 586), 盘里 2 个苹果 + 1 个草莓。
    """
    img = Image.new('RGBA', (TEX * SS, TEX * SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)

    top_x0, top_x1 = 196, 356
    top_y0, top_y1 = 596, 648
    leg_cx = 276

    # --- 桌腿 (细, 一根) ---
    poly(dr, [(leg_cx - 13, top_y1 - 4), (leg_cx + 13, top_y1 - 4),
              (leg_cx + 8, 990), (leg_cx - 8, 990)],
          fill=WHITE2, outline=INK, width=3 * SS)
    poly(dr, [(leg_cx - 3, top_y1 - 4), (leg_cx + 5, top_y1 - 4),
              (leg_cx + 4, 986), (leg_cx - 2, 986)], fill=TEAL)
    # 桌脚下的小底盘
    el(dr, (leg_cx - 40, 962, leg_cx + 40, 996), fill=WHITE2, outline=INK, width=3 * SS)
    el(dr, (leg_cx - 26, 968, leg_cx + 26, 990), fill=TEAL_L)

    # --- 桌面 (圆角浅色) ---
    rr(dr, (top_x0, top_y0, top_x1, top_y1), 22, fill=WHITE, outline=INK, width=3 * SS)
    rr(dr, (top_x0 + 10, top_y0 + 8, top_x1 - 10, top_y1 - 12), 16,
       fill=(255, 255, 255, 255), outline=TEAL_L, width=2 * SS)
    rr(dr, (top_x0 + 4, top_y1 - 22, top_x1 - 4, top_y1 - 6), 8, fill=TEAL_L)

    # --- 果盘 (浅色椭圆盘, 放在桌面上) ---
    pcx, pcy = 272, 586
    el(dr, (pcx - 62, pcy - 12, pcx + 62, pcy + 30), fill=WHITE2, outline=INK, width=3 * SS)
    el(dr, (pcx - 54, pcy - 8, pcx + 54, pcy + 22), fill=(255, 255, 255, 255),
       outline=TEAL_L, width=2 * SS)
    el(dr, (pcx - 40, pcy - 2, pcx + 40, pcy + 18), fill=(226, 238, 247, 255))

    # --- 盘里的水果 (拿出去的那颗不在这里) ---
    draw_apple(dr, pcx - 30, pcy - 10, 21)
    draw_apple(dr, pcx + 6, pcy - 16, 25)
    draw_strawberry(dr, pcx + 40, pcy - 6, 17)

    img = down(img)
    img = outline(img, 2)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    stool = draw_stool()
    table = draw_fruit_table()

    items = []
    for name, im in (('prop_stool.png', stool), ('prop_fruit_table.png', table)):
        path = os.path.join(OUT, name)
        im.save(path)
        a = np.asarray(im)[:, :, 3]
        ys, xs = np.nonzero(a > 0)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
        assert bbox[0] >= 0 and bbox[1] >= 0 and bbox[2] <= TEX and bbox[3] <= TEX, \
            f'{name} 越界: {bbox}'
        items.append({'file': name, 'bbox': bbox, 'px': int((a > 0).sum())})
        print(f'  ✅ {name:24s} bbox={bbox}  非透明像素={int((a > 0).sum())}')

    # 五官保护检查: 脸框 x427~627 / y176~310 不得被道具覆盖
    FACE = (427, 176, 627, 310)
    for it in items:
        b = it['bbox']
        ov = not (b[2] <= FACE[0] or b[0] >= FACE[2] or b[3] <= FACE[1] or b[1] >= FACE[3])
        print(f"  🔎 {it['file']} 与五官框重叠 = {ov}")
        assert not ov, f"{it['file']} 压到五官"

    with open(os.path.join(OUT, 'eat_fruit_props_report.json'), 'w', encoding='utf-8') as f:
        json.dump({'round': 'R170', 'action': 'eat_fruit', 'items': items},
                  f, ensure_ascii=False, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
