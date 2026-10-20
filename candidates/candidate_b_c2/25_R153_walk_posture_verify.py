#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R153 行走姿态客观测量 (像素级, 不依赖坐标符号/动画名)

用户真机反馈 (R153):
    "行走时身体明显前倾, 像要摔倒"

R153 的判定与修复:
    · R147/R148 用**整体水平错切** (skew_x) 表达"行走方向":
        walk_left  k = +0.085  → 上半身整体左移
        walk_right k = -0.11   → 上半身整体右移
      这种整体错切让身体偏离垂直轴, 在 200x240 的紧凑窗口里
      观感就是"上半身往前栽", 用户明确反馈"像要摔倒"。
    · R148 已经用**派生镜像帧**把"迈步方向"修对了 (鞋尖几何客观测量 PASS),
      方向表达不再依赖错切 ⇒ R153 把 walk_*.lean.skew_x 归零。

本脚本做三件事:
    1. 用**与 renderer/PixiJS 完全相同的顶点变换**把真实帧错切出来,
       在像素上测量"上半身重心相对下半球的水平偏移 / 身高" (前倾量)。
    2. 输出 k=0.085 / k=-0.11 / k=0 三种情况的真实渲染对比图 (肉眼可复核)。
    3. 给出 PASS/FAIL 判定: R153 归零后的前倾量必须显著小于 R148 旧值,
       且低于"站姿端正"的物理门槛 (上身重心偏移 < 身高 3%)。

判定不依赖:
    · x 坐标正负
    · 动画名
    · 本脚本自身的 PASS
全部来自对**真实像素**的测量。

产物:
    evidence_r153_posture.json        测量数据 + 判定
    evidence_r153_posture/posture_compare.png   三态渲染对比图
    evidence_r153_posture/posture_k0.png / posture_k0085.png ...
"""

import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
OUT_DIR = os.path.join(CAND, 'evidence_r153_posture')
OUT_JSON = os.path.join(CAND, 'evidence_r153_posture.json')

# 与 src/sprite_layout.js 的 DEFAULT_ANCHOR 一致
ANCHOR_X = 0.5
ANCHOR_Y = 0.9
CANVAS = 1024

# R148 旧值 (manifest 改动前的 skew_x)
K_R148_LEFT = 0.085
K_R148_RIGHT = -0.11

# 站姿端正门槛: 上半身重心相对下半身重心的水平偏移 < 身高的 3%
LEAN_RATIO_LIMIT = 0.03

# R148 旧值的相对倍率上限: 归零后前倾量不得高于旧值的 45%
REDUCTION_RATIO_LIMIT = 0.45


def load_manifest():
    with open(os.path.join(ASSETS, 'character_R141_manifest.json'), encoding='utf-8') as f:
        return json.load(f)


def alpha_mask(path):
    im = Image.open(path).convert('RGBA')
    a = np.asarray(im)[:, :, 3]
    return a > 24, np.asarray(im)


def shear_render(rgba, k):
    """按 PixiJS 顶点语义施加整体水平错切 k (与 sprite_layout.js 一致)。

    PixiJS:  screen_x = pos.x + s*(lx + k*ly),  screen_y = pos.y + s*cosθ*ly
    局部:    lx = u - ax*W,  ly = v - ay*H,  cosθ = sqrt(1-k²)

    输出图像坐标系 (与纹理同尺寸 1024x1024):
        Xo = local_x + W/2        (local_x = lx + k*ly)
        Yo = local_y + ay*H       (local_y = cosθ*ly)
    即输出图覆盖 local_x ∈ [-W/2, W/2], local_y ∈ [-ay*H, H-ay*H]。

    逆映射 (输出 → 输入, AFFINE 需要):
        v = (Yo - ay*H)/cosθ + ay*H
        u = Xo - k*(v - ay*H)   (因为 local_x = u - ax*W + k*ly, 且 ax*W = W/2)
    """
    if k == 0:
        return rgba.copy()
    im = Image.fromarray(rgba, 'RGBA')
    cos_t = np.sqrt(max(0.0, 1.0 - k * k))
    ay_h = ANCHOR_Y * CANVAS
    coeffs = (1.0, -k / cos_t, k * ay_h / cos_t,
              0.0, 1.0 / cos_t, ay_h - ay_h / cos_t)
    return im.transform(im.size, Image.AFFINE, coeffs, resample=Image.BILINEAR)


def measure_lean(mask):
    """像素级测量"上半身重心相对下半身重心的水平偏移 / 身高"。

    上半身带 = 剪影竖直范围顶部 30%
    下半身带 = 剪影竖直范围底部 30%
    lean_ratio = (cx_upper - cx_lower) / height
      > 0 → 上半身偏向画面右侧 (右倾)
      < 0 → 上半身偏向画面左侧 (左倾)
    绝对值越大 = 身体越偏离垂直轴 = 越像"要摔倒"。
    """
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    top, bottom = ys.min(), ys.max()
    height = bottom - top
    if height <= 0:
        return None

    def band_centroid(y0, y1):
        sel = (ys >= y0) & (ys < y1)
        if sel.sum() < 8:
            return None
        return float(xs[sel].mean()), float(ys[sel].mean()), int(sel.sum())

    up = band_centroid(top, top + height * 0.30)
    lo = band_centroid(bottom - height * 0.30, bottom + 1)
    if up is None or lo is None:
        return None
    # 重心差 (用身体中线作为参考, 避免剪影本身左右不对称干扰)
    mid_x = (xs.min() + xs.max()) / 2.0
    lean_px = (up[0] - mid_x) - (lo[0] - mid_x)
    return {
        'height_px': int(height),
        'upper_cx': round(up[0], 2),
        'lower_cx': round(lo[0], 2),
        'lean_px': round(lean_px, 2),
        'lean_ratio': round(lean_px / height, 5),
        'lean_deg': round(float(np.degrees(np.arctan2(lean_px, height))), 3),
    }


def group_measure(frames, k):
    rows = []
    for rel in frames:
        path = os.path.join(ASSETS, rel)
        mask, rgba = alpha_mask(path)
        m = measure_lean(mask)
        if m is None:
            continue
        m['frame'] = rel
        # 同时测量"施加错切之后"的量 (真实运行时观感)
        warped = shear_render(rgba, k)
        wmask = np.asarray(warped)[:, :, 3] > 24
        mw = measure_lean(wmask)
        m['lean_ratio_with_skew'] = mw['lean_ratio'] if mw else None
        m['lean_deg_with_skew'] = mw['lean_deg'] if mw else None
        rows.append(m)
    ratios = [abs(r['lean_ratio']) for r in rows]
    warped = [abs(r['lean_ratio_with_skew']) for r in rows if r['lean_ratio_with_skew'] is not None]
    return {
        'frames': rows,
        'source_lean_ratio_mean': round(float(np.mean(ratios)), 5) if ratios else None,
        'source_lean_ratio_max': round(float(np.max(ratios)), 5) if ratios else None,
        'skew_lean_ratio_mean': round(float(np.mean(warped)), 5) if warped else None,
        'skew_lean_ratio_max': round(float(np.max(warped)), 5) if warped else None,
        'skew_lean_deg_mean': round(float(np.mean(
            [abs(r['lean_deg_with_skew']) for r in rows if r['lean_deg_with_skew'] is not None])), 3)
        if warped else None,
    }


def make_compare_png(manifest, out_path):
    """渲染 k=0.085 / k=-0.11 / k=0 三态, 并排输出真实渲染对比图。"""
    wl = manifest['actions']['walk_left']['frames'][0]
    wr = manifest['actions']['walk_right']['frames'][0]

    panels = []
    for label, rel, k in (('R148 walk_left  k=+0.085', wl, K_R148_LEFT),
                          ('R148 walk_right k=-0.110', wr, K_R148_RIGHT),
                          ('R153 walk_left  k= 0.000', wl, 0.0),
                          ('R153 walk_right k= 0.000', wr, 0.0)):
        mask, rgba = alpha_mask(os.path.join(ASSETS, rel))
        warped = shear_render(rgba, k)
        a = np.asarray(warped)
        # 合成到中性深色背景上 (只看轮廓与倾斜, 不看原画配色)
        bg = np.zeros_like(a)
        bg[:, :, 0] = 26
        bg[:, :, 1] = 28
        bg[:, :, 2] = 34
        bg[:, :, 3] = 255
        al = a[:, :, 3:4].astype(np.float32) / 255.0
        comp = (a[:, :, :3].astype(np.float32) * al + bg[:, :, :3].astype(np.float32) * (1 - al))
        comp = comp.astype(np.uint8)
        panels.append((label, comp, k))

    # 裁到统一内容框并按身高对齐缩放, 便于肉眼比较倾斜
    cell = 420
    cols = 4
    canvas = Image.new('RGB', (cell * cols, cell + 46), (18, 19, 24))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(canvas)
    for i, (label, comp, k) in enumerate(panels):
        im = Image.fromarray(comp, 'RGB')
        ys, xs = np.nonzero(np.asarray(Image.fromarray(comp, 'RGB')).sum(axis=2) > 40)
        if len(xs) == 0:
            continue
        bbox = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        crop = im.crop(bbox)
        h = crop.height
        sc = (cell - 24) / float(h)
        crop = crop.resize((max(1, int(crop.width * sc)), cell - 24), Image.LANCZOS)
        x0 = i * cell + (cell - crop.width) // 2
        y0 = 24 + (cell - 24 - crop.height) // 2
        canvas.paste(crop, (x0, y0))
        draw.text((i * cell + 10, 6), label, fill=(225, 228, 235))
    canvas.save(out_path)
    return out_path


def main():
    manifest = load_manifest()
    wl_frames = manifest['actions']['walk_left']['frames']
    wr_frames = manifest['actions']['walk_right']['frames']

    cur_left = manifest['actions']['walk_left'].get('lean', {}).get('skew_x')
    cur_right = manifest['actions']['walk_right'].get('lean', {}).get('skew_x')

    left_old = group_measure(wl_frames, K_R148_LEFT)
    right_old = group_measure(wr_frames, K_R148_RIGHT)
    left_new = group_measure(wl_frames, 0.0)
    right_new = group_measure(wr_frames, 0.0)

    os.makedirs(OUT_DIR, exist_ok=True)
    cmp_png = os.path.join(OUT_DIR, 'posture_compare.png')
    make_compare_png(manifest, cmp_png)

    # 判定
    new_max = max(left_new['source_lean_ratio_max'], right_new['source_lean_ratio_max'])
    old_max = max(left_old['skew_lean_ratio_max'], right_old['skew_lean_ratio_max'])
    reduction = (new_max / old_max) if old_max > 0 else None

    checks = []
    checks.append({
        'name': 'manifest 行走错切已归零',
        'pass': (cur_left == 0.0 and cur_right == 0.0),
        'detail': f"walk_left.skew_x={cur_left} walk_right.skew_x={cur_right}",
    })
    checks.append({
        'name': f'归零后上半身偏心 < 身高的 {LEAN_RATIO_LIMIT*100:.0f}% (站姿端正)',
        'pass': new_max < LEAN_RATIO_LIMIT,
        'detail': f"实测最大 |lean_ratio| = {new_max:.5f} (门槛 {LEAN_RATIO_LIMIT})",
    })
    checks.append({
        'name': f'相对 R148 旧错切的前倾量降至 {REDUCTION_RATIO_LIMIT*100:.0f}% 以下',
        'pass': (reduction is not None and reduction <= REDUCTION_RATIO_LIMIT),
        'detail': f"旧最大 {old_max:.5f} → 新最大 {new_max:.5f}, 保留比例 {reduction*100:.1f}%"
        if reduction is not None else '无法计算',
    })

    result = {
        'metric': '上半身重心相对下半身重心的水平偏移 / 角色身高 (像素级测量, 非坐标符号)',
        'lean_ratio_limit': LEAN_RATIO_LIMIT,
        'reduction_ratio_limit': REDUCTION_RATIO_LIMIT,
        'current_manifest_skew': {'walk_left': cur_left, 'walk_right': cur_right},
        'groups': {
            'walk_left_R148_skew': left_old,
            'walk_right_R148_skew': right_old,
            'walk_left_R153_k0': left_new,
            'walk_right_R153_k0': right_new,
        },
        'summary': {
            'old_max_lean_ratio': round(old_max, 5),
            'new_max_lean_ratio': round(new_max, 5),
            'reduction_ratio': round(reduction, 4) if reduction is not None else None,
            'old_max_lean_deg': round(max(
                left_old['skew_lean_deg_mean'] or 0, right_old['skew_lean_deg_mean'] or 0), 3),
        },
        'compare_png': os.path.relpath(cmp_png, CAND),
        'checks': checks,
        'verdict': 'PASS' if all(c['pass'] for c in checks) else 'FAIL',
    }

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print('R153 行走姿态客观测量')
    print(f"  旧错切 (R148) 最大前倾量 = {old_max:.5f} 身高 "
          f"(≈ {np.degrees(np.arctan2(old_max,1)):.2f}°)")
    print(f"  归零后 (R153) 最大前倾量 = {new_max:.5f} 身高")
    if reduction is not None:
        print(f"  保留比例 = {reduction*100:.1f}% (门槛 ≤ {REDUCTION_RATIO_LIMIT*100:.0f}%)")
    for c in checks:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['name']} — {c['detail']}")
    print(f"  对比图: {os.path.relpath(cmp_png, CAND)}")
    print(f"  判定: {result['verdict']}")
    return 0 if result['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
