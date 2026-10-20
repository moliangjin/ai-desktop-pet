#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R158 运行时客观校验 —— 全部基于**真实 Electron 运行采集到的像素**。

R156 的 34_R156_runtime_verify.py 覆盖的是"点击池随机性 / 道具可见 / 道具退场 / 不遮脸 /
身份不漂移 / 点击反馈区别于待机"。R158 在此之上新增 5 类**只有真实运行时才能验**的判据:

  9.  爱心特效在比心动作里**真的可见** (不是只登记在 manifest)
  10. 爱心特效**不串场** (挥手/欢呼等其它动作的采集帧里看不到它)
  11. 跳跃的腾空帧**真的离地** —— 用采集帧里角色最低可见像素行实测, 不看 manifest 声明
  12. 手臂**真的抬起来了** —— 用采集帧里"头侧上方区域"的可见像素实测 (抬手前该区域必为空)
  13. 6 个点击动作在真实运行里**两两画面不同** —— 防止接入后多个动作指向同一组帧

判据不依赖动作名或 manifest 声明, 全部来自真实像素。
"""
import argparse
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('r156v', os.path.join(HERE, '34_R156_runtime_verify.py'))
_v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_v)

check = _v.check
results = _v.results
scene_frames = _v.scene_frames
load_captured = _v.load_captured
load_rgba = _v.load_rgba
diff_ratio = _v.diff_ratio
compute_layout = _v.compute_layout
dilate = _v.dilate

CANVAS_W = _v.CANVAS_W
CANVAS_H = _v.CANVAS_H
GROUND_Y = _v.GROUND_Y
ANCHOR_TEX_Y = _v.ANCHOR_TEX_Y

R158_CLICK_SCENES = ['cheer_wave', 'cheer_hands_up', 'cheer_heart', 'cheer_clap',
                     'cheer_jump', 'cheer_tilt']


def visible_rows(cap):
    """采集帧里可见像素的最小/最大行。"""
    ys = np.nonzero(cap[:, :, 3] > 24)[0]
    if len(ys) == 0:
        return None
    return int(ys.min()), int(ys.max())


def region_visible_count(cap, x0, y0, x1, y1):
    vis = cap[:, :, 3] > 24
    return int(vis[y0:y1, x0:x1].sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview-dir', default='evidence_r158_preview')
    a = ap.parse_args()

    m = json.load(open(_v.MANIFEST, encoding='utf-8'))
    meta = json.load(open(os.path.join(a.preview_dir, 'preview_meta.json'), encoding='utf-8'))
    layout = compute_layout(m)
    props = m.get('props') or {}
    lib = props.get('library') or {}
    scenes = props.get('scenes') or {}
    lib_actions = (m.get('action_library') or {}).get('actions') or {}

    print("R158 运行时客观校验 (全部基于真实采集像素):")
    print(f"  布局: scale={layout['scale']:.6f} groundY={layout['groundY']}")

    # ---------- 9. 爱心特效在比心动作里真的可见 ----------
    #   判据口径: 爱心是 **front 层特效, 直接叠在角色身上**, 所以不能用
    #   "道具掩膜 - 角色掩膜" 的办法 (那会把叠在角色身上的特效一起减掉)。
    #   改用**颜色判据**: 爱心的粉红 (255,92,122) 与角色配色 (银白/冰蓝/白大褂/深蓝衬衫/青边/肤���)
    #   没有任何重叠 —— 粉红像素数必须随动作推进明显增长。
    def heart_pink_count(cap):
        rgb = cap[:, :, :3].astype(int)
        al = cap[:, :, 3]
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        # 爱心主色 (255,92,122): R-G=163; 皮肤高光 (254,230,213): R-G=24 ⇒ 阈值取 80 可完全区分
        pink = (al > 24) & (r > 190) & ((r - g) > 80) & ((r - b) > 80)
        # 只取爱心所在的屏幕区域 (脸在更上方, 不会被算进来)
        reg = np.zeros_like(pink)
        reg[106:150, 74:120] = True
        return int((pink & reg).sum())

    heart_scene = scenes.get('cheer_heart')
    if not heart_scene:
        check('9. 爱心特效在比心动作里真实可见', False, 'manifest 没有 cheer_heart 的道具场景')
    else:
        files = scene_frames(meta, 'click_cheer_heart')
        if not files:
            check('9. 爱心特效在比心动作里真实可见', False, '无比心动作的采集帧')
        else:
            counts = [heart_pink_count(load_captured(f)) for f in files]
            mx = max(counts) if counts else 0
            check('9. 爱心特效在比心动作里真实可见', mx > 60,
                  f'爱心区域粉红像素 {counts} → max={mx} (阈值 60)')

    # ---------- 10. 爱心特效不串场 ----------
    leak = []
    for act in R158_CLICK_SCENES:
        if act == 'cheer_heart':
            continue
        files = scene_frames(meta, f'click_{act}')
        if not files:
            continue
        for f in files:
            n = heart_pink_count(load_captured(f))
            if n > 20:
                leak.append((act, os.path.basename(f), n))
    check('10. 爱心特效不串到其它动作', len(leak) == 0,
          f'串场 {len(leak)} 处' + (f': {leak[:3]}' if leak else ''))

    # ---------- 11. 跳跃腾空帧真的离地 (实测采集帧最低可见行) ----------
    files = scene_frames(meta, 'click_cheer_jump')
    if not files:
        check('11. 跳跃腾空帧真的离地 (实测)', False, '无跳跃动作的采集帧')
    else:
        bottoms = []
        for f in files:
            vr = visible_rows(load_captured(f))
            if vr:
                bottoms.append(vr[1])
        ground = GROUND_Y
        lifted = [b for b in bottoms if b <= ground - 2]
        check('11. 跳跃腾空帧真的离地 (实测采集帧最低可见行)',
              len(lifted) >= 1 and max(bottoms) >= ground - 3,
              f'最低可见行 = {min(bottoms) if bottoms else None}~{max(bottoms) if bottoms else None} '
              f'(地面线 {ground}); 离地帧数 = {len(lifted)}')

    # ---------- 12. 手臂真的抬起来了 (屏幕空间实测) ----------
    # 抬手后手会出现在"头右侧上方"的屏幕区域; 抬手前该区域必然空。
    def raised_region_count(act, tex_x0, tex_y0, tex_x1, tex_y1):
        spec = lib_actions[act]
        x0 = int(round(layout['x'] + layout['scale'] * (tex_x0 - 512)))
        x1 = int(round(layout['x'] + layout['scale'] * (tex_x1 - 512)))
        y0 = int(round(GROUND_Y + layout['scale'] * (tex_y0 - 987)))
        y1 = int(round(GROUND_Y + layout['scale'] * (tex_y1 - 987)))
        if x1 <= x0 or y1 <= y0:
            return 0
        fs = scene_frames(meta, f'click_{act}')
        best = 0
        for f in fs:
            cap = load_captured(f)
            best = max(best, region_visible_count(cap, x0, y0, x1, y1))
        return best

    wave_n = raised_region_count('cheer_wave', 706, 180, 800, 300)
    check('12. cheer_wave 的手臂真的抬到了头侧 (屏幕空间实测)', wave_n > 20,
          f'头右侧上方区域可见像素 max={wave_n} (阈值 20)')
    up_l = raised_region_count('cheer_hands_up', 210, 200, 300, 320)
    up_r = raised_region_count('cheer_hands_up', 720, 200, 810, 320)
    check('12b. cheer_hands_up 的两条手臂都举高 (屏幕空间实测)',
          up_l > 15 and up_r > 15,
          f'左臂区 {up_l} / 右臂区 {up_r} (阈值各 15)')

    # ---------- 13. 6 个点击动作在真实运行里两两画面不同 ----------
    sigs = {}
    for act in R158_CLICK_SCENES:
        fs = scene_frames(meta, f'click_{act}')
        if not fs:
            continue
        caps = [load_captured(f) for f in fs]
        sig = caps[len(caps) // 2] if caps else None
        sigs[act] = sig
    clash = []
    acts = list(sigs.keys())
    for i in range(len(acts)):
        for j in range(i + 1, len(acts)):
            r = diff_ratio(sigs[acts[i]], sigs[acts[j]])
            if r < 0.01:
                clash.append((acts[i], acts[j], round(r, 4)))
    check('13. 6 个点击动作在真实运行里两两画面不同', len(clash) == 0,
          f'疑似重复 {len(clash)} 组' + (f': {clash[:3]}' if clash else ''))

    passed = sum(1 for r in results if r['ok'])
    failed = sum(1 for r in results if not r['ok'])
    out = {'round': 'R158', 'passed': passed, 'failed': failed, 'checks': results}
    with open(os.path.join(a.preview_dir, 'r158_runtime_verify.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('')
    print(f"R158 运行时客观校验: {passed} passed, {failed} failed (共 {len(results)})")
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
