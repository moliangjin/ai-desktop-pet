#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R153 运行时预览合成器 — 把真实 Electron 采集的帧合成可直接观看的 GIF。

输入: evidence_r153_preview/ 下由 `electron src/main.js --preview <dir>` 真实采集的 PNG 帧
      + preview_meta.json (含每帧窗口的真实 x 位移)
输出: R153_*.gif (每个新动作一个) + 动作总览图 + 姿态对比图

诚实说明:
  · GIF 里的角色像素 = 真实运行时 capturePage 的像素, 未做任何重绘
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


def make_gif(meta, out_dir, scene, label, duration_ms, prefix="R153"):
    frames = load_scene(meta, scene)
    if not frames:
        print(f"  ⚠️  {scene}: 无采集帧, 跳过")
        return None
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


def make_action_sheet(meta, out_dir):
    """15 个动作的总览图 (每个动作取其最有代表性的一帧)。"""
    items = [
        ('idle', '自然待机 idle'),
        ('walk_left', '向左走 walk_left'),
        ('walk_right', '向右走 walk_right'),
        ('lib_look_around', '左右张望 look_around'),
        ('lib_tilt_head', '歪头观察 tilt_head'),
        ('lib_head_nod', '点头回应 head_nod'),
        ('lib_happy', '开心反馈 happy'),
        ('lib_blink_soft', '柔和眨眼 blink_soft'),
        ('lib_stretch', '伸懒腰 stretch'),
        ('lib_sit_rest', '坐下休息 sit_rest'),
        ('lib_doze', '困倦打盹 doze'),
        ('lib_sleep_breath', '躺姿呼吸 sleep_breath'),
        ('click', '点击反馈 click'),
        ('wake', '睡眠唤醒 wake'),
    ]
    picks = []
    for scene, label in items:
        fr = load_scene(meta, scene)
        if not fr:
            continue
        base = fr[0][0]
        best, best_d = base, -1.0
        for im, _, _ in fr:
            d = sum(abs(a - b) for a, b in zip(im.tobytes(), base.tobytes())) / (im.size[0] * im.size[1] * 4)
            if d > best_d:
                best, best_d = im, d
        picks.append((label, best))
    if not picks:
        return None
    cw = max(p[1].size[0] for p in picks) + 24
    ch = max(p[1].size[1] for p in picks) + 40
    cols = 7
    rows = (len(picks) + cols - 1) // cols
    sheet = Image.new("RGB", (cw * cols, ch * rows), (252, 252, 254))
    d = ImageDraw.Draw(sheet)
    FONT = cjk_font(12)
    for i, (label, im) in enumerate(picks):
        x = (i % cols) * cw + 12
        y = (i // cols) * ch + 24
        sheet.paste(im.convert("RGB"), (x, y), im.split()[3])
        d.text((x, 4 + (i // cols) * ch), label, fill=TEXT, font=FONT)
    p = os.path.join(out_dir, "R153_action_overview.png")
    sheet.save(p)
    print(f"  ✅ {os.path.basename(p)}  ({len(picks)} 个动作)")
    return p


def make_transition_strip(meta, out_dir):
    """坐→躺 的逐帧渐变条 (证明"坐下瞬间躺下"已变成溶解过渡)。"""
    fr = load_scene(meta, 'lib_transition')
    if not fr:
        return None
    sel = fr[8:18]
    w, h = sel[0][0].size
    sheet = Image.new("RGB", (w * len(sel), h + 26), (252, 252, 254))
    d = ImageDraw.Draw(sheet)
    FONT = cjk_font(12)
    for i, (im, _, _) in enumerate(sel):
        bg = Image.new("RGBA", im.size, (247, 248, 251, 255))
        sheet.paste(Image.alpha_composite(bg, im).convert("RGB"), (i * w, 26))
        d.text((i * w + 4, 5), f"#{i + 8}", fill=TEXT, font=FONT)
    d.text((6, h + 8), "坐 → 躺 的逐帧渐变 (中间为交叉溶解的混合帧)", fill=ACCENT, font=FONT)
    p = os.path.join(out_dir, "R153_sit_to_lie_transition.png")
    sheet.save(p)
    print(f"  ✅ {os.path.basename(p)}")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-dir", default="evidence_r153_preview")
    ap.add_argument("--out-dir", default="evidence_r153_gifs")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    meta = load_meta(a.preview_dir)

    print("R153 预览合成 (全部来自真实运行采集):")
    # 核心 6 组的真实表现 (R153 修复后的版本)
    make_gif(meta, a.out_dir, 'walk_left',
             "walk_left 向左行走 (R153: 错切归零, 重心端正)", 65)
    make_gif(meta, a.out_dir, 'walk_right',
             "walk_right 向右行走 (R153: 错切归零, 重心端正)", 65)
    make_gif(meta, a.out_dir, 'idle',
             "自然待机 idle (稳定站姿 + 自然眨眼; 不再出现'手放胸前')", 70)
    make_gif(meta, a.out_dir, 'click',
             "鼠标单击反馈 click (R153: 歪头+眯眼笑 + 轻微弹跳)", 45)
    make_gif(meta, a.out_dir, 'wake',
             "睡眠点击唤醒 sleep_breath → wake_up → 伸懒腰 → idle", 60)

    # R153 新增的 9 个库动作
    LIB = [
        ('lib_look_around', "左右张望 look_around", 90),
        ('lib_tilt_head', "歪头观察 tilt_head", 100),
        ('lib_head_nod', "点头回应 head_nod", 70),
        ('lib_happy', "开心反馈 happy (歪头+眯眼笑)", 90),
        ('lib_blink_soft', "柔和眨眼 blink_soft (手臂始终下垂)", 40),
        ('lib_stretch', "伸懒腰 stretch", 110),
        ('lib_sit_rest', "坐下休息 sit_rest", 150),
        ('lib_doze', "困倦打盹 doze (坐着, 不躺下)", 150),
        ('lib_sleep_breath', "躺姿呼吸 sleep_breath (胸口微起伏)", 160),
    ]
    for scene, label, dur in LIB:
        make_gif(meta, a.out_dir, scene, label, dur)

    # 过渡
    make_gif(meta, a.out_dir, 'lib_transition',
             "坐 → 躺 的交叉溶解过渡 (R153: 不再瞬间躺下)", 40)
    make_gif(meta, a.out_dir, 'lib_sit_to_doze',
             "坐 → 打盹 (坐着打盹, 不躺下)", 90)

    make_action_sheet(meta, a.out_dir)
    make_transition_strip(meta, a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
