#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R170 生活场景 **EAT_FRUIT (吃水果)** —— 角色帧烘焙器。

背景
----
R165 的手臂 rig (36_R158_arm_rig.py) 的关节坐标是按**站立底图**
(character_R138/idle/idle_00_base.png) 硬编码的, 而吃水果要求角色**坐在小凳上**
⇒ 底图换成 character_R138/sleep_enter/sleep_enter_01_sit.png。
坐姿下手臂的解剖与站立完全不同 (手臂贴着身体、双手搭在膝盖上、
右手的手在画面中线偏右而不是身体外侧), 站立底图的 S/E/W 与接缝线表
在坐姿上会切错 (实测: 站立硬编码腕点 (654,556) 与坐姿真实腕点 (512,558)
相差 142 px), 所以本脚本**自己给坐姿标定了一套关节与接缝线**,
但**旋转 / 合成 / 插值全部复用 36_ 的已验证实现** (rotate_rgba 双线性预乘、
over 合成、compose 图层顺序), 不重写像素算法。

R165 的两条铁律
---------------
1. **两条手臂都必须参与** —— 不动的一侧也要走一遍"摘袖子 → 原位摆回"。
   本脚本对 R 侧同样执行 detach → pose(0,0,0) → re-attach, 并断言该区域
   与底图**逐像素一致** (实测 diff = 0 px), 所以既不会出现"空袖子",
   也不会像直接复用站立底图几何那样在胸口留下一条伪造的接缝线。
2. **摘掉手臂后要把衣身/大腿补回来** —— 36_ 的 restore_body 只回填**肩区**
   (半径 46 px), 手臂原本搭在**大腿**上的那一块会被抹成透明洞。
   本脚本实现了 **竖向克隆填充**:
   先用"去掉手臂后的本体做二值孔洞填充"求出**真实剪影**,
   只有落在剪影**内部**的洞才填 (落在剪影外的 = 本来就是背景, 应当透明),
   洞内像素沿**同列向下**扫描, 跳过所有属于手臂的像素, 取第一个
   "不透明且非手臂"的像素的 RGBA 复制过来 ⇒ 大腿洞取到青色裤腿,
   衣身洞取到白色大褂; 填完再沿剪影边界补 2 px 深色描边并做 1 px 羽化。

产出
----
assets/character_R156/eat_fruit_0.png … eat_fruit_4.png  (1024x1024 RGBA)
5 帧 = 伸手拿水果 / 举到嘴边 / 低头张嘴咬 / 轻微咀嚼 / 开心笑眼
"""
import importlib.util
import json
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')
R156 = os.path.join(ASSETS, 'character_R156')
OUT = R156


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_rig = _mod('r36', os.path.join(HERE, '36_R158_arm_rig.py'))
_r153 = _mod('r22', os.path.join(HERE, '22_R153_pose_bake.py'))

# --- 复用 36_ 的已验证像素算法 (不改那个文件) ---
rotate_rgba = _rig.rotate_rgba
over = _rig.over
compose = _rig.compose
dilate = _rig.dilate
skin_relaxed = _rig.skin_relaxed
teal = _rig.teal
lum = _rig.lum
disc = _rig.disc
components = _rig.components

# ---------------------------------------------------------------------------
# 坐姿几何 (全部实测, 依据见注释)
# ---------------------------------------------------------------------------
TEX = 1024
SIT = os.path.join(R138, 'sleep_enter', 'sleep_enter_01_sit.png')
DONOR = os.path.join(R138, 'idle', 'idle_05_blink_closed.png')

# 坐姿头部几何 (供 head_transform 用; R153 的默认值是站立底图的)
HEAD_CENTER = (516, 168)
HEAD_RADII = (148, 134)
NECK_PIVOT = (516, 268)
CHIN_Y = 300
_r153.HEAD_CENTER = HEAD_CENTER
_r153.HEAD_RADII = HEAD_RADII
_r153.NECK_PIVOT = NECK_PIVOT
_r153.CHIN_Y = CHIN_Y
_r153.FACE_TOP_Y = 150
# R153 的 head_weight() 里有"脖子正下方必须固定"的保护项, 半径写死 (95,62);
# 坐姿的嘴 (507,271) 离支点只有 25px ⇒ 权重被压到 0.20, 头怎么动嘴都不动。
# 这里把支点抬高、保护区收紧, "低头"才真的看得见。
# 脖子保护区: 放在**衣领上沿** (不是嘴的高度)。原来的保护区中心在 (516,268)
# = 嘴的高度, 权重场在嘴上只有 0.175 ⇒ "低头"完全看不出来; 而且嘴几乎不动、
# 下巴却跟着动 ⇒ 下半张脸被压扁。
# 保护区下移到衣领后: 嘴/下唇整块往下走 (权重≈1), 下巴走得多一点, 衣领几乎不动
# ⇒ 读起来就是"头往衣领里沉了一下"。
NECK_GUARD = (516, 345)
NECK_GUARD_SIG = (54.0, 30.0)


def _sit_head_weight(W, H, core=1.02, fade=1.75):
    yy, xx = np.mgrid[0:H, 0:W]
    e = np.sqrt(((xx - HEAD_CENTER[0]) / HEAD_RADII[0]) ** 2 +
                ((yy - HEAD_CENTER[1]) / HEAD_RADII[1]) ** 2)
    w = 1.0 - _r153.smoothstep(core, fade, e)
    neck = np.exp(-(((xx - NECK_GUARD[0]) / NECK_GUARD_SIG[0]) ** 2 +
                    ((yy - NECK_GUARD[1]) / NECK_GUARD_SIG[1]) ** 2))
    w = w * (1.0 - 0.85 * neck)
    return np.clip(w, 0.0, 1.0)


_r153.head_weight = _sit_head_weight

# --- 画面左臂 (角色的右手) = 拿水果的那条 ---
#   S 肩关节: 落在袖子内部 (实测袖子在 y390 处 x418~440)
#   E 肘:     袖子中段微弯处
#   W 腕:     青色腕带下缘 (实测腕带 x376~437 / y547~589)
L_S = (428, 390)
L_E = (405, 478)
L_W = (392, 545)
# --- 画面右臂 (角色的左手) ---
R_S = (610, 356)
R_E = (642, 470)
R_W = (514, 556)

# 画面左臂"袖子内缘 = 大褂外缘"逐行实测 (1024 纹理坐标)
#   y=366 时该暗线在 x=433, 随手臂下垂外张到 y=498 的 x=459,
#   袖口段 (y>=534) 收回到 x=455 左右。
L_SEAM = [
    (366, 433), (372, 434), (378, 436), (384, 438), (390, 440), (396, 442),
    (402, 445), (408, 445), (414, 444), (420, 443), (426, 443), (432, 442),
    (438, 443), (444, 443), (450, 444), (456, 446), (462, 447), (468, 449),
    (474, 451), (480, 453), (486, 455), (492, 457), (498, 459), (504, 460),
    (510, 459), (516, 458), (522, 459), (528, 459), (534, 457), (540, 457),
    (546, 455), (552, 453), (558, 444),
]
L_ARM_TOP = 366          # 袖子起始行 (以上是肩帽, 归肩关节球)
L_CUFF_TOP = 534         # 袖口起始行
L_HAND_TOP = 556         # 手部起始行
L_HAND_ZONE = (332, 552, 440, 646)     # 左手肤色搜索框
L_OUTER_LO, L_OUTER_HI = 300, 512       # 剪影外缘搜索窗

# 画面右臂 (只做原位摆回, 几何只需"合理")
R_ARM_TOP = 344
R_HAND_TOP = 556
R_INNER = [(344, 566), (392, 540), (444, 538), (500, 540), (540, 545), (560, 540)]
R_HAND_ZONE = (428, 552, 548, 650)

OUTLINE_RGB = (10, 14, 34)   # 底图描边色 (实测 x638,y460 处 rgb=9,14,34)
SHOULDER_BALL_R = 26
SHOULDER_FILL_R = 46
CUT_EDGE_PX = 2              # 被切开的边要补的描边宽度
ARM_TOP_L = 366              # 画面左臂的袖口起始行 (上臂段顶边)
HOLE_MAX_DIST = 46           # 竖向克隆填充的最大向下距离 (超过 = 那里本来就是背景)

# 嘴 / 鼻 (实测: 嘴的暗像素在 x485~530 / y267~277; 鼻子在 x493~496 / y249~253)
MOUTH_C = (507, 271)
# 脸颊肤色 (从坐姿底图实测: (447,269)~(477,283) 的中位肤色)
CHEEK_SKIN = (254, 227, 210)
MOUTH_HALF = (13, 7)

# 眼睛 (实测: 左眼 x436~482 / y194~238, 右眼 x518~572 / y192~240)
EYE_L_RECT = (432, 192, 490, 244)
EYE_R_RECT = (516, 192, 580, 244)
# donor (站立底图 idle_05_blink_closed) 里的闭眼区域
DONOR_L_RECT = (428, 198, 486, 250)
DONOR_R_RECT = (514, 198, 578, 250)
# 面部皮肤框 (实测脸皮肤 x427~627 / y176~310) —— 用来算"苹果到脸的距离"
FACE_SKIN_BOX = (427, 176, 627, 310)

# ---- 验收方 (父 agent) 给的硬指标框 ----
FACE_BOX = (410, 160, 645, 320)     # 面部框
MOUTH_BOX = (470, 240, 570, 300)    # 嘴框
EYE_BAND = (432, 190, 580, 246)     # 双眼所在带 (苹果不许压到眼睛)

# ---- 苹果与手的贴合参数 (全部按坐姿底图实测) ----
# 底图左手: 腕 (392,545), 掌心沿手指方向 52px, 指尖 95px
APPLE_PROJ = 52        # 苹果中心到腕关节沿手指方向的距离 (掌心/掌指关节处)
FINGER_SPLIT = 58      # 手掌层 / 指尖层的分界 (指尖压在苹果远端 ⇒ 苹果被手指遮挡)
APPLE_EDGE = (74, 58, 52)       # 苹果描边: 柔和深棕 (父 agent 第 4 轮指定 ~RGB(74,58,52))
APPLE_LEAF_EDGE = (44, 104, 84)  # 叶子的描边 (深绿)
APPLE_EDGE_W = 2.4     # 苹果描边宽度 (父 agent: 2~3 纹理 px)


# ---------------------------------------------------------------- 基础工具
def load(path):
    return Image.open(path).convert('RGBA')


def to_np(im):
    return np.asarray(im).astype(np.int32)


def to_im(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')


def lerp_table(tbl, y):
    if y <= tbl[0][0]:
        return float(tbl[0][1])
    for (y0, x0), (y1, x1) in zip(tbl, tbl[1:]):
        if y0 <= y <= y1:
            t = 0.0 if y1 == y0 else (y - y0) / float(y1 - y0)
            return x0 + (x1 - x0) * t
    return float(tbl[-1][1])


def rot_pt(pivot, ang, p):
    """点绕 pivot 旋转 ang 度 (正 = 屏幕顺时针)。"""
    th = np.deg2rad(ang)
    c, s = np.cos(th), np.sin(th)
    dx, dy = p[0] - pivot[0], p[1] - pivot[1]
    return (pivot[0] + dx * c - dy * s, pivot[1] + dx * s + dy * c)


def rot_render(pivot, ang, p):
    """**渲染器一致**的点变换 (36_ 的 rotate_rgba 用的就是这个)。

    【为什么必须单独写一个】
    rotate_rgba(img, pivot, ang) 的输出像素 (x,y) 在输入图里采样于
        pivot + M(ang)·(x-pivot)      (M = [[c,-s],[s,c]])
    ⇒ 内容点 p 落到  pivot + M(-ang)·(p-pivot)  —— 方向是 **-ang**。
    而 rot_pt() 用的是 +ang。拿 rot_pt 去给 IK 做"苹果落点"预测,
    预测位置和**实际渲染出来的手**差一个镜像 ⇒ 苹果与手完全脱节
    (R170 复核: F0 苹果飘在左边 26~30px, F1/F2 苹果与手差 ~80px)。
    """
    return rot_pt(pivot, -ang, p)


def binary_fill(mask):
    """把 mask 的**内部孔洞**补上 (外部背景保持 False)。"""
    h, w = mask.shape
    free = ~mask
    seen = np.zeros_like(free)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if free[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if free[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and free[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return ~seen


def over_correct(dst, src):
    """正确的 source-over (直通 alpha, 非预乘)。

    36_ 的 over() 假设 dst 是不透明的; 手臂摘掉之后 dst 在那块是**全透明**,
    用 36_ 的 over 会把半透明边缘像素的 RGB 乘上 alpha => 边缘发黑。
    这里按直通 alpha 重写, dst 全透明时 RGB 原样保留。
    """
    sa = src[:, :, 3].astype(np.float32) / 255.0
    da = dst[:, :, 3].astype(np.float32) / 255.0
    oa = sa + da * (1.0 - sa)
    out = dst.copy()
    safe = np.where(oa > 1e-6, oa, 1.0)
    for c in range(3):
        out[:, :, c] = ((src[:, :, c].astype(np.float32) * sa
                        + dst[:, :, c].astype(np.float32) * da * (1.0 - sa))
                       / safe).astype(np.int32)
    out[:, :, 3] = np.clip(oa * 255.0, 0, 255).astype(np.int32)
    return out


def compose2(base, segments):
    out = base.copy()
    for seg in segments:
        out = over_correct(out, seg)
    return out


def fill_vertical_clone(body, base, hole, arm_mask, max_dist=HOLE_MAX_DIST):
    """竖向克隆填充: 洞像素 (x,y) 取同列向下第一个"不透明且非手臂"的像素。

    `max_dist` 是关键: 手臂原来搭在**大腿**上的那一块, 向下几十 px 就是
    青色裤腿 ⇒ 会被填成裤腿 (正确); 而袖子那一段向下要跨 90+ px 才能碰到
    大腿 ⇒ 超过 max_dist 就不填 ⇒ 那里本来就是**背景**, 必须保持透明。
    """
    if not hole.any():
        return body, 0
    out = body.copy()
    base_solid = base[:, :, 3] > 40
    src_ok = base_solid & ~arm_mask
    filled = 0
    ys, xs = np.nonzero(hole)
    for x in set(xs.tolist()):
        col_src = np.nonzero(src_ok[:, x])[0]
        if len(col_src) == 0:
            continue
        col_hole = ys[xs == x]
        for y in col_hole:
            below = col_src[(col_src > y) & (col_src <= y + max_dist)]
            if len(below):
                sy = below[0]
            else:
                continue
            out[y, x, 0:3] = base[sy, x, 0:3]
            out[y, x, 3] = base[sy, x, 3]
            filled += 1
    return out, filled


def outline_region(img, region, rgb=OUTLINE_RGB, width=2):
    """给 region 的**外边界**(贴透明处)补一条深色描边。"""
    m = region.copy()
    band = m.copy()
    for _ in range(width):
        o = band.copy()
        o[1:, :] |= band[:-1, :]
        o[:-1, :] |= band[1:, :]
        o[:, 1:] |= band[:, :-1]
        o[:, :-1] |= band[:, 1:]
        band = o
    edge = band & ~m
    out = img.copy()
    out[edge, 0] = rgb[0]
    out[edge, 1] = rgb[1]
    out[edge, 2] = rgb[2]
    out[edge, 3] = 255
    return out


# ---------------------------------------------------------------- 手臂切分
def build_arm(base, side):
    """切出一条坐姿手臂, 返回掩膜 + 关节。"""
    solid = base[:, :, 3] > 40
    arm = np.zeros_like(solid)
    if side == 'L':
        top, bot = L_ARM_TOP, L_HAND_TOP + 92
        for y in range(top, bot):
            if y >= L_HAND_TOP:
                inner = 434
            else:
                inner = int(round(lerp_table(L_SEAM, y)))
            xs = np.nonzero(solid[y, L_OUTER_LO:L_OUTER_HI])[0]
            if len(xs) == 0:
                continue
            outer = L_OUTER_LO + int(xs.min())
            hi = min(inner - 1, 511)
            if hi >= outer:
                arm[y, outer:hi + 1] = True
        hz = np.zeros_like(arm)
        hx0, hy0, hx1, hy1 = L_HAND_ZONE
        hz[hy0:hy1, hx0:hx1] = True
        hand = dilate(skin_relaxed(base) & hz, 7) & solid & hz
        arm |= hand
        S, E, W = L_S, L_E, L_W
    else:
        top, bot = R_ARM_TOP, R_HAND_TOP + 92
        for y in range(top, bot):
            if y >= 552:
                inner = 536
            else:
                inner = int(round(lerp_table(R_INNER, y)))
            xs = np.nonzero(solid[y, 512:])[0]
            if len(xs) == 0:
                continue
            outer = 512 + int(xs.max())
            lo = max(inner + 1, 512)
            if outer >= lo:
                arm[y, lo:outer + 1] = True
        hz = np.zeros_like(arm)
        hx0, hy0, hx1, hy1 = R_HAND_ZONE
        hz[hy0:hy1, hx0:hx1] = True
        hand = dilate(skin_relaxed(base) & hz, 7) & solid & hz
        arm |= hand
        S, E, W = R_S, R_E, R_W

    nS, nE, nW = (disc(base.shape[:2], p, r) for p, r in
                  ((S, 14), (E, 15), (W, 13)))

    def bisect(p, q):
        mx, my = (p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0
        ux, uy = q[0] - p[0], q[1] - p[1]
        n = max(1e-6, (ux * ux + uy * uy) ** 0.5)
        ux, uy = ux / n, uy / n
        yy, xx = np.mgrid[0:base.shape[0], 0:base.shape[1]].astype(np.float64)
        val = (xx - mx) * ux + (yy - my) * uy
        if uy < 0:
            val = -val
        return val

    s_e = bisect(S, E)
    e_w = bisect(E, W)

    # ---- 三段划分 (**必须无重叠、无遗漏**, 否则手臂会"碎成几块") ----
    #  36_ 的划分有一个**像素级漏洞**: elbow 圆盘 nE 的"肩侧那一半"
    #  (s_e<0) 被 upper 的 `~nE` 排除, 又被 fore 的 `s_e>0` 排除
    #  ⇒ 这一半不属于任何一段, 摘掉手臂后那里就是一个**透明缺口**,
    #    肘一折就变成"手臂断成两截"。这里补上:
    #      · fore 额外接管 `nE` 的肩侧一半 (肘圆盘整体绕肘旋转 ⇒ 关节不裂)
    #      · hand 额外接管 `nW` 的全部 (腕圆盘整体绕腕旋转)
    upper = arm & (s_e < 0) & ~nE & ~nW
    fore = arm & (s_e > 0) & (e_w < 0) & ~nW
    fore = fore | (arm & nE & (e_w < 0))
    handseg = (arm & (e_w > 0)) | (arm & nW)
    ball = arm & disc(base.shape[:2], S, SHOULDER_BALL_R)
    fill = upper & disc(base.shape[:2], S, SHOULDER_FILL_R)

    # ---- 前臂段被二分线切开的那条边: 补 2px 描边 ----
    #  R165 实测: 不补的话, 前臂一转, 那条"没有描边的白直边"就暴露在
    #  剪影上, 200x240 下读成**锯齿状虚线**(父 agent R170 复核第①条硬伤)。
    fore_edge = np.zeros_like(arm)
    cut = ((s_e > 0) & (s_e <= CUT_EDGE_PX) & ~nE) | \
          ((e_w < 0) & (e_w >= -CUT_EDGE_PX) & ~nW)
    fore_edge = fore & cut
    # 上臂段顶端 (ARM_TOP) 那条横切边也要描边, 否则抬手时会露出白边
    top_edge = upper & (np.arange(base.shape[0])[:, None] == (L_ARM_TOP if side == 'L'
                                                           else R_ARM_TOP))

    ys, xs = np.nonzero(handseg)
    hand_c = (float(xs.mean()), float(ys.mean())) if len(xs) else (float(W[0]), float(W[1]))
    # **掌心**: 只取"手"的肤色像素 (不含青色袖口), 否则苹果会被放到袖口上
    hskin = skin_relaxed(base) & handseg
    pys, pxs = np.nonzero(hskin)
    palm_c = (float(pxs.mean()), float(pys.mean())) if len(pxs) else hand_c

    # 上臂/前臂切边上的采样点 (给 IK 挑"肘部叠合"的解用)
    cut_pts = []
    if fore_edge is not None and fore_edge.any():
        cy, cx = np.nonzero(fore_edge)
        if len(cx):
            step = max(1, len(cx) // 14)
            cut_pts = [(float(cx[i]), float(cy[i])) for i in range(0, len(cx), step)][:14]

    return dict(side=side, arm=arm, nS=nS, ball=ball, fill=fill,
                upper=upper, fore=fore, hand=handseg, hand_full=hand,
                fore_edge=fore_edge, top_edge=top_edge, cut_pts=cut_pts,
                S=S, E=E, W=W, hand_c=hand_c, palm_c=palm_c)


def detach(body, arm_mask):
    """摘掉手臂 (置透明), 返回 (新身体, 摘下来的像素)。"""
    out = body.copy()
    saved = body[arm_mask].copy()
    out[arm_mask] = 0
    return out, saved


def pose_arm(base, rig, angles, paint_edges=True):
    """三层旋转: 手段绕腕 → 前臂绕肘 → 上臂绕肩; 再静态补肩关节球。

    `paint_edges=False` 用于**原位摆回**的那条手臂 (角度全 0):
    此时不该给切边补描边, 否则会在白大褂上凭空多出两条**长对角墨线**
    (R170 父 agent 复核第①条硬伤里那条"斜线"的真正来源)。
    """
    S, E, W = rig['S'], rig['E'], rig['W']
    a_s, a_e, a_w = angles
    hand = np.where(rig['hand'][:, :, None], base, 0)
    fore = np.where(rig['fore'][:, :, None], base, 0)
    upper = np.where(rig['upper'][:, :, None], base, 0)

    # 被切开的边补描边 (用底图轮廓线的原色) ⇒ 剪影连续, 不会出现白边/虚线
    if paint_edges:
        # 【描边风格 — 父 agent 第 4 轮】袖口切边不要"黑色硬边":
        #   主线用比纯墨色稍浅的 (24,30,56) 全不透明, 再往外补一行半透明
        #   ⇒ 边缘有一层过渡, 读起来是"柔和描边"而不是贴上去的黑条。
        EDGE_SOFT = (24, 30, 56)
        for key in ('fore_edge', 'top_edge'):
            fe = rig.get(key)
            if fe is not None and fe.any():
                tgt = fore if key == 'fore_edge' else upper
                halo = dilate(fe, 1) & ~fe
                tgt[halo, 0] = EDGE_SOFT[0]
                tgt[halo, 1] = EDGE_SOFT[1]
                tgt[halo, 2] = EDGE_SOFT[2]
                tgt[halo, 3] = np.maximum(tgt[halo, 3], 120)
                tgt[fe, 0] = EDGE_SOFT[0]
                tgt[fe, 1] = EDGE_SOFT[1]
                tgt[fe, 2] = EDGE_SOFT[2]
                tgt[fe, 3] = np.maximum(tgt[fe, 3], 255)

    hand1 = rotate_rgba(hand, W, a_w)
    fore1 = rotate_rgba(fore, E, a_e)
    hand2 = rotate_rgba(hand1, E, a_e)
    fore2 = rotate_rgba(fore1, S, a_s)
    hand3 = rotate_rgba(hand2, S, a_s)
    upper2 = rotate_rgba(upper, S, a_s)
    ball = np.where(rig['ball'][:, :, None], base, 0)
    return upper2, fore2, hand3, ball


def transform_point(rig, angles, p):
    """手部像素的净变换 (与 pose_arm 的旋转链**完全一致**: 用 rot_render)。"""
    S, E, W = rig['S'], rig['E'], rig['W']
    a_s, a_e, a_w = angles
    q = rot_render(W, a_w, p)
    q = rot_render(E, a_e, q)
    q = rot_render(S, a_s, q)
    return q


def solve_wrist_only(S, E, W, hand_c, apple_target, a_s, a_e, hand_out=None,
                     palm_c=None):
    """固定肩角/肘角, 只解腕角 a_w: 苹果沿"绕腕的圆弧"移动 (最自然的抬果轨迹)。"""
    hc = np.array(hand_c, float)
    wv = hc - np.array(W, float)
    h_hand = float(np.hypot(*wv))
    base_dir = wv / max(1e-6, h_hand)
    # 苹果锚点 = 腕 + APPLE_PROJ * 手指方向 (掌心 52 / 指尖 95 之间的实测值)
    ref = np.array(W, float) + APPLE_PROJ * base_dir
    U = np.array([E[0] - S[0], E[1] - S[1]], float)
    Ew = np.array([E[0], E[1]], float)
    Wv = np.array([W[0], W[1]], float)
    target = np.array(apple_target, float)

    def pos_of(a_w):
        # rot_render 方向 (内容随 -ang 转), 与 pose_arm 一致
        th = np.deg2rad(-a_w)
        c, s = np.cos(th), np.sin(th)
        v = ref - Wv
        P1 = Wv + np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c])
        th = np.deg2rad(-a_e)
        c, s = np.cos(th), np.sin(th)
        v = P1 - Ew
        Q = Ew + np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c])
        th = np.deg2rad(-a_s)
        c, s = np.cos(th), np.sin(th)
        v = Q - np.array([S[0], S[1]], float)
        return np.array([S[0] + v[0] * c - v[1] * s, S[1] + v[0] * s + v[1] * c])

    best = None
    for a_w in np.arange(-180.0, 180.0, 2.0):
        p = pos_of(a_w)
        e = float(np.hypot(*(target - p)))
        if best is None or e < best[0]:
            best = (e, float(a_w))
    a_w = best[1]
    for _ in range(60):
        p = pos_of(a_w)
        r = target - p
        if float(np.hypot(*r)) < 0.02:
            break
        eps = 0.02
        J = (pos_of(a_w + eps) - p) / eps
        try:
            d = float(np.dot(r, J) / max(1e-6, float(np.dot(J, J))))
        except Exception:
            break
        if abs(d) > 8.0:
            d = 8.0 * (1 if d > 0 else -1)
        a_w += d
    a_w = (a_w + 180.0) % 360.0 - 180.0
    return float(a_s), float(a_e), float(a_w), pos_of(a_w)


def make_arm_underlay(layers, offset=(4, 5), blur=6, alpha=58, rgb=(64, 84, 116),
                      outline_rgb=(14, 20, 42), outline_w=3):
    """手臂压在衣身/头发上会**白对白**糊成一片 (R170 父 agent 复核第①条硬伤)。

    坐姿底图里手臂是**贴着身体**的, 一旦抬起就会整条压在白大褂 / 银白头发上,
    两者都是浅色 ⇒ 手臂只剩两条描边, 读起来就是"碎片 + 悬浮袖口"。

    修法 (与原作风格一致): 在手臂图层下面垫一层
      ① **深色轮廓**(沿手臂剪影外扩 3px 的墨线) —— 原画每个部件都有粗描边,
         手臂抬起后也必须保留自己的轮廓, 否则白对白就没有边界;
      ② **柔和投影**(偏移 4,5 的模糊灰影) —— 给手臂体积, 从大褂上"浮"起来。
    """
    H, W = layers[0].shape[:2]
    m = np.zeros((H, W), bool)
    for lay in layers:
        m |= lay[:, :, 3] > 40
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))

    # ① 墨线轮廓 (垫在手下面, 只露出外侧那一半)
    ring = dilate(m, outline_w) & ~m
    ring_im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ra = np.zeros((H, W, 4), np.uint8)
    ra[:, :, 0] = outline_rgb[0]
    ra[:, :, 1] = outline_rgb[1]
    ra[:, :, 2] = outline_rgb[2]
    ra[:, :, 3] = np.where(ring, 255, 0)
    out.alpha_composite(Image.fromarray(ra, 'RGBA'))

    # ② 柔和投影
    sh = Image.fromarray((m * 255).astype(np.uint8), 'L').filter(
        ImageFilter.GaussianBlur(radius=blur))
    sh = sh.point(lambda v: int(v * alpha / 255))
    sa = np.zeros((H, W, 4), np.uint8)
    sa[:, :, 0] = rgb[0]
    sa[:, :, 1] = rgb[1]
    sa[:, :, 2] = rgb[2]
    sa[:, :, 3] = np.asarray(sh)
    sa = np.roll(sa, shift=(offset[1], offset[0]), axis=(0, 1))
    out.alpha_composite(Image.fromarray(sa, 'RGBA'))
    return out


def solve_arm(S, E, W, hand_c, apple_target, fdir, flip=1, hand_out=None,
              upper_mask=None, cut_pts=None, palm_c=None, fore_mask=None,
              base_arr=None):
    """IK: 让"苹果中心"落到 apple_target, 且最终手指方向 = fdir。

    36_ 的旋转链是 手段绕腕 → 前臂绕肘 → 上臂绕肩 (复合变换), 所以
      final = S + R(a_s)[ (E-S) + R(a_e)(P1-E) ],  P1 = W + R(a_w)(ref-W)
    a_w 由"手指最终朝向 = fdir"唯一确定:  a_w = ang(fdir) - ang(base_dir) - a_s - a_e
    ⇒ 只剩 (a_s, a_e) 两个未知量, 用 粗网格 + 高斯牛顿 精确求解。
    """
    hc = np.array(hand_c, float)
    wv = hc - np.array(W, float)
    h_hand = float(np.hypot(*wv))
    base_dir = wv / max(1e-6, h_hand)
    # 苹果锚点 = 腕 + APPLE_PROJ * 手指方向 (掌心 52 / 指尖 95 之间的实测值)
    ref = np.array(W, float) + APPLE_PROJ * base_dir
    fdir = np.array(fdir, float)
    fdir = fdir / max(1e-6, float(np.hypot(*fdir)))
    target = np.array(apple_target, float)

    U = np.array([E[0] - S[0], E[1] - S[1]], float)
    Ew = np.array([E[0], E[1]], float)
    Wv = np.array([W[0], W[1]], float)

    def a_w_of(a_s, a_e):
        # 最终手指方向 = R(-(a_s+a_e+a_w))·base_dir  (渲染器方向)
        # ⇒ a_w = ang(base_dir) - ang(fdir) - a_s - a_e
        return (float(np.degrees(np.arctan2(base_dir[1], base_dir[0])))
                - float(np.degrees(np.arctan2(fdir[1], fdir[0]))) - a_s - a_e)

    def pos_of(a_s, a_e):
        a_w = a_w_of(a_s, a_e)
        th = np.deg2rad(-a_w)
        c, s = np.cos(th), np.sin(th)
        v = ref - Wv
        P1 = Wv + np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c])
        th = np.deg2rad(-a_e)
        c, s = np.cos(th), np.sin(th)
        v = P1 - Ew
        Q = Ew + np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c])
        th = np.deg2rad(-a_s)
        c, s = np.cos(th), np.sin(th)
        v = Q - np.array([S[0], S[1]], float)
        return np.array([S[0] + v[0] * c - v[1] * s, S[1] + v[0] * s + v[1] * c])

    _ov_cache = {}

    def overlap_score(a_e):
        """前臂绕肘转 a_e 之后, 与上臂**叠合**的像素数 (肘部会不会裂开)。

        【为什么要这个判据】上臂与前臂的切边是一条**直线**(肩肘连线的垂直
        平分线)。两段绕各自关节转过不同的角之后, 这条切边会**错开**
        |S-E|·|sin(a_e/2)| 像素 ⇒ 肘部裂开一道口子。
        36_ 在站立底图上没暴露, 是因为裂开的那块正好被**身体**挡住;
        坐姿底图里手臂贴着剪影 ⇒ 裂缝直接露在背景上, 读成"手臂断成两截"
        (父 agent R170 复核第①条硬伤)。

        【关键】上臂与前臂的**相对**变换只有 Rot(E, a_e) —— 与 a_s 无关
        (a_s 是两者共有的那一层), 所以叠合量只取决于 a_e, 可以按 a_e 缓存。
        """
        key = round(a_e, 1)
        if key in _ov_cache:
            return _ov_cache[key]
        if upper_mask is None or fore_mask is None:
            return 0.0
        fore_rot = rotate_rgba(np.where(fore_mask[:, :, None], base_arr, 0), E, a_e)
        fr = fore_rot[:, :, 3] > 100
        ov = int((dilate(upper_mask, 3) & fr).sum())
        _ov_cache[key] = ov
        return ov

    def refine(a_s0, a_e0):
        # 高斯牛顿精修 (把苹果落点推到 target)
        a_s, a_e = float(a_s0), float(a_e0)
        for _ in range(60):
            p = pos_of(a_s, a_e)
            r = target - p
            if float(np.hypot(*r)) < 0.02:
                break
            J = np.zeros((2, 2))
            eps = 0.05
            for i in range(2):
                if i == 0:
                    p2 = pos_of(a_s + eps, a_e)
                else:
                    p2 = pos_of(a_s, a_e + eps)
                J[:, i] = (p2 - p) / eps
            try:
                d = np.linalg.solve(J, r)
            except np.linalg.LinAlgError:
                break
            # 限步长, 防止牛顿迭代发散到几千度
            dn = float(np.hypot(*d))
            if dn > 8.0:
                d = d * (8.0 / dn)
            a_s += float(d[0])
            a_e += float(d[1])
        return a_s, a_e

    # --- 粗网格: 收集**所有**够得着的 (a_s,a_e) 候选 ---
    # 【为什么不能只在 err<8 的网格点上挑】同一个手部落点对应**一族**解,
    # 它们的 a_e 不同 ⇒ 肘部切边张开量不同 (张开量 ≈ |S-E|·2sin(a_e/2))。
    # 只在"误差 < 8px"的网格点上打分, 会因为 7° 的网格步长把
    # "肘部连续"的那一族解整族漏掉 ⇒ 画面上出现断肘 (R170 F0 实测)。
    # 现在: ① 放宽到 err<16 收集候选; ② 每个候选都精修; ③ 用**精修后**
    # 的肘部叠合量重新打分。
    cands = []
    for a_s in np.arange(-175.0, 180.0, 7.0):
        for a_e in np.arange(-175.0, 180.0, 7.0):
            p = pos_of(a_s, a_e)
            err = float(np.hypot(*(target - p)))
            if err > 16.0:
                continue
            cands.append((err, float(a_s), float(a_e)))
    if not cands:
        bestg = None
        for a_s in np.arange(-175.0, 180.0, 7.0):
            for a_e in np.arange(-175.0, 180.0, 7.0):
                p = pos_of(a_s, a_e)
                err = float(np.hypot(*(target - p)))
                if bestg is None or err < bestg[0]:
                    bestg = (err, float(a_s), float(a_e))
        a_s, a_e = refine(bestg[1], bestg[2])
    else:
        # 按 a_e 分箱 (叠合量只取决于 a_e), 每箱只留误差最小的一个候选
        boxes = {}
        for err, a_s, a_e in cands:
            k = int(round(a_e / 6.0))
            if k not in boxes or err < boxes[k][0]:
                boxes[k] = (err, a_s, a_e)
        best = None
        for k, (err0, a_s0, a_e0) in boxes.items():
            a_s, a_e = refine(a_s0, a_e0)
            p = pos_of(a_s, a_e)
            err = float(np.hypot(*(target - p)))
            if err > 6.0:
                continue
            ov = overlap_score(a_e)
            pen = 0.02 * abs(a_s) + 0.01 * abs(a_e)
            score = err - 0.03 * ov + pen
            if best is None or score < best[0]:
                best = (score, a_s, a_e, ov, err)
        if best is None:
            a_s, a_e = refine(*min(cands)[1:])
        else:
            a_s, a_e = best[1], best[2]
    a_w = a_w_of(a_s, a_e)
    # 归一到 (-180,180]
    a_s = (a_s + 180.0) % 360.0 - 180.0
    a_e = (a_e + 180.0) % 360.0 - 180.0
    a_w = (a_w + 180.0) % 360.0 - 180.0
    return float(a_s), float(a_e), float(a_w), pos_of(a_s, a_e)


# ---------------------------------------------------------------- 苹果
def make_apple(diameter=64):
    """程序化画一颗苹果 (RGBA, 4x 超采样后缩回)。

    【描边风格 — 父 agent 第 3 轮要求】
      ① **柔和深棕**, 不是角色的墨蓝 (10,14,34): 苹果是暖色系, 用墨蓝会显脏;
      ② **线宽比角色略细** (1.6px vs 角色 ~2px);
      ③ **去白边**: 之前的高光用了 alpha=215, 而 ImageDraw 是**直接覆盖**而不是
         alpha 合成 ⇒ 果身上被挖出一个半透明的洞, 合成到白大褂上就是一圈白边。
         现在所有色块都不透明, 边缘像素统一染成描边色。

    【果身对称】红像素 bbox 的中心必须严格等于画布中心, 这样
    "苹果中心 = 贴图位置" 才成立, 报告里的 apple_center 才是可信的实测值。
    """
    SS = 4
    d = diameter * SS
    pad = int(d * 0.30)
    size = d + 2 * pad
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    cx = size // 2
    cy = size // 2

    body = (226, 84, 88, 255)
    dark = (168, 48, 58, 255)

    def el(box, **kw):
        dr.ellipse([int(box[0]), int(box[1]), int(box[2]), int(box[3])], **kw)

    def poly(pts, **kw):
        dr.polygon([(int(x), int(y)) for x, y in pts], **kw)

    r = int(d * 0.50)
    # --- 果身: 三块都关于 (cx, cy) 对称 ⇒ 红像素 bbox 中心 == 画布中心 ---
    el((cx - r, cy - r, cx + r, cy + r), fill=body)
    el((cx - int(d * 0.54), cy - int(d * 0.44), cx - int(d * 0.02), cy + int(d * 0.44)), fill=body)
    el((cx + int(d * 0.02), cy - int(d * 0.44), cx + int(d * 0.54), cy + int(d * 0.44)), fill=body)
    el((cx - int(d * 0.36), cy - int(d * 0.10), cx + int(d * 0.36), cy + int(d * 0.50)), fill=body)
    # 底部暗面 (左右对称)
    el((cx - int(d * 0.32), cy + int(d * 0.24), cx + int(d * 0.32), cy + int(d * 0.48)), fill=dark)
    el((cx - int(d * 0.28), cy + int(d * 0.20), cx + int(d * 0.28), cy + int(d * 0.42)), fill=body)
    # 高光 (不透明, 靠颜色而不是 alpha 做柔光 ⇒ 不会在果身上打洞)
    el((cx - int(d * 0.28), cy - int(d * 0.30), cx - int(d * 0.12), cy - int(d * 0.13)),
       fill=(243, 138, 130, 255))
    # 果柄 (正中, 深棕)
    poly([(cx - 3, cy - r + 2), (cx + 3, cy - r + 1),
          (cx + 5, cy - r - int(d * 0.17)), (cx - 1, cy - r - int(d * 0.15))],
         fill=(112, 74, 52, 255))
    # 叶子 (右上)
    el((cx + int(d * 0.02), cy - r - int(d * 0.20), cx + int(d * 0.34), cy - r - int(d * 0.02)),
       fill=(74, 158, 128, 255))
    el((cx + int(d * 0.08), cy - r - int(d * 0.16), cx + int(d * 0.26), cy - r - int(d * 0.06)),
       fill=(112, 196, 158, 255))

    img = img.resize((size // SS, size // SS), Image.LANCZOS)
    arr = np.asarray(img).copy()
    a = arr[:, :, 3]

    # --- 柔和内描边: 按"到剪影边缘的距离"混色, 线宽 APPLE_EDGE_W ---
    solid = a > 8
    dist = np.zeros(solid.shape, np.int32)
    cur = solid.copy()
    for k in range(1, 5):
        nxt = cur.copy()
        nxt[1:, :] &= cur[:-1, :]
        nxt[:-1, :] &= cur[1:, :]
        nxt[:, 1:] &= cur[:, :-1]
        nxt[:, :-1] &= cur[:, 1:]
        nxt &= cur
        dist[nxt] = k
        cur = nxt
    t = np.clip((APPLE_EDGE_W - dist) / APPLE_EDGE_W, 0.0, 1.0)[:, :, None]
    is_leaf = (arr[:, :, 1].astype(np.int32) - arr[:, :, 0].astype(np.int32) > 24)
    edge_col = np.where(is_leaf[:, :, None],
                         np.array(APPLE_LEAF_EDGE, float)[None, None, :],
                         np.array(APPLE_EDGE, float)[None, None, :])
    mixed = arr[:, :, :3].astype(float) * (1 - t) + edge_col * t
    arr[:, :, :3] = np.clip(mixed, 0, 255).astype(np.uint8)
    # 半透明边缘像素直接染成描边色 ⇒ 彻底去掉白边
    low = (a > 0) & (a < 250)
    for ch in range(3):
        arr[:, :, ch] = np.where(low, edge_col[:, :, ch].astype(np.uint8), arr[:, :, ch])
    return Image.fromarray(arr, 'RGBA')


def apple_red_center(im):
    """贴图内**红色果身**像素 bbox 的中心 (相对贴图左上角)。"""
    arr = np.asarray(im)
    red = (arr[:, :, 0] > 180) & (arr[:, :, 3] > 100) \
        & (arr[:, :, 0] - arr[:, :, 1] > 90) & (arr[:, :, 0] - arr[:, :, 2] > 110)
    ys, xs = np.nonzero(red)
    if len(xs) == 0:
        return (im.width / 2.0, im.height / 2.0)
    return ((xs.min() + xs.max()) / 2.0, (ys.min() + ys.max()) / 2.0)


# ---------------------------------------------------------------- 表情
def sample_skin(arr, box):
    x0, y0, x1, y1 = box
    reg = arr[y0:y1, x0:x1, :3].astype(np.float64)
    L = 0.299 * reg[:, :, 0] + 0.587 * reg[:, :, 1] + 0.114 * reg[:, :, 2]
    m = (L > 200) & (reg[:, :, 0] > 235) & (reg[:, :, 2] > 180)
    if m.sum() < 3:
        return np.array([250, 213, 196])
    return np.median(reg[m], axis=0)


def draw_open_mouth(arr):
    """把闭嘴画成张嘴 (R138 没有张嘴素材, 程序化绘制)。

    画法: ① 用周围肤色把原来的嘴**抹平**(带羽化, 不留硬边);
          ② 画一个上下唇包住的**口腔**(深赭红) + 一点舌头;
          ③ 补一条上唇线。
    嘴的位置用实测值 MOUTH_C=(507,271), 嘴宽 45px (x485~530)。
    """
    im = to_im(arr)
    cx, cy = MOUTH_C
    hw, hh = MOUTH_HALF
    skin = CHEEK_SKIN

    # ① 抹掉原来的嘴 (椭圆羽化)
    erase = Image.new('RGBA', im.size, (0, 0, 0, 0))
    de = ImageDraw.Draw(erase)
    de.ellipse([cx - hw - 7, cy - hh - 7, cx + hw + 7, cy + hh + 11], fill=skin + (255,))
    erase = erase.filter(ImageFilter.GaussianBlur(radius=2.2))
    im.alpha_composite(erase)

    dr = ImageDraw.Draw(im)
    # ② 口腔
    dr.ellipse([cx - hw + 2, cy - hh, cx + hw - 2, cy + hh - 1], fill=(112, 46, 50, 255))
    dr.ellipse([cx - hw + 5, cy - hh + 1, cx + hw - 5, cy - 1], fill=(78, 30, 36, 255))
    # 舌头
    dr.ellipse([cx - int(hw * 0.58), cy + 1, cx + int(hw * 0.58), cy + int(hh * 0.92)],
               fill=(200, 108, 106, 255))
    # ③ 上唇线
    dr.arc([cx - hw + 2, cy - hh - 3, cx + hw - 2, cy + hh - 3], 190, 350,
           fill=(126, 56, 54, 255), width=2)
    return to_np(im)


def draw_blush(arr, strength=1.0):
    """腮微鼓: 两侧脸颊加一点柔和的腮红。"""
    im = to_im(arr).filter(ImageFilter.GaussianBlur(radius=3))
    blush = Image.new('RGBA', im.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(blush)
    for cx in (462, 552):
        dr.ellipse([cx - 22, 262, cx + 22, 290], fill=(246, 158, 158, int(90 * strength)))
    out = Image.alpha_composite(to_im(arr), blush)
    return to_np(out)


def swap_happy_eyes(arr, donor_arr):
    """把 donor 的闭眼(笑眼)搬到当前帧的两个眼睛区域。"""
    out = arr.copy()
    for rect, drect in ((EYE_L_RECT, DONOR_L_RECT), (EYE_R_RECT, DONOR_R_RECT)):
        x0, y0, x1, y1 = rect
        dx0, dy0, dx1, dy1 = drect
        patch = Image.fromarray(np.clip(donor_arr[dy0:dy1, dx0:dx1], 0, 255).astype(np.uint8), 'RGBA')
        tw, th = x1 - x0, y1 - y0
        patch = patch.resize((tw, th), Image.LANCZOS)
        # 边缘羽化 6px
        alpha = patch.getchannel('A')
        ramp = Image.new('L', (tw, th), 255)
        d2 = ImageDraw.Draw(ramp)
        f = 6
        for i in range(f):
            v = int(255 * (i + 1) / f)
            d2.rectangle([i, i, tw - 1 - i, th - 1 - i], outline=None)
            d2.rectangle([i, i, tw - 1 - i, i], fill=v)
            d2.rectangle([i, th - 1 - i, tw - 1 - i, th - 1 - i], fill=v)
            d2.rectangle([i, i, i, th - 1 - i], fill=v)
            d2.rectangle([tw - 1 - i, i, tw - 1 - i, th - 1 - i], fill=v)
        patch.putalpha(Image.composite(alpha, Image.new('L', (tw, th), 0), ramp.point(lambda v: 255 if v > 128 else 0)))
        base_im = to_im(out)
        base_im.alpha_composite(patch, (x0, y0))
        out = to_np(base_im)
    return out


# ---------------------------------------------------------------- 动作表
# 【R170 第 4 轮方案 — 父 agent 改方案】
#   旧方案 "手精确送到嘴边" 在 2D 刚体 rig 上做不到 (苹果要么压嘴、要么手挡嘴),
#   改成: **双手捧果在胸前 + 低头张嘴咬一口**。
#   苹果全程在**胸口/下颌**高度, 只有咬的那一帧抬头去够;
#   嘴框 (470,240)-(570,300) 全程不被手/苹果遮挡。
#
# 硬性几何 (1024 纹理坐标, 全部按父 agent 第 4 轮口径):
#   · 苹果位置 = 掌心锚点 (腕 + APPLE_PROJ * 手指方向), 不再给苹果独立目标点
#   · 苹果 ∩ FACE_BOX (410,160)-(645,320) == 0  ⇒ 苹果顶边必须 ≥ 320
#   · F2 苹果 ∩ 嘴框 == 0 且 到嘴框距离 ≤ 30 (验收脚本 E4) ⇒ 苹果顶边 ∈ [300,320]
#   · 果体到嘴框距离: F0 ≥200 / F1 ≥110 / F2 ≤45(实测≤30) / F3 40~90 / F4 100~170
#   · F2 手+苹果覆盖嘴框 ≤ 30 px  ⇒ 指尖不能碰到 y<300
FRAMES = [
    # 0: 伸手去果盘拿水果 —— 手臂下探外探, 苹果刚离开小边桌上的果盘
    dict(name='eat_fruit_0', apple=(340, 545), fdir=(-0.45, 0.89), flip=1,
         head=(0, 0, 1.0), face=None, mouth='closed', blush=0.0,
         note='伸手去果盘拿水果 (手臂下探外探, 苹果刚离开果盘)'),
    # 1: 把水果捧到胸前 —— 苹果在脸正下方, 完全不遮脸
    dict(name='eat_fruit_1', apple=(448, 438), fdir=(0.25, -0.97), flip=1,
         head=(0, 0, 1.0), face=None, mouth='closed', blush=0.0,
         note='把水果捧到胸前 (苹果在脸下方, 完全不遮脸)'),
    # 2: 低头张嘴咬一口 —— 头下压 + 嘴张开, 苹果顶到下唇下方, 嘴不被遮挡
    dict(name='eat_fruit_2', apple=(505, 348), fdir=(0.98, 0.20), flip=1,
         head=(-3.0, 10, 0.99), face=None, mouth='open', blush=0.0,
         note='低头张嘴咬一口 (苹果顶到下唇下方, 嘴全程可见)'),
    # 3: 咀嚼 —— 头回正一点, 苹果稍微退开, 腮微鼓
    dict(name='eat_fruit_3', apple=(500, 378), fdir=(0.95, 0.31), flip=1,
         head=(0, 4, 0.995), face=None, mouth='closed', blush=1.0,
         note='咀嚼 (苹果退开一点, 腮微鼓)'),
    # 4: 满足地笑 —— 苹果放回胸前, 换成笑眼
    dict(name='eat_fruit_4', apple=(478, 432), fdir=(0.35, -0.94), flip=1,
         head=(0, 0, 1.0), face='happy', mouth='closed', blush=0.6,
         note='满足地笑 (苹果放回胸前, 笑眼)'),
]

APPLE_D = 44
APPLE_R = APPLE_D // 2


def build_frame(base, rigL, rigR, spec, donor_np, rigL2=None):
    """合成一帧。

    【绘制顺序 — 父 agent 第 4 轮要求】
        身体(已含表情/头部变形) → 手臂下垫 → 上臂 → 前臂 → 手掌
        → **苹果** → **指尖** → 肩球
    ⇒ 苹果压在掌心之上、指尖压在苹果之上 = "手指握住苹果"。
    """
    fdir = spec['fdir']
    flip = spec.get('flip', 1)

    # ---------- 1) 身体: 摘掉两条手臂 + 补洞 ----------
    body = base.copy()
    body, _ = detach(body, rigL['arm'])
    body, _ = detach(body, rigR['arm'])
    upR, foR, hdR, ballR = pose_arm(base, rigR, (0, 0, 0), paint_edges=False)
    body = compose2(body, [upR, foR, hdR])
    solid = base[:, :, 3] > 40
    hole = rigL['arm'] & solid
    body, n_filled = fill_vertical_clone(body, base, hole, rigL['arm'])
    filled_region = hole & (body[:, :, 3] > 40)
    body = outline_region(body, filled_region)

    # ---------- 2) 表情 (画在身体上, 之后随头部一起变形) ----------
    if spec['mouth'] == 'open':
        body = draw_open_mouth(body)
    if spec['blush']:
        body = draw_blush(body, spec['blush'])
    if spec['face'] == 'happy':
        body = swap_happy_eyes(body, donor_np)

    # ---------- 3) 头部局部变形 (只作用在身体, 手臂/苹果不跟着头动) ----------
    rot, dy, sc = spec['head']
    if rot or dy or sc != 1.0:
        tmp = os.path.join('/tmp', '_r170_head.png')
        to_im(body).save(tmp)
        _r153.head_transform(tmp, tmp, dx=0, dy=dy, scale=sc, rotate=rot, tag=spec['name'])
        body = to_np(load(tmp))

    # ---------- 4) IK: 苹果锚点 = 腕 + APPLE_PROJ * 手指方向 ----------
    a_s, a_e, a_w, elbow = solve_arm(
        rigL['S'], rigL['E'], rigL['W'], rigL['hand_c'], spec['apple'], fdir,
        flip=flip, upper_mask=rigL['upper'], cut_pts=rigL.get('cut_pts'),
        fore_mask=rigL['fore'], base_arr=base)
    angles = (a_s, a_e, a_w)

    # ---------- 5) 摆臂 + 手掌/指尖分层 ----------
    up, fo, hd, ball = pose_arm(base, rigL, angles)
    W, E, S = rigL['W'], rigL['E'], rigL['S']
    base_dir = np.array(rigL['hand_c'], float) - np.array(W, float)
    base_dir = base_dir / max(1e-6, float(np.hypot(*base_dir)))
    yy, xx = np.mgrid[0:base.shape[0], 0:base.shape[1]].astype(np.float64)
    along = (xx - W[0]) * base_dir[0] + (yy - W[1]) * base_dir[1]
    # 分界带 2px 羽化 (硬切会留下 1px 锯齿, 放大后像"撕纸边")
    hand_m = rigL['hand']
    f_a = np.clip((along - FINGER_SPLIT + 1.0) / 2.0, 0.0, 1.0) * hand_m
    p_a = np.clip((FINGER_SPLIT + 1.0 - along) / 2.0, 0.0, 1.0) * hand_m

    def layer_of(alpha):
        lay = base.copy()
        a = lay[:, :, 3].astype(np.float64) * alpha
        lay[:, :, 3] = np.clip(a, 0, 255).astype(np.uint8)
        lay[a <= 0, 0:3] = 0
        return lay

    palm = layer_of(p_a)
    fing = layer_of(f_a)
    palm = rotate_rgba(palm, W, a_w)
    palm = rotate_rgba(palm, E, a_e)
    palm = rotate_rgba(palm, S, a_s)
    fing = rotate_rgba(fing, W, a_w)
    fing = rotate_rgba(fing, E, a_e)
    fing = rotate_rgba(fing, S, a_s)

    # ---------- 6) 苹果 (位置 = 掌心锚点, 红像素中心严格落在锚点上) ----------
    apple_ref = np.array(W, float) + APPLE_PROJ * base_dir
    got = transform_point(rigL, angles, apple_ref)
    apple_im = make_apple(APPLE_D)
    rcx, rcy = apple_red_center(apple_im)
    ax = int(round(got[0] - rcx))
    ay = int(round(got[1] - rcy))
    apple_layer = Image.new('RGBA', base.shape[:2], (0, 0, 0, 0))
    apple_layer.alpha_composite(apple_im, (ax, ay))
    # 实测: 最终成图里红色果身的 bbox 中心
    _ab = np.asarray(apple_layer)
    _red = (_ab[:, :, 0] > 180) & (_ab[:, :, 3] > 100) \
        & (_ab[:, :, 0] - _ab[:, :, 1] > 90) & (_ab[:, :, 0] - _ab[:, :, 2] > 110)
    _ay, _ax = np.nonzero(_red)
    if len(_ax):
        got = (float((_ax.min() + _ax.max()) / 2.0), float((_ay.min() + _ay.max()) / 2.0))

    # ---------- 7) 合成 ----------
    canvas_im = to_im(body)
    # 手臂下垫 (在身体之上、手臂之下): 墨线轮廓 + 柔和投影, 让白袖从白大褂里"浮"出来
    canvas_im.alpha_composite(make_arm_underlay([up, fo, palm, fing]))
    canvas_im.alpha_composite(to_im(up))
    canvas_im.alpha_composite(to_im(fo))
    canvas_im.alpha_composite(to_im(palm))
    canvas_im.alpha_composite(apple_layer)     # 苹果在掌心之上
    canvas_im.alpha_composite(to_im(fing))      # 指尖压在苹果之上
    canvas_im.alpha_composite(to_im(ball))
    canvas_im.alpha_composite(to_im(ballR))
    out = to_np(canvas_im)
    return out, angles, got, n_filled, fing[:, :, 3] > 100



def sweep(base, rigL, rigR, donor_np):
    """姿态扫描: 渲染 (苹果目标 × 手指方向) 组合, 供肉眼挑"手臂连续"的姿态。"""
    cands = []
    for apple in [(480, 300), (470, 295), (490, 310), (450, 330)]:
        for ang in (30, 60, 100, 120, 140, 160, 200, 250):
            f = (np.cos(np.deg2rad(ang)), np.sin(np.deg2rad(ang)))
            cands.append((apple, f))
    tiles = []
    for apple, fdir in cands:
        spec = dict(name='sweep', apple=apple, fdir=fdir, flip=1,
                    head=(0, 0, 1.0), face=None, mouth='closed', blush=0.0)
        out, angles, got, nf = build_frame(base, rigL, rigR, spec, donor_np)
        im = to_im(out)
        bg = Image.new('RGBA', im.size, (248, 249, 252, 255))
        bg.alpha_composite(im)
        d = ImageDraw.Draw(bg)
        d.text((6, 6), f'p{apple} f{np.degrees(np.arctan2(fdir[1], fdir[0])):.0f}'
                      f' a=({angles[0]:.0f},{angles[1]:.0f},{angles[2]:.0f})',
               fill=(200, 0, 0))
        tiles.append(bg)
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    W, H = tiles[0].size
    sheet = Image.new('RGB', (W * cols, H * rows), (255, 255, 255))
    for i, t in enumerate(tiles):
        sheet.paste(t.convert('RGB'), ((i % cols) * W, (i // cols) * H))
    sheet = sheet.resize((sheet.width // 3, sheet.height // 3), Image.LANCZOS)
    sheet.save('/tmp/r170_sweep.png')
    print('sweep 图:', sheet.size, ' 组合数', len(cands))
    return 0


def comp_count(mask, min_px=40, conn=8):
    """连通块计数 (返回 [(px, bbox), ...])。"""
    h, w = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    ys, xs = np.nonzero(mask)
    for sy, sx in zip(ys, xs):
        if seen[sy, sx]:
            continue
        stack = [(sy, sx)]
        seen[sy, sx] = True
        pts = []
        while stack:
            y, x = stack.pop()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if conn == 4 and dx and dy:
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        if len(pts) >= min_px:
            pa = np.array(pts)
            out.append((len(pts), [int(pa[:, 1].min()), int(pa[:, 0].min()),
                                   int(pa[:, 1].max()) + 1, int(pa[:, 0].max()) + 1]))
    out.sort(key=lambda t: -t[0])
    return out


# ---------------------------------------------------------------- 指标
def label_comps(mask, conn=4, min_px=300):
    """连通块标注 (run-based union-find, 不依赖 scipy)。

    返回 (labels, comps): labels 是每个像素所属块 (小块记 -1), comps 是
    [(n_px, [x0,y0,x1,y1]), ...] 按面积降序。4 邻接 —— 与验收脚本 83_ 一致。
    """
    h, w = mask.shape
    parent = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    rows = []
    prev = []
    for y in range(h):
        row = mask[y]
        if not row.any():
            prev = []
            continue
        idx = np.flatnonzero(np.diff(np.concatenate(([0], row.view(np.int8), [0]))))
        cur = []
        for s, e in zip(idx[0::2], idx[1::2] - 1):
            lab = len(parent)
            parent.append(lab)
            cur.append((int(s), int(e), lab))
            rows.append((y, int(s), int(e), lab))
        for (s, e, l) in cur:
            for (ps, pe, pl) in prev:
                if s <= pe and ps <= e:
                    union(l, pl)
        prev = cur
    stats = {}
    for (y, s, e, l) in rows:
        r = find(l)
        st = stats.get(r)
        if st is None:
            stats[r] = [0, s, y, e, y]
        st = stats[r]
        st[0] += e - s + 1
        if s < st[1]:
            st[1] = s
        if y < st[2]:
            st[2] = y
        if e > st[3]:
            st[3] = e
        if y > st[4]:
            st[4] = y
    labels = np.full((h, w), -1, np.int32)
    for (y, s, e, l) in rows:
        r = find(l)
        st = stats[r]
        if st[0] >= min_px:
            labels[y, s:e + 1] = r
    comps = sorted([(v[0], [v[1], v[2], v[3], v[4]]) for v in stats.values() if v[0] >= min_px],
                   key=lambda t: -t[0])
    return labels, comps


def min_dist_np(a_mask, b_mask, metric='cheb'):
    """两组像素间的最短距离。metric='cheb' 与验收脚本 83_ 的 BFS 口径一致
    (8 邻域 ⇒ 切比雪夫距离), metric='euclid' 给出欧氏距离。"""
    ay, ax = np.nonzero(a_mask)
    by, bx = np.nonzero(b_mask)
    if len(ay) == 0 or len(by) == 0:
        return None
    best = None
    step = 512
    for i in range(0, len(ay), step):
        dy = np.abs(ay[i:i + step, None].astype(np.int32) - by[None, :])
        dx = np.abs(ax[i:i + step, None].astype(np.int32) - bx[None, :])
        if metric == 'cheb':
            d = np.maximum(dx, dy)
        else:
            d = np.sqrt(dx.astype(np.float64) ** 2 + dy.astype(np.float64) ** 2)
        m = float(d.min())
        if best is None or m < best:
            best = m
    return best


def fruit_mask_of(arr):
    """果体像素 (与验收脚本 83_ 的 fruit_mask 同口径: 暖色 + 最大连通块)。"""
    R, G, B, Al = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    warm = (Al > 60) & (R > 130) & ((R - G) > 60) & ((R - B) > 60) & (G < 150)
    if not warm.any():
        return warm
    _, comps = label_comps(warm, min_px=150)
    if not comps:
        return np.zeros(warm.shape, bool)
    best = comps[0]
    out = np.zeros(warm.shape, bool)
    x0, y0, x1, y1 = best[1]
    out[y0:y1 + 1, x0:x1 + 1] = warm[y0:y1 + 1, x0:x1 + 1]
    return out


def skin_mask_of(arr):
    """肤色 (与验收脚本 83_ 的 skin_mask 同口径)。"""
    R, G, B, Al = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    return (Al > 60) & (R >= 195) & (G >= 160) & (B >= 140) \
        & ((R - B) >= 12) & ((R - G) >= -8)


def box_mask(shape, box):
    m = np.zeros(shape[:2], bool)
    x0, y0, x1, y1 = box
    m[y0:y1, x0:x1] = True
    return m


def verify_frame(arr, base, rigL, angles, apple_px, face_box, finger_world=None,
                 base_skin_dil=None):
    """一帧的客观指标 (口径对齐验收脚本 83_R170_scene_verify.py)。"""
    res = {}
    a_s, a_e, a_w = angles
    up, fo, hd, ball = pose_arm(base, rigL, angles)
    up_m = up[:, :, 3] > 100
    fo_m = fo[:, :, 3] > 100
    hd_m = hd[:, :, 3] > 100
    res['upper_px'] = int(up_m.sum())
    res['fore_px'] = int(fo_m.sum())
    res['hand_px'] = int(hd_m.sum())
    res['seam_upper_fore'] = int((dilate(up_m, 3) & fo_m).sum())
    res['seam_fore_hand'] = int((dilate(fo_m, 3) & hd_m).sum())
    arm_union = up_m | fo_m | hd_m
    comps = comp_count(arm_union, min_px=30)
    res['arm_components'] = len(comps)
    res['arm_largest_frac'] = round(comps[0][0] / max(1, arm_union.sum()), 4) if comps else 0.0

    # ---- 果体 (验收脚本口径) ----
    fr = fruit_mask_of(arr)
    res['fruit_px'] = int(fr.sum())
    ys, xs = np.nonzero(fr)
    if len(xs):
        res['fruit_bbox'] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        res['fruit_center'] = [round(float((xs.min() + xs.max()) / 2.0), 1),
                                round(float((ys.min() + ys.max()) / 2.0), 1)]
    else:
        res['fruit_bbox'] = None
        res['fruit_center'] = None

    face_sk = skin_mask_of(arr) & box_mask(arr.shape, FACE_BOX)
    hand_sk = skin_mask_of(arr) & ~face_sk
    mouth_m = box_mask(arr.shape, MOUTH_BOX)
    face_m = box_mask(arr.shape, FACE_BOX)
    eye_m = box_mask(arr.shape, EYE_BAND)

    res['apple_to_hand_dist'] = min_dist_np(fr, hand_sk)
    res['apple_to_hand_dist_euclid'] = min_dist_np(fr, hand_sk, 'euclid')
    res['apple_to_mouth_dist'] = min_dist_np(fr, mouth_m)
    res['apple_to_mouth_dist_euclid'] = min_dist_np(fr, mouth_m, 'euclid')
    res['apple_to_face_dist'] = min_dist_np(fr, face_sk)
    res['apple_mouth_overlap_px'] = int((fr & mouth_m).sum())
    res['apple_face_overlap_px'] = int((fr & face_m).sum())
    res['apple_eye_overlap_px'] = int((fr & eye_m).sum())
    # 手 + 苹果 一起盖住嘴框的像素
    res['hand_apple_cover_mouth_px'] = int(((fr | hand_sk) & mouth_m).sum())
    # 苹果被指尖遮挡的像素 (苹果层在指尖层之下)
    if finger_world is not None:
        res['apple_occluded_by_finger_px'] = int((fr & finger_world).sum())
    res['apple_hand_overlap_px'] = int((fr & hand_sk).sum())

    # ---- 角色整体连通块 (E5) / 苹果是否落在主块里 (E10) ----
    solid = arr[:, :, 3] > 60
    labels, scomps = label_comps(solid, min_px=300)
    res['solid_block_count'] = len(scomps)
    res['solid_blocks'] = [[c[0], c[1]] for c in scomps[:4]]
    if scomps and fr.any():
        big = max(range(len(scomps)), key=lambda i: scomps[i][0])
        # labels 里用的是 root id, 重新取主块的像素集合
        main_mask = np.zeros(solid.shape, bool)
        ys2, xs2 = np.nonzero(solid)
        vals, counts = np.unique(labels[ys2, xs2], return_counts=True)
        main_id = int(vals[int(np.argmax(counts))])
        main_mask = (labels == main_id)
        tot = int(fr.sum())
        on_main = int((fr & main_mask).sum())
        res['apple_in_main_block_ratio'] = round(on_main / tot, 4) if tot else 0.0
    else:
        res['apple_in_main_block_ratio'] = 0.0

    # ---- 抬起的手臂 (E9: 相对基图新增的肤色) ----
    if base_skin_dil is not None:
        res['raised_hand_px'] = int((hand_sk & ~base_skin_dil).sum())

    # ---- 手与嘴的实际坐标 (交接用) ----
    ys3, xs3 = np.nonzero(hd_m)
    res['hand_bbox'] = ([int(xs3.min()), int(ys3.min()), int(xs3.max()), int(ys3.max())]
                        if len(xs3) else None)
    R, G, B, Al = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    cav = (Al > 60) & (R > 60) & (R < 200) & ((R - G) > 40) & ((R - B) > 30) & mouth_m
    ys4, xs4 = np.nonzero(cav)
    res['mouth_cavity_bbox'] = ([int(xs4.min()), int(ys4.min()), int(xs4.max()), int(ys4.max())]
                                if len(xs4) else None)
    res['mouth_cavity_px'] = int(cav.sum())

    # ---- 手臂区肤色连通块 (E5 细项) ----
    sk = skin_relaxed(arr)
    comps_skin = comp_count(sk, min_px=150)
    res['skin_blobs'] = [[c[0], c[1]] for c in comps_skin[:8]]
    arm_band = sk.copy()
    arm_band[:360] = False
    res['skin_blobs_arm_band'] = int(len(comp_count(arm_band, min_px=150)))

    # ---- 大腿破洞 / 整体丢像素 ----
    tl = teal(base)
    leg = np.zeros_like(tl)
    leg[600:1000, :] = tl[600:1000, :]
    leg = dilate(leg, 6)
    holes = (base[:, :, 3] > 40) & (arr[:, :, 3] <= 40) & leg
    res['thigh_hole_px'] = int(holes.sum())
    res['total_lost_px'] = int(((base[:, :, 3] > 40) & (arr[:, :, 3] <= 40)).sum())
    return res



def compose_scene(char_path, prop_paths, scale, canvas_w, canvas_h, floor_tex_y,
                  char_ground):
    """复刻 45_R165_scene_preview.py 的合成规则 (同 scale / 同 anchor)。"""
    canvas = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    margin = 4
    anchor_tex_y = 0.9 * TEX
    ground_y = canvas_h - margin

    def blit(path, ground_row):
        img = Image.open(path).convert('RGBA')
        w = max(1, int(round(TEX * scale)))
        img = img.resize((w, w), Image.LANCZOS)
        arr = np.asarray(img).astype(np.float64)
        sy = ground_y - (ground_row - anchor_tex_y) * scale
        y_bottom = sy + (TEX - ground_row) * scale
        left = int(round(canvas_w / 2 - 512 * scale))
        top = int(round(y_bottom - w))
        dx0, dy0 = max(0, left), max(0, top)
        dx1, dy1 = min(canvas_w, left + w), min(canvas_h, top + w)
        if dx1 <= dx0 or dy1 <= dy0:
            return
        sub = arr[dy0 - top:dy0 - top + (dy1 - dy0), dx0 - left:dx0 - left + (dx1 - dx0)]
        layer = Image.fromarray(np.clip(sub, 0, 255).astype(np.uint8), 'RGBA')
        canvas.alpha_composite(layer, (dx0, dy0))

    for p in prop_paths:
        blit(p, floor_tex_y)
    blit(char_path, char_ground)
    bg = Image.new('RGBA', (canvas_w, canvas_h), (250, 250, 252, 255))
    for y in range(0, canvas_h, 16):
        for x in range(0, canvas_w, 16):
            if ((x // 16) + (y // 16)) % 2 == 0:
                bg.paste((232, 235, 242, 255), (x, y, x + 16, y + 16))
    bg.alpha_composite(canvas)
    return bg


def main():
    os.makedirs(OUT, exist_ok=True)
    base = to_np(load(SIT))
    donor_np = to_np(load(DONOR))
    rigL = build_arm(base, 'L')
    rigR = build_arm(base, 'R')
    print('L 关节', rigL['S'], rigL['E'], rigL['W'], '手质心', [round(v, 1) for v in rigL['hand_c']])
    print('R 关节', rigR['S'], rigR['E'], rigR['W'], '手质心', [round(v, 1) for v in rigR['hand_c']])
    print('L 掩膜', {k: int(rigL[k].sum()) for k in ('arm', 'upper', 'fore', 'hand')})
    print('R 掩膜', {k: int(rigR[k].sum()) for k in ('arm', 'upper', 'fore', 'hand')})

    if '--sweep' in sys.argv:
        return sweep(base, rigL, rigR, donor_np)

    report = {'round': 'R170', 'action': 'eat_fruit',
              'scheme': '双手捧果在胸前 + 低头张嘴咬一口 (第 4 轮方案)',
              'boxes': {'face': list(FACE_BOX), 'mouth': list(MOUTH_BOX),
                        'eye_band': list(EYE_BAND)},
              'frames': []}
    frames = []
    base_skin_dil = dilate(skin_mask_of(base), 3)
    for i, spec in enumerate(FRAMES):
        out, angles, got, n_filled, fing_world = build_frame(base, rigL, rigR, spec, donor_np)
        path = os.path.join(OUT, spec['name'] + '.png')
        to_im(out).save(path)
        arr = out
        v = verify_frame(arr, base, rigL, angles, None, FACE_SKIN_BOX,
                         finger_world=fing_world, base_skin_dil=base_skin_dil)
        got_final = got
        dev = float(np.hypot(got_final[0] - spec['apple'][0],
                              got_final[1] - spec['apple'][1]))
        rec = dict(file=spec['name'] + '.png', index=i,
                   angles=dict(a_s=round(angles[0], 2), a_e=round(angles[1], 2),
                               a_w=round(angles[2], 2)),
                   apple_center=[round(got_final[0], 1), round(got_final[1], 1)],
                   apple_target=list(spec['apple']),
                   apple_deviation_px=round(dev, 2),
                   fdir=[round(vv, 3) for vv in spec['fdir']],
                   head=dict(rotate=spec['head'][0], dy=spec['head'][1], scale=spec['head'][2]),
                   face=spec['face'], mouth=spec['mouth'],
                   hole_filled_px=n_filled, note=spec['note'])
        rec.update(v)
        report['frames'].append(rec)
        frames.append((spec, out, angles, got_final, v, dev))
        print(f"  ✅ {spec['name']:16s} a=({angles[0]:7.1f},{angles[1]:7.1f},{angles[2]:7.1f})"
              f" 苹果=({got_final[0]:6.1f},{got_final[1]:6.1f}) 偏={dev:4.1f}"
              f" 到嘴={v['apple_to_mouth_dist']} 到手={v['apple_to_hand_dist']}"
              f" 压嘴={v['apple_mouth_overlap_px']}/{v['hand_apple_cover_mouth_px']}"
              f" 压脸={v['apple_face_overlap_px']} 块={v['solid_block_count']}"
              f" 主块={v['apple_in_main_block_ratio']} 抬手={v['raised_hand_px']}"
              f" 遮挡={v.get('apple_occluded_by_finger_px')} 破洞={v['thigh_hole_px']}")

    report['manifest_suggestion'] = {
        'action': 'eat_fruit',
        'action_library.actions.eat_fruit.frames': [
            'character_R156/eat_fruit_%d.png' % i for i in range(5)],
        'action_library.actions.eat_fruit.anchor': 'sit',
        'action_library.actions.eat_fruit.ground_tex_y': 1001,
        'props.scenes.eat_fruit.floor_tex_y': 1001,
        'props.scenes.eat_fruit.back': ['prop_stool', 'prop_fruit_table'],
        'props.scenes.eat_fruit.front': [],
        'props.library.prop_stool.file': 'character_R156/prop_stool.png',
        'props.library.prop_fruit_table.file': 'character_R156/prop_fruit_table.png',
        'note': 'manifest 已由父 agent 侧写入, 这里给出建议值供比对',
    }
    with open(os.path.join(OUT, 'eat_fruit_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ---------------- 对照图 + 真实尺寸场景图 + 交付拷贝 ----------------
    deliver(report, frames, base)
    return 0


DELIVER_DIR = '/Users/musk123/Downloads/minimax工作文件夹/图文工作/R170_吃水果'


def deliver(report, frames, base):
    import shutil
    os.makedirs(DELIVER_DIR, exist_ok=True)
    # 1) 逐帧对照图
    tiles = []
    for spec, out, angles, got, v, dev in frames:
        im = to_im(out)
        bg = Image.new('RGBA', im.size, (248, 249, 252, 255))
        bg.alpha_composite(im)
        d = ImageDraw.Draw(bg)
        d.rectangle([0, 0, 1023, 26], fill=(255, 255, 255, 210))
        d.text((8, 6), f"{spec['name']}  a=({angles[0]:.0f},{angles[1]:.0f},{angles[2]:.0f})"
                       f"  苹果=({got[0]:.0f},{got[1]:.0f})  上臂={v['upper_px']}px",
               fill=(20, 20, 40))
        tiles.append(bg)
    sheet = Image.new('RGB', (1024 * len(tiles), 1024), (255, 255, 255))
    for i, t in enumerate(tiles):
        sheet.paste(t.convert('RGB'), (i * 1024, 0))
    sheet = sheet.resize((sheet.width // 4, sheet.height // 4), Image.LANCZOS)
    sheet.save('/tmp/r170_eat_sheet.png')
    sheet.save(os.path.join(DELIVER_DIR, 'r170_eat_sheet.png'))
    print('  🖼  对照图 /tmp/r170_eat_sheet.png +', os.path.join(DELIVER_DIR, 'r170_eat_sheet.png'))

    # 2) 真实尺寸场景图 (与运行时同一套 scale / anchor)
    _sp = _mod('sc45', os.path.join(HERE, '45_R165_scene_preview.py'))
    manifest = json.load(open(_sp.MANIFEST, encoding='utf-8'))
    stool = os.path.join(OUT, 'prop_stool.png')
    table = os.path.join(OUT, 'prop_fruit_table.png')
    for (w, h) in ((200, 240), (256, 256)):
        scale = _sp.build_scale(manifest, w, h)
        strip = Image.new('RGB', (w * len(frames), h), (255, 255, 255))
        for i, (spec, out, angles, got, v, dev) in enumerate(frames):
            ch = os.path.join(OUT, spec['name'] + '.png')
            sc = compose_scene(ch, [stool, table], scale, w, h, 990, 1000)
            strip.paste(sc.convert('RGB'), (i * w, 0))
            sc.convert('RGB').save(os.path.join(DELIVER_DIR, f'scene_{spec["name"]}_{w}x{h}.png'))
        strip.save(os.path.join(DELIVER_DIR, f'scene_strip_{w}x{h}.png'))
        strip.save(f'/tmp/r170_scene_strip_{w}x{h}.png')
        print(f'  🖼  场景条 {w}x{h}  scale={scale:.4f}  → {DELIVER_DIR}/scene_strip_{w}x{h}.png')

    # 3) 拷贝帧与道具
    for spec, *_ in frames:
        shutil.copy(os.path.join(OUT, spec['name'] + '.png'),
                    os.path.join(DELIVER_DIR, spec['name'] + '.png'))
    for p in ('prop_stool.png', 'prop_fruit_table.png'):
        shutil.copy(os.path.join(OUT, p), os.path.join(DELIVER_DIR, p))
    shutil.copy(os.path.join(OUT, 'eat_fruit_report.json'),
                os.path.join(DELIVER_DIR, 'eat_fruit_report.json'))
    print('  📦 交付目录:', DELIVER_DIR)


if __name__ == '__main__':
    sys.exit(main())
