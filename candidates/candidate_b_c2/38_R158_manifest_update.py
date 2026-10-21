#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R158 manifest 更新器 — 点击互动动作池换成 R158 的 6 个真实动作。

R158 任务书的硬要求:
  · ≥5 种**视觉上明确、动作含义清晰**的点击互动
  · **禁止**用压缩/平移/重命名冒充新动作 ⇒ R156 的 4 个几何形变动作必须下架:
      cheer_spin  (整体水平压缩 64% 冒充转身)   → 删除
      cheer_sway  (整体水平平移冒充摇摆)         → 删除
      cheer_heart (复用 idle_04"右手横在胸前")   → 删除, 由 R158 真比心替换
      cheer_wink  (与 R153 head_tilt 语义重叠)   → 删除, 由 R158 cheer_tilt 替换
      cheer_hands (复用 idle_01"双臂抬起", 动作不明显) → 删除, 由 R158 cheer_hands_up 替换
      cheer_jump  (R156 版无手臂动作)           → 由 R158 cheer_jump 替换

R158 保留 R156 已完成的场景 (床/月亮/被子 / 小沙发 / 办公转椅+小桌+笔记本+屏幕微光) 与
R156 的 work 待机动作 —— 本轮**不重做**场景。

同时登记:
  · props.library.prop_heart + props.scenes.cheer_heart (爱心特效, 程序化矢量绘制)
  · layout.frame_bboxes 补齐 R158 新帧的实测 bbox (缩放/地面线核算的基础)
  · r158_click_actions 段: 素材可行性评估结论 + 做不到项的新素材需求
"""
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
MANIFEST_PATH = os.path.join(ASSETS, 'character_R141_manifest.json')
R153 = 'character_R153'
R156 = 'character_R156'
R158 = 'character_R158'

# ---------- R158 新增的 6 个点击互动动作 ----------
LIBRARY_R158 = {
    'cheer_wave': {
        'frames': [f'{R158}/cheer_wave_{i}.png' for i in range(3)],
        'frame_ms': [170, 300, 210],
        'loop': False,
        'anchor': 'stand',
        'desc': ('真挥手: 右臂(角色左手)抬到头侧 → 手腕向右摆 → 手腕向左摆。'
                 '手臂由 R158 手臂骨架切出真实"袖+袖口+张开的手"(R138 切层脚本原本漏切了这只手), '
                 '肩/肘/腕三关节圆形咬口旋转, 摘掉袖子后按行重建大褂边缘, 不留鬼影。'),
        'source': 'R158 局部烘焙 (arm_rig + head_transform + face_swap)',
    },
    'cheer_hands_up': {
        'frames': [f'{R158}/cheer_hands_up_{i}.png' for i in range(3)],
        'frame_ms': [160, 330, 200],
        'loop': False,
        'anchor': 'stand',
        'desc': ('双臂欢呼: 双臂高举成 V → 更高更开(闭眼大笑) → 落回。'
                 '取代 R156 的 cheer_hands(那只用 R138 idle_01 的"双臂抬起"近似, 动作不明显)。'),
        'source': 'R158 局部烘焙 (arm_rig + head_transform + face_swap)',
    },
    'cheer_heart': {
        'frames': [f'{R158}/cheer_heart_{i}.png' for i in range(3)],
        'frame_ms': [190, 340, 230],
        'loop': False,
        'anchor': 'stand',
        'ground_tex_y': 987,
        'desc': ('比心: 双手在胸前合拢(头微低) + 爱心特效(prop_heart) 淡入淡出。'
                 '**如实说明**: 手指级"心形"在桌宠实际显示尺寸下不可读 —— '
                 'compact 200x240 窗口缩放 0.196, 整只开口只有约 12x16 屏幕 px, 单根手指宽约 2px, '
                 '拇指+食指围出的心形在任何缩放下都读不出来 ⇒ 本轮采用"双手合拢 + 爱心特效"的可读性方案。'),
        'source': 'R158 局部烘焙 (arm_rig + head_transform + face_swap + prop_heart)',
    },
    'cheer_clap': {
        'frames': [f'{R158}/cheer_clap_{i}.png' for i in range(3)],
        'frame_ms': [170, 260, 300],
        'loop': False,
        'anchor': 'stand',
        'desc': ('鼓掌: 双臂向两侧张开(准备) → 双手在身前合拢(闭眼笑) → 再张开。'
                 '张/合两种剪影差异明显, 与"比心"(始终合拢+爱心特效)可区分。'),
        'source': 'R158 局部烘焙 (arm_rig + head_transform + face_swap)',
    },
    'cheer_jump': {
        'frames': [f'{R158}/cheer_jump_{i}.png' for i in range(3)],
        'frame_ms': [150, 330, 190],
        'loop': False,
        'anchor': 'stand',
        'ground_tex_y': [None, 1015, None],
        'desc': ('开心跳跃: 蓄力下蹲(压扁 20%) → 腾空(**双臂上扬** + 仰头 + 闭眼笑 + 离地) → 落地压缩(16%)。'
                 'R158 改进点 = 腾空帧加了手臂动作与头部上仰; 离地量仍由运行时 ground_tex_y 实现, '
                 '上限受窗口高度硬约束(standard 256x256 头顶只剩 11px 余量, 故离地 ≤7 屏幕 px), '
                 '不能靠纹理内挪动硬凑。'),
        'source': 'R158 局部烘焙 (arm_rig + body_shift + head_transform + face_swap)',
    },
    'cheer_tilt': {
        'frames': [f'{R158}/cheer_tilt_{i}.png' for i in range(3)],
        'frame_ms': [210, 260, 330],
        'loop': False,
        'anchor': 'stand',
        'desc': ('歪头眨眼卖萌: 歪头 17° 睁眼 → 歪头 17° 眯眼 → 轻歪头 12° 闭眼笑。'
                 '角度与 R153 head_tilt(11°)/R153 happy(9°)/R156 cheer_wink(14°/7°) 都不重合, '
                 '烘焙唯一性自检保证新帧与既有帧无字节重复。'),
        'source': 'R158 局部烘焙 (head_transform + face_swap)',
    },
}

# ---------- R156 的 5 个几何形变动作下架 (R158 规则: 禁止用压缩/平移/重命名冒充) ----------
REMOVE_ACTIONS = ['cheer_heart', 'cheer_jump', 'cheer_spin', 'cheer_wink',
                  'cheer_hands', 'cheer_sway']

CLICK_POOL = [
    {'action': 'cheer_wave', 'weight': 3, 'desc': '真挥手 (手臂骨架, 手腕摆动)'},
    {'action': 'cheer_hands_up', 'weight': 3, 'desc': '双臂高举欢呼'},
    {'action': 'cheer_heart', 'weight': 3, 'desc': '比心 (双手合拢 + 爱心特效)'},
    {'action': 'cheer_clap', 'weight': 2, 'desc': '鼓掌 (张开→合拢→张开)'},
    {'action': 'cheer_jump', 'weight': 2, 'desc': '开心跳跃 (双臂上扬 + 离地)'},
    {'action': 'cheer_tilt', 'weight': 3, 'desc': '歪头眨眼卖萌'},
]

PROP_HEART = {'file': f'{R158}/prop_heart.png',
               'desc': '爱心特效: 程序化矢量绘制, 叠在双手合拢处上方 (front 层)'}

# ---------------------------------------------------------------------------
# R165: 办公场景桌子拆成 back(台面+笔记本) / front(前沿+桌腿) 两个道具
#
#   病根: 整张桌子放在 front 层 ⇒ 角色 sprite 里的双手 (y567..641) 完全落在
#   桌板**上方**, 一根手指都碰不到桌面 ⇒ 用户看到的是"双手搭在腿上"。
#   桌子是一张横板, 正面视角下远端在角色身后、近端在角色身前 ⇒ 必须分层。
# ---------------------------------------------------------------------------
PROP_DESK_SURFACE = {
    'file': f'{R156}/prop_desk_surface.png',
    'desc': ('办公桌台面 + 笔记本电脑 (back 层, 角色坐在桌后): 台面远沿 y=556 / '
             '近沿 y=668, 笔记本盖板在角色右侧, 背板朝观众、屏幕朝角色; '
             '含双手落在台面上的接触阴影'),
}
PROP_DESC_UPDATE = {
    'prop_bed': '小床: 木架 + 床垫 + 枕头 + 床腿 (R165 重做: 床垫分顶面/侧面两层, 床品与被子同色系)',
    'prop_quilt': ('被子 (R165 重做): 上沿沿角色身体实测轮廓起伏, 4 长 3 短羽化弧形褶皱, '
                   '17px 翻折亮边, 对角柔和渐变; 左边界 x=416 不遮脸不切手, 下沿搭到床垫前沿'),
    'prop_moon': '月亮 + 小星 + 一小片淡月晕 (夜晚氛围辅助, 不做大块背景, 不喧宾夺主)',
    'prop_desk': '办公桌前沿厚边 + 两条桌腿 (front 层, 角色身前); 桌下留空, 靴子露出 ⇒ 读作坐着',
    'prop_screen_glow': '屏幕微光: 三块小柔光落在胸口/下巴/桌面上的双手, 不遮五官',
}


def bbox_of(rel):
    p = os.path.join(ASSETS, rel)
    if not os.path.exists(p):
        raise SystemExit(f'❌ 帧资源缺失: {rel}')
    bb = Image.open(p).convert('RGBA').getbbox()
    return [int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])]


def main():
    m = json.load(open(MANIFEST_PATH, encoding='utf-8'))
    m['version'] = 'R158-RUNTIME'

    lib = m.get('action_library') or {}
    lib_actions = dict(lib.get('actions') or {})
    lib_bboxes = dict(m['layout'].get('frame_bboxes') or {})

    # ---------- 1. 下架 R156 的几何形变点击动作 ----------
    for name in REMOVE_ACTIONS:
        lib_actions.pop(name, None)
        lib_bboxes.pop(name, None)
        if name in (m.get('click_reactions') or {}).get('pool', []):
            pass
    print(f'   下架 R156 点击动作: {", ".join(REMOVE_ACTIONS)}')

    # ---------- 2. 登记 R158 的 6 个动作 ----------
    for name, spec in LIBRARY_R158.items():
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
    lib['round'] = 'R158'
    lib['note'] = (lib.get('note', '') +
                   ' | R158: 点击互动池换成 6 个**真实**动作 (cheer_wave/cheer_hands_up/cheer_heart/'
                   'cheer_clap/cheer_jump/cheer_tilt, 每个 3 帧 开始/中间/结束)。'
                   '新增技术 arm_rig (36_R158_arm_rig.py): 描边阻隔洪水填充切出 R138 漏切的'
                   '"袖+袖口+张开的手", 肩/肘/腕圆形咬口三关节链 + 衣身边缘重建, '
                   '从而能真正把手臂摆到头上/胸前。'
                   'R156 的 cheer_spin(水平压缩冒充转身)/cheer_sway(整体平移)/cheer_heart(复用 idle_04 '
                   '"右手横在胸前")/cheer_wink/cheer_hands 已按 R158 规则下架。')
    lib['actions'] = lib_actions
    m['action_library'] = lib

    # ---------- 3. 点击互动池 ----------
    m['click_reactions'] = {
        'enabled': True,
        'round': 'R158',
        'note': ('R158: 点击反馈仍为**随机池**, 每次点击随机挑一个, 短时间内不重复上一次; '
                 '播放期间暂停普通 idle/walk/sleep 推进, 播完回到正常状态机。'
                 '6 个动作全部由 R158 手臂骨架/头部权重场/跳跃剪影**局部**处理生成, '
                 '没有用整体压缩/平移/重命名冒充新动作。'),
        'no_repeat_last': True,
        'pool': CLICK_POOL,
    }

    # ---------- 4. 道具: 保留 R156 全部场景, 只加爱心特效 ----------
    props = m.get('props') or {}
    libp = dict(props.get('library') or {})
    libp['prop_heart'] = PROP_HEART
    scenes = dict(props.get('scenes') or {})
    scenes['cheer_heart'] = {
        'floor_tex_y': 987,
        'back': [],
        'front': ['prop_heart'],
        'desc': '比心: 爱心特效叠在双手合拢处上方 (角色身前), 随动作淡入淡出',
    }
    # ---------- 4b. R165: 办公场景桌子分层 + 5 个道具文案更新 ----------
    libp['prop_desk_surface'] = PROP_DESK_SURFACE
    for _k, _v in PROP_DESC_UPDATE.items():
        if _k in libp:
            libp[_k] = dict(libp[_k])
            libp[_k]['desc'] = _v
    scenes['work'] = {
        'floor_tex_y': 1001,
        'back': ['prop_chair', 'prop_desk_surface'],
        'front': ['prop_desk', 'prop_screen_glow'],
        'desc': ('办公待机: 坐在转椅上, 台面在身后/身前分层 ⇒ 双手完整压在台面上; '
                 '笔记本电脑在右侧桌上, 屏幕朝角色 (观众看到背板), 屏幕微光落在脸与手上'),
    }
    props['enabled'] = True
    props['round'] = 'R165'
    props['library'] = libp
    props['scenes'] = scenes
    props['technique'] = ('程序化矢量绘制 (30_R156_props_bake.py + 37_R158_action_bake.py, '
                          '无外部素材/无 AI 生图)')
    m['props'] = props

    # ---------- 5. bbox 与说明 ----------
    m['layout']['frame_bboxes'].update(lib_bboxes)
    m['notes'] = [n for n in m.get('notes', [])
                   if not n.startswith('R156: 新增点击互动池')]
    m['notes'].append(
        'R158: 点击互动池换成 6 个真实动作 (cheer_wave/cheer_hands_up/cheer_heart/cheer_clap/'
        'cheer_jump/cheer_tilt) —— 18 张新烘焙帧在 character_R158/; '
        'R156 的几何形变点击动作 (cheer_spin/cheer_sway/cheer_heart/cheer_wink/cheer_hands) 已下架')
    m['notes'].append(
        'R158: 新增 arm_rig 技术 (36_R158_arm_rig.py) —— 把 R138 切层脚本漏掉的"张开的手"切出来, '
        '肩/肘/腕三关节圆形咬口旋转 + 摘袖后按行重建大褂边缘')
    m['notes'].append(
        'R158: R156 已完成的场景 (床+月亮+被子 / 小沙发 / 办公转椅+小桌+笔记本+屏幕微光) 与 work '
        '待机动作原样保留, 本轮未重做')

    m['r158_click_actions'] = {
        'round': 'R158',
        'goals': [
            '点击互动动作池 ≥5 种视觉上明确、动作含义清晰的互动 (实际 6 种)',
            '优先实现: 真正的比心 / 开心跳跃 / 挥手庆祝 / 歪头眨眼',
            '禁止用压缩、平移、重命名冒充新动作 ⇒ R156 的 4 个几何形变动作下架',
            '先评估素材可行性; 做不到的明确列出新素材需求, 不虚报 PASS',
        ],
        'asset_feasibility': [
            'R153/R156 的"R138 无手部素材"结论**是错的**: idle_00_base.png 里两只手都是张开的、'
            '5 指带描边; 真正缺的是"能把手臂摆到别的位置"的技术 ⇒ R158 用 arm_rig 补上',
            'R138 自己的切层脚本 (03_LAYERS/split_a1_layers.py) 漏切了画面左臂, '
            'LAYERS.json 只登记了 head/torso/leg_r/arm_r(arm_r = 胸前的拳头)',
            '全仓库逐目录核查: 只有**正面**素材, 无任何侧身/背面视图',
        ],
        'honest_limits': [
            '真正的 180° 背面转身**做不到** —— R138 全库只有正面素材; 程序化"合成背面"需要重画'
            '后脑勺+实验服背面(去前襟/胸牌/纽扣), 属于重画角色且质量不可控 ⇒ 本轮不做, '
            '输出精确的新素材需求清单 (见 new_asset_requests)',
            '手指级"比心"几何在桌宠实际显示尺寸下不可读 (整只开口约 12x16 屏幕 px, 单指宽约 2px) ⇒ '
            '比心用"双手合拢 + 爱心特效"实现, 并在动作描述里如实写明',
            '跳跃离地上限受**窗口高度**硬约束 (standard 256x256 头顶只剩 11px 余量 ⇒ 离地 ≤7 屏幕 px), '
            '已在 standard 模式下把 ground_tex_y 顶到 1015 (R156 同值, 已是上限)',
            '办公场景仍然只能做"看屏幕/思考/停顿", 做不到"敲键盘"手部动作 (R138 无键盘手部素材)',
        ],
        'new_asset_requests': [
            {
                'action': 'cheer_turn_180',
                'need': '真正的原地 180° 转身 (背面视图)',
                'spec': ('需要 4~6 张 1024x1024 正面→侧身(3/4)→背面→侧身→正面的连续帧, '
                         '每张保持 A1 母版身份一致(银白短发/冰蓝眼睛/白色实验服/科技研究员风格), '
                         '背面须为: 后脑勺发型 + 实验服背面(去掉前襟/胸牌/纽扣, 露出内搭深蓝衬衫)'),
                'acceptance': ('背面帧必须能被普通用户一眼认成"同一个角色转过去"; '
                               '正/背面的身高比例一致; 脚底纹理行一致 (987)'),
                'note': 'i2i 三/四视角在 R130 已连续三次失败 (身份漂移/姿态漂移), 且本轮禁止充值',
            },
            {
                'action': 'cheer_finger_heart',
                'need': '真正的手指比心 (拇指+食指围成心形)',
                'spec': ('需要 3 张手部特写或半身帧, 单手做手指心; '
                         '另需一张"双手捧心"备选'),
                'acceptance': '在 200x240 窗口缩放 0.196 下, 心形轮廓必须仍可读 (即心形尺寸 ≥12 屏幕 px)',
                'note': '现有开口手在该尺寸下只有约 12x16 屏幕 px, 单指宽约 2px, 无法围出可读心形',
            },
        ],
        'click_pool': [p['action'] for p in CLICK_POOL],
        'prop_scenes': sorted(scenes.keys()),
    }

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'✅ manifest 已更新: {MANIFEST_PATH}')
    print(f'   version = {m["version"]}')
    print(f'   action_library = {len(lib_actions)} 个动作')
    print(f'   click pool = {len(CLICK_POOL)} 个: ' + ', '.join(p["action"] for p in CLICK_POOL))
    print(f'   prop scenes = {len(scenes)} 个: ' + ', '.join(sorted(scenes)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
