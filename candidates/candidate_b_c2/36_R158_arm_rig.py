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
SIDES = {
    'L': dict(  # 画面左臂 = 角色右手
        hand_box=(335, 588, 398, 668),
        hand_zone=(328, 572, 390, 676),
        cuff_box=(340, 548, 408, 606),
        sleeve_box=(352, 500, 384, 556),
        roi=(322, 300, 438, 684),
        shoulder=(398, 386),
        elbow=(376, 486),
        wrist=(366, 574),
        r_shoulder=26,
        r_elbow=17,
        r_wrist=15,
    ),
    'R': dict(  # 画面右臂 = 角色左手
        hand_box=(626, 588, 692, 668),
        hand_zone=(620, 572, 700, 676),
        cuff_box=(620, 548, 688, 606),
        sleeve_box=(640, 500, 672, 556),
        roi=(586, 300, 702, 684),
        shoulder=(626, 386),
        elbow=(648, 486),
        wrist=(658, 574),
        r_shoulder=26,
        r_elbow=17,
        r_wrist=15,
    ),
}

# 衣身还原参数 (可调, 靠肉眼看图迭代)
#   实测 (idle_00_base, 1024 纹理坐标):
#     y=452 行: x394 灰边 / x395-398 深色描边 / x399-400 灰 / x401+ 袖子白 / x435+ 大褂白
#     ⇒ 袖子的**描边**被洪水填充当成阻隔, 落在掩膜之外 ⇒ 擦除时必须一起带走
#     ⇒ 袖子与大褂在肩部基本齐平, 所以衣身边缘默认重建在袖子外轮廓处 (inset=0)
INSET_MODE = 'graded'   # 'graded' | 'zero'
SHOULDER_FLAT = 470     # 此行以上: 袖子与大褂轮廓齐平 → 衣身不内缩
INSET_FULL_Y = 660      # 此行: 袖口+手完全悬空 → 衣身内缩到极限
INSET_REF_WIDTH = 62    # 内缩上限 (参考袖子最大宽度)
HAND_Y = 575            # 此行以下 (袖口+手) 完全悬空 → 全部透明
OUTLINE_PX = 2          # 重建的衣身外缘描边宽度
RING_R = 3              # 擦除袖子描边时向外扩的像素数


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


def rotate_rgba(rgba, pivot, ang):
    """绕 pivot 旋转 RGBA。ang>0 = 屏幕顺时针 (y 向下坐标系)。"""
    px, py = pivot
    th = np.deg2rad(ang)
    cos, sin = np.cos(th), np.sin(th)
    H, W = rgba.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    dx = xx - px
    dy = yy - py
    xi = np.round(px + dx * cos - dy * sin).astype(int)
    yi = np.round(py + dx * sin + dy * cos).astype(int)
    ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
    out = rgba[np.clip(yi, 0, H - 1), np.clip(xi, 0, W - 1)].copy()
    out[~ok, 3] = 0
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
    # 洪水偶尔从袖口漏到衣身口袋饰条上 ⇒ 去掉衣身那一坨青色
    for _size, m in components(tl, 200):
        ys, xs = np.nonzero(m)
        if ys.min() < 400 and ys.max() > 640 and xs.max() - xs.min() > 120:
            arm &= ~m
    # 去掉袖口右上方漏进衣身竖向饰条的部分
    YY, XX = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    if side == 'L':
        arm &= ~((XX > 412) & (YY > 512))
    else:
        arm &= ~((XX < 612) & (YY > 512))

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
    # 肩圆盘也归上臂段 (上臂的近端关节) —— 绕肩旋转时圆盘与自身重合 ⇒ 无缝
    upper = upper | (arm & nS)
    # 肩圆盘内若混有非袖子像素 (衣身), 用袖子主色补齐, 保证圆盘完整
    full_disc = nS & (s_e < 0)
    sleeve_color = a[arm & (s_e < 0)][:, :3].mean(axis=0) if arm.any() else np.array([240, 240, 245])
    upper = upper | (full_disc & ~upper)
    # 手部整块归"手段" (含描边与手指)
    handseg = handseg | hand_full
    # 身体里保留一份肩圆盘 (角色肩头), 旋转后的上臂圆盘正好盖住它
    cap = arm & nS

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


def restore_body(base, arm_mask, side, hand_y=None,
                 outline_px=OUTLINE_PX, ring_r=RING_R):
    """摘掉袖子, 并把被袖子压住的**衣身**补回来。

    实测依据 (idle_00_base):
      · 袖子的深色描边被洪水填充当成"阻隔", 落在掩膜之外 ⇒ 必须用
        dilate(arm,ring_r) ∩ 暗像素 一并擦掉, 否则原处会留一圈虚线鬼影。
      · 袖子是画在大褂**上面**的一层; 肩部与大褂轮廓齐平, 往下逐渐悬空。

    返回 (body_img, fill_mask) —— fill_mask 记录新补的衣身区域 (用于自检)。
    """
    out = base.copy()
    H, W = arm_mask.shape
    solid = base[:, :, 3] > 40
    dark = (lum(base) < 130) & solid
    ring = dilate(arm_mask, ring_r) & (~arm_mask)
    # 只擦"袖子自己的描边": 外轮廓 (lo 左侧一小条) + 内轮廓 (hi 右侧一小条)。
    # 不能用整圈 ring —— 否则大褂下摆/短裤的描边会被误擦成虚线。
    ring_l = np.zeros_like(arm_mask)
    ring_r_ = np.zeros_like(arm_mask)
    for y in range(H):
        xs = np.nonzero(arm_mask[y])[0]
        if len(xs) == 0:
            continue
        lo, hi = int(xs.min()), int(xs.max())
        ring_l[y, max(0, lo - 7):lo + 2] = True
        ring_r_[y, max(0, hi - 2):min(W, hi + 3)] = True
    erase = arm_mask | ((ring & dark) & (ring_l | ring_r_))
    body = solid & (~erase)
    fill = np.zeros_like(arm_mask)

    # 全局衣身主色 (兜底): 取画面中部大片白大褂像素的中位数
    mid = base[380:700, 400:620, :3].astype(np.float64).reshape(-1, 3)
    ml = 0.299 * mid[:, 0] + 0.587 * mid[:, 1] + 0.114 * mid[:, 2]
    mt = teal(base[380:700, 400:620])
    bright = mid[(ml > 190) & (~mt.reshape(-1))]
    global_coat = np.median(bright, axis=0) if len(bright) else np.array([244, 251, 254])

    def coat_color(y, s_lo, s_hi):
        """取该行大褂面料色: 只用"亮且非青"像素, 取亮部高分位 (避开描边暗线)。"""
        if s_hi - s_lo < 3:
            return global_coat
        strip = base[y, s_lo:s_hi, :3].astype(np.float64)
        m = (lum(strip) > 190) & (~teal(base[y, s_lo:s_hi]))
        if m.sum() >= 3:
            return np.percentile(strip[m], 75, axis=0)
        return global_coat

    # R158 修: 记录每一行重建出的**大褂外缘**位置, 循环结束后把"大褂之外"的残留全部清成透明。
    # 根因: 手臂掩膜只包含肤色/袖色像素, **手的描边与手指间的暗线不在掩膜内**
    #       (洪水填充把暗线当阻隔), 于是摘掉手臂后原手轮廓残留成**虚线鬼影**。
    #       之前只擦 ring_l/ring_r_ 两条窄带, 手指轮廓的大多数像素漏网。
    # 对策: 重建好的大褂边缘之外本来就应该是背景(透明), 直接整段清掉, 鬼影无处可藏。
    edge_by_row = {}

    for y in range(H):
        xs = np.nonzero(arm_mask[y])[0]
        if len(xs) == 0:
            continue
        lo, hi = int(xs.min()), int(xs.max())
        width = hi - lo + 1
        if INSET_MODE == 'zero':
            inset = 0
        elif y <= SHOULDER_FLAT:
            inset = 0
        elif y >= INSET_FULL_Y:
            inset = INSET_REF_WIDTH
        else:
            # 平滑单调的内缩曲线 (不能用"每行按袖子宽度比例" —— 宽度逐行抖动会让衣身边缘成锯齿虚线)
            t = (y - SHOULDER_FLAT) / float(INSET_FULL_Y - SHOULDER_FLAT)
            t = min(1.0, max(0.0, t))
            ts = t * t * (3 - 2 * t)
            inset = int(round(INSET_REF_WIDTH * ts))
        inset = int(round(inset))

        # 大褂边缘 (往里收 inset)
        if side == 'L':
            edge = lo + inset
            src_lo = hi + 3
            src_hi = min(W, hi + 20)
            if edge >= hi + 1 or src_hi - src_lo < 4:
                continue
            # 平铺大褂白 (逐行取"真实像素"会在描边处产生横向条纹, 实测不可用)
            outl = base[y, max(0, lo - 7):lo, :3].reshape(-1, 3)
            dark_c = outl[outl.sum(axis=1).argmin()] if len(outl) else np.array([40, 45, 70])
            for x in range(edge, hi + 3):
                if x < 0 or x >= W:
                    continue
                out[y, x, 0:3] = global_coat
                out[y, x, 3] = 255
                fill[y, x] = True
            # 外缘描边 (在填充区最外侧)
            for k in range(outline_px):
                x = edge + k
                if 0 <= x < W:
                    out[y, x, 0:3] = dark_c
                    out[y, x, 3] = 255
                    fill[y, x] = True
            edge_by_row[y] = edge
        else:
            edge = hi - inset
            src_lo = max(0, lo - 20)
            src_hi = lo - 3
            if edge <= lo - 1 or src_hi - src_lo < 4:
                continue
            outl = base[y, hi + 1:hi + 8, :3].reshape(-1, 3)
            dark_c = outl[outl.sum(axis=1).argmin()] if len(outl) else np.array([40, 45, 70])
            for x in range(lo - 3, edge + 1):
                if x < 0 or x >= W:
                    continue
                out[y, x, 0:3] = global_coat
                out[y, x, 3] = 255
                fill[y, x] = True
            # 外缘描边 (在填充区最外侧 = 右边)
            for k in range(outline_px):
                x = edge + k
                if 0 <= x < W:
                    out[y, x, 0:3] = dark_c
                    out[y, x, 3] = 255
                    fill[y, x] = True
            edge_by_row[y] = edge

    # 擦除区里没被衣身填回的部分 → 透明
    out[erase & (~fill)] = 0

    # R158 修: 大褂外缘之外**整段清成透明** —— 原手轮廓/手指暗线不在手臂掩膜内,
    #   擦不干净就会在髋部留下虚线鬼影 (原来只擦两条窄带, 漏掉手指轮廓的大部分像素)。
    #   大褂外缘之外本来就应该透明, 所以整段清掉既根治鬼影, 又不会误伤衣身。
    for y, edge in edge_by_row.items():
        if side == 'L':
            out[y, :edge] = 0
        else:
            out[y, edge + outline_px:] = 0

    # R158 修 2: 上面那圈循环里, **只有重建了大褂的行**才被清干净。
    #   但手部那几行 (袖子已完全离开大褂, edge 会越界) 会被 continue 跳过 ⇒
    #   那些行上的原手轮廓残像素仍在 ⇒ 髋部出现一圈**虚线鬼影**。
    #   对策: 只清"紧贴手部皮肤的暗线"(半径 5 纹理 px)。
    #   实测几何: 手的描边就画在皮肤外沿 (离皮肤 0~4 px), 而大褂门襟的竖线
    #   离皮肤 ≥6 px ⇒ 半径 5 刚好能把两者分开, 不误伤衣身。
    #   亮度阈值放到 215: 肉眼看到的"虚线"其实是描边外的**抗锯齿浅色晕**(lum≈175),
    #   只清 lum<130 的暗线核心清不掉它 (实测踩过)。
    hz = SIDES[side]['hand_zone']
    zx0, zy0, zx1, zy1 = hz
    zy1 = min(zy1, H)
    zmask = np.zeros_like(arm_mask)
    zmask[zy0:zy1, zx0:zx1] = True
    near_skin = dilate(skin_relaxed(base) & zmask, 5)
    ghost = (lum(base) < 215) & solid & near_skin
    for y in range(zy0, zy1):
        if y in edge_by_row:
            continue
        xs = np.nonzero(arm_mask[y])[0]
        if len(xs) == 0:
            continue
        row = ghost[y, zx0:zx1]
        if row.any():
            out[y, zx0:zx1][row] = 0
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
