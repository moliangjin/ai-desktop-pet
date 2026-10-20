#!/usr/bin/env python3
"""R156 manifest 修订器 (幂等, 可重放)。

变更:
  1. **点击互动池** (6 个动作, 每个 3 帧: 开始/中间/结束)
       cheer_heart  比心 (近似)      cheer_jump   开心小跳
       cheer_spin   原地轻盈转身      cheer_wink   歪头眨眼卖萌
       cheer_hands  双手小庆祝        cheer_sway   开心摇摆
     全部由 29_R156_pose_bake.py 基于 R138/R153 既有帧局部处理生成, 每个动作有独立帧资源。
  2. **办公待机动作** work (2 帧: 前倾看屏幕 / 抬头思考)
  3. **道具场景段** props: 程序化绘制的 7 个小道具 + 每个动作的 back/front 分层与地面行
  4. **ground_tex_y** (地面行): 布局算法"每帧内容底边贴同一条地面线"在有道具时不成立 ——
     真正的地面是**道具的底** (床脚 818 / 沙发底 1001 / 桌腿底 1001)。
     ground_tex_y 声明"该帧的哪一条纹理行落在屏幕地面线上":
       · 有道具的动作 → 等于道具场景的 floor_tex_y (角色踩在道具底上)
       · 腾空帧     → 1150 (比 987 高 163 纹理 px ⇒ 离地 ≈32 屏幕 px)
       · null       → 缺省行为 (内容底边贴地面线, R153 语义不变)
  5. layout.frame_bboxes 补齐 R156 新帧的实测 bbox (缩放/地面线核算的基础)

不做的事:
  · 不动核心 6 组动作的 23 个帧槽位 (R113/R148/R153 门禁口径不变)
  · 不动 R138 原始帧字节
  · 不动行走错切 (R153 已归零)
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
MANIFEST_PATH = os.path.join(ASSETS, 'character_R141_manifest.json')

R156 = 'character_R156'

# ---------- R156 新增动作 (动作名 → 规格) ----------
LIBRARY_R156 = {
    # ---- 办公待机 (新增 idle 类状态) ----
    'work': {
        'frames': [f'{R156}/work_1.png', f'{R156}/work_2.png'],
        'frame_ms': [2800, 2800],
        'loop': True,
        'anchor': 'sit',
        'ground_tex_y': 1001,
        'desc': '在电脑前办公: 坐姿上半身前倾看屏幕 / 抬头思考 (连续权重场前倾, 下半身固定)',
        'source': 'R156 局部烘焙 (torso_lean)',
    },
    # ---- 点击互动池 (6 个) ----
    'cheer_heart': {
        'frames': [f'{R156}/cheer_heart_0.png', f'{R156}/cheer_heart_1.png', f'{R156}/cheer_heart_2.png'],
        'frame_ms': [170, 330, 200],
        'loop': False,
        'anchor': 'stand',
        'desc': ('比心 (近似): 站立期待(闭眼笑) → 手贴胸闭眼笑 → 手贴胸睁眼; '
                 'R138 无双手比心手势素材, 用"右手横在胸前"近似'),
        'source': 'R156 局部烘焙 (face_swap)',
    },
    'cheer_jump': {
        'frames': [f'{R156}/cheer_jump_0.png', f'{R156}/cheer_jump_1.png', f'{R156}/cheer_jump_2.png'],
        'frame_ms': [150, 320, 180],
        'loop': False,
        'anchor': 'stand',
        'ground_tex_y': [None, 1015, None],
        'desc': ('开心小跳: 蓄力下蹲(压扁 14%) → 腾空(伸展 + 离地 28 纹理 px, 闭眼笑) → 落地压缩(12%); '
                 '离地量由运行时 ground_tex_y 实现, 不是把角色在纹理里挪动。'
                 '离地上限受**窗口高度**硬约束: standard 模式 (256x256) 角色头顶只剩 11px 余量, '
                 '故离地 ≤7 屏幕 px; "跳"的观感主要来自压扁↔伸展的剪影对比 (头部竖直行程 ~31px)'),
        'source': 'R156 局部烘焙 (body_shift + face_swap)',
    },
    'cheer_spin': {
        'frames': [f'{R156}/cheer_spin_0.png', f'{R156}/cheer_spin_1.png', f'{R156}/cheer_spin_2.png'],
        'frame_ms': [170, 330, 200],
        'loop': False,
        'anchor': 'stand',
        'desc': ('原地轻盈转身: 起转(头 8°) → 侧身(整体水平压缩 64% + 头 14°) → 转回(压缩 82% + 头 5°); '
                 '这是 2D "变窄=正在转身"的表现手法, 不是真正的 180° 背面转身 (R138 无背面素材)'),
        'source': 'R156 局部烘焙 (body_narrow + head_transform)',
    },
    'cheer_wink': {
        'frames': [f'{R156}/cheer_wink_0.png', f'{R156}/cheer_wink_1.png', f'{R156}/cheer_wink_2.png'],
        'frame_ms': [200, 260, 320],
        'loop': False,
        'anchor': 'stand',
        'desc': '歪头眨眼卖萌: 歪头 11° 睁眼 → 歪头 11° 眯眼 → 轻歪头 6° 闭眼笑',
        'source': 'R156 局部烘焙 (head_transform + face_swap)',
    },
    'cheer_hands': {
        'frames': [f'{R156}/cheer_hands_0.png', f'{R156}/cheer_hands_1.png', f'{R156}/cheer_hands_2.png'],
        'frame_ms': [170, 330, 200],
        'loop': False,
        'anchor': 'stand',
        'desc': '双手小庆祝: 举手期待 → 举手续 bigger 笑 → 举手下沉 (弹跳收势)',
        'source': 'R156 局部烘焙 (head_transform + face_swap + body_shift)',
    },
    'cheer_sway': {
        'frames': [f'{R156}/cheer_sway_0.png', f'{R156}/cheer_sway_1.png', f'{R156}/cheer_sway_2.png'],
        'frame_ms': [200, 300, 260],
        'loop': False,
        'anchor': 'stand',
        'desc': '开心摇摆: 身体左移 46px + 头右倾 8° → 身体右移 46px + 头左倾 8° → 回正闭眼笑',
        'source': 'R156 局部烘焙 (body_shift_x + head_transform + face_swap)',
    },
}

# ---------- 点击互动池 (权重 + 不重复上一次) ----------
CLICK_POOL = [
    {'action': 'cheer_heart', 'weight': 3, 'desc': '比心 (近似)'},
    {'action': 'cheer_jump', 'weight': 2, 'desc': '开心小跳'},
    {'action': 'cheer_spin', 'weight': 2, 'desc': '原地轻盈转身'},
    {'action': 'cheer_wink', 'weight': 3, 'desc': '歪头眨眼卖萌'},
    {'action': 'cheer_hands', 'weight': 2, 'desc': '双手小庆祝'},
    {'action': 'cheer_sway', 'weight': 2, 'desc': '开心摇摆'},
]

# ---------- 道具库 (程序化绘制, 无外部素材/无 AI 生图) ----------
PROP_LIBRARY = {
    'prop_bed': {'file': f'{R156}/prop_bed.png', 'desc': '小床: 床头板 + 床垫 + 枕头 + 床腿'},
    'prop_quilt': {'file': f'{R156}/prop_quilt.png', 'desc': '被子: 盖住身体右半与腿, 左边界收到 x=470 不遮脸'},
    'prop_moon': {'file': f'{R156}/prop_moon.png', 'desc': '月亮 + 小星 + 一小片淡月晕 (夜晚氛围, 不做大块背景)'},
    'prop_sofa': {'file': f'{R156}/prop_sofa.png', 'desc': '低矮豆袋小沙发: 无细高腿, 厚坐垫直接落地'},
    'prop_chair': {'file': f'{R156}/prop_chair.png', 'desc': '办公转椅: 靠背宽到能在笔记本两侧露出'},
    'prop_desk': {'file': f'{R156}/prop_desk.png', 'desc': '小桌子 + 笔记本电脑 (观众视角看到屏幕正面)'},
    'prop_screen_glow': {'file': f'{R156}/prop_screen_glow.png', 'desc': '屏幕微光: 淡淡一层冷色光'},
}

# ---------- 动作 → 道具场景 (back = 角色身后, front = 角色身前) ----------
PROP_SCENES = {
    'sleep_breath': {
        'floor_tex_y': 818, 'back': ['prop_bed', 'prop_moon'], 'front': ['prop_quilt'],
        'desc': '睡眠主循环: 躺在床上 + 月亮夜晚氛围 + 被子盖身',
    },
    'sleep_loop': {
        'floor_tex_y': 818, 'back': ['prop_bed', 'prop_moon'], 'front': ['prop_quilt'],
        'desc': '睡眠中的姿态微调: 同一套床与夜色氛围',
    },
    # wake_up **不带道具** —— 硬约束: 这张床只放得下"躺姿"。
    #   床面 (床垫顶 632) 之上的净空只有 632 纹理 px, 而坐姿帧高 886~964 纹理 px,
    #   坐起来的角色放不进这张床 (会陷进床垫或被裁掉)。所以醒来过渡走"场景溶解":
    #   睡觉时床淡入、醒来时床淡出, 角色始终不与道具产生错误接触关系。
    'sit_rest': {
        'floor_tex_y': 1001, 'back': ['prop_sofa'], 'front': [],
        'desc': '坐下休息: 坐在低矮小沙发上',
    },
    'doze': {
        'floor_tex_y': 1001, 'back': ['prop_sofa'], 'front': [],
        'desc': '困倦打盹: 坐在同一张小沙发上闭眼',
    },
    'work': {
        'floor_tex_y': 1001, 'back': ['prop_chair'], 'front': ['prop_desk', 'prop_screen_glow'],
        'desc': '办公待机: 坐在转椅上, 角色从笔记本电脑屏幕后面探出上半身, 屏幕微光',
    },
}


def bbox_of(rel):
    p = os.path.join(ASSETS, rel)
    if not os.path.exists(p):
        raise SystemExit(f'❌ 帧资源缺失: {rel}')
    bb = Image.open(p).convert('RGBA').getbbox()
    return [int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])]


def main():
    m = json.load(open(MANIFEST_PATH, encoding='utf-8'))
    m['version'] = 'R156-RUNTIME'

    # ---------- 1. 动作库: R153 的 9 个原样保留 + R156 新增 7 个 ----------
    lib = m.get('action_library') or {}
    lib_actions = dict(lib.get('actions') or {})
    lib_bboxes = dict(m['layout'].get('frame_bboxes') or {})

    for name, spec in LIBRARY_R156.items():
        entry = {
            'frames': spec['frames'],
            'frame_ms': spec['frame_ms'],
            'loop': spec['loop'],
            'anchor': spec['anchor'],
            'desc': spec['desc'],
            'source': spec['source'],
        }
        if 'ground_tex_y' in spec:
            entry['ground_tex_y'] = spec['ground_tex_y']
        lib_actions[name] = entry
        lib_bboxes[name] = [bbox_of(f) for f in spec['frames']]

    lib['enabled'] = True
    lib['round'] = 'R156'
    lib['note'] = (lib.get('note', '') +
                   ' | R156: 新增 7 个动作 —— 点击互动池 6 个 (cheer_heart/cheer_jump/cheer_spin/'
                   'cheer_wink/cheer_hands/cheer_sway, 每个 3 帧 开始/中间/结束) + 办公待机 1 个 (work)。'
                   '全部由 29_R156_pose_bake.py 基于 R138/R153 既有帧做**局部**处理生成 '
                   '(眼部区域合成 / 头部连续权重场弯曲 / 整体垂直平移 / 整体水平压缩 / 整体水平平移 / 上半身前倾)')
    lib['actions'] = lib_actions
    m['action_library'] = lib

    # ---------- 2. 地面行 (ground_tex_y) 落到动作上 ----------
    #   有道具的动作: 角色踩在道具底上 → 与道具场景 floor_tex_y 一致
    #   腾空帧: 1150 (比脚底 987 高 163 纹理 px ⇒ 离地 ≈32 屏幕 px)
    GROUND_TEX_Y = {
        'sleep_breath': 818,
        'sleep_loop': 818,
        'sit_rest': 1001,
        'doze': 1001,
    }
    # wake_up 不带道具 (这张床只放得下躺姿) → 不声明地面行, 走缺省行为
    if 'wake_up' in m['actions']:
        m['actions']['wake_up'].pop('ground_tex_y', None)
        m['actions']['wake_up'].pop('ground_tex_y_note', None)
    for action, g in GROUND_TEX_Y.items():
        if action in m['actions']:
            m['actions'][action]['ground_tex_y'] = g
            m['actions'][action]['ground_tex_y_note'] = (
                'R156: 该动作的"地面行"(哪一条纹理行落在屏幕地面线上)。'
                '有道具时真正的地面是道具的底, 不是角色内容的底边')
        elif action in lib_actions:
            lib_actions[action]['ground_tex_y'] = g
    m['action_library']['actions'] = lib_actions

    # ---------- 3. 点击互动池 ----------
    m['click_reactions'] = {
        'enabled': True,
        'round': 'R156',
        'note': ('R156: 点击反馈从"固定 1 个动作"改为**随机池**。每次点击从池里随机挑一个, '
                 '短时间内不重复上一次; 播放期间暂停普通 idle/walk/sleep 推进, 播完回到正常状态机。'
                 '每个动作都有 3 帧 (开始/中间/结束), 不是单张定格。'),
        'no_repeat_last': True,
        'pool': CLICK_POOL,
    }

    # ---------- 4. 道具场景 ----------
    m['props'] = {
        'enabled': True,
        'round': 'R156',
        'technique': '程序化矢量绘制 (30_R156_props_bake.py, 无外部素材/无 AI 生图)',
        'coordinate_note': ('道具 PNG 与角色帧**同一纹理坐标系** (1024x1024), 渲染时与角色 sprite '
                            '共享 position/anchor/scale, 所以"道具落地"= 画到该场景的地面纹理行'),
        'z_order_note': ('back 层 = 道具在角色身后 (月亮/床/沙发/转椅); '
                         'front 层 = 道具在角色身前 (被子/桌子+笔记本/屏幕微光)'),
        'library': PROP_LIBRARY,
        'scenes': PROP_SCENES,
    }

    # ---------- 5. bbox 与顶层说明 ----------
    m['layout']['frame_bboxes'].update(lib_bboxes)
    m['layout']['ground_rule'] = (
        m['layout'].get('ground_rule', '') +
        ' | R156: 有道具的动作改用 ground_tex_y (道具底所在纹理行) 作为地面行; '
        '腾空帧用更高的地面行 (1150) 表示离地')
    m['notes'] = [
        'R141 运行时 manifest: 帧路径相对本 manifest 所在目录 (assets/character_R141_manifest.json -> character_R138/...)',
        'R138 六组动作 23 帧全部为 1024x1024 RGBA PNG (R153 起**逐字节未变**, R156 仍逐字节未变)',
        'sleep_enter / wake_up 为一次性动画, 由 renderer 播完回报主进程',
        'R148: walk_right 运行时使用 4 张派生帧 (character_R138_derived/walk_right_mirror/)',
        'R153: 新增 action_library 段 (9 个新动作, 12 张新烘焙帧在 character_R153/); '
        '核心 6 组动作的帧槽位仍是 23 个互不相同的文件',
        'R153: 行走整体错切归零 (用户反馈"身体前倾像摔倒"), 方向由 R148 的步态本身承担',
        'R156: 新增点击互动池 6 个动作 (3 帧/个) + 办公待机 work (2 帧) —— '
        '15 张新烘焙帧在 character_R156/',
        'R156: 新增 props 段 —— 7 个程序化绘制的小道具 + 6 个动作的道具场景 (back/front 分层)',
        'R156: 新增 ground_tex_y (地面行) —— 有道具时地面是道具底, 腾空帧用更高的地面行表示离地',
    ]
    m['r156_click_props_work'] = {
        'goals': [
            '点击互动动作池 ≥5 个 (实际 6 个), 每个有开始/中间/结束, 随机触发且不重复',
            '睡觉加床 + 月亮夜晚氛围; 坐下加小沙发',
            '新增"在电脑前办公"的待机场景 (小桌子 + 笔记本 + 屏幕微光)',
            '全部接入行为系统与运行逻辑 (不是只交静态图)',
        ],
        'honest_limits': [
            '真正的双手比心手势做不到 —— R138 无手部素材, 用"右手横在胸前"近似',
            '"双手小庆祝"用 R138 idle_01 的双臂抬起近似, 不是真正的双手拍掌',
            '原地转身是 2D 表现手法 (正面→水平压缩 64% 读作侧身→回正), 不是 180° 背面转身',
            '办公只能做"看屏幕/思考/停顿", 做不到"敲键盘"手部动作 (R138 无手部素材)',
            'R138 素材角色轮廓在纹理里占 y=37~987, 头顶只剩 37px 余量 —— '
            '腾空离地由运行时 ground_tex_y 实现, 若在纹理内挪动最多只能离地 7 屏幕 px',
        ],
        'prop_scenes': sorted(PROP_SCENES.keys()),
        'click_pool': [p['action'] for p in CLICK_POOL],
    }

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'✅ manifest 已更新: {MANIFEST_PATH}')
    print(f'   version = {m["version"]}')
    print(f'   action_library = {len(lib_actions)} 个动作')
    print(f'   click pool = {len(CLICK_POOL)} 个: ' + ', '.join(p["action"] for p in CLICK_POOL))
    print(f'   prop scenes = {len(PROP_SCENES)} 个: ' + ', '.join(sorted(PROP_SCENES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
