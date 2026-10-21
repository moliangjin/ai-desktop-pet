#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R158 点击互动动作烘焙器 — 手臂骨架 + 衣身还原 + 表情/头部/跳跃复用。

R158 任务书要求:
  · ≥5 种**视觉上明确、动作含义清晰**的点击互动
  · 优先: 真正的比心 / 开心跳跃 / 优美转身 / 挥手庆祝 / 歪头眨眼
  · **禁止**用压缩、平移、重命名冒充新动作
  · 先评估素材可行性; 做不到的如实列出新素材需求, 不虚报

本脚本的做法 (全部基于 R138/R153 既有帧的**局部**处理, 不重画角色):
  H. 手臂骨架摆姿  (36_R158_arm_rig.py)
     · 描边阻隔洪水填充切出"袖+袖口+张开的手" (R138 切层脚本漏切了这只手)
     · 肩/肘/腕三个**圆形咬口**: 每段只带自己近端关节的完整圆盘
       ⇒ 绕关节旋转后圆盘与自身重合, 关节处永不出现缝隙
     · 两骨 IK + 直接关节角标定 (角度约定见 rotate_rgba 的 docstring)
     · 摘掉袖子后按行重建**大褂边缘** (描边 + 白大褂面料), 不留鬼影
  I. 爱心特效 (程序化矢量绘制, 与 R156 的道具同一套纹理坐标系)
  复用 R153 的: face_swap (眼���区域合成) / head_transform (头部连续权重场弯曲)
  复用 R156 的: body_shift (跳跃压扁/伸展, 支点在脚底)

素材边界 (必须写进报告, 不能硬标 PASS):
  · **真正的 180° 背面转身做不到** —— R138 全库只有正面素材 (已逐目录核查),
    程序化"合成背面"需要重画后脑勺+实验服背面 (去掉前襟/胸牌/纽扣),
    属于重画角色, 质量不可控 ⇒ 本轮不做, 输出精确的新素材需求清单。
  · **手指级"比心"几何在桌宠实际显示尺寸下不可读** —— 整只开口只有约
    12x16 屏幕 px (compact 200x240 窗口, 缩放 0.196), 单根手指宽约 2px,
    拇指+食指围出的心形在任何缩放下都读不出来 ⇒ 比心采用
    "双手在胸前合拢 + 爱心特效"的可读性方案, 报告中如实说明。
"""
import hashlib
import importlib.util
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
R138 = os.path.join(ASSETS, 'character_R138')
R153 = os.path.join(ASSETS, 'character_R153')
R156 = os.path.join(ASSETS, 'character_R156')
OUT = os.path.join(ASSETS, 'character_R158')

_spec = importlib.util.spec_from_file_location('r153_bake', os.path.join(CAND, '22_R153_pose_bake.py'))
_r153 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_r153)
face_swap = _r153.face_swap
head_transform = _r153.head_transform
load = _r153.load
to_np = _r153.to_np
to_im = _r153.to_im

_spec2 = importlib.util.spec_from_file_location('r156_bake', os.path.join(CAND, '29_R156_pose_bake.py'))
_r156 = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(_r156)
body_shift = _r156.body_shift

_spec3 = importlib.util.spec_from_file_location('r158_rig', os.path.join(CAND, '36_R158_arm_rig.py'))
_rig = importlib.util.module_from_spec(_spec3)
_spec3.loader.exec_module(_rig)

BASE = os.path.join(R138, 'idle', 'idle_00_base.png')
CLOSED_SMILE = os.path.join(R138, 'idle', 'idle_05_blink_closed.png')
HALF_BLINK = os.path.join(R138, 'idle', 'idle_04_blink_half.png')
FOOT_Y = 987

# ---------------------------------------------------------------------------
# 姿态表 —— 角度 = (肩, 肘, 腕), 增量角, **正 = 视觉逆时针** (见 rotate_rgba doc)
#   画面左臂 (角色右手) 向上外抬 → 肩角负值 (-90 ~ -130)
#   画面右臂 (角色左手) 向上外抬 → 肩角正值 (+90 ~ +130)
#   前臂向身体中线折叠 (手到胸前) → 肘角正值 (+90 ~ +145)
# ---------------------------------------------------------------------------
POSES = {
    # 1. 真挥手: 右臂 (画面右) 举到头侧, 手腕左右摆
    'cheer_wave': [
        dict(L=None, R=(130, 0, 0)),
        dict(L=None, R=(133, -14, 30)),
        dict(L=None, R=(126, -7, -30)),
    ],
    # 2. 双臂欢呼: 双臂高举成 V
    'cheer_hands_up': [
        dict(L=(-118, 0, 0), R=(118, 0, 0)),
        dict(L=(-126, -10, 0), R=(126, 10, 0)),
        dict(L=(-112, 0, 0), R=(112, 0, 0)),
    ],
    # 3. 比心: 双手在胸前/下颌**合成心形**(最高点 a_e=141), 配头侧爱心特效
    #    R162 重标定: 旧参数 a_s=-6 / a_e=140 把手举到**领口正中央**, 两只手
    #    互相压住只剩一团深色 ⇒ 200x240 下完全读不出"比心"。
    #    实测 (200px 实际显示尺寸逐帧比对): a_s=-22 时手掌分开、掌缘朝上,
    #    满分辨率下能看出心形; 再配合头侧的大颗爱心特效 ⇒ 显示尺寸下可读。
    'cheer_heart': [
        dict(L=(-20, 136, -6), R=(20, -136, 6)),
        dict(L=(-22, 141, 0), R=(22, -141, 0)),
        dict(L=(-20, 137, -5), R=(20, -137, 5)),
    ],
    # 4. 鼓掌: 双手在身前**张开→合拢→张开**(手心相对)
    #    R162 重标定: 旧参数 a_s=±30/a_e=-34 是"双臂平举", 根本不是鼓掌;
    #    且与比心帧几乎同姿态 ⇒ 6 个动作里有两个长得一样。
    #    实测: a_s=32 时肘部外张、双手在领口高度张开, 200px 下"两只手对着"清晰可读。
    'cheer_clap': [
        dict(L=(32, 112, 0), R=(-32, -112, 0)),   # 张开 (两掌间距 ~92 纹理 px)
        dict(L=(32, 140, 0), R=(-32, -140, 0)),   # 合拢 (两掌贴合, 间距 0)
        dict(L=(32, 120, 0), R=(-32, -120, 0)),   # 再张开 (间距 ~64)
    ],
    # 5. 开心跳跃: 蓄力下蹲 → 腾空(双臂上扬+离地) → 落地压缩
    'cheer_jump': [
        dict(L=(-18, 0, 0), R=(18, 0, 0)),
        dict(L=(-124, 0, 0), R=(124, 0, 0)),
        dict(L=(-20, 0, 0), R=(20, 0, 0)),
    ],
    # 6. 歪头眨眼: 手臂自然垂放, 只动头 (R153 连续权重场) + 眼���
    'cheer_tilt': [
        dict(L=None, R=None),
        dict(L=None, R=None),
        dict(L=None, R=None),
    ],
}

# 表情: 每帧用哪个 donor 换眼 (None = 不换)
FACE = {
    'cheer_wave': [HALF_BLINK, CLOSED_SMILE, None],
    'cheer_hands_up': [HALF_BLINK, CLOSED_SMILE, HALF_BLINK],
    'cheer_heart': [CLOSED_SMILE, CLOSED_SMILE, None],
    'cheer_clap': [None, CLOSED_SMILE, None],
    'cheer_jump': [CLOSED_SMILE, CLOSED_SMILE, None],
    'cheer_tilt': [None, HALF_BLINK, CLOSED_SMILE],
}

# 头部连续权重场: (rotate 度, dy 像素)
HEAD = {
    'cheer_wave': [(4, 0), (6, -2), (3, 0)],
    'cheer_hands_up': [(6, -2), (8, -4), (4, -1)],
    'cheer_heart': [(-6, 0), (-8, -3), (-4, 0)],
    'cheer_clap': [(3, 0), (5, -2), (2, 0)],
    'cheer_jump': [(0, 0), (6, -4), (-4, 2)],
    'cheer_tilt': [(17, 0), (17, 0), (12, 0)],
}

# 跳跃的三帧: (scale_y, shift_up)
JUMP_SCALE = [0.80, 1.0, 0.84]


def arm_pose_frame(poses, base_np, rigL, rigR, tmp_path):
    """把手臂骨架摆好并合成, 输出 1024x1024 RGBA 数组。"""
    body = base_np.copy()
    layers = []
    for side in ('L', 'R'):
        ang = poses.get(side)
        if not ang:
            continue
        r = rigL if side == 'L' else rigR
        b, _fill = _rig.restore_body(body, r['arm'], side)
        body = b
        up, fo, hd = _rig.pose_arm(base_np, r, ang)
        layers += [up, fo, hd]
    return _rig.compose(body, layers)


def bake():
    os.makedirs(OUT, exist_ok=True)
    base_np = to_np(load(BASE))
    rigL = _rig.build_arm(base_np, 'L')
    rigR = _rig.build_arm(base_np, 'R')
    rep = {'round': 'R158', 'techniques': ['arm_rig (肩/肘/腕 圆形咬口 + 衣身还原)',
                                           'face_swap (眼部区域合成, 复用 R153)',
                                           'head_transform (头部连续权重场, 复用 R153)',
                                           'body_shift (跳跃剪影对比, 复用 R156)',
                                           'prop_heart (程序化矢量爱心)'],
           'items': []}

    def emit(info):
        rep['items'].append(info)
        print(f"  ✅ {info['file']:26s} {info.get('note','')}")

    for action, frame_poses in POSES.items():
        for i, poses in enumerate(frame_poses):
            name = f'{action}_{i}.png'
            path = os.path.join(OUT, name)
            # 1) 手臂骨架
            arr = arm_pose_frame(poses, base_np, rigL, rigR, path)
            im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')
            tmp = os.path.join(OUT, '_tmp_' + name)
            im.save(tmp)
            # 2) 眼部表情 —— 必须在**头部变换与整体压缩之前**做
            #    R162 修正: 原顺序是 头部变换 → 整体压缩 → 贴五官,
            #    而 donor 是**未压缩**的底图帧, 于是五官被按原坐标贴进已被压扁/转过的头,
            #    跳跃蓄力帧 (scale_y=0.80) 上五官直接落在**头顶** ⇒ 看起来像"头顶图像破损"。
            #    先贴五官(此时目标与 donor 同坐标系, 严丝合缝), 再让后续变换把五官一起带走。
            donor = FACE[action][i]
            if donor:
                face_swap(tmp, donor, tmp, tag=action)
            # 3) 头部连续权重场
            rot, dy = HEAD[action][i]
            if rot or dy:
                head_transform(tmp, tmp, rotate=rot, dy=dy, tag=action)
            # 4) 跳跃剪影 (压扁/伸展, 支点在脚底)
            if action == 'cheer_jump':
                body_shift(tmp, tmp, shift_up=0, scale_y=JUMP_SCALE[i], pivot_y=FOOT_Y, tag=action)
            os.replace(tmp, path)
            res = Image.open(path)
            emit({'file': name, 'action': action, 'index': i,
                  'bbox': list(res.getbbox()),
                  'pose': {k: v for k, v in poses.items() if v},
                  'head': {'rotate': rot, 'dy': dy},
                  'face': os.path.basename(donor) if donor else None,
                  'scale_y': JUMP_SCALE[i] if action == 'cheer_jump' else None,
                  'note': '手臂骨架摆姿 + 头部权重场 + 眼部合成'})

    # ---------- 爱心特效 (程序化矢量, 与 R156 道具同一纹理坐标系) ----------
    heart_path = os.path.join(OUT, 'prop_heart.png')
    draw_heart(heart_path)
    _hp = Image.open(heart_path)
    emit({'file': 'prop_heart.png', 'action': 'cheer_heart', 'index': -1,
          'bbox': list(_hp.getbbox()),
          'note': '程序化矢量爱心特效 (头侧左上空白区, front 层, 不遮手不遮脸)'} )

    # ---------- 唯一性自检 ----------
    def sha(fp):
        return hashlib.sha256(open(fp, 'rb').read()).hexdigest()
    existing = {}
    for d in (R138, R153, R156):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.png'):
                existing[sha(os.path.join(d, fn))] = f'{os.path.basename(d)}/{fn}'
    mine = {}
    dupes = []
    for it in rep['items']:
        fp = os.path.join(OUT, it['file'])
        if not os.path.exists(fp):
            continue
        h = sha(fp)
        if h in existing:
            dupes.append(f"{it['file']} 与既有帧 {existing[h]} 字节相同")
        if h in mine:
            dupes.append(f"{it['file']} 与 {mine[h]} 字节相同")
        mine[h] = it['file']
    if dupes:
        raise SystemExit('❌ R158 烘焙唯一性自检失败:\n   ' + '\n   '.join(dupes))
    print(f"  🔒 唯一性自检通过: {len(mine)} 张新帧互不相同, 且与 R138/R153/R156 无字节重复")

    rep_path = os.path.join(OUT, 'bake_report.json')
    with open(rep_path, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"  📄 {rep_path}")
    return 0


def draw_heart(path, size=120):
    """画一颗柔和的爱心特效 (1024x1024 纹理坐标系)。"""
    SS = 4
    W = H = 1024
    img = Image.new('RGBA', (W * 1, H * 1), (0, 0, 0, 0))
    s = size * SS
    pad = s // 2
    # 用一张小图画心形再放大 ⇒ 边缘平滑
    small = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(small)
    # 经典心形: 两个圆 + 一个三角
    r = int(s * 0.26)
    cx1, cx2 = int(s * 0.29), int(s * 0.71)
    cy = int(s * 0.33)
    d.ellipse([cx1 - r, cy - r, cx1 + r, cy + r], fill=(255, 92, 122, 255))
    d.ellipse([cx2 - r, cy - r, cx2 + r, cy + r], fill=(255, 92, 122, 255))
    d.polygon([(int(s * 0.06), int(s * 0.45)), (int(s * 0.94), int(s * 0.45)), (int(s * 0.5), int(s * 0.97))],
              fill=(255, 92, 122, 255))
    big = small.resize((s // SS, s // SS), Image.LANCZOS)
    # 高光
    hl = Image.new('RGBA', (s // SS, s // SS), (0, 0, 0, 0))
    dh = ImageDraw.Draw(hl)
    dh.ellipse([int(s * 0.22 / SS), int(s * 0.26 / SS), int(s * 0.40 / SS), int(s * 0.40 / SS)],
               fill=(255, 200, 210, 210))
    big = Image.alpha_composite(big, hl)
    # 柔光底
    glow = big.filter(ImageFilter.GaussianBlur(radius=6))
    glow.putalpha(glow.getchannel('A').point(lambda v: int(v * 0.55)))
    canvas = Image.alpha_composite(glow, big)
    # 贴到画布: **角色头侧左上角** (R162 改)
    #   旧位置 (512,400) 正好压在手心/领口上 ⇒ 把"手在胸前合拢"的手势整个盖掉,
    #   200x240 显示尺寸下反而更看不清比心。
    #   新位置: 头部左外侧空白区 (底图该处 x186-304 完全空白, 头发最左只到 x331)
    #   ⇒ 爱心不遮脸、不遮手, 且在 200px 下是 23x23 px 的清晰粉色块。
    cx, cy = 245, 222
    img.alpha_composite(canvas, (cx - canvas.width // 2, cy - canvas.height // 2))
    img.save(path)


if __name__ == '__main__':
    print('R158 点击互动动作烘焙 (手臂骨架 + 表情 + 跳跃 + 爱心特效):')
    sys.exit(bake())
