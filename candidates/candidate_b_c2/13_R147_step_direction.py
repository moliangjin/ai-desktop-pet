#!/usr/bin/env python3
"""R147 步态方向判定 — 逐帧判定"哪只脚在前", 从而得出真实迈步方向。

原理:
  R138 行走素材是正面 3/4 视角。迈步的前脚 = 画得更靠下(离镜头更近)的那只脚。
  做法:
    1. 取角色 bbox 底部 30% 的水平带
    2. 用颜色把"鞋/靴"像素分离出来 (低亮度 + 偏蓝), 排除皮肤(R>G>B)与浅色袜子
    3. 按列聚成左右两只脚, 记录每只脚的 x 中心与鞋底 y (该列最低的不透明像素)
    4. 鞋底 y 更大的 = 前脚
    5. 前脚在角色右边 → 向右迈; 前脚在角色左边 → 向左迈
输出逐帧方向序列, 并检查 4 帧循环是否闭合。
"""
import os
import json
import argparse

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "assets", "character_R141_manifest.json")
ASSET_ROOT = os.path.join(HERE, "assets")


def load_action(action):
    if action.endswith("_orig"):
        real = action[:-5]
        d = os.path.join(ASSET_ROOT, "character_R138", real)
        files = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
        return [(f, Image.open(os.path.join(d, f)).convert("RGBA")) for f in files]
    m = json.load(open(MANIFEST, encoding="utf-8"))
    spec = m["actions"][action]
    return [(os.path.basename(r), Image.open(os.path.join(ASSET_ROOT, r)).convert("RGBA"))
            for r in spec["frames"]]


def feet_of(im):
    arr = np.array(im)
    a = arr[:, :, 3]
    ys, xs = np.where(a > 40)
    if len(xs) == 0:
        return None
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    h = y1 - y0
    band_y0 = y0 + int(h * 0.70)
    rgb = arr[:, :, :3].astype(int)
    R, G, B = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    lum = 0.299 * R + 0.587 * G + 0.114 * B
    shoe = (a > 40) & (lum < 175) & (B - R > 4)
    shoe[:band_y0, :] = False
    cols = np.where(shoe.any(axis=0))[0]
    if len(cols) == 0:
        return None
    # 按列间隙切成两只脚
    groups = []
    start = cols[0]
    prev = cols[0]
    for c in cols[1:]:
        if c - prev > 6:
            groups.append((start, prev))
            start = c
        prev = c
    groups.append((start, prev))
    if len(groups) < 2:
        return None
    # 合并过近的组 (同一只鞋被袜口/靴筒切断)
    merged = [list(groups[0])]
    for g in groups[1:]:
        if g[0] - merged[-1][1] <= 10:
            merged[-1][1] = g[1]
        else:
            merged.append(list(g))
    if len(merged) < 2:
        return None
    # 取最左与最右两组
    feet = []
    for (gx0, gx1) in (merged[0], merged[-1]):
        sub = shoe[:, gx0:gx1 + 1]
        rows = np.where(sub.any(axis=1))[0]
        if len(rows) == 0:
            return None
        feet.append(dict(x0=int(gx0), x1=int(gx1),
                         xc=(gx0 + gx1) / 2.0,
                         sole=int(rows.max())))
    return feet


def analyze(action, label):
    frames = load_action(action)
    print(f"\n=== {label} ===")
    seq = []
    for name, im in frames:
        feet = feet_of(im)
        if not feet:
            print(f"  {name:34s} 未能分离出两只脚")
            seq.append(None)
            continue
        L, R = feet[0], feet[1]
        # 前脚 = 鞋底 y 更大(更靠下)的那只
        if L['sole'] >= R['sole']:
            fwd, back, side = L, R, '左'
        else:
            fwd, back, side = R, L, '右'
        # 前脚相对后脚的水平位移 → 迈步方向
        dx = fwd['xc'] - back['xc']
        direction = '右' if dx > 0 else '左'
        print(f"  {name:34s} 左脚(x={L['xc']:.0f},sole={L['sole']}) "
              f"右脚(x={R['xc']:.0f},sole={R['sole']}) → 前脚={side}脚 "
              f"前移dx={dx:+.0f} → 迈步方向={direction}")
        seq.append((direction, side, dx))
    dirs = [s[0] for s in seq if s]
    print(f"  方向序列: {''.join(dirs)}")
    alt = all(dirs[i] != dirs[i + 1] for i in range(len(dirs) - 1)) if len(dirs) > 1 else False
    print(f"  迈步是否左右交替: {'是 (跨步循环)' if alt else '否 (同向/横滑)'}")
    return seq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(ASSET_ROOT, "character_R138"))
    a = ap.parse_args()
    l = analyze("walk_left_orig", "walk_left (R138 原始)")
    r = analyze("walk_right_orig", "walk_right (R138 原始)")


if __name__ == "__main__":
    main()
