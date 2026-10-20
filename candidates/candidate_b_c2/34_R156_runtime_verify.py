#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R156 运行时客观校验 — 直接量**真实 Electron 采集到的像素**, 不看脚本自报。

校验项:
  1. 点击池随机性: 连续 10 次真实点击 → 触发的动作 ≥3 种, 且**没有相邻重复**
  2. 每个点击动作确实有"开始/中间/结束": 采集帧里至少 3 个**互不相同**的剪影
  3. 睡觉场景真的有床与月亮 (正向对照: 道具区域里必须有像素)
  4. 坐下场景真的有沙发 / 办公场景真的有笔记本 (同上)
  5. **道具不残留**: 退出动作后, 道具所在区域必须重新变透明 (用"道具掩膜 - 角色掩膜"精确判定)
  6. 道具不遮脸: front 层道具的屏幕区域不得覆盖角色脸部区域
  7. 角色身份未漂移: 睡觉/沙发/办公三个场景里, 角色区域的主色仍是银白+冰蓝+白大褂

判定全部基于像素, 不依赖脚本自报的 PASS。
"""
import json
import os
import sys
import argparse

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
MANIFEST = os.path.join(ASSETS, 'character_R141_manifest.json')

CANVAS_W, CANVAS_H = 200, 240
MARGIN = 4
GROUND_Y = CANVAS_H - MARGIN
TEX = 1024
ANCHOR_TEX_Y = 0.9 * TEX

results = []


def check(name, ok, detail=''):
    results.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(f"  {'✅' if ok else '❌'} {name}" + (f"  — {detail}" if detail else ''))
    return ok


def alpha_bbox(arr, thr=24):
    a = arr[:, :, 3] > thr
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def to_rect(bb):
    if not bb:
        return None
    return dict(left=bb[0], top=bb[1], right=bb[2], bottom=bb[3])


def load_rgba(rel):
    return np.asarray(Image.open(os.path.join(ASSETS, rel)).convert('RGBA'))


def uniform_scale(bboxes):
    half_w = CANVAS_W / 2 - MARGIN
    avail_h = CANVAS_H - 2 * MARGIN
    scale = float('inf')
    for bb in bboxes:
        if not bb:
            continue
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if w <= 0 or h <= 0:
            continue
        scale = min(scale, avail_h / h)
        min_lx, max_lx = bb[0] - 512, bb[2] - 512
        if min_lx < 0:
            scale = min(scale, half_w / (-min_lx))
        if max_lx > 0:
            scale = min(scale, half_w / max_lx)
    return scale


def compute_layout(m):
    """与 sprite_layout.computeLayout 等价的 Python 实现 (供像素级核算)。"""
    frames = []
    for src in (m['actions'], (m.get('action_library') or {}).get('actions') or {}):
        for action, spec in src.items():
            boxes = (m['layout'].get('frame_bboxes') or {}).get(action) or []
            g = spec.get('ground_tex_y')
            for i in range(len(spec.get('frames') or [])):
                bb = boxes[i] if i < len(boxes) else None
                gv = (g[i] if isinstance(g, list) else g) if g is not None else None
                frames.append({'action': action, 'index': i, 'bbox': bb, 'g': gv})
    scale = uniform_scale([f['bbox'] for f in frames])
    frame_y = {}
    for f in frames:
        bb = f['bbox']
        if not bb:
            continue
        ground_row = f['g'] if isinstance(f['g'], (int, float)) else bb[3]
        frame_y[(f['action'], f['index'])] = GROUND_Y - (ground_row - ANCHOR_TEX_Y) * scale
    return {'scale': scale, 'x': CANVAS_W / 2, 'groundY': GROUND_Y, 'frame_y': frame_y}


def screen_mask(arr, layout, frame_y, thr=24):
    """把一张纹理帧按生产变换投到屏幕, 得到屏幕空间的 alpha 掩膜。"""
    H, W = CANVAS_H, CANVAS_W
    mask = np.zeros((H, W), dtype=bool)
    ys, xs = np.nonzero(arr[:, :, 3] > thr)
    if len(xs) == 0:
        return mask
    sx = np.round(layout['x'] + layout['scale'] * (xs - 512)).astype(int)
    sy = np.round(frame_y + layout['scale'] * (ys - ANCHOR_TEX_Y)).astype(int)
    ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
    mask[sy[ok], sx[ok]] = True
    return mask


def scene_frames(meta, scene):
    return [f['file'] for f in (meta.get(scene) or [])]


def load_captured(path):
    return np.asarray(Image.open(path).convert('RGBA'))


def dilate(mask, r=2):
    out = mask.copy()
    for _ in range(r):
        o = out.copy()
        o[1:, :] |= out[:-1, :]
        o[:-1, :] |= out[1:, :]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


def diff_ratio(a, b):
    if a.shape != b.shape:
        return 1.0
    d = np.abs(a.astype(np.int32) - b.astype(np.int32)).sum(axis=2)
    return float((d > 40).sum()) / max(1, a.shape[0] * a.shape[1])


def iris_blue_count(im):
    """头部区域的"虹膜蓝"像素数 (睁眼有, 闭眼/眨眼几乎没有)。

    与 27_R153_runtime_verify.py 的 iris_pixels 同口径 (头部取整体高度的 30%)。
    入参为 RGBA 的 numpy 数组 (load_captured 的返回值)。
    """
    a = np.asarray(im).astype(np.int32)
    if a.ndim != 3 or a.shape[2] < 4:
        return 0
    m = a[:, :, 3] > 60
    ys, xs = np.where(m)
    if len(xs) == 0:
        return 0
    y0, y1 = ys.min(), ys.max()
    h = max(1, y1 - y0)
    head = a[y0:y0 + int(h * 0.30), :, :]
    hm = m[y0:y0 + int(h * 0.30), :]
    r, g, b = head[:, :, 0], head[:, :, 1], head[:, :, 2]
    blue = (b > 130) & (b > r + 25) & (b > g + 8) & hm
    return int(blue.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview-dir', default='evidence_r156_preview')
    a = ap.parse_args()

    m = json.load(open(MANIFEST, encoding='utf-8'))
    meta = json.load(open(os.path.join(a.preview_dir, 'preview_meta.json'), encoding='utf-8'))
    layout = compute_layout(m)
    props = m.get('props') or {}
    lib = props.get('library') or {}
    scenes = props.get('scenes') or {}

    print("R156 运行时客观校验 (全部基于真实采集像素):")
    print(f"  布局: scale={layout['scale']:.6f} groundY={layout['groundY']}")

    # ---------- 1. 点击池随机性 ----------
    seq = meta.get('click_pool_random') or []
    uniq = sorted(set(seq))
    adjacent_repeat = any(seq[i] == seq[i + 1] for i in range(len(seq) - 1))
    check('1. 真实点击 10 次触发的动作 ≥3 种', len(uniq) >= 3,
          f'序列 = {",".join(seq)} (共 {len(uniq)} 种)')
    check('1b. 相邻两次点击没有重复同一个动作', not adjacent_repeat,
          f'相邻重复 = {adjacent_repeat}')

    # ---------- 2. 每个点击动作有 ≥3 个互不相同的剪影 ----------
    for scene in ('click_cheer_heart', 'click_cheer_jump', 'click_cheer_spin',
                  'click_cheer_wink', 'click_cheer_hands', 'click_cheer_sway'):
        files = scene_frames(meta, scene)
        if not files:
            check(f'2. {scene} 有采集帧', False, '无采集帧')
            continue
        imgs = [load_captured(f) for f in files]
        base = imgs[0]
        dists = [diff_ratio(base, im) for im in imgs]
        # 把采集帧按"画面是否相同"聚类 (同一状态的两帧差异 <0.5%) → 状态数 = 开始/中间/结束
        groups = []
        for im in imgs:
            for g in groups:
                if diff_ratio(g[0], im) < 0.005:
                    g.append(im)
                    break
            else:
                groups.append([im])
        check(f'2. {scene} 至少有 3 个互不相同的画面 (开始/中间/结束)', len(groups) >= 3,
              f'{len(imgs)} 帧 → {len(groups)} 个不同画面, 帧间差异 {min(dists):.4f}~{max(dists):.4f}')

    # ---------- 3/4/5. 道具的存在与退场 (用"道具掩膜 - 角色掩膜"精确判定) ----------
    def prop_scene_mask(scene_name, action, frame_index, prop_names):
        """返回 (道具掩膜, 角色掩膜) —— 屏幕空间。"""
        scene = scenes[scene_name]
        floor = scene['floor_tex_y']
        prop_y = GROUND_Y - (floor - ANCHOR_TEX_Y) * layout['scale']
        pm = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
        for n in prop_names:
            arr = load_rgba(lib[n]['file'])
            ys, xs = np.nonzero(arr[:, :, 3] > 24)
            sx = np.round(layout['x'] + layout['scale'] * (xs - 512)).astype(int)
            sy = np.round(prop_y + layout['scale'] * (ys - ANCHOR_TEX_Y)).astype(int)
            ok = (sx >= 0) & (sx < CANVAS_W) & (sy >= 0) & (sy < CANVAS_H)
            pm[sy[ok], sx[ok]] = True
        char_masks = []
        spec = (m['actions'].get(action) or (m.get('action_library', {}).get('actions') or {}).get(action))
        for idx in range(len(spec['frames'])):
            fy = layout['frame_y'].get((action, idx))
            if fy is None:
                continue
            char_masks.append(screen_mask(load_rgba(spec['frames'][idx]), layout, fy))
        cm = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
        for x in char_masks:
            cm |= x
        return pm, cm

    def count_prop_pixels(captured, prop_mask, char_mask):
        # 角色掩膜向外膨胀 2px: 排除角色自身的抗锯齿边缘被误判成"道具残留"
        region = prop_mask & (~dilate(char_mask, 2))
        vis = captured[:, :, 3] > 24
        return int((vis & region).sum())

    # 3. 睡觉场景: 床 + 月亮 + 被子必须在 (正向对照)
    sleep_files = scene_frames(meta, 'scene_sleep')
    if sleep_files:
        pm, cm = prop_scene_mask('sleep_breath', 'sleep_breath', 0,
                                  scenes['sleep_breath']['back'] + scenes['sleep_breath']['front'])
        cap = load_captured(sleep_files[len(sleep_files) // 2])
        n = count_prop_pixels(cap, pm, cm)
        check('3. 睡觉场景里道具(床/月亮/被子)真实可见', n > 400,
              f'道具专属区域可见像素 = {n} (阈值 400)')
    else:
        check('3. 睡觉场景里道具真实可见', False, '无采集帧')

    # 4. 沙发 / 办公
    for scene_name, action, label, thr in (('scene_sofa', 'sit_rest', '坐下场景的沙发', 400),
                                           ('scene_work', 'work', '办公场景的桌子/笔记本/微光', 400)):
        files = scene_frames(meta, scene_name)
        if not files:
            check(f'4. {label}真实可见', False, '无采集帧')
            continue
        sc = scenes[action]
        pm, cm = prop_scene_mask(action, action, 0, sc['back'] + sc['front'])
        cap = load_captured(files[len(files) // 2])
        n = count_prop_pixels(cap, pm, cm)
        check(f'4. {label}真实可见', n > thr, f'道具专属区域可见像素 = {n} (阈值 {thr})')

    # 5. 道具退场: 最后几帧里道具区域必须重新透明
    exit_files = scene_frames(meta, 'scene_prop_exit')
    if exit_files:
        pm, cm = prop_scene_mask('sleep_breath', 'idle', 0,
                                  scenes['sleep_breath']['back'] + scenes['sleep_breath']['front'])
        last = [load_captured(f) for f in exit_files[-4:]]
        ns = [count_prop_pixels(c, pm, cm) for c in last]
        check('5. 退出动作后道具不残留 (道具区域重新变透明)', max(ns) <= 30,
              f'最后 4 帧的道具残留像素 = {ns} (阈值 30)')
        # 正向对照: 睡觉场景里同样的区域是有像素的
        if sleep_files:
            cap = load_captured(sleep_files[len(sleep_files) // 2])
            n_sleep = count_prop_pixels(cap, pm, cm)
            check('5b. 正向对照: 同一区域在睡觉场景里确有像素 (证明 5 的判据有效)',
                  n_sleep > 400, f'睡觉场景同一区域像素 = {n_sleep}')
    else:
        check('5. 退出动作后道具不残留', False, '无采集帧')

    # 6. 道具不遮脸 (屏幕空间判定)
    for action, sc in scenes.items():
        spec = (m['actions'].get(action) or (m.get('action_library', {}).get('actions') or {}).get(action))
        if not spec:
            continue
        face_rows = []
        for idx in range(len(spec['frames'])):
            fy = layout['frame_y'].get((action, idx))
            arr = load_rgba(spec['frames'][idx])
            ys, xs = np.nonzero(arr[:, :, 3] > 24)
            sy = np.round(fy + layout['scale'] * (ys - ANCHOR_TEX_Y)).astype(int)
            sx = np.round(layout['x'] + layout['scale'] * (xs - 512)).astype(int)
            ok = (sx >= 0) & (sx < CANVAS_W) & (sy >= 0) & (sy < CANVAS_H)
            face_rows.append((sy[ok], sx[ok]))
        if not face_rows:
            continue
        # 脸部 = 角色掩膜的最上面 18% (头部)
        allsy = np.concatenate([r[0] for r in face_rows])
        face_cut = int(np.percentile(allsy, 18))
        face_mask = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
        for sy, sx in face_rows:
            sel = sy <= face_cut
            face_mask[sy[sel], sx[sel]] = True
        floor = sc['floor_tex_y']
        prop_y = GROUND_Y - (floor - ANCHOR_TEX_Y) * layout['scale']
        front_mask = np.zeros((CANVAS_H, CANVAS_W), dtype=bool)
        for n in (sc.get('front') or []):
            arr = load_rgba(lib[n]['file'])
            ys, xs = np.nonzero(arr[:, :, 3] > 24)
            sx = np.round(layout['x'] + layout['scale'] * (xs - 512)).astype(int)
            sy = np.round(prop_y + layout['scale'] * (ys - ANCHOR_TEX_Y)).astype(int)
            ok = (sx >= 0) & (sx < CANVAS_W) & (sy >= 0) & (sy < CANVAS_H)
            front_mask[sy[ok], sx[ok]] = True
        covered = int((front_mask & face_mask).sum())
        check(f'6. 场景 {action} 的 front 层道具没有遮住脸', covered == 0,
              f'重叠像素 = {covered}')

    # 7. 身份未漂移: 三个场景里角色的主色仍是银白/冰蓝/白大褂
    for scene_name, action in (('scene_sleep', 'sleep_breath'), ('scene_sofa', 'sit_rest'),
                               ('scene_work', 'work')):
        files = scene_frames(meta, scene_name)
        if not files:
            continue
        cap = load_captured(files[len(files) // 2])
        rgb = cap[:, :, :3].astype(int)
        vis = cap[:, :, 3] > 24
        if vis.sum() < 100:
            check(f'7. {scene_name} 角色主色未漂移', False, '可见像素太少')
            continue
        px = rgb[vis]
        white = ((px[:, 0] > 195) & (px[:, 1] > 195) & (px[:, 2] > 195)).mean()
        blue = ((px[:, 2] > px[:, 0] + 18) & (px[:, 2] > 120)).mean()
        silver = ((px[:, 0] > 120) & (px[:, 0] < 235) & (abs(px[:, 0] - px[:, 2]) < 22)).mean()
        check(f'7. {scene_name} 角色主色未漂移 (银白+冰蓝+白大褂)',
              white > 0.25 and blue > 0.04 and silver > 0.10,
              f'白 {white:.2f} / 冰蓝 {blue:.2f} / 银白 {silver:.2f}')

    # ---------- 8. 点击反馈明显区别于僵立待机 (R156 口径) ----------
    #   R153 当年的代理判据是"点击反馈必须用 happy 闭眼笑 (虹膜≈8)",
    #   但 R156 的点击反馈是**随机池多帧动作**, 每个动作面部状态本就不同
    #   (cheer_wink 只闭一只眼 ⇒ 虹膜 14), 该代理判据已失效。
    #   改为等价且更稳的表述: 点击反馈必须明显区别于僵立待机 ——
    #     ① 表情变化 (虹膜像素 < 睁眼待机), 或 ② 姿态变化 (整图平均差 ≥ 6)。
    idle_files = scene_frames(meta, 'idle')
    click_files = scene_frames(meta, 'click')
    if idle_files and click_files:
        idle_arrs = [load_captured(f).astype(int) for f in idle_files[:20]]
        ck_iris = [iris_blue_count(load_captured(f)) for f in click_files[:12]]
        idle_iris = [iris_blue_count(load_captured(f)) for f in idle_files[:8]]
        ck_min = min(ck_iris) if ck_iris else 0
        idle_min = min(idle_iris) if idle_iris else 0
        mad_max = 0.0
        for f in click_files:
            cf = load_captured(f).astype(int)
            mad_max = max(mad_max, min(float(np.abs(cf - j).mean()) for j in idle_arrs))
        face_changed = ck_min < idle_min
        pose_changed = mad_max >= 6.0
        check('8. 点击反馈明显区别于僵立待机 (表情变化或姿态变化)',
              face_changed or pose_changed,
              f'点击段虹膜 min={ck_min} / 睁眼待机 min={idle_min} → 表情变化={face_changed}; '
              f'到最近待机帧的最大整图平均差={mad_max:.2f} (门槛 6) → 姿态变化={pose_changed}')
    else:
        check('8. 点击反馈明显区别于僵立待机', False, '无 idle / click 采集帧')

    passed = sum(1 for r in results if r['ok'])
    failed = sum(1 for r in results if not r['ok'])
    out = {'round': 'R156', 'passed': passed, 'failed': failed, 'checks': results}
    with open(os.path.join(a.preview_dir, 'r156_runtime_verify.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('')
    print(f"R156 运行时客观校验: {passed} passed, {failed} failed (共 {len(results)})")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
