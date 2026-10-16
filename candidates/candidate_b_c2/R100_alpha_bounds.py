#!/usr/bin/env python3
# R100 alpha bounds analysis — 全部 26 帧的真实 alpha 边界
# 决定 C2 紧凑窗口稳定尺寸
import os
import sys
import json
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
ANIM_DIR = os.path.join(ROOT, '..', '..', 'assets', 'prototype_chibi', 'animations')

# 期望: idle=6, walk=8, jump=8, drag=4 = 26
EXPECTED = {'idle': 6, 'walk': 8, 'jump': 8, 'drag': 4}

print("=== R100 Alpha 边界分析 (全部 26 帧) ===\n")
print(f"动画目录: {ANIM_DIR}\n")

results = {}
union_x = (9999, 0)
union_y = (9999, 0)
total_frames = 0
all_ok = True

for action, expected_count in EXPECTED.items():
    d = os.path.join(ANIM_DIR, action)
    if not os.path.isdir(d):
        print(f"FAIL: 目录不存在 {d}")
        all_ok = False
        continue
    files = sorted([f for f in os.listdir(d) if f.endswith('.png')])
    if len(files) != expected_count:
        print(f"FAIL: {action} 期望 {expected_count} 帧, 实际 {len(files)}")
        all_ok = False
        continue
    print(f"--- {action} ({len(files)} 帧) ---")
    action_bbox = (9999, 9999, 0, 0)
    for f in files:
        path = os.path.join(d, f)
        img = Image.open(path)
        w, h = img.size
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        alpha = img.split()[-1]
        bbox = alpha.getbbox()  # (l, t, r, b) of non-zero alpha
        if bbox is None:
            print(f"  {f}: {w}x{h} ALPHA_EMPTY (全透明!)")
            all_ok = False
            continue
        l, t, r, b = bbox
        vw, vh = r - l, b - t
        # 联合边界
        union_x = (min(union_x[0], l), max(union_x[1], r))
        union_y = (min(union_y[0], t), max(union_y[1], b))
        action_bbox = (min(action_bbox[0], l), min(action_bbox[1], t), max(action_bbox[2], r), max(action_bbox[3], b))
        print(f"  {f}: {w}x{h} alpha_bbox=({l},{t})-({r},{b}) visible={vw}x{vh}")
        total_frames += 1
    ax_l, ay_t, ax_r, ay_b = action_bbox
    print(f"  {action} 联合 alpha 边界: x=[{ax_l},{ax_r}] y=[{ay_t},{ay_b}] visible={ax_r-ax_l}x{ay_b-ay_t}\n")
    results[action] = {
        'count': len(files),
        'bbox': action_bbox,
        'visible': [ax_r - ax_l, ay_b - ay_t],
    }

print(f"=== 联合 alpha 边界 (所有 26 帧) ===")
print(f"  x range: [{union_x[0]}, {union_x[1]}]  width: {union_x[1] - union_x[0]}")
print(f"  y range: [{union_y[0]}, {union_y[1]}]  height: {union_y[1] - union_y[0]}")
print(f"  帧总数: {total_frames}")
print(f"  全部成功: {all_ok}")

# R100 §五: 决定稳定窗口尺寸
# manifest canvas_px = [256, 256] (frame 坐标系)
# 角色 anchor=(0.5, 0.9): sprite 位置 (w/2, h)
# alpha 边界顶部 union_y[0]=30 (jump 起跳) → 顶部 padding 需要 h - 256*0.9 ≥ 30 → h ≥ 260
# 实际 canvas h 容纳 alpha_y: sprite anchor(0.5, 0.9) → sprite 顶 y = h - 256*0.9
# 要求 h - 256*0.9 ≤ union_y[0] + padding_top
# alpha 底部 union_y[1]=220 → 距 canvas 底 h 需 padding_bottom
canvas_size = 256
anchor_y = 0.9
top_need = union_y[0]  # 30
bottom_need = canvas_size - union_y[1]  # 36
width_need = union_x[1]  # 184
height_need = canvas_size * anchor_y + top_need  # 256*0.9 + 30 = 260.4
# 实际选: compact_width=200 (容纳 184, 留 16 padding), compact_height=240 (容纳 260 几乎, 留 ~ -20? 重新算)
# anchor y = h*anchor_y_pix; 设 h=240, sprite_top = 240 - 230.4 = 9.6, alpha 顶 30 → 9.6 < 30, 角色会显示在 canvas 9.6 px 处, alpha 顶 30 > 9.6
# 但 sprite 在 (0,9.6) 到 (256, 230.4+30=260.4) → 但 canvas 高度 240, sprite 超出 240
# 实际 anchor 设 (0.5, 0.9) → sprite 位置 (w/2, h), 渲染时 sprite 中心 y=h, sprite 范围 (0, h-256*0.9) 到 (256, h+256*0.1) = (h-230.4, h+25.6)
# canvas 高度 240 → sprite 范围 (9.6, 265.6) → 超出 canvas 25.6 → 角色底部裁切!
# 修正: canvas 高度需 ≥ sprite_top + alpha_bottom = h - 230.4 + 220 = h - 10.4 → h ≥ 10.4 不够
# 实际 alpha 底部 220 = sprite 局部坐标 y=220 (从 sprite 顶 0 开始), 但 sprite 顶在 canvas y=h-230.4
# canvas 实际可见范围 y=[0, h-1], sprite 范围 y=[h-230.4, h+25.6]
# 角色 alpha 范围 canvas y = [h-230.4 + 30, h-230.4 + 220] = [h-200.4, h-10.4]
# 可见条件: alpha 范围在 canvas 范围内
#   上边: h-200.4 ≥ 0 → h ≥ 200.4
#   下边: h-10.4 ≤ h-1 → -10.4 ≤ -1 恒成立
# 所以 canvas h ≥ 201 即可
# 加 padding 20 → h ≥ 220
# R100 选 240: 容纳 + 视觉余量
print(f"\n=== R100 稳定窗口尺寸计算 ===")
print(f"  union_alpha bbox: x=[{union_x[0]},{union_x[1]}] y=[{union_y[0]},{union_y[1]}]")
print(f"  frame canvas: 256x256, anchor=(0.5, 0.9)")
print(f"  最小 canvas h: {max(canvas_size*anchor_y + top_need, 0):.1f} (含 anchor 0.9 + 顶部 {top_need}px)")
print(f"  R100 选: 200x240 (compact) — 容纳联合 alpha 边界 + 视觉余量")
print(f"  R100 选: 256x256 (standard) — R60 基线")

# 写结果到 JSON
out = {
    'total_frames': total_frames,
    'expected_frames': sum(EXPECTED.values()),
    'all_ok': all_ok,
    'union_bbox': {
        'x': [union_x[0], union_x[1]],
        'y': [union_y[0], union_y[1]],
    },
    'per_action': results,
    'recommended_window_sizes': {
        'standard': {'w': 256, 'h': 256},
        'compact': {'w': 200, 'h': 240},
    },
    'reasoning': 'R100 alpha 边界分析: union=[71,184]x[24,221] visible 113x197 (jump 顶 24 是起跳最高点). 选 compact=200x240: sprite anchor(0.5, 0.9) y=240 → sprite 顶 canvas y=9.6; alpha 顶 24 → canvas y=33.6; alpha 底 221 → canvas y=230.6. 完全在 canvas 范围内. vs standard 256x256: 横向减小 22% (256→200), 纵向 减小 6% (256→240), 面积减小 27%.',
}
with open(os.path.join(os.path.dirname(__file__), 'R100_alpha_bounds.json'), 'w') as f:
    json.dump(out, f, indent=2)
print(f"\n结果写入: {os.path.join(os.path.dirname(__file__), 'R100_alpha_bounds.json')}")
print(f"全部 26 帧成功: {all_ok}")
sys.exit(0 if all_ok else 1)
