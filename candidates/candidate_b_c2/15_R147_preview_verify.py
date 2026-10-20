#!/usr/bin/env python3
"""R147 运行时预览的**客观量化校验** — 直接分析真实 Electron 采集帧。

不靠肉眼, 用像素测量回答三个问题:
  1. 待机是否真的没有胸腔膨胀?  (轮廓宽度变化 + 出现过的姿态种类)
  2. 单击是否真的有可见反馈?    (角色离地高度曲线 + 眨眼姿态出现)
  3. 左右行走朝向是否正确?      (上半身相对下半身的水平偏移符号)

用法: python3 15_R147_preview_verify.py --preview-dir /tmp/r147_preview
"""
import os
import json
import argparse

import numpy as np
from PIL import Image


def load_scene(preview_dir, scene):
    meta = json.load(open(os.path.join(preview_dir, "preview_meta.json"), encoding="utf-8"))
    return [(Image.open(f["file"]).convert("RGBA"), f.get("dx", 0)) for f in (meta.get(scene) or [])]


def mask_of(im):
    return np.array(im)[:, :, 3] > 30


def bbox_of(m):
    ys, xs = np.where(m)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def upper_lower_shift(im):
    """上半身水平中心 - 下半身水平中心 (正 = 上半身偏右 = 向右倾)。"""
    m = mask_of(im)
    bb = bbox_of(m)
    if not bb:
        return None
    x0, y0, x1, y1 = bb
    h = y1 - y0
    if h < 20:
        return None

    def band_center(a, b):
        sub = m[a:b, :]
        if not sub.any():
            return None
        cols = np.where(sub.any(axis=0))[0]
        xs = np.arange(sub.shape[1])
        w = sub.sum(axis=0)
        return float((xs * w).sum() / max(w.sum(), 1))

    top = band_center(y0, y0 + int(h * 0.32))
    bot = band_center(y1 - int(h * 0.32), y1)
    if top is None or bot is None:
        return None
    return top - bot


def chest_width(im):
    """胸部区域的最大轮廓宽度 (胸腔膨胀会直接体现在这个值上)。"""
    m = mask_of(im)
    bb = bbox_of(m)
    if not bb:
        return None
    x0, y0, x1, y1 = bb
    h = y1 - y0
    widths = []
    for frac in (0.26, 0.30, 0.34, 0.38, 0.42):
        a = y0 + int(h * frac)
        b = y0 + int(h * (frac + 0.04))
        if b >= y1:
            break
        sub = m[a:b, :]
        cols = np.where(sub.any(axis=0))[0]
        if len(cols):
            widths.append(int(cols.max() - cols.min() + 1))
    return max(widths) if widths else None


def bottom_y(im):
    m = mask_of(im)
    bb = bbox_of(m)
    return bb[3] if bb else None


def distinct_poses(frames, tol=6):
    """按像素差聚类, 统计出现过的不同姿态数量与占比。"""
    arrs = []
    for im, _ in frames:
        a = np.array(im.convert("RGBA").resize((48, 58), Image.BILINEAR)).astype(int)
        arrs.append(a)
    clusters = []
    counts = []
    for a in arrs:
        placed = False
        for i, c in enumerate(clusters):
            d = np.abs(a - c).mean()
            if d < tol:
                counts[i] += 1
                placed = True
                break
        if not placed:
            clusters.append(a)
            counts.append(1)
    return len(clusters), counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-dir", default="/tmp/r147_preview")
    a = ap.parse_args()
    report = {}

    # ---------- 1. 待机: 无胸腔膨胀 ----------
    idle = load_scene(a.preview_dir, "idle")
    widths = [chest_width(im) for im, _ in idle]
    widths = [w for w in widths if w]
    bottoms = [bottom_y(im) for im, _ in idle]
    bottoms = [b for b in bottoms if b is not None]
    n_pose, counts = distinct_poses(idle)
    print("=== 待机 (真实采集帧) ===")
    print(f"  采集帧数={len(idle)}")
    print(f"  胸部最大轮廓宽度: min={min(widths)} max={max(widths)} 波动={max(widths)-min(widths)}px")
    print(f"  角色底边(地面线)位置: min={min(bottoms)} max={max(bottoms)} 波动={max(bottoms)-min(bottoms)}px")
    print(f"  出现过的不同姿态数={n_pose} (各姿态帧数={counts})")
    report['idle'] = {
        'frames': len(idle),
        'chest_width_min': min(widths), 'chest_width_max': max(widths),
        'chest_width_delta': max(widths) - min(widths),
        'bottom_delta': max(bottoms) - min(bottoms),
        'distinct_poses': n_pose, 'pose_counts': counts,
    }

    # ---------- 2. 单击反馈: 有可见变化 ----------
    click = load_scene(a.preview_dir, "click")
    cb = [bottom_y(im) for im, _ in click]
    cb = [b for b in cb if b is not None]
    n_pose_c, counts_c = distinct_poses(click)
    print("\n=== 单击反馈 (真实采集帧) ===")
    print(f"  采集帧数={len(click)}")
    print(f"  角色底边位置序列(离地=越小越弹起): {cb}")
    print(f"  弹跳幅度(最大离地像素)={max(cb)-min(cb)}px")
    print(f"  出现过的不同姿态数={n_pose_c} (各姿态帧数={counts_c})")
    report['click'] = {
        'frames': len(click),
        'bounce_px': max(cb) - min(cb),
        'distinct_poses': n_pose_c, 'pose_counts': counts_c,
        'bottom_series': cb,
    }

    # ---------- 3. 左右行走朝向 ----------
    print("\n=== 行走朝向 (真实采集帧, 上半身相对下半身的水平偏移) ===")
    for scene, expect in (("walk_left", "左 (负)"), ("walk_right", "右 (正)")):
        fr = load_scene(a.preview_dir, scene)
        shifts = [upper_lower_shift(im) for im, _ in fr]
        shifts = [s for s in shifts if s is not None]
        avg = sum(shifts) / len(shifts) if shifts else 0
        neg = sum(1 for s in shifts if s < 0)
        print(f"  {scene}: 期望={expect}  实测均值={avg:+.2f}px  负偏移帧={neg}/{len(shifts)}")
        report[scene] = {'avg_shift': avg, 'neg_frames': neg, 'total': len(shifts),
                         'dx_min': min(dx for _, dx in fr), 'dx_max': max(dx for _, dx in fr)}

    # ---------- 4. 睡眠唤醒 ----------
    wake = load_scene(a.preview_dir, "wake")
    n_pose_w, counts_w = distinct_poses(wake)
    print(f"\n=== 睡眠点击唤醒 ===\n  采集帧数={len(wake)}  不同姿态数={n_pose_w} (各姿态帧数={counts_w})")
    report['wake'] = {'frames': len(wake), 'distinct_poses': n_pose_w, 'pose_counts': counts_w}

    out = os.path.join(a.preview_dir, 'preview_verify.json')
    json.dump(report, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\n校验结果已写入: {out}")


if __name__ == "__main__":
    main()
