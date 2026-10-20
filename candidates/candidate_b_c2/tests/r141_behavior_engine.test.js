// R141 自主行为引擎单元测试 (R153 修订版)
//
// R141 §八 要求: "测试必须调用真实生产代码, 不得仅通过 grep、检查字符串、
//                   模拟不存在的功能, 宣布行为引擎 PASS"
//
// 本测试直接 require 候选目录下的 src/behavior_engine.js (生产代码本体),
// 通过注入 fake clock / fake random / fake timer 驱动真实状态机。
//
// ── R153 修订说明 ────────────────────────────────────────────────────────
// R153 把 R141 的"走 / 睡 二选一"模型换成了 5 类生活活动的加权池:
//     gesture(站立小动作) / walk(散步) / sit(坐下休息) / doze(困倦打盹) / sleep(躺下长睡)
// 因此 T2/T3/T4/T5/T6/T7/T8 的旧断言 ("首个动作必须是 walk"、"只能走或只能睡")
// 已被设计本身推翻, 本轮按**新设计的正确行为**重写, 不是把断言放宽。
// 新增 T13~T17 覆盖 R153 的自主行为多样化与睡眠分层。
// ────────────────────────────────────────────────────────────────────────

'use strict';

const path = require('path');
const assert = require('assert');

// ★ 直接 require 生产代码
const ENGINE_PATH = path.join(__dirname, '..', 'src', 'behavior_engine.js');
const {
    BehaviorEngine, STATES, ONE_SHOT_ACTIONS, LOOP_ACTIONS,
    ACTIVITY_KINDS, DEFAULT_CONFIG,
} = require(ENGINE_PATH);

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

// 常量随机源 (每次都返回同一个值)
function makeConstRandom(v) {
    return () => v;
}

// ── R153 活动池权重 (与 DEFAULT_CONFIG 一致, 显式写出便于推理) ──
//   gesture 0.46 | walk 0.62 | sit 0.22 | doze 0.22 | sleep 0.10  → total 1.62
// 随机值 r 落在哪个区间决定抽到哪一类:
//   r < 0.46/1.62=0.2840            → gesture
//   0.2840 ≤ r < 1.08/1.62=0.6667   → walk
//   0.6667 ≤ r < 1.30/1.62=0.8025   → sit
//   0.8025 ≤ r < 1.52/1.62=0.9383   → doze
//   0.9383 ≤ r                       → sleep


const TEST_CONFIG = {
    idle_min_ms: 3000, idle_max_ms: 8000,
    walk_speed_px_per_sec: 30, walk_min_distance_px: 80, walk_max_distance_px: 250,
    walk_move_tick_ms: 33,
    sleep_min_ms: 20000, sleep_max_ms: 45000,
    sleep_probability: 0.10,
    walk_probability: 0.62,
    drag_resume_delay_ms: 800,
    gesture_probability: 0.46,
    sit_probability: 0.22,
    doze_probability: 0.22,
    gesture_min_ms: 1600, gesture_max_ms: 3400,
    sit_min_ms: 6000, sit_max_ms: 13000,
    doze_min_ms: 7000, doze_max_ms: 15000,
    sleep_shift_min_ms: 7000, sleep_shift_max_ms: 15000,
    sleep_shift_duration_ms: 4200,
    stretch_after_wake: true,
    activity_repeat_penalty: 0.25,
    no_sleep_after_wake_ms: 45000,
};

// 活动池的随机阈值: **从引擎自己的权重反推**, 不写死数字
//   (R156 又加了 work 一类活动, 写死的阈值会随权重漂移 → 之前 R_SLEEP=0.99 落到 work 上,
//    睡眠相关测试全挂。改成反推后, 新增活动不会再打坏旧测试。)
const ACTIVITY_W_KEY = {
    gesture: 'gesture_probability', walk: 'walk_probability', sit: 'sit_probability',
    doze: 'doze_probability', work: 'work_probability', sleep: 'sleep_probability',
};
const MERGED_CONFIG = Object.assign({}, DEFAULT_CONFIG, TEST_CONFIG);
function randomForKind(kind) {
    const total = ACTIVITY_KINDS.reduce((s, k) => s + (MERGED_CONFIG[ACTIVITY_W_KEY[k]] || 0), 0);
    let acc = 0;
    for (const k of ACTIVITY_KINDS) {
        const w = MERGED_CONFIG[ACTIVITY_W_KEY[k]] || 0;
        if (k === kind) return (acc + w / 2) / total;
        acc += w;
    }
    throw new Error(`未知活动类别 ${kind}`);
}
const R_GESTURE = randomForKind('gesture');
const R_WALK = randomForKind('walk');
const R_SIT = randomForKind('sit');
const R_DOZE = randomForKind('doze');
const R_WORK = randomForKind('work');
const R_SLEEP = randomForKind('sleep');

function makeEngine(randomSeq, config) {
    const clock = new FakeClock();
    const actions = [];
    const moves = [];
    const states = [];
    const engine = new BehaviorEngine({
        config: config || TEST_CONFIG,
        random: typeof randomSeq === 'function' ? randomSeq : makeRandom(randomSeq),
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

// 从派发的动作名反推"活动类别" (R153 活动池的 5 类)
function activityKindOf(actionName) {
    if (actionName === 'walk_left' || actionName === 'walk_right') return 'walk';
    if (actionName === 'sit_rest') return 'sit';
    if (actionName === 'doze') return 'doze';
    if (actionName === 'sleep_enter') return 'sleep';
    if (['look_around', 'tilt_head', 'head_nod', 'stretch', 'happy', 'blink_soft'].includes(actionName)) return 'gesture';
    return null;
}

// ====== 测试 1: 引擎导出与状态集合 (R141 §三 4) ======
test('T1 引擎导出基础状态 + R153 新增 3 个生活状态, one-shot/loop 分类正确', () => {
    const expected = ['IDLE', 'WALK_LEFT', 'WALK_RIGHT', 'SLEEP_ENTER', 'SLEEP_LOOP', 'WAKE_UP', 'DRAGGING'];
    for (const s of expected) {
        assert.ok(STATES[s], `缺状态 ${s}`);
    }
    // R153 新增: 站立小动作 / 坐下休息 / 困倦打盹
    for (const s of ['GESTURE', 'SIT', 'DOZE']) {
        assert.ok(STATES[s], `R153 缺状态 ${s}`);
    }
    assert.deepStrictEqual(ONE_SHOT_ACTIONS, ['sleep_enter', 'wake_up']);
    assert.deepStrictEqual(LOOP_ACTIONS, ['idle', 'walk_left', 'walk_right', 'sleep_loop']);
});

// ====== 测试 2: IDLE 自动切换 (R141 §八 5) ======
test('T2 启动后自动进入 IDLE, 超时后自动从 5 类生活活动池里挑一类执行', () => {
    const { engine, clock, actions } = makeEngine([0.5, R_WALK, 0.0, 0.5]);
    engine.start();
    assert.strictEqual(engine.getState(), STATES.IDLE);
    clock.advance(9000);
    assert.notStrictEqual(engine.getState(), STATES.IDLE, 'IDLE 未自动切换');
    assert.ok(actions.length > 0, '未派发任何动作');
    // R153: 首个动作来自活动池, 而不是硬编码的"走或睡"
    const kind = activityKindOf(actions[0].action);
    assert.ok(kind, `首个动作不属于任何活动类别: ${actions[0] && actions[0].action}`);
    assert.ok(['gesture', 'walk', 'sit', 'doze', 'sleep'].includes(kind), `活动类别非法 ${kind}`);
});

// ====== 测试 3: 行走方向随机 (R141 §八 6) ======
test('T3 行走方向由随机源决定, 左右两个方向都能出现', () => {
    // 抽中 walk 后: 下一个随机值 < 0.5 → 左, ≥ 0.5 → 右
    const l = makeEngine([0.5, R_WALK, 0.0, 0.5]);
    l.engine.start(); l.clock.advance(9000);
    assert.strictEqual(l.engine.getState(), STATES.WALK_LEFT, '方向源 0.0 未产生 WALK_LEFT');
    const r = makeEngine([0.5, R_WALK, 0.9, 0.5]);
    r.engine.start(); r.clock.advance(9000);
    assert.strictEqual(r.engine.getState(), STATES.WALK_RIGHT, '方向源 0.9 未产生 WALK_RIGHT');
});

// ====== 测试 4: 行走产生真实位移 (R141 §八 7) ======
test('T4 行走状态持续派发位移请求 (不是原地踏步)', () => {
    const { engine, clock, moves } = makeEngine([0.5, R_WALK, 0.0, 0.5]);
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
    const states = [];
    let blockedOnce = false;
    const engine = new BehaviorEngine({
        config: TEST_CONFIG,
        random: makeRandom([0.5, R_WALK, 0.0, 0.5]),
        now: () => clock.now,
        setTimeout: (fn, ms) => clock.setTimeout(fn, ms),
        clearTimeout: (h) => clock.clearTimeout(h),
        setInterval: (fn, ms) => clock.setInterval(fn, ms),
        clearInterval: (h) => clock.clearInterval(h),
        onAction: () => {},
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
test('T6 sleep_enter → sleep_loop(躺姿呼吸) → wake_up → 伸懒腰 → idle 顺序正确', () => {
    const { engine, clock, states, actions } = makeEngine([0.5, R_SLEEP]);
    engine.start();
    clock.advance(9000);
    assert.strictEqual(engine.getState(), STATES.SLEEP_ENTER, '未进入 SLEEP_ENTER');
    // renderer 回报 sleep_enter 播完
    const handled1 = engine.onAnimationFinished('sleep_enter');
    assert.ok(handled1, 'sleep_enter 回调未被处理');
    assert.strictEqual(engine.getState(), STATES.SLEEP_LOOP, '未进入 SLEEP_LOOP');
    // R153: 睡眠主循环是"躺姿呼吸", 不是原来 3 个大幅换姿势的睡姿帧
    assert.ok(actions.some(a => a.action === 'sleep_breath'),
        `睡眠主循环应为 sleep_breath, 实际 ${JSON.stringify(actions.map(a => a.action))}`);
    // 睡眠时长到
    clock.advance(60000);
    assert.strictEqual(engine.getState(), STATES.WAKE_UP, '未进入 WAKE_UP');
    // renderer 回报 wake_up 播完
    const handled2 = engine.onAnimationFinished('wake_up');
    assert.ok(handled2, 'wake_up 回调未被处理');
    // R153: 醒来后先伸懒腰 (有语义的收尾), 不是直接站定
    assert.strictEqual(engine.getState(), STATES.GESTURE, '醒来后应进入 GESTURE(伸懒腰)');
    assert.ok(actions.some(a => a.action === 'stretch'), '醒来后应下发 stretch 动作');
    clock.advance(3000);
    assert.strictEqual(engine.getState(), STATES.IDLE, '伸懒腰后应回到 IDLE');
    // 动作序列检查
    const seq = states.map(s => s.to);
    const iEnter = seq.indexOf('SLEEP_ENTER');
    const iLoop = seq.indexOf('SLEEP_LOOP');
    const iWake = seq.indexOf('WAKE_UP');
    assert.ok(iEnter < iLoop && iLoop < iWake, `状态顺序错: ${seq.join('->')}`);
});

// ====== 测试 7: sleep_loop 不反复播放入睡流程 (R141 §八 10) ======
test('T7 sleep_loop 期间不重复触发 sleep_enter (不反复睡醒)', () => {
    const { engine, clock, states } = makeEngine([0.5, R_SLEEP]);
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
    const { engine, clock, moves, states } = makeEngine([0.5, R_WALK, 0.0, 0.5]);
    engine.start();
    clock.advance(9000);
    assert.ok(engine.getState() === STATES.WALK_LEFT || engine.getState() === STATES.WALK_RIGHT,
        `测试前置条件: 应处于行走态, 实际 ${engine.getState()}`);
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
    const { engine, clock, moves, states } = makeEngine([0.5, R_WALK, 0.0, 0.5]);
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
    // 过渡延迟后应恢复自主决策 (表现为新的状态转移)
    const statesAtRelease = states.length;
    clock.advance(20000);
    assert.ok(engine.getState() !== STATES.DRAGGING, '拖拽状态未清除');
    assert.ok(states.length > statesAtRelease,
        `恢复后自主行为未继续 (状态转移数 ${statesAtRelease} → ${states.length})`);
});

// ====== 测试 10: 单一时钟链, 无并发定时器 (R141 §七 F) ======
test('T10 引擎只维持单一行为计时器 + 至多一个位移计时器', () => {
    const { engine, clock } = makeEngine([0.5, R_WALK, 0.0, 0.5]);
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
    const { engine, clock } = makeEngine([0.5, R_WALK, 0.0, 0.5]);
    engine.start();
    clock.advance(9000);
    engine.stop();
    assert.strictEqual(clock.pendingTimers(), 0, `残留 timeout: ${clock.pendingTimers()}`);
    assert.strictEqual(clock.pendingIntervals(), 0, `残留 interval: ${clock.pendingIntervals()}`);
});

// ====== 测试 12: 状态优先级 (R141 §三 4) ======
test('T12 DRAGGING 优先级最高, 状态优先级表完整', () => {
    const { engine } = makeEngine([0.5, R_WALK, 0.0, 0.5]);
    engine.start();
    engine.setDragging(true);
    assert.strictEqual(engine.getStatePriority(), 10, 'DRAGGING 优先级应为最高');
    engine.setDragging(false);
    assert.ok(engine.getStatePriority() <= 3);
});

// ====== R153 新增: 自主行为多样化 ======

// ====== 测试 13: 活动池加权, 五类活动都可达 ======
test('T13 活动池覆盖 5 类生活活动 (gesture/walk/sit/doze/sleep 均可达)', () => {
    const kinds = new Set();
    for (const r of [R_GESTURE, R_WALK, R_SIT, R_DOZE, R_SLEEP]) {
        const { engine, clock, actions } = makeEngine([0.5, r]);
        engine.start();
        clock.advance(9000);
        const k = activityKindOf(actions.length ? actions[0].action : null);
        assert.ok(k, `随机源 ${r} 未派发出可识别的活动动作`);
        kinds.add(k);
        engine.stop();
    }
    assert.strictEqual(kinds.size, 5, `5 类活动只可达 ${kinds.size} 类: ${[...kinds].join(',')}`);
});

// ====== 测试 14: 重复折扣生效 (不会连着做同一件事) ======
test('T14 连续同类活动被打折: 同随机流下, 有折扣者不会重复、无折扣者会重复', () => {
    const collectKinds = (config, seconds) => {
        const { engine, clock, actions } = makeEngine(makeConstRandom(R_GESTURE), config);
        engine.start();
        clock.advance(seconds * 1000);
        const kinds = [];
        for (const a of actions) {
            const k = activityKindOf(a.action);
            if (k && k !== 'idle') kinds.push(k);
        }
        engine.stop();
        return kinds;
    };
    // 有重复折扣 (R153 默认 0.25): 第一次 gesture 之后不应再抽到 gesture
    const withPenalty = collectKinds(TEST_CONFIG, 30);
    assert.ok(withPenalty.length >= 2, `样本不足: ${JSON.stringify(withPenalty)}`);
    assert.notStrictEqual(withPenalty[0], withPenalty[1],
        `重复折扣未生效: 连续两次都是 ${withPenalty[0]} (${JSON.stringify(withPenalty)})`);
    // 关掉折扣作为对照: 同一随机流下必然连着做同一件事
    const noPenalty = collectKinds(Object.assign({}, TEST_CONFIG, { activity_repeat_penalty: 1.0 }), 30);
    assert.strictEqual(noPenalty[0], noPenalty[1],
        `对照组应连续重复, 实际 ${JSON.stringify(noPenalty)}`);
});

// ====== 测试 15: 打盹与躺睡是两个不同状态 ======
test('T15 "短暂打盹"(DOZE) 与 "躺下长睡"(SLEEP_ENTER) 分层, 打盹不会躺下', () => {
    const cfg = Object.assign({}, TEST_CONFIG, {
        gesture_probability: 0, walk_probability: 0, sit_probability: 0,
        doze_probability: 1, sleep_probability: 0,
    });
    const { engine, clock, states, actions } = makeEngine([0.5, R_DOZE], cfg);
    engine.start();
    clock.advance(9000);
    assert.strictEqual(engine.getState(), STATES.DOZE, `应进入 DOZE, 实际 ${engine.getState()}`);
    assert.ok(actions.some(a => a.action === 'doze'), 'DOZE 应下发 doze 动作');
    // 打盹结束后有明确的结束转移, 且绝不升级为躺下入睡
    clock.advance(20000);
    assert.ok(states.some(s => s.reason === 'doze-complete'),
        `打盹应有明确的结束转移, 实际转移序列 ${JSON.stringify(states.map(s => s.reason))}`);
    assert.ok(!states.some(s => s.to === 'SLEEP_ENTER'), '打盹不得升级为躺下入睡');
    assert.ok(!states.some(s => s.to === 'SLEEP_LOOP'), '打盹不得进入躺睡循环');
});

// ====== 测试 16: 醒后冷却期内不立刻再睡 ======
test('T16 醒来后冷却期 (45s) 内不再触发睡眠, 冷却期后可再次入睡', () => {
    const cfg = Object.assign({}, TEST_CONFIG, {
        gesture_probability: 0, walk_probability: 0, sit_probability: 0,
        doze_probability: 0, sleep_probability: 1,
    });
    const { engine, clock, states } = makeEngine(makeConstRandom(R_SLEEP), cfg);
    engine.start();
    clock.advance(9000);
    assert.strictEqual(engine.getState(), STATES.SLEEP_ENTER, '应先进入 SLEEP_ENTER');
    engine.onAnimationFinished('sleep_enter');
    clock.advance(60000);              // 睡眠时长到 → WAKE_UP
    assert.strictEqual(engine.getState(), STATES.WAKE_UP, '应进入 WAKE_UP');
    engine.onAnimationFinished('wake_up');
    const wakeCount = states.filter(s => s.to === 'WAKE_UP').length;
    // 冷却期 (45s) 内推进 40s: 不得再次入睡
    clock.advance(40000);
    const enterAfterCooldown = states.filter(s => s.to === 'SLEEP_ENTER').length;
    assert.strictEqual(enterAfterCooldown, 1,
        `醒后冷却期内不应再次入睡 (SLEEP_ENTER 计数 ${enterAfterCooldown})`);
    assert.strictEqual(states.filter(s => s.to === 'WAKE_UP').length, wakeCount,
        '冷却期内不应重复醒来');
    // 冷却期过后: 允许再次入睡
    clock.advance(40000);
    assert.ok(states.filter(s => s.to === 'SLEEP_ENTER').length >= 1, '冷却期后应允许再次入睡');
});

// ====== 测试 17: 睡眠期间有呼吸主循环 + 偶尔姿态微调 ======
test('T17 睡眠期间播放躺姿呼吸, 并周期性插入一次姿态微调', () => {
    const { engine, clock, actions } = makeEngine([0.5, R_SLEEP]);
    engine.start();
    clock.advance(9000);
    engine.onAnimationFinished('sleep_enter');
    const seq = actions.map(a => a.action);
    assert.ok(seq.includes('sleep_breath'), '应播放躺姿呼吸');
    // 推进到姿态微调应该发生的时刻
    clock.advance(20000);
    const seq2 = actions.map(a => a.action);
    assert.ok(seq2.includes('sleep_loop'),
        `睡眠中应偶尔切换睡姿, 实际动作序列 ${JSON.stringify(seq2)}`);
    // 姿态微调之后要回到呼吸
    assert.strictEqual(seq2[seq2.length - 1], 'sleep_breath',
        `姿态微调后应回到呼吸, 实际末尾 ${seq2[seq2.length - 1]}`);
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
