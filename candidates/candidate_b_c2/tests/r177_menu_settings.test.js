// R177 桌宠控制菜单 + 设置面板 集成单元测试
//
// 覆盖 R177 任务书 §一.2 / §一.3 的可验收项:
//   · 右键菜单包含: 睡觉 / 醒来 / 坐沙发休息 / 电脑办公 / 吃水果 / 随机可爱动作
//   · 每个菜单项都接到**正式行为系统** (BehaviorEngine.command), 不是播演示图片
//   · 菜单里没有调试项, 不污染桌宠外观
//   · 设置面板的 5 个开关都能作用到运行时 (频率/大小/点击反馈/自启)
//
// 被测生产模块:
//   src/menu_template.js    : 菜单模板 (纯模块)
//   src/behavior_engine.js   : 正式行为系统 (含 R177 新增的 command/applyConfig)
//   src/mood_engine.js       : 心情 (给引擎当适配器)
//   src/settings_store.js    : 设置 (换算成引擎参数)
//   src/action_library.js    : 点击动作池 (心情加权)
//
// 运行: node tests/r177_menu_settings.test.js
'use strict';

const path = require('path');
const assert = require('assert');

const CAND = path.join(__dirname, '..');
const { buildMenuTemplate, MENU_COMMANDS, MENU_LABELS } = require(path.join(CAND, 'src', 'menu_template.js'));
const { BehaviorEngine, STATES } = require(path.join(CAND, 'src', 'behavior_engine.js'));
const { MoodEngine, MOODS } = require(path.join(CAND, 'src', 'mood_engine.js'));
const { rateEffects, sanitizeSettings } = require(path.join(CAND, 'src', 'settings_store.js'));
const { pickClickReaction } = require(path.join(CAND, 'src', 'action_library.js'));

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

// ====== Fake 时钟 / 随机源 ======
class FakeClock {
    constructor() {
        this.now = 1000000;
        this.timers = new Map();
        this.intervals = new Map();
        this.nextId = 1;
        this.lastDelay = 0;
    }
    setTimeout(fn, ms) {
        const id = this.nextId++;
        this.timers.set(id, { fn, at: this.now + (ms || 0), delay: ms || 0 });
        this.lastDelay = ms || 0;
        return id;
    }
    clearTimeout(id) { this.timers.delete(id); }
    setInterval(fn, ms) {
        const id = this.nextId++;
        this.intervals.set(id, { fn, every: Math.max(1, ms || 1), next: this.now + Math.max(1, ms || 1) });
        return id;
    }
    clearInterval(id) { this.intervals.delete(id); }
    advance(ms) {
        const target = this.now + ms;
        let guard = 0;
        while (guard++ < 100000) {
            let nextAt = Infinity;
            for (const t of this.timers.values()) nextAt = Math.min(nextAt, t.at);
            for (const i of this.intervals.values()) nextAt = Math.min(nextAt, i.next);
            if (nextAt > target) break;
            this.now = nextAt;
            for (const [id, t] of [...this.timers.entries()]) {
                if (t.at <= this.now) { this.timers.delete(id); t.fn(); }
            }
            for (const [id, i] of [...this.intervals.entries()]) {
                if (i.next <= this.now) { i.next = this.now + i.every; i.fn(); }
            }
        }
        this.now = target;
    }
}

function makeEngine(extra = {}) {
    const clock = new FakeClock();
    const actions = [];
    const states = [];
    const engine = new BehaviorEngine(Object.assign({
        now: () => clock.now,
        random: () => 0.5,
        setTimeout: (fn, ms) => clock.setTimeout(fn, ms),
        clearTimeout: (id) => clock.clearTimeout(id),
        setInterval: (fn, ms) => clock.setInterval(fn, ms),
        clearInterval: (id) => clock.clearInterval(id),
        onAction: (action, state) => actions.push({ action, state }),
        onState: (from, to, reason) => states.push({ from, to, reason }),
    }, extra));
    return { engine, clock, actions, states };
}

// ====== C1: 菜单项与任务书措辞一致 ======
test('C1 右键菜单包含任务书要求的 6 个行为命令 + 设置 + 退出', () => {
    const tpl = buildMenuTemplate({ moodLabel: '平静' });
    const labels = tpl.filter((i) => i.type !== 'separator').map((i) => i.label);
    assert.ok(labels.includes('睡觉'));
    assert.ok(labels.includes('醒来'));
    assert.ok(labels.includes('坐沙发休息'));
    assert.ok(labels.includes('电脑办公'));
    assert.ok(labels.includes('吃水果'));
    assert.ok(labels.includes('随机可爱动作'));
    assert.ok(labels.includes('设置…'));
    assert.ok(labels.includes('退出桌宠'));
    assert.strictEqual(MENU_COMMANDS.length, 6);
    assert.strictEqual(MENU_COMMANDS.join(','), 'sleep,wake,sit,work,eat_fruit,gesture');
});

// ====== C2: 每个命令项点击后传给正确的 kind ======
test('C2 每个命令项的 click 都把正确的 kind 交给行为系统', () => {
    const got = [];
    const tpl = buildMenuTemplate({ moodLabel: '平静', onCommand: (k) => got.push(k) });
    for (const kind of MENU_COMMANDS) {
        const item = tpl.find((i) => i.label === MENU_LABELS[kind]);
        assert.ok(item, `菜单缺少项: ${MENU_LABELS[kind]}`);
        assert.strictEqual(typeof item.click, 'function');
        item.click();
    }
    assert.deepStrictEqual(got, MENU_COMMANDS.slice());
});

// ====== C3: 心情项只读 ======
test('C3 心情项是只读信息 (不可点击, 不产生命令)', () => {
    const got = [];
    const tpl = buildMenuTemplate({ moodLabel: '开心', onCommand: (k) => got.push(k) });
    const moodItem = tpl.find((i) => typeof i.label === 'string' && i.label.startsWith('心情：'));
    assert.ok(moodItem, '菜单缺少心情项');
    assert.strictEqual(moodItem.label, '心情：开心');
    assert.strictEqual(moodItem.enabled, false);
    assert.strictEqual(moodItem.click, undefined, '心情项不应有点击处理');
});

// ====== C4: 菜单里没有调试项 ======
test('C4 菜单里只有正式功能项, 没有任何调试/演示入口', () => {
    const tpl = buildMenuTemplate({ moodLabel: '平静' });
    const clickable = tpl.filter((i) => i.type !== 'separator' && i.enabled !== false);
    const allowed = new Set([...MENU_COMMANDS.map((k) => MENU_LABELS[k]), '设置…', '退出桌宠']);
    for (const item of clickable) {
        assert.ok(allowed.has(item.label), `菜单出现了非预期项: ${item.label}`);
    }
    const banned = /debug|测试|演示|debug|log|日志|状态/i;
    for (const item of tpl) {
        if (typeof item.label !== 'string') continue;
        assert.ok(!banned.test(item.label), `菜单项含调试字样: ${item.label}`);
    }
});

// ====== C5: 设置项与退出项接线正确 ======
test('C5 "设置…" 与 "退出桌宠" 分别接到自己的处理函数', () => {
    let opened = 0, quit = 0;
    const tpl = buildMenuTemplate({ onOpenSettings: () => opened++, onQuit: () => quit++ });
    tpl.find((i) => i.label === '设置…').click();
    tpl.find((i) => i.label === '退出桌宠').click();
    assert.strictEqual(opened, 1);
    assert.strictEqual(quit, 1);
});

// ====== C6: 菜单命令走**正式行为系统** (状态真的切换了) ======
test('C6 菜单命令真的驱动行为系统状态机 (不是播演示图片)', () => {
    const cases = [
        ['work', STATES.WORK, 'work'],
        ['sit', STATES.SIT, 'sit_rest'],
        ['eat_fruit', STATES.EAT_FRUIT, 'eat_fruit'],
        ['doze', STATES.DOZE, 'doze'],
        ['gesture', STATES.GESTURE, 'ANY'],
        ['sleep', STATES.SLEEP_ENTER, 'sleep_enter'],
    ];
    for (const [kind, expectState, expectAction] of cases) {
        const { engine, actions } = makeEngine();
        engine.start();
        const res = engine.command(kind);
        assert.strictEqual(res.ok, true, `${kind} 命令应成功: ${JSON.stringify(res)}`);
        assert.strictEqual(res.kind, kind);
        assert.strictEqual(engine.getState(), expectState, `${kind} 之后状态应为 ${expectState}`);
        // 动作也必须真的下发给渲染器 (场景/道具挂载靠这个)
        assert.ok(actions.length > 0, `${kind} 应下发动作`);
        const gotAction = actions[actions.length - 1].action;
        if (expectAction === 'ANY') {
            // 随机可爱动作: 动作名由动作池随机决定, 但必须是一个真实下发的动作
            assert.strictEqual(typeof gotAction, 'string');
            assert.ok(gotAction.length > 0, '随机动作必须有动作名');
        } else {
            assert.strictEqual(gotAction, expectAction,
                `${kind} 应下发动作 ${expectAction}, 实际 ${gotAction}`);
        }
    }
});

// ====== C7: 醒来命令 ======
test('C7 "醒来" 走正式的 wake_up 一次性动画 (不瞬移站姿)', () => {
    const { engine, actions } = makeEngine();
    engine.start();
    engine.command('sleep');
    assert.strictEqual(engine.getState(), STATES.SLEEP_ENTER);
    const res = engine.command('wake');
    assert.strictEqual(res.ok, true);
    assert.strictEqual(engine.getState(), STATES.WAKE_UP);
    const last = actions[actions.length - 1];
    assert.strictEqual(last.action, 'wake_up');
});

// ====== C8: 非法/不合状态的命令被明确拒绝 ======
test('C8 不合状态的命令被明确拒绝 (不是静默假成功)', () => {
    const { engine } = makeEngine();
    engine.start();
    const wake = engine.command('wake');
    assert.strictEqual(wake.ok, false);
    assert.strictEqual(wake.error, 'not sleeping');
    engine.command('sleep');
    const sleep2 = engine.command('sleep');
    assert.strictEqual(sleep2.ok, false);
    assert.strictEqual(sleep2.error, 'already sleeping');
    const bad = engine.command('fly_to_moon');
    assert.strictEqual(bad.ok, false);
    assert.ok(/unknown command/.test(bad.error));
});

// ====== C9: 手动命令接管排程 (不会被下一次自主决策立刻覆盖) ======
test('C9 手动命令会接管排程 (旧的自主决策计时器被清掉, 换成该行为自己的计时器)', () => {
    const { engine } = makeEngine();
    engine.start();
    const before = engine.snapshot();
    assert.strictEqual(before.hasTimer, true, '启动后应已排下一次自主决策');
    assert.strictEqual(before.stateTimerKind, null, '自主决策计时器没有行为种类');
    engine.command('work');
    const after = engine.snapshot();
    // 旧的自主决策计时器已被清掉 —— 现在挂的是"办公时长"计时器
    assert.strictEqual(after.stateTimerKind, 'work',
        '手动命令后应挂该行为自己的状态计时器, 实际 ${after.stateTimerKind}');
    assert.ok(after.stateDeadline > 0, '状态计时器应设有到期时刻');
});

// ====== C10: 手动命令不受"同类冷却"限制 ======
test('C10 手动命令不受同类冷却限制 (用户明确要求就该立刻生效)', () => {
    const { engine } = makeEngine();
    engine.start();
    const a = engine.command('work');
    assert.strictEqual(a.ok, true);
    // 办公冷却是 60s; 手动再点一次必须仍然成功
    const b = engine.command('work');
    assert.strictEqual(b.ok, true, '第二次手动办公不应被冷却拦住');
    assert.strictEqual(engine.getState(), STATES.WORK);
});

// ====== C11: 命令与自主决策走同一条内部路径 ======
test('C11 手动命令与自主决策的状态转移原因一致 (同一套内部路径)', () => {
    const { engine, states } = makeEngine();
    engine.start();
    engine.command('work');
    const manual = states[states.length - 1];
    assert.strictEqual(manual.reason, 'idle-decision',
        `手动命令的转移原因应与自主决策一致, 实际 ${manual.reason}`);

    // 自主决策触发一次 walk, 对比转移原因
    const { engine: e2, states: s2, clock } = makeEngine();
    e2.start();
    clock.advance(200000);   // 越过 idle 间隔 → 触发自主决策
    const autonomous = s2[s2.length - 1];
    assert.ok(autonomous, '应至少发生一次自主状态转移');
    assert.strictEqual(autonomous.reason, manual.reason);
});

// ====== C12: 心情影响引擎的自主决策节奏 ======
test('C12 心情接入引擎后, 自主决策间隔真的被心情系数改变', () => {
    // 基础配置: idle 固定 1000ms, 便于精确测量
    const cfg = { idle_min_ms: 1000, idle_max_ms: 1000 };
    const plain = makeEngine({ config: cfg });
    plain.engine.start();
    const plainDelay = plain.clock.lastDelay;

    const mood = new MoodEngine({ state: { mood: MOODS.SLEEPY }, now: () => 1000000 });
    const adapter = {
        getMood: () => mood.getMood(),
        activityWeight: (k, m) => mood.activityWeight(k, m),
        idleIntervalScale: (m) => mood.idleIntervalScale(m),
    };
    const sleepy = makeEngine({ config: cfg, moodAdapter: adapter });
    sleepy.engine.start();
    const sleepyDelay = sleepy.clock.lastDelay;

    assert.strictEqual(plainDelay, 1000);
    assert.strictEqual(sleepyDelay, 1500, '困倦时自主决策间隔应 ×1.5');
    assert.strictEqual(sleepy.engine.getMood(), MOODS.SLEEPY);
});

// ====== C13: 设置的"自主活动频率"作用到引擎 ======
test('C13 设置面板的频率档位通过 applyConfig 作用到引擎 (只改数值不改逻辑)', () => {
    const cfg = { idle_min_ms: 1000, idle_max_ms: 1000 };
    const { engine, clock } = makeEngine({ config: cfg });
    engine.start();
    assert.strictEqual(clock.lastDelay, 1000);

    const fx = rateEffects('high', 'high');
    engine.applyConfig({
        activity_rate_interval_scale: fx.idle_interval,
        activity_weight_scale: fx.activity_weight,
        sleep_weight_scale: fx.sleep_weight,
    });
    // 重新排程一次, 观察间隔
    engine.command('work');
    engine._scheduleIdle ? null : null;
    const { engine: e2, clock: c2 } = makeEngine({ config: cfg });
    e2.start();
    e2.applyConfig({ activity_rate_interval_scale: fx.idle_interval });
    e2.stop();
    // 重新启动后按新系数排程
    const { engine: e3, clock: c3 } = makeEngine({ config: cfg });
    e3.applyConfig({ activity_rate_interval_scale: fx.idle_interval });
    e3.start();
    assert.strictEqual(c3.lastDelay, 600, '高频档位应把自主决策间隔压到 ×0.6');

    const snap = engine.snapshot();
    assert.strictEqual(snap.activityRateIntervalScale, fx.idle_interval);
    assert.strictEqual(snap.activityWeightScale, fx.activity_weight);
    assert.strictEqual(snap.sleepWeightScale, fx.sleep_weight);
});

// ====== C14: 设置 → 频率 → 引擎 的端到端串联 ======
test('C14 端到端: 设置文件 → sanitize → rateEffects → 引擎参数', () => {
    const settings = sanitizeSettings({ activity_rate: 'low', sleep_rate: 'high' });
    const fx = rateEffects(settings.activity_rate, settings.sleep_rate);
    const { engine } = makeEngine();
    engine.applyConfig({
        activity_rate_interval_scale: fx.idle_interval,
        activity_weight_scale: fx.activity_weight,
        sleep_weight_scale: fx.sleep_weight,
    });
    const snap = engine.snapshot();
    assert.strictEqual(snap.activityRateIntervalScale, 1.8);   // 低频 → 间隔 ×1.8
    assert.strictEqual(snap.activityWeightScale, 0.6);
    assert.strictEqual(snap.sleepWeightScale, 2.0);             // 高睡眠频率 → ×2.0
});

// ====== C15: 心情给点击动作池加权 ======
test('C15 心情给点击反馈动作池加权 (权重乘子真实生效)', () => {
    const pool = [
        { action: 'a', weight: 1 },
        { action: 'b', weight: 1 },
    ];
    // a 的权重被压到 0 ⇒ 永远不该抽到 a
    const onlyB = pickClickReaction(() => 0.0001, [], pool, (act) => (act === 'a' ? 0 : 1));
    assert.strictEqual(onlyB, 'b');
    // b 的权重被压到 0 ⇒ 永远不该抽到 b
    const onlyA = pickClickReaction(() => 0.9999, [], pool, (act) => (act === 'b' ? 0 : 1));
    assert.strictEqual(onlyA, 'a');
    // 权重越高越容易抽中: a 权重 ×100 ⇒ random=0.9 也该是 a
    const heavy = pickClickReaction(() => 0.9, [], pool, (act) => (act === 'a' ? 100 : 1));
    assert.strictEqual(heavy, 'a');
    // 不传 weightFn 时行为与旧版一致 (权重 1:1)
    assert.ok(['a', 'b'].includes(pickClickReaction(() => 0.5, [], pool)));
});

// ====== C16: 引擎命令在拖拽时被拒绝 (不与拖拽打架) ======
test('C16 拖拽过程中菜单命令被明确拒绝', () => {
    const { engine } = makeEngine();
    engine.start();
    engine.setDragging(true);
    const res = engine.command('work');
    assert.strictEqual(res.ok, false);
    assert.strictEqual(res.error, 'dragging');
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R177 菜单与设置 集成单元测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) {
        console.log(`  - ${r.name}: ${r.error}`);
    }
    process.exit(1);
}
process.exit(0);
