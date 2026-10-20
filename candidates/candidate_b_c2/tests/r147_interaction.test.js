// R147 交互与动画质量单元测试
//
// 覆盖 R147 任务书 §六 的可验收项 (全部调用**真实生产代码**):
//   · 点击能触发响应 / 点击不误拖 / 拖拽不误点击 / 睡眠点击能唤醒
//   · 点击反馈结束后状态机正常恢复
//   · idle 无快速胸部膨胀 / 眨眼不每 1.2s 机械循环
//   · 左右行走方向正确 (映射 + 朝向倾斜)
//   · 撞边反向时动作同步更新
//
// 被测生产模块:
//   src/click_policy.js   : 点击/拖拽判定
//   src/idle_director.js  : 自然待机导演
//   src/behavior_engine.js: 自主行为状态机 (含 R147 新增的点击/唤醒)
//   src/sprite_layout.js  : 布局与方向倾斜
//
// 运行: node tests/r147_interaction.test.js
'use strict';

const path = require('path');
const fs = require('fs');
const assert = require('assert');

const CAND = path.join(__dirname, '..');
const MANIFEST = JSON.parse(fs.readFileSync(path.join(CAND, 'assets', 'character_R141_manifest.json'), 'utf8'));

const {
    classifyPress, isClickReaction, isDragEnd, releasesPress,
    CLICK_MAX_MS, CLICK_MAX_PX, DRAG_THRESHOLD_PX,
} = require(path.join(CAND, 'src', 'click_policy.js'));
const { IdleDirector } = require(path.join(CAND, 'src', 'idle_director.js'));
const { BehaviorEngine, STATES } = require(path.join(CAND, 'src', 'behavior_engine.js'));
const { computeLayout, frameScreenRect, skewAngleX } = require(path.join(CAND, 'src', 'sprite_layout.js'));

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

// ====== 可控时钟 / 定时器 (测试用) ======
function makeClock() {
    let now = 0;
    const timers = [];
    let seq = 0;
    return {
        now: () => now,
        setTimeout: (fn, ms) => { const h = ++seq; timers.push({ h, fn, at: now + (ms || 0), kind: 'timeout' }); return h; },
        clearTimeout: (h) => { const i = timers.findIndex(t => t.h === h); if (i >= 0) timers.splice(i, 1); },
        setInterval: (fn, ms) => { const h = ++seq; timers.push({ h, fn, at: now + (ms || 0), every: ms || 0, kind: 'interval' }); return h; },
        clearInterval: (h) => { const i = timers.findIndex(t => t.h === h); if (i >= 0) timers.splice(i, 1); },
        advance(ms) {
            const target = now + ms;
            let guard = 0;
            while (guard++ < 10000) {
                const due = timers.filter(t => t.at <= target).sort((a, b) => a.at - b.at);
                if (due.length === 0) break;
                const t = due[0];
                now = t.at;
                if (t.kind === 'interval') { t.at = now + t.every; } else { timers.splice(timers.indexOf(t), 1); }
                t.fn();
            }
            now = target;
        },
        pending: () => timers.length,
    };
}

// ====== A. 点击 / 拖拽判定 ======
test('A1 短按且几乎无位移 → CLICK (触发点击反馈)', () => {
    const kind = classifyPress({ reason: 'up', elapsedMs: 120, distancePx: 0, wasWindowDrag: false });
    assert.strictEqual(kind, 'CLICK');
    assert.ok(isClickReaction(kind));
    assert.ok(!isDragEnd(kind), '点击不得同时被判为拖拽结束');
});

test('A2 累计位移达到 3px → DRAG (不触发点击反馈)', () => {
    for (const d of [3, 3.5, 10, 120]) {
        const kind = classifyPress({ reason: 'up', elapsedMs: 100, distancePx: d, wasWindowDrag: false });
        assert.strictEqual(kind, 'DRAG', `位移 ${d}px 应判为 DRAG`);
        assert.ok(!isClickReaction(kind));
        assert.ok(isDragEnd(kind));
    }
});

test('A3 已进入窗口拖拽 → 一律 DRAG (拖拽绝不误触发点击)', () => {
    const kind = classifyPress({ reason: 'up', elapsedMs: 50, distancePx: 0, wasWindowDrag: true });
    assert.strictEqual(kind, 'DRAG');
    assert.ok(!isClickReaction(kind));
});

test('A4 按住超过 400ms 且未移动 → HOLD (不算单击, 但安全松开)', () => {
    const kind = classifyPress({ reason: 'up', elapsedMs: CLICK_MAX_MS + 1, distancePx: 1, wasWindowDrag: false });
    assert.strictEqual(kind, 'HOLD');
    assert.ok(!isClickReaction(kind));
    assert.ok(releasesPress(kind));
});

test('A5 鼠标取消 / 离开角色区域松开 → CANCEL (安全清理, 不触发反馈)', () => {
    for (const reason of ['cancel', 'outside']) {
        const kind = classifyPress({ reason, elapsedMs: 80, distancePx: 0, wasWindowDrag: false });
        assert.strictEqual(kind, 'CANCEL', `${reason} 应判为 CANCEL`);
        assert.ok(!isClickReaction(kind));
        assert.ok(releasesPress(kind));
    }
});

test('A6 同一次操作只可能得到一个结论 (点击与拖拽互斥)', () => {
    for (let elapsed = 0; elapsed <= 800; elapsed += 37) {
        for (let dist = 0; dist <= 12; dist += 0.5) {
            for (const wasDrag of [false, true]) {
                const kind = classifyPress({ reason: 'up', elapsedMs: elapsed, distancePx: dist, wasWindowDrag: wasDrag });
                const click = isClickReaction(kind);
                const drag = isDragEnd(kind);
                assert.ok(!(click && drag), `elapsed=${elapsed} dist=${dist} drag=${wasDrag} 同时命中 CLICK 与 DRAG`);
            }
        }
    }
});

test('A7 阈值常量与文档一致 (3px / 400ms)', () => {
    assert.strictEqual(DRAG_THRESHOLD_PX, 3);
    assert.strictEqual(CLICK_MAX_PX, 3);
    assert.strictEqual(CLICK_MAX_MS, 400);
});

// ====== B. 引擎层: 点击响应 / 拖拽互斥 / 睡眠唤醒 ======
function newEngine(extra = {}) {
    const clock = makeClock();
    const actions = [];
    const engine = new BehaviorEngine(Object.assign({
        config: Object.assign({
            idle_min_ms: 3000, idle_max_ms: 8000,
            walk_min_distance_px: 80, walk_max_distance_px: 250,
            walk_speed_px_per_sec: 30, walk_move_tick_ms: 33,
            sleep_min_ms: 20000, sleep_max_ms: 45000,
            sleep_probability: 0, walk_probability: 1,
            drag_resume_delay_ms: 800,
        }, extra.config || {}),
        onAction: (a) => actions.push(a),
        onMove: () => ({ moved: 1 }),
        random: extra.random || (() => 0.5),
        now: clock.now,
        setTimeout: clock.setTimeout,
        clearTimeout: clock.clearTimeout,
        setInterval: clock.setInterval,
        clearInterval: clock.clearInterval,
    }, extra.opts || {}));
    return { engine, clock, actions };
}

test('B1 点击站立角色 → 引擎记录反应, 不切换动作, 自主行为被暂缓', () => {
    const { engine, clock, actions } = newEngine();
    engine.start();
    actions.length = 0;
    const r = engine.onUserClick('idle', 700);
    assert.strictEqual(r, 'react');
    // 点击不产生动作切换 (反馈由 renderer 层的弹跳+眨眼承担)
    assert.strictEqual(actions.length, 0, `点击不应切换动作, 实际 ${JSON.stringify(actions)}`);
    // 自主行为计时器被暂缓: 700ms 内不会进入下一次决策
    clock.advance(500);
    assert.strictEqual(engine.getState(), STATES.IDLE);
    // 暂缓结束后恢复排程
    clock.advance(400);
    assert.ok(engine.snapshot().hasTimer, '暂缓结束后应重新排程自主行为');
    engine.stop();
});

test('B2 点击反馈结束后状态机正常恢复 (不会卡死)', () => {
    const { engine, clock } = newEngine();
    engine.start();
    engine.onUserClick('idle', 700);
    clock.advance(1200);
    assert.strictEqual(engine.getState(), STATES.IDLE);
    assert.strictEqual(engine.snapshot().hasTimer, true);
    // 连续多次点击不泄漏计时器
    for (let i = 0; i < 12; i++) {
        engine.onUserClick('idle', 700);
        clock.advance(120);
    }
    const snap = engine.snapshot();
    assert.strictEqual(snap.pendingTimerCount, 1,
        `连续点击后应只剩 1 个待触发计时器, 实际 ${snap.pendingTimerCount} (hasTimer=${snap.hasTimer} hasHoldTimer=${snap.hasHoldTimer})`);
    engine.stop();
    assert.strictEqual(engine.snapshot().pendingTimerCount, 0, 'stop() 后不得残留计时器');
});

test('B3 睡眠状态点击 → 走 wake_up 一次性动画, 不瞬移成站姿', () => {
    const { engine, clock, actions } = newEngine();
    engine.start();
    // 强制进入睡眠
    engine._transition(STATES.SLEEP_LOOP, 'test-setup');
    actions.length = 0;
    const r = engine.onUserClick('sleep_loop', 700);
    assert.strictEqual(r, 'wake');
    assert.strictEqual(engine.getState(), STATES.WAKE_UP, '睡眠点击后应进入 WAKE_UP');
    assert.ok(actions.includes('wake_up'), `应下发 wake_up 动作, 实际 ${JSON.stringify(actions)}`);
    assert.ok(!actions.includes('idle'), '睡眠点击不得直接下发 idle (那是瞬移)');
    // wake_up 播完 → 回到 idle
    engine.onAnimationFinished('wake_up');
    assert.strictEqual(engine.getState(), STATES.IDLE);
    assert.ok(actions.includes('idle'));
    clock.advance(100);
    engine.stop();
});

test('B4 睡眠点击只下发一次 wake_up (不会重复触发)', () => {
    const { engine, actions } = newEngine();
    engine.start();
    engine._transition(STATES.SLEEP_LOOP, 'test-setup');
    actions.length = 0;
    engine.onUserClick('sleep_loop', 700);
    engine.onUserClick('sleep_loop', 700);
    assert.strictEqual(actions.filter(a => a === 'wake_up').length, 1,
        `wake_up 不应重复下发: ${JSON.stringify(actions)}`);
    engine.stop();
});

test('B5 拖拽 (按住) → 引擎进入 DRAGGING, 不会同时产生点击反应', () => {
    const { engine, clock, actions } = newEngine();
    engine.start();
    actions.length = 0;
    engine.setDragging(true);
    assert.strictEqual(engine.getState(), STATES.DRAGGING);
    // 拖拽过程中不移动窗口
    let moved = 0;
    engine.onMove = () => { moved++; return { moved: 1 }; };
    clock.advance(500);
    assert.strictEqual(moved, 0, '拖拽期间不得移动窗口');
    engine.setDragging(false);
    assert.strictEqual(engine.getState(), STATES.IDLE);
    engine.stop();
});

test('B6 撞边反向 → 动作方向同步切换 (walk_left ↔ walk_right)', () => {
    const { engine, clock, actions } = newEngine();
    engine.start();
    // 强制向左走
    engine._startWalk(-1);
    assert.strictEqual(engine.getState(), STATES.WALK_LEFT);
    actions.length = 0;
    // 模拟撞到左边界 (一次推进只触发一个 33ms 位移 tick)
    engine.onMove = () => ({ blocked: true, moved: 0 });
    clock.advance(34);
    assert.strictEqual(engine.getState(), STATES.WALK_RIGHT, '撞边后应反向');
    assert.ok(actions.includes('walk_right'), `撞边后应下发 walk_right: ${JSON.stringify(actions)}`);
    // 再撞右边界
    actions.length = 0;
    clock.advance(34);
    assert.strictEqual(engine.getState(), STATES.WALK_LEFT);
    assert.ok(actions.includes('walk_left'), `再次撞边应下发 walk_left: ${JSON.stringify(actions)}`);
    engine.stop();
});

test('B7 点击期间行走被暂停, 反馈结束后继续走完 (不被 walk 覆盖, 也不丢进度)', () => {
    const { engine, clock } = newEngine();
    engine.start();
    engine._startWalk(1);
    const before = engine.snapshot().walkRemaining;
    engine.onUserClick('walk_right', 700);
    clock.advance(500);
    assert.strictEqual(engine.snapshot().walkRemaining, before, '点击反馈期间不应继续移动');
    assert.strictEqual(engine.snapshot().hasMoveTimer, false, '点击反馈期间位移计时器应暂停');
    clock.advance(400);
    assert.strictEqual(engine.snapshot().hasMoveTimer, true, '反馈结束后位移应恢复');
    engine.stop();
});

// ====== C. 自然待机 ======
test('C1 待机不再播放胸部膨胀帧 (idle_01 不进入播放序列)', () => {
    const spec = MANIFEST.actions.idle.director;
    assert.ok(spec && spec.enabled, 'manifest 必须启用 idle director');
    assert.deepStrictEqual(spec.excluded_frames, [1, 2, 3], '膨胀帧 1 与回落帧 2/3 必须被排除');
    const dir = new IdleDirector({ spec, random: () => 0.5, now: () => 0 });
    dir.setAction('idle', 0);
    const played = new Set();
    for (let t = 0; t <= 20000; t += 16) {
        const d = dir.tick(t);
        played.add(d.frameIndex);
    }
    assert.ok(!played.has(1), 'idle_01_inhale_peak 绝不能被播放');
    assert.ok(!played.has(2) && !played.has(3), '回落帧不应被播放');
    assert.ok(played.has(0), '稳定站姿必须被使用');
});

test('C2 眨眼间隔不是 1.2s 机械循环 (1.6~3.4s 随机)', () => {
    const spec = MANIFEST.actions.idle.director;
    const gaps = [];
    for (let seed = 0; seed < 200; seed++) {
        // 伪随机但确定
        let s = seed + 1;
        const rnd = () => { s = (s * 1103515245 + 12345) % 2147483648; return s / 2147483648; };
        const dir = new IdleDirector({ spec, random: rnd, now: () => 0 });
        dir.setAction('idle', 0);
        let last = 0;
        let prevPhase = 'hold';
        for (let t = 0; t <= 60000; t += 16) {
            const d = dir.tick(t);
            // 只统计"由 hold 进入 blink"的瞬间 (眨眼中途还有一次换帧, 不是新的一次眨眼)
            if (d.changed && d.phase === 'blink' && prevPhase !== 'blink') {
                gaps.push(t - last); last = t;
            }
            prevPhase = d.phase;
        }
    }
    assert.ok(gaps.length > 50, `应采到足够多的眨眼样本, 实际 ${gaps.length}`);
    const min = Math.min(...gaps), max = Math.max(...gaps);
    // 两次眨眼"起点"的间隔 = 站姿保持时长 + 一次眨眼时长(约 200ms) + 采样误差(16ms)
    assert.ok(min >= 1600 - 32, `最短眨眼间隔 ${min}ms 应 ≥ 1600ms (远慢于 1.2s 机械循环)`);
    assert.ok(max <= 3400 + 220 + 32, `最长眨眼间隔 ${max}ms 超出 3.4s 站姿保持上限`);
    // 直接核对导演吐出的站姿保持时长本身
    const holds = [];
    for (let seed = 0; seed < 200; seed++) {
        let s = seed + 1;
        const rnd = () => { s = (s * 1103515245 + 12345) % 2147483648; return s / 2147483648; };
        const d = new IdleDirector({ spec, random: rnd, now: () => 0 });
        holds.push(d.nextHoldMs());
    }
    assert.ok(Math.min(...holds) >= 1600, `站姿保持时长下限 ${Math.min(...holds)}ms 应 ≥ 1600ms`);
    assert.ok(Math.max(...holds) <= 3400, `站姿保持时长上限 ${Math.max(...holds)}ms 应 ≤ 3400ms`);
    // 不是机械重复: 间隔必须有明显变化
    const uniq = new Set(gaps.map(g => Math.round(g / 50)));
    assert.ok(uniq.size > 10, `眨眼间隔应有随机性, 不同取值仅 ${uniq.size} 种`);
});

test('C3 眨眼与呼吸节奏不同 (眨眼是一次性短促动作, 不是循环膨胀)', () => {
    const spec = MANIFEST.actions.idle.director;
    const dir = new IdleDirector({ spec, random: () => 0.5, now: () => 0 });
    dir.setAction('idle', 0);
    // 眨眼期间只允许出现半闭/全闭两帧, 且总时长 < 400ms
    const seen = [];
    let blinkStart = null;
    for (let t = 0; t <= 20000; t += 8) {
        const d = dir.tick(t);
        if (d.changed) {
            if (d.phase === 'blink' && blinkStart === null) blinkStart = t;
            if (d.phase === 'hold' && blinkStart !== null) {
                seen.push(t - blinkStart);
                blinkStart = null;
            }
        }
    }
    assert.ok(seen.length > 0, '应采到眨眼样本');
    const maxBlink = Math.max(...seen);
    assert.ok(maxBlink < 400, `一次眨眼应短促 (<400ms), 实际最长 ${maxBlink}ms`);
});

test('C4 待机期间角色轮廓不发生整体伸缩 (只切换站姿与眨眼帧)', () => {
    const spec = MANIFEST.actions.idle.director;
    const dir = new IdleDirector({ spec, random: () => 0.5, now: () => 0 });
    dir.setAction('idle', 0);
    const frames = new Set();
    for (let t = 0; t <= 30000; t += 16) frames.add(dir.tick(t).frameIndex);
    // 允许的帧集合 = 站姿 + 两个眨眼帧 (膨胀/回落帧一律不许出现)
    for (const f of frames) {
        assert.ok(spec.excluded_frames.indexOf(f) === -1,
            `待机出现被排除的膨胀/回落帧 index=${f}`);
    }
});

// ====== D. 左右行走方向 (映射 + 朝向倾斜) ======
test('D1 manifest: walk_left / walk_right 各自保留原始帧, 且倾斜方向相反', () => {
    const wl = MANIFEST.actions.walk_left, wr = MANIFEST.actions.walk_right;
    assert.strictEqual(wl.frames.length, 4);
    assert.strictEqual(wr.frames.length, 4);
    // 两组素材**不同源** (不是改名, 也不是同一套帧)
    assert.ok(wl.frames.every(f => f.includes('/walk_left/')), 'walk_left 必须使用 walk_left 原始帧');
    assert.ok(wr.frames.every(f => f.includes('/walk_right/')), 'walk_right 必须使用 walk_right 原始帧');
    // 倾斜方向相反
    assert.ok(wl.lean.skew_x > 0, 'walk_left 应向左倾斜 (k>0)');
    assert.ok(wr.lean.skew_x < 0, 'walk_right 应向右倾斜 (k<0)');
    assert.strictEqual(wl.lean.direction, -1);
    assert.strictEqual(wr.lean.direction, 1);
});

test('D2 倾斜后角色确实朝各自移动方向倾斜 (屏幕坐标实测)', () => {
    const frames = [];
    for (const action of MANIFEST.animation_order) {
        const a = MANIFEST.actions[action];
        const lean = (a.lean && typeof a.lean.skew_x === 'number') ? a.lean.skew_x : 0;
        const boxes = MANIFEST.layout.frame_bboxes[action];
        for (let i = 0; i < a.frames.length; i++) {
            frames.push({ action, index: i, bbox: boxes[i], skew_x: lean });
        }
    }
    const layout = computeLayout({
        canvasW: 200, canvasH: 240,
        textureW: MANIFEST.canvas_px[0], textureH: MANIFEST.canvas_px[1],
        frames, margin: MANIFEST.layout.margin_px,
    });
    // 用"上半身中心 x" 相对 "下半身中心 x" 判断倾斜方向
    const torsoShift = (action) => {
        const boxes = MANIFEST.layout.frame_bboxes[action];
        const mid = Math.floor(boxes.length / 2);
        const b = boxes[mid];
        const headMid = (b[0] + b[2]) / 2;
        const feetY = b[3];
        const headY = b[1];
        const rect = { left: b[0], top: b[1], right: b[2], bottom: b[3] };
        const scr = frameScreenRect(layout, action, mid);
        // 上半身取 bbox 顶部 30% 的水平中心, 下半身取底部 30%
        const topRect = { left: b[0], top: b[1], right: b[2], bottom: b[1] + (b[3] - b[1]) * 0.3 };
        const botRect = { left: b[0], top: b[3] - (b[3] - b[1]) * 0.3, right: b[2], bottom: b[3] };
        const k = layout.skewByAction[action];
        const cosT = Math.sqrt(Math.max(0, 1 - k * k));
        const W = MANIFEST.canvas_px[0], H = MANIFEST.canvas_px[1];
        const ax = layout.anchor.x, ay = layout.anchor.y;
        const cx = (r) => {
            const lx = (r.left + r.right) / 2 - ax * W;
            const ly = (r.top + r.bottom) / 2 - ay * H;
            return layout.x + layout.scale * (lx + k * ly);
        };
        return cx(topRect) - cx(botRect);
    };
    const shiftL = torsoShift('walk_left');
    const shiftR = torsoShift('walk_right');
    assert.ok(shiftL < 0, `walk_left 上半身应偏左 (负), 实际 ${shiftL.toFixed(2)}px`);
    assert.ok(shiftR > 0, `walk_right 上半身应偏右 (正), 实际 ${shiftR.toFixed(2)}px`);
});

test('D3 倾斜纳入布局后 200x240 仍零裁切 (不靠缩小角色规避)', () => {
    const frames = [];
    for (const action of MANIFEST.animation_order) {
        const a = MANIFEST.actions[action];
        const lean = (a.lean && typeof a.lean.skew_x === 'number') ? a.lean.skew_x : 0;
        const boxes = MANIFEST.layout.frame_bboxes[action];
        for (let i = 0; i < a.frames.length; i++) {
            frames.push({ action, index: i, bbox: boxes[i], skew_x: lean });
        }
    }
    for (const [w, h] of [[200, 240], [256, 256]]) {
        const layout = computeLayout({
            canvasW: w, canvasH: h,
            textureW: MANIFEST.canvas_px[0], textureH: MANIFEST.canvas_px[1],
            frames, margin: MANIFEST.layout.margin_px,
        });
        for (const f of frames) {
            const scr = frameScreenRect(layout, f.action, f.index);
            assert.ok(scr.left >= layout.margin - 1e-6 && scr.right <= w - layout.margin + 1e-6
                && scr.top >= layout.margin - 1e-6 && scr.bottom <= h - layout.margin + 1e-6,
                `${w}x${h}/${f.action}[${f.index}] 越界 (${scr.left.toFixed(2)},${scr.top.toFixed(2)})-(${scr.right.toFixed(2)},${scr.bottom.toFixed(2)})`);
        }
    }
});

test('D4 skewAngleX 的方向语义与 PixiJS 一致 (k>0 → 向左倾)', () => {
    assert.ok(Math.sin(skewAngleX(0.085)) > 0, 'k>0 的 sin(skew.x) 应为正');
    assert.ok(Math.sin(skewAngleX(-0.075)) < 0, 'k<0 的 sin(skew.x) 应为负');
});

// ====== E. 资产完整性 ======
test('E1 23 帧资产完整, 且 walk_left 的原始 4 帧仍被真实加载', () => {
    let total = 0;
    const allFiles = new Set();
    for (const action of MANIFEST.animation_order) {
        const a = MANIFEST.actions[action];
        total += a.frames.length;
        for (const f of a.frames) {
            allFiles.add(f);
            assert.ok(fs.existsSync(path.join(CAND, 'assets', f)), `文件不存在: ${f}`);
        }
    }
    assert.strictEqual(total, 23, `资产帧总数应为 23, 实际 ${total}`);
    assert.strictEqual(allFiles.size, 23, '23 帧必须是 23 个不同文件 (无重复引用)');
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R147 交互与动画质量测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) console.log(`  - ${r.name}: ${r.error}`);
    process.exit(1);
}
process.exit(0);
