#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R156 场景道具烘焙器 (v3 · R165 场景重做) — 程序化绘制"小场景"道具 (不依赖任何外部素材/AI 生图)。

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

v2 的三个真问题 (已在 v2 修掉, v3 保留其语义):
  1) 落影用**显式边界的地面椭圆**, 不会把道具的 alpha bbox 向外撑破;
  2) `clip_bottom(img, floor)` 语义保留 —— 道具 bbox 底边**精确等于**地面行;
  3) 转椅底盘压暗, 整体放 back 层。

v3 (R165 轮次) 的改动 —— 只针对用户真机反馈的两处场景:
  · P0-3 睡眠场景: 被子原来是一块"摆在旁边"的硬多边形 (左边界 x=470, 硬网格直线),
    读作"床边放了一床被子"。v3 重做为**真正盖在身上**的被子:
      - 上沿沿角色身体轮廓起伏 (胸口凹 → 臀/腰凸 → 大腿斜落 → 小腿平直),
      - 下沿垂到床垫前沿 (y≈740), 左边界收到 x≈426 (不遮脸/不切手),
      - 材质: 竖向柔和渐变 + 3~5 条羽化弧形褶皱 + 上沿 15px 翻折亮边,
      - alpha 边缘干净 (mask + 1.6px 羽化), 不糊成大团。
  · P0-2 办公场景: 原来把笔记本画成**正对观众的大看板** (梯形板 + 文字行),
    角色站在"广告牌"后面。v3 改成**屏幕朝向角色**:
      - 观众看到的是笔记本**背板** (石墨色圆角梯形, 上窄下宽 = 盖板朝角色后仰),
      - 上沿 + 左沿一道很细的冷蓝边缘光 (屏幕亮着, 光从缝里漏出来),
      - 盖板下沿是铰链 + 基座 (键盘面) 的一小块水平面, 键帽行若隐若现,
      - 桌面: 后沿 y=640 (人物坐在桌后, 双手搭在桌面), 前沿 y=716, 桌裙落地,
      - 屏幕微光重做成**从笔记本屏幕边缘溢出**的冷光, 落在胸口/下巴/手上,
        范围小、柔和, 不糊成一团, 不遮五官。
  · 床与月亮同步做柔化: 床垫分"顶面/侧面"两层, 床品与被子同色系, 月亮亮度略降。

坐标系实测值 (直接用, 来自 assets/character_R153/sleep_breath_in.png 与
assets/character_R156/work_1.png 的 alpha 逐列测量):
  睡眠 (floor_tex_y=818): 头/发 x 49~390 y 330~490; 身体 x 390~976 y 440~690;
                          逐列身体上沿见 QUILT_TOP_EDGE 常量。
  办公 (floor_tex_y=1001): 角色 bbox (339,41)-(772,1001); 头/脸 x 470~660 y 41~300;
                          双手当前垂在身前 (x 340~540 / y 555~645) —— 本脚本**不改角色帧**,
                          只按 DESK_FAR_EDGE 等常量给出桌面对齐坐标 (见 props_report.json)。
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

# ---------- v3 新增调色板 (只被新写的函数使用, 不影响 sofa/chair) ----------
# 床 (v3): 木架压成暖灰木, 床品与被子同色系 (冷蓝), 整体更柔和
BED_WOOD = (214, 198, 176, 255)
BED_WOOD_D = (184, 166, 144, 255)
BED_SHEET = (206, 222, 240, 255)
BED_SHEET_D = (178, 198, 222, 255)
# 被子 (v3): 折口亮边 / 底色 / 深处 / 褶皱线
QUILT_FOLD = (219, 235, 251, 255)   # 翻折亮边 (折口)
QUILT_BODY = (198, 219, 241, 255)   # 主体底色
QUILT_DEEP = (166, 194, 223, 255)   # 深处/背光面
QUILT_LINE = (172, 198, 226, 255)   # 褶皱线 (接近底色)
# 笔记本 (v3): 石墨背板 + 冷蓝边缘光
LID = (56, 68, 87, 255)
LID_D = (40, 50, 66, 255)
LID_EDGE = (146, 200, 250, 255)     # 屏幕漏出的冷蓝边缘光
LID_LOGO = (92, 106, 128, 255)
BASE_METAL = (132, 144, 162, 255)   # 笔记本基座 (键盘面)
BASE_METAL_D = (102, 114, 132, 255)


# ======================================================================
# 通用工具
# ======================================================================
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


def soft_mask(pts, blur=1.6):
    """多边形 → 抗锯齿 mask (轻微羽化, 不糊成大团)。"""
    m = Image.new('L', (S, S), 0)
    ImageDraw.Draw(m).polygon([(int(x), int(y)) for (x, y) in pts], fill=255)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    return m


def rounded_quad_mask(quad, radius, ss=2):
    """梯形 + 圆角 → mask (2 倍超采样抗锯齿)。"""
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    big = Image.new('L', (S * ss, S * ss), 0)
    ImageDraw.Draw(big).polygon([(x * ss, y * ss) for (x, y) in quad], fill=255)
    rr = Image.new('L', (S * ss, S * ss), 0)
    ImageDraw.Draw(rr).rounded_rectangle(
        [min(xs) * ss, min(ys) * ss, max(xs) * ss, max(ys) * ss],
        radius=radius * ss, fill=255)
    m = Image.fromarray(np.minimum(np.asarray(big), np.asarray(rr)))
    return m.resize((S, S), Image.LANCZOS)


def diag_gradient(c_hi, c_lo, x0, x1, y0, y1, w_y=0.62, w_x=0.38, alpha=255):
    """对角柔和渐变: t=0 → c_hi (右上, 受月光侧), t=1 → c_lo (左下深处)。"""
    yy, xx = np.mgrid[0:S, 0:S]
    tx = np.clip((xx - x0) / max(1.0, float(x1 - x0)), 0.0, 1.0)
    ty = np.clip((yy - y0) / max(1.0, float(y1 - y0)), 0.0, 1.0)
    t = (w_y * ty + w_x * (1.0 - tx))[:, :, None]
    hi = np.array(c_hi[:3], dtype=np.float32)[None, None, :]
    lo = np.array(c_lo[:3], dtype=np.float32)[None, None, :]
    rgb = hi * (1.0 - t) + lo * t
    out = np.dstack([rgb, np.full((S, S), float(alpha), dtype=np.float32)])
    return Image.fromarray(out.astype(np.uint8), 'RGBA')


def vertical_gradient(c_top, c_bot, y0, y1, alpha=255):
    """竖向渐变。"""
    yy, xx = np.mgrid[0:S, 0:S]
    t = np.clip((yy - y0) / max(1.0, float(y1 - y0)), 0.0, 1.0)[:, :, None]
    top = np.array(c_top[:3], dtype=np.float32)[None, None, :]
    bot = np.array(c_bot[:3], dtype=np.float32)[None, None, :]
    rgb = top * (1.0 - t) + bot * t
    out = np.dstack([rgb, np.full((S, S), float(alpha), dtype=np.float32)])
    return Image.fromarray(out.astype(np.uint8), 'RGBA')


def bez(p0, p1, p2, n=48):
    """二次贝塞尔折线 (画弧形褶皱用)。"""
    pts = []
    for i in range(n + 1):
        t = i / float(n)
        u = 1.0 - t
        pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return pts


# ======================================================================
# 1. 小床 (躺姿用; 场景地面纹理 y = 818)
#    v3: 床垫分"顶面/侧面"两层 + 床品与被子同色系; 右端延伸到 x=996,
#        让角色的脚 (x=976) 不再悬在床外; bbox 底边仍由 clip_bottom(818) 决定。
# ======================================================================
def make_bed():
    img = canvas()
    d = ImageDraw.Draw(img)

    # 床腿 (4 条, 略微外撇, 颜色比 v2 柔和)
    for x0 in (104, 330, 700, 906):
        d.rounded_rectangle([x0, 744, x0 + 44, 806], radius=16,
                            fill=BED_WOOD, outline=BED_WOOD_D, width=4)
    # 底部横梁
    d.rounded_rectangle([94, 770, 944, 806], radius=14,
                        fill=BED_WOOD, outline=BED_WOOD_D, width=4)

    # 床头板 (在角色头后面, 只从左侧露出)
    d.rounded_rectangle([42, 424, 104, 748], radius=24,
                        fill=BED_WOOD, outline=BED_WOOD_D, width=4)
    d.rounded_rectangle([52, 442, 86, 730], radius=16,
                        fill=(226, 212, 192, 255), outline=None)

    # 床垫: 侧面 (下层) + 顶面 (上层) —— 两层分开, 层次清楚
    d.rounded_rectangle([42, 664, 996, 752], radius=30,
                        fill=MATTRESS_D, outline=None)
    d.rounded_rectangle([50, 628, 990, 706], radius=28,
                        fill=MATTRESS, outline=None)
    # 顶面/侧面之间的分界: 一条柔和的阴影线
    edge = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(edge).line([(66, 700), (972, 700)], fill=(150, 172, 196, 190), width=7)
    edge = edge.filter(ImageFilter.GaussianBlur(3))
    img.alpha_composite(edge)
    # 顶面高光 (月光从右上打下来)
    hi = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hi).rounded_rectangle([58, 632, 984, 656], radius=12,
                                         fill=(255, 255, 255, 120), outline=None)
    hi = hi.filter(ImageFilter.GaussianBlur(7))
    img.alpha_composite(hi)

    # 床品 (被面底子): 与被子同色系的浅蓝, 铺在床垫顶面上
    sheet = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheet)
    sd.polygon([(48, 634), (990, 634), (990, 682), (760, 676),
                (520, 684), (280, 674), (48, 680)], fill=BED_SHEET)
    sheet = sheet.filter(ImageFilter.GaussianBlur(3))
    sheet.putalpha(Image.composite(sheet.split()[3], Image.new('L', (S, S), 0),
                                   sheet.split()[3]))
    img.alpha_composite(sheet)
    d = ImageDraw.Draw(img)
    # 床品下缘的一道柔和折边
    d.line([(60, 678), (300, 672), (520, 682), (760, 674), (986, 680)],
           fill=BED_SHEET_D, width=4)

    # 枕头 (承托头部: 头在纹理 x 49~390 / y 330~490)
    d.ellipse([38, 424, 374, 604], fill=PILLOW, outline=PILLOW_D, width=5)
    # 枕头高光 —— 必须画在独立图层再合成: PIL 的 ImageDraw 用 RGBA 填充是
    # **直接覆盖像素**而不是做 alpha 混合, 直接画在 img 上会把枕头打成半透明窟窿。
    phl = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(phl).ellipse([70, 448, 340, 572], fill=(255, 255, 255, 170))
    phl = phl.filter(ImageFilter.GaussianBlur(6))
    img.alpha_composite(phl)
    # 枕头下方的柔和阴影 (让枕头"陷"进床垫)
    psh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(psh).ellipse([52, 540, 366, 618], fill=(150, 170, 194, 110))
    psh = psh.filter(ImageFilter.GaussianBlur(14))
    img.alpha_composite(psh)

    img = ground_shadow(img, 92, 950, 788, 818, alpha=60, blur=8)
    return clip_bottom(img, 818)


# ======================================================================
# 2. 被子 (front 层; 真正盖在身上)
#    v3 关键改动:
#      · 上沿沿角色身体轮廓起伏 (不是一条直线/直角多边形),
#      · 左边界 x≈426 (不遮脸、不切手),
#      · 下沿垂到 y≈740, 搭在床垫前沿上,
#      · 材质: 对角柔和渐变 + 羽化弧形褶皱 + 15px 翻折亮边, alpha 边缘干净。
#    上沿采样自 assets/character_R153/sleep_breath_in.png 的 alpha 逐列测量
#    (身体上沿减去 6px, 让被子边缘刚好盖住身体轮廓线)。
# ======================================================================
QUILT_TOP_EDGE = [
    (438, 434), (452, 440), (468, 446), (486, 452), (506, 457), (526, 457),
    (546, 450), (566, 439), (586, 432), (606, 425), (626, 420), (646, 419),
    (664, 429), (680, 449), (696, 469), (712, 496), (728, 518), (748, 531),
    (772, 527), (796, 526), (820, 522), (844, 525), (868, 529), (892, 526),
    (916, 532), (938, 543), (956, 562), (968, 586),
]
QUILT_BOTTOM_EDGE = [
    (980, 700), (978, 728), (940, 738), (880, 742), (800, 741), (720, 737),
    (640, 733), (560, 729), (486, 725), (440, 718),
]
QUILT_LEFT_EDGE = [
    (440, 718), (424, 700), (414, 640), (412, 570), (420, 500), (438, 434),
]


def make_quilt():
    # 轮廓: 上沿 (左→右) + 右侧 + 下沿 (右→左) + 左侧 (下→上)
    outline = (QUILT_TOP_EDGE
               + [(978, 606), (982, 646), (980, 700)]
               + QUILT_BOTTOM_EDGE[1:]
               + QUILT_LEFT_EDGE[1:])
    mask = soft_mask(outline, blur=1.6)

    # 底色: 右上有月光 → 略亮; 左下深处 → 略暗
    base = diag_gradient(QUILT_BODY, QUILT_DEEP, x0=420, x1=980, y0=430, y1=742)
    base.putalpha(mask)

    # 弧形褶皱 (颜色接近底色, 边缘羽化) —— 4 条长褶 + 3 条短褶,
    # 刻意做得"若隐若现": 太强会在 200px 窗口里变成"罗纹/波浪"条纹。
    folds = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    fd = ImageDraw.Draw(folds)
    long_curves = [
        bez((470, 458), (446, 584), (470, 718)),
        bez((596, 430), (574, 578), (606, 730)),
        bez((742, 528), (718, 622), (756, 736)),
        bez((884, 528), (862, 626), (894, 740)),
    ]
    short_curves = [
        bez((520, 476), (506, 546), (524, 620)),
        bez((668, 470), (652, 552), (674, 640)),
        bez((828, 528), (812, 588), (832, 652)),
    ]
    for c in long_curves:
        fd.line([(int(x), int(y)) for (x, y) in c], fill=QUILT_LINE[:3] + (64,), width=8)
    for c in short_curves:
        fd.line([(int(x), int(y)) for (x, y) in c], fill=QUILT_LINE[:3] + (44,), width=7)
    folds = folds.filter(ImageFilter.GaussianBlur(13))
    folds.putalpha(Image.composite(folds.split()[3], Image.new('L', (S, S), 0), mask))
    base.alpha_composite(folds)

    # 形体内阴影 —— 让被子读成"盖在身上的布", 而不是一块波浪形色块:
    #  · 臀→腿转折处的深谷 (斜向柔影)
    #  · 胸口下方的一道浅谷
    #  · 左侧近侧垂下的一条柔影
    form = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    fdr = ImageDraw.Draw(form)
    fdr.line([(int(x), int(y)) for (x, y) in bez((682, 446), (706, 518), (748, 604))],
             fill=(120, 150, 186, 205), width=58)
    fdr.line([(int(x), int(y)) for (x, y) in bez((520, 470), (508, 540), (516, 610))],
             fill=(128, 157, 190, 155), width=40)
    fdr.line([(int(x), int(y)) for (x, y) in bez((432, 460), (424, 560), (438, 690))],
             fill=(126, 155, 188, 145), width=38)
    form = form.filter(ImageFilter.GaussianBlur(24))
    form.putalpha(Image.composite(form.split()[3], Image.new('L', (S, S), 0), mask))
    base.alpha_composite(form)

    # 受月光的高光: 臀部最高处受光最亮 (一条贴着上沿的柔光带)
    crest = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(crest).line(
        [(int(x), int(y)) for (x, y) in bez((556, 458), (618, 440), (682, 452))],
        fill=(236, 245, 255, 150), width=34)
    crest = crest.filter(ImageFilter.GaussianBlur(20))
    crest.putalpha(Image.composite(crest.split()[3], Image.new('L', (S, S), 0), mask))
    base.alpha_composite(crest)

    # 翻折亮边 (上沿往下 17px 的一条亮带 = 被子的折口/床单翻边)
    band_pts = (QUILT_TOP_EDGE
                + [(x, y + 17) for (x, y) in reversed(QUILT_TOP_EDGE)])
    band = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(band).polygon([(int(x), int(y)) for (x, y) in band_pts],
                                 fill=QUILT_FOLD[:3] + (225,))
    band = band.filter(ImageFilter.GaussianBlur(4.0))
    band.putalpha(Image.composite(band.split()[3], Image.new('L', (S, S), 0), mask))
    base.alpha_composite(band)

    # 折口翻回去的那一道细暗线 (让折边有厚度)
    edge_line = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(edge_line).line(
        [(int(x), int(y) + 17) for (x, y) in QUILT_TOP_EDGE],
        fill=(150, 176, 206, 150), width=4)
    edge_line = edge_line.filter(ImageFilter.GaussianBlur(2.0))
    edge_line.putalpha(Image.composite(edge_line.split()[3], Image.new('L', (S, S), 0), mask))
    base.alpha_composite(edge_line)

    # 折口下方的柔和阴影 (让被子有厚度)
    sh_pts = ([(x, y + 15) for (x, y) in QUILT_TOP_EDGE]
              + [(x, y + 44) for (x, y) in reversed(QUILT_TOP_EDGE)])
    sh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon([(int(x), int(y)) for (x, y) in sh_pts],
                               fill=(120, 148, 182, 95))
    sh = sh.filter(ImageFilter.GaussianBlur(13))
    sh.putalpha(Image.composite(sh.split()[3], Image.new('L', (S, S), 0), mask))
    base.alpha_composite(sh)

    # ---------- 左侧翻折亮边 (R165) ----------
    # 左侧边紧贴角色面部/枕头, v3 那里是一条**竖直硬边** ⇒ 读起来像"旁边立了一块板"。
    # 加一道 13px 的翻折亮带 + 一道内侧细暗线, 让它读成"毯子翻过来的边"。
    left_band_pts = (QUILT_LEFT_EDGE
                     + [(x + 13, y) for (x, y) in reversed(QUILT_LEFT_EDGE)])
    lb = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(lb).polygon([(int(x), int(y)) for (x, y) in left_band_pts],
                               fill=QUILT_FOLD[:3] + (200,))
    lb = lb.filter(ImageFilter.GaussianBlur(4.5))
    lb.putalpha(Image.composite(lb.split()[3], Image.new('L', (S, S), 0), mask))
    base.alpha_composite(lb)
    # 翻折带内侧的细暗线 (给厚度)
    lline = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(lline).line(
        [(int(x + 13), int(y)) for (x, y) in QUILT_LEFT_EDGE],
        fill=(150, 176, 206, 130), width=4)
    lline = lline.filter(ImageFilter.GaussianBlur(2.4))
    lline.putalpha(Image.composite(lline.split()[3], Image.new('L', (S, S), 0), mask))
    base.alpha_composite(lline)
    # 最外沿再柔化 6px (消掉"硬切"感) —— 横向渐变淡出:
    # 左边缘 x=405 处 alpha→0, x=452 处 alpha→1, 让毯子的左边融进暗处,
    # 而不是一条贴着面部的竖直切口。
    ramp = np.clip((np.arange(S)[None, :] - 405.0) / 47.0, 0.0, 1.0).astype(np.float32)
    ramp = np.repeat(ramp, S, axis=0)
    a_new = np.asarray(base.split()[3]).astype(np.float32) * ramp
    base.putalpha(Image.fromarray(a_new.astype(np.uint8), 'L'))

    # 下摆一条更深的收边 (被子垂到床垫前沿的厚度感)
    hem = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hem).line([(int(x), int(y)) for (x, y) in QUILT_BOTTOM_EDGE],
                              fill=QUILT_DEEP[:3] + (170,), width=8)
    hem = hem.filter(ImageFilter.GaussianBlur(4))
    hem.putalpha(Image.composite(hem.split()[3], Image.new('L', (S, S), 0), mask))
    base.alpha_composite(hem)

    # 被子下摆落在床垫上的接触阴影 (画在被子轮廓之外, 落在床垫上) ——
    # 让被子"压"在床垫上, 而不是和床垫糊成一片。
    contact = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(contact).line(
        [(int(x), int(y) + 7) for (x, y) in QUILT_BOTTOM_EDGE],
        fill=(128, 150, 178, 120), width=11)
    contact = contact.filter(ImageFilter.GaussianBlur(9))
    out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    out.alpha_composite(contact)
    out.alpha_composite(base)
    return out


# ======================================================================
# 3. 月亮 + 星星 (back 层; 夜空氛围, 画布上部)
#    v3: 亮度/饱和略降, 月晕更大更淡, 尺寸不变。
# ======================================================================
def make_moon():
    img = canvas()
    m = Image.new('L', (S, S), 0)
    md = ImageDraw.Draw(m)
    md.ellipse([700, 56, 838, 194], fill=255)
    md.ellipse([740, 26, 878, 164], fill=0)
    moon = Image.new('RGBA', (S, S), MOON)
    moon.putalpha(m)
    img.alpha_composite(moon)
    # 月晕 (范围稍大但更淡, 不做大块背景)
    glow = Image.new('RGBA', (S, S), (253, 240, 190, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([652, 10, 892, 244], fill=(250, 238, 198, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(42))
    img.alpha_composite(glow)
    # 小星星 (限制在 x 70~900, 避免出画布; 亮度略降)
    # 同样注意: ImageDraw 的 RGBA 填充是覆盖而不是混合 ⇒ 星星画在独立图层上合成。
    stars = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    for (cx, cy, r) in ((150, 92, 12), (286, 46, 8), (430, 120, 10), (576, 62, 7),
                        (662, 176, 9), (236, 206, 8), (498, 232, 7), (872, 262, 8),
                        (96, 268, 7), (372, 300, 6), (830, 128, 6)):
        ImageDraw.Draw(stars).ellipse([cx - r, cy - r, cx + r, cy + r],
                                      fill=(236, 232, 212, 220))
    stars = stars.filter(ImageFilter.GaussianBlur(1.2))
    img.alpha_composite(stars)
    return img


# ======================================================================
# 4. 小沙发 (坐姿用; 场景地面纹理 y = 1001)
#    v3 **不改造型** (本轮不在范围内)。
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
# 5.办公转椅 (坐姿用; back 层, 在角色身后)
#    v3 **不改造型** (本轮不在范围内)。
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
# 6. 办公桌 + 笔记本电脑  (R165 v4: 拆成 back 层台面 + front 层前沿/桌腿)
#
#    【v3 的方向是对的, 但层序错了 —— R165 才定位到真正的病根】
#      v3 把整张桌子放在 **front 层** (角色身前), 于是:
#        · 角色 sprite 里的双手 (SIT 实测 y567~641) **完全落在桌板上方**,
#          一根手指都碰不到桌面 ⇒ 用户看到的是"双手搭在腿上", 不是"手在键盘上";
#        · 桌板 (y640~716) 横在角色**大腿根部**, 读作"站在柜台后面"。
#      根因: **桌子是一张横板, 正面视角下它一半在角色身前、一半在角色身后**。
#      角色坐在桌后 ⇒ 桌板的**远端部分被角色身体挡住** (⇒ back 层),
#      桌板的**近端部分 (前沿 + 桌腿) 在角色身前** (⇒ front 层)。
#      v4 据此把桌子拆成两个道具:
#        prop_desk_surface (back 层) : 台面 + 双手接触阴影
#        prop_desk         (front 层): 前沿厚边 + 桌腿 + 笔记本电脑 + 落影
#          (笔记本在 front 层: 它立在桌上、在角色身前, 下缘会挡住角色裙摆 —— 物理正确)
#      于是角色 sprite 的双手**完整地压在台面上** ⇒ 一眼读得出"手在桌上打字"。
#
#    屏幕方向 (v3 起的核心方向, v4 保持):
#      **屏幕朝角色, 不朝观众** —— 观众看到的是笔记本的**背板**。
#        · 背板 = 石墨色圆角梯形 (上窄下宽 = 盖板朝角色后仰的透视),
#        · 上沿 + 左沿一道很细的冷蓝边缘光 (屏幕亮着, 光从盖板边缘漏出来),
#        · 盖板下沿 = 铰链 + 基座 (键盘面) 的一小块水平面, 键帽行若隐若现,
#        · 板面中央一个低调的圆形徽记 + 下缘一道散热格栅。
#
#    坐标约定 (1024 纹理; 角色帧实测见下):
#      DESK_FAR_EDGE_Y  = 556   台面远沿 (角色身后, 被角色身体遮住)
#      DESK_NEAR_EDGE_Y = 668   台面近沿 (角色身前)
#      DESK_TOP_X       = 270..900
#      LID_QUAD         = x 714..876, y 466..636   盖板背板 (在角色右侧)
#      LID_BASE_QUAD    = x 704..884, y 636..660   键盘面
#      双手 (SIT 实测): 左手 x348..425 y567..638 / 右手 x439..535 y571..641
#        ⇒ 两手完整落在台面带 (556..668) 内 ✔
# ======================================================================
DESK_FAR_EDGE_Y = 556
DESK_NEAR_EDGE_Y = 668
DESK_TOP_X = (300, 830)
DESK_SURFACE_X = (310, 820)
LID_QUAD = [(656, 466), (796, 466), (804, 636), (648, 636)]   # 盖板背板 (上窄下宽)
LID_BASE_QUAD = [(648, 636), (804, 636), (812, 660), (640, 660)]  # 基座/键盘面
DESK_LEG_X = ((318, 382), (744, 808))
DESK_LIP_Y = (668, 698)


def make_desk_surface():
    """back 层: 桌面台面 (角色坐在桌后 ⇒ 台面的远端部分在角色身后)。"""
    img = canvas()
    d = ImageDraw.Draw(img)

    # ---------- 台面 (近沿更宽 = 透视) ----------
    top_quad = [(DESK_SURFACE_X[0], DESK_FAR_EDGE_Y),
                (DESK_SURFACE_X[1], DESK_FAR_EDGE_Y),
                (DESK_TOP_X[1], DESK_NEAR_EDGE_Y),
                (DESK_TOP_X[0], DESK_NEAR_EDGE_Y)]
    d.polygon(top_quad, fill=WOOD)
    # 台面远沿的一道暗线 (桌面与身后空间的交界)
    d.line([(DESK_SURFACE_X[0], DESK_FAR_EDGE_Y), (DESK_SURFACE_X[1], DESK_FAR_EDGE_Y)],
           fill=(184, 160, 130, 255), width=4)
    # 台面上的一条柔和高光 (冷光从右上斜下来)
    hl = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hl).polygon(
        [(DESK_SURFACE_X[0], DESK_FAR_EDGE_Y), (DESK_SURFACE_X[1], DESK_FAR_EDGE_Y),
         (DESK_TOP_X[1], DESK_FAR_EDGE_Y + 34), (DESK_TOP_X[0], DESK_FAR_EDGE_Y + 34)],
        fill=(255, 250, 238, 66))
    hl = hl.filter(ImageFilter.GaussianBlur(13))
    img.alpha_composite(hl)

    # ---------- 双手在台面上的接触阴影 ----------
    # 角色双手 (SIT 实测 左手 x348..425 / 右手 x439..535, y567..641) 落在台面上,
    # 影子落在手的前下方一小块 ⇒ 读作"手压着桌面"而不是"手浮在桌面上方"。
    hs = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hs)
    hd.ellipse([344, 572, 432, 612], fill=(96, 78, 58, 120))
    hd.ellipse([436, 576, 542, 618], fill=(96, 78, 58, 118))
    hs = hs.filter(ImageFilter.GaussianBlur(11))
    img.alpha_composite(hs)

    return img


def make_desk():
    """front 层: 桌板前沿厚边 + 两条桌腿 (角色身前)。

    桌下留空 ⇒ 角色的靴子从桌下露出来 ⇒ 一眼看出"她是坐着", 不是站在柜台后。
    """
    img = canvas()
    d = ImageDraw.Draw(img)

    # ---------- 桌腿 ----------
    for (x0, x1) in DESK_LEG_X:
        d.polygon([(x0, DESK_LIP_Y[1] - 6), (x1, DESK_LIP_Y[1] - 6),
                   (x1 - 8, 1001), (x0 + 8, 1001)], fill=WOOD_D)
        d.line([(x0 + 3, DESK_LIP_Y[1] - 6), (x0 + 11, 1001)], fill=WOOD, width=7)
    # 桌腿落地处的一点落影
    legsh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    lsd = ImageDraw.Draw(legsh)
    for (x0, x1) in DESK_LEG_X:
        lsd.ellipse([x0 - 8, 962, x1 + 14, 1002], fill=(70, 58, 46, 90))
    legsh = legsh.filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(legsh)

    # ---------- 笔记本电脑 (front 层: 它在桌上、在角色身前, 会遮住角色的裙摆 —— 物理正确) ----------
    d.polygon(LID_BASE_QUAD, fill=BASE_METAL)
    d.line([(LID_BASE_QUAD[0][0], LID_BASE_QUAD[0][1]), (LID_BASE_QUAD[1][0], LID_BASE_QUAD[1][1])],
           fill=BASE_METAL_D, width=4)
    d.line([(LID_BASE_QUAD[3][0], LID_BASE_QUAD[3][1]), (LID_BASE_QUAD[2][0], LID_BASE_QUAD[2][1])],
           fill=BASE_METAL_D, width=5)
    # 键帽行 (很淡, 不抢戏) —— 画在独立图层再合成, 否则半透明填充会在
    # 基座上打出"洞", 角色的手/衣服会从基座里透出来。
    keys = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    kd = ImageDraw.Draw(keys)
    for i, yy in enumerate((645, 652)):
        x0 = 730 + i * 6
        x1 = 866 - i * 6
        kd.line([(x0, yy), (x1, yy)], fill=(120, 132, 152, 70), width=3)
    keys = keys.filter(ImageFilter.GaussianBlur(1.4))
    img.alpha_composite(keys)

    # ---------- 笔记本电脑: 盖板背板 ----------
    lid_m = rounded_quad_mask(LID_QUAD, radius=12)
    lid = vertical_gradient(LID, LID_D, y0=466, y1=636)
    lid.putalpha(lid_m)
    # 板面中间的低调徽记
    mk = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(mk).ellipse([778, 534, 818, 574], fill=LID_LOGO[:3] + (150,))
    mk = mk.filter(ImageFilter.GaussianBlur(2))
    mk.putalpha(Image.composite(mk.split()[3], Image.new('L', (S, S), 0), lid_m))
    lid.alpha_composite(mk)
    # 下缘散热格栅
    gr = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(gr)
    for yy in (598, 606, 614):
        gd2.line([(742, yy), (852, yy)], fill=(30, 38, 50, 150), width=4)
    gr = gr.filter(ImageFilter.GaussianBlur(2.2))
    gr.putalpha(Image.composite(gr.split()[3], Image.new('L', (S, S), 0), lid_m))
    lid.alpha_composite(gr)
    img.alpha_composite(lid)

    # ---------- 屏幕漏出的冷蓝边缘光 (上沿 + 左沿) ----------
    rim = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim)
    rd.line([(LID_QUAD[0][0] + 3, LID_QUAD[0][1] + 3), (LID_QUAD[1][0] - 3, LID_QUAD[1][1] + 3)],
            fill=LID_EDGE[:3] + (235,), width=5)
    rd.line([(LID_QUAD[3][0] + 3, LID_QUAD[3][1] - 4), (LID_QUAD[0][0] + 3, LID_QUAD[0][1] + 4)],
            fill=LID_EDGE[:3] + (205,), width=5)
    rim = rim.filter(ImageFilter.GaussianBlur(1.6))
    rim.putalpha(Image.composite(rim.split()[3], Image.new('L', (S, S), 0), lid_m))
    img.alpha_composite(rim)
    # 边缘光外溢的一点点辉光 (很小, 不喧宾夺主)
    halo = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    hd2 = ImageDraw.Draw(halo)
    hd2.line([(LID_QUAD[0][0] + 3, LID_QUAD[0][1] + 3), (LID_QUAD[1][0] - 3, LID_QUAD[1][1] + 3)],
             fill=(130, 190, 250, 110), width=12)
    hd2.line([(LID_QUAD[3][0] + 3, LID_QUAD[3][1] - 4), (LID_QUAD[0][0] + 3, LID_QUAD[0][1] + 4)],
             fill=(130, 190, 250, 95), width=11)
    halo = halo.filter(ImageFilter.GaussianBlur(9))
    halo.putalpha(Image.composite(halo.split()[3], Image.new('L', (S, S), 0), lid_m))
    img.alpha_composite(halo)

    # ---------- 桌板前沿 (近沿的厚边, 横在角色身前) ----------
    d.polygon([(DESK_TOP_X[0], DESK_NEAR_EDGE_Y), (DESK_TOP_X[1], DESK_NEAR_EDGE_Y),
               (DESK_TOP_X[1] - 6, DESK_LIP_Y[0] + 12), (DESK_TOP_X[0] + 6, DESK_LIP_Y[0] + 12)],
              fill=WOOD)
    d.polygon([(DESK_TOP_X[0] + 6, DESK_LIP_Y[0] + 12), (DESK_TOP_X[1] - 6, DESK_LIP_Y[0] + 12),
               (DESK_TOP_X[1] - 10, DESK_LIP_Y[1]), (DESK_TOP_X[0] + 10, DESK_LIP_Y[1])],
              fill=WOOD_D)
    # 前沿上缘的一道亮线 (桌板的厚度高光)
    d.line([(DESK_TOP_X[0] + 6, DESK_LIP_Y[0] + 12), (DESK_TOP_X[1] - 6, DESK_LIP_Y[0] + 12)],
           fill=(255, 248, 234, 190), width=4)
    # 桌沿下方一圈柔和落影
    sh = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([DESK_TOP_X[0], DESK_LIP_Y[0] + 8,
                                  DESK_TOP_X[1], DESK_LIP_Y[0] + 34],
                                 fill=(96, 78, 58, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(12))
    img.alpha_composite(sh)

    return clip_bottom(img, 1001)




# ======================================================================
# 7. 屏幕微光 (front 层; 从笔记本屏幕边缘溢出的冷光)
#    v3: v2 是一团糊在角色下半身的大蓝斑 (bbox 328..793 / 379..774)。
#    v3 改成三块小而柔的冷光, 落在**胸口 / 下巴 / 双手**, 不遮五官。
# ======================================================================
def make_screen_glow():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    a = np.zeros((S, S, 4), dtype=np.float32)
    yy, xx = np.mgrid[0:S, 0:S]

    def blob(cx, cy, rx, ry, peak, power=1.7):
        r = np.sqrt(((xx - cx) / float(rx)) ** 2 + ((yy - cy) / float(ry)) ** 2)
        v = np.clip(1.0 - r, 0.0, 1.0) ** power
        a[:, :, 0] += 116 * v * peak
        a[:, :, 1] += 172 * v * peak
        a[:, :, 2] += 238 * v * peak
        a[:, :, 3] += 112 * v * peak

    blob(556, 448, 170, 200, 0.72)   # 胸口 (离屏幕最近)
    blob(566, 376, 126, 112, 0.58)   # 下颌/颈侧 (下移到脸部框下沿 y=305 之下,
                                        #   alpha>24 的可见范围不侵入脸部区域)
    blob(444, 590, 154, 76, 0.64)    # 桌面上的双手 (SIT 实测 y567..641)
    blob(700, 470, 120, 150, 0.50)   # 笔记本屏幕漏出的一团冷光
    np.clip(a, 0, 255, out=a)
    out = Image.fromarray(a.astype(np.uint8), 'RGBA')
    return out.filter(ImageFilter.GaussianBlur(15))


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
    print("R156 场景道具绘制 v3 (R165 场景重做):")
    for fn, name, floor in (
            (make_bed, 'prop_bed.png', 818),
            (make_quilt, 'prop_quilt.png', None),
            (make_moon, 'prop_moon.png', None),
            (make_sofa, 'prop_sofa.png', 1001),
            (make_chair, 'prop_chair.png', 1001),
            (make_desk_surface, 'prop_desk_surface.png', None),
            (make_desk, 'prop_desk.png', 1001),
            (make_screen_glow, 'prop_screen_glow.png', None)):
        save(fn(), name, floor, rep)
    path = os.path.join(OUT, 'props_report.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"  📄 {path}")

    # R165: 场景对齐坐标单独出一份 (props_report.json 的结构保持不变)
    guides = {
        'round': 'R165',
        'note': ('场景道具与角色帧对齐用的坐标 (纹理坐标系 1024x1024); '
                 '父 agent 做角色帧 IK 时按这里的数值摆位'),
        'sleep': {
            'floor_tex_y': 818,
            'character_frame': 'character_R153/sleep_breath_in.png',
            'quilt_top_edge': [list(p) for p in QUILT_TOP_EDGE],
            'quilt_bottom_edge': [list(p) for p in QUILT_BOTTOM_EDGE],
            'quilt_left_edge': [list(p) for p in QUILT_LEFT_EDGE],
            'quilt_bbox': [416, 415, 1007, 776],
            'note': ('被子上沿沿角色身体轮廓 (胸口 x=438 → 臀峰 x=628 → 小腿 x=820); '
                     '左边界 x≈420 不遮脸/不切手; 下沿垂到 y≈742, 搭在床垫前沿'),
        },
        'work': {
            'floor_tex_y': 1001,
            'character_frame': 'character_R156/work_1.png',
            'layering_note': ('桌子拆成两个道具: prop_desk_surface (back 层, 台面+笔记本) '
                              '+ prop_desk (front 层, 前沿厚边+桌腿) ⇒ 角色 sprite 的双手'
                              '完整压在台面上 (而不是悬在桌板上方)'),
            'desk_far_edge_y': DESK_FAR_EDGE_Y,
            'desk_near_edge_y': DESK_NEAR_EDGE_Y,
            'desk_top_x': list(DESK_TOP_X),
            'desk_lip_y': list(DESK_LIP_Y),
            'desk_leg_x': [list(x) for x in DESK_LEG_X],
            'laptop_lid_x': [LID_QUAD[3][0], LID_QUAD[1][0]],
            'laptop_lid_y': [LID_QUAD[0][1], LID_QUAD[2][1]],
            'laptop_base_x': [LID_BASE_QUAD[3][0], LID_BASE_QUAD[2][0]],
            'laptop_base_y': [LID_BASE_QUAD[0][1], LID_BASE_QUAD[3][1]],
            'hands_measured': {
                'left': [348, 567, 425, 638],
                'right': [439, 571, 535, 641],
                'source': 'assets/character_R138/sleep_enter/sleep_enter_01_sit.png (肤色连通块实测)',
            },
            'hands_target_x': [344, 542],
            'hands_target_y': [567, 641],
            'note': ('双手完整落在台面带 (556..668) 内 ⇒ 读作"手压在桌面上"; '
                     '笔记本盖板中心 x=795 在角色身体中心 x=530 的右侧, '
                     '角色视线需略向右; 盖板不遮脸 (脸 y38..310)'),
        },
    }
    gpath = os.path.join(OUT, 'prop_scene_guides.json')
    with open(gpath, 'w', encoding='utf-8') as f:
        json.dump(guides, f, ensure_ascii=False, indent=2)
    print(f"  📄 {gpath}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
