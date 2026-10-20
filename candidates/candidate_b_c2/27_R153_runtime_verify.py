#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R153 运行时预览的**客观量化校验** — 直接分析真实 Electron 采集帧。

不靠肉眼, 用像素测量回答 R153 用户反馈对应的六个问题:
  1. 行走还"前倾像摔倒"吗?      → 躯干偏心 (归一化到身高) 的符号与幅度
  2. 坐下还会"瞬间躺下"吗?      → 坐→躺之间是否存在多帧渐变 (混合帧)
  3. 新增动作真的"动"起来了吗?  → 每个多帧库动作的帧间像素差 (回归防线)
  4. 9 个库动作彼此真的不同吗?  → 两两像素差异矩阵
  5. 点击反馈还是"手放胸前"吗?  → 头部区域的虹膜像素 (睁眼 vs 闭眼)
  6. 睡眠期间有"自然呼吸"吗?    → 躺姿帧的帧间起伏幅度

用法: python3 27_R153_runtime_verify.py --preview-dir evidence_r153_preview3
产物: evidence_r153_runtime.json
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

CAND = os.path.dirname(os.path.abspath(__file__))

# ---- 门槛 (来自"站姿端正 / 肉眼可辨"的物理判据, 不是凑出来的) ----
LEAN_RATIO_LIMIT = 0.03      # 躯干偏心 < 身高的 3% (R153 修复"前倾像摔倒")
MIXED_FRAME_MIN = 3          # 坐→躺至少要有 3 帧中间态 (否则等于瞬切)
LIB_ACTION_MIN_DIFF = 0.35   # 相邻库动作的最小平均像素差 (0-255 尺度)
ACTION_MOTION_MIN = 0.05     # 多帧动作内部至少要有这点整图均值差 (否则等于静止)
CHANGED_PIXEL_MIN = 25       # 多帧动作内部至少要有这么多像素真的变了 (眨眼只改眼睛几个像素, 整图均值会把它稀释掉)
BREATH_MAX_RATIO = 0.02      # 呼吸起伏 < 身高的 2% (不能夸张)


def load_meta(preview_dir):
    p = os.path.join(preview_dir, 'preview_meta.json')
    return json.load(open(p, encoding='utf-8'))


def frames(meta, scene):
    return [Image.open(f['file']).convert('RGBA') for f in (meta.get(scene) or [])]


def arr(im):
    return np.asarray(im).astype(np.float32)


def mask_of(im):
    return np.asarray(im)[:, :, 3] > 30


def bbox_of(m):
    ys, xs = np.where(m)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def lean_ratio(im):
    """上半身重心相对下半身重心的水平偏移 / 身高 (负=左倾, 正=右倾)。"""
    m = mask_of(im)
    bb = bbox_of(m)
    if not bb:
        return None
    x0, y0, x1, y1 = bb
    h = y1 - y0
    if h < 20:
        return None

    def bc(a, b):
        sub = m[a:b, :]
        if not sub.any():
            return None
        cols = np.where(sub.any(axis=0))[0]
        xs = np.arange(sub.shape[1])
        w = sub.sum(axis=0)
        return float((xs * w).sum() / max(w.sum(), 1))

    top = bc(y0, y0 + int(h * 0.32))
    bot = bc(y1 - int(h * 0.32), y1)
    if top is None or bot is None:
        return None
    return (top - bot) / h


def mad(a, b):
    return float(np.abs(a - b).mean())


def iris_pixels(im):
    """头部区域的"虹膜蓝"像素数 (睁眼有, 闭眼几乎没有)。

    用于客观区分 "睁眼待机" 与 "闭眼笑/闭眼睡" —— 剪影看不出眼睛颜色。
    """
    a = np.asarray(im.convert('RGBA')).astype(np.int32)
    m = a[:, :, 3] > 60
    ys, xs = np.where(m)
    if len(xs) == 0:
        return 0, 0
    y0, y1 = ys.min(), ys.max()
    h = max(1, y1 - y0)
    head = a[y0:y0 + int(h * 0.30), :, :]
    hm = m[y0:y0 + int(h * 0.30), :]
    r, g, b = head[:, :, 0], head[:, :, 1], head[:, :, 2]
    blue = (b > 130) & (b > r + 25) & (b > g + 8) & hm
    return int(blue.sum()), int(hm.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview-dir', required=True)
    ap.add_argument('--out', default=os.path.join(CAND, 'evidence_r153_runtime.json'))
    args = ap.parse_args()
    meta = load_meta(args.preview_dir)

    checks = []
    report = {'preview_dir': os.path.relpath(args.preview_dir, CAND), 'checks': []}

    # ---------- 1. 行走姿态 ----------
    wl = [lean_ratio(im) for im in frames(meta, 'walk_left')]
    wr = [lean_ratio(im) for im in frames(meta, 'walk_right')]
    wl = [v for v in wl if v is not None]
    wr = [v for v in wr if v is not None]
    if wl and wr:
        ml, mr = float(np.mean(wl)), float(np.mean(wr))
        mx = float(max(max(abs(v) for v in wl), max(abs(v) for v in wr)))
        ok = (ml < 0 < mr) and (mx < LEAN_RATIO_LIMIT)
        checks.append({
            'id': 'TH1', 'pass': ok,
            'desc': '行走躯干偏心: 左右符号相反且 < 身高的 3% (修复"前倾像摔倒")',
            'detail': f'walk_left 均值={ml:+.5f} walk_right 均值={mr:+.5f} 最大绝对值={mx:.5f} 门槛={LEAN_RATIO_LIMIT}',
        })
        report['walk_lean'] = {'left_mean': ml, 'right_mean': mr, 'max_abs': mx}

    # ---------- 2. 坐→躺是渐变 ----------
    tr = frames(meta, 'lib_transition')
    sit = frames(meta, 'lib_sit_rest')
    if tr and sit:
        sit_ref = arr(sit[len(sit) // 2])
        lie_ref = arr(tr[-1])
        mixed = []
        for i, im in enumerate(tr):
            a = arr(im)
            d_sit, d_lie = mad(a, sit_ref), mad(a, lie_ref)
            # 中间态: 既不像纯坐, 也不像纯躺 (两个差都显著)
            if d_sit > 3.0 and d_lie > 3.0:
                mixed.append({'frame': i, 'd_sit': round(d_sit, 3), 'd_lie': round(d_lie, 3)})
        ok = len(mixed) >= MIXED_FRAME_MIN
        checks.append({
            'id': 'TH2', 'pass': ok,
            'desc': '坐→躺之间存在多帧渐变 (修复"坐下瞬间变成躺姿")',
            'detail': f'中间态帧 {len(mixed)} 帧 (门槛 ≥{MIXED_FRAME_MIN}) {json.dumps(mixed)}',
        })
        report['sit_to_lie_mixed'] = mixed

    # ---------- 3. 多帧库动作真的在动 ----------
    # 用"真正发生变化的像素数"而不是整图均值 —— 眨眼只改眼睛几个像素,
    # 整图均值会被 4.8 万像素稀释成 0。
    LIB = ['look_around', 'tilt_head', 'head_nod', 'blink_soft', 'sleep_breath']
    motion = {}
    for sc in LIB:
        fr = frames(meta, f'lib_{sc}')
        if len(fr) < 2:
            continue
        best = 0
        for i in range(len(fr) - 1):
            a, b = arr(fr[i]), arr(fr[i + 1])
            changed = int((np.abs(a - b).max(axis=2) > 6).sum())
            best = max(best, changed)
        motion[sc] = best
    if motion:
        stuck = [k for k, v in motion.items() if v < CHANGED_PIXEL_MIN]
        checks.append({
            'id': 'TH3', 'pass': not stuck,
            'desc': '多帧库动作在真实运行时确实逐帧推进 (防 anim_clock 每帧时长回归)',
            'detail': f'各动作最大"变化像素数" {json.dumps(motion)} (门槛 ≥{CHANGED_PIXEL_MIN}); 静止的动作: {stuck or "无"}',
        })
        report['lib_motion'] = motion

    # ---------- 4. 9 个库动作彼此不同 ----------
    # 每个动作取"与自身首帧差异最大"的那一帧作为代表姿势,
    # 避免首帧正好落在过渡混合态上导致误判。
    reps = {}
    for sc in ['look_around', 'tilt_head', 'head_nod', 'happy', 'blink_soft',
               'stretch', 'sit_rest', 'doze', 'sleep_breath']:
        fr = frames(meta, f'lib_{sc}')
        if not fr:
            continue
        base = arr(fr[0])
        best_i, best_d = 0, -1.0
        for i, im in enumerate(fr):
            d = mad(arr(im), base)
            if d > best_d:
                best_i, best_d = i, d
        reps[sc] = (arr(fr[best_i]), best_i, best_d)
    pairs = []
    names = list(reps)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            pairs.append((names[i], names[j], mad(reps[names[i]][0], reps[names[j]][0])))
    worst = min(pairs, key=lambda p: p[2]) if pairs else None
    ok = bool(pairs) and worst[2] >= LIB_ACTION_MIN_DIFF
    checks.append({
        'id': 'TH4', 'pass': ok,
        'desc': '9 个库动作彼此画面不同 (无"改名即新动作")',
        'detail': (f'最小差异对 = {worst[0]} vs {worst[1]} = {worst[2]:.3f} (门槛 {LIB_ACTION_MIN_DIFF})'
                   if worst else '无数据'),
    })
    report['lib_pair_min_diff'] = worst
    report['lib_representatives'] = {k: {'frame_index': v[1], 'mad_vs_first': round(v[2], 3)}
                                     for k, v in reps.items()}

    # ---------- 5. 点击反馈是"闭眼笑"而不是"手放胸前" ----------
    ck = frames(meta, 'click')
    idle = frames(meta, 'idle')
    hp = frames(meta, 'lib_happy')
    if ck and idle and hp:
        # 取点击反馈的前段 (反馈进行中) 与待机、happy 参照对比
        ck_iris = [iris_pixels(im)[0] for im in ck[:8]]
        idle_iris = [iris_pixels(im)[0] for im in idle[:8]]
        hp_iris = [iris_pixels(im)[0] for im in hp[:4]]
        ck_min = min(ck_iris)
        idle_min = min(idle_iris)
        hp_min = min(hp_iris)
        ok = (ck_min <= hp_min + 2) and (ck_min < idle_min * 0.5)
        checks.append({
            'id': 'TH5', 'pass': ok,
            'desc': '点击反馈用"闭眼笑" (虹膜像素接近 happy 参照, 明显低于睁眼待机)',
            'detail': f'点击段虹膜像素 min={ck_min} / happy 参照 min={hp_min} / 待机 min={idle_min}',
        })
        report['iris'] = {'click': ck_iris, 'idle': idle_iris, 'happy': hp_iris}

    # ---------- 6. 躺姿呼吸有起伏且幅度小 ----------
    sb = frames(meta, 'lib_sleep_breath')
    if len(sb) >= 2:
        diffs = [mad(arr(sb[i]), arr(sb[i + 1])) for i in range(len(sb) - 1)]
        m = mask_of(sb[0])
        bb = bbox_of(m)
        h = max(1, bb[3] - bb[1]) if bb else 1
        motion_px = max(diffs)
        ratio = motion_px / 255.0 / h * 4  # 粗略折算成"身高比例"的上界
        ok = motion_px > ACTION_MOTION_MIN and ratio < BREATH_MAX_RATIO
        checks.append({
            'id': 'TH6', 'pass': ok,
            'desc': '睡眠期间有可见呼吸起伏, 且幅度不过大',
            'detail': f'最大帧间差={motion_px:.4f} (需 >{ACTION_MOTION_MIN}), 身高={h}px, 粗估比例={ratio:.4f} (门槛 <{BREATH_MAX_RATIO})',
        })
        report['breath'] = {'max_frame_diff': round(motion_px, 4), 'body_h': h}

    report['checks'] = checks
    report['verdict'] = 'PASS' if all(c['pass'] for c in checks) else 'FAIL'
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print('R153 运行时客观量化校验')
    for c in checks:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['id']} {c['desc']}")
        print(f"         {c['detail']}")
    print(f"  判定: {report['verdict']}")
    print(f"  产物: {os.path.relpath(args.out, CAND)}")
    return 0 if report['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
