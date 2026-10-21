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
        hand_zone=(326, 566, 397, 682),
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
        hand_zone=(627, 566, 698, 682),
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

# ---------------------------------------------------------------------------
# R165 手臂掩膜的几何重建参数 (全部实测, 依据见下方 restore_body / build_arm 注释)
#
# 【R165 根因 —— 之前四轮都错在"手臂掩膜不是手臂"】
#   R162 的 arm 掩膜是**洪水填充**出来的, 而洪水填充有两个硬伤:
#     ① 袖子中段那条**青色饰条的暗描边**横在袖子里 ⇒ 填充被拦腰截断,
#        肩→肘的**上臂整段没进掩膜** (实测 upper 段只有 854 px);
#        ⇒ 肘部一折, 前臂+手就变成**没有根的漂浮肢体**横穿胸口
#        —— 这就是用户真机看到的"多出来一双手"。
#     ② `cuff_box` 写的是 (340,548,408,606), 但底图里**真正的青色腕带在 x407~436**,
#        种子完全落空 ⇒ 腕带**整条留在身体上**, 手臂转走后髋部留下一截青带。
#   R165 改成**几何重建**: 手臂 = 该行 [剪影左缘, 衣身接缝线右缘] 的连续像素,
#   接缝线用"该行最靠右的暗线 (lum<120, 右缘<=445)"实测出来, 不再靠洪水填充猜。
ARM_TOP = 376           # 袖子与肩帽的分界行 (此行以上属于身体, 以下属于手臂)
HAND_ROW = 596          # 此行以下只有手 (手腕以下), 不再有大褂接缝线
SEAM_DARK = 120         # 接缝线(暗描边)的亮度阈值
SEAM_MAX_X = 445        # 接缝线搜索的右界 (再往右是衣身自己的褶皱线)
SEAM_KEEP = 4           # 接缝线本身保留的宽度 (手臂抹掉后要把它贴回当衣身外缘)
SEAM_MIN_X = 1024 - SEAM_MAX_X   # R 侧接缝线的搜索左界 (与 L 侧关于 x=512 对称)
SEAM_SEARCH = 10        # 接缝线精修窗口 (相对 SEAM_L 表先验, ±10 纹理 px)
SHOULDER_BALL_R = 26    # 肩关节球半径 (静态再画, 盖住旋转畸变 + 关节缝隙)
SHOULDER_FILL_R = 46    # 肩区回填半径 (只回填肩关节附近, 不得把衣身涂到袖子的外缘)
OUTLINE_RGB = (10, 14, 34)   # 底图轮廓线颜色 (实测 x638,y460 处 rgb=9,14,34)
CUT_EDGE_PX = 2         # 被切开的那条边要补的描边宽度


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


def seam_band(a, y, side, x_edge=None):
    """实测该行的**衣身接缝线**(袖子内缘 = 大褂外缘) 暗带位置。

    R165 修正 (第二版):
      原来的实现是"从衣身一侧往外找, 取**最靠外**的那条暗线"(L 侧) /
      "取**最靠内**的那条暗线"(R 侧)。这条规则在两处会抓错线:
        ① 肩部 (y≈376~395): 肩帽自己的描边比真正的接缝线更靠外
           ⇒ 抓到的其实是肩帽线, 手臂内缘因此被多切掉 ~13px;
        ② 腕部 (y≈545~600): 大褂自己���褶皱线比接缝线更靠内
           ⇒ 抓到的其实是褶皱线, 手臂掩膜因此**多吃了 20 多 px 的衣身**,
              手臂一转就把衣身一块带走。
      改法: 用**已实测的 SEAM_L 表**做先验(逐行数暗线量出来的),
      再在 ±10px 内取**中心离先验最近**的那条暗段做精修。
      实测: 全部 224 行的接缝线都能在该窗口内命中, 与 L 侧实测表逐行吻合;
      R 侧用 x→1024-x 镜像 (实测两侧接缝线严格镜像, 误差 ≤2px)。

    返回 (l, r) 或 None。
    """
    row = lum(a)[y]
    al = a[y, :, 3]
    dark = (row < SEAM_DARK) & (al > 40)
    runs = []
    s0 = None
    for x in range(a.shape[1]):
        if dark[x] and s0 is None:
            s0 = x
        elif (not dark[x]) and s0 is not None:
            runs.append((s0, x - 1))
            s0 = None
    if s0 is not None:
        runs.append((s0, a.shape[1] - 1))
    if not runs:
        return None
    prior = seam_x(side, y)
    best, bestd = None, 1e9
    for r in runs:
        c = (r[0] + r[1]) / 2.0
        d = abs(c - prior)
        if d < bestd:
            best, bestd = r, d
    if best is None or bestd > SEAM_SEARCH:
        # 先验附近没有暗段 (肩帽/腕带过渡处) ⇒ 用先验本身兜底
        c = int(round(prior))
        return (max(0, c - 1), min(a.shape[1] - 1, c + 1))
    return best


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


def _outer_edge_R(a, y):
    """R 侧袖子外缘 = 该行**最右侧的不透明像素** (即剪影边缘)。

    【R165 二次修正 —— 这才是"残留手臂描边"的第二个根因】
      之前用"镜像参考位右侧的第一条暗线"定位袖子外缘, 结果:
        · 镜像参考位常常正好落在袖子**青色饰条的暗边**上 ⇒ 取到饰条而不是外轮廓;
        · 或者落在外轮廓**描边的中间** ⇒ 手臂掩膜只吃掉描边的前半段。
      ⇒ 每行都有 1~4px 的描边/抗锯齿残渣留在衣身上。手臂转走后, 衣身上
        就留下一串**点状残线** (R165 实测: 残留暗像素 20 px + 大量抗锯齿残渣,
        在 1024 纹理坐标下从髋部一路延伸到肘部 —— 正是用户真机看到的
        "残留手臂描边/虚线鬼影")。

    实测依据: 底图 R 侧**头发的侧发只到 y≈330**, 而手臂掩膜从 ARM_TOP=376
    起算 ⇒ 376~596 行内 R 侧剪影的最外缘**就是袖子自己的外轮廓**,
    不存在头发搭在袖子上的干扰。
    交叉验证: R 侧剪影边缘与 L 侧镜像位的偏差逐行平滑 (+10 → +6 px),
    没有突变 ⇒ 确认没有混入头发。
    """
    solid = a[y, 512:, 3] > 40
    xs = np.nonzero(solid)[0]
    if len(xs) == 0:
        return None
    return 512 + int(xs.max())


def _extend_dark_outline(a, mask, side, max_px=14, dark_thr=150):
    """把袖子的外缘**向外扩**若干像素, 只吃"暗描边 + 抗锯齿带"。

    R165 实测根因 (用户真机看到"残留手臂描边/虚线鬼影"):
      袖子的外轮廓是**粗黑描边** + 外侧 1~2px 的半透明抗锯齿带。
      掩膜的外缘取的是"那条暗线的**最后一个像素**", 于是抗锯齿带留在掩膜外
      ⇒ 手臂转走后, 那一圈暗像素原地留下 ⇒ 变成一串**虚线鬼影**
      (R165 实测: 掩膜外缘比剪影真实右缘差 1~9 px)。
    修法: 从掩膜外缘继续向外走, 只把"暗像素 (lum<150) 与半透明抗锯齿"并入掩膜,
      遇到**银白头发**(亮)或全透明就停 ⇒ 头发与背景都不受影响。
    """
    H, W = mask.shape
    lum_a = lum(a)
    al = a[:, :, 3]
    out = mask.copy()
    for y in range(H):
        xs = np.nonzero(mask[y])[0]
        if len(xs) == 0:
            continue
        if side == 'L':
            edge = int(xs.min())
            rng = range(edge - 1, max(-1, edge - max_px - 1), -1)
        else:
            edge = int(xs.max())
            rng = range(edge + 1, min(W, edge + max_px + 1))
        for x in rng:
            if al[y, x] <= 0:
                break          # 已经到背景外, 停
            if lum_a[y, x] < dark_thr:
                out[y, x] = True
            else:
                break          # 遇到亮像素(头发), 停
    return out


def _sleeve_mask(a, side, ref=None):
    """几何重建一条手臂的**袖子 + 袖口腕带**掩膜。

    手臂 = 每一行 [剪影外缘, 衣身接缝线] 之间的连续像素:
      · 剪影外缘 = 该侧袖子的外描边 (R 侧用 _outer_edge_R 定位, 见该函数注释)
      · 接缝线   = seam_band() 实测 (把手臂和衣身分开的那条暗线)
    腕带(青色)夹在外缘与接缝线之间, 天然被整段包含 ⇒ 转走后不会留在身体上。
    ref = L 侧掩膜 (R 侧用来做镜像参考)。

    【R165 根因修复 —— 接缝线必须留在衣身上, 不能进手臂旋转层】
      接缝线是**大褂的外缘描边**, 属于身体, 不属于手臂。
      R165 初版把它算进了手臂掩膜, 于是:
        · 手臂在肘/腕二分线处被切成三段, 接缝线也被切成三段;
        · 三段各绕**不同的关节**旋转 (上臂绕肩 / 前臂绕肘 / 手绕腕);
        · 接缝线的下半截(前臂段)被甩到完全不同的位置 ⇒
          髋部凭空多出一条**游离的细暗弧**, 1~3px 宽经双线性重采样后碎成虚线
          —— 这就是用户真机看到的"右髋残留手臂描边"(R165 实测:
          该暗弧的反变换落点 = 底图 (586,430) 正是 R 侧接缝线)。
      修法: 手臂掩膜**不含接缝线** ⇒ 接缝线整条留在衣身上,
        永远不会被旋转搬运, 也不可能被切成两半。
    """
    solid = a[:, :, 3] > 40
    m = np.zeros_like(solid)
    for y in range(ARM_TOP, HAND_ROW):
        if side == 'L':
            xs = np.nonzero(solid[y, 300:512])[0]
            if len(xs) == 0:
                continue
            x_edge = 300 + int(xs.min())
        else:
            x_edge = _outer_edge_R(a, y)
            if x_edge is None:
                continue
        band = seam_band(a, y, side, x_edge)
        if band is None:
            continue
        # 【关键】接缝线(暗描边本体)归衣身, 不进手臂:
        #   L 侧手臂在接缝线**左边** ⇒ 掩膜到 band[0]-1 为止
        #   R 侧手臂在接缝线**右边** ⇒ 掩膜从 band[1]+1 开始
        if side == 'L':
            m[y, x_edge:band[0]] = True
        else:
            m[y, band[1] + 1:x_edge + 1] = True
    # R165: 把外缘的暗描边 + 抗锯齿带并进掩膜 (否则手臂转走后原地留一圈虚线鬼影)
    m = _extend_dark_outline(a, m, side)
    return m


# ---------------------------------------------------------------- 手臂骨架
def build_arm(a, side):
    """切出一条手臂, 返回三关节骨架 + 三段掩膜。"""
    J = SIDES[side]
    sk, tl = skin(a), teal(a)

    # ------------------------------------------------------------------
    # R165: 手臂掩膜改成**几何重建** (不再靠洪水填充)
    #
    # 【R165 实测根因 —— 这才是"多出来一双手"的真凶, 之前四轮都判错了】
    #   R162 的 arm 掩膜是**洪水填充**出来的, 而:
    #     ① 袖子中段那条**青色饰条的暗描边**横在袖子里当"阻隔"
    #        ⇒ 填充只能从腕部往上走到饰条就停 ⇒ **肩→肘的上臂整段没进掩膜**
    #           (实测 upper 段只有 854 px) ⇒ 肘部一折, 前臂+手就成了
    #           **没有根的漂浮肢体**横穿胸口 ⇒ 真机看到"多出来一双手"。
    #     ② `cuff_box` 写的是 (340,548,408,606), 而底图里真正的**青色腕带
    #        在 x407~436** ⇒ 腕带种子完全落空 ⇒ 腕带整条留在身体上。
    #   R165 改法: 手臂 = 该行 [剪影左缘, 衣身接缝线右缘] 的连续像素;
    #   接缝线用 seam_band() 实测 (该行最靠右的那条暗线), 手部仍用肤色膨胀。
    solid_a = a[:, :, 3] > 40
    arm = np.zeros_like(solid_a)
    if side == 'L':
        arm = _sleeve_mask(a, 'L')
    else:
        # R165 二次修正: R 侧外缘改用**底图剪影边缘**直接定位 (见 _outer_edge_R),
        #   不再需要 L 侧掩膜做镜像参考 (两侧剪影偏差逐行平滑, 实测无头发混入)。
        arm = _sleeve_mask(a, 'R')

    # ---- 手部单独切: 手的描边与手指 (暗线不能当阻隔, 用肤色膨胀兜住) ----
    hz = np.zeros_like(arm)
    hx0, hy0, hx1, hy1 = J['hand_zone']
    hz[hy0:hy1, hx0:hx1] = True
    hand_full = dilate(skin_relaxed(a) & hz, 7) & (a[:, :, 3] > 40) & hz
    arm = arm | hand_full

    S, E, W = J['shoulder'], J['elbow'], J['wrist']
    rS, rE, rW = J['r_shoulder'], J['r_elbow'], J['r_wrist']
    nS, nE, nW = (disc(a.shape[:2], p, r) for p, r in ((S, rS), (E, rE), (W, rW)))

    # 三段: 上臂(肩→肘) / 前臂(肘→腕) / 手(腕→指尖)
    # 分界用**垂直平分线**; 每一段带自己**近端关节的完整圆盘**, 不带远端关节圆盘
    def bisect(p, q):
        """p/q 的垂直平分线, 返回带符号距离。

        R165 修正: 原来直接返回 (xx-mx)*ux + (yy-my)*uy, 而左右两侧的
        (p→q) 方向向量是**镜像**的 (L 侧指向上/左, R 侧指向下/右) ⇒
        **同一套判据在 R 侧符号整个反过来**。
        后果 (实测): R 侧 "e_w>0 = 腕侧" 变成了"肘侧",
        于是 R 侧的手部段只有 806 px (L 侧 8151 px), 前臂段 8710 px (L 侧 4893)，
        整条右臂的三段分配全错 ⇒ 右臂一转就是**横穿胸口的漂浮肢体**。
        修法: 统一符号约定 —— 返回值 >0 一律表示"在 q 那一侧"(y 向下即更靠下)。
        """
        mx, my = (p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0
        ux, uy = q[0] - p[0], q[1] - p[1]
        n = max(1e-6, (ux * ux + uy * uy) ** 0.5)
        ux, uy = ux / n, uy / n
        yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]].astype(np.float64)
        val = (xx - mx) * ux + (yy - my) * uy
        if uy < 0:
            val = -val
        return val

    s_e = bisect(S, E)      # >0 = 靠肘一侧
    e_w = bisect(E, W)      # >0 = 靠腕一侧

    upper = arm & (s_e < 0) & ~nE & ~nW
    fore = arm & (s_e > 0) & (e_w < 0) & ~nW
    handseg = arm & (e_w > 0)
    # 咬口归属: 肘圆盘归前臂段, 腕圆盘归手段 (各自**近端**关节 → 完整圆盘)
    fore = fore | (arm & nE & (s_e > 0) & ~nW)
    handseg = handseg | (arm & nW)
    # R165 修正: 肩盘**参与**上臂段旋转 (绕自身圆心转 ⇒ 位置不变, 关节不会开缝),
    #   旋转带来的内部畸变由**静态肩关节球** (ball, 见 pose_arm) 覆盖。
    #   R162 把它排除出上臂段, 结果手臂转走后肩部只剩一圈描边 + 青色碎块。
    # 手部整块归"手段" (含描边与手指)
    handseg = handseg | hand_full
    # 身体里保留一份肩章 (角色肩头), 旋转后的上臂正好盖住它
    cap = arm & nS
    # R165 三次修正: 前臂段被"肘/腕二分线"切开的地方, 旋转后会**暴露在剪影上**,
    #   而二分线切出来的是一条**没有描边的白色直边** ⇒ 角色左缘出现一截白边
    #   (R162 的 R2-2 判据直接判 FAIL: "衣身边缘成了虚线")。
    #   实测: 比心帧 L 侧 x397~403 / y439~479 这一段的像素全部来自 L.fore,
    #   正是前臂段被切开的那条边 —— 二分线原本近水平, 随前臂转 118° 后变成近垂直,
    #   正好落在剪影上。
    #   修法: 给被切开的那条边补一条 2px 描边 (用底图轮廓线的原色),
    #   旋转后它就成为该段自己的外缘描边 ⇒ 剪影连续。
    fore_edge = np.zeros_like(arm)
    if fore.any():
        cut = ((s_e > 0) & (s_e <= CUT_EDGE_PX) & ~nE) | \
              ((e_w < 0) & (e_w >= -CUT_EDGE_PX) & ~nW)
        fore_edge = fore & cut

    # R165 二次修正: 肩区回填**必须限定在肩关节附近**。
    #   原实现把**整条上臂**当回填区 ⇒ 手臂转走后, 衣身被平涂的衣身色
    #   一路涂到**袖子原本的外轮廓**, 而那一段本来是"袖子画在衣身外面"的部分,
    #   衣身根本不该长到那里 ⇒ 角色左缘出现 41 行**没有描边的白边**
    #   (R162 的 R2-2 判据直接判 FAIL: "衣身边缘成了虚线")。
    #   实测: 袖子外缘在 x≈398 处离肩关节 (428,383) 有 63px, 超出 46px 半径 ⇒
    #   限定半径后 y439~479 这段不再被涂, 剪影边缘回到**衣身接缝线**(连续描边)。
    fill = upper & disc(a.shape[:2], S, SHOULDER_FILL_R)

    # R165: 肩关节球 = 肩膀附近那一小块手臂素材。
    #   它会**静态**再画一遍(画在旋转后的手臂之上):
    #     ① 盖住绕肩旋转把肩章内容甩歪的畸变
    #     ② 盖住手臂与身体之间的接缝 ⇒ 关节处永不出现缺口/碎块
    ball = arm & disc(a.shape[:2], S, SHOULDER_BALL_R)
    sleeve_color = a[arm & (s_e < 0)][:, :3].mean(axis=0) if arm.any() else np.array([240, 240, 245])

    ys, xs = np.nonzero(handseg)
    hand_c = (float(xs.mean()), float(ys.mean())) if len(xs) else (float(W[0]), float(W[1]))

    return dict(side=side, arm=arm, cap=cap, nS=nS, ball=ball, fill=fill,
                fore_edge=fore_edge,
                upper=upper, fore=fore, hand=handseg,
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
    fe = rig.get('fore_edge')
    if fe is not None and fe.any():
        fore[fe, 0] = OUTLINE_RGB[0]
        fore[fe, 1] = OUTLINE_RGB[1]
        fore[fe, 2] = OUTLINE_RGB[2]
        fore[fe, 3] = np.maximum(fore[fe, 3], 255)
    upper = np.where(rig['upper'][:, :, None], a, 0)

    hand1 = rotate_rgba(hand, W, a_w)
    fore1 = rotate_rgba(fore, E, a_e)
    hand2 = rotate_rgba(hand1, E, a_e)

    fore2 = rotate_rgba(fore1, S, a_s)
    hand3 = rotate_rgba(hand2, S, a_s)
    upper2 = rotate_rgba(upper, S, a_s)
    # R165: 静态肩关节球 —— 画在旋转后的手臂**之上**。
    #   它用底图原始像素 ⇒ 肩章(青色肩线)不会被旋转甩歪;
    #   同时盖住手臂与身体之间的接缝 ⇒ 关节处不会出现缺口或碎块。
    ball = np.where(rig.get('ball') is not None and rig['ball'][:, :, None], a, 0)
    return upper2, fore2, hand3, ball


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


def restore_body(base, arm_mask, side, outline_px=OUTLINE_PX, cap_mask=None,
                 fill_mask=None):
    """摘掉整条手臂 (袖子 + 袖口腕带 + 手), 并把**大褂的外缘**恢复出来。

    R165 重写 (之前几轮全错在"袖子该怎么消失 / 大褂边缘该画在哪"):
      底图解剖 (idle_00_base, 左臂, 1024 纹理坐标):
        x  外侧粗黑描边(剪影) | 袖子白 + 青色饰条 | 袖口青色腕带 | 接缝暗线 | 大褂本体
      ⇒ 袖子(连腕带)是一整块"手臂"; 它的**内缘(接缝线)就是大褂的外缘**。

      【R162 的错法 —— 这就是真机"多出来一双手"的根因】
        摘掉袖子后用"平涂一块衣身色"补上, 结果:
          ① 平涂区把**上臂**整段盖住 ⇒ 肘部一折, 前臂+手**没有根**,
             横穿胸口 ⇒ 用户看到"多出来一双手" (R165 实测: upper 段仅 854 px)
          ② 平涂区保留了袖子的**外轮廓描边带** ⇒ 身体上留着一只"空袖子"
             ⇒ 胸口再叠一对漂浮的手 ⇒ 更像凭空多了一双手
      【R165 改法】
        · 手臂掩膜 = 袖子 + 腕带 + 手 (几何实测, 一个不多一个不少) ⇒ **整块抹掉**
        · 抹完把底图**接缝线那一小条贴回原位** —— 它就是大褂该有的外缘描边
          (腕带那几行, 腕带右缘正好压在大褂边上, 贴回来同样成立)
        · 肩关节球由 pose_arm 用底图原始像素**静态补回** (肩章不畸变 + 关节无缝)
        · 大褂本体(接缝线右侧)本来就完整, 一个像素没被动过, 不需要补

    返回 (body_img, fill_mask)。
    """
    out = base.copy()
    H, W = arm_mask.shape

    # ① 先把"接缝线"那一小条存下来 (袖子连同接缝线一起被抹掉, 要贴回来当衣身外缘)
    seam_save = {}
    for y in range(ARM_TOP, HAND_ROW):
        xs = np.nonzero(arm_mask[y])[0]
        if len(xs) == 0:
            continue
        x_edge = int(xs.min()) if side == 'L' else int(xs.max())
        band = seam_band(base, y, side, x_edge)
        if band is None:
            continue
        seam_save[y] = (band, base[y, band[0]:band[1] + 1].copy())

    # ② 抹掉整条手臂 (含肩球 —— 肩球会由 pose_arm 用底图原始像素**静态补回**)
    out[arm_mask] = 0

    # ③ 接缝线贴回来 = 大褂的外缘描边 (底图原件, 颜色/抗锯齿天然正确)
    for y, (band, px) in seam_save.items():
        out[y, band[0]:band[1] + 1] = px

    # ④ **肩区回填衣身色** (R165 新增)
    #    手臂绕肩旋转时, 肩→肘那一段(上臂)会从原位**扫走**, 原位就缺了一块,
    #    肩膀上凭空出现一个三角形的透明缺口 (真机看到"肩膀豁了个洞")。
    #    R162 的平涂衣身色就是为这个加的, 但它**整条袖子都涂** ⇒ 身体上留了
    #    一只"空袖子"(只有外轮廓描边、手却没了) ⇒ 这才是"多出来一双手"的另一半。
    #    R165 只回填**肩区**(上臂那一小段, 约 30x50 纹理 px), 并让它长成
    #    大褂的**肩部面料**, 不是一只空袖子 ⇒ 既是肩膀, 也不是多余的肢体。
    if fill_mask is not None and fill_mask.any():
        _fill_shoulder(out, base, fill_mask, side, seam_save)

    return out, np.zeros((H, W), bool)


def _fill_shoulder(out, base, fill_mask, side, seam_save):
    """把"肩区"(上臂扫走后留下的缺口) 回填成大褂的肩部面料。"""
    H, W = out.shape[:2]
    # 大褂主色兜底: 取画面中部大片白大褂像素的中位数
    mid = base[380:700, 400:620, :3].astype(np.float64).reshape(-1, 3)
    ml = 0.299 * mid[:, 0] + 0.587 * mid[:, 1] + 0.114 * mid[:, 2]
    mt = teal(base[380:700, 400:620]).reshape(-1)
    bright = mid[(ml > 190) & (~mt)]
    global_coat = np.median(bright, axis=0) if len(bright) else np.array([244, 251, 254])

    for y in range(H):
        xs = np.nonzero(fill_mask[y])[0]
        if len(xs) == 0:
            continue
        if side == 'L':
            lo, hi = int(xs.min()), int(xs.max())
            sx = seam_save.get(y, (None,))[0]
            sx = sx[1] if sx is not None else hi
        else:
            lo, hi = int(xs.min()), int(xs.max())
            sx = seam_save.get(y, (None,))[0]
            sx = sx[0] if sx is not None else lo
        # 取"大褂本体"一侧的干净白做填充色 (避开描边与青色饰条)
        if side == 'L':
            c0, c1 = sx + 4, min(W, sx + 90)
        else:
            c0, c1 = max(0, sx - 90), sx - 4
        if c1 - c0 < 3:
            col = global_coat
        else:
            strip = base[y, c0:c1, :3].astype(np.float64)
            msk = (lum(strip) > 185) & (~teal(base[y, c0:c1]))
            col = np.median(strip[msk], axis=0) if msk.sum() >= 2 else global_coat
        n = hi - lo + 1
        if n <= 0:
            continue
        # 靠身体一侧留一点柔和阴影, 让肩部有体积感 (不是一块平涂白板)
        ramp = np.ones(n)
        m = min(n, EDGE_SHADOW_PX)
        if m > 0:
            ramp[:m] = 1.0 - 0.10 * (1.0 - np.linspace(0.0, 1.0, m))
        # 颜色取"大褂面料色"(col), **不能**取 out —— 该区域已经被抹成透明,
        # 取 out 会得到 (0,0,0) ⇒ 肩膀上出现一块黑楔子 (R165 初版踩过)
        out[y, lo:hi + 1, 0:3] = np.clip(col[None, :] * ramp[:, None], 0, 255).astype(np.int32)
        out[y, lo:hi + 1, 3] = 255


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
