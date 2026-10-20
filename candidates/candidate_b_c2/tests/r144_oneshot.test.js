// R144 一次性动画结束机制回归测试
//
// R144 P0-2 要求:
//   - loop=true 继续循环
//   - loop=false 到最后一帧后停止推进
//   - 最后一帧保持指定时长
//   - 仅发送一次 animation-finished IPC
//   - 切换 sleep_loop 或 idle 前不闪回首帧
//   - 拖拽打断动画后, 旧动画不能再次发送过期的完成事件
//   - "增加实际生产 ticker 的执行测试, 模拟连续时间推进"
//
// 本测试直接 require 生产模块 src/anim_clock.js —— renderer.js 的 ticker
// 调用的就是同一个 AnimationClock 实例逻辑, 不是复刻一份。
// 用真实 R141 manifest 的 frame_ms / loop 配置驱动连续时间推进。

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const CAND = path.join(__dirname, '..');
const MANIFEST = JSON.parse(fs.readFileSync(path.join(CAND, 'assets', 'character_R141_manifest.json'), 'utf8'));

// ★ 生产时钟模块
const { AnimationClock } = require(path.join(CAND, 'src', 'anim_clock.js'));

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

// 从真实 manifest 取动作配置 (frame_ms / loop / 帧数)
function metaOf(action) {
    const a = MANIFEST.actions[action];
    return {
        frames: a.frames.map((_, i) => ({ id: i })),   // 只需长度
        frame_ms: a.frame_ms,
        fps: a.fps,
        loop: a.loop,
    };
}

// 连续时间推进: 以 16ms 为一帧 (≈60fps ticker), 推进 totalMs
function drive(clock, action, totalMs, stepMs = 16) {
    const events = [];
    let t = clock.lastAdvanceAt;
    const end = t + totalMs;
    while (t < end) {
        t += stepMs;
        const r = clock.tick(t);
        if (r.changed) events.push({ t, frame: r.frameIndex });
        if (r.finished) events.push({ t, finished: true, action: r.action });
    }
    return events;
}

// ====== 测试 1: 循环动画正常回卷 ======
test('T1 loop=true 动画持续循环 (idle 6 帧回卷, 不会卡在末帧)', () => {
    const clock = new AnimationClock();
    const meta = metaOf('idle');
    clock.setAction('idle', meta, 0);
    const events = drive(clock, 'idle', 2000);
    const frames = events.filter(e => e.frame !== undefined).map(e => e.frame);
    assert.ok(frames.length >= 8, `2000ms 内应推进多帧, 实际 ${frames.length}`);
    assert.ok(frames.includes(0), '循环动画未回卷到首帧');
    assert.ok(frames.includes(meta.frames.length - 1), '循环动画未到达末帧');
    assert.ok(!events.some(e => e.finished), '循环动画不应上报完成事件');
});

// ====== 测试 2: 一次性动画末帧停住, 不回卷 ======
test('T2 loop=false 动画推进到末帧后停住 (绝不跳回首帧)', () => {
    const clock = new AnimationClock();
    const meta = metaOf('sleep_enter');   // 3 帧, frame_ms=600, loop=false
    clock.setAction('sleep_enter', meta, 0);
    const events = drive(clock, 'sleep_enter', 5000);
    const frames = events.filter(e => e.frame !== undefined).map(e => e.frame);
    const last = meta.frames.length - 1;
    assert.deepStrictEqual(frames, [1, 2], `帧序列应单调推进到末帧, 实际 ${JSON.stringify(frames)}`);
    assert.ok(!frames.includes(0), '一次性动画回卷到了首帧 (闪回首帧 bug)');
    assert.strictEqual(clock.frameIndex, last, '末帧后帧号未停住');
});

// ====== 测试 3: 完成事件只发一次 ======
test('T3 一次性动画只上报一次 animation-finished', () => {
    const clock = new AnimationClock();
    const meta = metaOf('wake_up');   // 3 帧, frame_ms=600, loop=false
    clock.setAction('wake_up', meta, 0);
    const events = drive(clock, 'wake_up', 10000);
    const finished = events.filter(e => e.finished);
    assert.strictEqual(finished.length, 1, `完成事件应恰好 1 次, 实际 ${finished.length}`);
    assert.strictEqual(finished[0].action, 'wake_up');
});

// ====== 测试 4: 末帧保持指定时长 ======
test('T4 末帧保持恰好一个 frame_ms 后才上报完成', () => {
    const clock = new AnimationClock();
    const meta = metaOf('sleep_enter');   // frame_ms = 600
    clock.setAction('sleep_enter', meta, 0);
    const events = drive(clock, 'sleep_enter', 5000, 1);   // 1ms 精度
    const lastFrameAt = events.find(e => e.frame === meta.frames.length - 1).t;
    const finishedAt = events.find(e => e.finished).t;
    const held = finishedAt - lastFrameAt;
    assert.strictEqual(held, meta.frame_ms, `末帧应保持 ${meta.frame_ms}ms, 实际 ${held}ms`);
    // 末帧保持期间不得有新的帧推进
    const between = events.filter(e => e.t > lastFrameAt && e.t < finishedAt && e.frame !== undefined);
    assert.strictEqual(between.length, 0, '末帧保持期间发生了额外帧推进');
});

// ====== 测试 5: 切换动作后旧的一次性动画不再上报 ======
test('T5 切换动作后, 旧一次性动画的完成事件被丢弃 (不闪回首帧/不发过期事件)', () => {
    const clock = new AnimationClock();
    const meta = metaOf('sleep_enter');
    clock.setAction('sleep_enter', meta, 0);
    // 推进到末帧 (t=1200)
    clock.tick(600); clock.tick(1200);
    assert.strictEqual(clock.frameIndex, meta.frames.length - 1);
    // 末帧还没保持够时长, 此时切换到 sleep_loop
    clock.setAction('sleep_loop', metaOf('sleep_loop'), 1300);
    // 继续推进很久
    const events = drive(clock, 'sleep_loop', 3000);
    assert.ok(!events.some(e => e.finished), '切换动作后仍上报了旧动画的完成事件');
});

// ====== 测试 6: 拖拽打断后不再上报完成 ======
test('T6 拖拽打断 (interrupt) 后旧动画不得再上报完成事件', () => {
    const clock = new AnimationClock();
    const meta = metaOf('sleep_enter');
    clock.setAction('sleep_enter', meta, 0);
    clock.tick(600); clock.tick(1200);   // 已到末帧, 待回报
    clock.interrupt(1250);                // 用户按住角色 → 打断
    const events = drive(clock, 'sleep_enter', 3000);
    assert.ok(!events.some(e => e.finished), '打断后仍上报了完成事件 (过期事件)');
    assert.strictEqual(clock.frameIndex, meta.frames.length - 1, '打断后帧号不应继续推进');
});

// ====== 测试 7: 帧号永不超过末帧 ======
test('T7 长时间推进后帧号始终不超过末帧 (无越界/无回卷)', () => {
    for (const action of ['sleep_enter', 'wake_up']) {
        const clock = new AnimationClock();
        const meta = metaOf(action);
        clock.setAction(action, meta, 0);
        drive(clock, action, 20000);
        assert.ok(clock.frameIndex >= 0 && clock.frameIndex <= meta.frames.length - 1,
            `${action} 帧号越界: ${clock.frameIndex}`);
        assert.strictEqual(clock.frameIndex, meta.frames.length - 1,
            `${action} 未停在末帧: ${clock.frameIndex}`);
    }
});

// ====== 测试 8: 切走再切回会从首帧重新开始 ======
test('T8 一次性动画播完后切走再切回, 从首帧重新播放', () => {
    const clock = new AnimationClock();
    const enter = metaOf('sleep_enter');
    clock.setAction('sleep_enter', enter, 0);
    drive(clock, 'sleep_enter', 3000);
    assert.strictEqual(clock.frameIndex, enter.frames.length - 1);
    clock.setAction('idle', metaOf('idle'), 3000);
    clock.setAction('sleep_enter', enter, 3100);
    assert.strictEqual(clock.frameIndex, 0, '切回后未从首帧开始');
});

// ====== 测试 9: frame_ms 缺失时回退 fps ======
test('T9 无 frame_ms 时按 fps 推导帧时长', () => {
    const clock = new AnimationClock();
    const meta = { frames: [{ id: 0 }, { id: 1 }], fps: 10, loop: false };
    clock.setAction('x', meta, 0);
    assert.strictEqual(clock.period(), 100);
    const events = drive(clock, 'x', 500, 1);
    assert.ok(events.some(e => e.frame === 1), '未按 fps 推进到末帧');
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R144 一次性动画测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) {
        console.log(`  - ${r.name}: ${r.error}`);
    }
    process.exit(1);
}
process.exit(0);
