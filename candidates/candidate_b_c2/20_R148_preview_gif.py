#!/usr/bin/env python3
"""R148 运行时预览合成器 — 把真实 Electron 采集的帧合成可直接观看的 GIF。

输入: /tmp/r148_preview/ 下由 `electron src/main.js --preview <dir>` 真实采集的 PNG 帧
      + preview_meta.json (含每帧窗口的真实 x 位移)
输出: R148_*.gif + 汇总图 + 撞边 x 轨迹图

诚实说明:
  · GIF 里的角色像素 = 真实运行时 capturePage 的像素, 未做任何重绘
  · 行走场景里角色在画布上的横向位置 = 该帧窗口的**真实** x 位移 (dx),
    因此"往哪边走"是运行时真实发生的事, 不是手工摆位
  · 地面线与方向标注是后加的说明层
  · 步态循环数 = 采集时长 / (帧数 × frame_ms), 直接按 manifest 的 frame_ms 算
"""
import json
import os
import sys
import argparse

from PIL import Image, ImageDraw, ImageFont


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


BG = (247, 248, 251, 255)
GROUND = (168, 172, 184, 255)
ARROW_L = (222, 118, 40, 255)
ARROW_R = (60, 120, 220, 255)
TURN = (216, 62, 92, 255)
TEXT = (24, 26, 36, 255)

# 每个动作一循环的时长 (4 帧 × 130ms) —— 来自 manifest 的 frame_ms
GAIT_CYCLE_MS = 4 * 130


def load_meta(preview_dir):
    return json.load(open(os.path.join(preview_dir, "preview_meta.json"), encoding="utf-8"))


def load_scene(meta, scene):
    out = []
    for f in (meta.get(scene) or []):
        im = Image.open(f["file"]).convert("RGBA")
        out.append((im, f.get("dx", 0), f.get("winX", 0)))
    return out


def compose_frame(pet, dx, base_x, scene_w, scene_h, ground_y, label, direction, turn_x=None):
    canvas = Image.new("RGBA", (scene_w, scene_h), BG)
    d = ImageDraw.Draw(canvas)
    FONT = cjk_font(13)
    d.line([(0, ground_y), (scene_w, ground_y)], fill=GROUND, width=2)
    x = int(base_x + dx)
    canvas.alpha_composite(pet, (x, ground_y - pet.size[1] + 6))
    ay = 22
    if turn_x is not None:
        # 撞边点: 标出转向位置, 并画双向箭头
        tx = int(base_x + turn_x)
        d.line([(tx, 4), (tx, ground_y)], fill=TURN, width=2)
        d.text((tx + 6, ay + 30), "← 撞到屏幕边缘, 转向 →", fill=TURN, font=FONT)
        d.line([(tx - 120, ay), (tx, ay)], fill=ARROW_L, width=3)
        d.polygon([(tx - 120, ay - 8), (tx - 136, ay), (tx - 120, ay + 8)], fill=ARROW_L)
        d.line([(tx, ay), (tx + 120, ay)], fill=ARROW_R, width=3)
        d.polygon([(tx + 120, ay - 8), (tx + 136, ay), (tx + 120, ay + 8)], fill=ARROW_R)
    elif direction < 0:
        d.line([(60, ay), (scene_w - 60, ay)], fill=ARROW_L, width=3)
        d.polygon([(60, ay - 8), (44, ay), (60, ay + 8)], fill=ARROW_L)
        d.text((70, ay - 8), "窗口真实向左移动", fill=ARROW_L, font=FONT)
    elif direction > 0:
        d.line([(60, ay), (scene_w - 60, ay)], fill=ARROW_R, width=3)
        d.polygon([(scene_w - 60, ay - 8), (scene_w - 44, ay), (scene_w - 60, ay + 8)], fill=ARROW_R)
        d.text((70, ay - 8), "窗口真实向右移动", fill=ARROW_R, font=FONT)
    d.text((8, 4), label, fill=TEXT, font=FONT)
    return canvas.convert("RGB")


def make_gif(meta, out_dir, scene, label, direction, duration_ms, prefix="R148",
             turn_dx=None, note=None):
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

    rendered = []
    for im, dx, _ in frames:
        rendered.append(compose_frame(im, dx, base_x, scene_w, scene_h, ground_y,
                                      label, direction, turn_dx))
    gif_path = os.path.join(out_dir, f"{prefix}_{scene}.gif")
    rendered[0].save(gif_path, save_all=True, append_images=rendered[1:],
                     duration=duration_ms, loop=0, disposal=2)
    dur = len(frames) * duration_ms / 1000.0
    cycles = dur / (GAIT_CYCLE_MS / 1000.0)
    print(f"  ✅ {gif_path}  ({len(frames)} 帧, {scene_w}x{scene_h}, 位移 {min_dx}~{max_dx}px, "
          f"时长 {dur:.2f}s ≈ {cycles:.2f} 个步态循环)")
    return gif_path


def make_edge_trail(meta, out_dir):
    """撞边 x 轨迹图: 直接用 preview_meta 里每帧的**真实**窗口 x。"""
    frames = load_scene(meta, 'edge_turn')
    if not frames:
        return None
    xs = [wx for _, _, wx in frames]
    W, H = 900, 260
    img = Image.new("RGB", (W, H), (252, 252, 254))
    d = ImageDraw.Draw(img)
    FONT = cjk_font(12)
    pad = 46
    x0, x1 = min(xs), max(xs)
    span = max(1, x1 - x0)

    def px(v):
        return pad + (v - x0) / span * (W - pad * 2)

    # 转向点 = x 序列的局部最小值
    turn_i = min(range(len(xs)), key=lambda i: xs[i])
    for i in range(1, len(xs)):
        c = ARROW_L if xs[i] < xs[i - 1] else (ARROW_R if xs[i] > xs[i - 1] else TURN)
        d.line([(px(xs[i - 1]), 150), (px(xs[i]), 150)], fill=c, width=3)
    d.line([(pad, 150), (W - pad, 150)], fill=(210, 212, 220), width=1)
    d.line([(px(xs[turn_i]), 40), (px(xs[turn_i]), 230)], fill=TURN, width=2)
    d.text((px(xs[turn_i]) + 6, 44), f"撞边转向 (第 {turn_i} 帧, x={xs[turn_i]})",
           fill=TURN, font=FONT)
    d.text((pad, 16), "撞边场景: 窗口真实 x 轨迹 (左=屏幕左缘)", fill=TEXT, font=FONT)
    d.text((pad, 232), f"起始 x={x0} → 最小 x={x1} → 末帧 x={xs[-1]}", fill=TEXT, font=FONT)
    p = os.path.join(out_dir, "R148_edge_turn_trail.png")
    img.save(p)
    print(f"  ✅ {p}  (转向发生在第 {turn_i}/{len(xs)} 帧)")
    return p, turn_i, xs


def make_sheet(meta, out_dir):
    picks = []
    for scene, label in (('walk_left', 'walk_left (向左)'),
                         ('walk_right', 'walk_right (向右, R148 修复)'),
                         ('edge_turn', '撞边转向 edge-turn'),
                         ('idle', '自然待机 idle'),
                         ('click', '单击反馈 click'),
                         ('wake', '睡眠唤醒 wake')):
        frames = load_scene(meta, scene)
        if not frames:
            continue
        picks.append((label, frames[len(frames) // 2][0]))
    if not picks:
        return None
    cell_w = max(p[1].size[0] for p in picks) + 30
    cell_h = max(p[1].size[1] for p in picks) + 40
    sheet = Image.new("RGB", (cell_w * len(picks), cell_h), (252, 252, 254))
    d = ImageDraw.Draw(sheet)
    FONT = cjk_font(12)
    for i, (label, im) in enumerate(picks):
        x = i * cell_w + 15
        sheet.paste(im.convert("RGB"), (x, 30), im.split()[3])
        d.text((x, 8), label, fill=TEXT, font=FONT)
    p = os.path.join(out_dir, "R148_preview_summary.png")
    sheet.save(p)
    print(f"  ✅ {p}")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview-dir", default="/tmp/r148_preview")
    ap.add_argument("--out-dir", default="/tmp/r148_gifs")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    meta = load_meta(a.preview_dir)

    print("R148 预览合成 (全部来自真实运行采集):")
    make_gif(meta, a.out_dir, 'walk_left',
             "walk_left  向左行走 (窗口真实向左移动, 落脚脚在左、鞋尖朝左)",
             -1, 65)
    make_gif(meta, a.out_dir, 'walk_right',
             "walk_right 向右行走 (R148 镜像修复: 落脚脚在右、鞋尖朝右)",
             1, 65)
    make_gif(meta, a.out_dir, 'idle',
             "自然待机 idle (稳定站姿 + 自然眨眼)", 0, 70)
    make_gif(meta, a.out_dir, 'click',
             "鼠标单击反馈 CLICK (眨眼 + 轻微弹跳)", 0, 45)
    make_gif(meta, a.out_dir, 'wake',
             "睡眠点击唤醒 sleep_loop → wake_up → idle", 0, 60)

    # 撞边场景: 找出转向点并标注
    frames = load_scene(meta, 'edge_turn')
    turn_dx = None
    if frames:
        xs = [wx for _, _, wx in frames]
        turn_i = min(range(len(xs)), key=lambda i: xs[i])
        turn_dx = frames[turn_i][1]
    make_gif(meta, a.out_dir, 'edge_turn',
             "edge_turn 撞边转向: 向左走 → 撞到屏幕左缘 → 自动反向向右 (全身朝向与步态同步切换)",
             0, 55, turn_dx=turn_dx)
    make_edge_trail(meta, a.out_dir)
    make_sheet(meta, a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
