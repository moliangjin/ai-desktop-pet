#!/usr/bin/env python3
"""R144 角色资源布局构建器 + R141 裁切回归复现器.

职责:
  1. 逐帧测量 R138 素材 (真实 PNG alpha 通道) 的非透明可见范围 (bbox).
  2. 把测量结果写进运行时 manifest 的 layout 段 (renderer 与测试共用的唯一真源).
  3. 用真实 PNG + 真实 PixiJS 变换公式复现 R141 遗留算法的裁切 (写报告证据).
  4. 用 src/sprite_layout.js (生产布局模块) 核算新算法下 23 帧是否完整显示.

用法:
  python3 08_R144_layout_builder.py            # 构建 + 复现 + 核算, 写证据 JSON
  python3 08_R144_layout_builder.py --check    # 只核算, 不改 manifest
"""

import json
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "assets")
MANIFEST = os.path.join(ASSETS, "character_R141_manifest.json")
EVIDENCE_DIR = os.path.join(HERE, "evidence_r144")

# R144 布局参数 (与 src/sprite_layout.js 的 DEFAULT_MARGIN_PX 保持一致)
MARGIN_PX = 4
MODES = [("compact", 200, 240), ("standard", 256, 256)]


def measure_bboxes(manifest):
    """逐帧测量真实 PNG 的非透明 bbox (PIL getbbox 约定: right/bottom 开区间)."""
    from PIL import Image

    out = {}
    for action, info in manifest["actions"].items():
        boxes = []
        for rel in info["frames"]:
            path = os.path.join(ASSETS, rel)
            if not os.path.exists(path):
                boxes.append(None)
                continue
            with Image.open(path) as im:
                im = im.convert("RGBA")
                bb = im.getchannel("A").getbbox()
                boxes.append(list(bb) if bb else None)
        out[action] = boxes
    return out


def frame_rects(manifest, bboxes):
    """把 bbox 摊平成 sprite_layout.js 需要的 frames 数组."""
    frames = []
    for action, info in manifest["actions"].items():
        boxes = bboxes.get(action) or []
        for i, _rel in enumerate(info["frames"]):
            bb = boxes[i] if i < len(boxes) else None
            frames.append({"action": action, "index": i, "bbox": bb})
    return frames


def node_layout(frames, canvas_w, canvas_h, texture, margin):
    """调用生产布局模块 src/sprite_layout.js 计算布局 (单一真源)."""
    script = os.path.join(HERE, "tools", "r144_layout_probe.js")
    payload = {
        "frames": frames,
        "canvasW": canvas_w,
        "canvasH": canvas_h,
        "textureW": texture,
        "textureH": texture,
        "margin": margin,
    }
    res = subprocess.run(
        ["node", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(f"layout probe failed: {res.stderr.strip()}")
    return json.loads(res.stdout)


def rect_on_screen(rect, layout):
    s = layout["scale"]
    x0 = layout["x"] + (rect["left"] - layout["anchor"]["x"] * layout["textureW"]) * s
    x1 = layout["x"] + (rect["right"] - layout["anchor"]["x"] * layout["textureW"]) * s
    y1 = layout["groundY"]
    y0 = layout["groundY"] - (rect["bottom"] - rect["top"]) * s
    return {"left": x0, "top": y0, "right": x1, "bottom": y1}


def main():
    check_only = "--check" in sys.argv
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    with open(MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    bboxes = measure_bboxes(manifest)
    measured = {a: b for a, b in bboxes.items()}
    missing = [
        f"{a}[{i}]" for a, boxes in bboxes.items() for i, b in enumerate(boxes) if b is None
    ]
    if missing:
        print(f"FATAL: 以下帧无法测量 bbox: {missing}")
        return 2

    # ---- 1. 写回 manifest 的 layout 段 ----
    if not check_only:
        manifest["layout"] = {
            "source": "R144 08_R144_layout_builder.py — 真实 PNG alpha 通道逐帧测量",
            "bbox_convention": "PIL getbbox 约定 [left, top, right, bottom], right/bottom 为开区间, 单位=纹素",
            "margin_px": MARGIN_PX,
            "anchor": {"x": 0.5, "y": 0.9},
            "scale_rule": "全局统一缩放: scale = min over 23 frames of fit; 逐帧禁止改大小",
            "ground_rule": "每帧内容底边贴 canvasH - margin_px (同一地面接触线)",
            "frame_bboxes": measured,
        }
        manifest["version"] = "R144-RUNTIME"
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"manifest layout 已写入: {MANIFEST}")

    # ---- 2. 新算法核算 (生产布局模块) ----
    texture = manifest["canvas_px"][0]
    frames = frame_rects(manifest, measured)
    new_results = {}
    for mode, w, h in MODES:
        layout = node_layout(frames, w, h, texture, MARGIN_PX)
        per_action = {}
        clipped_total = 0
        worst = None
        for fr in frames:
            a = fr["action"]
            i = fr["index"]
            bb = fr["bbox"]
            rect = {"left": bb[0], "top": bb[1], "right": bb[2], "bottom": bb[3]}
            scr = rect_on_screen(rect, layout)
            out_left = max(0.0, layout["margin"] - scr["left"])
            out_top = max(0.0, layout["margin"] - scr["top"])
            out_right = max(0.0, scr["right"] - (layout["canvasW"] - layout["margin"]))
            out_bottom = max(0.0, scr["bottom"] - (layout["canvasH"] - layout["margin"]))
            overflow = out_left + out_top + out_right + out_bottom
            if overflow > 0.001:
                clipped_total += 1
            if worst is None or overflow > worst["overflow"]:
                worst = {"action": a, "index": i, "overflow": round(overflow, 4)}
            per_action.setdefault(a, []).append(
                {
                    "index": i,
                    "src_bbox": bb,
                    "screen_rect": {k: round(v, 3) for k, v in scr.items()},
                    "overflow_px": round(overflow, 4),
                }
            )
        new_results[mode] = {
            "canvas": {"w": w, "h": h},
            "scale": round(layout["scale"], 6),
            "groundY": layout["groundY"],
            "frames_total": len(frames),
            "frames_clipped": clipped_total,
            "worst": worst,
            "per_action": per_action,
        }
        print(
            f"[{mode} {w}x{h}] 新算法 scale={layout['scale']:.6f} groundY={layout['groundY']} "
            f"裁切帧={clipped_total}/{len(frames)}"
        )

    # ---- 3. R141 遗留算法复现 (证明旧参数确实裁切) ----
    legacy = {}
    for mode, w, h in MODES:
        # R141: anchor(0.5,0.9), y=h, sc = compact ? w/canvas : 1.0
        sc = (w / texture) if mode == "compact" else 1.0
        ax, ay = 0.5, 0.9
        px, py = w / 2, h
        per_action = {}
        for fr in frames:
            bb = fr["bbox"]
            x0 = px + (bb[0] - ax * texture) * sc
            x1 = px + (bb[2] - ax * texture) * sc
            y0 = py + (bb[1] - ay * texture) * sc
            y1 = py + (bb[3] - ay * texture) * sc
            # 可见区 = [0,w]x[0,h]
            ox = max(0.0, -x0) + max(0.0, x1 - w)
            oy = max(0.0, -y0) + max(0.0, y1 - h)
            per_action.setdefault(fr["action"], []).append(
                {
                    "index": fr["index"],
                    "screen_rect": {"left": round(x0, 2), "top": round(y0, 2), "right": round(x1, 2), "bottom": round(y1, 2)},
                    "overflow_px": round(ox + oy, 2),
                    "clip_ratio_estimate": round((ox + oy) / max(1.0, (x1 - x0) + (y1 - y0)), 6),
                }
            )
        legacy[mode] = {
            "canvas": {"w": w, "h": h},
            "scale": sc,
            "anchor": {"x": ax, "y": ay},
            "position": {"x": px, "y": py},
            "per_action": per_action,
        }
        print(f"[{mode} {w}x{h}] R141 遗留算法 scale={sc} — 见 evidence 逐帧越界像素")

    evidence = {
        "round": "R144",
        "generated_by": "08_R144_layout_builder.py",
        "manifest": os.path.relpath(MANIFEST, ROOT),
        "canvas_px": manifest["canvas_px"],
        "margin_px": MARGIN_PX,
        "measured_frame_bboxes": measured,
        "r144_layout": new_results,
        "r141_legacy_repro": legacy,
    }
    out_path = os.path.join(EVIDENCE_DIR, "render_bounds_r144.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print(f"证据: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
