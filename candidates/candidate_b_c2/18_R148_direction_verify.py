#!/usr/bin/env python3
"""R148: 行走方向的**客观**测量与验收。

核心原则 (R148 任务书): "禁止仅通过 x 坐标正负、动画名称或测试脚本 PASS, 认定视觉方向正确。"
所以本脚本**不看坐标符号, 不看文件名**, 而是用**鞋尖几何**判定:

    对每帧:
      1. 用颜色把"靴子"像素与"袜子(浅蓝)/皮肤"分开, 取角色最底部 16% 高度带 (纯靴子区)
      2. 按 x 分成左/右两只靴
      3. 落地靴 = 靴底 y 最大 (贴地) 的那只; 两只靴底同高 → 该帧是"并立站姿", 无步向
      4. 鞋尖朝向 = 靴体重心 x 相对"靴筒口 x"(靴子最高一行的像素中心) 的偏移方向
         (靴体是从靴筒口朝鞋头延伸的, 重心落在鞋头一侧)
             -1 = 鞋尖朝左,  +1 = 鞋尖朝右
      5. 期望: 向左走 → 落地靴在左且鞋尖朝左; 向右走 → 落地靴在右且鞋尖朝右

同时校验 (结构性证明, 与脚本 PASS 无关):
      · 派生帧在徽章区**之外**与源帧的水平镜像**逐像素完全一致**
        → 证明是"整体水平镜像", 绝非"只翻转双腿"
      · 徽章在派生帧里**没有被镜像** (与源徽章的相关性 >> 与翻转徽章的相关性)
      · 徽章仍在角色**自己的左胸** (观者右侧), 两个方向一致
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
R138 = os.path.join(ASSETS, 'character_R138')
DERIVED = os.path.join(ASSETS, 'character_R138_derived', 'walk_right_mirror')
DERIVE_REPORT = os.path.join(DERIVED, 'derive_report.json')


def load_rgba(path):
    return np.asarray(Image.open(path).convert('RGBA')).astype(int)


def boot_metric(a):
    """测量一帧的落脚脚与鞋尖朝向。"""
    fg = a[:, :, 3] > 60
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    ys, xs = np.nonzero(fg)
    if len(xs) == 0:
        return None
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    H = y1 - y0
    band_top = y0 + int(H * 0.84)          # 最底部 16% → 纯靴子区
    sock = (B - R > 30) & (B > 175) & fg    # 浅蓝长袜
    boot = fg & ~sock
    boot[:band_top] = False
    cx = (x0 + x1) // 2
    halves = {}
    for side in ('L', 'R'):
        m = boot.copy()
        if side == 'L':
            m[:, cx:] = False
        else:
            m[:, :cx] = False
        sy, sx = np.nonzero(m)
        halves[side] = None if len(sx) == 0 else {
            'bottom': int(sy.max()), 'top': int(sy.min()),
            'x0': int(sx.min()), 'x1': int(sx.max()), 'mass': float(sx.mean()),
        }
    L, Rr = halves['L'], halves['R']
    if L is None or Rr is None:
        return None
    if L['bottom'] == Rr['bottom']:
        return {                          # 两只靴子同时贴地 → 并立站姿, 无步向
            'stance': 'STAND',
            'Lbottom': L['bottom'], 'Rbottom': Rr['bottom'],
            'planted': None, 'toe_dir': 0,
        }
    planted = 'L' if L['bottom'] > Rr['bottom'] else 'R'
    b = halves[planted]
    m = boot.copy()
    if planted == 'L':
        m[:, cx:] = False
    else:
        m[:, :cx] = False
    sy, sx = np.nonzero(m)
    top_row = sx[sy == b['top']]
    ankle_x = float(top_row.mean())
    mass_x = b['mass']
    toe_dir = -1 if mass_x < ankle_x else (1 if mass_x > ankle_x else 0)
    return {
        'stance': 'STEP',
        'planted': planted,
        'Lbottom': L['bottom'], 'Rbottom': Rr['bottom'],
        'lift_px': int(min(L['bottom'], Rr['bottom']) - max(L['bottom'], Rr['bottom'])) * -1,
        'ankle_x': round(ankle_x, 1),
        'mass_x': round(mass_x, 1),
        'toe_offset_px': round(mass_x - ankle_x, 1),
        'toe_dir': toe_dir,
    }


def ncc(a, b):
    a = a.astype(float).ravel()
    b = b.astype(float).ravel()
    a = a - a.mean()
    b = b - b.mean()
    na, nb = np.sqrt((a ** 2).sum()), np.sqrt((b ** 2).sum())
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float((a * b).sum() / (na * nb))


def check_mirror_exact(src, der, box_a, box_b):
    """徽章区之外, 派生帧必须与源帧的水平镜像逐像素完全一致。"""
    flip = src[:, ::-1]
    diff = np.abs(der - flip)
    mask = np.ones(diff.shape[:2], dtype=bool)
    for (x0, y0, x1, y1) in (box_a, box_b):
        mask[max(0, y0 - 2):min(mask.shape[0], y1 + 2),
             max(0, x0 - 2):min(mask.shape[1], x1 + 2)] = False
    outside = diff[mask]
    return {
        'outside_emblem_max_abs_diff': int(outside.max()),
        'outside_emblem_differing_pixels': int((outside > 0).sum()),
        'outside_emblem_pixels': int(outside.size),
    }


def check_emblem(src, der, box):
    """徽章必须**未镜像**, 且仍在角色自己的左胸 (观者右侧)。"""
    x0, y0, x1, y1 = box
    src_patch = src[y0:y1, x0:x1, :3]
    der_patch = der[y0:y1, x0:x1, :3]
    unflipped = ncc(src_patch, der_patch)
    flipped = ncc(src_patch[:, ::-1], der_patch)
    ys, xs = np.nonzero(der[:, :, 3] > 60)
    body_cx = (xs.min() + xs.max()) / 2.0
    return {
        'emblem_ncc_unflipped': round(unflipped, 4),
        'emblem_ncc_flipped': round(flipped, 4),
        'emblem_not_mirrored': bool(unflipped > flipped),
        'emblem_side_rel_body_px': round((x0 + x1) / 2.0 - body_cx, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(CAND, 'evidence_r148_direction.json'))
    a = ap.parse_args()

    drep = json.load(open(DERIVE_REPORT, encoding='utf-8'))
    boxes = [tuple(f['emblem_box']) for f in drep['frames']]

    groups = {
        'walk_left': ([os.path.join(R138, 'walk_left', f) for f in
                       ('walk_left_00_stand.png', 'walk_left_01_left_step.png',
                        'walk_left_02_pass.png', 'walk_left_03_right_step.png')], -1),
        'walk_right_OLD': ([os.path.join(R138, 'walk_right', f) for f in
                            ('walk_right_00_stand.png', 'walk_right_01_right_step.png',
                             'walk_right_02_pass.png', 'walk_right_03_left_step.png')], +1),
        'walk_right_R148': ([os.path.join(DERIVED, f) for f in
                             ('walk_right_m_00.png', 'walk_right_m_01.png',
                              'walk_right_m_02.png', 'walk_right_m_03.png')], +1),
    }

    report = {'round': 'R148',
              'metric': 'boots/ankle-offset (鞋尖几何), 不使用坐标符号/文件名/动画名',
              'groups': {}}
    print("R148 方向客观测量 (鞋尖几何):")
    for g, (files, expect) in groups.items():
        rows = []
        for i, f in enumerate(files):
            m = boot_metric(load_rgba(f))
            m['file'] = os.path.basename(f)
            m['index'] = i
            rows.append(m)
        steps = [r for r in rows if r['stance'] == 'STEP']
        tds = [r['toe_dir'] for r in steps]
        plants = [r['planted'] for r in steps]
        want_side = 'L' if expect < 0 else 'R'
        toe_ok = bool(tds) and all(t == expect for t in tds)
        side_ok = bool(plants) and all(p == want_side for p in plants)
        report['groups'][g] = {
            'frames': rows, 'expected_toe_dir': expect,
            'step_toe_dirs': tds, 'step_planted_sides': plants,
            'toe_dir_all_match': toe_ok, 'planted_side_all_match': side_ok,
            'verdict': 'PASS' if (toe_ok and side_ok) else 'FAIL',
        }
        print(f"  {g:16s} 步态帧={len(steps)} 鞋尖方向={tds} 落脚侧={plants} "
              f"→ {report['groups'][g]['verdict']}")

    # ---- 镜像严格性 + 徽章 ----
    checks = []
    print("  逐帧结构校验:")
    for i, (sf, df) in enumerate(zip(groups['walk_left'][0], groups['walk_right_R148'][0])):
        src = load_rgba(sf)
        der = load_rgba(df)
        b = boxes[i]
        W = src.shape[1]
        mb = (W - b[2], b[1], W - b[0], b[3])
        mc = check_mirror_exact(src, der, b, mb)
        eo = check_emblem(src, der, b)
        checks.append({'index': i, **mc, **eo})
        print(f"    frame{i}: 徽章区外 vs 镜像 逐像素差={mc['outside_emblem_max_abs_diff']} "
              f"(差异 {mc['outside_emblem_differing_pixels']}/{mc['outside_emblem_pixels']}) | "
              f"徽章未镜像={eo['emblem_not_mirrored']} "
              f"(ncc 正/翻 {eo['emblem_ncc_unflipped']}/{eo['emblem_ncc_flipped']}) | "
              f"徽章相对身体中心 {eo['emblem_side_rel_body_px']}px (观者右侧=角色左胸)")
    report['mirror_checks'] = checks
    report['mirror_exact_outside_emblem'] = bool(all(
        c['outside_emblem_max_abs_diff'] == 0 for c in checks))
    report['emblem_not_mirrored_all'] = bool(all(c['emblem_not_mirrored'] for c in checks))
    report['emblem_on_character_left_chest'] = bool(all(
        c['emblem_side_rel_body_px'] > 0 for c in checks))

    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  📄 {a.out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
