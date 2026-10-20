#!/usr/bin/env python3
"""R153 manifest 修订器 (幂等, 可重放)。

变更:
  1. 行走整体错切归零 (skew_x = 0)
     原因: R147 加的"方向倾斜"在正面 3/4 视角下读作"身体前倾像要摔倒" (用户真机反馈)。
     R148 已把**步态本身**修对 (落地脚/鞋尖朝正确方向), 方向不再需要靠剪切来表达 → 归零。
  2. 眨眼序列换成"手臂自然下垂的闭眼帧"
     原因: R138 的 idle_04 不是眨眼帧, 它是**右手横在胸前**的姿势;
     R147 的眨眼序列 [4,5] 用了它 → 站立时每 1.6~3.4s 手就抽到胸前一下 (用户反馈"莫名抬手")。
     现在 blink_sequence = [5] (idle_05: 闭眼 + 手臂下垂), idle_04 列入永不播放的排除帧。
  3. 新增 action_library 段: R153 烘焙的 9 个新动作 (歪头/张望/点头/开心/柔和眨眼/
     伸懒腰/坐下休息/困倦打盹/躺姿呼吸), 帧资源与语义独立, 不是重命名或重复播放。
  4. layout.frame_bboxes 补齐新动作的实测 bbox (地面线/缩放核算的基础)。
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ASSETS = os.path.join(CAND, 'assets')
MANIFEST_PATH = os.path.join(ASSETS, 'character_R141_manifest.json')

R153 = 'character_R153'
R138 = 'character_R138'

# R153 动作库: 动作名 → (帧列表, 帧时长列表, 是否循环, 说明)
LIBRARY = {
    'look_around': ([f'{R153}/glance_left.png', f'{R153}/glance_right.png'],
                     [800, 800], True, '左右张望: 头部局部横移 + 微缩 + 微旋 (连续权重场变形, 非整体旋转)'),
    'tilt_head': ([f'{R153}/head_tilt.png', f'{R153}/head_tilt_other.png'],
                  [950, 950], True, '歪头观察: 头部绕颈部支点 ±11° 局部弯曲'),
    'head_nod': ([f'{R153}/head_nod.png', f'{R153}/head_nod_back.png'], [260, 380], False,
                 '点头回应: 头部下移+压扁 → 抬起回位 (两帧, 非定格)'),
    'happy': ([f'{R153}/happy.png'], [700], False, '开心反馈: 歪头 + 眯眼笑 (点击时使用)'),
    'blink_soft': ([f'{R153}/blink_half.png', f'{R153}/blink_closed.png'],
                   [130, 170], False, '柔和眨眼: 仅换眼部区域, 手臂始终自然下垂'),
    'stretch': ([f'{R138}/idle/idle_01_inhale_peak.png'], [1000], False,
                '伸懒腰: 复用 R138 idle_01 (双臂抬起), 仅在"醒来后伸展"这一明确语义下播放'),
    'sit_rest': ([f'{R138}/sleep_enter/sleep_enter_01_sit.png'], [1500], True,
                 '坐下休息: 复用 R138 坐姿, 作为独立活动持续一段时间', 'sit'),
    'doze': ([f'{R153}/doze_sit.png'], [1600], True,
             '困倦打盹: 坐姿 + 闭眼 (仅换眼部区域)', 'sit'),
    'sleep_breath': ([f'{R153}/sleep_breath_in.png', f'{R153}/sleep_breath_out.png'],
                     [1500, 1500], True,
                     '躺姿呼吸: 仅胸口软遮罩区域垂直微缩, 头顶与脚底固定', 'lie'),
}

# R153: 帧级溶解时长 (一次性动画**内部**换帧时用)
#   实测根因: sleep_enter 第 0 帧本身就是坐姿, 所以动作级 "sit→sleep_enter" 的溶解
#             实际是"坐→坐"(看不出变化); 真正的躺姿出现在换帧那一瞬, 是硬切。
#             ⇒ 帧级溶解才是"坐下→躺下"的真过渡。
FRAME_BLEND_MS = {
    'sleep_enter': 320,   # 坐 → 躺 (最关键的一处)
    'wake_up': 280,       # 躺 → 坐起 → 站
    'head_nod': 180,      # 点头 → 回位
}


def bbox_of(rel):
    p = os.path.join(ASSETS, rel)
    if not os.path.exists(p):
        raise SystemExit(f'❌ 帧资源缺失: {rel}')
    bb = Image.open(p).convert('RGBA').getbbox()
    return [int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])]


def main():
    m = json.load(open(MANIFEST_PATH, encoding='utf-8'))
    m['version'] = 'R153-RUNTIME'

    # ---------- 1. 行走错切归零 ----------
    m['actions']['walk_left']['lean'] = {
        'skew_x': 0.0,
        'pivot_y': 921.6,
        'direction': -1,
        'note': ('R153: 整体错切归零 —— R147 的方向倾斜在正面 3/4 视角下被用户读作'
                 '"身体明显前倾像要摔倒"; R148 已把步态本身修对 (落地脚/鞋尖朝正确方向), '
                 '方向不再需要靠剪切表达, 归零后重心端正'),
    }
    m['actions']['walk_right']['lean'] = {
        'skew_x': 0.0,
        'pivot_y': 921.6,
        'direction': 1,
        'note': ('R153: 同 walk_left, 整体错切归零 (同上); R148 的派生镜像帧自带正确的迈步方向'),
    }
    m['actions']['walk_left']['note'] = (
        'R147/R148: 4 帧为已确认**方向正确**的向左步态 (落地脚在左、鞋尖朝左, '
        '由 18_R148_direction_verify.py 客观测量确认); R153 去掉整体倾斜, 重心端正')
    m['actions']['walk_right']['note'] = (
        'R148: 由 walk_left 4 帧整体水平镜像 + 徽章归位派生 (落脚脚在右、鞋尖朝右); '
        'R153 去掉整体倾斜, 重心端正')

    # ---------- 2. 眨眼序列: 换掉"手放胸前"的 idle_04 ----------
    idle = m['actions']['idle']
    idle['director'] = {
        'enabled': True,
        'base_index': 0,
        'blink_sequence': [5],
        'blink_frame_ms': [130],
        'blink_interval_ms': [1600, 3400],
        'excluded_frames': [1, 2, 3, 4],
        'note': ('R153: blink_sequence 由 [4,5] 改为 [5] —— idle_04 并不是眨眼帧, '
                 '它是**右手横在胸前**的姿势, 站立时每 1.6~3.4s 抽手到胸前会被读成"莫名抬手"; '
                 'idle_05 是纯闭眼且手臂下垂。idle_04 与胸腔膨胀帧 1/2/3 一并列入永不播放的排除帧'),
    }
    idle['note'] = ('R153: 播放序列 = 稳定站姿(idle_00) + 自然眨眼(idle_05); '
                    'idle_01/02/03 (胸腔膨胀) 与 idle_04 (手放胸前) 永不播放')

    # ---------- 3. 动作库 ----------
    lib_actions = {}
    lib_bboxes = {}
    for name, spec in LIBRARY.items():
        frames, fms, loop, desc = spec[0], spec[1], spec[2], spec[3]
        anchor = spec[4] if len(spec) > 4 else 'stand'
        entry = {
            'frames': frames,
            'frame_ms': fms,
            'loop': loop,
            'anchor': anchor,
            'desc': desc,
            'source': 'R153 局部烘焙' if frames[0].startswith(R153) else 'R138 既有帧 (语义化复用)',
        }
        if name in FRAME_BLEND_MS:
            entry['frame_blend_ms'] = FRAME_BLEND_MS[name]
        lib_actions[name] = entry
        lib_bboxes[name] = [bbox_of(f) for f in frames]
    m['action_library'] = {
        'enabled': True,
        'round': 'R153',
        'note': ('R153 新增动作库: 每个动作都有独立帧资源与独立语义 (禁止重命名/重复播放/整体旋转虚增)。'
                 '所有新帧由 22_R153_pose_bake.py 基于现有素材做**局部**处理生成: '
                 '眼部区域合成 / 头部连续权重场弯曲 / 胸口软遮罩微缩'),
        'actions': lib_actions,
    }
    m['layout']['frame_bboxes'].update(lib_bboxes)

    # ---------- 3b. 帧级溶解 (坐→躺 的真过渡) ----------
    for action, ms in FRAME_BLEND_MS.items():
        if action in m['actions']:
            m['actions'][action]['frame_blend_ms'] = ms
    m['actions']['sleep_enter']['frame_blend_ms_note'] = (
        'R153: 帧级溶解 320ms —— sleep_enter 第 0 帧本身就是坐姿, 动作级溶解是"坐→坐"(无变化); '
        '真正的躺姿出现在换帧那一瞬, 用帧级溶解把它变成渐变过渡 (修复"坐下瞬间变成躺姿")')
    m['actions']['wake_up']['frame_blend_ms_note'] = (
        'R153: 帧级溶解 280ms —— 躺→坐起→站 的两处大姿态变化都走渐变')

    # ---------- 4. 顶层说明 ----------
    m['notes'] = [
        'R141 运行时 manifest: 帧路径相对本 manifest 所在目录 (assets/character_R141_manifest.json -> character_R138/...)',
        'R138 六组动作 23 帧全部为 1024x1024 RGBA PNG (R153 起**逐字节未变**)',
        'sleep_enter / wake_up 为一次性动画, 由 renderer 播完回报主进程',
        'R148: walk_right 运行时使用 4 张派生帧 (character_R138_derived/walk_right_mirror/)',
        'R153: 新增 action_library 段 (9 个新动作, 12 张新烘焙帧在 character_R153/); '
        '核心 6 组动作的帧槽位仍是 23 个互不相同的文件',
        'R153: 行走整体错切归零 (用户反馈"身体前倾像摔倒"), 方向由 R148 的步态本身承担',
    ]
    m['r153_action_naturalness'] = {
        'issues_from_user': [
            '启动/点击时莫名抬手、手放胸前 → 根因: idle_04 是手放胸前的姿势却被当作眨眼帧使用',
            '坐下后瞬间变成躺姿 → 根因: sleep_enter 只有 sit→lie→settled 三帧, 无过渡',
            '行走时身体明显前倾像要摔倒 → 根因: R147 的整体错切 skew_x',
            '动作太少、行为重复 → 根因: 只有 6 组动作 + 机械的 走→停→睡→醒 循环',
        ],
        'fixes': [
            '眨眼序列改为 [5] (纯闭眼, 手臂下垂); idle_04 列入永不播放',
            '点击反馈改为 R153 烘焙的"歪头+眯眼笑" (happy), 不再复用手放胸前帧',
            '行走 skew_x 归零',
            '新增 action_library 9 个动作; 引擎改为加权活动池 + 不重复上次 + 自然停顿',
            '新增动作过渡交叉溶解 (sit→lie / doze→lie 等), 消除姿态瞬切',
        ],
    }

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'✅ manifest 已更新: {MANIFEST_PATH}')
    print(f'   version = {m["version"]}')
    print(f'   walk_left.skew_x = {m["actions"]["walk_left"]["lean"]["skew_x"]} / '
          f'walk_right.skew_x = {m["actions"]["walk_right"]["lean"]["skew_x"]}')
    print(f'   idle.blink_sequence = {idle["director"]["blink_sequence"]} '
          f'excluded = {idle["director"]["excluded_frames"]}')
    print(f'   action_library = {len(lib_actions)} 个动作: {", ".join(lib_actions)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
