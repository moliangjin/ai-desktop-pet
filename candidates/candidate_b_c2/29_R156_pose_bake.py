#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R156 姿态烘焙器 (v2) — 派生点击互动 6 动作 (每个 3 帧) + 办公 2 帧。

R153 的三种技法 (复用 22_R153_pose_bake.py, 不重复实现):
  A. 眼睛区域合成      face_swap
  B. 头部连续权重场弯曲 head_transform
  C. 胸口软遮罩微缩    torso_breath

R156 新增的四种技法 (本文件):
  D. 整体垂直平移 + 支点缩放  body_shift   → 跳跃蓄力/腾空/落地
  E. 整体水平压缩 (中轴支点)   body_narrow  → 2D "变窄 = 正在转身"
  F. 上半身连续权重场前倾      torso_lean   → 办公看屏幕/思考
  G. 整体水平平移              body_shift_x → 开心摇摆 (身体左右摆)

硬约束 (R156 任务书):
  · 身份不漂移: 全部基于 R138/R153 既有帧做局部处理, 不重画角色
  · 不靠"重命名/重复播放/整体旋转/强行缩放"虚增动作数
  · 每个点击动作都有 **开始/中间/结束** 三帧 (不是单张定格)
  · 做不到的动作 (真正的双手比心手势/挥手/敲键盘手部) 如实标注, 不硬凑

素材边界 (必须写进报告, 不能硬标 PASS):
  · R138 素材的角色轮廓在纹理里占 y=37~987, 头顶只剩 37px 余量。
    ⇒ 腾空帧最多只能离地 34 纹理 px (≈6.7 屏幕 px)。
    "跳" 的可读性主要靠 蓄力下蹲 → 伸展腾空 → 落地压缩 的剪影对比,
    真正的"跳起离地"需要重新绘制带留白的原画 (列入"需要新素材")。
"""
import importlib.util
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')
OUT = os.path.join(ASSETS, 'character_R156')

# ---- 复用 R153 烘焙器的工具函数 ----
_spec = importlib.util.spec_from_file_location(
    'r153_bake', os.path.join(CAND, '22_R153_pose_bake.py'))
_r153 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_r153)

load = _r153.load
to_np = _r153.to_np
to_im = _r153.to_im
dilate = _r153.dilate
face_swap = _r153.face_swap
head_transform = _r153.head_transform
torso_breath = _r153.torso_breath
bilinear_sample = _r153.bilinear_sample
smoothstep = _r153.smoothstep

BASE = os.path.join(R138, 'idle', 'idle_00_base.png')
ARMS_UP = os.path.join(R138, 'idle', 'idle_01_inhale_peak.png')
HAND_CHEST = os.path.join(R138, 'idle', 'idle_04_blink_half.png')
CLOSED_SMILE = os.path.join(R138, 'idle', 'idle_05_blink_closed.png')
HALF_BLINK = os.path.join(R138, 'idle', 'idle_04_blink_half.png')
SIT = os.path.join(R138, 'sleep_enter', 'sleep_enter_01_sit.png')

# 角色几何 (纹理坐标, 实测)
FOOT_Y = 987          # 站姿脚底
BODY_AXIS_X = 512     # 身体中轴
SIT_HIP_Y = 700       # 坐姿臀部/座面接触线
SIT_AXIS_X = 530      # 坐姿身体中轴
HEAD_TOP_Y = 37       # 站姿头顶 (纹理余量只有 37px)

# ----------------------------------------------------------------------
# R167 办公场景: 角色要真的坐在桌后、手压在键盘上 ⇒ 必须解决 z 序。
#
# 【为什么必须剪掉下半身】
#   渲染顺序是 back 道具 → 角色 → front 道具。台面 (prop_desk_surface) 在
#   back 层, 而角色的**大腿正好压在台面带上** ⇒ 台面被她的腿整片挡住,
#   键盘根本没法出现在她手下 (R165 真机看到的就是"手搭在腿上")。
#   ⇒ 把 CUT_Y 以下的身体剪掉, 台面就能从她腰部开始露出来, 双手正好落在
#     台面上 ⇒ 读作"她坐在桌后、双手压在键盘上"。
#   保留区 = 两只手 + 两个腕带 (它们要留在键盘上)。
# ----------------------------------------------------------------------
WORK_CUT_Y = 592
WORK_KEEP = [
    (368, 528, 448, 602),    # L 腕带
    (326, 550, 430, 656),    # L 手
    (490, 528, 568, 608),    # R 腕带
    (430, 548, 556, 656),    # R 手
]
# 双手在键盘上的"按键"位移 (纹理 px): 一帧按下、一帧抬起
WORK_PRESS = {'work_1': 17, 'work_2': 0}


def cut_lower_body(im, cut_y=WORK_CUT_Y, keep=WORK_KEEP):
    """把 cut_y 以下的身体剪掉, 但保留 keep 矩形里的像素 (双手 + 腕带)。"""
    a = np.asarray(im).copy()
    keepm = np.zeros(a.shape[:2], bool)
    for (x0, y0, x1, y1) in keep:
        keepm[y0:y1, x0:x1] = True
    kill = np.zeros(a.shape[:2], bool)
    kill[cut_y:, :] = True
    a[kill & ~keepm] = 0
    return Image.fromarray(a, 'RGBA')


def _skin_mask(rgb):
    """坐姿帧的肤色判定 (与 67_R167_diag_sit_arms.py 同一套口径)。"""
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    return (r > 195) & (g > 140) & (g < 205) & (b > 110) & (b < 185) & (r > b + 35)


def _hand_region(reg):
    """手的**实心**区域: 肤色 + 手指暗线 + 手的外描边 (不含腕带/袖子/裤子)。

    R167 踩坑: 第一版用"肤色 + 2px 暗环"取手 ⇒ 手指的暗线只被抓到一部分,
    一平移手指就碎成虚线。第二版改成"**排除青色与白色**"的实心掩膜:
    腕带(青) / 袖子(白) / 裤子(青) 都被排除, 剩下的就是手的皮肤 + 全部暗线,
    平移时是一个**整体**, 不会出现断线。
    """
    rgb = reg[:, :, :3]
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    teal = (b > r + 12) & (g > r + 4)
    white = (r > 196) & (g > 196) & (b > 196)
    opaque = reg[:, :, 3] > 40
    sk = _skin_mask(rgb) & opaque
    return (~teal) & (~white) & opaque & dilate(sk, 6)


def _cuff_color(im, box):
    """取腕带 (青色饰条) 的代表色 —— 按键位移后用它补被顶长的袖口。"""
    x0, y0, x1, y1 = box
    a = np.asarray(im.convert('RGBA'))
    reg = a[y0:y1, x0:x1]
    r = reg[:, :, 0].astype(np.int16)
    g = reg[:, :, 1].astype(np.int16)
    b = reg[:, :, 2].astype(np.int16)
    teal = (b > r + 12) & (g > r + 4) & (reg[:, :, 3] > 120)
    if not teal.any():
        return (150, 205, 214, 255)
    px = reg[teal][:, :3]
    med = np.median(px, axis=0).astype(int)
    return (int(med[0]), int(med[1]), int(med[2]), 255)


def hand_press(im, box, dy, cuff_rgb):
    """把一只手整体下移 dy 纹理 px (模拟"手指按下")。

    做法:
      1. 取手的肤色块 + 紧贴的暗描边 → 整块平移;
      2. 原位置腾出的那一条用**腕带的青色**补上 (腕带本来就紧贴手背) ⇒ 看起来
         是手压下去、袖口被顶长, 而不是手从袖子里滑出来;
      3. **手的上边界描边必须跟着一起下移** —— 否则腕口的黑描边留在原地,
         手上会出现一道"断线 + 青色糊边" (R167 第一版就是这么坏的)。
         所以先记住上边界那一行的暗像素, 平移后补到新的上边界。
    """
    if dy == 0:
        return im
    x0, y0, x1, y1 = box
    a = np.asarray(im).copy()
    reg = a[y0:y1, x0:x1]
    m = _hand_region(reg)
    if not m.any():
        return im
    patch = reg.copy()
    patch[~m] = 0
    rows = np.nonzero(m.any(axis=1))[0]
    top = int(rows.min())
    # 手的上边界那一行 (含黑描边) —— 之后要跟着手下移
    edge_row = reg[top, :, :].copy()
    edge_dark = (edge_row[:, :3].mean(axis=1) < 130) & (edge_row[:, 3] > 40)
    # 腾出的那一条用腕带青色补上 (腕口被顶长)
    strip = m[top:top + dy, :]
    band = reg[top:top + dy, :, :]
    reg[top:top + dy, :, :] = np.where(
        strip[:, :, None], np.array(cuff_rgb, dtype=reg.dtype), band)
    # 平移手 (整块, 含手指暗线与外描边)
    shifted = np.zeros_like(reg)
    shifted[dy:, :, :] = patch[:-dy, :, :]
    keep = shifted[:, :, 3] > 0
    reg[keep] = shifted[keep]
    # 把上边界描边补到新的位置 (腕口的黑线跟着手走)
    nrow = top + dy
    if nrow < reg.shape[0]:
        row = reg[nrow, :, :]
        reg[nrow, :, :] = np.where(edge_dark[:, None], edge_row, row)
    a[y0:y1, x0:x1] = reg
    return Image.fromarray(a, 'RGBA')


# ======================================================================
# D. 整体垂直平移 + 支点缩放 (跳跃 / 缓冲)
# ======================================================================
def body_shift(src_path, out_path, shift_up=0.0, scale_y=1.0, pivot_y=FOOT_Y, tag=''):
    """整体垂直平移 (shift_up>0 = 向上) + 以 pivot_y 为支点的垂直缩放。

    逆映射 (输出 → 输入):
        src_y = pivot_y + (y - pivot_y)/scale_y + shift_up
    """
    im = load(src_path)
    W, H = im.size
    a = to_np(im)
    yy, xx = np.mgrid[0:H, 0:W]
    src_y = pivot_y + (yy - pivot_y) / scale_y + shift_up
    src_y = np.clip(src_y, 0, H - 1.001)
    out = bilinear_sample(a, xx.astype(np.float64), src_y)
    res = to_im(out)
    res.save(out_path)
    return {'file': os.path.basename(out_path), 'source': os.path.basename(src_path),
            'technique': 'body_shift',
            'transform': {'shift_up': shift_up, 'scale_y': scale_y, 'pivot_y': pivot_y},
            'bbox': list(res.getbbox()),
            'note': '整体垂直平移 + 脚底支点缩放 (跳跃/缓冲), 未旋转未整体缩放'}


# ======================================================================
# E. 整体水平压缩 (中轴为支点) — 2D "转身"表现
# ======================================================================
def body_narrow(src_path, out_path, scale_x=1.0, pivot_x=BODY_AXIS_X, tag=''):
    """以身体中轴为支点做水平压缩 (角色"变窄"= 正在转身的经典 2D 表现)。"""
    im = load(src_path)
    W, H = im.size
    a = to_np(im)
    yy, xx = np.mgrid[0:H, 0:W]
    src_x = pivot_x + (xx - pivot_x) / scale_x
    src_x = np.clip(src_x, 0, W - 1.001)
    out = bilinear_sample(a, src_x, yy.astype(np.float64))
    res = to_im(out)
    res.save(out_path)
    return {'file': os.path.basename(out_path), 'source': os.path.basename(src_path),
            'technique': 'body_narrow',
            'transform': {'scale_x': scale_x, 'pivot_x': pivot_x},
            'bbox': list(res.getbbox()),
            'note': '以身体中轴为支点的水平压缩 (2D 转身表现手法), 非整体旋转'}


# ======================================================================
# G. 整体水平平移 (开心摇摆)
# ======================================================================
def body_shift_x(src_path, out_path, dx=0.0, tag=''):
    """整体水平平移 (dx>0 = 向右)。角色轮廓不变, 只是位置变 —— 读作"扭一下"。"""
    im = load(src_path)
    W, H = im.size
    a = to_np(im)
    yy, xx = np.mgrid[0:H, 0:W]
    src_x = np.clip(xx - dx, 0, W - 1.001)
    out = bilinear_sample(a, src_x, yy.astype(np.float64))
    res = to_im(out)
    res.save(out_path)
    return {'file': os.path.basename(out_path), 'source': os.path.basename(src_path),
            'technique': 'body_shift_x',
            'transform': {'dx': dx},
            'bbox': list(res.getbbox()),
            'note': '整体水平平移 (身体左右摆动), 未旋转未缩放'}


# ======================================================================
# F. 上半身连续权重场前倾 (办公看屏幕)
# ======================================================================
def torso_weight(W, H, shoulder_y=300, hip_y=700, axis_x=SIT_AXIS_X):
    """上半身权重场: 肩部以上=1 (刚性前倾), 髋部=0 (固定)。"""
    yy, xx = np.mgrid[0:H, 0:W]
    w = 1.0 - smoothstep(shoulder_y, hip_y, yy)
    hip = np.exp(-(((xx - axis_x) / 150.0) ** 2 + ((yy - hip_y) / 70.0) ** 2))
    w = w * (1.0 - 0.9 * hip)
    return np.clip(w, 0.0, 1.0)


def torso_lean(src_path, out_path, angle=10.0, pivot=(SIT_AXIS_X, SIT_HIP_Y),
               shoulder_y=300, hip_y=700, tag=''):
    """上半身绕髋部支点前倾 (连续权重场, 无切口/无空洞)。"""
    im = load(src_path)
    W, H = im.size
    a = to_np(im)
    yy, xx = np.mgrid[0:H, 0:W]
    w = torso_weight(W, H, shoulder_y, hip_y, pivot[0])
    th = np.deg2rad(angle) * w
    px, py = pivot
    dxo, dyo = xx - px, yy - py
    cth, sth = np.cos(th), np.sin(th)
    sx = px + (cth * dxo + sth * dyo)
    sy = py + (-sth * dxo + cth * dyo)
    out = bilinear_sample(a, sx.astype(np.float64), sy.astype(np.float64))
    res = to_im(out)
    res.save(out_path)
    return {'file': os.path.basename(out_path), 'source': os.path.basename(src_path),
            'technique': 'torso_lean',
            'transform': {'angle': angle, 'pivot': list(pivot),
                          'shoulder_y': shoulder_y, 'hip_y': hip_y},
            'bbox': list(res.getbbox()),
            'note': '上半身连续权重场绕髋部前倾 (连续场, 无切口/无空洞), 下半身固定'}


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {'round': 'R156',
           'techniques': ['face_swap', 'head_transform', 'body_shift', 'body_narrow',
                          'body_shift_x', 'torso_lean'],
           'notes': ['复用 R153 烘焙器的 face_swap / head_transform / torso_breath',
                     '新增 body_shift (垂直平移+支点缩放) / body_narrow (水平压缩) / '
                     'body_shift_x (水平平移) / torso_lean (上身前倾)'],
           'material_limits': [
               'R138 无手部素材 → 比心=手贴胸近似, 双手庆祝=双臂抬起近似, 办公无"敲键盘"手部动作',
               '"腾空离地"由运行时的 ground_offset_px 实现 (整帧抬离地面线), 不是把角色在纹理里挪动; '
               'R138 素材头顶只剩 37px 余量, 纹理内挪动最多只能离地 7 屏幕 px, 抬升幅度不够',
               '"原地转身"是 2D 表现手法 (正面→水平压缩 64% 读作侧身→回正), 不是真正的 180° 背面转身 (R138 无背面素材)',
           ],
           'items': []}

    def emit(info):
        rep['items'].append(info)
        print(f"  ✅ {info['file']:26s} {info.get('note','')}")

    def p(name):
        return os.path.join(OUT, name)

    def tmp(name):
        return os.path.join(OUT, '_tmp_' + name)

    print("R156 姿态烘焙 v2 (基于 R138/R153 既有帧的局部处理):")

    # ================= 1. 比心 (手贴胸 + 笑) — 近似手势 =================
    # f0 起势: 站立闭眼笑 (期待)  |  f1 高点: 手贴胸+闭眼笑  |  f2 收势: 手贴胸+睁眼
    emit(face_swap(HAND_CHEST, CLOSED_SMILE, p('cheer_heart_1.png'), tag='手贴胸'))
    # 睁眼版用 idle_00 的眼睛做 donor (idle_04 本身就是"半闭眼", 不能自比)
    emit(face_swap(HAND_CHEST, BASE, p('cheer_heart_2.png'), tag='手贴胸睁眼'))
    # f0 起势: 微微歪头 + 闭眼笑。
    #   注意: 单纯 face_swap(BASE, CLOSED_SMILE) 会与 R153 的 blink_closed.png **字节相同**
    #   (R153 用的也是 BASE + CLOSED_SMILE) —— 那是"重复播放既有素材", 不算新动作。
    #   加一个 -6° 的头部连续权重场弯曲后, 画面才真正属于 R156。
    emit(head_transform(BASE, tmp('heart0.png'), rotate=-6.0, tag='起势歪头'))
    emit(face_swap(tmp('heart0.png'), CLOSED_SMILE, p('cheer_heart_0.png'), tag='起势闭眼笑'))
    os.remove(tmp('heart0.png'))

    # ================= 2. 开心小跳 =================
    # f0 蓄力下蹲 (压扁 12%) → f1 腾空 (伸展 + 离地 + 闭眼笑) → f2 落地压缩
    # 注意: "离地" **不是**靠把角色在纹理里往上挪 (R138 素材头顶只剩 37px 余量, 挪不动),
    #       而是靠运行时的 ground_offset_px (地面偏移) 把整帧抬离地面线。
    #       所以腾空帧的纹理必须是**完整身高**的帧, 离地量全部由 manifest 声明。
    emit(body_shift(BASE, p('cheer_jump_0.png'),
                    shift_up=0, scale_y=0.86, pivot_y=FOOT_Y, tag='蓄力下蹲'))
    # 腾空帧同样不能直接用 face_swap(BASE, CLOSED_SMILE) (会与 R153 blink_closed 字节相同),
    # 这里叠加"抬头 +5°/上移 3px"的头部连续权重场, 读作腾空时仰头大笑。
    emit(head_transform(BASE, tmp('jump_air.png'), dy=-3.0, rotate=5.0, tag='腾空仰头'))
    emit(face_swap(tmp('jump_air.png'), CLOSED_SMILE, p('cheer_jump_1.png'), tag='腾空闭眼笑'))
    os.remove(tmp('jump_air.png'))
    emit(body_shift(BASE, p('cheer_jump_2.png'),
                    shift_up=0, scale_y=0.88, pivot_y=FOOT_Y, tag='落地缓冲'))

    # ================= 3. 原地轻盈转身 (正面 → 侧身 → 回正) =================
    emit(head_transform(BASE, p('cheer_spin_0.png'), rotate=8.0, tag='起转'))
    emit(body_narrow(BASE, tmp('spin_side.png'), scale_x=0.64, pivot_x=BODY_AXIS_X, tag='侧身'))
    emit(head_transform(tmp('spin_side.png'), p('cheer_spin_1.png'), rotate=14.0, tag='侧身转头'))
    os.remove(tmp('spin_side.png'))
    emit(body_narrow(BASE, tmp('spin_back.png'), scale_x=0.82, pivot_x=BODY_AXIS_X, tag='转回'))
    emit(head_transform(tmp('spin_back.png'), p('cheer_spin_2.png'), rotate=5.0, tag='转回转头'))
    os.remove(tmp('spin_back.png'))

    # ================= 4. 歪头眨眼卖萌 (开始/中间/结束) =================
    # 角度用 ±14°/7° (避开 R153 head_tilt 的 ±11° —— 用同样的角度会得到**字节相同**的帧)
    emit(head_transform(BASE, p('cheer_wink_0.png'), rotate=14.0, tag='歪头'))
    emit(head_transform(BASE, tmp('wink.png'), rotate=14.0, tag='歪头'))
    emit(face_swap(tmp('wink.png'), HALF_BLINK, p('cheer_wink_1.png'), tag='歪头'))
    os.remove(tmp('wink.png'))
    emit(head_transform(BASE, tmp('wink2.png'), rotate=7.0, tag='轻歪头'))
    emit(face_swap(tmp('wink2.png'), CLOSED_SMILE, p('cheer_wink_2.png'), tag='轻歪头'))
    os.remove(tmp('wink2.png'))

    # ================= 5. 双手小庆祝 (举手 → 大笑 → 举手下沉) =================
    emit(head_transform(ARMS_UP, tmp('hands0.png'), rotate=7.0, tag='举手期待'))
    emit(face_swap(tmp('hands0.png'), HALF_BLINK, p('cheer_hands_0.png'), tag='举手期待'))
    os.remove(tmp('hands0.png'))
    emit(face_swap(ARMS_UP, CLOSED_SMILE, p('cheer_hands_1.png'), tag='举手大笑'))
    emit(body_shift(p('cheer_hands_1.png'), p('cheer_hands_2.png'),
                    shift_up=0, scale_y=0.96, pivot_y=FOOT_Y, tag='举手下沉'))

    # ================= 6. 开心摇摆 (身体左 → 右 → 回正) =================
    emit(body_shift_x(BASE, tmp('sway_l.png'), dx=-46.0, tag='左摆'))
    emit(head_transform(tmp('sway_l.png'), p('cheer_sway_0.png'), rotate=8.0, tag='左摆歪头'))
    os.remove(tmp('sway_l.png'))
    emit(body_shift_x(BASE, tmp('sway_r.png'), dx=46.0, tag='右摆'))
    emit(head_transform(tmp('sway_r.png'), p('cheer_sway_1.png'), rotate=-8.0, tag='右摆歪头'))
    os.remove(tmp('sway_r.png'))
    emit(head_transform(BASE, tmp('sway_c.png'), rotate=2.0, tag='回正'))
    emit(face_swap(tmp('sway_c.png'), CLOSED_SMILE, p('cheer_sway_2.png'), tag='回正笑'))
    os.remove(tmp('sway_c.png'))

    # ================= 7. 办公看屏幕 (R167: 双手真的按在键盘上) =================
    # R167 改动 (对应用户 R167 反馈: "角色双手仍没有真正操作键盘" /
    #             "增加轻微、自然的打字动作" / "在 200×240 下一眼看出在办公"):
    #   · 剪掉下半身 (cut_lower_body): 台面在 back 层, 原本被角色的大腿整片挡住,
    #     键盘压根没地方出现 ⇒ 剪掉后台面从腰部露出, 双手正好落在键盘上;
    #   · 双手"按键盘" (hand_press): work_1 按下 / work_2 抬起 ⇒ 打字的轻微动作;
    #   · work_1 = 低头看键盘 (在打字), work_2 = 抬头看屏幕 (打字间隙的思考)。
    sit_cut = cut_lower_body(Image.open(SIT).convert('RGBA'))
    sit_cut_path = tmp('sit_cut.png')
    sit_cut.save(sit_cut_path)
    cuff_l = _cuff_color(sit_cut, (372, 534, 446, 600))
    cuff_r = _cuff_color(sit_cut, (494, 534, 566, 604))

    w1 = hand_press(sit_cut, (326, 550, 430, 656), WORK_PRESS['work_1'], cuff_l)
    w1 = hand_press(w1, (430, 548, 556, 656), WORK_PRESS['work_1'], cuff_r)
    w1.save(tmp('work1.png'))
    emit(torso_lean(tmp('work1.png'), tmp('work1b.png'),
                     angle=6.0, pivot=(SIT_AXIS_X, SIT_HIP_Y),
                     shoulder_y=290, hip_y=700, tag='上身前倾+双手按键盘'))
    emit(head_transform(tmp('work1b.png'), p('work_1.png'),
                         rotate=16.0, dy=-6.0, dx=-5.0, tag='低头看键盘'))
    os.remove(tmp('work1b.png'))
    os.remove(tmp('work1.png'))

    w2 = hand_press(sit_cut, (326, 550, 430, 656), WORK_PRESS['work_2'], cuff_l)
    w2 = hand_press(w2, (430, 548, 556, 656), WORK_PRESS['work_2'], cuff_r)
    w2.save(tmp('work2.png'))
    emit(torso_lean(tmp('work2.png'), tmp('work2b.png'),
                     angle=2.0, pivot=(SIT_AXIS_X, SIT_HIP_Y),
                     shoulder_y=290, hip_y=700, tag='坐直+双手抬起'))
    emit(head_transform(tmp('work2b.png'), p('work_2.png'),
                         rotate=13.0, dy=2.0, dx=-6.0, tag='抬头看屏幕'))
    os.remove(tmp('work2b.png'))
    os.remove(tmp('work2.png'))
    os.remove(sit_cut_path)

    # ---------- 唯一性自检: 新帧不得与既有帧字节重复, 也不得彼此重复 ----------
    import hashlib
    def _sha(fp):
        return hashlib.sha256(open(fp, 'rb').read()).hexdigest()
    existing = {}
    for d in (os.path.join(ASSETS, 'character_R138'), os.path.join(ASSETS, 'character_R153')):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.png'):
                existing[_sha(os.path.join(d, fn))] = f'{os.path.basename(d)}/{fn}'
    mine = {}
    dupes = []
    for it in rep['items']:
        fp = p(it['file'])
        if not os.path.exists(fp):
            continue
        h = _sha(fp)
        if h in existing:
            dupes.append(f"{it['file']} 与既有帧 {existing[h]} 字节相同")
        if h in mine:
            dupes.append(f"{it['file']} 与 {mine[h]} 字节相同")
        mine[h] = it['file']
    if dupes:
        raise SystemExit('❌ R156 烘焙唯一性自检失败:\n   ' + '\n   '.join(dupes))
    print(f"  🔒 唯一性自检通过: {len(mine)} 张新帧互不相同, 且与 R138/R153 既有帧无字节重复")

    # 报告只保留最终帧 (中间用的 _tmp_ 文件已被删除, 不应出现在报告里)
    rep['items'] = [it for it in rep['items'] if not it['file'].startswith('_tmp_')]

    rep_path = p('bake_report.json')
    with open(rep_path, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"  📄 {rep_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
