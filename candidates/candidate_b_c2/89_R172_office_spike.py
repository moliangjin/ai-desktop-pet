#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R172 spike —— 验证"摘手 + 独立前层手部道具"的核心可行性。

要验证三件事:
  1. 能不能从坐姿帧里把两只手**干净地抹掉** (用下方裤子像素向上克隆填补),
     且不留下破洞/鬼影;
  2. 复制出来的手平移到"身前桌面"位置后, 形态是否还像手;
  3. 合成后 (角色无手 + 独立手道具在键盘上) 读不读得出"坐在桌前打字"。

不改任何仓库素材, 产物只写 /tmp。
"""
import importlib.util
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
SIT = os.path.join(ASSETS, 'character_R138', 'sleep_enter', 'sleep_enter_01_sit.png')

# 坐姿实测: 左手 x326..430 y550..656 / 右手 x430..556 y548..656
HAND_BOXES = {
    'L': (318, 536, 438, 664),
    'R': (424, 534, 564, 664),
}
# 目标位置 (身前桌面): 双手下移, 压在新键盘上
TARGET = {
    'L': (318, 590, 438, 718),
    'R': (424, 588, 564, 716),
}
# 新键盘 (front 层): 远沿窄近沿宽
KB = dict(far_y=606, near_y=690, far_x=(336, 574), near_x=(306, 606))


def load(p):
    return np.asarray(Image.open(p).convert('RGBA')).astype(np.int32)


def to_im(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')


def skin_mask(a):
    r, g, b, al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (al > 60) & (r > 195) & (g > 140) & (g < 205) & (b > 110) & (b < 185) & (r > b + 35)


def teal_mask(a):
    """青色 (腕带 / 裤子) 判定。"""
    r, g, b, al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (al > 60) & (b > 130) & (g > 140) & (b >= r - 10) & (g >= r - 5)


def dilate(m, n=2):
    """n 轮 3x3 膨胀 (保持形状)。"""
    out = m.copy()
    for _ in range(n):
        p = np.pad(out, 1, mode='constant', constant_values=False)
        out = (p[0:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, 0:-2] | p[1:-1, 2:] | out)
    return out


def hand_region(a, box):
    """手的实心区域: 肤色 + 描边 (含腕带与袖口一小段), 排除裤子。"""
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1]
    m = (sub[:, :, 3] > 60)
    # 手部 = 肤色 或 (描边暗色) ; 腕带(青) 与 袖子(白) 单独处理
    sm = skin_mask(sub)
    r, g, b = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
    dark = (sub[:, :, 3] > 60) & (r < 150) & (g < 150) & (b < 165)
    hand = dilate(sm | dark, 2)
    full = np.zeros(a.shape[:2], bool)
    full[y0:y1, x0:x1] = hand
    return full


def extract_and_erase(a, boxes):
    """把两只手从帧里抠出来 (含描边), 原位用下方像素向上克隆填补。"""
    out = a.copy()
    pieces = {}
    for key, box in boxes.items():
        x0, y0, x1, y1 = box
        m = hand_region(a, box)
        # 区域内的手像素
        patch = np.zeros_like(out)
        patch[m] = a[m]
        pieces[key] = patch
        # 原位填补: 沿同列向下找第一个"不是手"的像素, 向上克隆
        for x in range(x0, x1):
            col_m = m[:, x]
            ys = np.nonzero(col_m)[0]
            if len(ys) == 0:
                continue
            top, bot = int(ys.min()), int(ys.max())
            # 找 bot 之下第一个非手像素
            src = None
            for y in range(bot + 1, min(1024, bot + 260)):
                if not col_m[y] and a[y, x, 3] > 40:
                    src = y
                    break
            if src is None:
                continue
            for y in range(top, bot + 1):
                if col_m[y]:
                    out[y, x] = a[src, x]
    return out, pieces


def place(piece, src_box, dst_box):
    """把抠出来的手整体平移到目标框 (保持像素, 无重采样)。

    目标区域用**目标框的左上角**, 不是位移量 —— 用位移量会把手搬到画布左上角。
    """
    x0, y0, x1, y1 = src_box
    dx0, dy0, dx1, dy1 = dst_box
    h, w = y1 - y0, x1 - x0
    out = np.zeros_like(piece)
    out[dy0:dy0 + h, dx0:dx0 + w] = piece[y0:y0 + h, x0:x0 + w]
    return out


def make_keyboard():
    img = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fy, ny = KB['far_y'], KB['near_y']
    fx, nx = KB['far_x'], KB['near_x']
    quad = [(fx[0], fy), (fx[1], fy), (nx[1], ny), (nx[0], ny)]
    d.polygon(quad, fill=(214, 220, 230, 255))
    row_t = (0.0, 0.17, 0.38, 0.62, 1.0)
    for i in range(4):
        t0, t1 = row_t[i], row_t[i + 1]
        y0 = fy + (ny - fy) * t0
        y1 = fy + (ny - fy) * t1
        xa0 = fx[0] + (nx[0] - fx[0]) * t0
        xa1 = fx[1] + (nx[1] - fx[1]) * t0
        xb0 = fx[0] + (nx[0] - fx[0]) * t1
        xb1 = fx[1] + (nx[1] - fx[1]) * t1
        d.line([(xa0, y0), (xa1, y0)], fill=(146, 156, 174, 255), width=5)
        n = 11 if i < 3 else 1
        if n == 1:
            d.line([(xb0 + 34, y1 - 7), (xb1 - 34, y1 - 7)], fill=(168, 178, 196, 255), width=4)
        else:
            for k in range(1, n):
                u = k / float(n)
                d.line([(xa0 + (xb0 - xa0) * u, y0), (xa1 + (xb1 - xa1) * u, y1)],
                       fill=(168, 178, 196, 255), width=3)
    for a_, b_ in ((quad[0], quad[1]), (quad[3], quad[2]), (quad[0], quad[3]), (quad[1], quad[2])):
        d.line([a_, b_], fill=(92, 102, 120, 255), width=4)
    return img


def over(dst, src):
    """标准 alpha 合成: src 叠在 dst 之上。

    **不能用逐通道 np.maximum** —— 白大褂的 RGB 255 会把叠在它上面的
    手部肤色 (230,190,170) 顶成白色, 手看起来就"半透明/发白"。
    """
    sa = src[:, :, 3:4].astype(np.float32) / 255.0
    da = dst[:, :, 3:4].astype(np.float32) / 255.0
    oa = sa + da * (1.0 - sa)
    safe = np.maximum(oa, 1e-6)
    rgb = (src[:, :, :3].astype(np.float32) * sa
           + dst[:, :, :3].astype(np.float32) * da * (1.0 - sa)) / safe
    out = np.zeros_like(dst)
    out[:, :, :3] = np.clip(rgb, 0, 255)
    out[:, :, 3:4] = np.clip(oa * 255.0, 0, 255)
    return out


def main():
    a = load(SIT)
    body, pieces = extract_and_erase(a, HAND_BOXES)

    # 独立手部道具 (front 层用)
    hands = np.zeros_like(a)
    for key, sb in HAND_BOXES.items():
        hands = over(hands, place(pieces[key], sb, TARGET[key]))

    # 键盘 (front 层, 在手之下)
    kb = np.asarray(make_keyboard()).astype(np.int32)

    # 桌沿 (front, 最后画)
    desk = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
    dd = ImageDraw.Draw(desk)
    dd.polygon([(250, 688), (900, 688), (892, 726), (258, 726)], fill=(206, 186, 156, 255))
    dd.polygon([(258, 714), (892, 714), (886, 734), (264, 734)], fill=(176, 154, 126, 255))
    for (lx0, lx1) in ((272, 332), (826, 886)):
        dd.polygon([(lx0, 720), (lx1, 720), (lx1 - 8, 1001), (lx0 + 8, 1001)],
                   fill=(176, 154, 126, 255))
    desk = np.asarray(desk).astype(np.int32)

    out = over(body, kb)
    out = over(out, hands)
    out = over(out, desk)

    bg2 = Image.new('RGBA', (1024, 1024), (246, 248, 252, 255))
    bg2.alpha_composite(to_im(body))
    bg2.convert('RGB').resize((512, 512), Image.LANCZOS).save('/tmp/r172_body.png')

    bg = Image.new('RGBA', (1024, 1024), (246, 248, 252, 255))
    bg.alpha_composite(to_im(out))
    bg.convert('RGB').resize((512, 512), Image.LANCZOS).save('/tmp/r172_spike.png')
    print('✅ /tmp/r172_spike.png  /tmp/r172_body.png')

    # 抹手后是否有残留的手部像素 (用肤色在原位统计)
    for key, box in HAND_BOXES.items():
        x0, y0, x1, y1 = box
        reg = body[y0:y1, x0:x1]
        sm = skin_mask(reg)
        print(f'  {key} 原位残留肤色像素 = {int(sm.sum())} (区域 {box})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
