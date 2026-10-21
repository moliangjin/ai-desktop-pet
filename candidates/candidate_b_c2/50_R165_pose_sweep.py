#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 姿势标定扫描器 —— 在"手势可读"与"无多余肢体"之间找可行解。

要解决的矛盾:
  · R158/R162 的手势判据要求**手在胸前**(肤色盒 450..580 × 400..520,
    两掌间距在 400..640 × 320..500 内量) ⇒ 手臂必须抬到胸口高度;
  · 但 R165 的实测: 肘折角 a_e ≥ 96 时**宽袖子前臂横扫胸口**, 读起来就是
    "多出来一双手"(这正是用户真机看到的缺陷)。

本脚本对候选 (a_s, a_e, a_w) 组合输出**绝对量**:
  · 手部皮肤包围盒 / 胸前肤色像素数 (C5 口径) / 两掌间距 (C6 口径)
  · **胸前无根肢体**: 胸前区里"不属于 rig 预期手臂覆盖范围"的皮肤像素 (C1 新口径)
  · 幽灵袖描边残留 (C4)
  · 一张 1024 预览图 (肉眼复核)
"""
import importlib.util
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')

_spec = importlib.util.spec_from_file_location('rig', os.path.join(CAND, '36_R158_arm_rig.py'))
rig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rig)
_spec2 = importlib.util.spec_from_file_location('bake', os.path.join(CAND, '37_R158_action_bake.py'))
bake = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(bake)

BASE = os.path.join(ASSETS, 'character_R138', 'idle', 'idle_00_base.png')
CHEST_ZONE = (420, 380, 610, 520)
C5_ZONE = (450, 400, 580, 520)
GAP_ZONE = (400, 320, 640, 500)
OUT = '/tmp/r165_pose'


def skin_of(a):
    R, G, B, Al = a[:, :, 0], a[:, :, 1], a[:, :, 2], a[:, :, 3]
    return (Al > 40) & (R > 200) & (G > 165) & (B < 228) & ((R - B) > 18)


def zone_count(mask, z):
    return int(mask[z[1]:z[3], z[0]:z[2]].sum())


def hand_gap(mask):
    """两掌间距 (与 tests/r158_click_actions.test.js 的 handGap 同口径)。"""
    x0, y0, x1, y1 = GAP_ZONE
    sub = mask[y0:y1, x0:x1]
    from collections import deque
    seen = np.zeros_like(sub)
    comps = []
    for sy, sx in zip(*np.nonzero(sub)):
        if seen[sy, sx]:
            continue
        q = deque([(sy, sx)]); seen[sy, sx] = True; pts = []
        while q:
            y, x = q.popleft(); pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < sub.shape[0] and 0 <= nx < sub.shape[1] \
                            and sub[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True; q.append((ny, nx))
        if len(pts) >= 150:
            pa = np.array(pts)
            comps.append((int(pa[:, 1].min()), int(pa[:, 1].max())))
    if len(comps) < 2:
        return 0.0, len(comps)
    comps.sort()
    return float(comps[1][0] - comps[0][1]), len(comps)


def run(poses, base_np, rigL, rigR, tag, save=True):
    body = base_np.copy()
    layers = []
    cover = np.zeros(base_np.shape[:2], bool)
    for side in ('L', 'R'):
        r = rigL if side == 'L' else rigR
        ang = poses.get(side) or (0, 0, 0)
        b, _f = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'], fill_mask=r['upper'])
        body = b
        up, fo, hd, ball = rig.pose_arm(base_np, r, ang)
        for lay in (up, fo, hd, ball):
            cover |= (lay[:, :, 3] > 40)
        layers += [up, fo, hd, ball]
    arr = rig.compose(body, layers)
    skin = skin_of(arr)
    # 只取"手"的肤色 (排除脸/腿): 手 = 皮肤里不属于底图静态皮肤的部分
    base_skin = skin_of(base_np)
    dyn = np.zeros_like(base_skin)
    dyn |= rigL['arm']; dyn |= rigR['arm']
    hand_only = skin & ~base_skin & ~dyn
    chest = np.zeros_like(skin)
    chest[CHEST_ZONE[1]:CHEST_ZONE[3], CHEST_ZONE[0]:CHEST_ZONE[2]] = True
    c1_rootless = int((skin & chest & ~cover).sum())
    ys, xs = np.nonzero(hand_only)
    out = {
        'c5_chest_skin': zone_count(skin, C5_ZONE),
        'c1_rootless_in_chest': c1_rootless,
        'hand_bbox': ([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
                      if len(xs) else None),
        'hand_px': int(hand_only.sum()),
    }
    gap, ncomp = hand_gap(skin)
    out['hand_gap'] = round(gap, 1)
    out['hand_comps_in_gap_zone'] = ncomp
    if save:
        os.makedirs(OUT, exist_ok=True)
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA').save(
            os.path.join(OUT, f'{tag}.png'))
    return out


def main():
    base_np = rig.to_np(rig.load_rgba(BASE))
    rigL = rig.build_arm(base_np, 'L')
    rigR = rig.build_arm(base_np, 'R')
    print("== 比心 (cheer_heart) 候选姿势 ==")
    print("  a_s    a_e   | C5胸前肤色 | 两掌间距 | 胸前无根肢体 | 手部包围盒")
    for a_s in (-6, -10, -14):
        for a_e in (82, 88, 94, 100, 106):
            poses = dict(L=(-a_s, a_e, 0), R=(a_s, -a_e, 0))
            r = run(poses, base_np, rigL, rigR,
                    f'heart_a{abs(a_s)}_{a_e}', save=(a_e in (88, 94, 100)))
            print(f"  {a_s:4d} {a_e:5d} | {r['c5_chest_skin']:9d} | {r['hand_gap']:8.1f} | "
                  f"{r['c1_rootless_in_chest']:11d} | {r['hand_bbox']}")
    print()
    print("== 鼓掌 (cheer_clap) 候选姿势 ==")
    print("  a_s    a_e   | C5胸前肤色 | 两掌间距 | 胸前无根肢体 | 手部包围盒")
    for a_s in (20, 26, 32, 38):
        for a_e in (74, 80, 86):
            poses = dict(L=(-a_s, a_e, 0), R=(a_s, -a_e, 0))
            r = run(poses, base_np, rigL, rigR,
                    f'clap_a{a_s}_{a_e}', save=(a_e == 80))
            print(f"  {a_s:4d} {a_e:5d} | {r['c5_chest_skin']:9d} | {r['hand_gap']:8.1f} | "
                  f"{r['c1_rootless_in_chest']:11d} | {r['hand_bbox']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
