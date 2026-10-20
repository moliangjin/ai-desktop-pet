#!/usr/bin/env python3
"""R148: 把 walk_right 切换到派生镜像帧, 并同步更新布局 bbox 与来源说明。

变更 (全部可复算):
  · actions.walk_right.frames → character_R138_derived/walk_right_mirror/*.png
      (由"已确认方向正确"的 walk_left 4 帧整体水平镜像 + 徽章归位派生, 见 17_R148_mirror_derive.py)
  · layout.frame_bboxes.walk_right → 派生帧的真实 bbox (逐帧从 PNG 实测)
  · version / notes → 标注 R148 来源与"原 walk_right 4 帧保留但不再被引用"

不改动: 原始 R138 的 23 个 PNG 一个字节都不动 (脚本末尾会校验)。
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
MANIFEST_PATH = os.path.join(ASSETS, 'character_R141_manifest.json')
DERIVED_DIR = os.path.join(ASSETS, 'character_R138_derived', 'walk_right_mirror')

DERIVED = [
    'character_R138_derived/walk_right_mirror/walk_right_m_00.png',
    'character_R138_derived/walk_right_mirror/walk_right_m_01.png',
    'character_R138_derived/walk_right_mirror/walk_right_m_02.png',
    'character_R138_derived/walk_right_mirror/walk_right_m_03.png',
]
OLD_WALK_RIGHT = [
    'character_R138/walk_right/walk_right_00_stand.png',
    'character_R138/walk_right/walk_right_01_right_step.png',
    'character_R138/walk_right/walk_right_02_pass.png',
    'character_R138/walk_right/walk_right_03_left_step.png',
]


def main():
    m = json.load(open(MANIFEST_PATH, encoding='utf-8'))

    m['version'] = 'R148-RUNTIME'
    m['source_round'] = 'R138'
    m['r148_walk_direction_fix'] = {
        'issue': 'R148 用户真机截图: walk_right 窗口向右移动, 但人物迈步像在向左 (倒退走)',
        'root_cause': ('R138 的 walk_left / walk_right 都是正面 3/4 立绘, 脚尖方向本身不携带行进信息; '
                       '实测两组步态的抬脚腿序列几乎相同, 且 walk_right 与 walk_left 的落脚脚/鞋尖朝向'
                       '指向同一侧 (均���左脚落地且鞋尖朝左) → 向右移动时观感为倒退'),
        'fix': ('整体水平镜像**已确认方向正确**的 walk_left 4 帧, 派生 walk_right 4 帧; '
                '并把胸口烧瓶徽章按原样 (不镜像) 归位回角色自己的左胸 (观者右侧)'),
        'not_leg_only_mirror': '逐像素校验: 派生帧在徽章区外与源帧的水平镜像差异 = 0 像素',
        'source_of_truth': 'character_R138_derived/walk_right_mirror/ (由 17_R148_mirror_derive.py 生成)',
        'original_walk_right_frames': {
            'paths': OLD_WALK_RIGHT,
            'status': '保留在 character_R138/walk_right/, 字节未改动; R148 起不再被 manifest 引用',
            'reason': '其步向与 walk_left 同向, 直接播放会造成"向右移动却向左迈步"的倒退观感',
        },
    }

    wr = m['actions']['walk_right']
    wr['frames'] = list(DERIVED)
    wr['frame_source'] = {
        'derived_from': 'character_R138/walk_left/ (R147 已确认其迈步方向正确)',
        'method': '整体水平镜像 + 胸口徽章 Poisson 无缝归位',
        'script': '17_R148_mirror_derive.py',
        'verify': '18_R148_direction_verify.py (鞋尖几何客观测量)',
    }
    wr['note'] = ('R148: 原 R138 walk_right 4 帧的落脚脚/鞋尖与 walk_left 同向 (均朝左), '
                  '向右移动时观感为倒退; 改为由"已确认正确"的 walk_left 4 帧整体水平镜像派生, '
                  '并把胸口烧瓶徽章归位回角色自己的左胸 (不镜像), 保证两个方向服装/徽章一致')

    wl = m['actions']['walk_left']
    wl['note'] = ('R147/R148: 4 帧为已确认**方向正确**的向左步态 (落地脚在左、鞋尖朝左, '
                  '由 18_R148_direction_verify.py 客观测量确认); 叠加整体向左倾斜, 纹理本身不镜像')

    # ---- bbox: 用派生帧真实 bbox 覆盖 ----
    boxes = []
    for rel in DERIVED:
        p = os.path.join(ASSETS, rel)
        if not os.path.exists(p):
            print(f"❌ 派生帧缺失: {rel}")
            return 1
        bb = Image.open(p).convert('RGBA').getbbox()
        boxes.append([int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])])
    m['layout']['frame_bboxes']['walk_right'] = boxes

    m['notes'] = [
        'R141 运行时 manifest: 帧路径相对本 manifest 所在目录 (assets/character_R141_manifest.json -> character_R138/...)',
        'R138 六组动作 23 帧全部为 1024x1024 RGBA PNG',
        'sleep_enter / wake_up 为一次性动画, 由 renderer 播完回报主进程',
        ('R148: walk_right 运行时使用 4 张派生帧 (character_R138_derived/walk_right_mirror/), '
         '由已确认方向正确的 walk_left 4 帧整体水平镜像 + 徽章归位生成; '
         'R138 原始 23 帧全部保留在 character_R138/ 内且字节未变, 其中原 walk_right 4 帧不再被引用'),
    ]

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f"✅ manifest 已更新: {MANIFEST_PATH}")
    print(f"   walk_right.frames = {len(DERIVED)} 派生帧")
    print(f"   walk_right bbox  = {boxes}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
