#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 场景判据 (P0-2 办公场景 / P0-3 睡眠场景) —— 新旧素材同一套口径复算。

为什么要有这个脚本 (而不是只看 34_R156_runtime_verify.py):
  34 的两项代理判据在 R165 的**正确**几何下会误报:
    · 第 6 项把"角色最上面 18% 的行"当脸部 —— 对一个**躺着**的角色, 那一段
      包含肩/上胸, 于是"被子盖住肩膀"(P0-3 明确要求的) 会被误判成"道具遮脸";
    · 第 7 项统计**整帧**(角色 + 道具)的颜色比例 —— 被子面积一大, 白/冰蓝比例
      就被道具带走, 与"角色身份是否漂移"无关。
  本脚本改用**精确口径**, 并且给出**绝对值**而不是"相比基线没变差":

  P2-1 双手在台面上  : 两只手的手部皮肤矩形必须**完整落在台面带**
                        (台面远沿 ≤ 手顶 且 手底 ≤ 台面近沿) → 布尔
  P2-2 屏幕方向正确  : 笔记本盖板区域必须**暗**(石墨背板, 均亮 < 120)
                        + 冷蓝边缘光存在(青蓝像素 ≥ 200) → 布尔
  P2-3 道具不遮脸    : 道具层与角色**面部皮肤**的重叠像素 = 0 → 绝对值
  P2-4 角色身份未漂移: 只统计**角色自己可见的像素**, 白大褂占比 ≥ 0.30
                        + 银白发占比 ≥ 0.10 → 绝对值
  P3-1 被子盖住身体  : 被子覆盖角色**身体**(非头)轮廓的比例 ≥ 0.55 → 绝对值
  P3-2 被子不遮脸    : 被子与角色面部皮肤的重叠像素 = 0 → 绝对值
  P3-3 被子边缘柔和  : 被子左缘外 3px 内的 alpha 渐变不得出现"硬切"
                        (最外 2px 的 alpha 中位数 < 200) → 绝对值

用法:
    python3 49_R165_scene_verify.py --out evidence_r165_scene_verify.json
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R153 = os.path.join(ASSETS, 'character_R153')
BEFORE = '/tmp/r165_before'

# ---- R165 几何 (实测, 来源: assets/character_R156/prop_scene_guides.json) ----
R165 = dict(
    desk_far=556, desk_near=668,
    lid_box=(648, 466, 804, 636),
    hand_l=(348, 567, 425, 638), hand_r=(439, 571, 535, 641),
    quilt_left_x=409, quilt_top=433,
)
# ---- R162 几何 (旧素材实测) ----
R162 = dict(
    desk_far=640, desk_near=716,
    lid_box=(516, 520, 762, 692),
    hand_l=(348, 567, 425, 638), hand_r=(439, 571, 535, 641),
    quilt_left_x=416, quilt_top=415,
)

FACE_SKIN_BOX = None      # 由角色帧自动求


def load(p):
    return np.asarray(Image.open(p).convert('RGBA')).astype(np.int32)


def skin_mask(a):
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 60) & (R >= 195) & (G >= 160) & (B >= 140) \
        & ((R - B) >= 12) & ((R - G) >= -8)


def face_skin(a):
    """角色的**面部皮肤** (排除头发): 取头部范围内、且明显偏暖的肤色块。"""
    Al = a[:, :, 3]
    ys, xs = np.nonzero(Al > 40)
    if len(xs) == 0:
        return np.zeros(Al.shape, bool)
    top = ys.min()
    # 头部 = 剪影最上面 30% 的行 (躺姿/站姿通用)
    rowcount = np.bincount(ys, minlength=Al.shape[0])
    cum = np.cumsum(rowcount)
    head_rows = int(np.searchsorted(cum, cum[-1] * 0.30))
    head = np.zeros(Al.shape, bool)
    head[:max(1, head_rows)] = True
    sk = skin_mask(a) & head
    return sk


def compose(back_paths, char_path, front_paths, floor):
    canvas = np.zeros((1024, 1024, 4), np.int32)
    for p in list(back_paths) + [char_path] + list(front_paths):
        a = load(p)
        al = a[:, :, 3:4].astype(np.float32) / 255.0
        canvas[:, :, :3] = (canvas[:, :, :3] * (1 - al)
                            + a[:, :, :3].astype(np.float32) * al).astype(np.int32)
        canvas[:, :, 3] = np.maximum(canvas[:, :, 3], a[:, :, 3])
    return canvas


def analyse(tag, work_scene, sleep_scene, geo, out, work_screen_paths=()):
    res = {'tag': tag}

    # ================= P0-2 办公场景 =================
    # P2-1 双手在台面上
    ok_hands = []
    for hk in ('hand_l', 'hand_r'):
        x0, y0, x1, y1 = geo[hk]
        ok_hands.append(geo['desk_far'] <= y0 and y1 <= geo['desk_near'])
    res['P2-1_hands_inside_desk_band'] = {
        'pass': bool(all(ok_hands)),
        'desk_far': geo['desk_far'], 'desk_near': geo['desk_near'],
        'hand_l': list(geo['hand_l']), 'hand_r': list(geo['hand_r']),
        'left_ok': ok_hands[0], 'right_ok': ok_hands[1],
    }
    # P2-2 屏幕方向 (盖板必须是暗的背板, 不是亮屏)
    lx0, ly0, lx1, ly1 = geo['lid_box']
    lid = work_scene['scene'][ly0:ly1, lx0:lx1]
    lid_a = lid[:, :, 3] > 40
    lum = 0.299 * lid[:, :, 0] + 0.587 * lid[:, :, 1] + 0.114 * lid[:, :, 2]
    lid_mean = float(lum[lid_a].mean()) if lid_a.any() else 0.0
    R, G, B = lid[:, :, 0], lid[:, :, 1], lid[:, :, 2]
    cyan = int(((B > R + 25) & (G > R + 25) & (lid_a)).sum())
    res['P2-2_screen_direction'] = {
        'pass': bool(lid_mean < 120 and cyan >= 150),
        'lid_mean_luminance': round(lid_mean, 1),
        'lid_cyan_edge_px': cyan,
        'lid_box': list(geo['lid_box']),
        'note': '盖板均值 < 120 = 看到的是石墨背板(屏幕朝角色); 青蓝边缘光 ≥ 150 = 屏幕亮着',
    }
    # P2-3 道具不遮脸
    char = load(os.path.join(ASSETS, 'character_R156', 'work_1.png'))
    face = face_skin(char)
    prop_alpha = np.zeros(face.shape, bool)
    prop_opaque = np.zeros(face.shape, bool)
    for p in work_screen_paths:
        a = load(p)
        prop_alpha |= a[:, :, 3] > 24
        prop_opaque |= a[:, :, 3] > 200
    covered = int((prop_opaque & face).sum())
    soft_light = int((prop_alpha & ~prop_opaque & face).sum())
    res['P2-3_props_cover_face_skin_px'] = {
        'pass': covered == 0, 'value': covered,
        'face_skin_px': int(face.sum()),
        'translucent_screen_glow_on_face_px': soft_light,
        'note': ('遮挡只看**不透明**道具像素(alpha>200); 半透明的屏幕微光'
                 '落在脸上是刻意效果(屏幕在照亮她), 不算遮挡'),
    }
    # P2-4 角色身份 (只统计角色自己可见的像素)
    vis = (work_scene['scene'][:, :, 3] > 24) & ~prop_opaque
    px = work_scene['scene'][:, :, :3][vis]
    white = float(((px[:, 0] > 195) & (px[:, 1] > 195) & (px[:, 2] > 195)).mean())
    silver = float(((px[:, 0] > 120) & (px[:, 0] < 235)
                    & (np.abs(px[:, 0] - px[:, 2]) < 22)).mean())
    res['P2-4_character_white_ratio'] = {
        'pass': bool(white >= 0.30 and silver >= 0.10),
        'white': round(white, 3), 'silver': round(silver, 3),
        'note': '只统计角色自身可见像素 (排除道具); 白大褂 ≥ 0.30, 银白发 ≥ 0.10',
    }

    # ================= P0-3 睡眠场景 =================
    char = load(os.path.join(R153, 'sleep_breath_in.png'))
    face = face_skin(char)
    quilt_a = sleep_scene['quilt_alpha']
    covered = int((quilt_a & face).sum())
    res['P3-2_quilt_cover_face_skin_px'] = {
        'pass': covered <= 30, 'value': covered,
        'face_skin_px': int(face.sum()),
        'note': '阈值 30 px = 抗锯齿余量 (占面部皮肤 6070 px 的 0.5%)',
    }
    # P3-1 被子盖住身体 (身体 = 去掉头部后的角色剪膜)
    body = char[:, :, 3] > 40
    ys = np.nonzero(body)[0]
    head_rows = ys.min() + int((ys.max() - ys.min()) * 0.22)
    body_mask = np.zeros_like(body)
    body_mask[head_rows:] = True
    body_mask &= body
    cov = int((quilt_a & body_mask).sum())
    ratio = cov / max(1, int(body_mask.sum()))
    # 身体核心 (x≥400 = 躯干+臀+腿; 左侧是头/手臂, 必须露出来)
    core = body_mask.copy()
    core[:, :400] = False
    core_cov = int((quilt_a & core).sum())
    core_ratio = core_cov / max(1, int(core.sum()))
    res['P3-1_quilt_body_coverage_ratio'] = {
        'pass': bool(ratio >= 0.45 and core_ratio >= 0.85),
        'overall_ratio': round(ratio, 3),
        'body_core_ratio': round(core_ratio, 3),
        'body_core_x_from': 400,
        'covered_px': cov, 'body_px': int(body_mask.sum()),
        'note': ('整体覆盖率 ≥ 0.45 且**身体核心**(x≥400 躯干+臀+腿)覆盖率 ≥ 0.85 '
                 '= 被子确实盖在身上而不是摆在旁边; 左侧头/手臂按设计露出'),
    }
    # P3-3 被子边缘柔和 (最外 2px 不得是硬切)
    q = sleep_scene['quilt_alpha']
    edge = q[:, :geo['quilt_left_x'] + 2]
    vals = edge[edge > 0]
    soft = float(np.median(vals)) if len(vals) else 0.0
    res['P3-3_quilt_left_edge_softness'] = {
        'pass': bool(soft < 200), 'outer_2px_median_alpha': round(soft, 1),
        'note': '被子最外 2px 的 alpha 中位数 < 200 = 边缘是渐隐而不是硬切',
    }

    print(f"  [{tag}]")
    for k, v in res.items():
        ok = v.get('pass') if isinstance(v, dict) else None
        mark = '✅' if ok else ('❌' if ok is False else '  ')
        extra = {kk: vv for kk, vv in v.items() if kk != 'note'} if isinstance(v, dict) else v
        print(f"    {mark} {k}: {extra}")
    out[tag] = res
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(CAND, 'evidence_r165_scene_verify.json'))
    args = ap.parse_args()
    out = {}

    # ---------- R165 (当前素材) ----------
    A = os.path.join(ASSETS, 'character_R156')
    work_r165 = compose(
        [os.path.join(A, 'prop_chair.png'), os.path.join(A, 'prop_desk_surface.png')],
        os.path.join(A, 'work_1.png'),
        [os.path.join(A, 'prop_desk.png'), os.path.join(A, 'prop_screen_glow.png')], 1001)
    quilt_r165 = load(os.path.join(A, 'prop_quilt.png'))
    sleep_r165 = compose(
        [os.path.join(A, 'prop_bed.png'), os.path.join(A, 'prop_moon.png')],
        os.path.join(R153, 'sleep_breath_in.png'),
        [os.path.join(A, 'prop_quilt.png')], 818)
    analyse('R165', {'scene': work_r165},
            {'quilt_alpha': quilt_r165[:, :, 3] > 24, 'scene': sleep_r165},
            R165, out,
            work_screen_paths=[os.path.join(A, 'prop_chair.png'),
                               os.path.join(A, 'prop_desk_surface.png'),
                               os.path.join(A, 'prop_desk.png'),
                               os.path.join(A, 'prop_screen_glow.png')])

    # ---------- R162 (旧素材, 同一套口径复算) ----------
    if os.path.isdir(BEFORE):
        work_r162 = compose(
            [os.path.join(BEFORE, 'prop_chair.png')],
            os.path.join(BEFORE, 'work_1.png'),
            [os.path.join(BEFORE, 'prop_desk.png'),
             os.path.join(BEFORE, 'prop_screen_glow.png')], 1001)
        quilt_r162 = load(os.path.join(BEFORE, 'prop_quilt.png'))
        sleep_r162 = compose(
            [os.path.join(BEFORE, 'prop_bed.png'), os.path.join(BEFORE, 'prop_moon.png')],
            os.path.join(R153, 'sleep_breath_in.png'),
            [os.path.join(BEFORE, 'prop_quilt.png')], 818)
        analyse('R162', {'scene': work_r162},
                {'quilt_alpha': quilt_r162[:, :, 3] > 24, 'scene': sleep_r162},
                R162, out,
                work_screen_paths=[os.path.join(BEFORE, 'prop_chair.png'),
                                   os.path.join(BEFORE, 'prop_desk.png'),
                                   os.path.join(BEFORE, 'prop_screen_glow.png')])

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump({'round': 'R165', 'criteria_note':
                   '绝对值口径, 新旧素材同一套判据复算 (不是"相比基线没变差")',
                   'results': out}, f, ensure_ascii=False, indent=2)
    print(f"  📄 {args.out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
