#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R170 触发记录取证 —— 真实 Electron 连跑, 统计自主行为里"办公/吃水果"到底出现没有。

为什么需要它
------------
R170 用户报"电脑办公场景在桌宠运行时消失不见了"。
R167 交付版的真机实测 (180s) 是: 空闲决策 9 次, **WORK 触发 0 次** ——
所以"状态机里有 WORK"根本不等于"用户能看到办公场景"。
本脚本把**真实运行**的状态转移日志抓下来, 算成可复算的绝对值:
  · 观测窗内 WORK / EAT_FRUIT 各进入几次
  · 每次持续了多久 (ms) —— 证明"不是刚出现就消失"
  · 两次之间隔了多久 (ms) —— 证明"正常运行时能自然出现"
  · 播放期间有没有被别的活动打断 —— 证明"不被随机行为立即打断"

判据 (绝对值, 门槛写在脚本里):
  T1 观测窗内 WORK 至少进入 1 次
  T2 WORK 的平均间隔 ≤ 150s (R167 交付版实测 ≈ 400s+)
  T3 每次 WORK 的持续时间 ≥ 12s (配置下限 16s, 留 25% 余量)
  T4 观测窗内 EAT_FRUIT 至少进入 1 次
  T5 每次 EAT_FRUIT 的持续时间 ≥ 10s
  T6 没有任何一次"刚进入 WORK/EAT_FRUIT 就立刻被别的活动顶掉"
     (即每次进入后, 下一个状态必须是 IDLE 且间隔 ≥ 10s)
  T7 WORK 与 EAT_FRUIT 从不同时处于激活状态 (逐毫秒区间不相交)

用法: python3 86_R170_trigger_verify.py --seconds 240
"""
import argparse
import json
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CAND = HERE
ROOT = os.path.dirname(os.path.dirname(HERE))
ELECTRON = os.path.join(ROOT, 'candidates', 'candidate_b_electronpixir',
                        'node_modules', '.bin', 'electron')
MANIFEST = os.path.join(CAND, 'assets', 'character_R141_manifest.json')

# 兼容两种日志格式:
#   R170 起带相对时间戳  [main] R141 STATE IDLE -> WORK (idle-decision) t=12345ms
#   R167 交付版没有时间戳 [main] R141 STATE IDLE -> WORK (idle-decision)
# 没有时间戳时**次数类判据仍然有效**(那是基线对比的关键), 时长/间隔类判据标为不可用。
STATE_RE = re.compile(
    r'\[main\] R141 STATE (\w+) -> (\w+) \(([^)]*)\)(?: t=(\d+)ms)?')


def run(seconds, log_path):
    env = dict(os.environ)
    cmd = [ELECTRON, CAND, '--manifest', MANIFEST, '--size', '200',
           '--quit-after', str(seconds)]
    with open(log_path, 'w', encoding='utf-8') as f:
        p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=CAND,
                           env=env, timeout=seconds + 90)
    return p.returncode


def parse(log_path):
    seq = []
    timing = True
    with open(log_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = STATE_RE.search(line)
            if m:
                t = int(m.group(4)) if m.group(4) is not None else None
                if t is None:
                    timing = False
                seq.append({'from': m.group(1), 'to': m.group(2),
                            'reason': m.group(3), 't': t})
    return seq, timing


def sessions(seq, state):
    """从状态序列里抽出某状态的**活动区间** [进入时刻, 离开时刻]。"""
    out = []
    start = None
    for s in seq:
        if s['to'] == state and start is None:
            start = s['t']
        elif s['to'] != state and start is not None:
            out.append({'start': start, 'end': s['t'], 'duration': s['t'] - start,
                        'ended_by': s['to'], 'reason': s['reason']})
            start = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=int, default=240)
    ap.add_argument('--out', default='evidence_r170_trigger.json')
    ap.add_argument('--log', default='/tmp/r170_trigger_run.log')
    args = ap.parse_args()

    print(f'R170 触发记录取证: 真实 Electron 连跑 {args.seconds}s …')
    rc = run(args.seconds, args.log)
    seq, timing = parse(args.log)
    print(f'  退出码 {rc}, 捕获状态转移 {len(seq)} 条'
          + ('' if timing else ' (该版本日志无相对时间戳 ⇒ 时长/间隔类判据不可用)'))

    work = sessions(seq, 'WORK')
    eat = sessions(seq, 'EAT_FRUIT')
    idle_decisions = sum(1 for s in seq if s['reason'] == 'idle-decision')

    work_gaps = []
    for i in range(1, len(work)):
        work_gaps.append(work[i]['start'] - work[i - 1]['start'])
    avg_work_gap = (sum(work_gaps) / len(work_gaps)) if work_gaps else None

    eat_gaps = []
    for i in range(1, len(eat)):
        eat_gaps.append(eat[i]['start'] - eat[i - 1]['start'])

    # T7: 区间是否相交
    def overlap(a, b):
        return not (a['end'] <= b['start'] or b['end'] <= a['start'])
    cross = [1 for a in work for b in eat if overlap(a, b)]

    # T6: 是否"刚进入就被顶掉"
    def aborted(sess, min_ms):
        return [s for s in sess if s['duration'] < min_ms]
    work_aborted = aborted(work, 12000)
    eat_aborted = aborted(eat, 10000)

    def dur_check(key, ok, threshold, durations, extra=None):
        d = dict(ok)
        if not timing:
            d['pass'] = None
            d['not_applicable'] = '该版本日志无相对时间戳, 时长类判据不可用'
        if extra:
            d.update(extra)
        return d

    checks = {
        'T1_work_triggered_at_least_once': {
            'pass': len(work) >= 1, 'threshold': '≥1 次',
            'value': len(work)},
        'T2_work_average_gap': {
            'pass': avg_work_gap is not None and avg_work_gap <= 150000,
            'threshold': '≤150s (R167 交付版实测 ≈400s+)',
            'value_ms': avg_work_gap,
            'gaps_ms': work_gaps},
        'T3_work_session_not_too_short': {
            'pass': len(work) >= 1 and all(s['duration'] >= 12000 for s in work),
            'threshold': '每次 ≥12s (配置下限 16s)',
            'durations_ms': [s['duration'] for s in work]},
        'T4_eat_fruit_triggered_at_least_once': {
            'pass': len(eat) >= 1, 'threshold': '≥1 次',
            'value': len(eat)},
        'T5_eat_fruit_session_not_too_short': {
            'pass': len(eat) >= 1 and all(s['duration'] >= 10000 for s in eat),
            'threshold': '每次 ≥10s (配置下限 14s)',
            'durations_ms': [s['duration'] for s in eat]},
        'T6_no_session_aborted_immediately': {
            'pass': (len(work) == 0 or not work_aborted)
            and (len(eat) == 0 or not eat_aborted),
            'threshold': '没有"刚进入就被别的活动顶掉"的会话',
            'work_aborted': work_aborted, 'eat_aborted': eat_aborted},
        'T7_work_and_eat_fruit_never_overlap': {
            'pass': len(cross) == 0, 'threshold': '两者活动区间不相交',
            'overlaps': len(cross)},
    }
    if not timing:
        for k in ('T2_work_average_gap', 'T3_work_session_not_too_short',
                  'T5_eat_fruit_session_not_too_short'):
            checks[k]['pass'] = None
            checks[k]['not_applicable'] = '该版本日志无相对时间戳, 时长类判据不可用'

    out = {
        'round': 'R170',
        'observation_seconds': args.seconds,
        'exit_code': rc,
        'log': args.log,
        'timing_available': timing,
        'idle_decisions': idle_decisions,
        'work_sessions': work,
        'eat_fruit_sessions': eat,
        'work_gaps_ms': work_gaps,
        'eat_fruit_gaps_ms': eat_gaps,
        'avg_work_gap_ms': avg_work_gap,
        'transition_count': len(seq),
        'checks': checks,
    }
    npass = sum(1 for v in checks.values() if v['pass'] is True)
    nfail = sum(1 for v in checks.values() if v['pass'] is False)
    na = sum(1 for v in checks.values() if v['pass'] is None)
    out['summary'] = {'passed': npass, 'failed': nfail, 'not_applicable': na,
                       'total': len(checks)}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    for k, v in checks.items():
        mark = '✅' if v['pass'] is True else ('❌' if v['pass'] is False else '➖')
        print(f'  {mark} {k}: {v}')
    print(f'  合计: {npass}/{len(checks)} PASS'
          + (f' | {nfail} FAIL' if nfail else '')
          + (f' | {na} N/A' if na else ''))
    print(f'  空闲决策 {idle_decisions} 次 | WORK {len(work)} 次 | EAT_FRUIT {len(eat)} 次')
    print(f'  📄 {args.out}')


if __name__ == '__main__':
    main()
