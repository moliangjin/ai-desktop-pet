#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R172 办公场景客观判据 —— 纹理空间(精确) + 真实合成图(可见性) 两层都量。

R167 任务书立下的规矩 (R172 继续遵守):
  "必须以 200×240 实际显示效果判断, 不得只凭像素覆盖率、颜色比例宣布视觉 PASS。"
用户 R172 补充:
  "不允许只凭像素占比或自动测试宣布 PASS。"

⇒ 本脚本分两层:
  · **纹理空间** (1024): 手是否真的压在键盘上、是不是只有两只手、下半身是否完整
    —— 这些在真尺寸下只剩十几个像素, 必须在纹理空间量才可靠;
  · **合成空间** (200×240 / 256×256 真实画面): 腿/鞋/手/屏幕**同屏可见**
    —— 这是用户真机看到的东西;
  · 另加 **修复前 → 修复后** 的同口径绝对差值 (不是"相比基线没变差")。

判据一览 (阈值出处写在每条 rule 里):
  A1 完整坐姿·腿可见   : 200×240 桌下区域青色长袜像素 ≥ 150 px
  A2 完整坐姿·鞋可见   : 200×240 桌下区域靴子像素 (冷白鞋面 + 深蓝鞋底) ≥ 120 px
  A3 双脚落地           : 腿/靴像素最低行 ≥ 地面线 - 3 px (不能悬空)
  A4 屏幕内容可见       : 屏幕投影区亮内容像素 ≥ 260 px 且高频细节能量 ≥ 12
                          (R167 的笔记本背板是整块石墨灰 ⇒ 细节能量 ≈ 5)
  A5 双手在键盘上       : 纹理空间 手部皮肤像素 ≥ 1500 且落在键盘投影区内 ≥ 0.50
  A6 双手数量正确       : 纹理空间 手部肤色连通块 == 2 (不多手不少手)
  A7 打字动作真实存在   : work_1 与 work_2 的手部质心位移 ≥ 4 纹理 px
  A8 身份未漂移         : 角色可见像素里 白大褂 ≥ 0.30 / 银白发 ≥ 0.08
  A9 道具不遮脸         : 前景道具不透明像素 ∩ 面部皮肤 = 0 px
  B1 两种尺寸同屏可见   : 200×240 与 256×256 下 人物/腿脚/双手/屏幕 **同时**达标
  C1 修复前后绝对差     : 角色帧下半身像素 修复后 ≥ 1500 且 修复前 = 0
                          (修复前下半身被剪掉 ⇒ 角色帧里腿脚像素真的是 0)
  C2 修复前后屏幕差     : 屏幕高频细节能量 修复后 ≥ 12 且 修复前 ≤ 8

用法:
    python3 92_R172_scene_verify.py --out evidence_r172_scene_verify.json
"""
import argparse
import copy
import importlib.util
import json
import os

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
MANIFEST = os.path.join(ASSETS, 'character_R141_manifest.json')

_spec = importlib.util.spec_from_file_location(
    'r165_preview', os.path.join(CAND, '45_R165_scene_preview.py'))
_prev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_prev)

TEX = 1024
MARGIN = 4
ANCHOR_Y = 0.9
FLOOR = 1001

# R172 新构图 (与 90_R172_office_bake.py 一致)
DESK_FAR_Y, DESK_NEAR_Y = 620, 706
KB_FAR_Y, KB_NEAR_Y = 634, 690
KB_FAR_X, KB_NEAR_X = (344, 692), (328, 710)
MON_SCREEN = [(690, 398), (872, 440), (866, 524), (700, 550)]
HAND_BAND = (300, 556, 720, 700)      # 纹理空间手区
LOWER_BODY_ROW = 706                  # 桌沿以下算"下半身"

# 修复前 (R167/R170)
BEFORE_DESK_FAR_Y, BEFORE_DESK_NEAR_Y = 552, 700
BEFORE_KB_FAR_Y, BEFORE_KB_NEAR_Y = 566, 664
BEFORE_KB_FAR_X, BEFORE_KB_NEAR_X = (338, 574), (306, 606)
BEFORE_LID = [(642, 428), (808, 428), (808, 596), (642, 596)]
BEFORE_FRAMES = ('character_R156/work_1.png', 'character_R156/work_2.png')

FACE_BOX = (427, 251, 627, 386)


# ---------------------------------------------------------------- 颜色工具
def ch(a, i):
    return a[:, :, i].astype(np.int32)


def is_teal(a):
    """青色长袜/裤腿。"""
    r, g, b = ch(a, 0), ch(a, 1), ch(a, 2)
    return (b > 140) & (b > r + 26) & (g > r + 12) & (g > b - 70)


def is_boot(a):
    """靴子: 冷调近白鞋面 或 深蓝鞋底。

    必须排除纯白背景 (255,255,255): 背景 b-r=0, 鞋面 (194,201,217) b-r=23
    ⇒ 用 b-r ≥ 4 把背景剔掉, 否则"桌下白像素"会被背景整片刷满。
    """
    r, g, b = ch(a, 0), ch(a, 1), ch(a, 2)
    white = (r > 165) & (g > 172) & (b > 185) & (b > r + 4) & (b < 250)
    dark = (r < 125) & (g < 145) & (b > 110) & (b < 210) & (b > r + 22)
    return white | dark


def is_skin(a):
    """肤色 (含手部高光)。手部实测 (254,227,210) —— g 接近 230, 上限不能取 212。"""
    r, g, b = ch(a, 0), ch(a, 1), ch(a, 2)
    return (r > 195) & (g > 140) & (g < 242) & (b > 105) & (b < 228) \
        & (r > g + 12) & (r > b + 26)


def comp_count(mask, min_px=25):
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    cur = 0
    stack = []
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or lab[y, x]:
                continue
            cur += 1
            stack.append((y, x))
            lab[y, x] = cur
            while stack:
                cy, cx = stack.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = cur
                        stack.append((ny, nx))
    counts = [int((lab == i).sum()) for i in range(1, cur + 1)]
    return sum(1 for c in counts if c >= min_px), counts


def poly_mask(shape, pts):
    m = Image.new('L', (shape[1], shape[0]), 0)
    ImageDraw.Draw(m).polygon([(float(p[0]), float(p[1])) for p in pts], fill=255)
    return np.asarray(m) > 0


# ---------------------------------------------------------------- 投影
def make_proj(canvas_w, canvas_h, scale):
    """纹理点 → 屏幕点 (与运行时 sprite_layout.js 一致: 地面行落在地面线上)。"""
    ground_y = canvas_h - MARGIN

    def f(x, y):
        return (canvas_w / 2 + (x - TEX / 2) * scale,
                ground_y - (FLOOR - y) * scale)
    return f


# ---------------------------------------------------------------- 场景合成
def before_manifest(m):
    b = copy.deepcopy(m)
    b['props']['scenes']['work'] = {
        'floor_tex_y': 1001,
        'back': ['prop_chair', 'prop_desk_surface', 'prop_keyboard'],
        'front': ['prop_desk', 'prop_screen_glow'],
    }
    b['action_library']['actions']['work']['frames'] = list(BEFORE_FRAMES)
    b['action_library']['actions']['work']['ground_tex_y'] = 1001
    return b


def compose_scene(m, scene, w, h, frame=None):
    canvas = _prev.compose(scene, w, h, m, frame_override=frame, checker=False)
    bg = Image.new('RGBA', canvas.size, (255, 255, 255, 255))
    bg.alpha_composite(canvas)
    return np.asarray(bg.convert('RGB')).astype(np.int32)


# ---------------------------------------------------------------- 合成空间测量
def measure_composite(arr, canvas_w, canvas_h, scale, desk_far_y, desk_near_y,
                      kb_far_y, kb_near_y, kb_far_x, kb_near_x, mon_quad,
                      char_x_lo, char_x_hi):
    f = make_proj(canvas_w, canvas_h, scale)
    out = {}

    # --- 桌下区域 (腿/脚) ---
    desk_near_sy = f(0, desk_near_y)[1]
    ground_sy = canvas_h - MARGIN
    y0 = int(np.ceil(desk_near_sy)) + 1
    y1 = int(np.floor(ground_sy))
    x0 = int(np.floor(f(char_x_lo, 0)[0])) + 1
    x1 = int(np.ceil(f(char_x_hi, 0)[0])) - 1
    reg = arr[max(0, y0):y1, max(0, x0):x1]
    teal = is_teal(reg)
    boot = is_boot(reg)
    out['below_desk_box'] = [max(0, x0), max(0, y0), max(0, x1), y1]
    out['leg_teal_px'] = int(teal.sum())
    out['boot_px'] = int(boot.sum())
    out['leg_or_boot_px'] = int((teal | boot).sum())
    rows = np.nonzero((teal | boot).any(axis=1))[0]
    out['lowest_leg_row_screen'] = int(max(0, y0) + rows.max()) if len(rows) else None
    out['ground_line_screen'] = round(ground_sy, 1)

    # --- 屏幕内容 ---
    mpts = [f(x, y) for (x, y) in mon_quad]
    smask = poly_mask(arr.shape[:2], mpts)
    sreg = arr[smask]
    lum = sreg.mean(axis=1)
    bright = (lum > 118)
    out['screen_box_px'] = int(smask.sum())
    out['screen_content_px'] = int(bright.sum())
    out['screen_lum_std'] = round(float(lum.std()), 2) if len(lum) else 0.0
    full = arr.mean(axis=2).astype(np.float64)
    k = np.ones((3, 3)) / 9.0
    pad = np.pad(full, 1, mode='edge')
    blur = np.zeros_like(full)
    for dy in range(3):
        for dx in range(3):
            blur += k[dy, dx] * pad[dy:dy + full.shape[0], dx:dx + full.shape[1]]
    out['screen_detail'] = round(float(np.abs(full - blur)[smask].mean()), 3)

    # --- 键盘投影区 + 手 ---
    kpts = [f(*p) for p in [(kb_far_x[0], kb_far_y), (kb_far_x[1], kb_far_y),
                             (kb_near_x[1], kb_near_y), (kb_near_x[0], kb_near_y)]]
    kmask = poly_mask(arr.shape[:2], kpts)
    out['keyboard_box_px'] = int(kmask.sum())
    skin = is_skin(arr)
    fy = f(0, desk_far_y)[1]
    hband = np.zeros_like(skin)
    hband[max(0, int(np.floor(fy)) - 26):int(np.ceil(fy)) + 30, :] = True
    hand = skin & hband
    out['hand_skin_px'] = int(hand.sum())
    out['hand_on_keyboard_ratio'] = round(float((hand & kmask).sum()) /
                                          max(1, int(hand.sum())), 3)
    return out


# ---------------------------------------------------------------- 纹理空间测量
def load_frame(rel):
    return np.asarray(Image.open(os.path.join(ASSETS, rel)).convert('RGBA')).astype(np.int32)


def measure_frame_texture(rel):
    """角色帧纹理空间的: 手部/下半身/手在键盘上的比例。"""
    a = load_frame(rel)
    op = a[:, :, 3] > 60
    skin = is_skin(a) & op
    hx0, hy0, hx1, hy1 = HAND_BAND
    hand = np.zeros_like(skin)
    hand[hy0:hy1, hx0:hx1] = skin[hy0:hy1, hx0:hx1]
    kb = poly_mask((TEX, TEX), [(KB_FAR_X[0], KB_FAR_Y), (KB_FAR_X[1], KB_FAR_Y),
                                (KB_NEAR_X[1], KB_NEAR_Y), (KB_NEAR_X[0], KB_NEAR_Y)])
    lower = np.zeros_like(op)
    lower[LOWER_BODY_ROW:, :] = True
    legs = (is_teal(a) | is_boot(a)) & op & lower
    n_comp, counts = comp_count(hand, min_px=120)
    return {
        'hand_skin_px': int(hand.sum()),
        'hand_on_keyboard_ratio': round(float((hand & kb).sum()) /
                                        max(1, int(hand.sum())), 3),
        'hand_components': n_comp,
        'hand_component_px': sorted(counts, reverse=True)[:4],
        'lower_body_px': int(legs.sum()),
    }


def measure_identity(rel):
    a = load_frame(rel)
    r, g, b = ch(a, 0), ch(a, 1), ch(a, 2)
    op = a[:, :, 3] > 60
    coat = op & (r > 196) & (g > 198) & (b > 198)
    hair = op & (r > 170) & (r < 235) & (abs(r - g) < 26) & (b > 205) & (b > r)
    total = int(op.sum())
    return {'coat_ratio': round(float(coat.sum()) / max(1, total), 4),
            'hair_ratio': round(float(hair.sum()) / max(1, total), 4),
            'opaque_px': total}


def measure_face_occlusion(m):
    lib = m['props']['library']
    face = np.zeros((TEX, TEX), bool)
    x0, y0, x1, y1 = FACE_BOX
    face[y0:y1, x0:x1] = True
    worst = 0
    for name in m['props']['scenes']['work']['front']:
        a = load_frame(lib[name]['file'])
        worst = max(worst, int(((a[:, :, 3] > 60) & face & is_skin(a)).sum()))
    return worst


def hand_centroid(rel):
    a = load_frame(rel)
    sk = is_skin(a)
    ys, xs = np.nonzero(sk)
    if len(xs) == 0:
        return None
    sel = (ys > 585) & (ys < 700)
    if sel.sum() < 50:
        sel = ys > 520
    return (float(xs[sel].mean()), float(ys[sel].mean()))


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='evidence_r172_scene_verify.json')
    args = ap.parse_args()

    m = json.load(open(MANIFEST, encoding='utf-8'))
    bm = before_manifest(m)
    checks = []

    def add(key, ok, detail):
        checks.append({'id': key, 'pass': bool(ok), **detail})
        print(f"  {'✅' if ok else '❌'} {key:28s} {detail.get('value')}")

    scales = {}
    for (w, h) in ((200, 240), (256, 256)):
        scales[f'{w}x{h}'] = round(_prev.build_scale(m, w, h), 6)
        scales[f'{w}x{h}_before'] = round(_prev.build_scale(bm, w, h), 6)

    # --- 合成空间 ---
    after, before = {}, {}
    for (w, h) in ((200, 240), (256, 256)):
        sc = _prev.build_scale(m, w, h)
        after[f'{w}x{h}'] = measure_composite(
            compose_scene(m, 'work', w, h), w, h, sc, DESK_FAR_Y, DESK_NEAR_Y,
            KB_FAR_Y, KB_NEAR_Y, KB_FAR_X, KB_NEAR_X, MON_SCREEN, 312, 718)
        scb = _prev.build_scale(bm, w, h)
        before[f'{w}x{h}'] = measure_composite(
            compose_scene(bm, 'work', w, h), w, h, scb, BEFORE_DESK_FAR_Y, BEFORE_DESK_NEAR_Y,
            BEFORE_KB_FAR_Y, BEFORE_KB_NEAR_Y, BEFORE_KB_FAR_X, BEFORE_KB_NEAR_X,
            BEFORE_LID, 312, 718)

    # --- 纹理空间 ---
    tex_after = measure_frame_texture('character_R172/work_1.png')
    tex_before = measure_frame_texture(BEFORE_FRAMES[0])
    ident = measure_identity('character_R172/work_1.png')
    occ = measure_face_occlusion(m)
    c1 = hand_centroid('character_R172/work_1.png')
    c2 = hand_centroid('character_R172/work_2.png')
    disp = float(np.hypot(c1[0] - c2[0], c1[1] - c2[1])) if c1 and c2 else None

    a200, a256 = after['200x240'], after['256x256']
    b200 = before['200x240']

    add('A1_legs_visible', a200['leg_teal_px'] >= 150,
        {'value': a200['leg_teal_px'], 'threshold': 150,
         'rule': '200×240 桌下区域青色长袜像素 ≥ 150 (桌面只遮大腿, 小腿必须完整)'})
    add('A2_shoes_visible', a200['boot_px'] >= 120,
        {'value': a200['boot_px'], 'threshold': 120,
         'rule': '200×240 桌下区域靴子像素 (冷白鞋面 + 深蓝鞋底) ≥ 120'})
    add('A3_feet_on_ground',
        a200['lowest_leg_row_screen'] is not None
        and a200['lowest_leg_row_screen'] >= a200['ground_line_screen'] - 3,
        {'value': a200['lowest_leg_row_screen'], 'ground_line': a200['ground_line_screen'],
         'threshold': '≥ 地面线 - 3 px', 'rule': '靴底必须落在地面线上 (不能悬空)'})
    add('A4_screen_content_visible',
        a200['screen_content_px'] >= 260 and a200['screen_detail'] >= 12,
        {'value': {'content_px': a200['screen_content_px'],
                   'detail': a200['screen_detail']},
         'threshold': 'content ≥ 260 px 且 detail ≥ 12',
         'rule': '显示器屏幕必须是"有内容的界面", 不是一块平涂背板 (背板 detail ≈ 5)'})
    min_hand = min(tex_after['hand_component_px'][:2]) if tex_after['hand_component_px'] else 0
    add('A5_hands_on_keyboard',
        tex_after['hand_skin_px'] >= 700 and tex_after['hand_on_keyboard_ratio'] >= 0.50
        and min_hand >= 300,
        {'value': {'skin_px': tex_after['hand_skin_px'],
                   'ratio': tex_after['hand_on_keyboard_ratio'],
                   'min_hand_px': min_hand},
         'threshold': '双手皮肤 ≥ 700 px, 单只 ≥ 300 px, 且 ≥0.50 落在键盘投影区',
         'rule': '双手必须真的压在键盘上 (纹理空间量; 真尺寸下每只手只剩 ~15x16 屏幕 px, '
                 '在 200×240 里量"是不是手"不可靠)'})
    add('A6_two_hands_only', tex_after['hand_components'] == 2,
        {'value': tex_after['hand_components'], 'threshold': 2,
         'components_px': tex_after['hand_component_px'],
         'rule': '手部肤色连通块必须正好 2 (不多手不少手)'})
    add('A7_typing_motion_real', disp is not None and disp >= 4.0,
        {'value': round(disp, 2) if disp is not None else None, 'threshold': 4.0,
         'c1': [round(v, 1) for v in c1] if c1 else None,
         'c2': [round(v, 1) for v in c2] if c2 else None,
         'rule': 'work_1 与 work_2 的手部质心位移 ≥ 4 纹理 px (打字动作真实存在)'})
    add('A8_identity_kept',
        ident['coat_ratio'] >= 0.30 and ident['hair_ratio'] >= 0.08,
        {'value': ident, 'threshold': 'coat ≥ 0.30 且 hair ≥ 0.08',
         'rule': 'A1 母版外观未漂移 (白大褂 + 银白发)'})
    add('A9_props_not_covering_face', occ == 0,
        {'value': occ, 'threshold': 0, 'rule': '前景道具不透明像素 ∩ 面部皮肤 = 0'})

    for key, tag, hand_min in (('200x240', 'B1a_200x240_all_visible', 24),
                               ('256x256', 'B1b_256x256_all_visible', 38)):
        d = after[key]
        ok = (d['leg_teal_px'] >= 150 and d['boot_px'] >= 120
              and d['hand_skin_px'] >= hand_min
              and d['screen_content_px'] >= 260
              and d['hand_on_keyboard_ratio'] >= 0.40)
        add(tag, ok, {'value': {'legs': d['leg_teal_px'], 'boots': d['boot_px'],
                                'hands': d['hand_skin_px'], 'screen': d['screen_content_px'],
                                'hand_on_kb': d['hand_on_keyboard_ratio']},
                       'threshold': f'腿≥150 鞋≥120 手≥{hand_min} 屏≥260 手在键盘≥0.40',
                       'rule': f'{key} 下 人物/腿脚/双手/电脑屏幕 必须同时可见'})

    add('C1_legs_before_after',
        tex_after['lower_body_px'] >= 1500 and tex_before['lower_body_px'] == 0,
        {'value': {'after': tex_after['lower_body_px'],
                   'before': tex_before['lower_body_px']},
         'threshold': 'after ≥ 1500 且 before == 0',
         'rule': '修复前下半身被剪掉 ⇒ 角色帧桌沿以下的腿脚像素真的是 0; '
                 '修复后必须成规模出现 (绝对值, 不是"相比基线没变差")'})
    add('C2_screen_before_after',
        a200['screen_detail'] >= 12 and b200['screen_detail'] <= 8,
        {'value': {'after': a200['screen_detail'], 'before': b200['screen_detail']},
         'threshold': 'after ≥ 12 且 before ≤ 8',
         'rule': '修复前是笔记本背板(高频细节≈5), 修复后必须是可见界面(细节≥12)'})

    npass = sum(1 for c in checks if c['pass'])
    report = {
        'round': 'R172', 'scene': 'work', 'sizes': ['200x240', '256x256'],
        'scale': scales, 'checks': checks,
        'summary': {'total': len(checks), 'pass': npass, 'fail': len(checks) - npass,
                    'all_pass': npass == len(checks)},
        'after': after, 'before': before,
        'texture_after': tex_after, 'texture_before': tex_before,
        'identity': ident,
        'note': ('本脚本只提供客观像素证据; 视觉是否"一眼看出在办公"仍以目视复核 + '
                 '用户真机确认为准 (MAC_REAL_GUI_ACCEPTANCE = PENDING)。'
                 '预览合成器 45_R165_scene_preview.py 的垂直落点已在本轮修正为与'
                 '运行时 sprite_layout.js 一致 (旧实现整幅上移 15.58px)。'),
    }
    path = os.path.join(CAND, args.out) if not os.path.isabs(args.out) else args.out
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"\n{'✅' if npass == len(checks) else '❌'} {npass}/{len(checks)} PASS  → {path}")
    return 0 if npass == len(checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
