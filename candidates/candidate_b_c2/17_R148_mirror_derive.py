#!/usr/bin/env python3
"""R148: 由**已确认方向正确**的 walk_left 步态派生 walk_right 帧 (整体水平镜像 + 徽章归位)。

背景 (R148 用户真机截图确认 walk_right 仍倒着走):
    R138 的 walk_left / walk_right 都是**正面 3/4 立绘**, 脚尖方向本身不携带行进信息;
    实测两组步态的"抬脚腿序列"几乎相同, 且 walk_right 与 walk_left 的落脚/鞋尖朝向
    指向同一侧 → 向右移动时看起来在倒退。

R148 方案 (任务书授权: "优先尝试对已确认的正确步态进行整体水平镜像"):
    1. 源素材 = walk_left 4 帧 (R147 已确认其迈步方向正确)
    2. **整体水平镜像** (整幅纹理翻转, 绝不单独镜像腿部)
    3. 镜像会把胸口那枚**烧瓶徽章**翻到角色另一侧胸 (且图形左右颠倒) →
       做**局部资产修复**:
         · 抹掉镜像后残留在另一侧的"镜像徽章" (调和扩散 inpaint, 不破坏外衣衣褶)
         · 把徽章按**原样 (不镜像)** 搬回角色**自己的左胸** (观者右侧)
    4. 原始 R138 的 23 帧**一个字节都不改**, 派生帧写入新目录 character_R138_derived/。

输出:
    assets/character_R138_derived/walk_right_mirror/walk_right_m_0{0..3}.png
    assets/character_R138_derived/walk_right_mirror/derive_report.json
"""
import json
import os
import sys
import argparse
import hashlib

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
SRC_DIR = os.path.join(ASSETS, 'character_R138', 'walk_left')
OUT_DIR = os.path.join(ASSETS, 'character_R138_derived', 'walk_right_mirror')

# 源帧 (walk_left = 已确认方向正确的那一组)
SRC_FILES = [
    'walk_left_00_stand.png',
    'walk_left_01_left_step.png',
    'walk_left_02_pass.png',
    'walk_left_03_right_step.png',
]
OUT_FILES = [
    'walk_right_m_00.png',
    'walk_right_m_01.png',
    'walk_right_m_02.png',
    'walk_right_m_03.png',
]

# 模板来源: idle 站姿 (无手臂遮挡), 用于在每个行走帧里定位胸口徽章
TEMPLATE_FILE = os.path.join(ASSETS, 'character_R138', 'idle', 'idle_00_base.png')
# 徽章包围盒 (纹理坐标) —— 必须**只框住烧瓶图标本身**, 不能框到外衣的深色衣褶线
TEMPLATE_BOX = (540, 370, 582, 416)
SEARCH_BOX = (500, 320, 640, 450)     # 在行走帧里搜索徽章的范围

INK_THRESHOLD = 14.0                   # 判定"墨迹"(描边+柔影) 的亮度差阈值
FEATHER_RADIUS = 5                      # 羽化半径 (纹理像素)
FEATHER_GAIN = 1.35                     # 羽化增益 (保证墨迹核心不透明)
INPAINT_ITERS = 400                    # 调和扩散迭代次数


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def ncc_locate(img, template, search):
    """在 img 里用归一化互相关定位 template (灰度), 返回 (x0, y0, score)。"""
    g = np.asarray(img.convert('L'), dtype=np.float64)
    t = np.asarray(template.convert('L'), dtype=np.float64)
    th, tw = t.shape
    sx0, sy0, sx1, sy1 = search
    best = (-2.0, sx0, sy0)
    t_c = t - t.mean()
    t_n = np.sqrt((t_c ** 2).sum())
    if t_n < 1e-6:
        return sx0, sy0, 0.0
    for y in range(sy0, sy1 - th + 1):
        for x in range(sx0, sx1 - tw + 1):
            w = g[y:y + th, x:x + tw]
            w_c = w - w.mean()
            w_n = np.sqrt((w_c ** 2).sum())
            if w_n < 1e-6:
                continue
            v = float((w_c * t_c).sum() / (w_n * t_n))
            if v > best[0]:
                best = (v, x, y)
    return best[1], best[2], best[0]


def local_bright(lum, r=4):
    """灰度形态学膨胀: 取 r 窗口内的最大亮度 → 近似"忽略细描边的外衣亮度"。"""
    padded = np.pad(lum, r, mode='edge')
    bg = np.full_like(lum, -1e9)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            np.maximum(bg, padded[dy:dy + lum.shape[0], dx:dx + lum.shape[1]], out=bg)
    return bg


def inpaint_harmonic(rgb, mask, iters=INPAINT_ITERS):
    """调和扩散填充: 被 mask 标记的像素用四邻域均值迭代逼近边界颜色 (无缝、无涂抹条纹)。"""
    if not mask.any():
        return rgb.copy()
    out = rgb.copy()
    # 初值: 用最近的有效像素粗填, 加快收敛
    valid = ~mask
    if valid.any():
        ys, xs = np.nonzero(valid)
        for k, (yy, xx) in enumerate(zip(ys, xs)):
            pass
        # 简单初值: 全局有效像素均值
        out[mask] = rgb[valid].mean(axis=0)
    for _ in range(iters):
        up = np.vstack([out[:1], out[:-1]])
        down = np.vstack([out[1:], out[-1:]])
        left = np.hstack([out[:, :1], out[:, :-1]])
        right = np.hstack([out[:, 1:], out[:, -1:]])
        avg = (up + down + left + right) * 0.25
        out[mask] = avg[mask]
    return out


def split_emblem(rgb, box):
    """把胸口徽章从 rgb 中分离。

    返回 (ink_alpha, ink_rgb, clean_rgb):
        ink_alpha : 墨迹覆盖率 0..1 (描边 + 柔影)
        ink_rgb   : 徽章原像素颜色
        clean_rgb : 去掉徽章后的干净外衣颜色 (调和扩散补回)
    """
    x0, y0, x1, y1 = box
    patch = rgb[y0:y1, x0:x1].astype(np.float64)
    lum = patch.mean(axis=2)
    bg = local_bright(lum)
    diff = bg - lum
    ink = np.clip(diff / 55.0, 0.0, 1.0)
    ink[diff < INK_THRESHOLD] = 0.0
    # 墨迹颜色: 原像素 (保持描边的深色与柔影的灰度)
    ink_rgb = patch.copy()
    # 干净外衣: 调和扩散
    mask = diff > INK_THRESHOLD
    clean = inpaint_harmonic(patch, mask)
    return ink, ink_rgb, clean


def feather(mask, radius=5, gain=1.35):
    """墨迹掩膜 → 羽化权重 (核心 1, 向外平滑衰减到 0), 避免硬贴产生矩形接缝。"""
    m = Image.fromarray((mask.astype(np.uint8) * 255), 'L')
    m = m.filter(ImageFilter.GaussianBlur(radius=radius))
    w = np.asarray(m).astype(np.float64) / 255.0
    w = np.clip(w * gain, 0.0, 1.0)
    return w


def derive_one(src_path, template, out_path):
    src = Image.open(src_path).convert('RGBA')
    a = np.asarray(src).astype(np.int16)
    rgb = a[:, :, :3]
    alpha = a[:, :, 3]

    tx, ty, score = ncc_locate(src, template, SEARCH_BOX)
    box = (tx, ty,
           tx + (TEMPLATE_BOX[2] - TEMPLATE_BOX[0]),
           ty + (TEMPLATE_BOX[3] - TEMPLATE_BOX[1]))
    ink, ink_rgb, clean_rgb = split_emblem(rgb, box)

    # ---- 1. 整体水平镜像 (整幅纹理, 含 alpha) ----
    mir_rgb = rgb[:, ::-1].copy()
    mir_alpha = alpha[:, ::-1].copy()
    W = rgb.shape[1]
    cx0, cy0, cx1, cy1 = box
    mcx0, mcy0, mcx1, mcy1 = (W - cx1, cy0, W - cx0, cy1)

    # ---- 2. 抹掉镜像后残留在另一侧的"镜像徽章" ----
    # 关键: 在**镜像图自己**上做调和扩散修补 (而不是贴源图的外衣) ——
    #       这样保留镜像外衣自身的着色, 不会出现亮度错位导致的"淡影/鬼影"。
    ink_mask = (ink > 0.02)
    w = feather(ink_mask, radius=FEATHER_RADIUS, gain=FEATHER_GAIN)
    w_b = w[:, ::-1]
    tgt_b = mir_rgb[mcy0:mcy1, mcx0:mcx1].astype(np.float64)
    clean_b = inpaint_harmonic(tgt_b, ink_mask[:, ::-1])   # 就地修补镜像图
    blended_b = tgt_b * (1 - w_b[:, :, None]) + clean_b * w_b[:, :, None]
    mir_rgb[mcy0:mcy1, mcx0:mcx1] = np.clip(blended_b, 0, 255).astype(np.int16)

    # ---- 3. 把徽章按原样搬回角色自己的左胸 (观者右侧) ----
    # 只把徽章的**墨迹**按原样搬过来 (羽化混合), 徽章不镜像、也不带来源图的亮度偏差
    tgt_a = mir_rgb[cy0:cy1, cx0:cx1].astype(np.float64)
    src_a = rgb[cy0:cy1, cx0:cx1].astype(np.float64)
    # 亮度对齐: 外衣在"源图"与"镜像图"两处本就存在轻微着色差 (褶皱/阴影不对称),
    #   直接融合会在羽化边缘留下一圈亮度阶跃 → 用非墨迹区的均值差先对齐再融合。
    non_ink = ~ink_mask
    if non_ink.sum() > 10:
        delta = (tgt_a[non_ink].mean(axis=0) - src_a[non_ink].mean(axis=0))
        src_a = src_a + delta
    blended_a = tgt_a * (1 - w[:, :, None]) + src_a * w[:, :, None]
    mir_rgb[cy0:cy1, cx0:cx1] = np.clip(blended_a, 0, 255).astype(np.int16)

    out = np.dstack([mir_rgb, mir_alpha[:, :, None]]).astype(np.uint8)
    Image.fromarray(out, 'RGBA').save(out_path)
    return {
        'src': os.path.relpath(src_path, CAND),
        'out': os.path.relpath(out_path, CAND),
        'emblem_box': list(box),
        'emblem_ncc': round(float(score), 4),
        'ink_pixels': int(ink_mask.sum()),
        'bbox': list(Image.fromarray(out, 'RGBA').getbbox()),
        'sha256': sha256(out_path),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=OUT_DIR)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    template = Image.open(TEMPLATE_FILE).convert('RGBA').crop(TEMPLATE_BOX)
    report = {
        'round': 'R148',
        'strategy': 'mirror(confirmed-correct walk_left) + emblem re-seat',
        'emblem_template_box': list(TEMPLATE_BOX),
        'source_dir': os.path.relpath(SRC_DIR, CAND),
        'frames': [],
    }
    for src_name, out_name in zip(SRC_FILES, OUT_FILES):
        src = os.path.join(SRC_DIR, src_name)
        out = os.path.join(a.out_dir, out_name)
        info = derive_one(src, template, out)
        report['frames'].append(info)
        print(f"  ✅ {out_name}  emblem_box={info['emblem_box']} ncc={info['emblem_ncc']} "
              f"ink={info['ink_pixels']}px bbox={info['bbox']}")
    rep = os.path.join(a.out_dir, 'derive_report.json')
    with open(rep, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  📄 {rep}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
