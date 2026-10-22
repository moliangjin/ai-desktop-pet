#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R172 办公场景构图重做 —— 恢复完整坐姿 + 3/4 透视电脑 + 可视屏幕内容。

【R167/R170 的根因与本轮的改法】
R167 的办公场景把"台面"放在 back 层, 而角色是**正面坐姿**, 躯干/大腿正好压在
台面带上 ⇒ 台面被整片挡死 ⇒ R167 只好把角色下半身剪掉 (cut_lower_body),
用户真机截图确认: 双腿消失、电脑只剩一块深灰背板。

本轮换底图 + 换图层归属, 不再剪身体:
  · 底图从 sleep_enter_01_sit (跪坐、膝盖高抬、手搭膝盖) 换成
    wake_up_01_sit_up (**双腿下垂、靴子踩地**的坐姿) ⇒ 腿/鞋天然完整;
  · 桌面/键盘/手全部**画进角色帧** (同一张 PNG 内可控 z 序):
        身体 → 桌面 → 键盘 → 手 → 桌沿桌腿
    ⇒ 桌面遮住大腿 (局部遮挡腿, 不是删除), 腿脚在桌下完整可见;
  · 电脑不再是"背板", 而是**3/4 透视的显示器正面**, 屏内画蓝白科技界面/代码。

产出 (assets/character_R172/):
  work_1.png / work_2.png   角色帧 (含桌面/键盘/手; work_1 低头打字, work_2 抬头看屏)
  prop_office_chair.png     办公转椅 (back 层)
  prop_office_monitor.png   3/4 显示器 (front 层, 屏内可见内容)
  bake_report.json

不改角色外观、不引入外部素材、不做 i2i。
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')
OUT = os.path.join(ASSETS, 'character_R172')
SITUP = os.path.join(R138, 'wake_up', 'wake_up_01_sit_up.png')

TEX = 1024
GROUND_Y = 1001          # 场景地面行 (与 R167 一致: 道具底边贴这条线)
SHIFT_Y = GROUND_Y - 925  # 坐姿帧脚底 925 → 1001 (76px)

# --------------------------------------------------------------------------
# 角色几何 (1024 纹理坐标, 已在最终空间 = 原 sit_up 空间 + SHIFT_Y 的 y)
# --------------------------------------------------------------------------
#   头顶 115 / 下巴 376 / 肩 416 / 袖口 614~646 / 手 631~681
#   大腿(肤色) 666~736 / 长袜 731~776 / 小腿 776~946 / 靴 946~1001
HEAD_CENTER = (516, 245)
HEAD_RADII = (150, 136)
NECK_PIVOT = (516, 344)
CHIN_Y = 376
FACE_TOP_Y = 228

# 手 (原 sit_up 空间实测: 左手 x320~392 / 右手 x637~707, 腕点 L(375,558) R(649,558))
# 腕点 = 手与青色袖口的交界 (皮肤上沿的靠内侧角)
HAND_WRIST = {'L': (376, 637), 'R': (648, 635)}
HAND_ZONE = {'L': (306, 548 + SHIFT_Y, 404, 616 + SHIFT_Y),
              'R': (620, 548 + SHIFT_Y, 718, 616 + SHIFT_Y)}
# 手腕旋转角 (正 = 手指由"向外偏下"转到"向前偏内")
HAND_ROT = {'L': 38.0, 'R': -38.0}
# 手整体上抬: 让手背盖住桌面远沿 (y=620), 手与袖子之间不留缝
HAND_LIFT = 16

# --------------------------------------------------------------------------
# 桌面 / 键盘 / 桌腿 (最终空间)
# --------------------------------------------------------------------------
DESK_FAR_Y, DESK_NEAR_Y = 620, 706
DESK_FAR_X = (300, 860)
DESK_NEAR_X = (258, 902)
DESK_LIP_Y = (706, 742)
DESK_LEG_X = ((268, 312), (848, 892))

KB_FAR_Y, KB_NEAR_Y = 634, 690
KB_FAR_X = (344, 692)
KB_NEAR_X = (328, 710)

# --------------------------------------------------------------------------
# 显示器 (3/4 透视, 屏幕正面朝观众偏左)
# --------------------------------------------------------------------------
MON_SCREEN = [(690, 398), (872, 440), (866, 524), (700, 550)]   # 屏幕四边形
MON_BEZEL = 14
MON_STAND_BASE_Y = 618   # 显示器底座落在桌面远端附近

# 配色 (蓝白科技系)
C_DESK_TOP = (232, 236, 243, 255)
C_DESK_TOP2 = (206, 214, 228, 255)
C_DESK_EDGE = (150, 164, 188, 255)
C_DESK_LIP = (196, 206, 224, 255)
C_DESK_LEG = (168, 180, 202, 255)
C_KB_BODY = (236, 240, 247, 255)
C_KB_KEY = (176, 188, 208, 255)
C_KB_LINE = (140, 154, 178, 255)
C_BEZEL = (36, 48, 74, 255)
C_SCREEN_BG = (238, 244, 252, 255)
C_OUTLINE = (18, 26, 46, 255)


# ====================================================================== 基础工具

def pline(d, pts, fill, width=1):
    """PIL 11 的 ImageDraw.line 只吃扁平坐标 (list of tuples 会报 incorrect coordinate type)。"""
    flat = [c for p in pts for c in (p[0], p[1])]
    d.line(flat, fill=fill, width=width)


def load(path):
    return Image.open(path).convert('RGBA')


def to_np(im):
    return np.asarray(im).astype(np.int32)


def to_im(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')


def over(dst, src):
    """标准 source-over 合成 (直通 alpha)。

    绝不能用逐通道 np.maximum —— 白大褂的 RGB 255 会把叠上去的肤色顶成白色。
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


def dilate(mask, n=1):
    """n 轮 3x3 膨胀 (保持形状)。"""
    out = mask.copy()
    for _ in range(n):
        p = np.pad(out, 1, mode='constant', constant_values=False)
        out = (p[0:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, 0:-2] | p[1:-1, 2:] | out)
    return out


def skin_mask(a):
    r, g, b, al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (al > 60) & (r > 190) & (g > 135) & (g < 210) & (b > 105) & (b < 190) & (r > b + 30)


def rot_patch(a, pivot, ang_deg, out_shape=None):
    """把 RGBA 数组绕 pivot 旋转 ang 度 (正 = 屏幕顺时针), 双线性重采样。

    旋转方向约定: 输出像素 (x,y) 采样输入 pivot + M(-ang)·(x-pivot),
    与 36_R158_arm_rig.rotate_rgba 一致 (内容转 -ang)。
    """
    h, w = a.shape[:2]
    if out_shape is None:
        out_shape = (h, w)
    oh, ow = out_shape
    th = np.deg2rad(ang_deg)
    c, s = np.cos(th), np.sin(th)
    yy, xx = np.mgrid[0:oh, 0:ow]
    px, py = pivot
    dxo, dyo = xx - px, yy - py
    sx = px + (c * dxo - s * dyo)
    sy = py + (s * dxo + c * dyo)
    sx = np.clip(sx, 0, w - 1.001)
    sy = np.clip(sy, 0, h - 1.001)
    x0 = np.floor(sx).astype(int)
    y0 = np.floor(sy).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    fx = (sx - x0)[:, :, None]
    fy = (sy - y0)[:, :, None]
    top = a[y0, x0] * (1 - fx) + a[y0, x1] * fx
    bot = a[y1, x0] * (1 - fx) + a[y1, x1] * fx
    return top * (1 - fy) + bot * fy


def persp_coeffs_quad_to_content(quad, content_size):
    """透视系数: 输出画布坐标 → 内容图坐标。

    PIL 的 Image.PERSPECTIVE 是"输出像素 (x,y) → 输入像素 (u,v)",
    所以这里要解的是 **四边形角点 → 内容矩形角点** 的单应。
    """
    W, H = content_size
    content_corners = [(0, 0), (W, 0), (W, H), (0, H)]
    A, B = [], []
    for (x, y), (X, Y) in zip(quad, content_corners):
        A.append([x, y, 1, 0, 0, 0, -x * X, -y * X])
        B.append(X)
        A.append([0, 0, 0, x, y, 1, -x * Y, -y * Y])
        B.append(Y)
    coeffs = np.linalg.solve(np.array(A, dtype=float), np.array(B, dtype=float))
    return coeffs.tolist()


# ====================================================================== 角色处理
def shift_down(im, dy):
    a = to_np(im)
    out = np.zeros_like(a)
    out[dy:, :, :] = a[:TEX - dy, :, :]
    return to_im(out)


def extract_hands(a):
    """把手 (肤色 + 描边) 从身体帧里抠出来, 原位留透明 (桌面会盖住)。

    **只抠手, 不抠青色袖口** —— 袖口是"袖子末端", 它必须与身体里的白袖子保持
    同向; R172 第一版把袖口一起抠出来跟着手旋转, 结果袖口跟着歪 76°,
    与袖子脱节成一个孤立的青色小块 (A/B 实测确认)。
    """
    pieces = {}
    for key, box in HAND_ZONE.items():
        x0, y0, x1, y1 = box
        sub = a[y0:y1, x0:x1]
        sm = skin_mask(sub)
        r, g, b = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
        dark = (sub[:, :, 3] > 60) & (r < 165) & (g < 165) & (b < 180)
        teal = (sub[:, :, 3] > 60) & (b > 130) & (g > 140) & (b >= r - 12)
        m = dilate(sm | dark, 2) & ~teal
        # 只保留与肤色连通的部分 (避免把手腕处大褂的暗褶皱也吃进来)
        m = m & (dilate(sm, 4) | dilate(dark & dilate(sm, 6), 1))
        full = np.zeros(a.shape[:2], bool)
        full[y0:y1, x0:x1] = m
        piece = np.zeros_like(a)
        piece[full] = a[full]
        pieces[key] = piece
    return pieces


def build_frame(base_np, hands_np, head_spec):
    """合成一帧: 身体 → 桌面 → 键盘 → 手 → 桌沿桌腿。"""
    frame = base_np.copy()
    frame[base_np[:, :, 3] == 0] = 0
    # 手从身体里抠掉 → 原位透明
    for key, piece in hands_np.items():
        pass  # 已在 base_np 里挖空
    frame = over(frame, DESK_SURFACE_NP)
    frame = over(frame, KEYBOARD_NP)
    frame = over(frame, hands_np['composite'])
    frame = over(frame, DESK_FRONT_NP)
    return frame


# ====================================================================== 桌面绘制
def draw_desk_surface():
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    quad = [(DESK_FAR_X[0], DESK_FAR_Y), (DESK_FAR_X[1], DESK_FAR_Y),
            (DESK_NEAR_X[1], DESK_NEAR_Y), (DESK_NEAR_X[0], DESK_NEAR_Y)]
    d.polygon(quad, fill=C_DESK_TOP)
    # 远端略深 (透视: 远处暗一点)
    d.polygon([(DESK_FAR_X[0], DESK_FAR_Y), (DESK_FAR_X[1], DESK_FAR_Y),
               (DESK_FAR_X[1] - 26, DESK_FAR_Y + 34), (DESK_FAR_X[0] + 26, DESK_FAR_Y + 34)],
              fill=C_DESK_TOP2)
    # 边缘高光
    pline(d, [quad[0], quad[1]], fill=C_DESK_EDGE, width=4)
    pline(d, [quad[3], quad[2]], fill=C_DESK_EDGE, width=5)
    pline(d, [quad[0], quad[3]], fill=C_DESK_EDGE, width=4)
    pline(d, [quad[1], quad[2]], fill=C_DESK_EDGE, width=4)
    return img


def draw_keyboard():
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fy, ny = KB_FAR_Y, KB_NEAR_Y
    fx, nx = KB_FAR_X, KB_NEAR_X
    quad = [(fx[0], fy), (fx[1], fy), (nx[1], ny), (nx[0], ny)]
    d.polygon(quad, fill=C_KB_BODY)
    rows = [0.0, 0.22, 0.46, 0.72, 1.0]
    for i in range(4):
        t0, t1 = rows[i], rows[i + 1]
        y0 = fy + (ny - fy) * t0
        y1 = fy + (ny - fy) * t1
        xa0 = fx[0] + (nx[0] - fx[0]) * t0
        xa1 = fx[1] + (nx[1] - fx[1]) * t0
        xb0 = fx[0] + (nx[0] - fx[0]) * t1
        xb1 = fx[1] + (nx[1] - fx[1]) * t1
        pline(d, [(xa0, y0), (xa1, y0)], fill=C_KB_LINE, width=4)
        n = 13 if i < 3 else 4
        for k in range(1, n):
            u = k / float(n)
            pline(d, [(xa0 + (xb0 - xa0) * u, y0), (xa1 + (xb1 - xa1) * u, y1)],
                 fill=C_KB_KEY, width=3)
    for p, q in ((quad[0], quad[1]), (quad[3], quad[2]), (quad[0], quad[3]), (quad[1], quad[2])):
        pline(d, [p, q], fill=C_KB_LINE, width=4)
    return img


def draw_desk_front():
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ly0, ly1 = DESK_LIP_Y
    d.polygon([(DESK_NEAR_X[0], ly0), (DESK_NEAR_X[1], ly0),
               (DESK_NEAR_X[1] - 6, ly1), (DESK_NEAR_X[0] + 6, ly1)], fill=C_DESK_LIP)
    pline(d, [(DESK_NEAR_X[0], ly0), (DESK_NEAR_X[1], ly0)], fill=C_DESK_EDGE, width=4)
    for (lx0, lx1) in DESK_LEG_X:
        d.polygon([(lx0, ly1 - 8), (lx1, ly1 - 8),
                   (lx1 - 9, GROUND_Y), (lx0 + 9, GROUND_Y)], fill=C_DESK_LEG)
        pline(d, [(lx0, ly1 - 8), (lx0 + 9, GROUND_Y)], fill=C_DESK_EDGE, width=4)
        pline(d, [(lx1, ly1 - 8), (lx1 - 9, GROUND_Y)], fill=C_DESK_EDGE, width=4)
    return img


# ====================================================================== 显示器
def draw_screen_content(w, h):
    """屏内内容: 蓝白科技界面 (标题栏 + 侧栏 + 代码行 + 图表)。"""
    img = Image.new('RGBA', (w, h), C_SCREEN_BG)
    d = ImageDraw.Draw(img)
    # 标题栏
    d.rectangle([0, 0, w, max(3, h // 9)], fill=(52, 118, 190, 255))
    for i in range(3):
        cx = max(4, w // 12) + i * max(7, w // 14)
        d.ellipse([cx, h // 26, cx + max(3, w // 30), h // 26 + max(3, w // 30)],
                  fill=(226, 240, 255, 255))
    # 左侧栏
    sw = max(8, w // 7)
    d.rectangle([0, h // 9, sw, h], fill=(214, 228, 246, 255))
    for i in range(6):
        yy = h // 9 + 4 + i * max(4, h // 12)
        if yy + 2 > h:
            break
        d.rectangle([2, yy, sw - 3, yy + max(2, h // 34)], fill=(150, 186, 224, 255))
    # 代码行 (右侧主区)
    x0 = sw + max(3, w // 18)
    widths = [0.62, 0.44, 0.70, 0.36, 0.58, 0.50, 0.66, 0.40]
    cols = [(64, 132, 214), (46, 104, 178), (96, 160, 226)]
    for i, frac in enumerate(widths):
        yy = h // 9 + 4 + i * max(4, h // 11)
        if yy + 2 > h:
            break
        wdt = int((w - x0 - 4) * frac)
        d.rectangle([x0, yy, x0 + wdt, yy + max(2, h // 30)],
                    fill=cols[i % len(cols)] + (255,))
    # 右上角一个状态块 (亮色)
    bx = w - max(10, w // 6)
    by = h // 9 + max(3, h // 16)
    d.rectangle([bx, by, w - 3, by + max(4, h // 9)], fill=(120, 206, 214, 255))
    return img


def draw_monitor():
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sq = MON_SCREEN
    # 底座 + 支架
    cx = (sq[0][0] + sq[1][0]) // 2
    base_y = MON_STAND_BASE_Y
    d.polygon([(cx - 46, base_y), (cx + 46, base_y),
               (cx + 60, base_y + 14), (cx - 60, base_y + 14)], fill=C_BEZEL)
    d.polygon([(cx - 14, sq[2][1]), (cx + 14, sq[2][1]),
               (cx + 10, base_y), (cx - 10, base_y)], fill=(56, 70, 102, 255))
    # 屏幕外框 (bezel) = 四边形外扩
    px, py = sq[0]
    bx = [p[0] + MON_BEZEL for p in sq]
    by = [p[1] for p in sq]
    bx = [sq[0][0] - MON_BEZEL, sq[1][0] + MON_BEZEL, sq[2][0] + MON_BEZEL, sq[3][0] - MON_BEZEL]
    by = [sq[0][1] - MON_BEZEL, sq[1][1] - MON_BEZEL, sq[2][1] + MON_BEZEL, sq[3][1] + MON_BEZEL]
    d.polygon(list(zip(bx, by)), fill=C_BEZEL)
    # 屏内内容: 先在矩形里画, 再透视贴到四边形
    sw, sh = 360, 300
    content = draw_screen_content(sw, sh)
    coeffs = persp_coeffs_quad_to_content(sq, (sw, sh))
    warped = content.transform((TEX, TEX), Image.PERSPECTIVE, coeffs,
                               resample=Image.BICUBIC)
    img.alpha_composite(warped, (0, 0))
    d = ImageDraw.Draw(img)
    # 屏幕内的反光 (左上一道淡高光)
    d.polygon([sq[0], (sq[0][0] + 60, sq[0][1]), (sq[0][0] + 10, sq[3][1]), sq[3]],
              fill=(255, 255, 255, 26))
    # 屏幕边框线
    pline(d, list(zip(sq, sq[1:] + sq[:1])), fill=(12, 18, 34, 255), width=5)
    return img


def draw_chair():
    """办公转椅 (back 层): 靠背 + 座面。

    **不画五星脚与中柱** —— 角色坐在椅子上时, 中柱正好落在两腿之间,
    R172 第一版画了完整转椅, 结果椅子底盘从两脚之间露出来, 看着像脚边一坨
    灰色异物 (真机截图复核确认)。靠背 + 座面已经足够读出"她坐在办公椅上"。
    """
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 靠背 (角色身后, 从肩/头两侧露出)
    bx0, bx1, by0, by1 = 362, 668, 168, 566
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=62,
                        fill=(190, 207, 231, 255), outline=C_OUTLINE, width=6)
    d.rounded_rectangle([bx0 + 18, by0 + 26, bx1 - 18, by1 - 96], radius=42,
                        fill=(230, 239, 251, 255), outline=(166, 186, 214, 255), width=4)
    # 腰靠 (靠背下段的一道横向分割)
    d.rounded_rectangle([bx0 + 26, by1 - 92, bx1 - 26, by1 - 40], radius=24,
                        fill=(196, 212, 236, 255), outline=(166, 186, 214, 255), width=4)
    # 座面
    d.rounded_rectangle([352, 540, 678, 622], radius=30,
                        fill=(190, 206, 230, 255), outline=C_OUTLINE, width=5)
    d.rounded_rectangle([366, 552, 664, 606], radius=24,
                        fill=(222, 232, 248, 255))
    return img


# ====================================================================== 头部
def head_transform(a, rotate=0.0, dy=0.0, dx=0.0):
    """坐姿专用的头部局部弯曲 (连续权重场, 无切口)。"""
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    e = np.sqrt(((xx - HEAD_CENTER[0]) / HEAD_RADII[0]) ** 2 +
                ((yy - HEAD_CENTER[1]) / HEAD_RADII[1]) ** 2)
    t = np.clip((e - 1.02) / (1.78 - 1.02), 0.0, 1.0)
    t = t * t * (3 - 2 * t)
    wgt = np.clip(1.0 - t, 0.0, 1.0)
    neck = np.exp(-(((xx - 516) / 58.0) ** 2 + ((yy - 356) / 34.0) ** 2))
    wgt = wgt * (1.0 - 0.8 * neck)
    th = np.deg2rad(rotate) * wgt
    px, py = NECK_PIVOT
    dxo, dyo = xx - px, yy - py
    cth, sth = np.cos(th), np.sin(th)
    sx = px + (cth * dxo + sth * dyo) + dx * wgt
    sy = py + (-sth * dxo + cth * dyo) + dy * wgt
    # 双线性重采样
    sx = np.clip(sx, 0, w - 1.001)
    sy = np.clip(sy, 0, h - 1.001)
    x0 = np.floor(sx).astype(int)
    y0 = np.floor(sy).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    fx = (sx - x0)[:, :, None]
    fy = (sy - y0)[:, :, None]
    top = a[y0, x0] * (1 - fx) + a[y0, x1] * fx
    bot = a[y1, x0] * (1 - fx) + a[y1, x1] * fx
    return top * (1 - fy) + bot * fy


# ====================================================================== 主流程
DESK_SURFACE_NP = None
KEYBOARD_NP = None
DESK_FRONT_NP = None


def main():
    global DESK_SURFACE_NP, KEYBOARD_NP, DESK_FRONT_NP
    os.makedirs(OUT, exist_ok=True)

    sit = load(SITUP)
    base_img = shift_down(sit, SHIFT_Y)
    base = to_np(base_img)

    # 1) 抠手 (只留手, 袖口留在身体里)
    pieces = extract_hands(base)
    body = base.copy()
    for key, piece in pieces.items():
        m = piece[:, :, 3] > 0
        body[m] = 0
        # 手腕处的断口: 用袖口/手背的暗色描边补一小圈, 避免出现亮洞
    # 2) 手旋转 (绕腕) —— 手指由"向外偏下"转到"向前偏内"
    hands = {}
    for key, piece in pieces.items():
        rotated = rot_patch(piece.astype(np.float32), HAND_WRIST[key], HAND_ROT[key])
        lifted = np.zeros_like(rotated)
        lifted[HAND_LIFT:, :, :] = rotated[:TEX - HAND_LIFT, :, :]
        hands[key] = lifted.astype(np.int32)

    # 3) 道具
    DESK_SURFACE_NP = to_np(draw_desk_surface())
    KEYBOARD_NP = to_np(draw_keyboard())
    DESK_FRONT_NP = to_np(draw_desk_front())

    # 4) 两帧
    specs = [
        ('work_1', dict(rotate=13.0, dy=7.0, dx=-3.0), 9),
        ('work_2', dict(rotate=-5.0, dy=-3.0, dx=7.0), 0),
    ]
    report = {'round': 'R172', 'base': os.path.relpath(SITUP, CAND),
              'shift_y': SHIFT_Y, 'ground_tex_y': GROUND_Y, 'items': []}
    for name, head_spec, hand_dy in specs:
        b = body.copy()
        # 手部合成 (按帧偏移做"按下/抬起")
        hs = np.zeros_like(base)
        for key in ('L', 'R'):
            piece = hands[key]
            if hand_dy:
                piece = np.roll(piece, hand_dy, axis=0)
            hs = over(hs, piece.astype(np.int32))
        # 头部
        b = head_transform(b.astype(np.float32), **head_spec).astype(np.int32)
        frame = b.copy()
        frame = over(frame, DESK_SURFACE_NP)
        frame = over(frame, KEYBOARD_NP)
        frame = over(frame, hs)
        frame = over(frame, DESK_FRONT_NP)
        out = to_im(frame)
        path = os.path.join(OUT, name + '.png')
        out.save(path)
        bb = out.getbbox()
        report['items'].append({'file': name + '.png', 'bbox': list(bb) if bb else None,
                                'head': head_spec, 'hand_offset_y': hand_dy})
        print(f'  ✅ {name}.png bbox={bb}')

    # 5) 道具
    chair = draw_chair()
    chair.save(os.path.join(OUT, 'prop_office_chair.png'))
    print(f'  ✅ prop_office_chair.png bbox={chair.getbbox()}')
    mon = draw_monitor()
    mon.save(os.path.join(OUT, 'prop_office_monitor.png'))
    print(f'  ✅ prop_office_monitor.png bbox={mon.getbbox()}')

    report['props'] = ['prop_office_chair.png', 'prop_office_monitor.png']
    with open(os.path.join(OUT, 'bake_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
