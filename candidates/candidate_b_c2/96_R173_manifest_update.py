#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R173 manifest 更新 (幂等): 办公场景换成 3/4 构图 + 全内嵌图层。

要点:
  · action_library.actions.work.frames → assets/character_R173/work_{1,2}.png
  · props.scenes.work 的 back/front **清空** —— 椅子/桌面/键盘/显示器/双手
    全部画进角色帧内部 (PNG 内 z 序可控), 不再由运行时按 action 挂载道具。
    R172 的 prop_office_chair / prop_office_monitor 文件保留在 library 里
    (历史成果不删), 只是 work 场景不再引用。
  · layout.frame_bboxes.work 换成新帧的 bbox。
  · 新增 r173_office_scene 段 (根因 / 改法 / 诚实限制 / 验收口径)。

幂等: 重复执行结果一致。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
MANIFEST = os.path.join(ASSETS, 'character_R141_manifest.json')
R173 = os.path.join(ASSETS, 'character_R173')

FRAMES = ['character_R173/work_1.png', 'character_R173/work_2.png']

SCENE_DESC = (
    '办公 (R173 透视整改): 底图换成**真 3/4 坐姿** sleep_enter_01_sit '
    '(膝盖/脸都朝画面左) ⇒ 角色**面对显示器**。显示器移到画面左侧更深处, '
    '屏面正面朝右(面向角色)、观众从侧面看到被透视压缩的屏幕内容 ⇒ '
    '不再出现"人物坐在显示器背面"。桌面改成**斜向透视台面**(左端更远更高), '
    '角色坐在桌子右端, 桌面遮住膝盖(局部遮挡不是删除), 小腿与靴子在桌下完整可见。'
    '手的图层关系: 原手留在身体帧 → 桌面盖住原位 → 手的像素**复制一份压在键盘之上** '
    '⇒ 手掌不被键盘整体遮住, 指尖落在键区, 手臂→袖口→手腕→手指衔接全部来自原画。'
    '椅子/桌面/键盘/显示器/双手全部内嵌进角色帧, 故 back/front 道具列表为空。'
)

OFFICE_SCENE = {
    'title': 'R173 办公场景透视与手部遮挡最终整改 (真 3/4 侧前方构图)',
    'round_from': 172,
    'root_cause': (
        'R172 的两个硬伤是**同一个构图前提错误**的两个后果: '
        '(1) 底图是**正面坐姿**, 而显示器被画成"正面朝观众", '
        '⇒ 几何上人物坐在显示器背面; '
        '(2) 桌面放在 back 层, 正面躯干/大腿整片挡死台面 ⇒ 只能把手/下半身删掉或遮死。'
        'R172 把"正面坐姿 + 正对观众的显示器只能这样表达看得到屏幕内容"写进了 honest_limits, '
        '却仍当 PASS 交付 —— 本轮从**底图与透视**上换掉, 而不是继续平移手/桌子/显示器。'
    ),
    'changes': [
        '底图: assets/character_R138/sleep_enter/sleep_enter_01_sit.png (3/4 坐姿, 膝盖与视线都朝画面左); 脚底 1002 ≈ 地面行 1001, 无需平移',
        '显示器: 移到画面左侧更深处, 屏面正面朝右(面向角色), 远侧边明显更矮 ⇒ 上下边向右侧发散、收敛点在左 = "从侧面斜看"; 屏内蓝白科技界面 (标题条 + 侧栏 + 5 条粗代码行 + 状态块), 粗线条以保证 200×240 下仍读得出"有内容"',
        '桌面: 斜向透视台面 (远沿 x215→690 / 近沿 x165→640), 左端更远更高; 桌沿厚度 + 两条桌腿画在角色之后 (真正在身前)',
        '键盘: 四边形透视贴图 (键帽网格), 位于手正下方, 右端收在右掌之下',
        '手: 原手保留在身体帧 (袖口朝向不变) → 桌面盖住原位 → 手的像素复制一份压在键盘之上 ⇒ 手掌不被键盘整体遮住; work_1/work_2 手部位移 ±3/±5 纹理 px 形成可见打字微动作',
        '椅子: 只在角色右肩/背后露一条 (画全椅子会变成右边一个灰柜子抢主角)',
        'props.scenes.work 的 back/front 清空 —— 全部内嵌进角色帧 (运行时道具按 action 整组挂载, 无法逐帧换道具, 内嵌才控得住图层)',
    ],
    'honest_limits': [
        '**屏幕内容在 200×240 下只有约 34×48 px**, 只能读出"有蓝白界面内容", 读不出具体文字; 这是"从侧面斜看"的必然结果 (透视压缩), 要看清内容就得让屏幕正对观众 —— 而那正是 R172 被否掉的构图。',
        '**显示器仍是"屏面朝向右侧角色"的 2D 近似**: 屏幕的四边形按"远侧边更矮"的透视画, 但没法真的算出单应, 因为角色帧本身是 2D 贴图、无 3D 相机。',
        '**桌是偏高的**: 桌面远沿压在腕点下方 (手必须落在桌面上, 而原坐姿的手腕高度就在那儿), 所以读起来像**高脚桌/吧台桌 + 高凳**, 不是常规办公桌; 角色坐在办公转椅上, 桌面高度偏高的原因未在画面里解释。',
        '**打字动作是手的整体位移 (±3/±5 纹理 px = 200×240 下约 0.6~1 px)**, 不是逐键动画; 可见度有限。',
        '**膝/大腿被桌面遮住**, 小腿与靴子完整可见 —— 沿用 R172 的"局部遮挡腿, 不是删除"口径, 但比正面构图遮得更多。',
        'MAC_REAL_GUI_ACCEPTANCE = PENDING (未经用户真机肉眼确认)。',
    ],
    'verification': '96_R173_manifest_update.py (幂等) / 97_R173_scene_verify.py (客观判据)',
}


def main():
    with open(MANIFEST, encoding='utf-8') as f:
        m = json.load(f)

    # ---- action_library.work ----
    work = m['action_library']['actions']['work']
    work['frames'] = list(FRAMES)
    work['frame_ms'] = [2600, 2600]
    work['loop'] = True
    work['anchor'] = 'sit'
    work['ground_tex_y'] = 1001
    work['desc'] = ('在电脑前办公: work_1 低头看键盘 (手指按下) → work_2 抬头看屏幕 '
                    '(打字间隙的思考)。角色是 3/4 侧向坐姿, **面对**左侧斜置的显示器; '
                    '双手压在键盘上, 手掌不被键盘遮住; 桌下小腿与靴子完整可见。')
    work['source'] = ('R173 局部烘焙 (换 3/4 底图 sleep_enter_01_sit + 斜向透视桌面/键盘/'
                      '斜置显示器内嵌 + 手部图层压在键盘之上)')

    # ---- props.scenes.work: 全部内嵌, 道具列表清空 ----
    scenes = m['props']['scenes']
    sc = scenes.get('work') or {}
    sc['floor_tex_y'] = 1001
    sc['back'] = []
    sc['front'] = []
    sc['desc'] = SCENE_DESC
    scenes['work'] = sc

    # ---- layout.frame_bboxes.work ----
    import numpy as np
    from PIL import Image
    bbs = []
    for rel in FRAMES:
        a = np.asarray(Image.open(os.path.join(ASSETS, rel)).convert('RGBA'))[:, :, 3]
        ys, xs = np.nonzero(a > 0)
        bbs.append([int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1])
    m['layout']['frame_bboxes']['work'] = bbs

    # ---- R173 场景说明段 ----
    m['r173_office_scene'] = OFFICE_SCENE

    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    print('✅ manifest 已更新:')
    print('   work.frames =', work['frames'])
    print('   work bbox   =', bbs)
    print('   work props  = back', sc['back'], '/ front', sc['front'])


if __name__ == '__main__':
    main()
