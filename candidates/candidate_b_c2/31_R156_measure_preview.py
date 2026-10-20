#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R156 测量 + 场景合成预览 (在写 manifest / 改渲染器之前, 先把几何算准)。

要解决的两个真问题:
  1) **z 序**: 上一版场景预览把 床/沙发/转椅 画在了角色**前面**, 于是
     枕头盖住脸、沙发像浴缸、转椅底盘压住鞋。正确 z 序是:
         back 层 (月亮/床/沙发/转椅) → 角色 → front 层 (被子/桌子+笔记本/屏幕微光)
  2) **地面偏移 (ground_offset_px)**: 布局算法把"每帧内容底边"贴到同一条地面线。
     但有道具时, 真正的"地面"是**道具的底** (床脚/沙发底/桌腿底), 不是角色内容的底边。
     例如躺着时角色内容底边在纹理 y=690, 床脚在 y=818 → 角色需要整体抬高 128 纹理 px,
     否则床会掉到窗口外面 (超出画布被裁切)。

本脚本输出:
  · 每个帧的真实 alpha bbox (含 R138 核心帧 / R153 动作库帧 / R156 新烘焙帧)
  · 新的统一 scale / groundY / 逐帧地面线 (含 ground_offset)
  · 4 张**正确 z 序**的场景合成预览 (睡觉/沙发/办公/跳跃) 供目视复核

坐标系与运行时完全一致:
  纹理 1024x1024, anchor (0.5, 0.9) → anchor 纹理点 (512, 921.6)
  screen_y(v) = groundY + (v - content_bottom - ground_offset) * scale
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')

TEX = 1024
ANCHOR_Y = 0.9
ANCHOR_TEX_Y = ANCHOR_Y * TEX      # 921.6
MARGIN = 4

# 运行时画布 (compact 模式, 与 R153 实测一致)
CANVAS_W, CANVAS_H = 200, 240
GROUND_Y = CANVAS_H - MARGIN       # 236

# 场景地板 (纹理 y): 道具的底
FLOOR = {
    'stand': None,      # 无道具 → 用角色自身内容底边
    'sleep': 818,       # 床脚底
    'sit': 1001,        # 沙发底 (直接落地)
    'work': 1001,       # 桌腿底
}

FRAME_FILES = {
    # R138 核心
    'idle_00_base': 'character_R138/idle/idle_00_base.png',
    'idle_01_inhale_peak': 'character_R138/idle/idle_01_inhale_peak.png',
    'idle_02_exhale_mid': 'character_R138/idle/idle_02_exhale_mid.png',
    'idle_03_exhale_low': 'character_R138/idle/idle_03_exhale_low.png',
    'idle_04_blink_half': 'character_R138/idle/idle_04_blink_half.png',
    'idle_05_blink_closed': 'character_R138/idle/idle_05_blink_closed.png',
    'sleep_enter_01_sit': 'character_R138/sleep_enter/sleep_enter_01_sit.png',
    'sleep_enter_02_lie': 'character_R138/sleep_enter/sleep_enter_02_lie.png',
    'sleep_enter_03_settled': 'character_R138/sleep_enter/sleep_enter_03_settled.png',
    'sleep_loop_00_base': 'character_R138/sleep_loop/sleep_loop_00_base.png',
    'sleep_loop_01_breath_in': 'character_R138/sleep_loop/sleep_loop_01_breath_in.png',
    'sleep_loop_02_stable': 'character_R138/sleep_loop/sleep_loop_02_stable.png',
    'wake_up_00_lift': 'character_R138/wake_up/wake_up_00_lift.png',
    'wake_up_01_sit_up': 'character_R138/wake_up/wake_up_01_sit_up.png',
    'wake_up_02_stand': 'character_R138/wake_up/wake_up_02_stand.png',
    # R153 动作库
    'R153_happy': 'character_R153/happy.png',
    'R153_doze_sit': 'character_R153/doze_sit.png',
    'R153_sleep_breath_in': 'character_R153/sleep_breath_in.png',
    'R153_sleep_breath_out': 'character_R153/sleep_breath_out.png',
    'R153_head_tilt': 'character_R153/head_tilt.png',
    # R156 新烘焙
    'R156_cheer_heart_1': 'character_R156/cheer_heart_1.png',
    'R156_cheer_jump_0': 'character_R156/cheer_jump_0.png',
    'R156_cheer_jump_1': 'character_R156/cheer_jump_1.png',
    'R156_cheer_jump_2': 'character_R156/cheer_jump_2.png',
    'R156_cheer_spin_1': 'character_R156/cheer_spin_1.png',
    'R156_cheer_wink_0': 'character_R156/cheer_wink_0.png',
    'R156_cheer_wink_1': 'character_R156/cheer_wink_1.png',
    'R156_cheer_wink_2': 'character_R156/cheer_wink_2.png',
    'R156_cheer_hands_1': 'character_R156/cheer_hands_1.png',
    'R156_cheer_hands_2': 'character_R156/cheer_hands_2.png',
    'R156_work_1': 'character_R156/work_1.png',
    'R156_work_2': 'character_R156/work_2.png',
}

PROP_FILES = {
    'prop_bed': 'character_R156/prop_bed.png',
    'prop_quilt': 'character_R156/prop_quilt.png',
    'prop_moon': 'character_R156/prop_moon.png',
    'prop_sofa': 'character_R156/prop_sofa.png',
    'prop_chair': 'character_R156/prop_chair.png',
    'prop_desk': 'character_R156/prop_desk.png',
    'prop_screen_glow': 'character_R156/prop_screen_glow.png',
}


def alpha_bbox(path):
    """与 PIL getbbox() 一致: 非透明像素的最小外接矩形 (right/bottom 为开区间)。"""
    im = Image.open(path).convert('RGBA')
    a = np.asarray(im)[:, :, 3]
    ys, xs = np.nonzero(a > 0)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def uniform_scale(entries, canvas_w=CANVAS_W, canvas_h=CANVAS_H, margin=MARGIN):
    """与 sprite_layout.computeUniformScaleWithSkew 一致 (skew 全 0)。"""
    half_w = canvas_w / 2 - margin
    avail_h = canvas_h - 2 * margin
    scale = float('inf')
    for (l, t, r, b) in entries:
        w, h = r - l, b - t
        if w <= 0 or h <= 0:
            continue
        scale = min(scale, avail_h / h)
        # anchor.x = 0.5 → 局部 x = u - 512
        min_lx, max_lx = l - 512, r - 512
        if min_lx < 0:
            scale = min(scale, half_w / (-min_lx))
        if max_lx > 0:
            scale = min(scale, half_w / max_lx)
    return scale if scale != float('inf') else 1.0


def screen_y_of(tex_row, content_bottom, offset, scale):
    return GROUND_Y + (tex_row - content_bottom - offset) * scale


def screen_x_of(tex_col, scale):
    return CANVAS_W / 2 + (tex_col - 512) * scale


def main():
    out = {'round': 'R156', 'canvas': [CANVAS_W, CANVAS_H], 'groundY': GROUND_Y}

    # ---------- 1) 逐帧 alpha bbox ----------
    bboxes = {}
    print("== R156 逐帧真实 alpha bbox (纹理坐标) ==")
    for name, rel in FRAME_FILES.items():
        p = os.path.join(ASSETS, rel)
        if not os.path.exists(p):
            print(f"  ❌ 缺文件 {rel}")
            continue
        bb = alpha_bbox(p)
        bboxes[name] = bb
        print(f"  {name:28s} bbox={bb}  h={bb[3]-bb[1]:4d} w={bb[2]-bb[0]:4d}")
    out['frame_bboxes'] = bboxes

    prop_bb = {}
    print("\n== 道具 alpha bbox ==")
    for name, rel in PROP_FILES.items():
        p = os.path.join(ASSETS, rel)
        bb = alpha_bbox(p)
        prop_bb[name] = bb
        print(f"  {name:20s} bbox={bb}  h={bb[3]-bb[1]:4d} w={bb[2]-bb[0]:4d}")
    out['prop_bboxes'] = prop_bb

    # ---------- 2) 统一缩放 (纳入 R156 新帧) ----------
    scale = uniform_scale([tuple(bboxes[n]) for n in bboxes if bboxes[n]])
    print(f"\n== 统一 scale = {scale:.6f}  (compact {CANVAS_W}x{CANVAS_H}, groundY={GROUND_Y}) ==")
    out['scale'] = scale

    # ---------- 3) 各场景的屏幕占位 (含 ground_offset) ----------
    scenes = [
        # (名称, 角色帧, 场景地板纹理 y, 道具 back, 道具 front)
        ('sleep', 'sleep_loop_02_stable', FLOOR['sleep'],
         ['prop_moon', 'prop_bed'], ['prop_quilt']),
        ('sit', 'sleep_enter_01_sit', FLOOR['sit'],
         ['prop_sofa'], []),
        ('work', 'R156_work_1', FLOOR['work'],
         ['prop_chair'], ['prop_desk', 'prop_screen_glow']),
        ('stand_idle', 'idle_00_base', None, [], []),
        ('jump_air', 'R156_cheer_jump_1', None, [], []),
    ]
    print("\n== 各场景屏幕占位 (含 ground_offset) ==")
    scene_report = {}
    for (sname, frame, floor, back, front) in scenes:
        bb = bboxes[frame]
        if floor is None:
            offset = 0
        else:
            offset = floor - bb[3]
        # 角色屏幕矩形
        cx0 = screen_x_of(bb[0], scale)
        cx1 = screen_x_of(bb[2], scale)
        cy0 = screen_y_of(bb[1], bb[3], offset, scale)
        cy1 = screen_y_of(bb[3], bb[3], offset, scale)
        # 道具屏幕矩形
        props = {}
        for p in back + front:
            pb = prop_bb[p]
            px0 = screen_x_of(pb[0], scale)
            px1 = screen_x_of(pb[2], scale)
            py0 = screen_y_of(pb[1], bb[3], offset, scale)
            py1 = screen_y_of(pb[3], bb[3], offset, scale)
            props[p] = [round(px0, 1), round(py0, 1), round(px1, 1), round(py1, 1)]
        print(f"  [{sname}] frame={frame} offset={offset} "
              f"char=({cx0:.1f},{cy0:.1f})-({cx1:.1f},{cy1:.1f})")
        for p, r in props.items():
            inside = r[0] >= -0.5 and r[1] >= -0.5 and r[2] <= CANVAS_W + 0.5 and r[3] <= CANVAS_H + 0.5
            print(f"      {p:18s} screen=({r[0]},{r[1]})-({r[2]},{r[3]}) inside={inside}")
        scene_report[sname] = {
            'frame': frame, 'ground_offset_px': offset,
            'char_screen': [round(cx0, 1), round(cy0, 1), round(cx1, 1), round(cy1, 1)],
            'props_screen': props,
            'back': back, 'front': front,
        }
    out['scenes'] = scene_report

    # ---------- 4) 正确 z 序的场景合成预览 ----------
    def compose(scene_name, out_path, checker=True):
        sc = scene_report[scene_name]
        frame = sc['frame']
        offset = sc['ground_offset_px']
        char = Image.open(os.path.join(ASSETS, FRAME_FILES[frame])).convert('RGBA')
        canvas = Image.new('RGBA', (TEX, TEX), (0, 0, 0, 0))
        for p in sc['back']:
            canvas.alpha_composite(Image.open(os.path.join(ASSETS, PROP_FILES[p])).convert('RGBA'))
        canvas.alpha_composite(char)
        for p in sc['front']:
            canvas.alpha_composite(Image.open(os.path.join(ASSETS, PROP_FILES[p])).convert('RGBA'))
        if checker:
            bg = Image.new('RGBA', (TEX, TEX), (250, 250, 252, 255))
            for y in range(0, TEX, 32):
                for x in range(0, TEX, 32):
                    if ((x // 32) + (y // 32)) % 2 == 0:
                        bg.paste((238, 240, 246, 255), (x, y, x + 32, y + 32))
            bg.alpha_composite(canvas)
            canvas = bg
        canvas.convert('RGB').save(out_path)
        print(f"  📷 {out_path}")

    print("\n== 正确 z 序场景预览 ==")
    os.makedirs('/tmp/r156', exist_ok=True)
    compose('sleep', '/tmp/r156/scene_sleep.png')
    compose('sit', '/tmp/r156/scene_sit.png')
    compose('work', '/tmp/r156/scene_work.png')

    with open(os.path.join(ASSETS, 'character_R156', 'r156_measure_report.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n📄 {os.path.join(ASSETS, 'character_R156', 'r156_measure_report.json')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
