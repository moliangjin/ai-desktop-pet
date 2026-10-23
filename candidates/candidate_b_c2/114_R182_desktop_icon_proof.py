#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R182 桌面图标"落地证据"渲染器
================================
用途: 把 macOS 真正画在桌面上的那个图标(NSWorkspace.iconForFile_ 取的是 Finder
      自己那份图标资源)渲染成 PNG, 并叠一张"桌面位置示意图"。

为什么不用 screencapture:
    实测本机会话里 `screencapture` 抓不到 Finder 的桌面图标层
    (桌面窗口 layer = -2147483603), 原有 36 个桌面图标在截图里同样不可见,
    所以截图不能作为"图标确实画出来了"的证据。
    NSWorkspace.iconForFile_ 走的是系统图标缓存, 与 Finder 画的是同一份资源。

用法:
    python3 114_R182_desktop_icon_proof.py
输出:
    evidence_r182/桌面图标_渲染_128.png   —— 图标本体(128px)
    evidence_r182/桌面图标_渲染_64.png    —— 图标本体(64px, 与桌面网格同尺寸)
    evidence_r182/桌面位置示意.png         —— 1920x1080 桌面上的位置示意
"""
import os
import sys

from AppKit import (
    NSWorkspace, NSBitmapImageRep, NSGraphicsContext, NSPNGFileType,
    NSMakeRect, NSZeroRect, NSCompositingOperationSourceOver, NSDeviceRGBColorSpace,
    NSColor, NSBezierPath, NSString,
)

CAND = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(CAND, "evidence_r182")
DESKTOP_ITEM = os.path.expanduser("~/Desktop/AI桌宠.app")

# Finder 报告的桌面坐标(逻辑像素, 屏幕 1920x1080)
ICON_POS = (1165, 46)
ICON_BOUNDS = (1133, 14, 1197, 78)
SCREEN = (1920, 1080)


def render_icon(size):
    """按给定边长把系统图标画到一张新 bitmap 上。"""
    ws = NSWorkspace.sharedWorkspace()
    img = ws.iconForFile_(DESKTOP_ITEM)
    if img is None:
        raise SystemExit(f"取不到图标: {DESKTOP_ITEM}")

    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, NSDeviceRGBColorSpace, 0, 0)
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)
    img.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(0, 0, size, size), NSZeroRect, NSCompositingOperationSourceOver, 1.0)
    NSGraphicsContext.restoreGraphicsState()
    return rep


def save(rep, path):
    data = rep.representationUsingType_properties_(NSPNGFileType, None)
    if data is None:
        raise SystemExit(f"PNG 编码失败: {path}")
    data.writeToFile_atomically_(path, True)
    print(f"saved: {path}  ({os.path.getsize(path)} bytes)")


def render_position_schematic(icon_png_path, out_path):
    """把图标按 Finder 给的屏幕坐标贴到 1920x1080 底图上, 直观标出落点。

    用 Pillow 而不是 AppKit 画布 —— AppKit 那条路要把 NSBitmapImageRep 当上下文
    反复 set/restore, 容易静默画空(Pillow 直接合成, 失败会抛异常而不是留白图)。
    """
    from PIL import Image, ImageDraw

    W, H = SCREEN
    img = Image.new("RGB", (W, H), (20, 23, 31))
    d = ImageDraw.Draw(img, "RGBA")

    # 桌面网格(与 Finder 实际网格间距一致: 列 110px / 行 112px)
    for x in range(0, W, 110):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 18), width=1)
    for y in range(0, H, 112):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 18), width=1)

    # 菜单栏
    d.rectangle([0, 0, W, 24], fill=(64, 66, 76))
    d.text((8, 7), "菜单栏", fill=(220, 220, 220))

    # 贴图标(屏幕坐标系 y 向下, Pillow 同向 ⇒ 直接用原坐标)
    icon = Image.open(icon_png_path).convert("RGBA")
    x0, y0, x1, y1 = ICON_BOUNDS
    icon = icon.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    img.paste(icon, (x0, y0), icon)

    # 标注框 + 文字
    d.rectangle([x0 - 5, y0 - 5, x1 + 5, y1 + 5], outline=(255, 115, 25), width=3)
    label = f"AI桌宠.app  pos={ICON_POS[0]},{ICON_POS[1]}"
    d.text((x1 + 14, y0 + 16), label, fill=(255, 160, 70))

    img.save(out_path)
    print(f"saved: {out_path}  ({os.path.getsize(out_path)} bytes)")
    return out_path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.exists(DESKTOP_ITEM):
        raise SystemExit(f"桌面项不存在: {DESKTOP_ITEM}")

    p128 = os.path.join(OUT_DIR, "桌面图标_渲染_128.png")
    p64 = os.path.join(OUT_DIR, "桌面图标_渲染_64.png")
    pmap = os.path.join(OUT_DIR, "桌面位置示意.png")

    save(render_icon(128), p128)
    save(render_icon(64), p64)
    render_position_schematic(p128, pmap)

    print(f"icon position = {ICON_POS}, bounds = {ICON_BOUNDS}, screen = {SCREEN}")


if __name__ == "__main__":
    main()
