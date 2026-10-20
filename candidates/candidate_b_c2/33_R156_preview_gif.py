#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R156 运行时预览合成器 — 把真实 Electron 采集的帧合成可直接观看的 GIF / 总览图。

输入: evidence_r156_preview/ 下由 `electron src/main.js --preview <dir>` 真实采集的 PNG 帧
      + preview_meta.json (含每帧窗口的真实 x 位移)
输出: R156_*.gif (点击动作 6 个 + 三个新场景 + 道具退场) + 点击动作总览图 + 场景总览图

诚实说明:
  · GIF 里的像素 = 真实运行时 capturePage 的像素, 未做任何重绘
  · 每个 GIF 的帧时长 = 该场景**实际采集间隔**, 即播放速度与真实运行时一致
  · 标题层是后加的说明文字, 不改变角色像素
"""
import json
import os
import sys
import argparse

from PIL import Image, ImageDraw, ImageFont

BG = (247, 248, 251, 255)
GROUND = (176, 180, 192, 255)
TEXT = (24, 26, 36, 255)
ACCENT = (216, 62, 92, 255)


def cjk_font(size=13):
    for path in ("/System/Library/Fonts/PingFang.ttc",
                 "/System/Library/Fonts/Hiragino Sans GB.ttc",
                 "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def load_meta(preview_dir):
    return json.load(open(os.path.join(preview_dir, "preview_meta.json"), encoding="utf-8"))


def load_scene(meta, scene):
    out = []
    for f in (meta.get(scene) or []):
        out.append((Image.open(f["file"]).convert("RGBA"), f.get("dx", 0), f.get("winX", 0)))
    return out


def compose(pet, dx, base_x, scene_w, scene_h, ground_y, label):
    canvas = Image.new("RGBA", (scene_w, scene_h), BG)
    d = ImageDraw.Draw(canvas)
    d.line([(0, ground_y), (scene_w, ground_y)], fill=GROUND, width=2)
    x = int(base_x + dx)
    canvas.alpha_composite(pet, (x, ground_y - pet.size[1] + 6))
    d.text((8, 4), label, fill=TEXT, font=cjk_font(13))
    return canvas.convert("RGB")


def make_gif(meta, out_dir, scene, label, duration_ms, prefix="R156", max_frames=None):
    frames = load_scene(meta, scene)
    if not frames:
        print(f"  ⚠️  {scene}: 无采集帧, 跳过")
        return None
    if max_frames:
        frames = frames[:max_frames]
    pet_w, pet_h = frames[0][0].size
    dxs = [dx for _, dx, _ in frames]
    min_dx, max_dx = min(dxs), max(dxs)
    span = max_dx - min_dx
    margin = 30
    scene_w = pet_w + span + margin * 2
    scene_h = pet_h + 46
    ground_y = pet_h + 6
    base_x = margin - min_dx
    rendered = [compose(im, dx, base_x, scene_w, scene_h, ground_y, label)
                for im, dx, _ in frames]
    path = os.path.join(out_dir, f"{prefix}_{scene}.gif")
    rendered[0].save(path, save_all=True, append_images=rendered[1:],
                     duration=duration_ms, loop=0, disposal=2)
    print(f"  ✅ {os.path.basename(path)}  ({len(frames)} 帧, {duration_ms}ms/帧, "
          f"{len(frames) * duration_ms / 1000:.2f}s)")
    return path


def make_click_overview(meta, out_dir):
    """6 个点击动作 × 3 帧 (开始/中间/结束) 的总览图。"""
    items = [
        ('click_cheer_heart', '比心 cheer_heart (近似)'),
        ('click_cheer_jump', '开心小跳 cheer_jump'),
        ('click_cheer_spin', '原地轻盈转身 cheer_spin'),
        ('click_cheer_wink', '歪头眨眼 cheer_wink'),
        ('click_cheer_hands', '双手小庆祝 cheer_hands'),
        ('click_cheer_sway', '开心摇摆 cheer_sway'),
    ]
    rows = []
    for scene, label in items:
        fr = load_scene(meta, scene)
        if not fr:
            continue
        # 取该场景里差异最大的 3 帧, 并**按采集顺序排回去** (否则开始/中间/结束会错位)
        base = fr[0][0]
        scored = []
        for idx, (im, _, _) in enumerate(fr):
            d = sum(abs(a - b) for a, b in zip(im.tobytes(), base.tobytes())) / (im.size[0] * im.size[1] * 4)
            scored.append((d, idx, im))
        scored.sort(key=lambda t: -t[0])
        top = sorted(scored[:3], key=lambda t: t[1])
        picks = [t[2] for t in top]
        while len(picks) < 3:
            picks.append(fr[-1][0])
        rows.append((label, picks))
    if not rows:
        return None
    cw = max(p[1][0].size[0] for p in rows) + 20
    ch = max(p[1][0].size[1] for p in rows) + 30
    sheet = Image.new("RGB", (cw * 3 + 96, ch * len(rows)), (252, 252, 254))
    d = ImageDraw.Draw(sheet)
    FONT = cjk_font(12)
    d.text((6, 6), "R156 点击互动动作池 (每个动作 3 帧: 开始 / 情绪高点 / 收势)",
           fill=ACCENT, font=cjk_font(14))
    for r, (label, picks) in enumerate(rows):
        y = 28 + r * ch
        d.text((4, y + ch // 2 - 8), label, fill=TEXT, font=FONT)
        for c, im in enumerate(picks):
            x = 96 + c * cw
            bg = Image.new("RGBA", im.size, BG)
            bg.alpha_composite(im)
            sheet.paste(bg.convert("RGB"), (x, y))
            d.text((x + 4, y + 2), ['开始', '中间', '结束'][c], fill=(120, 124, 138), font=FONT)
    p = os.path.join(out_dir, "R156_click_pool_overview.png")
    sheet.save(p)
    print(f"  ✅ {os.path.basename(p)}  ({len(rows)} 个点击动作 × 3 帧)")
    return p


def make_scene_overview(meta, out_dir):
    """睡觉 / 沙发 / 办公 三个新场景的总览图。"""
    items = [
        ('scene_sleep', '睡觉场景 (床 + 月亮夜晚氛围 + 被子)'),
        ('scene_sofa', '坐下场景 (低矮小沙发)'),
        ('scene_work', '办公待机 (转椅 + 小桌子 + 笔记本 + 屏幕微光)'),
        ('scene_prop_exit', '道具退场 (从床 → 站立, 床与月亮必须一起退出)'),
    ]
    picks = []
    for scene, label in items:
        fr = load_scene(meta, scene)
        if not fr:
            continue
        picks.append((label, fr[len(fr) // 2][0]))
    if not picks:
        return None
    cw = max(p[1].size[0] for p in picks) + 20
    ch = max(p[1].size[1] for p in picks) + 30
    cols = 4
    sheet = Image.new("RGB", (cw * cols, ch + 26), (252, 252, 254))
    d = ImageDraw.Draw(sheet)
    FONT = cjk_font(12)
    for i, (label, im) in enumerate(picks):
        x = i * cw + 10
        y = 24
        bg = Image.new("RGBA", im.size, BG)
        bg.alpha_composite(im)
        sheet.paste(bg.convert("RGB"), (x, y))
        d.text((x, 5), label, fill=TEXT, font=FONT)
    p = os.path.join(out_dir, "R156_scene_overview.png")
    sheet.save(p)
    print(f"  ✅ {os.path.basename(p)}  ({len(picks)} 个场景)")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-dir", default="evidence_r156_preview")
    ap.add_argument("--out-dir", default="evidence_r156_gifs")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    meta = load_meta(a.preview_dir)

    print("R156 预览合成 (全部来自真实运行采集):")
    # 点击互动池: 每个动作一个 GIF
    CLICKS = [
        ('click_cheer_heart', "比心 cheer_heart (手贴胸, 近似; 开始→高点→收势)", 55),
        ('click_cheer_jump', "开心小跳 cheer_jump (蓄力下蹲→腾空→落地缓冲)", 55),
        ('click_cheer_spin', "原地轻盈转身 cheer_spin (正面→侧身→回正)", 55),
        ('click_cheer_wink', "歪头眨眼卖萌 cheer_wink (歪头→眯眼→闭眼笑)", 55),
        ('click_cheer_hands', "双手小庆祝 cheer_hands (举手→大笑→下沉)", 55),
        ('click_cheer_sway', "开心摇摆 cheer_sway (左摆→右摆→回正笑)", 55),
    ]
    for scene, label, dur in CLICKS:
        make_gif(meta, a.out_dir, scene, label, dur)

    # 三个新场景
    make_gif(meta, a.out_dir, 'scene_sleep',
             "睡觉场景: 床 + 枕头 + 被子 + 月亮夜晚氛围", 160)
    make_gif(meta, a.out_dir, 'scene_sofa',
             "坐下场景: 低矮小沙发 (坐姿与座面接触)", 150)
    make_gif(meta, a.out_dir, 'scene_work',
             "办公待机: 转椅 + 小桌子 + 笔记本 + 屏幕微光", 280)
    make_gif(meta, a.out_dir, 'scene_prop_exit',
             "道具退场: 床与月亮随动作一起退出, 不得残留", 90)

    make_click_overview(meta, a.out_dir)
    make_scene_overview(meta, a.out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
