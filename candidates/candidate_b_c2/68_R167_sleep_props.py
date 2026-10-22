#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R167 睡眠场景道具重做 —— 被子材质 (蓬松浅蓝布被) + 床 (床垫 / 床架可见)。

背景 (用户原话):
    "被子已经覆盖身体, 但目前像光滑的灰蓝色硬壳, 缺乏布料质感。"
    "床垫和床架仍应清楚可见 (当前几乎看不见, 只有一条白边)。"

做法: 纯 PIL + numpy 程序化绘制, **不调用任何 AI 生图 / i2i**。

被子的核心变化 —— 从 "色块" 变成 "有高度场的布料":
    旧做法 = 一张竖向渐变 + 几条 alpha 极低的弧线 ⇒ 在 200x240 上完全读不出来,
            剩下的就是一块**光滑的灰蓝色硬壳**。
    新做法 = 先构造**高度场 h(x, y)**, 分三层:
        form  (形体)  = 布被盖在身体上的大起伏 (胸/臀/腿几个软包)
        puff  (蓬松)  = 绗缝鼓包 —— 菱形格 + 坐标扰动, 让缝线有机地弯
        fold  (褶皱)  = 折痕沟槽 (valley)
    再用 n = (-dh/dx, -dh/dy, 1) 做 Lambert 着色, 三层**分开**给权重:
        形体柔 (大梯度), 鼓包弱 (只是"棉"的暗示), 褶皱强 (要看得见一条条折痕)。
    ⇒ 鼓包自动出高光/凹陷, 沟槽自动出"一侧亮边 + 另一侧柔影"。
    最后叠加: 顶部翻折被沿 / 轮廓环境遮蔽 / 细布纹噪声 / 边缘羽化。

床的核心变化 —— 让"这是一张床"在 200x240 上能读出来:
    实测 (200x240, scale=0.1963): 画面底部对应纹理 y≈734,
    角色身体最低点在 y=690 (R153 帧) ⇒ **画在 y>700 的床腿/横梁基本看不见**
    (旧版床腿 744~806 被整条裁掉, 所以旧版"几乎看不见床架")。
    新版把床的近端下沿整体提进可见带:
      · 床头板 (左侧立柱 + 顶部横档)  —— 最强的"床"信号, 且不是"梯子";
      · 枕头 (角色头下, 白色软体 + 高光 + 陷进床垫的阴影);
      · 床垫 = 顶面(床单) + 侧面两层, 有厚度, 正好在角色身体下沿之下;
      · 木质床侧栏 (横梁)  —— 暖木色, 与冷蓝床品拉开对比;
      · 2 条床腿 (左后角 x 0~56, 右后角 x 980~1024) 往下伸到地面行 818;
      · 床不比被子抢戏: 饱和度/明度低于被子, 但**色相对比**够 (暖木 vs 冷蓝)。

硬约束:
  · 道具仍是带 alpha 的独立 PNG (不是一张不透明大背景);
  · prop_moon.png 完全不动;
  · QUILT_TOP_EDGE / QUILT_BOTTOM_EDGE / QUILT_LEFT_EDGE 三张表一个数都不改
    (只改**材质表现**, 不改轮廓位置);
  · prop_bed.png 的地面行 floor_tex_y 仍是 818, bbox 底边仍精确等于 818;
  · 只写 assets/character_R156/prop_quilt.png 与 prop_bed.png。

用法:
    python3 68_R167_sleep_props.py
"""
import importlib.util
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))

# 复用 30_R156_props_bake.py 的调色板 / 工具函数 (该文件顶层无写文件副作用)
_spec = importlib.util.spec_from_file_location(
    'r156props', os.path.join(HERE, '30_R156_props_bake.py'))
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

S = B.S                    # 1024
OUT = os.path.join(HERE, 'assets', 'character_R156')

# ======================================================================
# 新调色板 (R167) —— 偏浅、偏暖, 明确区别于旧版的灰蓝
# ======================================================================
Q_LIT = (224, 238, 250)      # #E0EEFA  完全受光 (鼓包顶 / 折口)
Q_SHADE = (126, 166, 209)    # #7EA6D1  折痕背光侧 / 谷底 (明确是蓝, 不发灰)
Q_FOLD_EDGE = (214, 233, 250)  # 翻折被沿亮面 (带一点蓝, 不用纯白)
Q_FOLD_SHADOW = (128, 160, 196)  # 翻折被沿下的厚度阴影

# 床: 木架比被子略低饱和, 但**暖木 vs 冷蓝**的色相对比要够
BD_WOOD = (193, 160, 124, 255)     # 暖木主色
BD_WOOD_HI = (216, 188, 154, 255)  # 木面高光
BD_WOOD_D = (146, 114, 86, 255)     # 木面暗部 / 轮廓
BD_SHEET = (213, 228, 244, 255)    # 床品 (偏蓝, 与暖白枕头拉开)
BD_SHEET_D = (182, 201, 224, 255)
BD_MATT = (172, 196, 222, 255)     # 床垫侧面
BD_MATT_D = (146, 172, 200, 255)
BD_PILLOW = (247, 250, 254, 255)
BD_PILLOW_D = (210, 224, 242, 255)

# ======================================================================
# 通用工具
# ======================================================================
YY, XX = np.mgrid[0:S, 0:S].astype(np.float32)
XF = XX
YF = YY


def lerp_table(table, x):
    """按 x 线性插值一条折线表 (x 递增)。超出范围取端点值。"""
    pts = sorted(table, key=lambda p: p[0])
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    return np.interp(x, xs, ys).astype(np.float32)


def polyline_mask(pts, width=6):
    m = Image.new('L', (S, S), 0)
    d = ImageDraw.Draw(m)
    p = [(int(round(x)), int(round(y))) for (x, y) in pts]
    if len(p) >= 2:
        d.line(p, fill=255, width=max(1, int(width)), joint='curve')
    return m


def blurred01(mask, radius):
    """掩码 → 0..1 的高斯模糊场 (numpy float32)。"""
    return np.asarray(mask.filter(ImageFilter.GaussianBlur(radius)),
                      dtype=np.float32) / 255.0


def mask_from_poly(pts, blur=2.4):
    m = Image.new('L', (S, S), 0)
    ImageDraw.Draw(m).polygon([(int(x), int(y)) for (x, y) in pts], fill=255)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    return m


def band_between(edge_table, d0, d1, blur=5.0):
    """沿一条折线生成 d0..d1 宽度的条带掩码 (向下偏移 d)。"""
    top = [(x, y + d0) for (x, y) in edge_table]
    bot = [(x, y + d1) for (x, y) in reversed(edge_table)]
    m = Image.new('L', (S, S), 0)
    ImageDraw.Draw(m).polygon([(int(x), int(y)) for (x, y) in top + bot], fill=255)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    return m


def smoothstep(a, b, x):
    t = np.clip((x - a) / max(1e-6, (b - a)), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def superellipse(cx, cy, a, b, n=3.2, rot=0.0, steps=120):
    """超椭圆 (圆角矩形化) 的轮廓点 —— 用来画"枕头"这种软方形物体。

    比旋转过的椭圆好: 旋转椭圆会在四角留下尖角, 在 200x240 上会读成"白纸团"。
    """
    pts = []
    ca, sa = np.cos(rot), np.sin(rot)
    for i in range(steps):
        t = 2.0 * np.pi * i / steps
        ct, st = np.cos(t), np.sin(t)
        x = a * np.sign(ct) * abs(ct) ** (2.0 / n)
        y = b * np.sign(st) * abs(st) ** (2.0 / n)
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


# ======================================================================
# 1. 被子 (front 层)
# ======================================================================
# 折痕 (R167): 旧的 6 条竖褶太密 ⇒ 在 200x240 上读成"竖条纹 / 瓦楞";
#              新的只留 4 条**间距不均**的主褶 + 1 条胸口横褶, 深度也调低,
#              并且羽化半径放大 ⇒ 变成"一条条柔和的折痕"而不是硬管。
QUILT_FOLDS = [
    # (控制点 p0,p1,p2, 沟槽深度, 羽化半径)
    ((505, 468), (486, 566), (496, 700), 25.0, 16.0),
    ((652, 432), (642, 536), (662, 706), 26.0, 16.0),
    ((760, 522), (748, 606), (768, 722), 24.0, 16.0),
    ((884, 530), (872, 610), (892, 730), 22.0, 16.0),
]
# 胸口一道横向折痕 (布被被身体压出的横褶)
QUILT_CROSS = [
    ((548, 508), (632, 496), (716, 514), 20.0, 17.0),
]

# 身体隆起 (软包): 让布被读成"包裹着身体", 而不是一整块均匀的壳
QUILT_BUMPS = [
    # (中心 x, 中心 v, 半径 x, 半径 v, 高度)
    (566, 0.44, 86, 0.30, 24.0),
    (688, 0.40, 78, 0.28, 28.0),
    (806, 0.50, 72, 0.26, 18.0),
    (906, 0.54, 62, 0.24, 12.0),
]


def make_quilt():
    top = B.QUILT_TOP_EDGE
    bot = B.QUILT_BOTTOM_EDGE
    left = B.QUILT_LEFT_EDGE

    # ---------- 轮廓 (与 R156 完全一致, 一个数都没改) ----------
    outline = (top
               + [(978, 606), (982, 646), (980, 700)]
               + bot[1:]
               + left[1:])
    mask = mask_from_poly(outline, blur=2.8)
    m_f = np.asarray(mask, dtype=np.float32) / 255.0

    # ---------- 布料坐标场 ----------
    top_y = lerp_table(top, XF)          # 上沿 (躯干轮廓)
    bot_y = lerp_table(bot, XF)          # 下沿 (垂到床垫前沿)
    v = np.clip((YF - top_y) / np.maximum(bot_y - top_y, 1.0), 0.0, 1.0)
    vv = YF - top_y                      # 到上沿的垂直距离 (纹理 px)

    # ---------- 高度场: 形体 ----------
    thick = np.clip((690.0 - top_y) / 250.0, 0.12, 1.0)   # 身体厚度代理
    env = np.exp(-((XF - 660.0) / 330.0) ** 2)            # 横向包络
    amp = 88.0 * (0.30 + 0.70 * thick) * (0.40 + 0.80 * env)
    h_form = amp * np.sin(np.pi * v)
    for (cx, cv, rx, rv, a) in QUILT_BUMPS:
        h_form += a * np.exp(-(((XF - cx) / rx) ** 2 + ((v - cv) / rv) ** 2))

    # ---------- 高度场: 绗缝鼓包 (菱形格 + 坐标扰动) ----------
    #  用菱形 (旋转 32° 而不是正交方格) + 低频坐标扰动:
    #  · 正交方格在 200x240 上会读成"浴室瓷砖";
    #  · 菱形 + 扰动 ⇒ 缝线有机地弯, 读成"棉被的绗缝"。
    PU = 108.0
    wu = XF + 6.0 * np.sin(vv / 74.0)
    wv = vv + 5.0 * np.sin(XF / 88.0 + 0.6)
    ca, sa = np.cos(np.deg2rad(32.0)), np.sin(np.deg2rad(32.0))
    gu = wu * ca + wv * sa
    gv = -wu * sa + wv * ca
    pu = np.cos(np.pi * gu / PU) ** 2
    pv = np.cos(np.pi * gv / PU) ** 2
    puff_env = (0.30 + 0.70 * env) * smoothstep(0.02, 0.16, v) \
        * (1.0 - 0.30 * smoothstep(0.84, 1.0, v))
    h_puff = 28.0 * pu * pv * puff_env
    # 把鼓包场自身也羽化一次 ⇒ 格与格之间过渡更软, 不出现硬边
    _lo, _hi = float(h_puff.min()), float(h_puff.max())
    h_puff = blurred01(Image.fromarray(
        ((h_puff - _lo) / max(1e-6, _hi - _lo) * 255).astype(np.uint8), 'L'), 5.0) \
        * (_hi - _lo) + _lo

    # ---------- 高度场: 折痕沟槽 ----------
    h_fold = np.zeros((S, S), dtype=np.float32)
    for (p0, p1, p2, depth, rad) in QUILT_FOLDS:
        pts = B.bez(p0, p1, p2, n=56)
        h_fold -= depth * blurred01(polyline_mask(pts, width=8), rad)
    for (p0, p1, p2, depth, rad) in QUILT_CROSS:
        pts = B.bez(p0, p1, p2, n=40)
        h_fold -= depth * blurred01(polyline_mask(pts, width=7), rad)

    # ---------- 着色 ----------
    L = np.array([0.46, -0.60, 0.66], dtype=np.float32)
    L /= np.linalg.norm(L)
    L2 = np.array([-0.40, 0.48, 0.78], dtype=np.float32)   # 反弹补光 (左下)
    L2 /= np.linalg.norm(L2)

    def shade(h, k):
        gy, gx = np.gradient(h)
        nx = -k * gx
        ny = -k * gy
        nz = np.ones_like(nx)
        ln = np.sqrt(nx * nx + ny * ny + nz * nz)
        nx, ny, nz = nx / ln, ny / ln, nz / ln
        return (nx * L[0] + ny * L[1] + nz * L[2],
                nx * L2[0] + ny * L2[1] + nz * L2[2])

    d_form, f_form = shade(h_form, 0.95)
    d_puff, f_puff = shade(h_puff, 0.95)
    d_fold, f_fold = shade(h_fold, 0.95)

    # 三层分开给权重: 形体柔 / 鼓包弱 / 褶皱强
    s = 0.62 + 0.72 * (d_form - 0.60) + 0.16 * (f_form - 0.55)
    s = s + 0.85 * (d_puff - 0.62) + 0.16 * (f_puff - 0.55)
    s = s + 1.15 * (d_fold - 0.60) + 0.24 * (f_fold - 0.55)
    s = np.clip((s - 0.62) * 1.12 + 0.62, 0.0, 1.0)

    lit = np.array(Q_LIT, dtype=np.float32)
    shade_c = np.array(Q_SHADE, dtype=np.float32)
    rgb = shade_c[None, None, :] + (lit - shade_c)[None, None, :] * s[:, :, None]

    # ---------- 顶部翻折被沿 (亮面 + 厚度暗线 + 落在布上的柔影) ----------
    band = np.asarray(band_between(top, 1.0, 25.0, blur=8.0), dtype=np.float32) / 255.0
    fold_c = np.array(Q_FOLD_EDGE, dtype=np.float32)
    rgb = rgb * (1.0 - band[:, :, None] * 0.55) + fold_c[None, None, :] * (band * 0.55)[:, :, None]

    lip = np.asarray(band_between(top, 23.0, 28.0, blur=2.4), dtype=np.float32) / 255.0
    lipc = np.array(Q_FOLD_SHADOW, dtype=np.float32)
    rgb = rgb * (1.0 - lip[:, :, None] * 0.38) + lipc[None, None, :] * (lip * 0.38)[:, :, None]

    under = np.asarray(band_between(top, 26.0, 58.0, blur=14.0), dtype=np.float32) / 255.0
    rgb = rgb * (1.0 - under[:, :, None] * 0.17)

    # ---------- 轮廓环境遮蔽 (AO): 让布有厚度, 边缘不是硬切 ----------
    inside = blurred01(mask, 16.0)
    ao = np.clip((inside - 0.45) / 0.55, 0.0, 1.0)
    rgb *= (0.90 + 0.10 * ao)[:, :, None]

    # 下摆更重一点的 AO (布压在床垫上)
    hem_ao = np.asarray(band_between(bot, -44.0, 4.0, blur=13.0), dtype=np.float32) / 255.0
    rgb *= (1.0 - 0.11 * hem_ao)[:, :, None]

    # ---------- 细布纹 (打破平涂; 低幅值, 不会变脏) ----------
    rng = np.random.default_rng(20261022)
    fine = rng.normal(0.0, 1.0, size=(S // 4, S // 4)).astype(np.float32)
    fine_img = Image.fromarray(((fine * 40) + 128).clip(0, 255).astype(np.uint8), 'L')
    fine_img = fine_img.resize((S, S), Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.1))
    fine_n = (np.asarray(fine_img, dtype=np.float32) - 128.0) / 40.0
    rgb += (fine_n * 2.0)[:, :, None]

    mottle = blurred01(Image.fromarray(
        ((rng.normal(0, 1, (S // 16, S // 16)) * 60) + 128).clip(0, 255).astype(np.uint8), 'L')
        .resize((S, S), Image.BICUBIC), 26.0)
    rgb += ((mottle - 0.5) * 2.5)[:, :, None]

    rgb = np.clip(rgb, 0, 255)

    out = Image.fromarray(
        np.dstack([rgb, np.full((S, S), 255.0, dtype=np.float32)]).astype(np.uint8), 'RGBA')
    out.putalpha(mask)

    # ---------- 左沿: 短一点的 alpha 淡出 (旧版 47px 渐变太散, 边缘像块板) ----------
    ramp = np.clip((XF - 404.0) / 26.0, 0.0, 1.0)
    a = np.asarray(out.split()[3], dtype=np.float32) * ramp
    out.putalpha(Image.fromarray(a.astype(np.uint8), 'L'))

    # ---------- 落在床垫上的接触阴影 (画在被子**外面**, 让被子压住床垫) ----------
    contact = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(contact).line(
        [(int(x), int(y) + 8) for (x, y) in bot], fill=(112, 138, 170, 120), width=12)
    contact = contact.filter(ImageFilter.GaussianBlur(10))
    comp = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    comp.alpha_composite(contact)
    comp.alpha_composite(out)
    return comp


# ======================================================================
# 2. 床 (back 层; 地面纹理 y = 818)
#    200x240 可见带实测: 画面底部 = 纹理 y≈734, 角色身体最低 = 690 (R153 帧)。
#    所以床的"近端下沿"全部安排在 y 610~736 内, 床腿再往下延伸到 818。
# ======================================================================
def make_bed():
    img = B.canvas()
    d = ImageDraw.Draw(img)

    # ---------- 床头板 ----------
    #  R156 旧版是"立柱 + 两根横档" ⇒ 在 200x240 上读成一把**梯子**;
    #  v2 试过"立柱 + 顶横档" ⇒ 读成一把**锤子**;
    #  v3/v4: 只留一块**床头立板** (圆角顶 + 一道竖槽), 干净不产生别的联想。
    #
    #  R167 改动 (用户: "床垫和床架仍应清楚可见"):
    #    200x240 窗口里, 床只可能在三个地方露出来:
    #      ① 左上角 (角色头以左, 头左边那一小条 + 头顶以上那一条)
    #      ② 画面最底下一条 (床侧栏)
    #      ③ 最右边 (床尾)
    #    ⇒ 床头板做成一块**又高又窄的立板**: 上沿提到 y=236 (高于 R138 睡姿的
    #      头顶 y=265), 一直落到 y=700 ⇒ 屏幕上是一条 90+ 屏幕 px 高的木质立板,
    #      一眼就是床头, 而不是一个小木墩。
    d.rounded_rectangle([0, 240, 96, 700], radius=24,
                        fill=BD_WOOD, outline=BD_WOOD_D, width=5)
    d.rounded_rectangle([12, 256, 34, 684], radius=10, fill=BD_WOOD_HI, outline=None)
    d.rounded_rectangle([56, 256, 74, 684], radius=8, fill=BD_WOOD_D, outline=None)
    # 顶盖 (圆润的一块, 不加球形柱头 —— 球头在 200x240 上会读成棒槌)
    d.rounded_rectangle([0, 228, 108, 300], radius=30,
                        fill=BD_WOOD, outline=BD_WOOD_D, width=5)
    d.rounded_rectangle([14, 242, 92, 272], radius=15, fill=BD_WOOD_HI, outline=None)
    # 柱脚的小雕花
    d.ellipse([20, 664, 60, 696], fill=BD_WOOD_HI, outline=BD_WOOD_D, width=3)

    # ---------- 床腿 (画在床垫之前 ⇒ 在床体之下) ----------
    for lx0, lx1 in ((0, 62), (976, 1024)):
        d.rounded_rectangle([lx0, 660, lx1, 818], radius=12,
                            fill=BD_WOOD, outline=BD_WOOD_D, width=4)
        d.rounded_rectangle([lx0 + 10, 672, lx0 + 24, 812], radius=6,
                            fill=BD_WOOD_HI, outline=None)

    # ---------- 床垫: 顶面 (床单) + 侧面 两层 ----------
    #  角色身体最低点 y=690 (R153) / 746 (R138) ⇒ 床垫侧面落在身体下沿之下,
    #  读作"人躺在床上"。
    #  R167: 床垫 + 床侧栏整体**上移** (~40 纹理 px) ⇒ 200x240 窗口最底下
    #  那一小条里能露出更厚的床垫侧面 + 木质床架, 不再只是一根细木条。
    d.rounded_rectangle([0, 574, 1024, 634], radius=16, fill=BD_SHEET, outline=None)
    d.rounded_rectangle([8, 580, 1016, 606], radius=10, fill=(240, 246, 252, 255), outline=None)
    d.rounded_rectangle([0, 626, 1024, 676], radius=14, fill=BD_MATT, outline=None)
    # 床单压在床垫上的那条边 (用一条**带起伏的软边**, 避免一条死板的直线)
    sheet_edge = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    sed = ImageDraw.Draw(sheet_edge)
    sed.line([(x, y) for (x, y) in
              [(int(t), 632 + 5 * np.sin(t / 61.0) + 3 * np.sin(t / 27.0 + 1.4))
               for t in range(0, 1024, 12)]],
             fill=BD_SHEET_D, width=6)
    sheet_edge = sheet_edge.filter(ImageFilter.GaussianBlur(2.0))
    img.alpha_composite(sheet_edge)
    d = ImageDraw.Draw(img)
    # 床垫侧面上缘的滚边 (床单压住床垫的那条线)
    d.line([(10, 634), (1014, 634)], fill=BD_SHEET_D, width=4)
    # 床垫侧面下缘阴影 (让它有厚度)
    msh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(msh).rectangle([0, 664, 1024, 682], fill=(110, 136, 168, 170))
    msh = msh.filter(ImageFilter.GaussianBlur(8))
    img.alpha_composite(msh)
    d = ImageDraw.Draw(img)

    # ---------- 木质床侧栏 (横梁; 与冷蓝床品形成色相对比) ----------
    #  R167: 横梁加高到 52 纹理 px, 并加一道**下横档** ⇒ 读成"床架"而不是"木条"。
    d.rounded_rectangle([58, 672, 980, 724], radius=12,
                        fill=BD_WOOD, outline=BD_WOOD_D, width=4)
    d.rounded_rectangle([68, 678, 970, 694], radius=6, fill=BD_WOOD_HI, outline=None)
    d.rounded_rectangle([110, 700, 930, 716], radius=7, fill=BD_WOOD_D, outline=None)
    d.line([(72, 708), (966, 708)], fill=(120, 92, 68, 255), width=3)

    # ---------- 枕头 (承托头部; 角色头在纹理 x49~390 / y330~490) ----------
    #  头把枕头压住, 所以枕头要**往左下挪一点**, 让左侧和下沿露出来;
    #  形状用超椭圆 (圆角方枕), 不要用旋转椭圆 (会留尖角, 读成白纸团)。
    pillow_pts = superellipse(132, 494, 158, 116, n=3.4, rot=-0.10)
    pil = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(pil).polygon([(int(x), int(y)) for (x, y) in pillow_pts],
                                fill=BD_PILLOW, outline=BD_PILLOW_D, width=5)
    # 枕套内缝线 (让它读成"枕头"而不是白团)
    ImageDraw.Draw(pil).polygon(
        [(int(x), int(y)) for (x, y) in superellipse(134, 496, 128, 90, n=3.4, rot=-0.10)],
        outline=(228, 238, 249, 255), width=5)
    img.alpha_composite(pil)
    # 枕头高光 (必须画在独立图层再合成: PIL 的 ImageDraw RGBA 填充是覆盖不是混合)
    phl = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(phl).polygon(
        [(int(x), int(y)) for (x, y) in superellipse(110, 456, 106, 66, n=3.0, rot=-0.10)],
        fill=(255, 255, 255, 190))
    phl = phl.filter(ImageFilter.GaussianBlur(16))
    img.alpha_composite(phl)
    # 枕头陷进床垫的阴影
    psh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(psh).polygon(
        [(int(x), int(y)) for (x, y) in superellipse(138, 526, 162, 108, n=3.4, rot=-0.10)],
        fill=(112, 134, 164, 165))
    psh = psh.filter(ImageFilter.GaussianBlur(20))
    img.alpha_composite(psh)

    # ---------- 床头板在枕头后面的接触阴影 (把它"贴"在床头) ----------
    hsh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hsh).rectangle([70, 240, 210, 700], fill=(104, 124, 150, 80))
    hsh = hsh.filter(ImageFilter.GaussianBlur(20))
    img.alpha_composite(hsh)

    # ---------- 落影 (在可见带内给床一点接地感) ----------
    gsh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(gsh).rectangle([0, 680, 1024, 818], fill=(52, 66, 86, 60))
    gsh = gsh.filter(ImageFilter.GaussianBlur(16))
    out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    out.alpha_composite(gsh)
    out.alpha_composite(img)
    out = B.clip_bottom(out, 818)
    # R167: 床原本铺满整张纹理 (x0..1024) ⇒ 在 200x240 上左右各溢出 ~0.5px
    # (生产布局算法判 "道具越界")。整体横向缩到 1000 并右移 8px, 上下不动
    # (地面行 818 不变), 这样左右都在画布内。
    out = out.resize((1000, 1024), Image.LANCZOS)
    fixed = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    fixed.alpha_composite(out, (8, 0))
    return fixed


# ======================================================================
def main():
    os.makedirs(OUT, exist_ok=True)

    quilt = make_quilt()
    qp = os.path.join(OUT, 'prop_quilt.png')
    quilt.save(qp)
    print(f'  ✅ prop_quilt.png  bbox={quilt.getbbox()}')

    bed = make_bed()
    bp = os.path.join(OUT, 'prop_bed.png')
    bed.save(bp)
    print(f'  ✅ prop_bed.png    bbox={bed.getbbox()}  floor=818')

    a = np.asarray(quilt)[:, :, 3]
    print(f'     quilt 不透明像素占比 = {100 * (a > 200).mean():.1f}%')
    print(f'     quilt 左边界 x<405 处 alpha 最大值 = {a[:, :405].max()}  (必须为 0)')

    # R167: 同步 props_report.json 里这两个道具的 bbox (30 写的还是 R165 旧值)
    rp = os.path.join(OUT, 'props_report.json')
    if os.path.exists(rp):
        try:
            with open(rp, encoding='utf-8') as f:
                rep = json.load(f)
            props = rep.setdefault('props', {})
            for name, floor, img in (('prop_quilt.png', None, quilt),
                                     ('prop_bed.png', 818, bed)):
                bb = img.getbbox()
                props[name] = {'bbox': list(bb) if bb else None,
                               'floor_tex_y': floor}
            rep['round'] = 'R167'
            with open(rp, 'w', encoding='utf-8') as f:
                json.dump(rep, f, ensure_ascii=False, indent=2)
            print(f'  📄 {rp}  (已同步 prop_quilt / prop_bed 的 bbox)')
        except Exception as e:
            print(f'  ⚠️  props_report 同步失败: {e}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
