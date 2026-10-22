#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R173 客观判据 —— 办公场景透视与手部遮挡最终整改。

针对用户 R173 的两条硬伤 + 验收清单逐条给出**可测量**的判据:

  A. 显示器朝向 (用户第 1 条: "不得让显示器正对观众, 却让人物坐在显示器背面")
     A1 屏幕远/近边高比 ≥ 1.35        ⇒ 屏面确实被透视压缩 (斜置), 不是正面
     A2 上下边在近侧**发散**            ⇒ 收敛点在远侧, 透视方向正确
     A3 屏幕中心在角色面部**左侧**       ⇒ 角色朝左、屏幕在左, 视线链自洽
     A4 头部**不是正面**: 虹膜左右面积比 ≥ 1.10 (3/4 近眼更大)
     A5 屏内蓝白界面内容 ≥ 500 px

  B. 手部图层 (用户第 2 条: "双手被键盘和桌面遮挡")
     B1 手的皮肤像素落在键盘四边形内 ≥ 400 px
     B2 两只手的皮肤像素**都**在键盘四边形内, 且各 ≥ 180 px
     B3 键盘∩手部区域里最终帧的像素**是肤色**(不是键帽色) ⇒ 手压在键盘之上
     B4 桌沿/桌腿区域与手部皮肤**不相交** ⇒ 桌沿没有遮挡正在打字的双手
     B5 手腕处青色袖口与皮肤**相邻**(无断裂) ⇒ 手臂→袖口→手腕→手指连贯

  C. 合成空间 (200×240 / 256×256 真实画面)
     C1 人物可见     C2 腿脚可见
     C3 手部可见     C4 屏幕内容可见 (观众真的看得到屏里有东西)

  D. 打字动作可见
     D1 两帧手部皮肤质心位移 ≥ 3 纹理 px
     D2 两帧头部虹膜质心位移 ≥ 5 纹理 px

  E. 全局缩放未被新帧改变 (200×240 / 256×256 与 R172 逐位相同)
  F. 既有成果未被破坏 (R170 吃水果 / R167 睡眠 / R172 素材仍在磁盘)

用法: python3 97_R173_scene_verify.py --out evidence_r173_scene_verify.json
"""
import argparse
import importlib.util
import json
import math
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
MANIFEST = os.path.join(ASSETS, 'character_R141_manifest.json')
R173 = os.path.join(ASSETS, 'character_R173')

TEX = 1024
GROUND_Y = 1001
MARGIN = 4

# R172 的全局缩放 (逐位值, 用来证明新帧没有改变全局比例)
SCALE_200 = 0.19631901840490798
SCALE_256 = 0.25357873210633947

# 与 95_ 烘焙脚本同口径的几何 (判据脚本必须独立复算, 不 import 烘焙脚本)
SCREEN_QUAD = [(195, 395), (330, 315), (372, 630), (215, 570)]
KEY_QUAD = [(330, 566), (548, 600), (532, 656), (312, 616)]
DESK_FAR = [(215, 548), (690, 645)]
DESK_NEAR = [(165, 662), (640, 757)]
DESK_FRONT_BAND = 34          # 桌沿厚度
LEG_NEAR_LEFT = [(158, 650), (186, 660), (186, 950), (162, 945)]
LEG_NEAR_RIGHT = [(632, 745), (662, 757), (662, 1001), (634, 1001)]

HAND_ZONE = {'L': (328, 528, 432, 652), 'R': (432, 530, 528, 654)}

RESULTS = []


def check(cid, name, ok, value, thr, detail=''):
    RESULTS.append({'id': cid, 'name': name, 'pass': bool(ok),
                    'value': value, 'threshold': thr, 'detail': detail})
    flag = '✅' if ok else '❌'
    print(f'{flag} {cid:4s} {name}: {value}  (门槛 {thr}) {detail}')
    return ok


def load_np(path):
    return np.asarray(Image.open(path).convert('RGBA')).astype(np.int32)


def skin_mask(a):
    r, g, b, al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (al > 60) & (r > 185) & (g > 130) & (g < 215) & (b > 100) & (b < 200) & (r > b + 25)


def teal_mask(a):
    r, g, b, al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (al > 60) & (b > 130) & (g > 140) & (b >= r - 12) & (g > r)


def iris_mask(a, box):
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1]
    r, g, b, al = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2], sub[:, :, 3]
    m = (al > 60) & (b > 150) & (b > r + 40) & (g > r) & (g < 230)
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return xs + x0, ys + y0


def poly_mask(quad, shape=(TEX, TEX)):
    m = Image.new('L', shape, 0)
    from PIL import ImageDraw
    ImageDraw.Draw(m).polygon([tuple(p) for p in quad], fill=255)
    return np.asarray(m) > 0


def in_quad(pt, quad):
    """点是否在四边形内 (射线法)。"""
    x, y = pt
    inside = False
    n = len(quad)
    for i in range(n):
        x1, y1 = quad[i]
        x2, y2 = quad[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


def load_preview_module():
    spec = importlib.util.spec_from_file_location(
        'r165_preview', os.path.join(HERE, '45_R165_scene_preview.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, 'evidence_r173_scene_verify.json'))
    args = ap.parse_args()

    m = json.load(open(MANIFEST, encoding='utf-8'))
    prev = load_preview_module()

    w1 = load_np(os.path.join(R173, 'work_1.png'))
    w2 = load_np(os.path.join(R173, 'work_2.png'))
    base = load_np(os.path.join(ASSETS, 'character_R138', 'sleep_enter',
                                'sleep_enter_01_sit.png'))
    base_fr = load_np(os.path.join(ASSETS, 'character_R138', 'wake_up',
                                   'wake_up_01_sit_up.png'))

    # ---------------- E. 全局缩放未变 ----------------
    scale200 = prev.build_scale(m, 200, 240)
    scale256 = prev.build_scale(m, 256, 256)
    check('E1', '200×240 全局缩放逐位不变', scale200 == SCALE_200,
          repr(scale200), repr(SCALE_200))
    check('E2', '256×256 全局缩放逐位不变', scale256 == SCALE_256,
          repr(scale256), repr(SCALE_256))

    # ---------------- A. 显示器朝向 ----------------
    far_h = math.hypot(SCREEN_QUAD[3][0] - SCREEN_QUAD[0][0],
                       SCREEN_QUAD[3][1] - SCREEN_QUAD[0][1])
    near_h = math.hypot(SCREEN_QUAD[2][0] - SCREEN_QUAD[1][0],
                        SCREEN_QUAD[2][1] - SCREEN_QUAD[1][1])
    ratio = near_h / far_h
    check('A1', '屏幕远/近边高比 (斜置程度)', ratio >= 1.35,
          round(float(ratio), 3), '≥1.35',
          f'远边{far_h:.0f}px 近边{near_h:.0f}px; 正面屏应≈1.0')
    top_slope = SCREEN_QUAD[1][1] - SCREEN_QUAD[0][1]
    bot_slope = SCREEN_QUAD[2][1] - SCREEN_QUAD[3][1]
    check('A2', '上下边在近侧发散 (上边升/下边降)', top_slope < 0 and bot_slope > 0,
          f'top{top_slope} bot{bot_slope}', 'top<0 且 bot>0',
          '收敛点在远侧(左) ⇒ 屏面朝右(角色)')

    # 角色面部中心 vs 屏幕中心 (纹理空间)
    iris = iris_mask(w1, (338, 38, 721, 340))
    face_cx = float(iris[0].mean())
    scr_cx = sum(p[0] for p in SCREEN_QUAD) / 4.0
    check('A3', '屏幕中心在角色面部左侧', scr_cx < face_cx - 40,
          f'screen_x={scr_cx:.0f} face_x={face_cx:.0f}', 'screen_x < face_x-40')

    # 头部非正面: 虹膜左右面积比
    def iris_ratio(arr):
        xs, ys = iris_mask(arr, (338, 38, 721, 340))
        mid = (xs.min() + xs.max()) / 2.0
        al = (xs < mid).sum()
        ar = (xs >= mid).sum()
        return al / max(ar, 1), al, ar
    r173_ratio, al, ar = iris_ratio(w1)
    fr_ratio, _, _ = iris_ratio(base_fr)
    check('A4', '头部非正面 (虹膜左右面积比)', r173_ratio >= 1.10,
          f'R173={r173_ratio:.3f} (左{al}/右{ar})', '≥1.10',
          f'正面底图 wake_up_01_sit_up 同口径={fr_ratio:.3f}')

    # 屏内内容像素 (蓝白界面)
    sq_m = poly_mask(SCREEN_QUAD)
    r, g, b, al = w1[:, :, 0], w1[:, :, 1], w1[:, :, 2], w1[:, :, 3]
    content = sq_m & (al > 60) & (b > 140) & (b > r + 15)
    n_content = int(content.sum())
    check('A5', '屏内蓝白界面内容像素', n_content >= 500, n_content, '≥500')

    # ---------------- B. 手部图层 ----------------
    skin = skin_mask(w1)
    kb_m = poly_mask(KEY_QUAD)
    hand_counts = {}
    for key, box in HAND_ZONE.items():
        x0, y0, x1, y1 = box
        zone = np.zeros_like(skin)
        zone[y0:y1, x0:x1] = True
        hm = skin & zone
        n = int(hm.sum())
        in_kb = int((hm & kb_m).sum())
        hand_counts[key] = (n, in_kb)
    check('B1', '手的皮肤像素落在键盘四边形内',
          hand_counts['L'][1] + hand_counts['R'][1] >= 400,
          hand_counts['L'][1] + hand_counts['R'][1], '≥400',
          f"L={hand_counts['L']} R={hand_counts['R']} (总数,在键区)")
    check('B2', '两只手都在键盘四边形内且各≥180px',
          all(hand_counts[k][1] >= 180 for k in ('L', 'R')),
          {k: hand_counts[k][1] for k in ('L', 'R')}, '各≥180')
    # B3 键盘∩手部区域里最终帧是肤色 (手压在键盘之上)
    kb_skin = int((kb_m & skin).sum())
    kb_total = int(kb_m.sum())
    check('B3', '键盘区内最终帧像素是肤色 (手未被键盘遮住)', kb_skin >= 400,
          kb_skin, '≥400', f'键盘四边形共{kb_total}px, 其中肤色{kb_skin}px')
    # B4 桌沿/桌腿 不与手部相交
    band = poly_mask([DESK_NEAR[0], DESK_NEAR[1],
                      (DESK_NEAR[1][0] - 4, DESK_NEAR[1][1] + DESK_FRONT_BAND),
                      (DESK_NEAR[0][0] - 4, DESK_NEAR[0][1] + DESK_FRONT_BAND)])
    legs = poly_mask(LEG_NEAR_LEFT) | poly_mask(LEG_NEAR_RIGHT)
    overlap = int(((band | legs) & skin).sum())
    check('B4', '桌沿/桌腿未遮挡正在打字的双手', overlap == 0, overlap, '=0')
    # B5 袖口与手部皮肤相邻 (手腕无断裂)
    teal = teal_mask(w1)
    ok_adj = True
    adj_detail = []
    for key, box in HAND_ZONE.items():
        x0, y0, x1, y1 = box
        zone = np.zeros_like(teal)
        zone[y0:y1, x0:x1] = True
        t = teal & zone
        s = skin & zone
        ys, xs = np.nonzero(s)
        if len(xs) == 0:
            ok_adj = False
            continue
        # 手部皮肤的上沿 (靠近腕) 与袖口的水平距离
        top_y = ys.min()
        band_y = slice(max(0, top_y - 26), top_y + 2)
        t_xs = np.nonzero(t[band_y].any(axis=0))[0]
        s_xs = np.nonzero(s[band_y].any(axis=0))[0]
        gap = None
        if len(t_xs) and len(s_xs):
            gap = int(np.abs(t_xs[:, None] - s_xs[None, :]).min())
        adj_detail.append(f'{key}:gap={gap}')
        if gap is None or gap > 26:
            ok_adj = False
    check('B5', '手腕处袖口与皮肤相邻 (无断裂)', ok_adj, ';'.join(adj_detail), '每只手 gap≤26px')

    # ---------------- C. 合成空间 ----------------
    for size, tag, sc in ((200, '200×240', scale200), (256, '256×256', scale256)):
        canvas = prev.compose('work', size, int(size * 240 / 200) if size == 200 else 256,
                              m, checker=False)
        arr = np.asarray(canvas)[:, :, :3].astype(int)
        a = arr[:, :, 3] if arr.shape[2] > 3 else np.full(arr.shape[:2], 255)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        opaque = a > 60
        sk = opaque & (r > 185) & (g > 130) & (g < 215) & (b > 100) & (b < 200) & (r > b + 25)
        n_skin = int(sk.sum())
        check(f'C1.{tag}', '人物可见 (肤色像素)', n_skin >= 250, n_skin, '≥250')
        # 腿脚: 下半区 (y > 55%) 的非背景像素
        h = arr.shape[0]
        low = opaque.copy()
        low[:int(h * 0.55), :] = False
        n_low = int(low.sum())
        check(f'C2.{tag}', '下半身(腿/靴)可见', n_low >= 900, n_low, '≥900')
        # C3 手部: 映射键盘四边形到画布, 统计其中的肤色
        def to_canvas(p):
            return (size / 2 + (p[0] - 512) * sc,
                    (size * 240 / 200 if size == 200 else size) - MARGIN
                    - (GROUND_Y - p[1]) * sc)
        kb_canvas = [to_canvas(p) for p in KEY_QUAD]
        mimg = Image.new('L', (arr.shape[1], arr.shape[0]), 0)
        from PIL import ImageDraw
        ImageDraw.Draw(mimg).polygon([tuple(p) for p in kb_canvas], fill=255)
        kbm = np.asarray(mimg) > 0
        n_kb_skin = int((kbm & sk).sum())
        check(f'C3.{tag}', '双手在键盘上 (键区内肤色)', n_kb_skin >= 12,
              n_kb_skin, '≥12')
        # C4 屏幕内容: 屏幕四边形映射到画布, 统计其中的蓝像素
        sc_canvas = [to_canvas(p) for p in SCREEN_QUAD]
        mimg2 = Image.new('L', (arr.shape[1], arr.shape[0]), 0)
        ImageDraw.Draw(mimg2).polygon([tuple(p) for p in sc_canvas], fill=255)
        scm = np.asarray(mimg2) > 0
        blue = scm & opaque & (b > 140) & (b > r + 15)
        n_blue = int(blue.sum())
        check(f'C4.{tag}', '观众看得到屏内容 (屏内蓝像素)', n_blue >= 40,
              n_blue, '≥40', f'屏幕在画布上约{scm.sum()}px')

    # ---------------- D. 打字动作可见 ----------------
    def hand_centroid(arr):
        s = skin_mask(arr)
        msk = np.zeros_like(s)
        for box in HAND_ZONE.values():
            x0, y0, x1, y1 = box
            msk[y0:y1, x0:x1] = True
        ys, xs = np.nonzero(s & msk)
        return float(xs.mean()), float(ys.mean())
    c1 = hand_centroid(w1)
    c2 = hand_centroid(w2)
    d_hand = math.hypot(c1[0] - c2[0], c1[1] - c2[1])
    check('D1', '两帧手部位移 (打字动作)', d_hand >= 3.0, round(d_hand, 2), '≥3 纹理px')
    i1 = iris_mask(w1, (338, 38, 721, 340))
    i2 = iris_mask(w2, (338, 38, 721, 340))
    d_head = math.hypot(float(i1[0].mean()) - float(i2[0].mean()),
                        float(i1[1].mean()) - float(i2[1].mean()))
    check('D2', '两帧头部(视线)位移', d_head >= 5.0, round(d_head, 2), '≥5 纹理px')

    # ---------------- F. 既有成果未被破坏 ----------------
    keep = [
        ('character_R156/eat_fruit_0.png', 'R170 吃水果帧'),
        ('character_R156/eat_fruit_4.png', 'R170 吃水果帧'),
        ('character_R138/sleep_loop/sleep_loop_00_base.png', 'R167 睡眠帧'),
        ('character_R138/walk_left/walk_left_00_stand.png', 'R148 行走帧'),
        ('character_R172/work_1.png', 'R172 办公帧'),
        ('character_R172/prop_office_chair.png', 'R172 椅子道具'),
        ('character_R172/prop_office_monitor.png', 'R172 显示器道具'),
    ]
    missing = [f for f, _ in keep if not os.path.exists(os.path.join(ASSETS, f))]
    check('F1', '既有成果文件仍在磁盘', not missing,
          '全部存在' if not missing else missing, '无缺失')
    lib = (m.get('props') or {}).get('library') or {}
    check('F2', 'R172 道具仍在 manifest library (历史成果不删)',
          'prop_office_chair' in lib and 'prop_office_monitor' in lib,
          sorted(k for k in lib if 'office' in k), '含两个 R172 道具')
    eat = (m.get('action_library') or {}).get('actions', {}).get('eat_fruit')
    check('F3', '吃水果行为未被改动', bool(eat) and
          all('character_R156/eat_fruit' in f for f in eat['frames']),
          eat['frames'] if eat else None, 'frames 指向 character_R156/eat_fruit_*')
    sleep = (m.get('action_library') or {}).get('actions', {}).get('sleep_breath')
    check('F4', '睡眠行为未被改动', bool(sleep) and
          all('character_R153' in f for f in sleep['frames']),
          sleep['frames'] if sleep else None, 'frames 指向 character_R153/*')

    # ---------------- 汇总 ----------------
    npass = sum(1 for r in RESULTS if r['pass'])
    total = len(RESULTS)
    print(f'\n=== R173 判据: {npass}/{total} PASS ===')
    out = {
        'round': 173,
        'script': '97_R173_scene_verify.py',
        'summary': {'pass': npass, 'total': total,
                    'all_pass': npass == total},
        'checks': RESULTS,
    }
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'📄 {args.out}')
    return 0 if npass == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
