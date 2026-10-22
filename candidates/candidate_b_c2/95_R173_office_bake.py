#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R173 办公场景透视与手部遮挡最终整改 —— 真 3/4 侧前方构图。

【R172 的两个硬伤 (用户真机截图确认)】
  1. 显示器**正面朝向观众**, 人物坐在显示器背面 —— 几何自相矛盾。
     R172 自己也把它写进了 honest_limits ("正面坐姿 + 正对观众的显示器只能这样
     表达看得到屏幕内容"), 但仍然当 PASS 交了 ⇒ 本轮必须换掉。
  2. 双手被键盘/桌面遮挡, 手掌看不见, 手臂→手腕→手指的衔接不成立。

【R173 的根因级改法】
  · **底图换成真 3/4 坐姿** `sleep_enter_01_sit` (膝盖/脸都朝画面左),
    角色面对显示器 ⇒ 显示器放到**画面左侧更深处**, 屏幕正面朝**右**(面向角色)
    并带一点朝观众的分量 ⇒ 观众从侧面看到一块**被透视压缩的屏幕内容**,
    显示器/角色/桌面共用同一套透视, 不再出现"人坐在屏幕背面"。
  · **桌面改成斜向透视台面** (左端更远 → 更高), 角色坐在桌子右端,
    桌面遮住膝盖(局部遮挡, 不是删除), 小腿与靴子在桌下完整可见。
  · **手的图层关系**: 原手留在身体帧里 → 桌面画上去时把手原位盖住 →
    再把手的像素**复制一份压到键盘之上** ⇒ 手掌不被键盘整体遮住,
    指尖落在键区, 手臂→袖口→手腕→手指的衔接全部来自原画, 没有假接缝。

产出 (assets/character_R173/):
  work_1.png / work_2.png   角色帧 (椅子+桌面+键盘+显示器+双手全部内嵌)
  bake_report.json

不改角色外观、不引入外部素材、不做 i2i。
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')
OUT = os.path.join(ASSETS, 'character_R173')
BASE = os.path.join(R138, 'sleep_enter', 'sleep_enter_01_sit.png')

TEX = 1024
GROUND_Y = 1001          # 场景地面行 (与 R167/R172 一致)

# --------------------------------------------------------------------------
# 角色几何 (1024 纹理 = 最终空间; 底图脚底 1002 ≈ 地面行 1001, 无需平移)
# --------------------------------------------------------------------------
#   头顶 38 / 下巴 ~300 / 肩 ~340 / 躯干 x470~720 / 膝盖 x400~570 y600~720
#   靴子 x355~620 y830~1002
#   左臂(画面左): 袖口 x430~450 y535~570, 手 x335~430 y555~645, 腕点 (405,556)
#   右臂(画面右): 袖口 x500~520 y545~580, 手 x435~505 y560~648, 腕点 (500,552)

HAND_WRIST = {'L': (405, 556), 'R': (500, 552)}
HAND_ZONE = {'L': (328, 528, 432, 652), 'R': (432, 530, 528, 654)}

# --------------------------------------------------------------------------
# 桌面 (斜向透视: 左端更远 → 更高)
# --------------------------------------------------------------------------
DESK_FAR = [(215, 548), (690, 645)]     # 远沿 (贴角色身体那侧), 左高右低
DESK_NEAR = [(165, 662), (640, 757)]    # 近沿 (朝观众那侧)

# 键盘 (桌面远端, 在手正下方)
KEY_QUAD = [(330, 566), (548, 600), (532, 656), (312, 616)]

# 显示器 (站在桌面远端左侧; 屏幕正面朝右 = 面向角色, 略带朝观众)
# 透视要点: **远侧(左)边明显更矮**, 近侧(右)边更高 ⇒ 上下边在右侧发散,
# 收敛点在左 ⇒ 读作"屏面转向右侧的角色, 观众从侧面斜看"。
SCREEN_QUAD = [(195, 395), (330, 315), (372, 630), (215, 570)]
BEZEL = 14                              # 屏幕外框厚度
MONITOR_BASE_Y = 636                     # 底座落在桌面上

# 办公转椅 (角色身后, 大部分被身体挡住, 只在右肩外侧与头顶上方露出)
CHAIR_BACK = [(600, 300), (790, 322), (802, 600), (610, 590)]
CHAIR_SEAT = [(640, 586), (798, 596), (802, 630), (642, 620)]

# 桌子腿 (近左 / 近右)
LEG_NEAR_LEFT = [(158, 650), (186, 660), (186, 950), (162, 945)]
LEG_NEAR_RIGHT = [(632, 745), (662, 757), (662, 1001), (634, 1001)]

SHADOW = [(355, 1002), (625, 1002), (660, 960), (330, 958)]


# ====================================================================== 基础工具
def pline(d, pts, fill, width=1):
    """PIL 11 的 ImageDraw.line 只吃扁平坐标。"""
    flat = [c for p in pts for c in (p[0], p[1])]
    d.line(flat, fill=fill, width=width)


def load(path):
    return Image.open(path).convert('RGBA')


def to_np(im):
    return np.asarray(im).astype(np.int32)


def to_im(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')


def over(dst, src):
    """标准 source-over 合成 (直通 alpha)。"""
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
    out = mask.copy()
    for _ in range(n):
        p = np.pad(out, 1, mode='constant', constant_values=False)
        out = (p[0:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, 0:-2] | p[1:-1, 2:] | out)
    return out


def skin_mask(a):
    r, g, b, al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (al > 60) & (r > 180) & (g > 130) & (g < 215) & (b > 100) & (b < 200) & (r > b + 25)


def persp_coeffs_quad_to_content(quad, content_size):
    """透视系数: 输出画布坐标 → 内容图坐标 (PIL PERSPECTIVE 的方向)。"""
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


def map_into_quad(content_img, quad):
    """把内容图透视贴进四边形 (输出 1024x1024 RGBA)。"""
    w, h = content_img.size
    coeffs = persp_coeffs_quad_to_content(quad, (w, h))
    # PIL 的 transform 是"输出像素 → 输入像素", 这里解的是
    # "四边形角点 → 内容矩形角点"的单应, 与 R172 同口径。
    return content_img.transform((TEX, TEX), Image.PERSPECTIVE, coeffs,
                                 resample=Image.BICUBIC)


# ====================================================================== 绘图
def expand_quad(q, d):
    """四边形向外等距扩 d (沿角点角平分线), 用于画屏幕外框。"""
    arr = np.array(q, dtype=float)
    cen = arr.mean(axis=0)
    n = len(q)
    out = []
    for i in range(n):
        p = arr[i]
        v1 = p - arr[(i - 1) % n]
        v2 = arr[(i + 1) % n] - p
        v1 = v1 / (np.linalg.norm(v1) + 1e-9)
        v2 = v2 / (np.linalg.norm(v2) + 1e-9)
        n1 = np.array([v1[1], -v1[0]])
        n2 = np.array([-v2[1], v2[0]])
        dv = p - cen
        dv = dv / (np.linalg.norm(dv) + 1e-9)
        b = n1 * (1 if n1 @ dv > 0 else -1) + n2 * (1 if n2 @ dv > 0 else -1)
        b = b / (np.linalg.norm(b) + 1e-9)
        out.append(tuple(p + b * d))
    return out


def draw_chair():
    """办公转椅: 画在**角色身后**(角色帧之前), 所以大部分被身体挡住,
    只在右肩外侧 + 头顶上方露出椅背 ⇒ 读作"她坐在办公椅上"。

    **刻意不画完整椅子**: 画全会变成角色右边一个灰色柜子抢主角
    (R173 第一版画整椅 = 右下一个悬空灰罐, 200×240 下完全不像椅子);
    也不画中柱与五星脚 —— 中柱正好落在两腿之间, 会在脚边露出一坨异物。
    """
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    body = (176, 191, 214, 255)
    dark = (120, 136, 162, 255)
    light = (214, 226, 242, 255)
    q = CHAIR_BACK
    d.polygon(q, fill=body)
    # 顶沿高光 (椅背上沿)
    pline(d, [q[0], q[1]], light, width=6)
    # 右侧暗边 (厚度)
    pline(d, [q[1], q[2]], dark, width=6)
    # 竖向结构线
    pline(d, [(740, 340), (748, 592)], (152, 168, 192, 255), width=4)
    # 座面 (从角色髋部右侧露出一条)
    s = CHAIR_SEAT
    d.polygon(s, fill=(158, 175, 200, 255))
    pline(d, [s[0], s[1]], dark, width=4)
    return img


def draw_shadow():
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([318, 928, 668, 978], fill=(70, 86, 112, 90))
    return img.filter(ImageFilter.GaussianBlur(10))


def draw_desk_surface():
    """斜向透视台面 (左端更远更高)。"""
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    top = (236, 241, 248, 255)
    quad = [DESK_FAR[0], DESK_FAR[1], DESK_NEAR[1], DESK_NEAR[0]]
    d.polygon(quad, fill=top)
    # 远沿高光
    pline(d, DESK_FAR, (255, 255, 255, 255), width=3)
    # 桌面浅灰蓝渐层 (近端略暗)
    shade = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    ds = ImageDraw.Draw(shade)
    ds.polygon([DESK_NEAR[0], DESK_NEAR[1], (DESK_NEAR[1][0], DESK_NEAR[1][1] + 40),
                (DESK_NEAR[0][0], DESK_NEAR[0][1] + 40)], fill=(120, 138, 166, 60))
    img.alpha_composite(shade.filter(ImageFilter.GaussianBlur(9)))
    return img


def draw_desk_front():
    """桌沿厚度 + 两条桌腿 (画在角色之后 ⇒ 真正在身前)。"""
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    edge = (206, 216, 232, 255)
    edge_d = (150, 163, 184, 255)
    n0, n1 = DESK_NEAR
    d.polygon([n0, n1, (n1[0] - 4, n1[1] + 34), (n0[0] - 4, n0[1] + 30)], fill=edge)
    pline(d, [n0, n1], edge_d, width=4)
    for leg in (LEG_NEAR_LEFT, LEG_NEAR_RIGHT):
        d.polygon(leg, fill=(206, 216, 232, 255))
        pline(d, [leg[0], leg[1]], edge_d, width=3)
        pline(d, [leg[3], leg[2]], edge_d, width=3)
    return img


def keyboard_content():
    """键盘面内容图 (键帽网格)。"""
    W, H = 420, 190
    img = Image.new('RGBA', (W, H), (222, 229, 240, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=(150, 163, 184, 255), width=3)
    rows, cols = 4, 13
    pad = 10
    cw = (W - 2 * pad) / cols
    ch = (H - 2 * pad) / rows
    for r in range(rows):
        for c in range(cols):
            x0 = pad + c * cw + 2
            y0 = pad + r * ch + 2
            x1 = x0 + cw - 5
            y1 = y0 + ch - 5
            d.rounded_rectangle([x0, y0, x1, y1], radius=3,
                                fill=(246, 249, 253, 255),
                                outline=(178, 190, 208, 255), width=1)
    # 空格键
    d.rounded_rectangle([pad + 5 * cw + 4, H - pad - ch + 4,
                         pad + 9 * cw - 4, H - pad - 4],
                        radius=3, fill=(238, 243, 250, 255),
                        outline=(178, 190, 208, 255), width=1)
    return img


def draw_keyboard():
    content = keyboard_content()
    kb = map_into_quad(content, KEY_QUAD)
    # 键盘投影 (落在桌面上)
    sh = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    ds.polygon([(KEY_QUAD[0][0] + 4, KEY_QUAD[0][1] + 6),
                (KEY_QUAD[1][0] + 6, KEY_QUAD[1][1] + 8),
                (KEY_QUAD[2][0] + 6, KEY_QUAD[2][1] + 10),
                (KEY_QUAD[3][0] + 4, KEY_QUAD[3][1] + 8)],
               fill=(70, 86, 112, 90))
    sh = sh.filter(ImageFilter.GaussianBlur(7))
    out = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    out.alpha_composite(sh)
    out.alpha_composite(kb)
    return out


def screen_content():
    """屏幕内容: 蓝白科技界面。

    **必须粗**: 这块屏在 200×240 下只有 ~34×48 px, 细线条会被采样糊掉,
    细笔画的代码行 ⇒ 全糊成灰 ⇒ 读不出"有内容"。所以只用
    标题条 + 侧栏色块 + 5 条粗代码行 + 1 个状态块。
    """
    W, H = 360, 300
    img = Image.new('RGBA', (W, H), (226, 238, 250, 255))
    d = ImageDraw.Draw(img)
    # 标题栏
    d.rectangle([0, 0, W - 1, 44], fill=(34, 82, 140, 255))
    d.rectangle([0, 44, W - 1, 50], fill=(104, 186, 232, 255))
    for i in range(3):
        d.ellipse([14 + i * 22, 14, 30 + i * 22, 30], fill=(226, 242, 255, 255))
    # 左侧栏 (实心块, 远端会被透视压缩)
    d.rectangle([0, 50, 86, H - 1], fill=(196, 220, 242, 255))
    for i in range(5):
        y = 62 + i * 46
        d.rectangle([10, y, 74, y + 28], fill=(120, 172, 222, 255) if i == 1
                    else (166, 200, 232, 255))
    # 代码行 (粗)
    y = 62
    for i, wdt in enumerate([196, 132, 224, 108, 168]):
        x = 104 + (26 if i == 1 else 0)
        d.rectangle([x, y, x + wdt, y + 18],
                    fill=(70, 122, 178, 255) if i % 2 == 0 else (118, 162, 204, 255))
        y += 42
    # 底部状态块
    d.rectangle([104, H - 58, W - 12, H - 16], fill=(198, 224, 246, 255))
    d.rectangle([116, H - 50, 206, H - 24], fill=(86, 190, 160, 255))
    return img


def draw_monitor():
    """3/4 透视显示器: 屏幕正面朝右 (面向角色), 观众从侧面看到被压缩的内容。

    透视读数: 近侧(右)边更高更宽, 远侧(左)边更矮更窄 —— 上下边在右侧**发散**,
    这是"屏面转向角色、观众从侧面斜看"的正确投影。
    """
    img = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sq = SCREEN_QUAD
    # 外框 (沿角平分线等距外扩)
    d.polygon(expand_quad(sq, BEZEL), fill=(42, 56, 76, 255))
    # 屏内内容
    content = screen_content()
    img.alpha_composite(map_into_quad(content, sq))
    # 屏面反光 (近侧更亮)
    gl = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
    dg = ImageDraw.Draw(gl)
    dg.polygon([sq[0], (sq[0][0] + 96, sq[0][1] + 4), (sq[0][0] + 60, sq[3][1]),
                (sq[0][0] + 4, sq[3][1] - 6)], fill=(255, 255, 255, 70))
    img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(8)))
    # 屏面边框
    d = ImageDraw.Draw(img)
    pline(d, list(sq) + [sq[0]], fill=(16, 24, 40, 255), width=4)
    # 支架: 立柱 + 底盘
    nx = 268
    d.polygon([(nx - 15, 560), (nx + 17, 556), (nx + 24, MONITOR_BASE_Y),
               (nx - 21, MONITOR_BASE_Y)], fill=(58, 74, 96, 255))
    d.polygon([(nx - 58, MONITOR_BASE_Y - 6), (nx + 72, MONITOR_BASE_Y - 1),
               (nx + 80, MONITOR_BASE_Y + 11), (nx - 64, MONITOR_BASE_Y + 3)],
              fill=(70, 88, 112, 255))
    return img


# ====================================================================== 手部图层
def extract_hand_layers(a):
    """把两只手 (肤色 + 描边) 抠成独立图层。

    **不抠青色袖口** —— 袖口必须与身体里的白袖子保持同向 (R172 实测教训)。
    原位保留在身体帧里 (桌面会盖住), 这里只取一份副本压到键盘之上。
    """
    out = {}
    for key, box in HAND_ZONE.items():
        x0, y0, x1, y1 = box
        sub = a[y0:y1, x0:x1]
        sm = skin_mask(sub)
        r, g, b = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
        dark = (sub[:, :, 3] > 60) & (r < 170) & (g < 170) & (b < 185)
        teal = (sub[:, :, 3] > 60) & (b > 130) & (g > 140) & (b >= r - 12)
        m = dilate(sm | dark, 2) & ~teal
        m = m & (dilate(sm, 4) | dilate(dark & dilate(sm, 6), 1))
        full = np.zeros(a.shape[:2], bool)
        full[y0:y1, x0:x1] = m
        piece = np.zeros_like(a)
        piece[full] = a[full]
        out[key] = piece
    return out


def shift_layer(piece, dx, dy):
    out = np.zeros_like(piece)
    h, w = piece.shape[:2]
    sy0, sy1 = max(0, dy), min(h, h + dy)
    dy0, dy1 = max(0, -dy), min(h, h - dy)
    sx0, sx1 = max(0, dx), min(w, w + dx)
    dx0, dx1 = max(0, -dx), min(w, w - dx)
    out[dy0:dy1, dx0:dx1] = piece[sy0:sy1, sx0:sx1]
    return out


# ====================================================================== 头部变换
# 3/4 坐姿的头部包围盒 (实测: 头顶 y=38, 最宽处 y=198 时 x 358..693, 发梢到 y≈318)
HEAD_CENTER = (525, 170)
HEAD_RADII = (172, 140)
NECK_PIVOT = (520, 318)


def head_transform(a, rotate=0.0, dy=0.0, dx=0.0):
    """头部局部变形 (连续权重场, **无切口** ⇒ 不产生接缝/鬼影)。

    权重场以头为椭圆中心, 颈部附近权重压低 ⇒ 脖子不动、头顶大幅动。
    """
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    e = np.sqrt(((xx - HEAD_CENTER[0]) / HEAD_RADII[0]) ** 2 +
                ((yy - HEAD_CENTER[1]) / HEAD_RADII[1]) ** 2)
    t = np.clip((e - 1.02) / (1.78 - 1.02), 0.0, 1.0)
    t = t * t * (3 - 2 * t)
    wgt = np.clip(1.0 - t, 0.0, 1.0)
    neck = np.exp(-(((xx - 520) / 62.0) ** 2 + ((yy - 330) / 36.0) ** 2))
    wgt = wgt * (1.0 - 0.85 * neck)
    th = np.deg2rad(rotate) * wgt
    px, py = NECK_PIVOT
    dxo, dyo = xx - px, yy - py
    cth, sth = np.cos(th), np.sin(th)
    sx = px + (cth * dxo + sth * dyo) + dx * wgt
    sy = py + (-sth * dxo + cth * dyo) + dy * wgt
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


# ====================================================================== 组帧
def build_frame(base_np, hands, hand_dx, hand_dy, head_spec):
    """合成顺序 (决定图层关系, 不能反):
        地面阴影 → 椅子 → **角色身体** → 桌面 → 显示器 → 键盘 → 双手 → 桌沿桌腿
      · 椅子在身体**之下** ⇒ 只在右肩外侧/头顶露出, 不会变成右边一个灰罐;
      · 桌面在身体**之上** ⇒ 遮住膝盖与手的原位 (局部遮挡, 不是删除);
      · 双手在键盘**之上** ⇒ 手掌不被键盘整体遮住, 指尖落在键区;
      · 桌沿桌腿最后 ⇒ 桌腿真正在角色身前。
    """
    frame = to_np(draw_shadow())
    frame = over(frame, to_np(draw_chair()))
    body = head_transform(base_np, **head_spec)
    frame = over(frame, body)
    frame = over(frame, to_np(draw_desk_surface()))
    frame = over(frame, to_np(draw_monitor()))
    frame = over(frame, to_np(draw_keyboard()))
    # 手压在键盘之上 (手掌不被键盘整体遮住)
    for key in ('L', 'R'):
        frame = over(frame, shift_layer(hands[key], hand_dx, hand_dy))
    frame = over(frame, to_np(draw_desk_front()))
    # **裁到地面行 1001**: 阴影的模糊会溢出到 1024, 而帧 bbox 高度是
    # **全局缩放的约束之一** (256×256 下 avail/h 会被它抢走 ⇒ 全局比例变化 ⇒
    # 所有场景的渲染尺寸都被改动)。R172 的帧底边是 1002, 这里保持同一口径。
    frame[GROUND_Y + 1:, :, 3] = 0
    return frame


def main():
    os.makedirs(OUT, exist_ok=True)
    base = load(BASE)
    base_np = to_np(base)
    hands = extract_hand_layers(base_np)

    report = {
        'round': 173,
        'base': 'character_R138/sleep_enter/sleep_enter_01_sit.png',
        'base_bbox': [338, 38, 721, 1002],
        'ground_tex_y': GROUND_Y,
        'geometry': {
            'desk_far': DESK_FAR, 'desk_near': DESK_NEAR,
            'keyboard_quad': KEY_QUAD, 'screen_quad': SCREEN_QUAD,
            'chair_back': CHAIR_BACK,
        },
        'frames': [],
    }

    # work_1 = 低头看键盘 (手指按下), work_2 = 抬头看屏幕 (打字间隙)
    # 手只做**向下**位移: 原手留在身体帧里被桌面盖住, 副本下移 ⇒
    # 露出来的只是原手腕那几像素 (与副本重叠, 连成一只手),
    # **不会像"上下移动"那样在指尖留一条鬼影** (R158 踩过的坑)。
    # head_transform 的 dy 是"内容位移"(采样源往下 = 画面往上), 故低头用负值。
    specs = [
        ('work_1', 0, 7, {'rotate': -2.5, 'dy': -9, 'dx': 0}),
        ('work_2', 0, 1, {'rotate': 1.5, 'dy': 3, 'dx': 0}),
    ]
    for name, hdx, hdy, hspec in specs:
        frame = build_frame(base_np, hands, hdx, hdy, hspec)
        im = to_im(frame)
        im.save(os.path.join(OUT, name + '.png'))
        a = np.asarray(im)[:, :, 3]
        ys, xs = np.nonzero(a > 0)
        report['frames'].append({
            'file': name + '.png',
            'bbox': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
            'hand_shift': [hdx, hdy],
        })
        print(f'✅ {name}.png  bbox={[int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1]}')

    with open(os.path.join(OUT, 'bake_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f'📦 {OUT}')


if __name__ == '__main__':
    main()
