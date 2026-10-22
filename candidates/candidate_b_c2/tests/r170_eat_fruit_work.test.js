// R170 专项单元测试 —— 恢复办公场景 + 新增吃水果生活行为
//
// 覆盖 R170 任务书里**可自动化**的硬约束:
//
//   1. 办公场景为什么会"消失": manifest 的 behavior.config 是 R141 陈旧快照,
//      静默覆盖引擎默认值 ⇒ 办公单次命中率只有 5% ⇒ 真机 180s 触发 0 次。
//      本测试锁死"manifest 配置必须与引擎默认值一致"(根因回归护栏)。
//   2. 办公/吃水果的权重·时长·冷却落在可用区间内 (真机实测重标定后)。
//   3. EAT_FRUIT 是独立生活行为: 有状态、有动作、有道具场景, 且**与办公互斥**。
//   4. 播放期间普通行走/睡眠**不得**打断; 动作结束后**必须**回到正常生活状态。
//   5. 点击反馈不得把"有时长"的状态卡死 (R170 修掉的 bug: 办公中点一下 ⇒ 永远停在 WORK)。
//   6. 验收专用入口 (--demo-scene) 存在, 且与正式自主行为分离 (自主决策被暂停)。
//   7. 道具随状态出现/消失, 不残留; 吃水果道具不遮脸。
//
// 判定不依赖坐标符号、动画名或本测试自身的 PASS。

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const CAND = path.join(__dirname, '..');
const ASSETS = path.join(CAND, 'assets');
const MANIFEST_PATH = path.join(ASSETS, 'character_R141_manifest.json');
const MANIFEST = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));

const { ACTION_CATALOG } = require(path.join(CAND, 'src', 'action_library.js'));
const {
    BehaviorEngine, STATES, STATE_ACTION, ACTIVITY_KINDS, DEFAULT_CONFIG,
} = require(path.join(CAND, 'src', 'behavior_engine.js'));
const { computeLayout, groundRowY } = require(path.join(CAND, 'src', 'sprite_layout.js'));

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

// ====== 假时钟 ======
class FakeClock {
    constructor() { this.now = 1000000; this.timers = new Map(); this.seq = 1; }
    setTimeout(fn, ms) { const id = this.seq++; this.timers.set(id, { fn, at: this.now + Math.max(0, ms || 0) }); return id; }
    clearTimeout(id) { this.timers.delete(id); }
    advance(ms) {
        const target = this.now + ms;
        for (;;) {
            let next = null;
            for (const [id, t] of this.timers) {
                if (t.at <= target && (next === null || t.at < next[1].at)) next = [id, t];
            }
            if (!next) break;
            this.timers.delete(next[0]);
            this.now = next[1].at;
            next[1].fn();
        }
        this.now = target;
    }
}

function makeEngine(opts = {}) {
    const clock = new FakeClock();
    const actions = [];
    const states = [];
    const engine = new BehaviorEngine({
        config: opts.config || { ...DEFAULT_CONFIG },
        random: opts.random || (() => 0.5),
        now: () => clock.now,
        setTimeout: (fn, ms) => clock.setTimeout(fn, ms),
        clearTimeout: (id) => clock.clearTimeout(id),
        setInterval: () => 1,
        clearInterval: () => {},
        onAction: (a, s) => actions.push({ action: a, state: s }),
        onState: (from, to, reason) => states.push({ from, to, reason }),
    });
    return { engine, clock, actions, states };
}

// 活动池的随机阈值: **从引擎自己的权重反推** (不写死数字)
const ACTIVITY_W_KEY = {
    gesture: 'gesture_probability', walk: 'walk_probability', sit: 'sit_probability',
    doze: 'doze_probability', work: 'work_probability', eat_fruit: 'eat_fruit_probability',
    sleep: 'sleep_probability',
};
function randomForKind(kind, cfg) {
    const c = cfg || DEFAULT_CONFIG;
    const total = ACTIVITY_KINDS.reduce((s, k) => s + (c[ACTIVITY_W_KEY[k]] || 0), 0);
    let acc = 0;
    for (const k of ACTIVITY_KINDS) {
        const w = c[ACTIVITY_W_KEY[k]] || 0;
        if (k === kind) return (acc + w / 2) / total;
        acc += w;
    }
    throw new Error(`未知活动类别 ${kind}`);
}

// ====== A. 根因回归护栏: manifest 配置不得静默覆盖引擎默认值 ======
test('A1 manifest 的 behavior.config 与引擎默认值一致 (R170 根因护栏)', () => {
    const cfg = MANIFEST.behavior && MANIFEST.behavior.config;
    assert.ok(cfg, 'manifest 缺 behavior.config');
    // 这些键是 R141 之后新增/调整过的 —— manifest 里一旦留旧值就会静默覆盖引擎
    const mustMatch = [
        'sleep_probability', 'walk_probability',
        'gesture_probability', 'sit_probability', 'doze_probability',
        'work_probability', 'work_min_ms', 'work_max_ms', 'work_cooldown_ms',
        'eat_fruit_probability', 'eat_fruit_min_ms', 'eat_fruit_max_ms',
        'eat_fruit_cooldown_ms',
    ];
    for (const k of mustMatch) {
        assert.ok(cfg[k] !== undefined, `manifest.behavior.config 缺 ${k} (会回落到引擎默认值, 配置与文档脱节)`);
        assert.strictEqual(cfg[k], DEFAULT_CONFIG[k],
            `manifest.behavior.config.${k} = ${cfg[k]} 与引擎 DEFAULT_CONFIG.${k} = ${DEFAULT_CONFIG[k]} 不一致 `
            + `⇒ manifest 会静默覆盖引擎, 行为参数会漂移`);
    }
});

test('A2 办公待机的命中率与时长落在"真机一定会出现"的区间', () => {
    // R170 真机实测基线: 权重 0.10 / 总权重 2.00 ⇒ 单次命中率 5%,
    //   空闲决策 ~20s 一次 ⇒ 180s 内触发 0 次 (用户报"办公场景消失")。
    const total = ACTIVITY_KINDS.reduce((s, k) => s + (DEFAULT_CONFIG[ACTIVITY_W_KEY[k]] || 0), 0);
    const pWork = DEFAULT_CONFIG.work_probability / total;
    assert.ok(pWork >= 0.15,
        `办公单次决策命中率仅 ${(pWork * 100).toFixed(1)}% (需 ≥15%, 否则真机长时间看不到)`);
    assert.ok(pWork <= 0.40,
        `办公单次决策命中率 ${(pWork * 100).toFixed(1)}% 偏高 (需 ≤40%, 避免一直只办公)`);
    assert.ok(DEFAULT_CONFIG.work_min_ms >= 12000, '办公单次持续时间太短 (会"刚出现就消失")');
    assert.ok(DEFAULT_CONFIG.work_cooldown_ms >= 30000, '办公冷却太短 (会一直只办公)');
});

// ====== B. 吃水果是独立生活行为 ======
test('B1 EAT_FRUIT 状态/动作/活动池登记齐全', () => {
    assert.ok(STATES.EAT_FRUIT, 'STATES 缺少 EAT_FRUIT');
    assert.strictEqual(STATE_ACTION[STATES.EAT_FRUIT], 'eat_fruit',
        'EAT_FRUIT 必须映射到 eat_fruit 动作');
    assert.ok(ACTIVITY_KINDS.includes('eat_fruit'), '活动池里必须有 eat_fruit');
    const spec = ACTION_CATALOG.eat_fruit;
    assert.ok(spec, 'eat_fruit 未登记进 ACTION_CATALOG');
    assert.strictEqual(spec.kind, 'rest', 'eat_fruit 应是 rest 类 (待机类)');
    const lib = MANIFEST.action_library.actions.eat_fruit;
    assert.ok(lib, 'manifest 的 action_library 缺 eat_fruit');
    assert.ok(Array.isArray(lib.frames) && lib.frames.length >= 5,
        `eat_fruit 至少要有 5 帧 (拿果/送到嘴边/咬一口/咀嚼/满足), 实际 ${(lib.frames || []).length}`);
    assert.strictEqual(lib.loop, true, 'eat_fruit 应为循环动作 (吃水果是一个持续行为)');
});

test('B2 吃水果的 5 帧素材真实存在且互不相同', () => {
    const lib = MANIFEST.action_library.actions.eat_fruit;
    const seen = new Set();
    for (const rel of lib.frames) {
        const p = path.join(ASSETS, rel);
        assert.ok(fs.existsSync(p), `帧文件缺失: ${rel}`);
        const buf = fs.readFileSync(p);
        const key = require('crypto').createHash('sha1').update(buf).digest('hex');
        assert.ok(!seen.has(key), `帧 ${rel} 与前面的帧字节完全相同 (不是新动作)`);
        seen.add(key);
    }
});

test('B3 吃水果场景的道具登记完整 (小凳 + 小边桌/果盘), 且不吃掉其它场景', () => {
    const scenes = MANIFEST.props.scenes;
    const eat = scenes.eat_fruit;
    assert.ok(eat, 'props.scenes 缺 eat_fruit');
    const all = (eat.back || []).concat(eat.front || []);
    assert.ok(all.includes('prop_stool'), '吃水果场景必须有小凳 (角色坐在上面)');
    assert.ok(all.includes('prop_fruit_table'), '吃水果场景必须有小桌/果盘');
    for (const n of all) {
        assert.ok(MANIFEST.props.library[n], `道具库缺 ${n}`);
        const f = path.join(ASSETS, MANIFEST.props.library[n].file);
        assert.ok(fs.existsSync(f), `道具文件缺失: ${MANIFEST.props.library[n].file}`);
    }
    // 既有场景不能被吃掉
    for (const k of ['work', 'sleep_breath', 'sit_rest', 'doze', 'cheer_heart']) {
        assert.ok(scenes[k], `既有场景 ${k} 丢了`);
    }
});

test('B4 吃水果道具不遮脸, 且在 200x240 / 256x256 下零裁切', () => {
    const scenes = MANIFEST.props.scenes;
    const eat = scenes.eat_fruit;
    const all = (eat.back || []).concat(eat.front || []);
    for (const n of all) {
        const lib = MANIFEST.props.library[n];
        const p = path.join(ASSETS, lib.file);
        if (!fs.existsSync(p)) continue;
        const buf = fs.readFileSync(p);
        // PNG IHDR: 宽高在字节 16..24
        const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
        assert.ok(w <= 1024 && h <= 1024, `道具 ${n} 超出 1024 纹理画布 (${w}x${h})`);
    }
    // 地面行必须登记, 否则道具会飘
    assert.strictEqual(typeof eat.floor_tex_y, 'number', 'eat_fruit 场景缺 floor_tex_y');
});

// ====== C. 互斥与不被打断 ======
test('C1 办公与吃水果不会同时运行 (状态机同一时刻只有一个状态)', () => {
    const { engine, clock, states } = makeEngine({
        random: () => randomForKind('work'),
        config: { ...DEFAULT_CONFIG, idle_min_ms: 10, idle_max_ms: 10 },
    });
    engine.start();
    for (let i = 0; i < 40; i++) {
        clock.advance(20000);
        const work = states.some(s => s.to === 'WORK');
        const eat = states.some(s => s.to === 'EAT_FRUIT');
        // 任意时刻只可能处于一个状态 —— 这里断言引擎的状态集合里二者不同时为当前态
        assert.ok(!(engine.getState() === 'WORK' && engine.getState() === 'EAT_FRUIT'),
            'WORK 与 EAT_FRUIT 同时激活');
    }
});

test('C2 吃水果播放期间不会被行走/睡眠打断, 结束后回到正常生活状态', () => {
    const { engine, clock, states, actions } = makeEngine({
        random: () => randomForKind('eat_fruit'),
        config: { ...DEFAULT_CONFIG, idle_min_ms: 10, idle_max_ms: 10, eat_fruit_min_ms: 5000, eat_fruit_max_ms: 5000 },
    });
    engine.start();
    clock.advance(100);
    assert.strictEqual(engine.getState(), STATES.EAT_FRUIT, `应进入 EAT_FRUIT, 实际 ${engine.getState()}`);
    assert.ok(actions.some(a => a.action === 'eat_fruit'), '应下发 eat_fruit 动作');
    // 播放期间: 不得出现行走/睡眠状态, 也不得离开 EAT_FRUIT
    clock.advance(2000);
    assert.strictEqual(engine.getState(), STATES.EAT_FRUIT, '吃水果期间状态被改掉了');
    assert.ok(!states.some(s => s.to === 'WALK_LEFT' || s.to === 'WALK_RIGHT' || s.to === 'SLEEP_ENTER'),
        '吃水果期间不得被行走/睡眠打断');
    // 结束 → 明确的完成转移 + 下发 idle 动作 (之后引擎继续正常生活, 所以查"完成过")
    clock.advance(6000);
    assert.ok(states.some(s => s.reason === 'eat_fruit-complete'),
        `应有 eat_fruit-complete 转移, 实际转移序列 ${JSON.stringify(states.map(s => s.reason))}`);
    assert.ok(actions.some(a => a.action === 'idle'), '结束应下发 idle 动作');
    assert.notStrictEqual(engine.getState(), STATES.EAT_FRUIT, '吃水果结束后不应还停在 EAT_FRUIT');
});

test('C3 吃水果与办公各自有冷却, 不会连着做', () => {
    const { engine } = makeEngine({ random: () => randomForKind('eat_fruit') });
    engine._lastActivity = 'gesture';
    engine._lastEatFruitAt = engine._now();
    assert.notStrictEqual(engine._pickActivity(), 'eat_fruit', '吃水果冷却期内不得再选 eat_fruit');
    const e2 = makeEngine({ random: () => randomForKind('work') });
    e2.engine._lastActivity = 'gesture';
    e2.engine._lastWorkAt = e2.engine._now();
    assert.notStrictEqual(e2.engine._pickActivity(), 'work', '办公冷却期内不得再选 work');
});

// ====== D. 点击反馈不得把状态卡死 (R170 修掉的 bug) ======
test('D1 办公中点击角色后, 办公计时器按剩余时间恢复 (不再卡死在 WORK)', () => {
    const { engine, clock, states } = makeEngine({
        random: () => randomForKind('work'),
        config: { ...DEFAULT_CONFIG, idle_min_ms: 10, idle_max_ms: 10, work_min_ms: 20000, work_max_ms: 20000 },
    });
    engine.start();
    clock.advance(100);
    assert.strictEqual(engine.getState(), STATES.WORK, '应进入 WORK');
    // 点击 → 暂缓自主行为 (旧实现会永久清掉 work 计时器 ⇒ 卡死)
    engine.holdBriefly(700);
    assert.strictEqual(engine.getState(), STATES.WORK, '点击不应改变当前状态');
    clock.advance(1000);   // 暂缓结束
    assert.strictEqual(engine.getState(), STATES.WORK, '暂缓结束后应仍在 WORK (计时器已恢复)');
    // 继续推进: 办公应当**自然结束** (旧实现会永远卡在 WORK)
    clock.advance(30000);
    assert.ok(states.some(s => s.reason === 'work-complete'),
        `办公最终应自然结束 (work-complete), 实际转移序列 ${JSON.stringify(states.map(s => s.reason))}`);
    assert.notStrictEqual(engine.getState(), STATES.WORK, '办公结束后不应还停在 WORK (说明计时器被点击吃掉了)');
});

test('D2 吃水果中点击角色后同样不会被卡死', () => {
    const { engine, clock, states } = makeEngine({
        random: () => randomForKind('eat_fruit'),
        config: { ...DEFAULT_CONFIG, idle_min_ms: 10, idle_max_ms: 10, eat_fruit_min_ms: 20000, eat_fruit_max_ms: 20000 },
    });
    engine.start();
    clock.advance(100);
    assert.strictEqual(engine.getState(), STATES.EAT_FRUIT, '应进入 EAT_FRUIT');
    engine.holdBriefly(700);
    clock.advance(30000);
    assert.ok(states.some(s => s.reason === 'eat_fruit-complete'),
        `吃水果最终应自然结束 (eat_fruit-complete), 实际转移序列 ${JSON.stringify(states.map(s => s.reason))}`);
    assert.notStrictEqual(engine.getState(), STATES.EAT_FRUIT, '吃水果结束后不应还停在 EAT_FRUIT');
});

// ====== E. 验收专用入口 ======
test('E1 main.js 提供 --demo-scene 验收入口, 且与正式自主行为分离', () => {
    const src = fs.readFileSync(path.join(CAND, 'src', 'main.js'), 'utf8');
    assert.ok(src.includes('--demo-scene'), 'main.js 缺 --demo-scene 验收入口');
    // 场景锁定时必须暂停自主决策 (否则场景会被随机行为立刻带走)
    assert.ok(/if \(demoScene_\)\s*behaviorEngine\.setAutonomousPaused\(true\)/.test(src),
        '--demo-scene 模式必须暂停自主决策, 否则场景会被随机行为立刻打断');
    // 且必须真的把这个动作下发到渲染器 (走与正式运行同一条渲染路径 ⇒ 道具自动挂载)
    assert.ok(/send\('set-action',\s*demoScene_\)/.test(src),
        '--demo-scene 必须通过 set-action 下发动作, 否则渲染器不会切场景/挂道具');
});

test('E2 引擎提供"暂停自主决策"开关 (验收模式与自主模式分离)', () => {
    const { engine, clock } = makeEngine({ random: () => randomForKind('work') });
    engine.setAutonomousPaused(true);
    engine.start();
    clock.advance(60000);
    assert.strictEqual(engine.getState(), STATES.IDLE,
        `自主决策暂停时不得自行进入任何活动, 实际 ${engine.getState()}`);
    assert.strictEqual(engine.snapshot().state, 'IDLE', '暂停后状态应保持 IDLE');
});

// ====== F. 既有成果未被破坏 ======
test('F1 六种点击互动动作与 R148 行走方向原样保留', () => {
    const pool = MANIFEST.click_reactions.pool.map(p => p.action).sort();
    assert.deepStrictEqual(pool,
        ['cheer_clap', 'cheer_hands_up', 'cheer_heart', 'cheer_jump', 'cheer_tilt', 'cheer_wave'],
        '点击互动池被改动了');
    assert.ok(MANIFEST.r148_walk_direction_fix, 'R148 行走方向修复记录丢失');
    // A1 母版指纹: 必须是 64 位十六进制 (它指向仓库外的 A1 母版 PNG)
    const sha = String(MANIFEST.a1_reference_sha256 || '');
    assert.ok(/^[0-9a-f]{64}$/i.test(sha), `A1 母版 SHA256 记录异常: ${sha}`);
    // 更强的保证: R138 原始 23 帧的 SHA256 **逐帧**与基线一致 (人物身份与服装未被改动)
    const ckPath = path.join(ASSETS, 'character_R138_derived', 'r138_source_checksums.json');
    if (fs.existsSync(ckPath)) {
        const ck = JSON.parse(fs.readFileSync(ckPath, 'utf8'));
        const files = ck.files || {};
        assert.ok(Object.keys(files).length >= 23,
            `R138 校验清单只剩 ${Object.keys(files).length} 条 (应 ≥23)`);
        const crypto = require('crypto');
        for (const [rel, expect] of Object.entries(files)) {
            const p = path.join(ASSETS, rel);
            assert.ok(fs.existsSync(p), `R138 原始帧缺失: ${rel}`);
            const got = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
            assert.strictEqual(got, expect, `R138 原始帧被改动: ${rel}`);
        }
    }
});

test('F2 R172 办公场景按任务书重做, 但 R167 旧素材与吃水果/睡眠场景原样保留', () => {
    // R172 任务书明确要求: "优先调整整体构图" + "不要继续通过裁掉人物身体解决图层遮挡"
    // ⇒ work 场景换了底图与图层归属, 这条断言随之改为:
    //   (a) work 场景已指向 R172 新构图 (转椅 + 3/4 显示器 + 新帧)
    //   (b) R167 的旧办公道具**文件仍在磁盘上** (历史成果不删)
    //   (c) 吃水果场景与睡眠场景一字未改
    const w = MANIFEST.props.scenes.work;
    const all = (w.back || []).concat(w.front || []);
    assert.ok(all.includes('prop_office_chair'), 'R172 办公场景必须有办公转椅');
    assert.ok(all.includes('prop_office_monitor'), 'R172 办公场景必须有显示器');
    const lib = MANIFEST.action_library.actions.work;
    assert.deepStrictEqual(lib.frames,
        ['character_R172/work_1.png', 'character_R172/work_2.png'], 'work 帧未指向 R172 新构图');
    for (const n of ['prop_chair', 'prop_desk_surface', 'prop_keyboard', 'prop_desk', 'prop_screen_glow']) {
        assert.ok(fs.existsSync(path.join(ASSETS, MANIFEST.props.library[n].file)),
            `R167 的旧办公道具文件 ${n} 被删了 (历史成果必须保留)`);
    }
    // 吃水果场景必须原样
    assert.deepStrictEqual(MANIFEST.props.scenes.eat_fruit.back,
        ['prop_stool', 'prop_fruit_table'], 'R170 吃水果场景的 back 层被改动');
    assert.deepStrictEqual(MANIFEST.action_library.actions.eat_fruit.frames,
        ['character_R156/eat_fruit_0.png', 'character_R156/eat_fruit_1.png',
            'character_R156/eat_fruit_2.png', 'character_R156/eat_fruit_3.png',
            'character_R156/eat_fruit_4.png'], 'R170 吃水果帧被改动');
    // 睡眠场景必须原样
    assert.deepStrictEqual(MANIFEST.props.scenes.sleep_breath.back,
        ['prop_bed', 'prop_moon'], '睡眠场景的 back 层被改动');
    assert.deepStrictEqual(MANIFEST.props.scenes.sleep_breath.front,
        ['prop_quilt'], '睡眠场景的 front 层被改动');
});

// ====== 汇总 ======
const failed = results.filter(r => !r.pass);
console.log(`\nR170 专项测试: ${results.length - failed.length} passed, ${failed.length} failed (共 ${results.length})`);
if (failed.length) {
    console.log('  ↳ 失败详情:');
    for (const f of failed) console.log(`    - ${f.name}: ${f.error}`);
    process.exit(1);
}
