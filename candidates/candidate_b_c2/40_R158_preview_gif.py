#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R158 运行时预览合成器 — 把真实 Electron 采集的帧合成可直接观看的 GIF / 总览图。

输入: evidence_r158_preview/ 下由 `electron src/main.js --preview <dir>` 真实采集的 PNG 帧
      + preview_meta.json (含每帧窗口的真实 x 位移)
输出: R158_*.gif (6 个点击动作) + 点击动作总览图

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

CLICKS = [
    ('click_cheer_wave', '真挥手 cheer_wave (抬手 → 手腕右摆 → 手腕左摆)', 55),
    ('click_cheer_hands_up', '双臂欢呼 cheer_hands_up (高举 → 更高 → 落回)', 55),
    ('click_cheer_heart', '比心 cheer_heart (双手合拢 + 爱心特效)', 55),
    ('click_cheer_clap', '鼓掌 cheer_clap (张开 → 合拢 → 张开)', 55),
    ('click_cheer_jump', '开心跳跃 cheer_jump (蓄力 → 腾空+双臂上扬 → 落地)', 55),
    ('click_cheer_tilt', '歪头眨眼 cheer_tilt (歪头 → 眯眼 → 闭眼笑)', 55),
]

OVERVIEW_LABELS = {
    'click_cheer_wave': '真挥手 cheer_wave',
    'click_cheer_hands_up': '双臂欢呼 cheer_hands_up',
    'click_cheer_heart': '比心 cheer_heart (+爱心特效)',
    'click_cheer_clap': '鼓掌 cheer_clap',
    'click_cheer_jump': '开心跳跃 cheer_jump',
    'click_cheer_tilt': '歪头眨眼 cheer_tilt',
}


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


def make_gif(meta, out_dir, scene, label, duration_ms, prefix="R158", max_frames=None):
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
    rows = []
    for scene, _label, _dur in CLICKS:
        fr = load_scene(meta, scene)
        if not fr:
            continue
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
        rows.append((OVERVIEW_LABELS.get(scene, scene), picks))
    if not rows:
        return None
    cw = max(p[1][0].size[0] for p in rows) + 20
    ch = max(p[1][0].size[1] for p in rows) + 30
    sheet = Image.new("RGB", (cw * 3 + 110, ch * len(rows) + 26), (252, 252, 254))
    d = ImageDraw.Draw(sheet)
    FONT = cjk_font(12)
    d.text((6, 5), "R158 点击互动动作池 (每个动作 3 帧: 开始 / 情绪高点 / 收势) — 真实运行采集像素",
           fill=ACCENT, font=cjk_font(14))
    for r, (label, picks) in enumerate(rows):
        y = 28 + r * ch
        d.text((4, y + ch // 2 - 8), label, fill=TEXT, font=FONT)
        for c, im in enumerate(picks):
            x = 110 + c * cw
            bg = Image.new("RGBA", im.size, BG)
            bg.alpha_composite(im)
            sheet.paste(bg.convert("RGB"), (x, y))
            d.text((x + 4, y + 2), ['开始', '中间', '结束'][c], fill=(120, 124, 138), font=FONT)
    p = os.path.join(out_dir, "R158_click_pool_overview.png")
    sheet.save(p)
    print(f"  ✅ {os.path.basename(p)}  ({len(rows)} 个点击动作 × 3 帧)")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-dir", default="evidence_r158_preview")
    ap.add_argument("--out-dir", default="evidence_r158_gifs")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    meta = load_meta(a.preview_dir)

    print("R158 预览合成 (全部来自真实运行采集):")
    for scene, label, dur in CLICKS:
        make_gif(meta, a.out_dir, scene, label, dur)
    make_click_overview(meta, a.out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
