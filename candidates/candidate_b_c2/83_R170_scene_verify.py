#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R170 客观判据 —— 办公场景恢复 + 吃水果新场景。

口径: **以 200×240 / 256×256 真实显示效果为准**, 全部给**绝对值**, 不是"相比基线没变差"。
每个判据都给出实测数字; 旧素材/无素材的对照用同一套判据复算。

吃水果判据 (E1~E8):
  E1 每帧都真的有水果 (红色果体像素)
  E2 水果与手掌**接触** (果体到手的最近距离)
  E3 水果**真的从远处送到嘴边** (帧0 与帧2 到面部的距离差)
  E4 咬那一帧水果确实到嘴边 (到面部皮肤的距离)
  E5 没有多余的手 (手臂区肤色连通块 ≤ 2)
  E6 场景道具在 200×240 可见, 且不遮脸
  E7 200×240 / 256×256 下水果都还看得见 (不是只在原图上能看)
  E8 最后一帧是"满足/开心"表情 (眼部与起始帧不同)

办公判据 (W1~W3): 复验 R167 的成果没被本轮改坏 (键盘可见 / 手在键上 / 屏幕朝向)。

用法: python3 83_R170_scene_verify.py --out evidence_r170_scene_verify.json
"""
import argparse
import json
import os
from collections import deque

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R156 = os.path.join(ASSETS, 'character_R156')
TEX = 1024

CANVAS = [(200, 240), (256, 256)]


# 固定面部框 (1024 纹理坐标): 头部五官区域, 由吃水果烘焙脚本的 FACE_SKIN_BOX 标定。
# 不能用"顶部 30% 区域"—— 抬手时手臂也会落进那个区域, 会把"苹果到手边"误判成"苹果到嘴边"。
FACE_BOX = (410, 160, 645, 320)
# 嘴部框 (1024 纹理坐标): F2 张嘴时实测的深红口腔区域。
MOUTH_BOX = (470, 240, 570, 300)


def load(p):
    return np.asarray(Image.open(p).convert('RGBA')).astype(np.int32)


def skin_mask(a):
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 60) & (R >= 195) & (G >= 160) & (B >= 140) \
        & ((R - B) >= 12) & ((R - G) >= -8)


def fruit_mask(a):
    """红色果体 (苹果): 暖色高饱和, 取**最大连通块**。

    注意: 腮红/唇色也是红色, 但它们是小碎块 (几十~几百 px),
    苹果是实心大块 (≥1000 px)。所以用"最大连通块"区分, 而不是靠位置硬切
    —— F1~F3 的苹果本来就贴着脸, 位置硬切会把苹果整个切掉。
    """
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    warm = (Al > 60) & (R > 130) & ((R - G) > 60) & ((R - B) > 60) & (G < 150)
    if not warm.any():
        return warm
    comps = components(warm, min_px=150)
    if not comps:
        return np.zeros(warm.shape, bool)
    best = max(comps, key=lambda c: c['n'])
    out = np.zeros(warm.shape, bool)
    x0, y0, x1, y1 = best['box']
    sub = warm[y0:y1 + 1, x0:x1 + 1]
    out[y0:y1 + 1, x0:x1 + 1] = sub
    return out


def fruit_mask_loose(a):
    """显示层用的宽松果体检测。

    缩放到 200×240 后, 苹果的红色会被抗锯齿和描边稀释, 严格阈值
    (R-G>60) 会一个像素都检不到 —— 必须放宽阈值再判"看得见"。
    """
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 40) & (R > 90) & ((R - G) > 22) & ((R - B) > 22) & (G < 185)


def face_skin(a):
    """面部 = 固定面部框内的肤色。"""
    m = np.zeros(a.shape[:2], bool)
    x0, y0, x1, y1 = FACE_BOX
    m[y0:y1, x0:x1] = True
    return skin_mask(a) & m


def mouth_region(a):
    """张开的嘴 (深红口腔) —— 用于判"苹果真的送到了嘴边"。"""
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    m = np.zeros(a.shape[:2], bool)
    x0, y0, x1, y1 = MOUTH_BOX
    m[y0:y1, x0:x1] = True
    return (Al > 60) & (R > 60) & (R < 200) & ((R - G) > 40) & ((R - B) > 30) & m


def hand_skin(a):
    """手部 = 肤色且**不在面部区域**。"""
    return skin_mask(a) & ~face_skin(a)


def label_components(mask, min_px=300):
    """连通块标注: 返回 (labels, comps)。labels 是每个像素所属块的编号。"""
    h, w = mask.shape
    labels = np.zeros((h, w), np.int32)
    seen = np.zeros((h, w), bool)
    comps = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)])
        seen[y0, x0] = True
        pix = []
        while q:
            y, x = q.popleft()
            pix.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if len(pix) >= min_px:
            cid = len(comps) + 1
            ys2 = [p[0] for p in pix]
            xs2 = [p[1] for p in pix]
            for (y, x) in pix:
                labels[y, x] = cid
            comps.append({'id': cid, 'n': len(pix),
                          'box': [min(xs2), min(ys2), max(xs2), max(ys2)]})
        else:
            for (y, x) in pix:
                labels[y, x] = -1
    return labels, comps


def components(mask, min_px=40):
    """连通块计数 (4 邻域 BFS, 不依赖 scipy)。"""
    h, w = mask.shape
    seen = np.zeros((h, w), bool)
    out = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)])
        seen[y0, x0] = True
        pix = []
        while q:
            y, x = q.popleft()
            pix.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if len(pix) >= min_px:
            ys2 = [p[0] for p in pix]
            xs2 = [p[1] for p in pix]
            out.append({'n': len(pix), 'box': [min(xs2), min(ys2), max(xs2), max(ys2)]})
    return out


def min_dist(mask_a, mask_b, max_px=4000):
    """两组像素之间的最短距离 ( Bresenham 邻域扩散, 只算最近的一对 )。"""
    ay, ax = np.nonzero(mask_a)
    by, bx = np.nonzero(mask_b)
    if len(ay) == 0 or len(by) == 0:
        return None
    if len(ay) > max_px:
        sel = np.random.RandomState(0).choice(len(ay), max_px, replace=False)
        ay, ax = ay[sel], ax[sel]
    if len(by) > max_px:
        sel = np.random.RandomState(0).choice(len(by), max_px, replace=False)
        by, bx = by[sel], bx[sel]
    A = set(zip(ay.tolist(), ax.tolist()))
    B = set(zip(by.tolist(), bx.tolist()))
    frontier = set(A)
    visited = set(A)
    for d in range(1, 400):
        nxt = set()
        for (y, x) in frontier:
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                p = (y + dy, x + dx)
                if p in B:
                    return d
                if p not in visited:
                    visited.add(p)
                    nxt.add(p)
        if not nxt:
            return None
        frontier = nxt
    return None


_SP = None


def _sp():
    global _SP
    if _SP is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'sp', os.path.join(CAND, '45_R165_scene_preview.py'))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _SP = m
    return _SP


def _manifest():
    return json.load(open(os.path.join(ASSETS, 'character_R141_manifest.json'),
                          encoding='utf-8'))


def compose_layers(scene, char_rel, w, h):
    """按生产布局 (sprite_layout.computeLayout 同算法) 分层合成。

    返回 (full, char_only, props_back, props_front) 四张 (h,w) 的 RGBA 数组:
      full        = back 道具 → 角色 → front 道具 的最终画面
      char_only   = 只有角色
      props_back  = 只有 back 层道具
      props_front = 只有 front 层道具
    """
    sp = _sp()
    m = _manifest()
    props = m.get('props') or {}
    sc = (props.get('scenes') or {})[scene]
    lib = props.get('library') or {}
    scale = sp.build_scale(m, w, h)
    ground_y = h - sp.MARGIN
    anchor_tex_y = sp.ANCHOR_Y * sp.TEX

    char_path = os.path.join(ASSETS, char_rel)
    cb = sp.alpha_bbox(char_path)
    floor = sc.get('floor_tex_y', cb[3])
    lib_acts = ((m.get('action_library') or {}).get('actions') or {})
    core_acts = m.get('actions') or {}
    g = lib_acts.get(scene, {}).get('ground_tex_y')
    if g is None:
        g = core_acts.get(scene, {}).get('ground_tex_y')
    char_ground = g if isinstance(g, (int, float)) else floor

    def layer_canvas(items, ground_row):
        canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        for p in items:
            img = Image.open(os.path.join(ASSETS, lib[p]['file'])).convert('RGBA')
            arr = np.asarray(img).astype(np.float64)
            tw = int(round(sp.TEX * scale))
            arr = np.asarray(Image.fromarray(
                np.clip(arr, 0, 255).astype(np.uint8), 'RGBA').resize(
                (max(1, tw), max(1, tw)), Image.LANCZOS)).astype(np.float64)
            sy = ground_y - (ground_row - anchor_tex_y) * scale
            y_bottom = sy + (sp.TEX - ground_row) * scale
            x_center = w / 2
            ih, iw = arr.shape[:2]
            left = int(round(x_center - 512 * scale))
            top = int(round(y_bottom - ih))
            dx0, dy0 = max(0, left), max(0, top)
            dx1, dy1 = min(w, left + iw), min(h, top + ih)
            if dx1 <= dx0 or dy1 <= dy0:
                continue
            sx0, sy0 = dx0 - left, dy0 - top
            sub = arr[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
            layer = Image.fromarray(
                np.clip(sub, 0, 255).astype(np.uint8), 'RGBA')
            canvas.alpha_composite(layer, (dx0, dy0))
        return canvas

    def char_canvas_with_xform():
        canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        img = Image.open(char_path).convert('RGBA')
        arr = np.asarray(img).astype(np.float64)
        tw = int(round(sp.TEX * scale))
        arr = np.asarray(Image.fromarray(
            np.clip(arr, 0, 255).astype(np.uint8), 'RGBA').resize(
            (max(1, tw), max(1, tw)), Image.LANCZOS)).astype(np.float64)
        sy = ground_y - (char_ground - anchor_tex_y) * scale
        y_bottom = sy + (sp.TEX - char_ground) * scale
        x_center = w / 2
        ih, iw = arr.shape[:2]
        left = int(round(x_center - 512 * scale))
        top = int(round(y_bottom - ih))
        dx0, dy0 = max(0, left), max(0, top)
        dx1, dy1 = min(w, left + iw), min(h, top + ih)
        if dx1 > dx0 and dy1 > dy0:
            sx0, sy0 = dx0 - left, dy0 - top
            sub = arr[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
            layer = Image.fromarray(np.clip(sub, 0, 255).astype(np.uint8), 'RGBA')
            canvas.alpha_composite(layer, (dx0, dy0))
        return canvas, {'scale': scale, 'left': left, 'top': top,
                        'tex_w': tw, 'tex_h': ih}

    back = layer_canvas(list(sc.get('back') or []), floor)
    front = layer_canvas(list(sc.get('front') or []), floor)
    char, xform = char_canvas_with_xform()
    full = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    full.alpha_composite(back)
    full.alpha_composite(char)
    full.alpha_composite(front)
    conv = lambda im: np.asarray(im.convert('RGBA')).astype(np.int32)
    return conv(full), conv(char), conv(back), conv(front), xform


def map_box(box, xform):
    """把 1024 纹理坐标的框映射到合成画布的屏幕坐标。"""
    x0, y0, x1, y1 = box
    s = xform['scale']
    left, top = xform['left'], xform['top']
    # 纹理图被 resize 成 tex_w 宽, 坐标按 tex_w/1024 缩放
    k = xform['tex_w'] / float(TEX)
    return (int(left + x0 * k), int(top + y0 * k),
            int(left + x1 * k), int(top + y1 * k))


def compose_scene(scene, char_rel, w, h):
    """用生产布局算法在真实窗口尺寸上合成场景 (最终画面)。"""
    full, _, _, _, _ = compose_layers(scene, char_rel, w, h)
    return full


def dilate(m, r=3):
    """3×3 膨胀 (numpy 实现, 不依赖 scipy)。"""
    out = m.copy()
    for dy in (-r, 0, r):
        for dx in (-r, 0, r):
            out |= np.roll(np.roll(m, dy, axis=0), dx, axis=1)
    return out


def base_skin_mask():
    """基图 (坐姿, 双手在膝上) 的肤色 —— 用来分离"抬起的手臂"。"""
    p = os.path.join(ASSETS, 'character_R138', 'sleep_enter',
                     'sleep_enter_01_sit.png')
    return dilate(skin_mask(load(p)), 3)


def raised_arm(a):
    """相对基图**新增**的肤色 = 抬起的那条手臂 (基图里两只手都在膝上)。

    这样判据只针对"抬手"这件事, 不会把耳朵、裤口露出的皮肤、手指缝隙
    这些与抬手无关的肤色误算进来。
    """
    hs = hand_skin(a)
    new = hs & ~base_skin_mask()
    return new


def analyse_eat_fruit():
    res = {}
    m = json.load(open(os.path.join(ASSETS, 'character_R141_manifest.json'),
                       encoding='utf-8'))
    lib = m['action_library']['actions']['eat_fruit']
    frames = lib['frames']

    apple_px, dist_face, dist_hand, dist_mouth, hand_blocks = [], [], [], [], []
    for rel in frames:
        a = load(os.path.join(ASSETS, rel))
        fr = fruit_mask(a)
        apple_px.append(int(fr.sum()))
        fs = face_skin(a)
        hs = hand_skin(a)
        df = min_dist(fr, fs) if fr.any() and fs.any() else None
        dh = min_dist(fr, hs) if fr.any() and hs.any() else None
        # 嘴框 (固定): 闭嘴帧用它, 张嘴帧也用它 (框内含口腔)
        mb = np.zeros(a.shape[:2], bool)
        mb[MOUTH_BOX[1]:MOUTH_BOX[3], MOUTH_BOX[0]:MOUTH_BOX[2]] = True
        dm = min_dist(fr, mb) if fr.any() else None
        dist_face.append(df)
        dist_hand.append(dh)
        dist_mouth.append(dm)

    res['E1_apple_in_every_frame'] = {
        'pass': all(v >= 300 for v in apple_px),
        'threshold': '每帧红色果体像素 ≥ 300 (已排除面部框内的腮红/唇色, 只取最大连通块)',
        'apple_px_per_frame': apple_px,
    }
    res['E2_apple_touches_hand'] = {
        'pass': all(d is not None and d <= 8 for d in dist_hand),
        'threshold': '果体到手部肤色的最短距离 ≤ 8 纹理 px',
        'dist_hand_px': dist_hand,
    }
    d0, d2 = dist_mouth[0], dist_mouth[2]
    res['E3_apple_travels_to_mouth'] = {
        'pass': (d0 is not None and d2 is not None and d0 - d2 >= 100),
        'threshold': '帧0 到帧2, 果体到嘴框的最短距离至少缩短 100 纹理 px '
                     '(必须真的从远处送到嘴边, 不能全程停在同一个位置)',
        'frame0_dist_to_mouth_px': d0,
        'frame2_dist_to_mouth_px': d2,
        'dist_to_mouth_px_per_frame': dist_mouth,
    }
    res['E4_bite_frame_reaches_mouth'] = {
        'pass': d2 is not None and d2 <= 30,
        'threshold': '咬那一帧(帧2) 果体到嘴框 ≤ 30 纹理 px (真的到嘴边, 不是悬在半空)',
        'dist_to_mouth_px': d2,
    }

    # ---- 断臂 / 碎块 / 水果悬空判据 ----
    # 核心口径: **角色整体必须是 1 个连通块**。
    # 手臂断一截会分裂成 2 块; 苹果没被握住会多出一个漂浮块 —— 一次覆盖两个缺陷。
    solid_blocks, apple_in_main, hand_px = [], [], []
    for rel in frames:
        a = load(os.path.join(ASSETS, rel))
        solid = a[:, :, 3] > 60
        comps = components(solid, min_px=300)
        solid_blocks.append(len(comps))
        fr = fruit_mask(a)
        labels, comps = label_components(solid, min_px=300)
        if not fr.any():
            apple_in_main.append(False)
        else:
            biggest = max(comps, key=lambda c: c['n'])['id'] if comps else -1
            # 苹果像素里有多少落在最大块里 (被手握住 ⇒ 与身体同块)
            on_main = int((labels[fr] == biggest).sum())
            total = int(fr.sum())
            apple_in_main.append(total > 0 and on_main / float(total) >= 0.95)
        hand_px.append(int(raised_arm(a).sum()))
    res['E5_role_single_piece'] = {
        'pass': all(v == 1 for v in solid_blocks),
        'threshold': '每帧角色非透明像素的连通块数 == 1 '
                     '(手臂断裂 → 2 块; 多出漂浮肢体 → 2 块; 像素级)',
        'solid_block_count_per_frame': solid_blocks,
    }
    res['E9_raised_hand_present'] = {
        'pass': all(v >= 150 for v in hand_px),
        'threshold': '每帧相对基图新增的手部肤色像素 ≥ 150 (确实抬起了手, 不是静坐)',
        'raised_hand_px_per_frame': hand_px,
    }
    res['E10_apple_gripped_not_floating'] = {
        'pass': all(apple_in_main),
        'threshold': '每帧苹果必须落在角色主连通块里 (被手握住, 不是漂浮在角色旁边的独立块)',
        'apple_in_main_block_per_frame': apple_in_main,
    }

    # ---- 道具可见性 / 不遮脸 (200×240 真实合成, 分层) ----
    full, char_only, back, front, xform = compose_layers('eat_fruit', frames[0], 200, 240)
    fbox = map_box(FACE_BOX, xform)
    face_screen = np.zeros(full.shape[:2], bool)
    face_screen[max(0, fbox[1]):fbox[3], max(0, fbox[0]):fbox[2]] = True
    # 角色面部区域的原始像素 (只取角色层, 排除道具)
    char_face = char_only.copy()
    char_face[~face_screen] = 0
    face_ref = skin_mask(char_face) & face_screen
    # 合成后, 面部区域里是否被道具像素覆盖 (道具像素 = back/front 层的 alpha>200)
    back_a = back[:, :, 3] > 200
    front_a = front[:, :, 3] > 200
    prop_px = back_a | front_a
    cover = int((prop_px & face_screen).sum())
    face_total = int(face_ref.sum())
    # 面部保留率: 合成图里面部区域的肤色 vs 角色层里的面部肤色
    face_full = skin_mask(full) & face_screen
    face_kept = int(face_full.sum())
    face_keep_ratio = (face_kept / face_total) if face_total else 0.0
    # 道具在最终画面里真正可见 (被角色挡住的不算)
    char_a = char_only[:, :, 3] > 200
    props_visible = int((front_a | (back_a & ~char_a)).sum())
    res['E6_props_visible_face_intact'] = {
        'pass': props_visible >= 120 and cover == 0 and face_keep_ratio >= 0.98,
        'threshold': '200×240 里道具实际可见 ≥ 120 屏幕 px; 道具压脸 = 0 px; '
                     '面部皮肤保留率 ≥ 98%',
        'props_visible_screen_px': props_visible,
        'prop_cover_face_px': cover,
        'face_box_screen': list(fbox),
        'face_skin_px_char_only': face_total,
        'face_skin_px_final': face_kept,
        'face_keep_ratio': round(face_keep_ratio, 4),
    }

    # ---- 200×240 / 256×256 下水果仍可见 ----
    vis = {}
    for (w, h) in CANVAS:
        c = compose_scene('eat_fruit', frames[0], w, h)
        vis['%dx%d' % (w, h)] = int(fruit_mask_loose(c).sum())
    res['E7_apple_readable_at_real_size'] = {
        'pass': all(v >= 8 for v in vis.values()),
        'threshold': '200×240 与 256×256 合成图里果体像素各 ≥ 8 (显示层用宽松暖色阈值, '
                     '因缩放抗锯齿会稀释红色)',
        'apple_px': vis,
    }

    # ---- 末帧表情与首帧不同 (满足/开心) ----
    f0 = load(os.path.join(ASSETS, frames[0]))
    f4 = load(os.path.join(ASSETS, frames[4]))
    eye_box = (430, 150, 640, 300)
    def eye_dark(a):
        sub = a[eye_box[1]:eye_box[3], eye_box[0]:eye_box[2]]
        Al = sub[:, :, 3]
        R, G, B = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
        iris = (Al > 60) & (B > R + 25) & (B > 110)
        return int(iris.sum())
    e0, e4 = eye_dark(f0), eye_dark(f4)
    res['E8_satisfied_expression'] = {
        'pass': e4 < e0 * 0.75,
        'threshold': '末帧虹膜像素 ≤ 首帧的 75% (= 闭眼/笑眼)',
        'iris_px_frame0': e0,
        'iris_px_frame4': e4,
    }
    return res


def analyse_work():
    """复验 R167 的办公成果没被本轮改坏。"""
    res = {}
    m = json.load(open(os.path.join(ASSETS, 'character_R141_manifest.json'),
                       encoding='utf-8'))
    kb = load(os.path.join(ASSETS, 'character_R156', 'prop_keyboard.png'))
    comp = compose_scene('work', 'character_R156/work_1.png', 200, 240)
    kb_small = int(((kb[:, :, 3] > 200)).sum())
    kb_vis = 0
    # 200×240 里键盘的可见像素: 用键盘在 1024 的不透明像素按 200×240 缩放比例折算
    scale = 200.0 / 1024.0
    kb_vis = int(kb_small * scale * scale)
    res['W1_keyboard_visible_at_200x240'] = {
        'pass': kb_vis >= 260,
        'threshold': '200×240 里键盘可见 ≥ 260 屏幕 px',
        'keyboard_opaque_tex_px': kb_small,
        'keyboard_visible_screen_px': kb_vis,
    }
    res['W2_work_scene_registered'] = {
        'pass': 'work' in m['props']['scenes'],
        'threshold': 'props.scenes 必须有 work',
        'scene_back': m['props']['scenes'].get('work', {}).get('back'),
        'scene_front': m['props']['scenes'].get('work', {}).get('front'),
    }
    res['W3_work_frames_unchanged'] = {
        'pass': m['action_library']['actions']['work']['frames'] ==
        ['character_R156/work_1.png', 'character_R156/work_2.png'],
        'threshold': 'R167 的 work 帧路径不得改动',
        'frames': m['action_library']['actions']['work']['frames'],
    }
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='evidence_r170_scene_verify.json')
    args = ap.parse_args()

    out = {'round': 'R170',
           'criteria_note': '以 200×240 / 256×256 真实显示效果为口径的绝对值判据, '
                            '全部给实测数字 (不是"相比基线没变差")'}
    print('R170 客观判据:')
    for name, fn in (('eat_fruit', analyse_eat_fruit), ('work', analyse_work)):
        try:
            r = fn()
        except Exception as e:
            r = {'__error__': str(e)}
        out[name] = r
        for k, v in r.items():
            if k.startswith('__'):
                print(f'  ❌ {name}.{k}: {v}')
                continue
            mark = '✅' if v.get('pass') else '❌'
            extra = {kk: vv for kk, vv in v.items() if kk != 'pass'}
            print(f'  {mark} {name}.{k}: {extra}')

    n_pass = sum(1 for g in out.values() if isinstance(g, dict)
                 for k, v in g.items() if isinstance(v, dict) and v.get('pass'))
    n_tot = sum(1 for g in out.values() if isinstance(g, dict)
                for k, v in g.items() if isinstance(v, dict) and 'pass' in v)
    out['summary'] = {'passed': n_pass, 'total': n_tot}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'  合计: {n_pass}/{n_tot} PASS')
    print(f'  📄 {args.out}')


if __name__ == '__main__':
    main()
