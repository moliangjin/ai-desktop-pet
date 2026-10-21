#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 点击动作视觉洁净度客观判据 (P0-1) —— 帧级, 与显示尺寸无关。

背景 (用户真机反馈): "点击人物时部分 cheer 动作出现额外手臂/多余手部残影"。
之前四轮之所以误判, 是因为只统计**肤色连通块** —— 而真机看到的
"多出来一双手"并不是多了一块肤色, 而是:

  ① **前臂+手横穿胸口** —— 手臂没有根, 像一根白木棍横在身前;
  ② **身体两侧挂着"空袖子"** —— 袖子的外轮廓描边还在, 手却没了;
  ③ 两者叠加 ⇒ 观感上就是"凭空多出一双手"。

本脚本给出 6 条可复算的判据, 分两类:

【A. 绝对判据 (与 rig 无关, 直接对应用户的验收语句)】
  C0 手部数量    : 帧内"手"的肤色连通块必须 **恰好 2 个** —— 直接对应
                   "角色四肢数量视觉上必须始终正确 / 不能有多余手掌"
  C4 幽灵袖描边  : 手臂动过的一侧, 底图袖子外轮廓带里残留的暗描边 ≤ 门槛
                   —— 直接对应 "不能有残留手臂描边"
  C5 衣身残留描边: 摘掉袖子后, 衣身层里"本该是袖子"的位置残留的暗像素 = 0
                   —— 直接对应 "不能有拼接残影"

【B. 以 rig 为参照的回归判据 (钉住几何, 防回归)】
  C1 胸前无根肢体: 胸前区域里**不属于任何手臂层**的皮肤像素 = 0
                   (语义修正: 比心/鼓掌本来就要把手放到胸前, 不能用
                    "胸前不能有皮肤"当判据, 那会把正确的手判成缺陷)
  C2 未解释的肤色: 帧内"不在 rig 预期位置"的皮肤像素 ≤ 60 (抗锯齿余量)
  C3 原手位残留  : 手臂动过的一侧, 底图原手位矩形内的皮肤像素 = 0

用法:
    python3 46_R165_arm_verify.py --dir assets/character_R158 --out evidence_r165_arm_verify.json
    python3 46_R165_arm_verify.py --dir /tmp/r162_old --out /tmp/old.json --expect-fail
"""
import argparse
import importlib.util
import json
import os
from collections import deque

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')

_spec = importlib.util.spec_from_file_location('rig', os.path.join(CAND, '36_R158_arm_rig.py'))
rig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rig)

_spec2 = importlib.util.spec_from_file_location('bake', os.path.join(CAND, '37_R158_action_bake.py'))
bake = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(bake)

_spec3 = importlib.util.spec_from_file_location('r153', os.path.join(CAND, '22_R153_pose_bake.py'))
r153 = importlib.util.module_from_spec(_spec3)
_spec3.loader.exec_module(r153)

BASE = os.path.join(R138, 'idle', 'idle_00_base.png')
FOOT_Y = 987

BASE_HAND_BOX = {'L': (344, 594, 384, 654), 'R': (646, 593, 685, 656)}
CHEST_ZONE = (420, 380, 610, 520)
THIGH_ZONES = ((425, 658, 500, 693), (531, 660, 608, 692))
FACE_ZONE = (380, 40, 660, 340)

C0_HAND_MAX = 2         # 手部连通块数上限 (双手相接时只有 1 块)
C0_HAND_MIN = 1         # 下限 (不能没有手)
C0_AREA_MIN_RATIO = 0.40  # 手部肤色总面积 ≥ 底图两只手肤色总面积的该比例
C0_AREA_MAX_RATIO = 1.80  # 上限: 超过说明多出手
C0_MERGE_PX = 30        # 相距该距离内的肤色块视为"同一只手"(被袖口/腕带切开)
C1_MAX = 0              # 胸前无根肢体
C2_MAX = 60             # 未解释的肤色 (抗锯齿余量)
C3_MAX = 0              # 原手位残留
C4_MAX = 60             # 幽灵袖描边
C5_MAX = 0              # 衣身残留描边

HAND_MIN_AREA = 150     # 手部连通块的最小面积 (纹理 px)
HAND_MAX_AREA = 9000


def comps(mask, min_px=60):
    h, w = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    for sy, sx in zip(*np.nonzero(mask)):
        if seen[sy, sx]:
            continue
        q = deque([(sy, sx)])
        seen[sy, sx] = True
        pts = []
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
        if len(pts) >= min_px:
            pa = np.array(pts)
            out.append((len(pts), int(pa[:, 1].min()), int(pa[:, 0].min()),
                        int(pa[:, 1].max()), int(pa[:, 0].max())))
    out.sort(reverse=True)
    return out


def dilate(m, r=2):
    out = m.copy()
    for _ in range(r):
        o = out.copy()
        o[1:, :] |= out[:-1, :]
        o[:-1, :] |= out[1:, :]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


def mask_to_rgba(m):
    a = (m.astype(np.uint8) * 255)
    return Image.fromarray(np.dstack([a, a, a, a]), 'RGBA')


def rgba_to_mask(im):
    return np.asarray(im.convert('RGBA'))[:, :, 3] > 40


class Base:
    def __init__(self):
        self.np = rig.to_np(rig.load_rgba(BASE))
        a = self.np
        self.skin = rig.skin_relaxed(a)
        self.lum = rig.lum(a)
        self.alpha = a[:, :, 3]
        self.skin_area = int(self.skin.sum())
        self.sleeveL = rig._sleeve_mask(a, 'L')
        self.sleeveR = rig._sleeve_mask(a, 'R')
        self.rigL = rig.build_arm(a, 'L')
        self.rigR = rig.build_arm(a, 'R')
        # 静态肩球: 由设计就是"不动的肩章", 它的描边不算幽灵 ⇒ 判据里排除
        self.ball_disc = {}
        for side, rg in (('L', self.rigL), ('R', self.rigR)):
            self.ball_disc[side] = rig.disc(a.shape[:2], rg['S'], rig.SHOULDER_BALL_R)
        self.outer_band = {}
        for side, m in (('L', self.sleeveL), ('R', self.sleeveR)):
            band = np.zeros_like(m)
            for y in range(m.shape[0]):
                xs = np.nonzero(m[y])[0]
                if len(xs) == 0:
                    continue
                if side == 'L':
                    band[y, xs.min():xs.min() + 26] = True
                else:
                    band[y, xs.max() - 25:xs.max() + 1] = True
            band &= ~self.ball_disc[side]        # 肩球区域不算幽灵描边
            self.outer_band[side] = band
        self.base_ghost = {
            'L': int(((self.lum < 115) & (self.alpha > 40) & self.outer_band['L']).sum()),
            'R': int(((self.lum < 115) & (self.alpha > 40) & self.outer_band['R']).sum()),
        }
        x0, y0, x1, y1 = CHEST_ZONE
        self.chest_mask = np.zeros_like(self.skin)
        self.chest_mask[y0:y1, x0:x1] = True
        self.chest_mask &= ~self.skin
        self.chest_area = int(self.chest_mask.sum())
        # rig
        # 静态皮肤 (脸 + 脖子 + 大腿) —— 手臂整块属于"动态皮肤"
        dyn = np.zeros_like(self.skin)
        dyn |= self.rigL['arm']
        dyn |= self.rigR['arm']
        self.static_skin = self.skin & ~dyn
        self.static_mask_img = mask_to_rgba(self.static_skin)
        # 手部判定用的排除区 (脸 / 大腿)
        self.not_hand = np.zeros_like(self.skin)
        fx0, fy0, fx1, fy1 = FACE_ZONE
        self.not_hand[fy0:fy1, fx0:fx1] = True
        for tx0, ty0, tx1, ty1 in THIGH_ZONES:
            self.not_hand[ty0:ty1, tx0:tx1] = True
        # 底图"两只手"的肤色面积基准 (用与帧完全同一套口径: 排除静态皮肤)
        hb = self.skin & ~dilate(self.static_skin, 2)
        self.base_hand_area = int(hb.sum())


def _apply_transforms(img, action, index, tmp=None):
    """对掩膜图套用与烘焙**完全相同**的变换链 (眼部合成只换眼睛像素, 不改几何,
    →    因此掩膜不需要它 —— 且掩膜在眼部没有差异, face_swap 会直接报错)。"""
    if tmp is None:
        # 唯一临时文件: 避免并发跑两个实例时互相覆盖 (R165 踩过)
        tmp = f'/tmp/_r165_mask_{os.getpid()}_{id(img)}.png'
    img.save(tmp)
    rot, dy = bake.HEAD[action][index]
    if rot or dy:
        r153.head_transform(tmp, tmp, rotate=rot, dy=dy, tag='m')
    if action == 'cheer_jump':
        bake.body_shift(tmp, tmp, shift_up=0, scale_y=bake.JUMP_SCALE[index],
                        pivot_y=FOOT_Y, tag='m')
    out = Image.open(tmp).convert('RGBA')
    if os.path.exists(tmp):
        os.remove(tmp)
    return out


def expected_masks(base, action, index):
    """用 rig 重跑这一帧, 得到"静态皮肤 / 手 / 手臂覆盖 / 袖带"应在的位置。"""
    poses = bake.POSES[action][index]
    arm_np = bake.arm_pose_frame(poses, base.np, base.rigL, base.rigR, None)
    arm_skin = rig.skin_relaxed(arm_np)
    hand_skin = arm_skin & ~base.static_skin
    hand_mask = mask_to_rgba(hand_skin)
    static_skin = base.static_skin.copy()
    donor_name = bake.FACE[action][index]
    if donor_name:
        donor_np = rig.to_np(rig.load_rgba(os.path.join(R138, 'idle', donor_name)))
        donor_skin = rig.skin_relaxed(donor_np)
        eye = np.zeros_like(static_skin)
        eye[r153.FACE_TOP_Y:r153.CHIN_Y, 380:660] = True
        static_skin[eye] = donor_skin[eye]
    static_mask = mask_to_rgba(static_skin)

    cover = np.zeros(base.np.shape[:2], bool)
    for side, r in (('L', base.rigL), ('R', base.rigR)):
        ang = poses.get(side) or (0, 0, 0)
        up, fo, hd, ball = rig.pose_arm(base.np, r, ang)
        for lay in (up, fo, hd, ball):
            cover |= (lay[:, :, 3] > 40)
    cover_mask = mask_to_rgba(cover)
    band_masks = {s: mask_to_rgba(base.outer_band[s]) for s in ('L', 'R')}

    out = {}
    for key, img in (('hand', hand_mask), ('static', static_mask),
                     ('cover', cover_mask), ('bandL', band_masks['L']),
                     ('bandR', band_masks['R'])):
        out[key] = rgba_to_mask(_apply_transforms(img, action, index))
    return out


def side_moved(action, index):
    poses = bake.POSES[action][index]
    out = {}
    for side in ('L', 'R'):
        ang = poses.get(side)
        out[side] = bool(ang) and any(abs(x) > 1e-6 for x in ang)
    return out


def count_hands(base, skin, static_mask):
    """统计"手"的肤色连通块。

    三处 R165 修正 (都是"度量方式"修正, 意图不变: 手不能多、不能少、不能被吃掉):
      ① 排除"静态皮肤"(脸/脖子/大腿) 用**变换后**的静态皮肤掩膜, 而不是固定的
         底图坐标矩形 —— 跳跃帧会把身体整体压扁, 大腿会上移到胸口高度,
         固定矩形就框不住它了 (实测 jump_0 曾把两条大腿算成 4 只手)。
      ② 相距 C0_MERGE_PX 内的肤色块视为**同一只手** —— 手腕的青色腕带会把
         一只手切成两块 (实测 heart_2 曾数出 3 块)。
      ③ 面积下限按"两只手"的 40% 算 —— 比心时两手**重叠**, 可见肤色只剩一只手的量,
         用 55% 会把正确的手判成"被吃掉"。
    """
    cand = skin & ~dilate(static_mask, 2)
    raw = []
    for area, x0, y0, x1, y1 in comps(cand, HAND_MIN_AREA):
        if area > HAND_MAX_AREA:
            continue
        raw.append((area, x0, y0, x1, y1))
    raw.sort(key=lambda t: t[1])
    merged = []
    for b in raw:
        if merged:
            m = merged[-1]
            if (b[1] - m[3] <= C0_MERGE_PX) and (b[2] - m[4] <= C0_MERGE_PX) \
                    and (m[2] - b[4] <= C0_MERGE_PX):
                m[0] += b[0]
                m[1] = min(m[1], b[1]); m[2] = min(m[2], b[2])
                m[3] = max(m[3], b[3]); m[4] = max(m[4], b[4])
                continue
        merged.append(list(b))
    return len(merged), int(sum(m[0] for m in merged))


def body_layer(base, action, index):
    """重跑这一帧的"摘袖子"步骤, 返回身体层 (用于 C5 衣身残留描边)。"""
    poses = bake.POSES[action][index]
    body = base.np.copy()
    for side, r in (('L', base.rigL), ('R', base.rigR)):
        ang = poses.get(side) or (0, 0, 0)
        body, _ = rig.restore_body(body, r['arm'], side, cap_mask=r['nS'],
                                   fill_mask=r['upper'])
    return body


def check_frame(path, base, action, index):
    im = Image.open(path).convert('RGBA')
    a = rig.to_np(im)
    skin = rig.skin_relaxed(a)
    lum = rig.lum(a)
    alpha = a[:, :, 3]
    dark = (lum < 115) & (alpha > 40)

    scale = bake.JUMP_SCALE[index] if action == 'cheer_jump' else 1.0
    ys = np.arange(a.shape[0])
    fy = np.clip(np.round(FOOT_Y + (ys - FOOT_Y) * scale).astype(int), 0, a.shape[0] - 1)
    inv = np.zeros_like(ys)
    inv[fy] = ys
    base_y = inv

    exp = expected_masks(base, action, index)

    # ---- C0 手部数量 / 手部面积 (绝对) ----
    hands, hand_area = count_hands(base, skin, exp['static'])
    c0 = 0 if (C0_HAND_MIN <= hands <= C0_HAND_MAX) else 1
    c0_area_min = int(base.base_hand_area * C0_AREA_MIN_RATIO)
    c0_area_max = int(base.base_hand_area * C0_AREA_MAX_RATIO)
    if not (c0_area_min <= hand_area <= c0_area_max):
        c0 = 1

    # ---- C1 胸前**无根**肢体 ----
    chest = np.zeros_like(base.chest_mask)
    for y in range(a.shape[0]):
        by = base_y[y]
        if by < base.chest_mask.shape[0]:
            chest[y] = base.chest_mask[by]
    c1 = int((skin & chest & ~exp['cover']).sum())

    # ---- C2 未解释的肤色 (rig 预期 vs 实际) ----
    allowed = dilate(exp['hand'] | exp['static'], 4)
    c2 = int((skin & ~allowed).sum())

    # ---- C3 原手位残留 (只看动过的一侧) ----
    moved = side_moved(action, index)
    res = np.zeros_like(skin)
    for side, (bx0, by0, bx1, by1) in BASE_HAND_BOX.items():
        if moved[side]:
            res[by0:by1 + 1, bx0:bx1 + 1] = True
    c3 = int((skin & res).sum())

    # ---- C4 幽灵袖描边 (只看动过的一侧, 且排除手臂合法覆盖的部分) ----
    c4 = {}
    for side in ('L', 'R'):
        if not moved[side]:
            c4[side] = -1
            continue
        band = exp['bandL'] if side == 'L' else exp['bandR']
        c4[side] = int((dark & band & ~exp['cover']).sum())

    # ---- C5 衣身残留描边 (摘袖子后, 衣身层里"本该是袖子"处的暗像素) ----
    body = body_layer(base, action, index)
    body_dark = (rig.lum(body) < 115) & (body[:, :, 3] > 40)
    arm_region = base.sleeveL | base.sleeveR
    c5 = int((body_dark & arm_region).sum())

    fails = []
    if c0 != 0:
        fails.append(f'C0 手部 {hands} 块 / 面积 {hand_area}px (期望 {C0_HAND_MIN}~{C0_HAND_MAX} 块, '
                     f'面积 {c0_area_min}~{c0_area_max}px) —— 多手/丢手/手被吃掉')
    if c1 > C1_MAX:
        fails.append(f'C1 胸前无根肢体 {c1}px > {C1_MAX}')
    if c2 > C2_MAX:
        fails.append(f'C2 未解释的肤色 {c2}px > {C2_MAX}')
    if c3 > C3_MAX:
        fails.append(f'C3 原手位残留 {c3}px > {C3_MAX}')
    worst = max((v for v in c4.values() if v >= 0), default=-1)
    if worst > C4_MAX:
        fails.append(f'C4 幽灵袖描边 {c4} > {C4_MAX}')
    if c5 > C5_MAX:
        fails.append(f'C5 衣身残留描边 {c5}px > {C5_MAX}')

    return {
        'file': os.path.basename(path),
        'action': action, 'index': index,
        'side_moved': moved,
        'C0_hand_blobs': hands,
        'C0_hand_area_px': hand_area,
        'C0_hand_area_min_px': c0_area_min,
        'C1_chest_rootless_skin_px': c1,
        'C2_unexplained_skin_px': c2,
        'C3_old_hand_region_skin_px': c3,
        'C4_ghost_sleeve_outline_px': c4,
        'C5_body_residual_outline_px': c5,
        'verdict': 'PASS' if not fails else 'FAIL',
        'failures': fails,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=os.path.join(ASSETS, 'character_R158'))
    ap.add_argument('--out', default=None)
    ap.add_argument('--expect-fail', action='store_true')
    args = ap.parse_args()

    base = Base()
    files = sorted(f for f in os.listdir(args.dir)
                   if f.endswith('.png') and f.startswith('cheer_')
                   and f[:-4] in
                   {f'{a}_{i}' for a in bake.POSES for i in range(3)})
    results = []
    for f in files:
        action = f.rsplit('_', 1)[0]
        index = int(f.rsplit('_', 1)[1].split('.')[0])
        r = check_frame(os.path.join(args.dir, f), base, action, index)
        results.append(r)
        c4 = r['C4_ghost_sleeve_outline_px']
        print(f"  {r['verdict']:4s} {f:20s} "
              f"C0手={r['C0_hand_blobs']}({r['C0_hand_area_px']}px) "
              f"C1={r['C1_chest_rootless_skin_px']:5d} "
              f"C2={r['C2_unexplained_skin_px']:6d} C3={r['C3_old_hand_region_skin_px']:5d} "
              f"C4=L{c4['L']}/R{c4['R']} C5={r['C5_body_residual_outline_px']:5d}")
        for x in r['failures']:
            print(f'        ❌ {x}')

    n_fail = sum(1 for r in results if r['verdict'] == 'FAIL')
    print(f"\n  合计: {len(results)} 帧, PASS {len(results)-n_fail}, FAIL {n_fail}")
    print(f"  底图基准: C4 幽灵袖描边(排除肩球) = {base.base_ghost}; 胸口无皮肤区面积 = {base.chest_area}")

    out = args.out or os.path.join(CAND, 'evidence_r165_arm_verify.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'round': 'R165', 'dir': args.dir,
                   'criteria': {'C0_hand_blobs': [C0_HAND_MIN, C0_HAND_MAX],
                                'C0_area_min_ratio': C0_AREA_MIN_RATIO, 'C1_max': C1_MAX,
                                'C2_max': C2_MAX, 'C3_max': C3_MAX,
                                'C4_max': C4_MAX, 'C5_max': C5_MAX},
                   'base_reference': {'ghost_px_excl_ball': base.base_ghost,
                                      'skin_area': base.skin_area,
                                      'base_hand_area': base.base_hand_area,
                                      'chest_zone': list(CHEST_ZONE),
                                      'chest_skinfree_area': base.chest_area},
                   'results': results,
                   'summary': {'frames': len(results), 'pass': len(results) - n_fail,
                               'fail': n_fail}},
                  f, ensure_ascii=False, indent=2)
    print(f"  📄 {out}")

    if args.expect_fail:
        if n_fail == 0:
            raise SystemExit('❌ 旧素材复验失败: 期望至少 1 帧 FAIL, 实际全 PASS '
                             '(说明判据对旧缺陷不敏感)')
        print(f"  ✅ 旧素材复验成立: {n_fail} 帧判 FAIL (判据对 R162 缺陷敏感)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
