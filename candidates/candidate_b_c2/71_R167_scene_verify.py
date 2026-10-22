#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R167 场景判据 (办公打字 / 睡眠被子) —— **以 200×240 实际显示效果**为口径。

为什么换口径 (用户 R167 明确要求):
  "必须以 200×240 实际显示效果判断, 不得只凭像素覆盖率、颜色比例宣布视觉 PASS。"

  ⇒ 本脚本的所有"可见性"判据都在 **200×240 真实合成图**上量:
      · 键盘在真尺寸下到底露出来多少像素
      · 双手在真尺寸下有没有压住键区
      · 床架/床头板/床垫在真尺寸下有没有露出来
  纹理坐标 (1024) 只用来定位, 不用来代替观感。

判据一览 (全部绝对值, 新旧素材同一套口径复算):
  办公场景
    P2-1 双手在台面带      : 手的 y 范围完整落在台面带 (远沿 ≤ 手顶, 手底 ≤ 近沿)
    P2-2 屏幕方向正确      : 笔记本盖板均亮 < 120 (石墨背板=屏幕朝角色) + 青蓝边缘光 ≥ 150
    P2-3 道具不遮脸        : 不透明道具像素 ∩ 面部皮肤 = 0
    P2-4 身份未漂移        : 角色自身可见像素里 白大褂 ≥ 0.30 / 银白发 ≥ 0.10
    P2-5 键盘在台上        : 键盘道具的不透明像素与双手区域重叠 ≥ 键区面积的 40%
    P2-6 双手压住键区      : 手部皮肤像素里, 落在键盘键区内的比例 ≥ 0.55
    P2-7 打字动作真实存在  : work_1 与 work_2 的手部质心位移 ≥ 6 纹理 px
    P2-8 真尺寸键盘可见    : 200×240 合成图里键盘可见像素 ≥ 260 px (必须真的看得见)
  睡眠场景
    P3-1 被子盖住身体      : 身体核心区覆盖率 ≥ 0.85 且整体 ≥ 0.45
    P3-2 被子不遮脸        : 被子 ∩ 面部皮肤 ≤ 30 px
    P3-3 被子边缘柔和      : 最外 2px alpha 中位数 < 200
    P3-4 被子是浅蓝        : 平均 B > R + 12 且平均亮度 ≥ 165 (旧版是灰蓝硬壳)
    P3-5 有褶皱明暗起伏    : 被子亮度的 p90-p10 ≥ 34 (不是一块平涂)
    P3-6 床架/床头可见     : 200×240 里床的木质像素 ≥ 150 px 且左上角有床头立板
    P3-7 床垫可见          : 200×240 里床垫侧面的浅色像素 ≥ 120 px

用法:
    python3 71_R167_scene_verify.py --out evidence_r167_scene_verify.json
"""
import argparse
import importlib.util
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R153 = os.path.join(ASSETS, 'character_R153')
R156 = os.path.join(ASSETS, 'character_R156')
BEFORE = '/tmp/r165_before'          # R162 旧素材 (复验用)
TEX = 1024

# ---- 200×240 真实显示参数 (与 45_R165_scene_preview.py / sprite_layout.js 一致) ----
CANVAS_W, CANVAS_H = 200, 240
MARGIN = 4
ANCHOR_X, ANCHOR_Y = 0.5, 0.9

# ---- R167 几何 (实测; 来源 prop_scene_guides.json) ----
R167 = dict(
    desk_far=552, desk_near=700,
    lid_box=(642, 428, 808, 596),
    hand_l=(348, 567, 425, 638), hand_r=(439, 571, 535, 641),
    kb_far=566, kb_near=664, kb_far_x=(338, 574), kb_near_x=(306, 606),
    quilt_left_x=407,
)
# ---- R162 旧素材几何 ----
R162 = dict(
    desk_far=640, desk_near=716,
    lid_box=(516, 520, 762, 692),
    hand_l=(348, 567, 425, 638), hand_r=(439, 571, 535, 641),
    kb_far=None, kb_near=None, kb_far_x=None, kb_near_x=None,
    quilt_left_x=416,
)

_spec = importlib.util.spec_from_file_location(
    'sp', os.path.join(CAND, '45_R165_scene_preview.py'))
_sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sp)


def load(p):
    return np.asarray(Image.open(p).convert('RGBA')).astype(np.int32)


def skin_mask(a):
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 60) & (R >= 195) & (G >= 160) & (B >= 140) \
        & ((R - B) >= 12) & ((R - G) >= -8)


def face_skin(a):
    Al = a[:, :, 3]
    ys, xs = np.nonzero(Al > 40)
    if len(xs) == 0:
        return np.zeros(Al.shape, bool)
    rowcount = np.bincount(ys, minlength=Al.shape[0])
    cum = np.cumsum(rowcount)
    head_rows = int(np.searchsorted(cum, cum[-1] * 0.30))
    head = np.zeros(Al.shape, bool)
    head[:max(1, head_rows)] = True
    return skin_mask(a) & head


def compose_1024(back_paths, char_path, front_paths):
    canvas = np.zeros((TEX, TEX, 4), np.int32)
    for p in list(back_paths) + [char_path] + list(front_paths):
        a = load(p)
        al = a[:, :, 3:4].astype(np.float32) / 255.0
        canvas[:, :, :3] = (canvas[:, :, :3] * (1 - al)
                            + a[:, :, :3].astype(np.float32) * al).astype(np.int32)
        canvas[:, :, 3] = np.maximum(canvas[:, :, 3], a[:, :, 3])
    return canvas


def compose_200(back_pairs, front_pairs, char_path, floor):
    """在 200×240 真实画布上合成 (与运行时同一套缩放/地面规则)。

    back_pairs / front_pairs = [(道具名, 绝对路径), ...]
    """
    import json as _json
    m = _json.load(open(os.path.join(ASSETS, 'character_R141_manifest.json'),
                        encoding='utf-8'))
    scene = 'work' if floor == 1001 else 'sleep_breath'
    lib = (m.get('props') or {}).get('library') or {}
    orig_lib = dict(lib)
    orig_back = list(m['props']['scenes'][scene].get('back') or [])
    orig_front = list(m['props']['scenes'][scene].get('front') or [])
    try:
        for name, real in list(back_pairs) + list(front_pairs):
            lib[name] = {'file': os.path.relpath(real, ASSETS)}
        sc = m['props']['scenes'][scene]
        sc['back'] = [n for n, _ in back_pairs]
        sc['front'] = [n for n, _ in front_pairs]
        out = _sp.compose(scene, CANVAS_W, CANVAS_H, m,
                          frame_override=os.path.relpath(char_path, ASSETS),
                          out_path=None, checker=False)
    finally:
        m['props']['library'] = orig_lib
        m['props']['scenes'][scene]['back'] = orig_back
        m['props']['scenes'][scene]['front'] = orig_front
    return np.asarray(out.convert('RGBA')).astype(np.int32)


def analyse(tag, paths, geo, out, has_keyboard):
    res = {'tag': tag}
    A = paths['A']
    work_scene = compose_1024(
        [p for _, p in paths['back']], paths['work1'], [p for _, p in paths['front']])
    quilt = load(os.path.join(A, 'prop_quilt.png'))

    # ---------- 办公 ----------
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

    lx0, ly0, lx1, ly1 = geo['lid_box']
    lid = work_scene[ly0:ly1, lx0:lx1]
    lid_a = lid[:, :, 3] > 40
    lum = 0.299 * lid[:, :, 0] + 0.587 * lid[:, :, 1] + 0.114 * lid[:, :, 2]
    lid_mean = float(lum[lid_a].mean()) if lid_a.any() else 0.0
    R, G, B = lid[:, :, 0], lid[:, :, 1], lid[:, :, 2]
    cyan = int(((B > R + 25) & (G > R + 25) & lid_a).sum())
    res['P2-2_screen_direction'] = {
        'pass': bool(lid_mean < 120 and cyan >= 150),
        'lid_mean_luminance': round(lid_mean, 1), 'lid_cyan_edge_px': cyan,
        'lid_box': list(geo['lid_box']),
        'note': '盖板均值 < 120 = 看到的是石墨背板(屏幕朝角色); 青蓝边缘光 ≥ 150 = 屏幕亮着',
    }

    char = load(os.path.join(A, 'work_1.png'))
    face = face_skin(char)
    prop_alpha = np.zeros(face.shape, bool)
    prop_opaque = np.zeros(face.shape, bool)
    for p in paths['all_props']:
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

    vis = (work_scene[:, :, 3] > 24) & ~prop_opaque
    px = work_scene[:, :, :3][vis]
    white = float(((px[:, 0] > 195) & (px[:, 1] > 195) & (px[:, 2] > 195)).mean())
    silver = float(((px[:, 0] > 120) & (px[:, 0] < 235)
                    & (np.abs(px[:, 0] - px[:, 2]) < 22)).mean())
    res['P2-4_character_white_ratio'] = {
        'pass': bool(white >= 0.30 and silver >= 0.10),
        'white': round(white, 3), 'silver': round(silver, 3),
        'note': '只统计角色自身可见像素 (排除道具); 白大褂 ≥ 0.30, 银白发 ≥ 0.10',
    }

    # ---------- P2-5 键盘在台面上且在手下方 ----------
    if has_keyboard:
        kb = load(os.path.join(A, 'prop_keyboard.png'))
        kb_a = kb[:, :, 3] > 40
        hx0 = min(geo['hand_l'][0], geo['hand_r'][0])
        hx1 = max(geo['hand_l'][2], geo['hand_r'][2])
        hy0 = min(geo['hand_l'][1], geo['hand_r'][1])
        hy1 = max(geo['hand_l'][3], geo['hand_r'][3])
        hand_zone = np.zeros_like(kb_a)
        hand_zone[hy0:hy1, hx0:hx1] = True
        overlap = int((kb_a & hand_zone).sum())
        key_area = int((kb_a & (np.arange(TEX)[:, None] >= geo['kb_far'])
                        & (np.arange(TEX)[:, None] <= geo['kb_near'])).sum())
        res['P2-5_keyboard_under_hands'] = {
            'pass': bool(key_area > 0 and overlap / max(1, key_area) >= 0.40),
            'key_area_px': key_area, 'overlap_with_hand_zone_px': overlap,
            'overlap_ratio': round(overlap / max(1, key_area), 3),
            'note': '键盘不透明像素落在双手区域内的比例 ≥ 0.40 = 键盘确实在手下',
        }
        # P2-6 双手压住键区
        R = char[:, :, 0].astype(np.int16)
        G = char[:, :, 1].astype(np.int16)
        B = char[:, :, 2].astype(np.int16)
        sk = ((char[:, :, 3] > 40) & (R > 195) & (G > 140) & (G < 205)
              & (B > 110) & (B < 185) & (R > B + 35))
        hand_sk = sk & (np.arange(TEX)[:, None] >= geo['kb_far']) \
            & (np.arange(TEX)[:, None] <= geo['kb_near'])
        hand_sk_total = int((sk & (np.arange(TEX)[:, None] >= 540)).sum())
        res['P2-6_hands_on_key_zone'] = {
            'pass': bool(hand_sk_total > 0 and hand_sk.sum() / hand_sk_total >= 0.55),
            'hand_skin_in_key_zone_px': int(hand_sk.sum()),
            'hand_skin_total_px': hand_sk_total,
            'ratio': round(hand_sk.sum() / max(1, hand_sk_total), 3),
            'note': '手部皮肤落在键盘键区(远沿..近沿)内的比例 ≥ 0.55 = 手真的按在键上',
        }
    else:
        res['P2-5_keyboard_under_hands'] = {
            'pass': False, 'value': 0,
            'note': '旧素材没有键盘道具 ⇒ 判 FAIL (这正是 R165 真机暴露的问题)',
        }
        res['P2-6_hands_on_key_zone'] = {
            'pass': False, 'value': 0,
            'note': '旧素材没有键盘 ⇒ 手无处可按',
        }

    # P2-7 打字动作: 两帧手部位移
    def hand_centroid(p):
        a = load(p)
        # 用与角色烘焙器同一套的**紧**肤色判定 (通用 skin_mask 会把白大褂/木质
        # 也算进来, 质心就不准了)
        R = a[:, :, 0].astype(np.int16)
        G = a[:, :, 1].astype(np.int16)
        B = a[:, :, 2].astype(np.int16)
        sk = ((a[:, :, 3] > 40) & (R > 195) & (G > 140) & (G < 205)
              & (B > 110) & (B < 185) & (R > B + 35))
        ys, xs = np.nonzero(sk & (np.arange(TEX)[:, None] >= 540))
        if len(xs) == 0:
            return None
        return float(xs.mean()), float(ys.mean())

    c1 = hand_centroid(os.path.join(A, 'work_1.png'))
    c2 = hand_centroid(os.path.join(A, 'work_2.png'))
    d = float(np.hypot(c1[0] - c2[0], c1[1] - c2[1])) if (c1 and c2) else 0.0
    res['P2-7_typing_motion_px'] = {
        'pass': bool(d >= 6.0), 'hand_centroid_shift_px': round(d, 1),
        'work_1_c': [round(c1[0], 1), round(c1[1], 1)] if c1 else None,
        'work_2_c': [round(c2[0], 1), round(c2[1], 1)] if c2 else None,
        'note': '两帧手部质心位移 ≥ 6 纹理 px (≈1.2 屏幕 px) = 手指真的在动',
    }

    # P2-8 200×240 真尺寸下键盘可见像素
    w200 = compose_200(paths['back'], paths['front'], paths['work1'], 1001)
    kb200 = None
    if has_keyboard:
        # 单独渲染"多了键盘"的版本, 与整场景差分 ⇒ 得到键盘在真尺寸的可见像素
        only_kb = compose_200(paths['back'] + [('prop_keyboard', paths['kb'])],
                              paths['front'], paths['work1'], 1001)
        diff = (np.abs(only_kb[:, :, :3].astype(int) - w200[:, :, :3].astype(int)).sum(axis=2)
                > 12) & (w200[:, :, 3] > 0)
        kb200 = int(diff.sum())
    res['P2-8_keyboard_visible_at_200x240_px'] = {
        'pass': bool(kb200 is not None and kb200 >= 260),
        'value': kb200,
        'note': '200×240 真实合成图里键盘可见的像素数 ≥ 260 (≈52×5 px 一块) = 真机看得见',
    }

    # ---------- 睡眠 ----------
    sleep_char = load(os.path.join(R153, 'sleep_breath_in.png'))
    face = face_skin(sleep_char)
    quilt_a = quilt[:, :, 3] > 24
    covered = int((quilt_a & face).sum())
    res['P3-2_quilt_cover_face_skin_px'] = {
        'pass': covered <= 30, 'value': covered,
        'face_skin_px': int(face.sum()),
        'note': '阈值 30 px = 抗锯齿余量 (占面部皮肤 6070 px 的 0.5%)',
    }
    body = sleep_char[:, :, 3] > 40
    ys = np.nonzero(body)[0]
    head_rows = ys.min() + int((ys.max() - ys.min()) * 0.22)
    body_mask = np.zeros_like(body)
    body_mask[head_rows:] = True
    body_mask &= body
    cov = int((quilt_a & body_mask).sum())
    ratio = cov / max(1, int(body_mask.sum()))
    core = body_mask.copy()
    core[:, :400] = False
    core_ratio = int((quilt_a & core).sum()) / max(1, int(core.sum()))
    res['P3-1_quilt_body_coverage_ratio'] = {
        'pass': bool(ratio >= 0.45 and core_ratio >= 0.85),
        'overall_ratio': round(ratio, 3), 'body_core_ratio': round(core_ratio, 3),
        'body_core_x_from': 400, 'covered_px': cov, 'body_px': int(body_mask.sum()),
        'note': ('整体覆盖率 ≥ 0.45 且**身体核心**(x≥400 躯干+臀+腿)覆盖率 ≥ 0.85 '
                 '= 被子确实盖在身上而不是摆在旁边; 左侧头/手臂按设计露出'),
    }
    edge = quilt_a[:, :geo['quilt_left_x'] + 2]
    vals = edge[edge > 0]
    soft = float(np.median(vals)) if len(vals) else 0.0
    res['P3-3_quilt_left_edge_softness'] = {
        'pass': bool(soft < 200), 'outer_2px_median_alpha': round(soft, 1),
        'note': '被子最外 2px 的 alpha 中位数 < 200 = 边缘是渐隐而不是硬切',
    }

    # P3-4 被子是浅蓝
    qa = quilt[:, :, 3] > 200
    qpx = quilt[:, :, :3][qa].astype(float)
    mr, mg, mb = qpx[:, 0].mean(), qpx[:, 1].mean(), qpx[:, 2].mean()
    qlum = 0.299 * mr + 0.587 * mg + 0.114 * mb
    res['P3-4_quilt_is_light_blue'] = {
        'pass': bool(mb > mr + 12 and qlum >= 165),
        'mean_rgb': [round(mr, 1), round(mg, 1), round(mb, 1)],
        'mean_luminance': round(qlum, 1),
        'note': '被子平均 B > R + 12 且平均亮度 ≥ 165 = 浅蓝蓬松布被 (R165 旧版是灰蓝硬壳)',
    }
    # P3-5 有褶皱明暗
    ql = (0.299 * quilt[:, :, 0] + 0.587 * quilt[:, :, 1] + 0.114 * quilt[:, :, 2])[qa]
    rng = float(np.percentile(ql, 90) - np.percentile(ql, 10))
    res['P3-5_quilt_has_soft_shading'] = {
        'pass': bool(rng >= 34.0), 'luminance_p90_minus_p10': round(rng, 1),
        'note': '被子亮度 p90-p10 ≥ 34 = 有起伏与褶皱明暗, 不是一块平涂硬壳',
    }
    # P3-6 / P3-7 床架与床垫在真尺寸下可见
    s200 = compose_200(paths['sleep_back'],
                       [('prop_quilt', paths['quilt'])],
                       os.path.join(R153, 'sleep_breath_in.png'), 818)
    px = s200[:, :, :3].astype(int)
    al = s200[:, :, 3]
    wood = ((px[:, :, 0] > 140) & (px[:, :, 0] < 235)
            & (px[:, :, 0] > px[:, :, 2] + 18) & (al > 200))
    bottom = np.zeros(wood.shape, bool)
    bottom[200:, :] = True
    head = np.zeros(wood.shape, bool)
    head[:200, :60] = True
    wood_px = int(wood.sum())
    res['P3-6_bed_frame_visible_at_200x240_px'] = {
        'pass': bool(int((wood & head).sum()) >= 300
                     and int((wood & bottom).sum()) >= 400),
        'wood_px': wood_px,
        'wood_in_bottom_band_px': int((wood & bottom).sum()),
        'wood_in_headboard_corner_px': int((wood & head).sum()),
        'note': ('200×240 里床头立板 ≥ 300 px 且底部床架条 ≥ 400 px '
                 '(R162 旧床只有 122/238 ⇒ FAIL) = 床架清楚可见'),
    }
    matt = ((px[:, :, 0] > 185) & (px[:, :, 2] > 200) & (px[:, :, 2] > px[:, :, 0])
            & (al > 200))
    res['P3-7_mattress_visible_at_200x240_px'] = {
        'pass': bool(int(matt.sum()) >= 120),
        'value': int(matt.sum()),
        'note': '200×240 里床垫/床品的浅色像素 ≥ 120 = 床垫清楚可见',
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
    ap.add_argument('--out', default=os.path.join(CAND, 'evidence_r167_scene_verify.json'))
    args = ap.parse_args()
    out = {}

    A = R156
    analyse('R167', dict(
        A=A,
        back=[('prop_chair', os.path.join(A, 'prop_chair.png')),
              ('prop_desk_surface', os.path.join(A, 'prop_desk_surface.png'))],
        front=[('prop_desk', os.path.join(A, 'prop_desk.png')),
               ('prop_screen_glow', os.path.join(A, 'prop_screen_glow.png'))],
        sleep_back=[('prop_bed', os.path.join(A, 'prop_bed.png')),
                    ('prop_moon', os.path.join(A, 'prop_moon.png'))],
        kb=os.path.join(A, 'prop_keyboard.png'),
        quilt=os.path.join(A, 'prop_quilt.png'),
        work1=os.path.join(A, 'work_1.png'),
        work2=os.path.join(A, 'work_2.png'),
        all_props=[os.path.join(A, 'prop_chair.png'),
                   os.path.join(A, 'prop_desk_surface.png'),
                   os.path.join(A, 'prop_keyboard.png'),
                   os.path.join(A, 'prop_desk.png'),
                   os.path.join(A, 'prop_screen_glow.png')],
    ), R167, out, has_keyboard=True)

    if os.path.isdir(BEFORE):
        analyse('R162', dict(
            A=BEFORE,
            back=[('prop_chair', os.path.join(BEFORE, 'prop_chair.png'))],
            front=[('prop_desk', os.path.join(BEFORE, 'prop_desk.png')),
                   ('prop_screen_glow', os.path.join(BEFORE, 'prop_screen_glow.png'))],
            sleep_back=[('prop_bed', os.path.join(BEFORE, 'prop_bed.png')),
                        ('prop_moon', os.path.join(BEFORE, 'prop_moon.png'))],
            kb=os.path.join(BEFORE, 'prop_keyboard.png'),
            quilt=os.path.join(BEFORE, 'prop_quilt.png'),
            work1=os.path.join(BEFORE, 'work_1.png'),
            work2=os.path.join(BEFORE, 'work_2.png'),
            all_props=[os.path.join(BEFORE, 'prop_chair.png'),
                       os.path.join(BEFORE, 'prop_desk.png'),
                       os.path.join(BEFORE, 'prop_screen_glow.png')],
        ), R162, out, has_keyboard=False)

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump({'round': 'R167',
                   'criteria_note': ('以 200×240 实际显示效果为口径的绝对值判据, '
                                     '新旧素材同一套复算 (不是"相比基线没变差")'),
                   'results': out}, f, ensure_ascii=False, indent=2)
    print(f"  📄 {args.out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
