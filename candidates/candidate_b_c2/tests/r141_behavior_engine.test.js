// R141 自主行为引擎单元测试
//
// R141 §八 要求: "测试必须调用真实生产代码, 不得仅通过 grep、检查字符串、
//                   模拟不存在的功能, 宣布行为引擎 PASS"
//
// 本测试直接 require 候选目录下的 src/behavior_engine.js (生产代码本体),
// 通过注入 fake clock / fake random / fake timer 驱动真实状态机。
//
// 覆盖 R141 §八 测试项: 5, 6, 8, 9, 10, 11, 12

'use strict';

const path = require('path');
const assert = require('assert');

// ★ 直接 require 生产代码
const ENGINE_PATH = path.join(__dirname, '..', 'src', 'behavior_engine.js');
const { BehaviorEngine, STATES, ONE_SHOT_ACTIONS, LOOP_ACTIONS } = require(ENGINE_PATH);

const results = [];
function test(name, fn) {
    try {
        fn();
        results.push({ name, pass: true });
        console.log(`  ✅ ${name}`);
    } catch (e) {
        results.push({ name, pass: false, error: e.message });
        console.log(`  ❌ ${name}\n      ${e.message}`);
    }
}

// ====== Fake 时钟 / 定时器 / 随机源 ======
class FakeClock {
    constructor() {
        this.now = 1000000;
        this.timers = new Map();
        this.intervals = new Map();
        this.nextId = 1;
    }
    setTimeout(fn, ms) {
        const id = this.nextId++;
        this.timers.set(id, { fn, at: this.now + (ms || 0) });
        return id;
    }
    clearTimeout(id) { this.timers.delete(id); }
    setInterval(fn, ms) {
        const id = this.nextId++;
        this.intervals.set(id, { fn, every: Math.max(1, ms || 1), next: this.now + Math.max(1, ms || 1) });
        return id;
    }
    clearInterval(id) { this.intervals.delete(id); }
    // 推进时间, 触发所有到期定时器
    advance(ms) {
        const target = this.now + ms;
        let guard = 0;
        while (guard++ < 100000) {
            let nextTimerAt = Infinity;
            for (const t of this.timers.values()) nextTimerAt = Math.min(nextTimerAt, t.at);
            for (const i of this.intervals.values()) nextTimerAt = Math.min(nextTimerAt, i.next);
            if (nextTimerAt > target) break;
            this.now = nextTimerAt;
            // 先跑 timeout
            for (const [id, t] of [...this.timers.entries()]) {
                if (t.at <= this.now) {
                    this.timers.delete(id);
                    t.fn();
                }
            }
            // 再跑 interval
            for (const [id, i] of [...this.intervals.entries()]) {
                if (i.next <= this.now) {
                    i.next = this.now + i.every;
                    i.fn();
                }
            }
        }
        this.now = target;
    }
    pendingTimers() { return this.timers.size; }
    pendingIntervals() { return this.intervals.size; }
}

// 确定性随机源: 依次返回给定序列, 之后循环
function makeRandom(seq) {
    let i = 0;
    return () => {
        const v = seq[i % seq.length];
        i++;
        return v;
    };
}

function makeEngine(randomSeq, config) {
    const clock = new FakeClock();
    const actions = [];
    const moves = [];
    const states = [];
    const engine = new BehaviorEngine({
        config: config || {},
        random: makeRandom(randomSeq),
        now: () => clock.now,
        setTimeout: (fn, ms) => clock.setTimeout(fn, ms),
        clearTimeout: (h) => clock.clearTimeout(h),
        setInterval: (fn, ms) => clock.setInterval(fn, ms),
        clearInterval: (h) => clock.clearInterval(h),
        onAction: (a, s) => actions.push({ action: a, state: s }),
        onMove: (dx, s) => { moves.push({ dx, state: s }); return { blocked: false }; },
        onState: (from, to, reason) => states.push({ from, to, reason }),
    });
    return { engine, clock, actions, moves, states };
}

// ====== 测试 1: 引擎导出与状态集合 (R141 §三 4) ======
test('T1 引擎导出 7 个基础状态 + one-shot/loop 分类正确', () => {
    const expected = ['IDLE', 'WALK_LEFT', 'WALK_RIGHT', 'SLEEP_ENTER', 'SLEEP_LOOP', 'WAKE_UP', 'DRAGGING'];
    for (const s of expected) {
        assert.ok(STATES[s], `缺状态 ${s}`);
    }
    assert.deepStrictEqual(ONE_SHOT_ACTIONS, ['sleep_enter', 'wake_up']);
    assert.deepStrictEqual(LOOP_ACTIONS, ['idle', 'walk_left', 'walk_right', 'sleep_loop']);
});

// ====== 测试 2: IDLE 自动切换 (R141 §八 5) ======
test('T2 启动后自动进入 IDLE 并在超时后自动切换行为 (无需用户按键)', () => {
    const { engine, clock, actions } = makeEngine([0.5, 0.9, 0.0, 0.5]);  // #1 idle时长 #2 0.9->走 #3 0.0->左 #4 距离
    engine.start();
    assert.strictEqual(engine.getState(), STATES.IDLE);
    // 前进超过 idle_max_ms
    clock.advance(9000);
    assert.notStrictEqual(engine.getState(), STATES.IDLE, 'IDLE 未自动切换');
    assert.ok(actions.length > 0, '未派发任何动作');
    assert.ok(['walk_left', 'walk_right'].includes(actions[0].action),
        `首个动作应为 walk, 实际 ${actions[0] && actions[0].action}`);
});

// ====== 测试 3: 行走方向随机 (R141 §八 6) ======
test('T3 行走方向由随机源决定, 左右两个方向都能出现', () => {
    const seen = new Set();
    // 两个方向各跑一次: #2 决定走不走, #3 决定方向
    for (const seq of [[0.5, 0.9, 0.0, 0.5], [0.5, 0.9, 0.9, 0.5]]) {
        const { engine, clock } = makeEngine(seq);
        engine.start();
        clock.advance(9000);
        const st = engine.getState();
        if (st === STATES.WALK_LEFT || st === STATES.WALK_RIGHT) seen.add(st);
        engine.stop();
    }
    assert.ok(seen.size >= 1, '未产生任何行走状态');
    // 明确验证两个方向都可达
    const l = makeEngine([0.5, 0.9, 0.0, 0.5]);
    l.engine.start(); l.clock.advance(9000);
    assert.strictEqual(l.engine.getState(), STATES.WALK_LEFT, '方向源 0.0 未产生 WALK_LEFT');
    const r = makeEngine([0.5, 0.9, 0.9, 0.5]);
    r.engine.start(); r.clock.advance(9000);
    assert.strictEqual(r.engine.getState(), STATES.WALK_RIGHT, '方向源 0.9 未产生 WALK_RIGHT');
});

// ====== 测试 4: 行走产生真实位移 (R141 §八 7) ======
test('T4 行走状态持续派发位移请求 (不是原地踏步)', () => {
    const { engine, clock, moves } = makeEngine([0.5, 0.9, 0.0, 0.5]);
    engine.start();
    clock.advance(9000);
    assert.ok(moves.length > 0, '行走期间没有任何位移请求');
    const totalDx = moves.reduce((s, m) => s + Math.abs(m.dx), 0);
    assert.ok(totalDx > 10, `累计位移 ${totalDx} 太小, 疑似原地踏步`);
    // 位移方向一致 (同一方向连续走)
    const signs = new Set(moves.map(m => Math.sign(m.dx)));
    assert.strictEqual(signs.size, 1, '同一次行走内位移方向不一致');
});

// ====== 测试 5: 到达边缘自动转向 (R141 §八 8) ======
test('T5 撞到屏幕边缘自动转向 (edge-turn) 且不越界', () => {
    const clock = new FakeClock();
    const actions = [];
    const states = [];
    let blockedOnce = false;
    const engine = new BehaviorEngine({
        config: {},
        random: makeRandom([0.5, 0.9, 0.0, 0.5]),
        now: () => clock.now,
        setTimeout: (fn, ms) => clock.setTimeout(fn, ms),
        clearTimeout: (h) => clock.clearTimeout(h),
        setInterval: (fn, ms) => clock.setInterval(fn, ms),
        clearInterval: (h) => clock.clearInterval(h),
        onAction: (a) => actions.push(a),
        // 第一次移动返回 blocked, 模拟撞边
        onMove: (dx) => {
            if (!blockedOnce) { blockedOnce = true; return { blocked: true }; }
            return { blocked: false };
        },
        onState: (from, to, reason) => states.push({ from, to, reason }),
    });
    engine.start();
    clock.advance(9000);
    const turn = states.find(s => s.reason === 'edge-turn');
    assert.ok(turn, '未出现 edge-turn 状态转移');
    assert.ok(turn.from !== turn.to, '转向前后状态相同');
    assert.ok(['WALK_LEFT', 'WALK_RIGHT'].includes(turn.to), `转向目标非法 ${turn.to}`);
});

// ====== 测试 6: 睡眠流程顺序 (R141 §八 9) ======
test('T6 sleep_enter -> sleep_loop -> wake_up -> idle 顺序正确', () => {
    // random: 0.0 -> 选 sleep; 之后 0.0 -> 选 walk
    const { engine, clock, states, actions } = makeEngine([0.5, 0.0, 0.5, 0.9]);  // #1 idle #2 0.0->睡 #3 睡眠时长
    engine.start();
    clock.advance(9000);
    assert.strictEqual(engine.getState(), STATES.SLEEP_ENTER, '未进入 SLEEP_ENTER');
    // renderer 回报 sleep_enter 播完
    const handled1 = engine.onAnimationFinished('sleep_enter');
    assert.ok(handled1, 'sleep_enter 回调未被处理');
    assert.strictEqual(engine.getState(), STATES.SLEEP_LOOP, '未进入 SLEEP_LOOP');
    // 睡眠时长到
    clock.advance(60000);
    assert.strictEqual(engine.getState(), STATES.WAKE_UP, '未进入 WAKE_UP');
    // renderer 回报 wake_up 播完
    const handled2 = engine.onAnimationFinished('wake_up');
    assert.ok(handled2, 'wake_up 回调未被处理');
    assert.strictEqual(engine.getState(), STATES.IDLE, '未回到 IDLE');
    // 动作序列检查
    const seq = states.map(s => s.to);
    const iEnter = seq.indexOf('SLEEP_ENTER');
    const iLoop = seq.indexOf('SLEEP_LOOP');
    const iWake = seq.indexOf('WAKE_UP');
    assert.ok(iEnter < iLoop && iLoop < iWake, `状态顺序错: ${seq.join('->')}`);
});

// ====== 测试 7: sleep_loop 不反复播放入睡流程 (R141 §八 10) ======
test('T7 sleep_loop 期间不重复触发 sleep_enter (不反复睡醒)', () => {
    const { engine, clock, states } = makeEngine([0.5, 0.0, 0.5, 0.9]);
    engine.start();
    clock.advance(9000);
    engine.onAnimationFinished('sleep_enter');
    assert.strictEqual(engine.getState(), STATES.SLEEP_LOOP);
    const enterCountBefore = states.filter(s => s.to === 'SLEEP_ENTER').length;
    // sleep_loop 期间推进很长时间 (远超一个睡眠周期)
    clock.advance(200000);
    const enterCountAfter = states.filter(s => s.to === 'SLEEP_ENTER').length;
    assert.strictEqual(enterCountAfter, enterCountBefore,
        `sleep_loop 期间重复进入 SLEEP_ENTER (${enterCountBefore} -> ${enterCountAfter})`);
    // 且在这段时间内只应发生一次 WAKE_UP
    const wakeCount = states.filter(s => s.to === 'WAKE_UP').length;
    assert.ok(wakeCount <= 1, `sleep_loop 期间多次 WAKE_UP (${wakeCount})`);
});

// ====== 测试 8: 拖拽期间暂停自主行为 (R141 §八 11) ======
test('T8 拖拽期间自主行为暂停 (无位移派发, 无自动切换)', () => {
    const { engine, clock, moves, states } = makeEngine([0.5, 0.9, 0.0, 0.5]);
    engine.start();
    clock.advance(9000);
    assert.ok(engine.getState() === STATES.WALK_LEFT || engine.getState() === STATES.WALK_RIGHT);
    const movesBefore = moves.length;
    engine.setDragging(true);
    assert.strictEqual(engine.getState(), STATES.DRAGGING);
    // 拖拽期间推进 30 秒
    clock.advance(30000);
    assert.strictEqual(moves.length, movesBefore, '拖拽期间仍派发位移');
    const statesBefore = states.length;
    clock.advance(30000);
    assert.strictEqual(states.length, statesBefore, '拖拽期间仍发生状态切换');
});

// ====== 测试 9: 松开拖拽后恢复自主行为 (R141 §八 12) ======
test('T9 松开拖拽后经过渡延迟恢复自主行为', () => {
    const { engine, clock, moves } = makeEngine([0.5, 0.9, 0.0, 0.5]);
    engine.start();
    clock.advance(9000);
    engine.setDragging(true);
    clock.advance(5000);
    engine.setDragging(false);
    assert.strictEqual(engine.getState(), STATES.IDLE);
    // 过渡延迟内不应立刻移动
    const movesAtRelease = moves.length;
    clock.advance(200);
    assert.strictEqual(moves.length, movesAtRelease, '过渡延迟内不应位移');
    // 过渡延迟后应恢复
    clock.advance(10000);
    assert.ok(engine.getState() !== STATES.DRAGGING, '拖拽状态未清除');
    assert.ok(moves.length > movesAtRelease || engine.getState() !== STATES.IDLE,
        '恢复后自主行为未继续');
});

// ====== 测试 10: 单一时钟链, 无并发定时器 (R141 §七 F) ======
test('T10 引擎只维持单一行为计时器 + 至多一个位移计时器', () => {
    const { engine, clock } = makeEngine([0.5, 0.9, 0.0, 0.5]);
    engine.start();
    let maxTimers = 0;
    let maxIntervals = 0;
    for (let i = 0; i < 40; i++) {
        clock.advance(500);
        maxTimers = Math.max(maxTimers, clock.pendingTimers());
        maxIntervals = Math.max(maxIntervals, clock.pendingIntervals());
    }
    assert.ok(maxTimers <= 2, `并发 timeout 过多: ${maxTimers}`);
    assert.ok(maxIntervals <= 1, `并发 interval 过多: ${maxIntervals}`);
});

// ====== 测试 11: 停止后清理全部定时器 (R141 §六 7) ======
test('T11 stop() 后清理全部定时器, 无残留', () => {
    const { engine, clock } = makeEngine([0.5, 0.9, 0.0, 0.5]);
    engine.start();
    clock.advance(9000);
    engine.stop();
    assert.strictEqual(clock.pendingTimers(), 0, `残留 timeout: ${clock.pendingTimers()}`);
    assert.strictEqual(clock.pendingIntervals(), 0, `残留 interval: ${clock.pendingIntervals()}`);
});

// ====== 测试 12: 状态优先级 (R141 §三 4) ======
test('T12 DRAGGING 优先级最高, 状态优先级表完整', () => {
    const { engine } = makeEngine([0.5, 0.9, 0.0, 0.5]);
    engine.start();
    engine.setDragging(true);
    assert.strictEqual(engine.getStatePriority(), 10, 'DRAGGING 优先级应为最高');
    engine.setDragging(false);
    assert.ok(engine.getStatePriority() <= 3);
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R141 behavior engine 单元测试: ${passed} passed, ${failed} failed (共 ${results.length})`);

if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) {
        console.log(`  - ${r.name}: ${r.error}`);
    }
    process.exit(1);
}
process.exit(0);
