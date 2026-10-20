#!/usr/bin/env python3
"""R147 运行时预览合成器 — 把真实 Electron 截图序列合成可观看的 GIF。

输入: /tmp/r147_preview/ 下由 `electron src/main.js --preview <dir>` 真实采集的 PNG 帧
      + preview_meta.json (含每帧窗口的真实 x 位移)
输出: 可直接观看的 GIF (左右行走 / 单击反馈 / 自然待机 / 睡眠唤醒) + 汇总图

诚实说明:
  · GIF 里的角色像素 = 真实运行时 capturePage 的像素, 未做任何重绘
  · 行走场景里角色在画布上的横向位置 = 该帧窗口的**真实** x 位移 (dx),
    因此"往哪边走"是运行时真实发生的事, 不是手工摆位
  · 地面线与方向箭头是后加的标注层, 便于阅读
"""
import json
import os
import sys
import argparse

from PIL import Image, ImageDraw, ImageFont


def cjk_font(size=13):
    """取一个支持中文的字体 (macOS 自带), 避免标签渲染成方块。"""
    for path in ("/System/Library/Fonts/PingFang.ttc",
                 "/System/Library/Fonts/Hiragino Sans GB.ttc",
                 "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

BG = (247, 248, 251, 255)
GROUND = (168, 172, 184, 255)
ARROW_L = (222, 118, 40, 255)
ARROW_R = (60, 120, 220, 255)
TEXT = (24, 26, 36, 255)

SCENES = [
    ("walk_left", "向左行走 walk_left (窗口真实向左移动)", -1),
    ("walk_right", "向右行走 walk_right (窗口真实向右移动)", 1),
    ("idle", "自然待机 idle (稳定站姿 + 自然眨眼, 无胸腔膨胀)", 0),
    ("click", "鼠标单击反馈 CLICK (眨眼 + 轻微弹跳)", 0),
    ("wake", "睡眠点击唤醒 sleep_loop → wake_up → idle", 0),
]


def load_scene(preview_dir, scene):
    meta = json.load(open(os.path.join(preview_dir, "preview_meta.json"), encoding="utf-8"))
    frames = meta.get(scene) or []
    out = []
    for f in frames:
        im = Image.open(f["file"]).convert("RGBA")
        out.append((im, f.get("dx", 0)))
    return out


def compose_frame(pet, dx, base_x, scene_w, scene_h, ground_y, label, direction):
    """把角色贴到画布上 (按真实 dx 摆放), 并绘制地面线与方向标注。"""
    canvas = Image.new("RGBA", (scene_w, scene_h), BG)
    d = ImageDraw.Draw(canvas)
    FONT = cjk_font(13)
    d.line([(0, ground_y), (scene_w, ground_y)], fill=GROUND, width=2)
    x = int(base_x + dx)
    canvas.alpha_composite(pet, (x, ground_y - pet.size[1] + 6))
    # 方向箭头
    ay = 22
    if direction < 0:
        d.line([(60, ay), (scene_w - 60, ay)], fill=ARROW_L, width=3)
        d.polygon([(60, ay - 8), (44, ay), (60, ay + 8)], fill=ARROW_L)
        d.text((70, ay - 8), "向左移动", fill=ARROW_L, font=FONT)
    elif direction > 0:
        d.line([(60, ay), (scene_w - 60, ay)], fill=ARROW_R, width=3)
        d.polygon([(scene_w - 60, ay - 8), (scene_w - 44, ay), (scene_w - 60, ay + 8)], fill=ARROW_R)
        d.text((70, ay - 8), "向右移动", fill=ARROW_R, font=FONT)
    d.text((8, 4), label, fill=TEXT, font=FONT)
    return canvas.convert("RGB")


def make_gif(preview_dir, out_dir, scene, label, direction, duration_ms):
    frames = load_scene(preview_dir, scene)
    if not frames:
        print(f"  ⚠️  {scene}: 无采集帧, 跳过")
        return None
    pet_w, pet_h = frames[0][0].size
    dxs = [dx for _, dx in frames]
    min_dx, max_dx = min(dxs), max(dxs)
    span = max_dx - min_dx
    margin = 24
    scene_w = pet_w + span + margin * 2
    scene_h = pet_h + 34
    ground_y = pet_h + 6

    rendered = []
    for im, dx in frames:
        # 让整段位移都落在画布内
        base_x = margin - min_dx
        rendered.append(compose_frame(im, dx, base_x, scene_w, scene_h, ground_y, label, direction))
    gif_path = os.path.join(out_dir, f"R147_{scene}.gif")
    rendered[0].save(gif_path, save_all=True, append_images=rendered[1:],
                     duration=duration_ms, loop=0, disposal=2)
    print(f"  ✅ {gif_path}  ({len(rendered)} 帧, {scene_w}x{scene_h}, 位移 {min_dx}~{max_dx}px)")
    return gif_path


def make_sheet(preview_dir, out_dir):
    """四个场景各取一帧, 拼成一张汇总图 (便于在报告里一眼对比)。"""
    picks = []
    for scene, label, direction in SCENES:
        frames = load_scene(preview_dir, scene)
        if not frames:
            continue
        im, dx = frames[len(frames) // 2]
        span = 0
        picks.append((scene, label, im, dx))
    if not picks:
        return None
    cell_w = max(p[2].size[0] for p in picks) + 30
    cell_h = max(p[2].size[1] for p in picks) + 40
    sheet = Image.new("RGB", (cell_w * len(picks), cell_h), (252, 252, 254))
    d = ImageDraw.Draw(sheet)
    FONT = cjk_font(12)
    for i, (scene, label, im, dx) in enumerate(picks):
        x = i * cell_w + 15
        sheet.paste(im.convert("RGB"), (x, 30), im.split()[3])
        d.text((x, 8), label[:26], fill=TEXT, font=FONT)
    p = os.path.join(out_dir, "R147_preview_summary.png")
    sheet.save(p)
    print(f"  ✅ {p}")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-dir", default="/tmp/r147_preview")
    ap.add_argument("--out-dir", default="/tmp/r147_gifs")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    print("R147 预览合成:")
    durations = {"walk_left": 65, "walk_right": 65, "idle": 70, "click": 45, "wake": 60}
    for scene, label, direction in SCENES:
        make_gif(a.preview_dir, a.out_dir, scene, label, direction, durations[scene])
    make_sheet(a.preview_dir, a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
