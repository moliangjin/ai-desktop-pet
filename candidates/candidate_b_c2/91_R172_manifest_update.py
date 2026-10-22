#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R172 manifest 更新器 —— 办公场景构图重做 (换底图 + 换图层归属 + 3/4 显示器)。

R167 的办公场景把"台面"放在 back 层, 正面坐姿的躯干/大腿正好压住台面 ⇒
R167 只能把角色下半身剪掉 (cut_lower_body), 用户 R172 真机截图确认:
双腿消失 + 电脑只剩深灰背板。

R172 的改法 (不改角色外观、不做 i2i):
  1. 底图: sleep_enter_01_sit (跪坐, 膝盖高抬) → wake_up_01_sit_up
     (**双腿下垂、靴子踩地**), 整帧下移 76px 使脚底对齐地面行 1001;
  2. 图层归属: 桌面 / 键盘 / 双手 **画进角色帧内部** (PNG 内可控 z 序)
     ⇒ 桌面遮住大腿 (局部遮挡腿, 不是删除下半身), 腿脚在桌下完整可见;
  3. 电脑: 不再画笔记本背板, 改画 **3/4 透视的显示器正面**, 屏内画蓝白科技界面/代码;
  4. 场景 back 层 = 办公转椅, front 层 = 显示器。

本脚本幂等: 重跑逐字节一致 (R170 修过 action_library.note / notes[] 追加的坑)。
"""
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
MANIFEST_PATH = os.path.join(ASSETS, 'character_R141_manifest.json')
R172 = 'character_R172'

PROP_LIBRARY = {
    'prop_office_chair': {
        'file': f'{R172}/prop_office_chair.png',
        'desc': ('办公转椅 (R172): 靠背 + 座面, 放在 back 层, 从角色肩/头两侧露出, '
                 '读作"她坐在办公椅上"。刻意不画中柱与五星脚 —— 角色坐在椅子上时'
                 '中柱正好落在两腿之间, 会在脚边露出一坨灰色异物。'),
    },
    'prop_office_monitor': {
        'file': f'{R172}/prop_office_monitor.png',
        'desc': ('3/4 透视的显示器正面 (R172): 屏内画蓝白科技界面 (标题栏 + 侧栏 + '
                 '代码行 + 状态块), 放在 front 层。取代 R167 的"笔记本背板" —— '
                 '那版观众只能看到一块石墨灰, 用户看不到任何屏幕内容。'),
    },
}

WORK_SCENE = {
    'floor_tex_y': 1001,
    'back': ['prop_office_chair'],
    'front': ['prop_office_monitor'],
    'desc': ('办公 (R172 构图重做): 底图换成 wake_up_01_sit_up —— **双腿下垂、靴子踩地的'
             '完整坐姿** (R167 的跪坐底图 + 剪下半身已废弃)。桌面/键盘/双手画进角色帧内部 '
             '(PNG 内 z 序: 身体 → 桌面 → 键盘 → 手 → 桌沿桌腿) ⇒ 桌面只遮住大腿, '
             '小腿与靴子在桌下完整可见。电脑不再是笔记本背板, 而是 **3/4 透视的显示器正面** '
             '(屏幕朝观众偏左), 屏内画蓝白科技界面/代码。back 层 = 办公转椅, front 层 = 显示器。'),
}

WORK_ACTION = {
    'frames': [f'{R172}/work_1.png', f'{R172}/work_2.png'],
    'frame_ms': [2600, 2600],
    'loop': True,
    'anchor': 'sit',
    'desc': ('在电脑前办公: work_1 低头看键盘 (手指按下) → work_2 抬头看屏幕 (打字间隙的思考)。'
             '双手压在键盘上, 完整坐姿 (双腿 + 靴子踩地) 可见。'),
    'source': 'R172 局部烘焙 (换底图 wake_up_01_sit_up + 桌面/键盘/手内嵌 + head_transform)',
    'ground_tex_y': 1001,
}

R172_SECTION = {
    'title': 'R172 办公场景构图重做 (恢复完整坐姿 + 3/4 透视电脑 + 可见屏幕内容)',
    'root_cause': (
        'R167 的设计前提是"台面在 back 层 ⇒ 正面坐姿的躯干/大腿整片挡住台面 ⇒ '
        '只能剪掉下半身"。这不是素材不够, 是**图层归属错了**。R172 不再剪身体, '
        '改为把桌面/键盘/双手画进角色帧内部 (PNG 内 z 序可控), 并把底图从跪坐的 '
        'sleep_enter_01_sit 换成双腿下垂的 wake_up_01_sit_up。'),
    'changes': [
        '底图: assets/character_R138/wake_up/wake_up_01_sit_up.png (双腿下垂/靴子踩地), '
        '整帧下移 76px 使脚底对齐地面行 1001',
        '桌面/键盘/双手/桌沿桌腿 全部内嵌进 character_R172/work_1.png 与 work_2.png',
        'R167 的 cut_lower_body (WORK_CUT_Y=592) 与 30_R156_props_bake.py 的'
        '笔记本背板 (LID_QUAD) 不再被 work 场景引用 (文件保留, 不删历史成果)',
        '电脑改为 3/4 透视显示器正面 (character_R172/prop_office_monitor.png), '
        '屏内画蓝白科技界面 (标题栏 + 侧栏 + 代码行 + 状态块)',
        '新增办公转椅 (character_R172/prop_office_chair.png) 作为 back 层道具',
    ],
    'honest_limits': [
        '**双手没有真正向内收到键盘中央** —— 坐姿底图的两只手腕间距实测 280 纹理 px, '
        '手臂总长 (肩→腕 227 px) 不够把手腕挪到角色中线附近, 强行平移会让手与袖口脱节。'
        '因此键盘按实际手位画成宽键盘 (344~692), 双手落在键区两端, 手指已旋转成"向前"方向。',
        '袖口在桌面远端被桌面遮住 (桌面远沿 y=620, 袖口 614~646) ⇒ 前臂与桌沿的衔接'
        '在 200×240 下只剩 2~3 屏幕 px, 肉眼读作"手臂伸到桌面上"。',
        '显示器是**正面 3/4 的屏幕**, 不是物理正确的背面同侧视角 —— 2D 插画里'
        '正面坐姿 + 正对观众的显示器只能这样表达"看得到屏幕内容"。',
        '打字动作是"手部整体上下 4 纹理 px"的一帧位移 + 头部抬头/低头, '
        '不是逐键动画 (键盘与桌面是场景道具, 运行时按 action 整组挂载, 不支持逐帧换道具)。',
        'MAC_REAL_GUI_ACCEPTANCE = PENDING (本轮只有脚本合成与真实 Electron 采集, '
        '未经用户真机肉眼确认)。',
    ],
    'verification': '91_R172_manifest_update.py (幂等) / 92_R172_scene_verify.py (客观判据)',
}


def measure(rel):
    im = Image.open(os.path.join(ASSETS, rel)).convert('RGBA')
    bb = im.getbbox()
    return [int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])] if bb else None


def main():
    with open(MANIFEST_PATH, encoding='utf-8') as f:
        m = json.load(f)

    props = m.setdefault('props', {})
    props.setdefault('enabled', True)
    lib = props.setdefault('library', {})
    for k, v in PROP_LIBRARY.items():
        lib[k] = dict(v)
    scenes = props.setdefault('scenes', {})
    scenes['work'] = dict(WORK_SCENE)

    lib_actions = m.setdefault('action_library', {}).setdefault('actions', {})
    lib_actions['work'] = dict(WORK_ACTION)

    layout = m.setdefault('layout', {})
    bbs = layout.setdefault('frame_bboxes', {})
    bbs['work'] = [measure('character_R172/work_1.png'),
                   measure('character_R172/work_2.png')]

    m['r172_office_scene'] = dict(R172_SECTION)

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f'✅ manifest 已更新: {MANIFEST_PATH}')
    print(f'   work frames  = {lib_actions["work"]["frames"]}')
    print(f'   work scene   = back={scenes["work"]["back"]} front={scenes["work"]["front"]}')
    print(f'   work bboxes  = {bbs["work"]}')
    print(f'   prop library = {len(lib)} 条')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
