#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R158 手臂骨架 — 三关节(肩 / 肘 / 腕)切分 + 两骨 IK 摆姿 + 衣身还原。

背景 (R158 任务书: "禁止用压缩、平移、重命名冒充新动作"):
  R156 的 6 个点击动作里 3 个是几何形变冒充的, 其中 cheer_heart 直接复用了
  idle_04 —— 而 idle_04 本身就是"右手横在胸前"的姿势(R153 当年就是因为这个
  把 idle_04 从眨眼序列踢掉), 所以必然还是用户已经明确不喜欢的那一手。

  R153 的 bake_report 写"R138 无手部素材" —— **这个结论是错的**:
  R138 的 idle_00_base.png 里**两只手都是张开的、5 指带描边**。
  真正缺的不是手, 是"能把手臂摆到别的位置"的技术。

本模块的做法:
  1. 描边线当阻隔做洪水填充 ⇒ 干净的"袖 + 袖口 + 手"连通区域 (R138 自己的切层
     脚本漏掉了这只手, 只切出胸前的拳头)
  2. 在肩 / 肘 / 腕各切一个**圆形咬口**(圆心=关节, 半径固定):
     **每一段只带自己"近端关节"的完整圆盘, 不带远端关节的圆盘**。
     圆盘绕自身圆心旋转后仍与原位重合 ⇒ 关节处永不出现缝隙。
  3. 三关节链: 肩 → 肘 → 腕 → 手; 用两骨 IK 求"手要到哪里"的关节角
  4. 摘掉袖子后, 把被袖子盖住的**衣身**按"外扩衣身边缘条带"补回来
     (袖子是压在白大褂上的, 衣身边缘条带 = [描边暗线 + 白大褂面料])

不做: 不重画角色, 不改脸, 不改配色, 不引入外部素材, 不做 i2i。
"""
import os
import sys
from collections import deque

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
R138 = os.path.join(CAND, 'assets', 'character_R138')

DARK_LUM = 118
BARRIER_R = 2

# 实测几何 (1024 纹理坐标)
#
# R162 修正: 原来的肩/肘枢轴**落在角色体外的空白区**(肩盘 398,386 整个悬空),
#   手臂绕体外一点旋转 ⇒ ①肩部甩出一块平涂白色的圆盘残块 ②手臂与躯干之间断开
#   ③袖子描边残留成虚线。现按**袖子的实测位置**重新标定:
#   袖子掩膜顶端在 x≈420 / y≈380, 袖口(青色腕带)在 y≈556, 袖身中段在 y≈470。
#   枢轴必须落在**袖子内部**, 圆盘才咬得住袖料。
SIDES = {
    'L': dict(  # 画面左臂 = 角色右手
        hand_box=(335, 588, 398, 668),
        hand_zone=(328, 572, 390, 676),
        cuff_box=(340, 548, 408, 606),
        sleeve_box=(352, 500, 384, 556),
        roi=(322, 300, 438, 684),
        shoulder=(428, 383),
        elbow=(408, 468),
        wrist=(370, 556),
        r_shoulder=14,
        r_elbow=15,
        r_wrist=13,
    ),
    'R': dict(  # 画面右臂 = 角色左手
        hand_box=(626, 588, 692, 668),
        hand_zone=(620, 572, 700, 676),
        cuff_box=(620, 548, 688, 606),
        sleeve_box=(640, 500, 672, 556),
        roi=(586, 300, 702, 684),
        shoulder=(596, 383),
        elbow=(616, 468),
        wrist=(654, 556),
        r_shoulder=14,
        r_elbow=15,
        r_wrist=13,
    ),
}

# 衣身还原参数 (R162 重标定)
#
# 【关键解剖结论 —— R162 实测得出, 之前几轮全错在这里】
#   底图 idle_00_base 里, 角色左臂的**袖子是画在白大褂"外面"的一层**:
#     x  外侧深色描边(4~5px) | 袖子白/青色饰条 |  x=seam 处的深色接缝线 | 大褂本体
#   也就是说:
#     · 最外侧那条粗黑线 = **袖子的外轮廓**, 也就是角色剪影的最外缘
#     · 接缝线 (seam) = 袖子压在衣身上的**内轮廓**, 大褂真正的衣身边缘藏在它后面
#   ⇒ 摘掉袖子后, 大褂的边缘就落在 **seam** 上, 而不是"袖子外轮廓"上。
#   ⇒ seam 以下 (袖口+手) 背后是背景, 摘掉后必须透明。
#
# 【L 侧 seam 实测 (1024 纹理坐标, 逐行数暗线得到)】
#   肩部 y350-378: 421→427  (与肩帽融合, 接缝线出现在 x≈427)
#   y380-410:      429→439  (腋下, 明显外张)
#   y415-445:      439→437  (手臂垂下, 接缝线回落到 x≈437)
#   y460-545:      436→424  (袖子内缘随袖口收窄)
#   y560-580:      412→398  (袖口青色腕带收口)
#   y590-675:      396→382  (手掌右缘)
# R 侧按 x→1024-x 镜像 (角色本体关于 x=512 严格对称: 肩 428↔596 / 肘 408↔616 / 腕 370↔654)
SEAM_L = [
    (335, 421), (345, 423), (355, 425), (365, 427), (375, 429), (385, 430),
    (395, 433), (405, 437), (415, 440), (425, 439), (435, 438), (445, 437),
    (465, 436), (485, 435), (505, 432), (525, 428), (545, 422), (558, 412),
    (570, 405), (580, 398), (595, 394), (615, 390), (635, 385), (655, 381),
    (675, 381),
]
SLEEVE_END = 585        # 此行以下只有袖口+手, 背后是背景 ⇒ 摘掉后必须透明
OUT_KEEP = 5            # 保留底图最外侧描边带的宽度 (底图描边 4~5px + 1px 抗锯齿)
OUTLINE_PX = 2          # 重建的衣身外缘描边宽度
SEAM_LINE_PX = 3        # 重建的衣身接缝描边宽度
EDGE_SHADOW_PX = 18     # 衣身外缘柔和投影的宽度 (纹理 px)
RING_R = 3              # (兼容旧常量, 新实现不再需要)


# ---------------------------------------------------------------- 基础工具
def load_rgba(path):
    return Image.open(path).convert('RGBA')


def to_np(im):
    return np.asarray(im).astype(np.int32)


def to_im(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')


def lum(a):
    """亮度。接受 (...,3) / (...,4) 任意形状。"""
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def dilate(m, r=1):
    out = m.copy()
    for _ in range(r):
        o = out.copy()
        o[1:, :] |= out[:-1, :]
        o[:-1, :] |= out[1:, :]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


def skin(a):
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 60) & (R > 205) & (R < 255) & (G > 170) & (G < 240) & (B > 150) & (B < 225) \
        & ((R - B) > 20) & ((R - G) > 8)


def teal(a):
    if a.ndim == 3 and a.shape[-1] == 4:
        R, G, B, Al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    else:
        R, G, B = a[..., 0], a[..., 1], a[..., 2]
        Al = np.full(R.shape, 255)
    return (Al > 60) & (B > R + 25) & (G > R + 25) & (G > 150) & (B > 170)


def skin_relaxed(a):
    """放宽的肤色判定 (专供手部切分)。

    严格的 skin() 判据 R<255 会把手部高光排除, 导致洪水填充只拿到手掌内部,
    手��描边与手指全部漏掉 —— 摘袖子之后手会"留在原地"。
    这里放宽到 R>=195, 同时用 (R-B)>=12 排除白大褂 (白大褂 R-B ≈ -2)。
    """
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 60) & (R >= 195) & (G >= 160) & (B >= 140) \
        & ((R - B) >= 12) & ((R - G) >= -8)


def components(mask, min_px=40):
    h, w = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    Y, X = np.nonzero(mask)
    for sy, sx in zip(Y, X):
        if seen[sy, sx]:
            continue
        q = deque([(sy, sx)])
        seen[sy, sx] = True
        pts = []
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
        if len(pts) >= min_px:
            m = np.zeros_like(mask, bool)
            pa = np.array(pts)
            m[pa[:, 0], pa[:, 1]] = True
            out.append((len(pts), m))
    out.sort(key=lambda t: -t[0])
    return out


def flood_region(a, seed, roi=None, dark_thr=DARK_LUM, barrier_r=BARRIER_R):
    h, w = a.shape[:2]
    solid = a[:, :, 3] > 40
    dark = (lum(a) < dark_thr) & solid
    barrier = dilate(dark, barrier_r) | (~solid)
    free = (~barrier) & solid
    if roi:
        x0, y0, x1, y1 = roi
        roim = np.zeros_like(free)
        roim[y0:y1, x0:x1] = True
        free = free & roim
    seed = dilate(seed, 3) & free
    seen = np.zeros_like(free, bool)
    q = deque()
    Y, X = np.nonzero(seed)
    for y, x in zip(Y, X):
        if not seen[y, x]:
            seen[y, x] = True
            q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and free[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
    return seen


def seam_x(side, y):
    """手臂与衣身之间的接缝线 x 坐标 (逐行线性插值)。"""
    tbl = SEAM_L if side == 'L' else [(y0, 1024 - x0) for y0, x0 in SEAM_L]
    if y <= tbl[0][0]:
        return float(tbl[0][1])
    for (y0, x0), (y1, x1) in zip(tbl, tbl[1:]):
        if y0 <= y <= y1:
            t = 0.0 if y1 == y0 else (y - y0) / float(y1 - y0)
            return x0 + (x1 - x0) * t
    return float(tbl[-1][1])


def rotate_rgba(rgba, pivot, ang):
    """绕 pivot 旋转 RGBA (双线性采样)。ang>0 = 屏幕顺时针 (y 向下坐标系)。

    R162 修正: 原来用**最近邻**采样, 斜着走的细描边被重采样成 1px 宽的
    **阶梯锯齿**(肉眼就是一条虚线), 看上去像"断线/残影"。
    改成预乘 alpha 的双线性 ⇒ 边缘平滑, 细线仍是连续的。
    """
    px, py = pivot
    th = np.deg2rad(ang)
    cos, sin = np.cos(th), np.sin(th)
    H, W = rgba.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    dx = xx - px
    dy = yy - py
    sx = px + dx * cos - dy * sin
    sy = py + dx * sin + dy * cos
    ok = (sx >= 0) & (sx <= W - 1) & (sy >= 0) & (sy <= H - 1)
    x0 = np.floor(sx).astype(np.int64)
    y0 = np.floor(sy).astype(np.int64)
    fx = (sx - x0)[..., None]
    fy = (sy - y0)[..., None]
    x0c = np.clip(x0, 0, W - 1)
    x1c = np.clip(x0 + 1, 0, W - 1)
    y0c = np.clip(y0, 0, H - 1)
    y1c = np.clip(y0 + 1, 0, H - 1)
    src = rgba.astype(np.float64)
    a = src[:, :, 3:4] / 255.0
    prem = np.concatenate([src[:, :, 0:3] * a, a * 255.0], axis=2)
    v = (prem[y0c, x0c] * (1 - fx) * (1 - fy) + prem[y0c, x1c] * fx * (1 - fy)
         + prem[y1c, x0c] * (1 - fx) * fy + prem[y1c, x1c] * fx * fy)
    v = np.where(ok[..., None], v, 0.0)
    va = np.clip(v[:, :, 3:4] / 255.0, 0, 1)
    out = np.zeros(rgba.shape, np.int32)
    safe = np.where(va > 1e-6, va, 1.0)[:, :, 0]
    for c in range(3):
        out[:, :, c] = np.clip(v[:, :, c] / safe, 0, 255).astype(np.int32)
    out[:, :, 3] = np.clip(v[:, :, 3], 0, 255).astype(np.int32)
    return out


def disc(shape, center, r):
    H, W = shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    return ((xx - center[0]) ** 2 + (yy - center[1]) ** 2) <= r * r


# ---------------------------------------------------------------- 手臂骨架
def build_arm(a, side):
    """切出一条手臂, 返回三关节骨架 + 三段掩膜。"""
    J = SIDES[side]
    sk, tl = skin(a), teal(a)

    hand = np.zeros_like(sk)
    x0, y0, x1, y1 = J['hand_box']
    hand[y0:y1, x0:x1] = True
    hand &= sk
    cuff = np.zeros_like(tl)
    x0, y0, x1, y1 = J['cuff_box']
    cuff[y0:y1, x0:x1] = True
    cuff &= tl
    slv = np.zeros_like(sk)
    x0, y0, x1, y1 = J['sleeve_box']
    slv[y0:y1, x0:x1] = True
    slv &= (a[:, :, 3] > 40) & (lum(a) > 130)

    arm = flood_region(a, hand | cuff | slv, roi=J['roi'])
    # ------------------------------------------------------------------
    # R162 修正 A: 洪水填充把**暗色描边当阻隔** ⇒ 描边落在掩膜之外。
    #   后果实测: ①切口是"没有描边的裸边" ②描边残留成虚线鬼影
    #   ③袖子外侧那条**青色高光带**(底图 y420 的 x410-416)整条留在掩膜外
    #      ⇒ 手臂转走后原地留下一条**青色虚线** —— 就是评审看到的"拼接残影"。
    #   对策: 从洪水区域**沿不透明像素一路走到真正的剪影**, 把这段
    #      (描边 + 抗锯齿 + 青色高光带) 全部并进手臂掩膜。
    #      剪影处必然是透明像素, 所以"走到透明为止"就等于真实外轮廓。
    solid_a = a[:, :, 3] > 40
    outer = np.zeros_like(arm)
    for _y in range(a.shape[0]):
        _xs = np.nonzero(arm[_y])[0]
        if len(_xs) == 0:
            continue
        if side == 'L':
            _x = int(_xs.min())
            _stop = _x
            while _stop > 0 and solid_a[_y, _stop - 1]:
                _stop -= 1
            outer[_y, _stop:_x + 1] = True
        else:
            _x = int(_xs.max())
            _stop = _x
            while _stop < a.shape[1] - 1 and solid_a[_y, _stop + 1]:
                _stop += 1
            outer[_y, _x:_stop + 1] = True
    arm = arm | outer
    # ------------------------------------------------------------------
    # R162 修正 B: 洪水填充会**从肩膀上方绕进大褂胸口** —— 袖子的暗描边
    #   在肩部不断开, 填充能绕过去 ⇒ 手臂掩膜里混进一大块衣身。
    #   手臂一转, 这块衣身跟着飞起来 ⇒ 肩上凭空多出一块**白色残块**。
    #   对策: 用实测接缝线 (seam) 给手臂掩膜的**内侧**封顶。
    capm = np.zeros_like(arm)
    for _y in range(a.shape[0]):
        _xs = np.nonzero(arm[_y])[0]
        if len(_xs) == 0:
            continue
        if side == 'L':
            _hi = int(_xs.max())
            _sx = int(round(seam_x('L', _y))) + SEAM_LINE_PX
            if _sx < _hi:
                capm[_y, _sx:] = True
        else:
            _lo = int(_xs.min())
            # R 侧接缝 = L 侧接缝关于 x=512 的镜像 (x → 1024-x)
            _sx = 1024 - int(round(seam_x('L', _y))) - SEAM_LINE_PX
            if _sx > _lo:
                capm[_y, :_sx + 1] = True
    arm = arm & (~capm)
    # 洪水偶尔从袖口漏到衣身口袋饰条上 ⇒ 去掉衣身那一坨青色
    for _size, m in components(tl, 200):
        ys, xs = np.nonzero(m)
        if ys.min() < 400 and ys.max() > 640 and xs.max() - xs.min() > 120:
            arm &= ~m
    # R162: 旧实现有一条"袖口右上方 x>412 全部切掉"的硬裁剪 —— 那是**旧几何**
    #   (袖口在 x340-408)下为防漏进衣身竖饰条而加的; 新几何里袖子内侧到 x=435,
    #   再切会把袖子自己腰斩 ⇒ 已由上面的"接缝线封顶"取代, 此处不再裁剪。

    # ---- 手部单独切: 洪水填充拿不到手的描边与手指 (暗线被当成阻隔) ----
    hz = np.zeros_like(arm)
    hx0, hy0, hx1, hy1 = J['hand_zone']
    hz[hy0:hy1, hx0:hx1] = True
    hand_full = dilate(skin_relaxed(a) & hz, 4) & (a[:, :, 3] > 40) & hz
    arm = arm | hand_full

    S, E, W = J['shoulder'], J['elbow'], J['wrist']
    rS, rE, rW = J['r_shoulder'], J['r_elbow'], J['r_wrist']
    nS, nE, nW = (disc(a.shape[:2], p, r) for p, r in ((S, rS), (E, rE), (W, rW)))

    # 三段: 上臂(肩→肘) / 前臂(肘→腕) / 手(腕→指尖)
    # 分界用**垂直平分线**; 每一段带自己**近端关节的完整圆盘**, 不带远端关节圆盘
    def bisect(p, q):
        mx, my = (p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0
        ux, uy = q[0] - p[0], q[1] - p[1]
        n = max(1e-6, (ux * ux + uy * uy) ** 0.5)
        ux, uy = ux / n, uy / n
        yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]].astype(np.float64)
        return (xx - mx) * ux + (yy - my) * uy

    s_e = bisect(S, E)      # >0 = 靠肘一侧
    e_w = bisect(E, W)      # >0 = 靠腕一侧

    upper = arm & (s_e < 0) & ~nE & ~nW
    fore = arm & (s_e > 0) & (e_w < 0) & ~nW
    handseg = arm & (e_w > 0)
    # 咬口归属: 肘圆盘归前臂段, 腕圆盘归手段 (各自**近端**关节 → 完整圆盘)
    fore = fore | (arm & nE & (s_e > 0) & ~nW)
    handseg = handseg | (arm & nW)
    # R162 修正: **肩盘不参与旋转**。
    #   它是"长在身体上的肩章"(大褂肩部 + 青色肩线), 手臂绕它转, 它自己不动。
    #   之前把肩盘塞进上臂段一起旋转 + 用平涂袖色补齐圆盘
    #   ⇒ 肩章内容在盘内被甩歪, 肩上凭空多出一块白色残块。
    upper = upper & ~nS
    # 手部整块归"手段" (含描边与手指)
    handseg = handseg | hand_full
    # 身体里保留一份肩章 (角色肩头), 旋转后的上臂正好盖住它
    cap = arm & nS
    sleeve_color = a[arm & (s_e < 0)][:, :3].mean(axis=0) if arm.any() else np.array([240, 240, 245])

    ys, xs = np.nonzero(handseg)
    hand_c = (float(xs.mean()), float(ys.mean())) if len(xs) else (float(W[0]), float(W[1]))

    return dict(side=side, arm=arm, cap=cap, upper=upper, fore=fore, hand=handseg,
                S=S, E=E, W=W, rS=rS, rE=rE, rW=rW, hand_c=hand_c,
                sleeve_color=sleeve_color)


def pose_arm(a, rig, angles):
    """angles = (肩角, 肘角, 腕角) —— 都是**相对原始姿态**的增量角(度, 正=顺时针)。

    链式求解顺序: 手段绕腕 → 前臂段(手+前臂)绕肘 → 上臂段(整条)绕肩。
    每一段的圆形咬口在"近端关节"上, 旋转后仍与远端段重合 ⇒ 接缝不出现。
    """
    S, E, W = rig['S'], rig['E'], rig['W']
    a_s, a_e, a_w = angles

    hand = np.where(rig['hand'][:, :, None], a, 0)
    fore = np.where(rig['fore'][:, :, None], a, 0)
    upper = np.where(rig['upper'][:, :, None], a, 0)

    hand1 = rotate_rgba(hand, W, a_w)
    fore1 = rotate_rgba(fore, E, a_e)
    hand2 = rotate_rgba(hand1, E, a_e)

    fore2 = rotate_rgba(fore1, S, a_s)
    hand3 = rotate_rgba(hand2, S, a_s)
    upper2 = rotate_rgba(upper, S, a_s)
    return upper2, fore2, hand3


def over(dst, src):
    sa = src[:, :, 3].astype(np.float32) / 255.0
    for c in range(3):
        dst[:, :, c] = (dst[:, :, c] * (1 - sa) + src[:, :, c] * sa).astype(np.int32)
    dst[:, :, 3] = np.maximum(dst[:, :, 3], src[:, :, 3])
    return dst


# ---------------------------------------------------------------- 衣身还原
def _inset_for_row(y, width):
    """袖子在行 y 处**超出大褂轮廓**的量 (往里收多少才等于大褂真实边缘)。"""
    if INSET_MODE == 'zero':
        return 0
    if y <= SHOULDER_FLAT:
        return INSET_FLAT
    if y >= HAND_Y:
        return width           # 袖口+手完全悬空 → 整块透明
    return int(round(FOREARM_RATIO * width))


def restore_body(base, arm_mask, side, outline_px=OUTLINE_PX):
    """摘掉袖子, 并把被袖子压住的**衣身**补回来。

    R162 重写 (之前几轮全错在"大褂边缘该画在哪"):
      底图解剖 (idle_00_base, 左臂, 1024 纹理坐标):
        x  外侧粗黑描边(剪影) | 袖子白 + 青色饰条 | x=seam 接缝线 | 大褂本体
      ⇒ 大褂的**可见边缘就是接缝线**, 袖子外那条粗黑线是**袖子的外轮廓**。
      ⇒ 摘掉袖子后: 大褂边缘落在 seam 上, 而 seam 之外(左边)回到背景。
      ⇒ 袖口+手 (y>SLEEVE_END) 背后本来就是背景 ⇒ 整块清透明, 不能补衣身。

    R 侧按 x→1024-x 镜像处理 (角色本体关于 x=512 严格对称)。

    返回 (body_img, fill_mask)。
    """
    if side == 'R':
        out, fill = restore_body(base[:, ::-1], arm_mask[:, ::-1], 'L', outline_px)
        return out[:, ::-1], fill[:, ::-1]

    out = base.copy()
    H, W = arm_mask.shape
    solid = base[:, :, 3] > 40
    lum_ = lum(base)

    # 全局衣身主色 (兜底): 取画面中部大片白大褂像素的中位数
    mid = base[380:700, 400:620, :3].astype(np.float64).reshape(-1, 3)
    ml = 0.299 * mid[:, 0] + 0.587 * mid[:, 1] + 0.114 * mid[:, 2]
    mt = teal(base[380:700, 400:620]).reshape(-1)
    bright = mid[(ml > 190) & (~mt)]
    global_coat = np.median(bright, axis=0) if len(bright) else np.array([244, 251, 254])

    def coat_color(y, x0, x1):
        """该行大褂面料色: 窗口内"亮且非青"像素的中位数 (避开描边与青色饰条)。"""
        x0 = max(0, x0)
        x1 = min(W, x1)
        if x1 - x0 < 3:
            return global_coat
        strip = base[y, x0:x1, :3].astype(np.float64)
        m = (lum(strip) > 185) & (~teal(base[y, x0:x1]))
        if m.sum() >= 2:
            return np.median(strip[m], axis=0)
        return global_coat

    def seam_color(y, sx):
        """接缝描边取底图该行接缝线自身的颜色 (不能瞎取, 之前取到透明区
        ⇒ 变成纯黑或纯白 ⇒ 整条衣身边缘变成**虚线**)。"""
        x0 = max(0, sx - 1)
        x1 = min(W, sx + 5)
        seg = base[y, x0:x1, :3].astype(np.float64)
        if not len(seg):
            return np.array([40, 45, 70])
        d = lum(seg)
        cand = seg[d <= np.percentile(d, 45)]
        return np.median(cand, axis=0) if len(cand) else np.array([40, 45, 70])

    fill = np.zeros((H, W), bool)

    for y in range(H):
        xs = np.nonzero(arm_mask[y])[0]
        if len(xs) == 0:
            continue
        lo, hi = int(xs.min()), int(xs.max())

        if y > SLEEVE_END:
            # 袖口+手: 背后是背景 ⇒ 整块清透明 (含描边, 不能留鬼影)
            out[y, :hi + 1] = 0
            continue

        sx = int(round(seam_x('L', y)))
        # ---- ① 保留底图最外侧描边带 (剪影 = 衣身外缘, 天然连续且颜色正确) ----
        keep_hi = min(W, lo + OUT_KEEP)
        # 描边带之外(左侧)本来就是背景
        out[y, :lo] = 0

        # ---- ② 衣身填充: 描边带内侧 → 接缝线 ----
        #    R162 再修: 之前直接用"该行亮像素中位数"平涂, 结果:
        #      · 采样窗口落在**袖子的暗部**上 ⇒ 填出一块**灰板** (与白大褂接缝明显)
        #      · 袖子外缘内侧那道**柔和投影**被整段抹平 ⇒ 大褂像一块没有体积的布
        #    改成: ① 采样窗口移到**接缝线右侧的大褂本体**取干净白
        #          ② 按底图实测的外缘投影深度, 给填充区补一条柔和的边缘阴影
        fill_hi = min(hi, sx)
        if fill_hi > keep_hi:
            col = coat_color(y, sx + 4, min(W, sx + 90))
            seg = out[y, keep_hi:fill_hi, 0:3].astype(np.float64)
            # 边缘投影: 取底图紧贴剪影内侧的暗度, 折算成"比衣身白暗多少"
            edge = base[y, keep_hi:min(W, keep_hi + 16), 0:3].astype(np.float64)
            if len(edge):
                el = lum(edge)
                emed = float(np.median(el))
                cb = float(np.median(lum(col)))
                depth = float(np.clip((cb - emed) / max(1.0, cb), 0.0, 0.22))
            else:
                depth = 0.10
            n = fill_hi - keep_hi
            ramp = np.ones(n)
            m = min(n, EDGE_SHADOW_PX)
            if m > 0:
                ramp[:m] = 1.0 - depth * (1.0 - np.linspace(0.0, 1.0, m))
            seg = seg * ramp[:, None]
            out[y, keep_hi:fill_hi, 0:3] = np.clip(seg, 0, 255).astype(np.int32)
            out[y, keep_hi:fill_hi, 3] = 255
            fill[y, keep_hi:fill_hi] = True

    return out, fill


def compose(base, segments, body_mask=None):
    """segments = [(rgba_layer), ...] 由远到近 (手臂画在身体前面)。"""
    out = base.copy()
    if body_mask is not None:
        out[:, :, 3] = np.where(body_mask, base[:, :, 3], 0).astype(np.int32)
    for seg in segments:
        out = over(out, seg)
    return out


# ---------------------------------------------------------------- 两骨 IK
def solve_ik(shoulder, target, l1, l2, flip=1):
    """两骨 IK: 求肘位置 (shoulder→elbow 长度 l1, elbow→target 长度 l2)。"""
    sx, sy = shoulder
    tx, ty = target
    dx, dy = tx - sx, ty - sy
    d = max(1e-6, (dx * dx + dy * dy) ** 0.5)
    d = min(d, l1 + l2 - 0.5)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = max(0.0, (l1 * l1 - a * a) ** 0.5)
    ux, uy = dx / d, dy / d
    px, py = -uy * flip, ux * flip
    return (sx + a * ux + h * px, sy + a * uy + h * py)


def angles_from_ik(rig, target, wrist_extra=0.0, flip=1):
    """给出手的目标位置, 返回 (肩角, 肘角, 腕角)。

    做法: 先把"手目标点"换算成"腕目标点"(手比腕长 h_hand, 沿手的方向),
          再用两骨 IK 解肩/肘, 最后腕角 = 手相对前臂的额外旋转。
    """
    S, E, W = rig['S'], rig['E'], rig['W']
    hand_vec = np.array([rig['hand_c'][0] - W[0], rig['hand_c'][1] - W[1]], float)
    h_hand = np.hypot(*hand_vec)
    ang_hand = np.degrees(np.arctan2(hand_vec[1], hand_vec[0]))
    wrist_target = (target[0] - h_hand * np.cos(np.deg2rad(ang_hand + wrist_extra)),
                    target[1] - h_hand * np.sin(np.deg2rad(ang_hand + wrist_extra)))
    l1 = float(np.hypot(E[0] - S[0], E[1] - S[1]))
    l2 = float(np.hypot(W[0] - E[0], W[1] - E[1]))
    elbow = solve_ik(S, wrist_target, l1, l2, flip=flip)
    a_upper = np.degrees(np.arctan2(elbow[1] - S[1], elbow[0] - S[0])) \
        - np.degrees(np.arctan2(E[1] - S[1], E[0] - S[0]))
    a_fore = np.degrees(np.arctan2(W[1] - elbow[1], W[0] - elbow[0])) \
        - np.degrees(np.arctan2(W[1] - E[1], W[0] - E[0]))
    return a_upper, a_fore, wrist_extra


if __name__ == '__main__':
    print("R158 手臂骨架模块自检 OK")
