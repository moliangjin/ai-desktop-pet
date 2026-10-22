#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R170 证据产出 —— 办公场景恢复 + 吃水果新场景 的真实显示尺寸证据。

产物 (默认写到 图文工作/R170_吃水果/):
  1. 办公场景 R167交付版 vs R170 对比 (200x240 + 256x256)
     —— **画面素材两轮逐字节一致** (R170 没改 R167 的办公帧和道具),
        真正的差异是"办公场景会不会自己出现"。所以第 3 张图才是关键证据:
  2. 触发频率对比卡 (真实 Electron 连跑, 修复前 180s vs 修复后 240s)
  3. 吃水果场景 200x240 / 256x256
  4. 吃水果 5 帧逐帧总览 (200x240 真实尺寸) + 5 帧放大对比 (手/果/嘴)
  5. 吃水果 场景放大 (手/果/嘴的关系)

所有图都用**生产布局算法** (45_R165_scene_preview.py 的 compose) 在真实窗口尺寸上合成,
不是用贴图凑的示意图。
"""
import argparse
import importlib.util
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R156 = os.path.join(ASSETS, 'character_R156')
# R167 交付版快照 (git show 3893c28:candidates/candidate_b_c2/assets/character_R156/*)
BEFORE_DIR = '/tmp/r167_before'
# 触发取证结果: 修复前 (R167 交付版真实连跑) / 修复后 (R170 真实连跑)
BEFORE_TRIGGER = '/tmp/r167_baseline_trigger.json'
AFTER_TRIGGER = os.path.join(CAND, 'evidence_r170_trigger.json')
OUTDIR = '/Users/musk123/Downloads/minimax工作文件夹/图文工作/R170_吃水果'
# 仓库内的对比图证据目录 (供 85_R170_package.py 入包)
COMPARE_DIR = os.path.join(CAND, 'evidence_r170_compare')

_spec = importlib.util.spec_from_file_location(
    'prev', os.path.join(CAND, '45_R165_scene_preview.py'))
prev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prev)

EAT_FRAMES = [f'character_R156/eat_fruit_{i}.png' for i in range(5)]


def font(sz):
    for p in ('/System/Library/Fonts/PingFang.ttc',
              '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def checker(w, h, step=16):
    bg = Image.new('RGBA', (w, h), (250, 250, 252, 255))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, step):
        for x in range(0, w, step):
            if ((x // step) + (y // step)) % 2 == 0:
                d.rectangle([x, y, x + step - 1, y + step - 1], fill=(232, 235, 242, 255))
    return bg


def render(scene, props, char_rel, w, h):
    """按给定道具列表渲染一个场景 (back → 角色 → front), 走生产布局算法。"""
    m = json.load(open(os.path.join(ASSETS, 'character_R141_manifest.json'),
                       encoding='utf-8'))
    lib = (m.get('props') or {}).get('library') or {}
    sc = m['props']['scenes'][scene]
    orig_b, orig_f = list(sc.get('back') or []), list(sc.get('front') or [])
    orig_lib = dict(lib)
    try:
        for name, real in props:
            lib[name] = {'file': os.path.relpath(os.path.abspath(real), ASSETS)}
        sc['back'] = [n for n, _ in props if n.endswith('_b')]
        sc['front'] = [n for n, _ in props if n.endswith('_f')]
        _cr = char_rel if os.path.isabs(char_rel) else os.path.join(ASSETS, char_rel)
        out = prev.compose(scene, w, h, m, frame_override=_cr,
                           out_path=None, checker=False)
    finally:
        m['props']['library'] = orig_lib
        m['props']['scenes'][scene]['back'] = orig_b
        m['props']['scenes'][scene]['front'] = orig_f
    bg = checker(w, h)
    bg.alpha_composite(out)
    return bg.convert('RGB')


def side_by_side(images, title, out_path, zoom=2, labels=None):
    """横向并排多张图 + 标题。"""
    n = len(images)
    W = sum(i.width for i in images) + 12 * (n - 1)
    H = max(i.height for i in images)
    canvas = Image.new('RGB', (W, H + 26), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    d.text((6, 6), title, fill=(20, 20, 30), font=font(13))
    x = 0
    for i, im in enumerate(images):
        canvas.paste(im, (x, 26))
        d.rectangle([x, 26, x + im.width - 1, 25 + im.height], outline=(120, 140, 170))
        if labels:
            d.text((x + 4, 30), labels[i], fill=(30, 30, 40), font=font(11))
        x += im.width + 12
    canvas = canvas.resize((canvas.width * zoom, canvas.height * zoom), Image.LANCZOS)
    canvas.save(out_path)
    # 同一张图再落一份到仓库的 evidence_r170_compare/ (供打包器入包)
    try:
        os.makedirs(COMPARE_DIR, exist_ok=True)
        canvas.save(os.path.join(COMPARE_DIR, os.path.basename(out_path)))
    except Exception:
        pass
    print(f'  📷 {out_path}  {canvas.size}')


def save_extra(im, out_path):
    im.save(out_path)
    try:
        os.makedirs(COMPARE_DIR, exist_ok=True)
        im.save(os.path.join(COMPARE_DIR, os.path.basename(out_path)))
    except Exception:
        pass
    print(f'  📷 {out_path}  {im.size}')


def trigger_card(out_path):
    """触发频率对比卡 —— 办公场景"消失"问题的**决定性证据**。

    修复前 = R167 交付版 (git 3893c28) 真实 Electron 连跑;
    修复后 = R170 真实 Electron 连跑。
    画面素材两轮逐字节一致, 差异全在"会不会自己出现"。
    """
    if not (os.path.exists(BEFORE_TRIGGER) and os.path.exists(AFTER_TRIGGER)):
        print('  ⚠️  缺少触发取证 JSON, 跳过触发对比卡')
        return
    before = json.load(open(BEFORE_TRIGGER, encoding='utf-8'))
    after = json.load(open(AFTER_TRIGGER, encoding='utf-8'))

    def stat(d):
        st = d.get('stats') or d.get('summary') or {}
        for k in ('work_sessions', 'eat_fruit_sessions'):
            pass
        return st

    W, H = 1180, 460
    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    d.text((16, 12), '办公场景"消失"问题 —— 真实 Electron 连跑触发对比',
           fill=(16, 18, 30), font=font(17))
    d.text((16, 36), '画面素材两轮逐字节一致 (R170 未改 R167 办公帧与道具); '
                     '差异全在"会不会自己出现"',
           fill=(90, 100, 120), font=font(12))

    def block(x, title, path, note):
        d.text((x, 72), title, fill=(16, 18, 30), font=font(15))
        d.text((x, 94), note, fill=(110, 118, 135), font=font(11))
        if not os.path.exists(path):
            d.text((x, 130), '(缺少证据文件)', fill=(200, 40, 40), font=font(12))
            return
        j = json.load(open(path, encoding='utf-8'))
        lines = []
        checks = j.get('checks') or {}
        for cid, v in checks.items():
            if not isinstance(v, dict):
                continue
            st = v.get('pass')
            st = 'PASS' if st is True else ('FAIL' if st is False else 'N/A')
            det = json.dumps({k: vv for k, vv in v.items() if k != 'pass'},
                             ensure_ascii=False)[:150]
            lines.append((cid, st, det))
        if not lines:
            for it in j.get('items', []):
                lines.append((it.get('id', ''), it.get('status', ''),
                              str(it.get('detail', ''))[:150]))
        if not lines:
            lines = [(k, '', json.dumps(v, ensure_ascii=False)[:150])
                     for k, v in (j.get('summary') or {}).items()]
        # 底部摘要: 关键数字
        st2 = j.get('stats') or {}
        y = 124
        for cid, st, det in lines:
            col = (30, 130, 60) if st == 'PASS' else (
                (200, 40, 40) if st == 'FAIL' else (150, 120, 40))
            d.text((x, y), '✔' if st == 'PASS' else ('✘' if st == 'FAIL' else '➖'),
                   fill=col, font=font(12))
            d.text((x + 22, y), f'{cid}  {st}', fill=col, font=font(11))
            d.text((x + 22, y + 15), det, fill=(70, 78, 95), font=font(10))
            y += 36
        # 关键数字条
        d.rectangle([x, y + 4, x + 540, y + 62], outline=(200, 205, 215))
        d.text((x + 8, y + 10),
               f"观测窗 {j.get('observation_seconds', '?')}s | 空闲决策 {j.get('idle_decisions', '?')} 次 | "
               f"WORK {len(j.get('work_sessions') or [])} 次 | "
               f"EAT_FRUIT {len(j.get('eat_fruit_sessions') or [])} 次",
               fill=(20, 24, 36), font=font(12))
        if j.get('work_sessions'):
            durs = [s['duration'] for s in j['work_sessions']]
            d.text((x + 8, y + 32),
                   f"WORK 每次持续 {durs} ms | 间隔 {j.get('work_gaps_ms')} ms",
                   fill=(60, 66, 82), font=font(11))
        if j.get('eat_fruit_sessions'):
            durs = [s['duration'] for s in j['eat_fruit_sessions']]
            d.text((x + 8, y + 46),
                   f"EAT_FRUIT 每次持续 {durs} ms",
                   fill=(60, 66, 82), font=font(11))
        return

    block(16, '修复前 —— R167 交付版 (git 3893c28)', BEFORE_TRIGGER,
          '基线: manifest.behavior.config 里**根本没有 work_probability**, '
          'sleep=0.30 / walk=0.70')
    block(600, '修复后 —— R170', AFTER_TRIGGER,
          'work_probability=0.55 / 16~28s / 冷却 60s; '
          'eat_fruit_probability=0.36 / 14~22s / 冷却 50s')

    save_extra(canvas, out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=OUTDIR)
    args = ap.parse_args()
    od = args.out_dir
    os.makedirs(od, exist_ok=True)
    print('R170 证据产出:')

    # ---------- 1. 办公场景: R167 交付版 vs R170 ----------
    work_props = [('prop_chair_b', os.path.join(R156, 'prop_chair.png')),
                  ('prop_desk_surface_b', os.path.join(R156, 'prop_desk_surface.png')),
                  ('prop_keyboard_b', os.path.join(R156, 'prop_keyboard.png')),
                  ('prop_desk_f', os.path.join(R156, 'prop_desk.png')),
                  ('prop_screen_glow_f', os.path.join(R156, 'prop_screen_glow.png'))]
    work_before = [('prop_chair_b', os.path.join(BEFORE_DIR, 'prop_chair.png')),
                   ('prop_desk_surface_b', os.path.join(BEFORE_DIR, 'prop_desk_surface.png')),
                   ('prop_keyboard_b', os.path.join(BEFORE_DIR, 'prop_keyboard.png')),
                   ('prop_desk_f', os.path.join(BEFORE_DIR, 'prop_desk.png')),
                   ('prop_screen_glow_f', os.path.join(BEFORE_DIR, 'prop_screen_glow.png'))]
    if os.path.isdir(BEFORE_DIR):
        b200 = render('work', work_before, os.path.join(BEFORE_DIR, 'work_1.png'), 200, 240)
        a200 = render('work', work_props, 'character_R156/work_1.png', 200, 240)
        side_by_side([b200, a200], '办公场景 R167交付版 | R170 (素材一致, 差别在"会不会自己出现")',
                     os.path.join(od, '办公场景_R167版_vs_R170_200x240.png'), zoom=2,
                     labels=['R167 交付版', 'R170'])
        b256 = render('work', work_before, os.path.join(BEFORE_DIR, 'work_1.png'), 256, 256)
        a256 = render('work', work_props, 'character_R156/work_1.png', 256, 256)
        side_by_side([b256, a256], '办公场景 R167交付版 | R170  256x256',
                     os.path.join(od, '办公场景_R167版_vs_R170_256x256.png'), zoom=2,
                     labels=['R167 交付版', 'R170'])
    else:
        print('  ⚠️  缺少 /tmp/r167_before (R167 交付版快照), 跳过办公前后对比')

    # ---------- 1b. 触发频率对比 (决定性证据) ----------
    trigger_card(os.path.join(od, '办公场景_触发频率_修复前vs修复后.png'))

    # ---------- 2. 吃水果场景 ----------
    eat_props = [('prop_stool_b', os.path.join(R156, 'prop_stool.png')),
                 ('prop_fruit_table_b', os.path.join(R156, 'prop_fruit_table.png'))]
    missing = [p for _, p in eat_props if not os.path.exists(p)]
    if missing:
        print('  ⚠️  吃水果道具缺失, 跳过:', missing)
        return
    for size in ((200, 240), (256, 256)):
        im = render('eat_fruit', eat_props, EAT_FRAMES[0], size[0], size[1])
        side_by_side([im], f'吃水果场景 {size[0]}x{size[1]}',
                     os.path.join(od, f'吃水果场景_{size[0]}x{size[1]}.png'), zoom=2)

    # ---------- 3. 5 帧逐帧总览 ----------
    tiles = []
    for rel in EAT_FRAMES:
        tiles.append(render('eat_fruit', eat_props, rel, 200, 240))
    side_by_side(tiles, '吃水果 5 帧逐帧总览 (200x240 真实尺寸)',
                 os.path.join(od, '吃水果_5帧逐帧总览_200x240.png'), zoom=2,
                 labels=['0 拿果', '1 举到嘴边', '2 咬一口', '3 咀嚼', '4 满足微笑'])

    # ---------- 4. 5 帧放大 (手/果/嘴) ----------
    zooms = []
    for rel in EAT_FRAMES:
        im = render('eat_fruit', eat_props, rel, 200, 240)
        z = im.crop((60, 40, 150, 130)).resize((90 * 4, 90 * 4), Image.LANCZOS)
        zooms.append(z)
    side_by_side(zooms, '吃水果 5 帧放大 (手 / 果 / 嘴)',
                 os.path.join(od, '吃水果_5帧放大_手果嘴.png'), zoom=1,
                 labels=['0', '1', '2', '3', '4'])


if __name__ == '__main__':
    main()
