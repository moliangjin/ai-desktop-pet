#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R162 手臂骨架缺陷验证 — 在**重建后的衣身**上做客观判定。

R158 独立审查提出的"袖子、手臂拼接残影", 在成品帧上有几处互相叠加的表现:
  ① 大褂外缘的描边变成**虚线** (重建时描边颜色取自描边外侧的透明区,
     取到随机颜色 ⇒ 有的行是纯黑、有的行是纯白 ⇒ 整条边断断续续)
  ② 手臂掩膜从肩膀上方**绕进大褂胸口** ⇒ 手臂一转, 这块衣身跟着飞起来,
     肩上凭空多出一块**白色残块**
  ③ 袖子外侧那条**青色高光带**留在掩膜之外 ⇒ 手臂转走后原地留下一条**青色虚线**

这三条都可以在"重建后的衣身"(restore_body 的输出)上直接客观测量 ——
比在成品帧上量更干净 (成品帧里抬起的手臂会盖住剪影, 干扰判定)。

输出: evidence_r162_rig_verify.json
"""
import importlib.util
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
BASE = os.path.join(CAND, 'assets', 'character_R138', 'idle', 'idle_00_base.png')
OUT_JSON = os.path.join(CAND, 'evidence_r162_rig_verify.json')

_spec = importlib.util.spec_from_file_location('r162_rig', os.path.join(CAND, '36_R158_arm_rig.py'))
rig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rig)

# 门槛 (取值依据见每条注释)
MAX_EDGE_GAP = 38       # 衣身外缘描边允许的最长断开行数
MAX_LEAK_ROWS = 0       # 手臂掩膜越过接缝线的行数 (一格都不允许)
MAX_TEAL_DASH = 30      # 衣身外缘外侧允许残留的青色像素数


def lum(a):
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def edge_continuity(body, side, x0, x1, y0=350, y1=586):
    """衣身外缘描边的连续性: 逐行看最外侧实心像素外侧有没有暗线核心。"""
    al = body[:, :, 3]
    L = lum(body)
    flags = []
    for y in range(y0, y1):
        xs = np.nonzero(al[y, x0:x1] > 40)[0]
        if len(xs) == 0:
            flags.append(0)
            continue
        if side == 'L':
            edge = int(xs.min()) + x0
            frm = edge
        else:
            edge = int(xs.max()) + x0
            frm = edge - 6
        w = L[y, max(0, frm):max(0, frm) + 7]
        flags.append(1 if (w < 130).sum() >= 2 else 0)
    best = cur = 0
    gapb = gapc = 0
    for f in flags:
        if f:
            cur += 1
            gapc = 0
            best = max(best, cur)
        else:
            gapc += 1
            gapb = max(gapb, gapc)
            cur = 0
    return dict(longest_run=best, longest_gap=gapb, rows=len(flags))


def seam_leak_rows(arm, side, y0=330, y1=590):
    """手臂掩膜越过接缝线的行数 (肩部大褂胸口被卷进来的证据)。"""
    bad = []
    for y in range(y0, y1):
        xs = np.nonzero(arm[y])[0]
        if len(xs) == 0:
            continue
        if side == 'L':
            hi = int(xs.max())
            limit = int(round(rig.seam_x('L', y))) + rig.SEAM_LINE_PX
            if hi > limit:
                bad.append((y, hi, limit))
        else:
            lo = int(xs.min())
            limit = 1024 - int(round(rig.seam_x('L', y))) - rig.SEAM_LINE_PX
            if lo < limit:
                bad.append((y, lo, limit))
    return bad


def teal_dash(body, side, y0=350, y1=590):
    """衣身外缘外侧带里的青色像素 (旧实现残留的"青色虚线")。"""
    R, G, B, Al = body[:, :, 0], body[:, :, 1], body[:, :, 2], body[:, :, 3]
    teal = (Al > 60) & (B > R + 25) & (G > R + 25) & (G > 150) & (B > 170)
    n = 0
    for y in range(y0, y1):
        xs = np.nonzero(body[y, :, 3] > 40)[0]
        if len(xs) == 0:
            continue
        if side == 'L':
            edge = int(xs.min())
            band = slice(max(0, edge - 8), edge)
        else:
            edge = int(xs.max())
            band = slice(edge + 1, min(body.shape[1], edge + 9))
        n += int(teal[y, band].sum())
    return n


def main():
    base = np.asarray(Image.open(BASE).convert('RGBA')).astype(np.int32)
    report = {'round': 'R162', 'technique': 'arm_rig 重建后衣身的客观测量',
              'thresholds': {'max_edge_gap': MAX_EDGE_GAP,
                             'max_leak_rows': MAX_LEAK_ROWS,
                             'max_teal_dash': MAX_TEAL_DASH},
              'sides': {}, 'pass': True}
    failures = []
    for side in ('L', 'R'):
        r = rig.build_arm(base, side)
        body, _fill = rig.restore_body(base.copy(), r['arm'], side)
        if side == 'L':
            L = edge_continuity(body, 'L', 300, 470)
            R = edge_continuity(body, 'R', 554, 724)
            leak = seam_leak_rows(r['arm'], 'L')
            teal_l = teal_dash(body, 'L')
            teal_r = teal_dash(body, 'R')
        else:
            # R 侧在镜像空间里量, 结论等价
            body_m = body[:, ::-1]
            L = edge_continuity(body_m, 'L', 300, 470)
            R = edge_continuity(body_m, 'R', 554, 724)
            leak = seam_leak_rows(r['arm'], 'R')
            teal_l = teal_dash(body_m, 'L')
            teal_r = teal_dash(body_m, 'R')
        report['sides'][side] = {
            'arm_px': int(r['arm'].sum()),
            'chunk_px': {'upper': int(r['upper'].sum()), 'fore': int(r['fore'].sum()),
                         'hand': int(r['hand'].sum())},
            'edge_left': L, 'edge_right': R,
            'seam_leak_rows': len(leak),
            'seam_leak_samples': leak[:5],
            'teal_dash_px': {'left': teal_l, 'right': teal_r},
        }
        for nm, e in (('左', L), ('右', R)):
            if e['longest_gap'] > MAX_EDGE_GAP:
                failures.append(f'{side} 侧{nm}衣身外缘描边最长断开 {e["longest_gap"]} 行 '
                                f'(门槛 {MAX_EDGE_GAP}) → 衣身边缘是虚线')
        if len(leak) > MAX_LEAK_ROWS:
            failures.append(f'{side} 侧有 {len(leak)} 行手臂掩膜越过接缝线 '
                            f'(门槛 {MAX_LEAK_ROWS}) → 大褂胸口被卷进手臂, 会变成白色残块')
        if max(teal_l, teal_r) > MAX_TEAL_DASH:
            failures.append(f'{side} 侧衣身外缘外侧残留青色 {max(teal_l, teal_r)} 像素 '
                            f'(门槛 {MAX_TEAL_DASH}) → 袖子高光带残留成青色虚线')

    report['failures'] = failures
    report['pass'] = not failures
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print('R162 手臂骨架缺陷验证 (重建后衣身的客观测量):')
    for side, d in report['sides'].items():
        print(f"  {side} 侧: 手臂掩膜 {d['arm_px']} px "
              f"(上臂 {d['chunk_px']['upper']} / 前臂 {d['chunk_px']['fore']} / 手 {d['chunk_px']['hand']})")
        print(f"        衣身外缘描边: 左 连续 {d['edge_left']['longest_run']} 行 / 断 {d['edge_left']['longest_gap']} 行"
              f"   右 连续 {d['edge_right']['longest_run']} 行 / 断 {d['edge_right']['longest_gap']} 行")
        print(f"        越过接缝线的行数: {d['seam_leak_rows']}   外侧青色残留: "
              f"左 {d['teal_dash_px']['left']} / 右 {d['teal_dash_px']['right']}")
    if failures:
        print('  ❌ 不通过:')
        for f_ in failures:
            print('   - ' + f_)
    else:
        print('  ✅ 全部通过')
    print(f'  📄 {OUT_JSON}')
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
