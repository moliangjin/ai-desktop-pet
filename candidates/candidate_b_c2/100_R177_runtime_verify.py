#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R177 真实 Electron 运行时验证 (菜单 / 设置 / 心情 / 持久化 / 重启恢复)

【为什么必须真跑 Electron】
   单元测试只能证明"纯逻辑模块"的行为。本脚本启动**真实的 Electron 进程**,
   用与用户真机完全相同的代码路径 (右键菜单 → sendMenuCommand → BehaviorEngine.command)
   触发行为, 并从真实日志里取证:
     · 菜单命令真的驱动了**正式行为系统** (状态机转移 + 场景道具挂载)
     · 设置真的写进了本机文件, 真的在重启后被恢复
     · 设置面板真的能打开并读到本地设置
   全部判据都是**客观可复算**的 (日志行 + 磁盘文件 + 窗口尺寸), 不含主观判断。

【运行】
   python3 100_R177_runtime_verify.py            # 全量 (5 次真实启动, 约 70 秒)
   python3 100_R177_runtime_verify.py --quick    # 只跑设置写入 + 重启恢复 (3 次启动)

【产物】
   evidence_r177_runtime/  logs + 报告 JSON
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CAND = Path(__file__).resolve().parent
REPO = CAND.parent.parent
ELECTRON = CAND.parent / 'candidate_b_electronpixir' / 'node_modules' / '.bin' / 'electron'
MANIFEST = CAND / 'assets' / 'character_R141_manifest.json'
EVIDENCE = CAND / 'evidence_r177_runtime'

# 本轮要写入并验证恢复的设置 (故意用非默认值, 便于肉眼区分)
PATCH = {
    'pet_scale': 1.25,
    'activity_rate': 'high',
    'sleep_rate': 'low',
    'click_feedback': False,
    'launch_at_login': False,
}

BASE_COMPACT = (200, 240)     # compact 模式基础尺寸
EXPECT_SCALE = PATCH['pet_scale']
EXPECT_W = int(round(BASE_COMPACT[0] * EXPECT_SCALE))   # 250
EXPECT_H = int(round(BASE_COMPACT[1] * EXPECT_SCALE))   # 300

checks = []


def check(cid, name, ok, detail=''):
    checks.append({'id': cid, 'name': name, 'pass': bool(ok), 'detail': detail})
    mark = '✅' if ok else '❌'
    print(f'  {mark} {cid} {name}' + (f' — {detail}' if detail else ''))
    return ok


def run_electron(tag, args, seconds=16, user_data=None):
    """跑一次真实 Electron, 返回 (stdout+stderr, 退出码)。"""
    ud = user_data or (EVIDENCE / f'ud_{tag}')
    ud.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(ELECTRON), 'src/main.js',
        '--manifest', str(MANIFEST),
        '--mode', 'compact',
        '--x', '600', '--y', '300',
        # 注意: 必须是 --user-data-dir=<path> 这种带等号的写法。
        # Electron/Chromium 的命令行解析只认 "--switch=value"; 写成两个独立参数
        # (--user-data-dir <path>) 会被当成"没有值", 于是悄悄用回默认目录 ——
        # 本轮第一次跑就踩了这个坑 (设置写到了 ~/Library/Application Support/Electron)。
        '--user-data-dir=' + str(ud),
        '--quit-after', str(seconds),
    ] + args
    log_path = EVIDENCE / f'run_{tag}.log'
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(CAND), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=seconds + 45)
    text = proc.stdout.decode('utf-8', 'replace')
    log_path.write_text(text, encoding='utf-8')
    print(f'    · {tag}: {len(text.splitlines())} 行日志, 用时 {time.time() - t0:.1f}s → {log_path.name}')
    return text, ud


def dumps_of(text):
    """提取日志里所有 R177 DUMP JSON。"""
    out = []
    for line in text.splitlines():
        m = re.search(r'R177 DUMP (\{.*\})\s*$', line)
        if m:
            try:
                out.append(json.loads(m.group(1)))
            except Exception:
                pass
    return out


def find(text, needle):
    return needle in text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true', help='只跑设置写入 + 重启恢复')
    args = ap.parse_args()

    if not ELECTRON.exists():
        print(f'FATAL: electron 不存在: {ELECTRON}')
        return 2
    # 不删目录 (只覆盖同名日志), 避免误删历史证据
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    # 隔离: 清掉上一轮遗留的本地设置/心情文件, 保证"重启恢复"测的是本次真写进去的
    for tag in ('ud_A', 'ud_B', 'ud_C', 'ud_D', 'ud_E'):
        d = EVIDENCE / tag
        d.mkdir(parents=True, exist_ok=True)
        for fn in ('pet_settings.json', 'pet_mood_state.json'):
            f = d / fn
            if f.exists():
                f.unlink()

    print('R177 真实 Electron 运行时验证')
    print('=' * 64)

    # ================================================================
    # 运行 A: 写入设置 + 菜单命令"电脑办公" + 打印本地状态
    # ================================================================
    print('\n[运行 A] 应用设置 + 右键菜单命令(电脑办公) + 打印本地状态')
    a_log, a_ud = run_electron('A', [
        '--r177-apply-settings', json.dumps(PATCH, ensure_ascii=False),
        '--r177-command', 'work',
        '--r177-dump-settings',
    ], seconds=16)
    a_dumps = dumps_of(a_log)
    a_start = next((d for d in a_dumps if d.get('tag') == 'startup'), None)
    a_cmd = next((d for d in a_dumps if d.get('tag') == 'after-command'), None)

    check('A1', '本地存储目录 = 本次指定的 user-data-dir (确实写在本机, 不联网)',
          bool(a_start) and str(a_ud) in a_start.get('dir', ''),
          f"dir={a_start.get('dir') if a_start else 'N/A'}")
    check('A2', '设置通过 applySettingsPatch 写入成功',
          find(a_log, 'R177 APPLY_SETTINGS ok=true saved=true'),
          re.search(r'R177 APPLY_SETTINGS ok=.*', a_log).group(0) if find(a_log, 'R177 APPLY_SETTINGS') else '')
    check('A3', '设置文件已落盘 (pet_settings.json)',
          (a_ud / 'pet_settings.json').exists())
    if (a_ud / 'pet_settings.json').exists():
        disk = json.loads((a_ud / 'pet_settings.json').read_text(encoding='utf-8'))
        check('A4', '磁盘上的设置内容 = 写入的值 (逐字段)',
              all(disk.get(k) == v for k, v in PATCH.items()),
              json.dumps(disk, ensure_ascii=False))

    check('A5', '菜单命令走正式行为系统: ok=true 且状态机切到 WORK',
          find(a_log, 'R177 MENU command=work ok=true state=WORK'),
          re.search(r'R177 MENU command=work.*', a_log).group(0) if find(a_log, 'R177 MENU command=work') else '未出现')
    check('A6', '状态机留下 IDLE -> WORK 的正式转移记录',
          re.search(r'R141 STATE IDLE -> WORK', a_log) is not None,
          (re.search(r'R141 STATE IDLE -> WORK.*', a_log).group(0) if re.search(r'R141 STATE IDLE -> WORK', a_log) else '未出现'))
    check('A7', '渲染器真的切到了办公场景 (set-action work applied=true)',
          find(a_log, 'set-action work applied=true'),
          re.search(r'.*set-action work applied=true.*', a_log).group(0).strip() if find(a_log, 'set-action work applied=true') else '未出现')
    check('A8', '办公场景道具按 R173 口径处理 (家具已内嵌, 故 mounted=none)',
          find(a_log, 'R156 PROPS action=work scene=yes mounted=none'),
          re.search(r'.*R156 PROPS action=work.*', a_log).group(0).strip() if find(a_log, 'R156 PROPS action=work') else '未出现')
    m_a = re.search(r'R177 PET_SCALE scale=([\d.]+) viewport=(\d+)x(\d+) '
                    r'bounds=\(-?\d+,-?\d+,(\d+),(\d+)\)', a_log)
    check('A9', f'桌宠大小生效: 视口 = {BASE_COMPACT[0]}×{BASE_COMPACT[1]} × {EXPECT_SCALE} = {EXPECT_W}×{EXPECT_H} '
                 f'(且真实窗口尺寸一致)',
          bool(m_a) and int(m_a.group(4)) == EXPECT_W and int(m_a.group(5)) == EXPECT_H
          and float(m_a.group(1)) == EXPECT_SCALE,
          m_a.group(0) if m_a else '未出现')
    check('A10', '渲染画布与窗口同尺寸 (INITIAL_VIEWPORT)',
          f'R177 INITIAL_VIEWPORT {EXPECT_W}x{EXPECT_H}' in a_log,
          re.search(r'R177 INITIAL_VIEWPORT.*', a_log).group(0) if find(a_log, 'R177 INITIAL_VIEWPORT') else '未出现')
    check('A11', '频率档位换算正确并作用到引擎 (活动 high→间隔×0.6/权重×1.4, 睡眠 low→×0.35)',
          '"idle_interval":0.6' in a_log and '"activity_weight":1.4' in a_log and '"sleep_weight":0.35' in a_log,
          re.search(r'R177 RATE .*', a_log).group(0) if find(a_log, 'R177 RATE') else '未出现')
    check('A12', '点击反馈开关已下发到渲染器 (click_feedback=false)',
          find(a_log, 'R177 SETTINGS_CHANGED click_feedback=false'))
    check('A13', '心情状态文件已落盘 (pet_mood_state.json)',
          (a_ud / 'pet_mood_state.json').exists())
    check('A14', '退出前保存了心情状态',
          find(a_log, 'R177 MOOD_SAVED'))

    if args.quick:
        print('\n[quick 模式] 跳过道具/面板验证')
    else:
        # ============================================================
        # 运行 C: 菜单命令"吃水果" → 场景道具真的挂载
        # ============================================================
        print('\n[运行 C] 右键菜单命令(吃水果) → 场景道具挂载')
        c_log, c_ud = run_electron('C', ['--r177-command', 'eat_fruit'], seconds=16)
        check('C1', '吃水果命令走正式行为系统 (ok=true, state=EAT_FRUIT)',
              find(c_log, 'R177 MENU command=eat_fruit ok=true state=EAT_FRUIT'),
              re.search(r'R177 MENU command=eat_fruit.*', c_log).group(0) if find(c_log, 'R177 MENU command=eat_fruit') else '未出现')
        m = re.search(r'R156 PROPS action=eat_fruit scene=(\w+) mounted=([^\s]*)', c_log)
        check('C2', '吃水果场景道具真的挂载 (小凳 + 小边桌 + 果盘)',
              bool(m) and m.group(1) == 'yes' and 'none' not in (m.group(2) or ''),
              m.group(0) if m else '未出现')
        check('C3', '渲染器真的切到了吃水果动作',
              find(c_log, 'set-action eat_fruit applied=true'))

        # ============================================================
        # 运行 D: 菜单命令"睡觉" → 床/月亮/被子挂载
        # ============================================================
        print('\n[运行 D] 右键菜单命令(睡觉) → 床/月亮/被子挂载')
        d_log, d_ud = run_electron('D', ['--r177-command', 'sleep'], seconds=18)
        check('D1', '睡觉命令走正式行为系统 (ok=true, state=SLEEP_ENTER)',
              find(d_log, 'R177 MENU command=sleep ok=true state=SLEEP_ENTER'),
              re.search(r'R177 MENU command=sleep.*', d_log).group(0) if find(d_log, 'R177 MENU command=sleep') else '未出现')
        m2 = re.search(r'R156 PROPS action=sleep_breath scene=(\w+) mounted=([^\s]*)', d_log)
        check('D2', '睡眠场景道具真的挂载 (床 + 月亮 + 被子)',
              bool(m2) and m2.group(1) == 'yes' and 'prop_bed' in (m2.group(2) or ''),
              m2.group(0) if m2 else '未出现')

        # ============================================================
        # 运行 E: 设置面板能打开并读到本地设置
        # ============================================================
        print('\n[运行 E] 设置面板 (独立窗口) 打开并读取本地设置')
        e_log, e_ud = run_electron('E', ['--r177-panel'], seconds=14, user_data=a_ud)
        check('E1', '设置面板窗口被真实创建',
              find(e_log, 'R177 SETTINGS_WINDOW opened'))
        m3 = re.search(r'R177 PANEL_READY settings=(\{.*\})', e_log)
        panel_settings = json.loads(m3.group(1)) if m3 else None
        check('E2', '设置面板读到的是**磁盘上已保存**的设置',
              bool(panel_settings) and all(panel_settings.get(k) == v for k, v in PATCH.items()),
              m3.group(1) if m3 else 'PANEL_READY 未出现')

    # ================================================================
    # 运行 B: 重启 (同一个 user-data-dir) → 设置与心情状态是否恢复
    # ================================================================
    print('\n[运行 B] 重启程序 (同一个本地目录) → 验证"重启后正确恢复"')
    # 关键: 必须在 B 启动**之前**把磁盘上的心情状态拍个快照。
    #   B 进程退出时会再写一次心情文件, 事后读磁盘拿到的是"新写的内容", 不是 B 读进去的内容。
    mood_file = a_ud / 'pet_mood_state.json'
    pre_b_mood = json.loads(mood_file.read_text(encoding='utf-8')) if mood_file.exists() else None
    b_log, b_ud = run_electron('B', ['--r177-dump-settings'], seconds=12, user_data=a_ud)
    b_dumps = dumps_of(b_log)
    b_start = next((d for d in b_dumps if d.get('tag') == 'startup'), None)

    check('B1', '重启后设置逐字段恢复 (大小/活动频率/睡眠频率/点击反馈/自启)',
          bool(b_start) and all(b_start['settings'].get(k) == v for k, v in PATCH.items()),
          json.dumps(b_start.get('settings'), ensure_ascii=False) if b_start else 'N/A')
    check('B2', '重启后心情状态从磁盘恢复 (mood_restored_raw 非空)',
          bool(b_start) and b_start.get('mood_restored_raw') is not None,
          json.dumps(b_start.get('mood_restored_raw'), ensure_ascii=False) if b_start else 'N/A')
    if b_start and b_start.get('mood_restored_raw') and pre_b_mood:
        restored = b_start['mood_restored_raw']
        num_keys = ['energy', 'interactionCount', 'interactionWindowStart', 'lastInteractionAt',
                    'lastActivityAt', 'lastSleepAt', 'awakeSince', 'sleepCount']
        same = (pre_b_mood.get('mood') == restored.get('mood'))
        for k in num_keys:
            a_ = float(pre_b_mood.get(k, 0) or 0)
            b_ = float(restored.get(k, 0) or 0)
            if abs(a_ - b_) > 1e-6:
                same = False
        check('B3', '恢复的心情状态 = 启动时磁盘文件内容 (逐字段一致)',
              same,
              f"disk.mood={pre_b_mood.get('mood')} restored.mood={restored.get('mood')} "
              f"energy {pre_b_mood.get('energy')} → {restored.get('energy')}")
    else:
        check('B3', '恢复的心情状态 = 启动时磁盘文件内容 (逐字段一致)', False,
              f"pre_b_mood={pre_b_mood is not None} restored={b_start.get('mood_restored_raw') if b_start else None}")
    m_b = re.search(r'R177 PET_SCALE scale=([\d.]+) viewport=(\d+)x(\d+) '
                    r'bounds=\(-?\d+,-?\d+,(\d+),(\d+)\)', b_log)
    check('B4', f'重启后桌宠大小仍然生效 (视口与真实窗口尺寸都是 {EXPECT_W}×{EXPECT_H})',
          bool(m_b) and int(m_b.group(4)) == EXPECT_W and int(m_b.group(5)) == EXPECT_H
          and float(m_b.group(1)) == EXPECT_SCALE,
          m_b.group(0) if m_b else '未出现')
    check('B5', '重启后频率档位仍然作用到引擎',
          '"idle_interval":0.6' in b_log and '"sleep_weight":0.35' in b_log,
          re.search(r'R177 RATE .*', b_log).group(0) if find(b_log, 'R177 RATE') else '未出现')

    # ================================================================
    # 汇总
    # ================================================================
    passed = sum(1 for c in checks if c['pass'])
    failed = len(checks) - passed
    report = {
        'round': 'R177',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'electron': str(ELECTRON),
        'manifest': str(MANIFEST),
        'patch': PATCH,
        'checks': checks,
        'passed': passed,
        'failed': failed,
        'total': len(checks),
    }
    (EVIDENCE / 'r177_runtime_verify.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print('\n' + '=' * 64)
    print(f'R177 真实 Electron 运行时验证: {passed} PASS / {failed} FAIL (共 {len(checks)})')
    if failed:
        print('\n失败详情:')
        for c in checks:
            if not c['pass']:
                print(f"  - {c['id']} {c['name']}: {c['detail']}")
    print(f'报告: {EVIDENCE / "r177_runtime_verify.json"}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
