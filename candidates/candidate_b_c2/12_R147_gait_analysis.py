#!/usr/bin/env python3
"""R147 步态方向定量分析 — 判定"倒着走"的真实根因。

不依赖肉眼印象, 用三个可测量指标回答:
  1. 躯干轴倾角 (肩中心 → 胯中心)  : 身体朝哪边倾, 与窗口移动方向是否一致
  2. 双脚间距序列                  : 该帧序是否构成闭合循环 (循环接缝是否跳变)
  3. 前后脚判定 (鞋底 y 差)        : 迈步顺序是否交替 (会不会同手同脚/横滑)

用法: python3 12_R147_gait_analysis.py
输出: 文本表格 + /tmp/r147_gait_zoom.png (腿脚放大对比)
"""

import os
import json
import argparse

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "assets", "character_R141_manifest.json")
ASSET_ROOT = os.path.join(HERE, "assets")


def load_action(action):
    """按 manifest 取帧。action 名带 '_orig' 后缀时直接取 R138 原始目录
    (R147 运行时 manifest 已把 walk_left 指向 walk_right 的跨步循环,
     分析原始素材必须绕开 manifest)。"""
    if action.endswith("_orig"):
        real = action[:-5]
        d = os.path.join(ASSET_ROOT, "character_R138", real)
        files = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
        return [(f, Image.open(os.path.join(d, f)).convert("RGBA")) for f in files]
    m = json.load(open(MANIFEST, encoding="utf-8"))
    spec = m["actions"][action]
    out = []
    for rel in spec["frames"]:
        out.append((os.path.basename(rel),
                    Image.open(os.path.join(ASSET_ROOT, rel)).convert("RGBA")))
    return out


def alpha_bbox(im):
    return im.getchannel("A").getbbox()


def slice_rows(im, y0, y1):
    """取指定行区间的非透明像素列区间 (用于分区定位身体部位)。"""
    a = im.getchannel("A")
    w, h = im.size
    y0 = max(0, int(y0)); y1 = min(h, int(y1))
    if y1 <= y0:
        return None
    band = a.crop((0, y0, w, y1))
    bb = band.getbbox()
    if not bb:
        return None
    return (bb[0], y0, bb[2], y1)


def center_x(im, y0, y1):
    """该水平带内不透明像素的重心 x。"""
    a = im.getchannel("A")
    w, h = im.size
    y0 = max(0, int(y0)); y1 = min(h, int(y1))
    if y1 <= y0:
        return None
    band = a.crop((0, y0, w, y1))
    bb = band.getbbox()
    if not bb:
        return None
    region = band.crop(bb)
    px = region.load()
    rw, rh = region.size
    tot = 0
    acc = 0
    for yy in range(rh):
        for xx in range(rw):
            v = px[xx, yy]
            if v:
                tot += v
                acc += v * (xx + bb[0])
    if tot == 0:
        return None
    return acc / tot


def shoe_boxes(im):
    """在图的下半部找两只鞋 (暗色连通块), 返回 (left_shoe, right_shoe) 的 bbox。"""
    import numpy as np
    arr = np.array(im)
    a = arr[:, :, 3]
    bb = alpha_bbox(im)
    if not bb:
        return None, None
    x0, y0, x1, y1 = bb
    h = y1 - y0
    # 鞋区: 整体底部往上 26% (足够覆盖小腿下段与鞋)
    shoe_y0 = y0 + int(h * 0.74)
    sub = a[shoe_y0:y1, :]
    cols = np.where(sub.max(axis=0) > 40)[0]
    if len(cols) == 0:
        return None, None
    # 找列间隙, 切成两组 (间隙阈值放宽, 交叉腿时两只鞋仍可分)
    gaps = []
    for i in range(1, len(cols)):
        if cols[i] - cols[i - 1] >= 4:
            gaps.append(i)
    if not gaps:
        # 只有一只鞋 / 连成一片
        return None, None
    # 取"最大间隙"作为左右分界
    best = max(range(len(gaps)), key=lambda i: cols[gaps[i]] - cols[gaps[i] - 1])
    left_cols = cols[:gaps[best]]
    right_cols = cols[gaps[best]:]

    def bbox_of(cs):
        if len(cs) == 0:
            return None
        rx0, rx1 = int(cs.min()), int(cs.max())
        band = a[shoe_y0:y1, rx0:rx1 + 1]
        rows = np.where(band.max(axis=1) > 40)[0]
        if len(rows) == 0:
            return None
        return (rx0, shoe_y0 + int(rows.min()), rx1, shoe_y0 + int(rows.max()))
    return bbox_of(left_cols), bbox_of(right_cols)


def analyze(action):
    frames = load_action(action)
    rows = []
    for name, im in frames:
        bb = alpha_bbox(im)
        x0, y0, x1, y1 = bb
        h = y1 - y0
        # 躯干带: 从上 18% 到上 48%
        sh = center_x(im, y0 + h * 0.18, y0 + h * 0.30)      # 肩
        hip = center_x(im, y0 + h * 0.46, y0 + h * 0.56)     # 胯
        ls, rs = shoe_boxes(im)
        lcx = (ls[0] + ls[2]) / 2 if ls else None
        rcx = (rs[0] + rs[2]) / 2 if rs else None
        lby = ls[3] if ls else None
        rby = rs[3] if rs else None
        rows.append(dict(
            name=name, bbox=bb,
            torso_tilt=(sh - hip) if (sh is not None and hip is not None) else None,
            shoulder_x=sh, hip_x=hip,
            left_shoe_x=lcx, right_shoe_x=rcx,
            spread=(rcx - lcx) if (lcx is not None and rcx is not None) else None,
            left_shoe_bottom=lby, right_shoe_bottom=rby,
        ))
    return rows


def print_table(action, rows):
    print(f"\n=== {action} ===")
    print(f"{'frame':34s} {'躯干倾角(肩-胯)':>16s} {'左鞋x':>8s} {'右鞋x':>8s} {'间距':>7s} {'左鞋底y':>9s} {'右鞋底y':>9s}")
    for r in rows:
        t = f"{r['torso_tilt']:.1f}" if r['torso_tilt'] is not None else "n/a"
        lx = f"{r['left_shoe_x']:.0f}" if r['left_shoe_x'] is not None else "n/a"
        rx = f"{r['right_shoe_x']:.0f}" if r['right_shoe_x'] is not None else "n/a"
        sp = f"{r['spread']:.0f}" if r['spread'] is not None else "n/a"
        ly = f"{r['left_shoe_bottom']}" if r['left_shoe_bottom'] is not None else "n/a"
        ry = f"{r['right_shoe_bottom']}" if r['right_shoe_bottom'] is not None else "n/a"
        print(f"{r['name']:34s} {t:>16s} {lx:>8s} {rx:>8s} {sp:>7s} {ly:>9s} {ry:>9s}")
    # 循环闭合度: 末帧→首帧 与 帧内相邻步 的差异
    spreads = [r['spread'] for r in rows if r['spread'] is not None]
    if len(spreads) >= 2:
        deltas = [abs(spreads[i + 1] - spreads[i]) for i in range(len(spreads) - 1)]
        wrap = abs(spreads[0] - spreads[-1])
        avg = sum(deltas) / len(deltas)
        print(f"  间距序列={spreads}")
        print(f"  帧内相邻平均变化={avg:.1f}  循环接缝变化(末→首)={wrap:.1f}  "
              f"接缝/帧内={wrap/avg if avg else float('inf'):.2f}  "
              f"{'闭合循环 OK' if avg and wrap/avg < 1.8 else '接缝跳变 (非闭合循环)'}")
    tilts = [r['torso_tilt'] for r in rows if r['torso_tilt'] is not None]
    if tilts:
        avg_t = sum(tilts) / len(tilts)
        print(f"  躯干平均倾角={avg_t:.1f} (正=向右倾)  → 朝向={'向右' if avg_t > 2 else ('向左' if avg_t < -2 else '基本正直')}")


def make_zoom(out):
    """把两组的腿脚区放大拼到一张图, 便于核对迈步顺序。"""
    wl = load_action("walk_left_orig")
    wr = load_action("walk_right_orig")
    cells = []
    for tag, frames in (("walk_left", wl), ("walk_right", wr)):
        for name, im in frames:
            bb = alpha_bbox(im)
            x0, y0, x1, y1 = bb
            h = y1 - y0
            crop = im.crop((x0 - 10, y0 + int(h * 0.62), x1 + 10, y1 + 6))
            crop = crop.resize((crop.size[0] * 2, crop.size[1] * 2), Image.LANCZOS)
            cells.append((f"{tag}/{name}", crop))
    cw = max(c.size[0] for _, c in cells) + 16
    ch = max(c.size[1] for _, c in cells) + 26
    cols = 4
    rowsn = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cw * cols, (ch) * rowsn), (250, 250, 252))
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheet)
    for i, (label, c) in enumerate(cells):
        cx = (i % cols) * cw + 8
        cy = (i // cols) * ch + 22
        sheet.paste(c.convert("RGB"), (cx, cy))
        d.text((cx, cy - 16), label, fill=(20, 20, 30))
    sheet.save(out)
    print("\n放大图:", out, sheet.size)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom-out", default="/tmp/r147_gait_zoom.png")
    a = ap.parse_args()
    for act in ("walk_left_orig", "walk_right_orig"):
        print_table(act, analyze(act))
    make_zoom(a.zoom_out)
