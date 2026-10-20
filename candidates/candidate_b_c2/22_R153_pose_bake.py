#!/usr/bin/env python3
"""R153 姿态烘焙器 — 用**现有素材**做可控的局部动画, 派生新的、视觉上明显不同的动作帧。

背景 (R153 用户真机验收):
  1. 启动/点击时"莫名抬手、手放胸前" → 根因: R138 的 idle_04 不是眨眼帧, 它是**右手横在胸前**的姿势;
     R147 的眨眼序列 [4,5] 与点击反馈都用到了它。
  2. "现有动作太少" → 需要 12+ 种视觉上不同的动作, 但**禁止**靠重命名/重复播放/整体旋转/强行缩放虚增。

本脚本的三种**局部**技术 (都只动局部像素, 不整体旋转/缩放):
  A. 眼睛区域合成 (face_swap)
     实测: idle_00 / idle_04 / idle_05 的头部外接框**完全相同** (329,37,703,329),
     眉眼头发逐像素同位 → 可以把"闭眼/半闭眼"的眼部像素精确搬到"手臂自然下垂"的底图上。
       → blink_half (半眨眼, 无抬手) / blink_closed (闭眼) / happy_squint (眯眼笑)
  B. 头部局部变换 (head_transform)
     把"头发+脸"切出来 (软遮罩), 绕颈部支点做旋转/位移/微缩, 再与"去掉头部的身体层"合成。
       → head_tilt (歪头) / head_nod (点头) / glance_left / glance_right (张望)
  C. 躯干局部呼吸 (torso_breath)
     只对"胸口"区域做极小的垂直缩放 (软遮罩), 头顶与脚底固定 → 躺姿呼吸的起伏。

所有输出写入 assets/character_R153/, R138 原始 23 帧一个字节都不动。
"""
import json
import os
import sys
import argparse

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')
OUT = os.path.join(ASSETS, 'character_R153')

BASE = os.path.join(R138, 'idle', 'idle_00_base.png')
DONOR_HALF = os.path.join(R138, 'idle', 'idle_04_blink_half.png')
DONOR_CLOSED = os.path.join(R138, 'idle', 'idle_05_blink_closed.png')
SIT = os.path.join(R138, 'sleep_enter', 'sleep_enter_01_sit.png')
SLEEP_STABLE = os.path.join(R138, 'sleep_loop', 'sleep_loop_02_stable.png')

# 头部几何 (1024x1024 纹理坐标) — 由 22_ 脚本实测 + 人工核对
HEAD_CENTER = (516, 150)
HEAD_RADII = (200, 122)      # 椭圆半轴 (含头发两侧发束)
NECK_PIVOT = (516, 268)      # 颈部支点 (绕它转头)
CHIN_Y = 252                 # 下巴线 (脸/眼睛区域的下界)
FACE_TOP_Y = 150             # 眼睛区域的上界


def load(path):
    return Image.open(path).convert('RGBA')


def to_np(im):
    return np.asarray(im).astype(np.float64)


def to_im(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'RGBA')


def dilate(mask, r):
    m = mask.copy()
    for _ in range(r):
        m2 = m.copy()
        m2[1:] |= m[:-1]
        m2[:-1] |= m[1:]
        m2[:, 1:] |= m[:, :-1]
        m2[:, :-1] |= m[:, 1:]
        m = m2
    return m


# ======================================================================
# A. 眼睛区域合成
# ======================================================================
def face_swap(base_path, donor_path, out_path, face_top=FACE_TOP_Y, face_bottom=CHIN_Y,
               tag=''):
    """把 donor 的"脸部表情"(眼睛/睫毛) 精确搬到 base 上, 身体与手臂完全不动。"""
    b = to_np(load(base_path))
    d = to_np(load(donor_path))
    diff = np.abs(b[:, :, :3] - d[:, :, :3]).max(axis=2)
    mask = (diff > 18) & (b[:, :, 3] > 40) & (d[:, :, 3] > 40)
    # 只保留脸部表情区 (排除身体/手臂)
    region = np.zeros_like(mask)
    region[face_top:face_bottom, 380:660] = True
    mask = mask & region
    if mask.sum() < 50:
        raise RuntimeError(f'{tag}: 眼部差异区域过小 ({int(mask.sum())}px), 拒绝产出')
    mask = dilate(mask, 2)
    out = b.copy()
    out[mask] = d[mask]
    im = to_im(out)
    im.save(out_path)
    return {'file': os.path.basename(out_path), 'source': os.path.basename(base_path),
            'donor': os.path.basename(donor_path), 'swapped_px': int(mask.sum()),
            'bbox': list(im.getbbox()), 'note': f'仅换眼部区域, 手臂/身体与 {tag} 底图逐像素一致'}


# ======================================================================
# B. 头部局部变换
# ======================================================================
def head_mask_arrays(W, H):
    """头部软遮罩: 椭圆(头发+脸) × 纵向渐隐(脖子以下淡出)"""
    yy, xx = np.mgrid[0:H, 0:W]
    e = ((xx - HEAD_CENTER[0]) / HEAD_RADII[0]) ** 2 + ((yy - HEAD_CENTER[1]) / HEAD_RADII[1]) ** 2
    ell = e <= 1.0
    # 纵向: 下巴以下淡出, 保住肩膀不跟着动
    fade = np.clip((CHIN_Y + 46 - yy) / 46.0, 0.0, 1.0)
    return (ell * fade).astype(np.float64)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def head_weight(W, H, core=1.02, fade=1.75):
    """头部的**连续**权重场: 头部核心=1 (刚性旋转), 外围平滑衰减到 0 (身体不动)。

    用连续场而不是二值遮罩 → 变形处处连续, 不会出现"挖掉头部再贴回"的月牙空洞。
    """
    yy, xx = np.mgrid[0:H, 0:W]
    e = np.sqrt(((xx - HEAD_CENTER[0]) / HEAD_RADII[0]) ** 2 +
                ((yy - HEAD_CENTER[1]) / HEAD_RADII[1]) ** 2)
    w = 1.0 - smoothstep(core, fade, e)
    # 脖子正下方必须固定 (否则脖子会被拧)
    neck = np.exp(-(((xx - NECK_PIVOT[0]) / 95.0) ** 2 + ((yy - NECK_PIVOT[1]) / 62.0) ** 2))
    w = w * (1.0 - 0.95 * neck)
    return np.clip(w, 0.0, 1.0)


def bilinear_sample(a, sx, sy):
    """对 (H,W,C) float 数组按 (sx,sy) 做双线性采样。"""
    H, W = a.shape[0], a.shape[1]
    sx = np.clip(sx, 0, W - 1.001)
    sy = np.clip(sy, 0, H - 1.001)
    x0 = np.floor(sx).astype(int)
    y0 = np.floor(sy).astype(int)
    fx = (sx - x0)[:, :, None]
    fy = (sy - y0)[:, :, None]
    c00 = a[y0, x0]
    c10 = a[y0, x0 + 1]
    c01 = a[y0 + 1, x0]
    c11 = a[y0 + 1, x0 + 1]
    return (c00 * (1 - fx) * (1 - fy) + c10 * fx * (1 - fy) +
            c01 * (1 - fx) * fy + c11 * fx * fy)


def head_transform(src_path, out_path, dx=0, dy=0, scale=1.0, rotate=0.0, tag=''):
    """头部局部弯曲变形 (连续权重场 + 逆向映射), 身体/腿部不参与旋转或缩放。"""
    im = load(src_path)
    W, H = im.size
    a = to_np(im)
    yy, xx = np.mgrid[0:H, 0:W]
    w = head_weight(W, H)
    th = np.deg2rad(rotate) * w
    s = np.where(w > 0, scale, 1.0)
    dxv, dyv = dx * w, dy * w
    px, py = NECK_PIVOT
    dxo, dyo = xx - px, yy - py
    cth, sth = np.cos(th), np.sin(th)
    # 逆向映射: 输出像素 → 输入采样位置
    sx = px + (cth * dxo + sth * dyo) / s + dxv
    sy = py + (-sth * dxo + cth * dyo) / s + dyv
    out = bilinear_sample(a, sx, sy)
    res = to_im(out)
    res.save(out_path)
    return {'file': os.path.basename(out_path), 'source': os.path.basename(src_path),
            'transform': {'dx': dx, 'dy': dy, 'scale': scale, 'rotate': rotate},
            'bbox': list(res.getbbox()),
            'note': '头部连续权重场局部弯曲 (无切口/无空洞), 身体与腿部未参与旋转或缩放'}


# ======================================================================
# C. 躯干局部呼吸
# ======================================================================
def torso_breath(src_path, out_path, chest_box, amount=0.018, tag=''):
    """胸口区域做极小垂直缩放 (软遮罩), 头顶与脚底不动 → 呼吸起伏。"""
    im = load(src_path)
    W, H = im.size
    a = to_np(im)
    x0, y0, x1, y1 = chest_box
    yy, xx = np.mgrid[0:H, 0:W]
    # 胸部椭圆 + 纵向渐隐
    e = ((xx - (x0 + x1) / 2) / ((x1 - x0) / 2)) ** 2 + ((yy - (y0 + y1) / 2) / ((y1 - y0) / 2)) ** 2
    soft = np.clip((1.0 - e) * 1.6, 0, 1)
    soft = soft * np.clip((yy - y0 - 8) / 20.0, 0, 1) * np.clip((y1 + 8 - yy) / 20.0, 0, 1)
    soft_img = Image.fromarray((soft * 255).astype(np.uint8), 'L').filter(
        ImageFilter.GaussianBlur(radius=6))
    soft = np.asarray(soft_img).astype(np.float64) / 255.0
    # 以 y1 (下缘) 为支点做垂直缩放
    sy = 1.0 + amount
    out = a.copy()
    # 仅在软遮罩内做垂直重采样: 用 numpy 逐列映射
    for x in range(W):
        col_w = soft[:, x]
        if col_w.max() < 0.02:
            continue
        ys = np.arange(H)
        src_y = y1 + (ys - y1) / sy
        src_y = np.clip(src_y, 0, H - 1)
        y0i = np.floor(src_y).astype(int)
        y1i = np.clip(y0i + 1, 0, H - 1)
        fy = (src_y - y0i)[:, None]
        col = a[:, x, :] * (1 - fy) + a[y0i, x, :] * fy
        w = col_w[:, None]
        out[:, x, :] = a[:, x, :] * (1 - w) + col * w
    res = to_im(out)
    res.save(out_path)
    return {'file': os.path.basename(out_path), 'source': os.path.basename(src_path),
            'chest_box': list(chest_box), 'amount': amount,
            'bbox': list(res.getbbox()),
            'note': '仅胸口软遮罩区域垂直微缩, 头顶/脚底固定'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=OUT)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    rep = {'round': 'R153', 'techniques': ['face_swap', 'head_transform', 'torso_breath'],
           'items': []}

    def emit(info):
        rep['items'].append(info)
        print(f"  ✅ {info['file']:26s} {info.get('note','')}")

    print("R153 姿态烘焙 (全部基于现有素材的局部处理):")

    # --- A. 眼睛区域合成 ---
    emit(face_swap(BASE, DONOR_HALF, os.path.join(a.out_dir, 'blink_half.png'),
                   tag='idle_00_base'))
    emit(face_swap(BASE, DONOR_CLOSED, os.path.join(a.out_dir, 'blink_closed.png'),
                   tag='idle_00_base'))
    # 坐着打盹: 坐姿 + 闭眼
    emit(face_swap(SIT, DONOR_CLOSED, os.path.join(a.out_dir, 'doze_sit.png'),
                   tag='sleep_enter_01_sit'))

    # --- B. 头部局部变换 ---
    emit(head_transform(BASE, os.path.join(a.out_dir, 'head_tilt.png'),
                        rotate=11.0, tag='tilt'))
    emit(head_transform(BASE, os.path.join(a.out_dir, 'head_tilt_other.png'),
                        rotate=-11.0, tag='tilt-other'))
    emit(head_transform(BASE, os.path.join(a.out_dir, 'head_nod.png'),
                        dy=9, scale=0.97, tag='nod'))
    # 点头的"回位"帧: 头部略微抬起 → 与 head_nod 组成 点头→回位 的两帧动作
    emit(head_transform(BASE, os.path.join(a.out_dir, 'head_nod_back.png'),
                        dy=-6, scale=1.0, rotate=-3.0, tag='nod-back'))
    emit(head_transform(BASE, os.path.join(a.out_dir, 'glance_left.png'),
                        dx=-11, dy=2, scale=0.985, rotate=-3.0, tag='glance-left'))
    emit(head_transform(BASE, os.path.join(a.out_dir, 'glance_right.png'),
                        dx=11, dy=2, scale=0.985, rotate=3.0, tag='glance-right'))
    # 开心: 歪头 + 眯眼
    tmp = os.path.join(a.out_dir, '_tmp_happy_tilt.png')
    head_transform(BASE, tmp, rotate=9.0, tag='happy-tilt')
    emit(face_swap(tmp, DONOR_CLOSED, os.path.join(a.out_dir, 'happy.png'), tag='tilt'))
    os.remove(tmp)

    # --- C. 躺姿呼吸 ---
    # 幅度说明: 1024 纹理 → 200x240 紧凑窗口的缩放约 0.244,
    #   amount=0.045 对应屏上约 3px (=身高的 1.2%), 肉眼可辨但不夸张;
    #   更小的幅度 (0.022) 在真实窗口里只有 1.4px, 等于"看不到变化" (用户反馈"几乎没有变化")。
    emit(torso_breath(SLEEP_STABLE, os.path.join(a.out_dir, 'sleep_breath_in.png'),
                      chest_box=(300, 430, 700, 700), amount=0.045, tag='breath-in'))
    emit(torso_breath(SLEEP_STABLE, os.path.join(a.out_dir, 'sleep_breath_out.png'),
                      chest_box=(300, 430, 700, 700), amount=-0.030, tag='breath-out'))

    rep_path = os.path.join(a.out_dir, 'bake_report.json')
    with open(rep_path, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"  📄 {rep_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
