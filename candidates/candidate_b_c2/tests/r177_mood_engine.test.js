// R177 本地性格与心情系统 单元测试
//
// 覆盖 R177 任务书 §一.1 的可验收项:
//   · 规则驱动"开心 / 平静 / 困倦 / 无聊"四种状态, 且判定**可复算** (无随机)
//   · 心情影响: 自主活动权重 / 自主决策节奏 / 点击反馈动作偏好 / 是否禁用点击反馈
//   · **不调用 AI、没有任何预设聊天文字冒充 AI 人格** (本测试显式断言没有对话接口)
//   · 心情状态可持久化并可恢复 (重启后正确恢复"基础心情状态")
//
// 被测生产模块: src/mood_engine.js (生产代码本体)
// 运行: node tests/r177_mood_engine.test.js
'use strict';

const path = require('path');
const fs = require('fs');
const assert = require('assert');

const CAND = path.join(__dirname, '..');
const MOOD_PATH = path.join(CAND, 'src', 'mood_engine.js');
const { MoodEngine, MOODS, MOOD_LABELS, DEFAULT_MOOD_CONFIG } = require(MOOD_PATH);

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

// ====== 固定时刻 (2026-03-15 12:00:00 本地) ======
const T0 = new Date('2026-03-15T12:00:00').getTime();
const HOUR_DAY = 12;
const HOUR_NIGHT = 23;

function engineAt(now, state) {
    const e = new MoodEngine({
        state: state || {},
        now: () => now,
    });
    return e;
}

// ====== M1: 四种心情与中文标签 ======
test('M1 只有 开心/平静/困倦/无聊 四种心情, 且各有中文标签', () => {
    assert.deepStrictEqual(Object.values(MOODS).sort(), ['bored', 'calm', 'happy', 'sleepy']);
    assert.deepStrictEqual(Object.values(MOOD_LABELS).sort(), ['开心', '无聊', '困倦', '平静'].sort());
    for (const m of Object.values(MOODS)) {
        assert.ok(MOOD_LABELS[m], `心情 ${m} 缺少中文标签`);
    }
});

// ====== M2: 默认是平静 ======
test('M2 刚启动 (无任何事件) 的心情是"平静"', () => {
    const e = engineAt(T0);
    const snap = e.update(T0, HOUR_DAY);
    assert.strictEqual(snap.mood, MOODS.CALM);
    assert.strictEqual(snap.label, '平静');
    assert.strictEqual(snap.prev, MOODS.CALM);
    assert.strictEqual(snap.changed, false);
});

// ====== M3: 交互 → 开心 ======
test('M3 用户交互后心情变为"开心" (分数超过平静基准)', () => {
    const e = engineAt(T0);
    e.noteAwake(T0);
    const snap = e.noteInteraction(T0 + 1000);
    assert.strictEqual(snap.mood, MOODS.HAPPY);
    assert.strictEqual(snap.label, '开心');
    assert.ok(snap.scores.happy > snap.scores.calm,
        `开心分数应高于平静: ${JSON.stringify(snap.scores)}`);
});

// ====== M4: 深夜 → 困倦 ======
test('M4 本地深夜 (23 点) 即使没互动也判定为"困倦"', () => {
    const e = engineAt(T0);
    e.noteAwake(T0);
    const snap = e.update(T0, HOUR_NIGHT);
    assert.strictEqual(snap.mood, MOODS.SLEEPY);
    assert.strictEqual(snap.label, '困倦');
    assert.ok(snap.scores.sleepy >= DEFAULT_MOOD_CONFIG.sleepy_night_score);
});

// ====== M5: 久不睡 → 困倦 (白天也一样) ======
test('M5 连续清醒很久没睡 → 判定为"困倦"', () => {
    const e = engineAt(T0, { awakeSince: T0 - 12 * 3600000 });  // 已清醒 12 小时
    const snap = e.update(T0, HOUR_DAY);
    assert.strictEqual(snap.mood, MOODS.SLEEPY);
    assert.ok(snap.scores.sleepy > snap.scores.calm);
});

// ====== M6: 久没人理 → 无聊 ======
test('M6 既没交互也没自主活动很久 → 判定为"无聊"', () => {
    const e = engineAt(T0, { awakeSince: T0 - 40 * 60000 });   // 醒来后 40 分钟没人理
    const snap = e.update(T0, HOUR_DAY);
    assert.strictEqual(snap.mood, MOODS.BORED);
    assert.strictEqual(snap.label, '无聊');
    assert.ok(snap.scores.bored > snap.scores.calm);
});

// ====== M7: 判定可复算 (无随机) ======
test('M7 同样的事件序列 → 同样的心情结果 (判定完全可复算)', () => {
    const run = () => {
        const e = engineAt(T0);
        e.noteAwake(T0);
        e.noteInteraction(T0 + 1000);
        e.noteInteraction(T0 + 2000);
        e.update(T0 + 3000, HOUR_DAY);
        e.update(T0 + 600000, HOUR_DAY);
        return e.getMood();
    };
    assert.strictEqual(run(), run());
});

// ====== M8: 心情影响自主决策节奏 ======
test('M8 心情影响自主决策间隔 (开心/无聊更活跃, 困倦更迟钝)', () => {
    const e = engineAt(T0);
    assert.strictEqual(e.idleIntervalScale(MOODS.HAPPY), 0.7);
    assert.strictEqual(e.idleIntervalScale(MOODS.CALM), 1.0);
    assert.strictEqual(e.idleIntervalScale(MOODS.SLEEPY), 1.5);
    assert.strictEqual(e.idleIntervalScale(MOODS.BORED), 0.6);
    assert.ok(e.idleIntervalScale(MOODS.HAPPY) < e.idleIntervalScale(MOODS.CALM));
    assert.ok(e.idleIntervalScale(MOODS.SLEEPY) > e.idleIntervalScale(MOODS.CALM));
});

// ====== M9: 心情影响自主活动权重 ======
test('M9 心情影响各类自主活动权重 (开心爱动 / 困倦爱打盹 / 无聊想找事做)', () => {
    const e = engineAt(T0);
    assert.strictEqual(e.activityWeight('gesture', MOODS.HAPPY), 1.6);
    assert.strictEqual(e.activityWeight('doze', MOODS.SLEEPY), 2.2);
    assert.strictEqual(e.activityWeight('sleep', MOODS.SLEEPY), 2.0);
    assert.strictEqual(e.activityWeight('walk', MOODS.BORED), 1.4);
    assert.strictEqual(e.activityWeight('eat_fruit', MOODS.BORED), 1.3);
    // 平静时所有权重都应该是 1 (不改既有行为)
    for (const kind of ['gesture', 'walk', 'sit', 'doze', 'work', 'eat_fruit', 'sleep']) {
        assert.strictEqual(e.activityWeight(kind, MOODS.CALM), 1,
            `平静状态下 ${kind} 权重应为 1`);
    }
    // 未知活动类型不能炸
    assert.strictEqual(e.activityWeight('not_a_kind', MOODS.HAPPY), 1);
});

// ====== M10: 心情影响点击反馈动作偏好 ======
test('M10 心情影响点击反馈动作权重 (开心偏活泼, 困倦偏轻量)', () => {
    const e = engineAt(T0);
    assert.ok(e.clickWeight('cheer_heart', MOODS.HAPPY) > 1);
    assert.ok(e.clickWeight('cheer_jump', MOODS.SLEEPY) < 1);
    assert.strictEqual(e.clickWeight('cheer_wave', MOODS.CALM), 1);
    assert.strictEqual(e.clickWeight('cheer_wave', 'no_such_mood'), 1);
});

// ====== M11: 心情**不**静默吞掉点击反馈 (守住 R156/R162 既有不变量) ======
test('M11 默认不因心情而禁用点击反馈 (点击永远有反馈; 困倦只改权重不改有无)', () => {
    const e = engineAt(T0);
    // R156/R162 的既有产品不变量: "点击必须产生可见反馈"。
    // 若这里默认禁用, 夜里(困倦)点她没反应会被当成 bug —— 所以默认一律不禁用。
    for (const m of [MOODS.HAPPY, MOODS.CALM, MOODS.SLEEPY, MOODS.BORED]) {
        assert.strictEqual(e.shouldSuppressClick(m), false,
            `心情 ${m} 不应禁用点击反馈`);
    }
    // 心情对互动反馈的影响**只用权重表达**: 困倦 ⇒ 偏轻量动作
    assert.ok(e.clickWeight('cheer_jump', MOODS.SLEEPY) < e.clickWeight('cheer_jump', MOODS.CALM));
    assert.ok(e.clickWeight('cheer_tilt', MOODS.SLEEPY) < e.clickWeight('cheer_tilt', MOODS.HAPPY));
    // 该能力仍然保留 (显式开启时才生效), 不是删掉
    const strict = new MoodEngine({ config: { sleepy_suppress_click: true }, now: () => T0 });
    assert.strictEqual(strict.shouldSuppressClick(MOODS.SLEEPY), true);
    assert.strictEqual(strict.shouldSuppressClick(MOODS.CALM), false);
});

// ====== M12: 持久化 → 恢复 往返一致 ======
test('M12 toJSON/restore 往返: 重启后能恢复基础心情状态', () => {
    const a = engineAt(T0);
    a.noteAwake(T0);
    a.noteInteraction(T0 + 1000);
    a.noteActivity('work', T0 + 2000);
    const saved = JSON.parse(JSON.stringify(a.toJSON()));

    const b = new MoodEngine({ state: saved, now: () => T0 + 5000 });
    assert.strictEqual(b.getMood(), saved.mood);
    assert.strictEqual(b.state.energy, saved.energy);
    assert.strictEqual(b.state.interactionCount, saved.interactionCount);
    assert.strictEqual(b.state.lastActivityAt, saved.lastActivityAt);
    assert.strictEqual(b.state.sleepCount, saved.sleepCount);
    assert.strictEqual(b.state.awakeSince, saved.awakeSince);
});

// ====== M13: 恢复损坏数据不抛异常 ======
test('M13 恢复时遇到损坏/非法数据 → 不抛异常, 回退到合法默认值', () => {
    const b = new MoodEngine({ state: { mood: '这不是心情', energy: 'NaN', interactionCount: 'x' }, now: () => T0 });
    assert.strictEqual(b.getMood(), MOODS.CALM);
    assert.strictEqual(b.state.energy, 1);
    assert.strictEqual(b.state.interactionCount, 0);
    const c = new MoodEngine({ state: null, now: () => T0 });
    assert.strictEqual(c.getMood(), MOODS.CALM);
    assert.strictEqual(c.restore(undefined), false);
    assert.strictEqual(c.restore('garbage'), false);
});

// ====== M14: 精力随清醒下降, 睡眠恢复 ======
test('M14 精力随清醒时间下降, 睡一觉后恢复为满', () => {
    const e = engineAt(T0, { awakeSince: T0 - 5 * 3600000, energy: 1 });
    e.update(T0, HOUR_DAY);
    assert.ok(e.getEnergy() < 1, `清醒 5 小时后精力应下降, 实际 ${e.getEnergy()}`);
    e.noteSleep(T0 + 1000);
    assert.strictEqual(e.getEnergy(), 1);
    assert.strictEqual(e.state.sleepCount, 1);
});

// ====== M15: 睡觉记为一次活动 (无聊计时被重置) ======
test('M15 自主活动/睡觉都会刷新"最后一次社交"时间 (不会一直无聊)', () => {
    const e = engineAt(T0, { awakeSince: T0 - 60 * 60000 });
    let snap = e.update(T0, HOUR_DAY);
    assert.strictEqual(snap.mood, MOODS.BORED);
    e.noteActivity('sit', T0 + 1000);
    snap = e.update(T0 + 1000, HOUR_DAY);
    assert.notStrictEqual(snap.mood, MOODS.BORED, '刚做完活动不该还是无聊');
});

// ====== M16: 【硬边界】不得冒充 AI 人格 —— 没有任何对话/台词接口 ======
test('M16 心情引擎不含任何"说话/聊天/台词"接口 (不冒充 AI 人格)', () => {
    const src = fs.readFileSync(MOOD_PATH, 'utf8');
    const proto = MoodEngine.prototype;
    const names = Object.getOwnPropertyNames(proto);
    const banned = /say|talk|chat|reply|respond|dialog|utter|speak|quote|line|message|text|script/i;
    for (const n of names) {
        assert.ok(!banned.test(n), `心情引擎不应有对话类方法: ${n}`);
    }
    // 模块导出里也不该有"生成台词"的函数
    const mod = require(MOOD_PATH);
    for (const k of Object.keys(mod)) {
        assert.ok(!banned.test(k), `心情模块不应导出对话类成员: ${k}`);
    }
    // 源码里不该出现网络调用
    assert.ok(!/https?:\/\/|fetch\(|XMLHttpRequest|axios|net\./i.test(src),
        '心情引擎源码不应包含网络调用');
    // 心情对象里唯一的中文就是 4 个标签
    const labels = Object.values(MOOD_LABELS);
    assert.strictEqual(labels.length, 4);
});

// ====== M17: 精力按**时间增量**扣, 连续刷新不会重复扣 (R179) ======
test('M17 精力按增量扣: 已清醒 1 小时 + 每 30s 刷新 10 分钟, 精力不会归零', () => {
    const T0 = new Date('2026-03-15T12:00:00').getTime();
    // 已清醒 1 小时, 初始精力 1
    const e = engineAt(T0, { awakeSince: T0 - 3600000, energy: 1 });
    e.update(T0, HOUR_DAY);
    assert.ok(Math.abs(e.getEnergy() - 0.95) < 1e-9,
        `首次结算后精力应约 0.95, 实际 ${e.getEnergy()}`);
    // 每 30 秒刷新一次, 共 20 次 (10 分钟)
    let now = T0;
    for (let i = 0; i < 20; i++) {
        now += 30000;
        e.update(now, HOUR_DAY);
    }
    // 理论值: 1 - (70 分钟 / 60) × 0.05 = 0.941666...
    const expect = 1 - (70 / 60) * 0.05;
    assert.ok(Math.abs(e.getEnergy() - expect) < 1e-9,
        `10 分钟后精力应约 ${expect.toFixed(6)}, 实际 ${e.getEnergy()}`);
    assert.ok(e.getEnergy() > 0.9, `精力不该被扣到接近 0, 实际 ${e.getEnergy()}`);
});

// ====== M18: 重启恢复后继续按增量扣 (R179) ======
test('M18 重启恢复后精力接着上次继续扣, 不重复扣也不跳变', () => {
    const T0 = new Date('2026-03-15T12:00:00').getTime();
    const a = engineAt(T0, { awakeSince: T0 - 3600000, energy: 1 });
    a.update(T0, HOUR_DAY);
    let now = T0;
    for (let i = 0; i < 20; i++) { now += 30000; a.update(now, HOUR_DAY); }
    const saved = JSON.parse(JSON.stringify(a.toJSON()));

    // 模拟重启: 用持久化状态恢复
    const b = new MoodEngine({ state: saved, now: () => now });
    assert.ok(Math.abs(b.getEnergy() - saved.energy) < 1e-12,
        `恢复后精力应等于保存值 ${saved.energy}, 实际 ${b.getEnergy()}`);
    // 恢复后再过 30 秒 ⇒ 只扣 30 秒的量
    b.update(now + 30000, HOUR_DAY);
    const expect = saved.energy - (0.5 / 60) * 0.05;
    assert.ok(Math.abs(b.getEnergy() - expect) < 1e-9,
        `恢复后 30 秒精力应约 ${expect.toFixed(8)}, 实际 ${b.getEnergy()}`);
    // 重启本身不能额外扣一次 (恢复时 update 不该扣)
    assert.ok(b.getEnergy() > 0.9, `重启不该让精力跳变, 实际 ${b.getEnergy()}`);
});

// ====== M19: 睡眠期间不扣精力, 睡醒后从满值接着扣 (R179) ======
test('M19 睡着的一段时间不计入清醒消耗', () => {
    const T0 = new Date('2026-03-15T12:00:00').getTime();
    const e = engineAt(T0, { awakeSince: T0 - 3600000, energy: 1 });
    e.update(T0, HOUR_DAY);
    assert.ok(Math.abs(e.getEnergy() - 0.95) < 1e-9);
    // 睡 2 小时 (期间 refresh 若干次) ⇒ 精力应恢复为 1 且不再被扣
    e.noteSleep(T0 + 1000);
    assert.strictEqual(e.getEnergy(), 1);
    for (let i = 1; i <= 20; i++) {
        e.update(T0 + 1000 + i * 360000, HOUR_DAY);   // 每次 +6 分钟
    }
    assert.strictEqual(e.getEnergy(), 1, `睡着时精力不该被扣, 实际 ${e.getEnergy()}`);
    // 醒来后再过 30 分钟 ⇒ 只扣 30 分钟
    const wakeAt = T0 + 1000 + 20 * 360000;
    e.noteAwake(wakeAt);
    e.update(wakeAt + 1800000, HOUR_DAY);
    assert.ok(Math.abs(e.getEnergy() - (1 - 0.5 * 0.05)) < 1e-9,
        `醒来 30 分钟后精力应约 ${(1 - 0.5 * 0.05)}, 实际 ${e.getEnergy()}`);
});

// ====== M20: 单次超长间隔有上限 (机器休眠/时钟回拨不会一次扣光) ======
test('M20 单次超长间隔有扣除上限 (休眠/时钟回拨不会一次归零)', () => {
    const T0 = new Date('2026-03-15T12:00:00').getTime();
    const e = engineAt(T0, { awakeSince: T0, energy: 1 });
    // 直接跳 100 小时
    e.update(T0 + 100 * 3600000, HOUR_DAY);
    const capHours = DEFAULT_MOOD_CONFIG.energy_max_delta_ms / 3600000;
    const expect = 1 - capHours * 0.05;
    assert.ok(Math.abs(e.getEnergy() - expect) < 1e-9,
        `100 小时后精力应只扣上限 ${capHours} 小时, 期望 ${expect}, 实际 ${e.getEnergy()}`);
    assert.ok(e.getEnergy() > 0.6, `不该被一次扣光, 实际 ${e.getEnergy()}`);
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R177 心情引擎 单元测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) {
        console.log(`  - ${r.name}: ${r.error}`);
    }
    process.exit(1);
}
process.exit(0);
