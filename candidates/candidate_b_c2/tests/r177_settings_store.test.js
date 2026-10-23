// R177 本地数据保存 (设置 + 基础心情状态) 单元测试
//
// 覆盖 R177 任务书 §一.4 的可验收项:
//   · 本地存储设置与基础心情状态
//   · 重启后能正确恢复
//   · 不联网、不上传
//   · 写入是原子的 (临时文件 + rename), 损坏文件回退默认值且**不拖垮启动**
//
// 被测生产模块: src/settings_store.js (生产代码本体)
// 运行: node tests/r177_settings_store.test.js
'use strict';

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');

const CAND = path.join(__dirname, '..');
const STORE_PATH = path.join(CAND, 'src', 'settings_store.js');
const {
    DEFAULT_SETTINGS, SCALE_MIN, SCALE_MAX, RATES,
    ACTIVITY_RATE_TABLE, SLEEP_RATE_TABLE,
    SETTINGS_FILE, MOOD_FILE,
    SettingsStore, sanitizeSettings, rateEffects, commitSettings,
} = require(STORE_PATH);

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

function tmpDir(tag) {
    const d = fs.mkdtempSync(path.join(os.tmpdir(), `r177_settings_${tag}_`));
    return d;
}

// ====== S1: 默认值 ======
test('S1 默认设置符合任务书 (大小 1.0 / 频率 normal / 点击反馈开 / 自启关)', () => {
    assert.strictEqual(DEFAULT_SETTINGS.pet_scale, 1.0);
    assert.strictEqual(DEFAULT_SETTINGS.activity_rate, 'normal');
    assert.strictEqual(DEFAULT_SETTINGS.sleep_rate, 'normal');
    assert.strictEqual(DEFAULT_SETTINGS.click_feedback, true);
    assert.strictEqual(DEFAULT_SETTINGS.launch_at_login, false);
    assert.strictEqual(SCALE_MIN, 0.6);
    assert.strictEqual(SCALE_MAX, 1.6);
    assert.deepStrictEqual(RATES.slice(), ['low', 'normal', 'high']);
});

// ====== S2: 保存 → 读取 往返 ======
test('S2 保存后能原样读回 (重启恢复的基础)', () => {
    const dir = tmpDir('roundtrip');
    const store = new SettingsStore({ dir });
    const patch = {
        pet_scale: 1.25,
        activity_rate: 'high',
        sleep_rate: 'low',
        click_feedback: false,
        launch_at_login: true,
    };
    const res = store.saveSettings(patch);
    assert.strictEqual(res.ok, true);
    assert.deepStrictEqual(res.settings, patch);

    // 模拟"重启": 全新 store 实例读同一个目录
    const store2 = new SettingsStore({ dir });
    assert.deepStrictEqual(store2.loadSettings(), patch);
});

// ====== S3: 大小被夹在合法区间 ======
test('S3 桌宠大小越界会被夹回 [0.6, 1.6]', () => {
    const dir = tmpDir('scale');
    const store = new SettingsStore({ dir });
    assert.strictEqual(store.saveSettings({ pet_scale: 99 }).settings.pet_scale, SCALE_MAX);
    assert.strictEqual(store.saveSettings({ pet_scale: 0.01 }).settings.pet_scale, SCALE_MIN);
    assert.strictEqual(store.saveSettings({ pet_scale: 1.234 }).settings.pet_scale, 1.23);
    // 写坏的值 (NaN / 字符串) → 保持默认值
    assert.strictEqual(store.saveSettings({ pet_scale: 'abc' }).settings.pet_scale, 1.0);
});

// ====== S4: 非法枚举/布尔 → 回退默认 ======
test('S4 非法枚举与非法布尔一律回退默认值, 不写坏数据', () => {
    const dir = tmpDir('enum');
    const store = new SettingsStore({ dir });
    const r = store.saveSettings({
        activity_rate: 'super_fast',
        sleep_rate: 123,
        click_feedback: 'yes',
        launch_at_login: 'true',
    });
    assert.strictEqual(r.settings.activity_rate, 'normal');
    assert.strictEqual(r.settings.sleep_rate, 'normal');
    assert.strictEqual(r.settings.click_feedback, true);
    assert.strictEqual(r.settings.launch_at_login, false);
});

// ====== S5: 逐字段合并 (不整体替换) ======
test('S5 只改一个字段时, 其余字段保持原值', () => {
    const dir = tmpDir('merge');
    const store = new SettingsStore({ dir });
    store.saveSettings({ pet_scale: 1.4, activity_rate: 'high' });
    const r = store.saveSettings({ click_feedback: false });
    assert.strictEqual(r.settings.pet_scale, 1.4);
    assert.strictEqual(r.settings.activity_rate, 'high');
    assert.strictEqual(r.settings.click_feedback, false);
});

// ====== S6: 文件损坏 → 回退默认值, 不抛异常 ======
test('S6 设置文件损坏 → 回退默认值且不抛异常 (不能拖垮启动)', () => {
    const dir = tmpDir('corrupt');
    fs.writeFileSync(path.join(dir, SETTINGS_FILE), '{ this is not json ', 'utf8');
    const store = new SettingsStore({ dir });
    let settings = null;
    assert.doesNotThrow(() => { settings = store.loadSettings(); });
    assert.deepStrictEqual(settings, Object.assign({}, DEFAULT_SETTINGS));
});

// ====== S7: 空文件 / 只有空白 → 默认值 ======
test('S7 空文件或纯空白文件 → 默认值', () => {
    const dir = tmpDir('empty');
    fs.writeFileSync(path.join(dir, SETTINGS_FILE), '   \n\t ', 'utf8');
    const store = new SettingsStore({ dir });
    assert.deepStrictEqual(store.loadSettings(), Object.assign({}, DEFAULT_SETTINGS));
});

// ====== S8: 原子写不留临时文件 ======
test('S8 写入是原子的: 目录里不残留 .tmp 文件', () => {
    const dir = tmpDir('atomic');
    const store = new SettingsStore({ dir });
    store.saveSettings({ pet_scale: 1.1 });
    const leftovers = fs.readdirSync(dir).filter((f) => f.endsWith('.tmp'));
    assert.deepStrictEqual(leftovers, [], `残留临时文件: ${leftovers.join(',')}`);
    assert.ok(fs.existsSync(path.join(dir, SETTINGS_FILE)));
});

// ====== S9: 心情状态保存 / 读取 ======
test('S9 基础心情状态能保存并读回', () => {
    const dir = tmpDir('mood');
    const store = new SettingsStore({ dir });
    const state = { version: 1, mood: 'happy', energy: 0.8, interactionCount: 3, sleepCount: 1 };
    assert.strictEqual(store.saveMoodState(state), true);
    const back = store.loadMoodState();
    assert.strictEqual(back.mood, 'happy');
    assert.strictEqual(back.energy, 0.8);
    assert.strictEqual(back.interactionCount, 3);
    assert.strictEqual(back.sleepCount, 1);
});

// ====== S10: 心情文件损坏 → null (不抛) ======
test('S10 心情状态文件损坏 → 返回 null 且不抛异常', () => {
    const dir = tmpDir('moodbad');
    fs.writeFileSync(path.join(dir, MOOD_FILE), '<<<not json', 'utf8');
    const store = new SettingsStore({ dir });
    let v = 'x';
    assert.doesNotThrow(() => { v = store.loadMoodState(); });
    assert.strictEqual(v, null);
    // 空状态不允许写入
    assert.strictEqual(store.saveMoodState(null), false);
});

// ====== S11: 频率档位 → 行为参数 ======
test('S11 频率档位换算正确 (活动间隔/活动权重/睡眠权重)', () => {
    const low = rateEffects('low', 'low');
    const normal = rateEffects('normal', 'normal');
    const high = rateEffects('high', 'high');
    assert.strictEqual(low.idle_interval, ACTIVITY_RATE_TABLE.low.interval);
    assert.strictEqual(normal.idle_interval, 1.0);
    assert.strictEqual(high.idle_interval, ACTIVITY_RATE_TABLE.high.interval);
    assert.strictEqual(low.activity_weight, 0.6);
    assert.strictEqual(high.activity_weight, 1.4);
    assert.strictEqual(low.sleep_weight, SLEEP_RATE_TABLE.low.sleep);
    assert.strictEqual(high.sleep_weight, SLEEP_RATE_TABLE.high.sleep);
    // 活动越频繁 ⇒ 间隔越短
    assert.ok(high.idle_interval < normal.idle_interval);
    assert.ok(normal.idle_interval < low.idle_interval);
    // 睡眠频率与活动频率互不影响
    assert.strictEqual(rateEffects('low', 'high').idle_interval, ACTIVITY_RATE_TABLE.low.interval);
    assert.strictEqual(rateEffects('low', 'high').sleep_weight, SLEEP_RATE_TABLE.high.sleep);
    // 非法档位 → normal
    assert.deepStrictEqual(rateEffects('nope', 'nope'), rateEffects('normal', 'normal'));
});

// ====== S12: sanitizeSettings 纯函数 ======
test('S12 sanitizeSettings 对任意输入都返回合法设置', () => {
    const s = sanitizeSettings(null);
    assert.deepStrictEqual(s, Object.assign({}, DEFAULT_SETTINGS));
    const s2 = sanitizeSettings({ pet_scale: 'x', activity_rate: 1 });
    assert.strictEqual(s2.pet_scale, 1.0);
    assert.strictEqual(s2.activity_rate, 'normal');
});

// ====== S13: 【硬边界】不联网、不上传 ======
test('S13 设置存储不联网、不上传 (源码里没有任何网络调用)', () => {
    const src = fs.readFileSync(STORE_PATH, 'utf8');
    assert.ok(!/https?:\/\//i.test(src), '源码里不应出现 http(s) 地址');
    assert.ok(!/\bfetch\s*\(/i.test(src), '源码里不应出现 fetch(');
    assert.ok(!/XMLHttpRequest/i.test(src), '源码里不应出现 XMLHttpRequest');
    assert.ok(!/\baxios\b/i.test(src), '源码里不应出现 axios');
    assert.ok(!/require\(['"]net['"]\)|require\(['"]https?['"]\)|require\(['"]dgram['"]\)/i.test(src),
        '源码里不应 require 网络模块');
    // 只允许读两个本地文件
    assert.ok(src.includes(SETTINGS_FILE));
    assert.ok(src.includes(MOOD_FILE));
});

// ====== S14: loadAll 一次读全 ======
test('S14 loadAll 一次读出设置与心情状态', () => {
    const dir = tmpDir('loadall');
    const store = new SettingsStore({ dir });
    store.saveSettings({ pet_scale: 0.8 });
    store.saveMoodState({ mood: 'calm', energy: 0.5 });
    const all = store.loadAll();
    assert.strictEqual(all.settings.pet_scale, 0.8);
    assert.strictEqual(all.mood.mood, 'calm');
});

// ====== S15: commitSettings 成功路径 ======
test('S15 commitSettings: 落盘成功 ⇒ ok=true 且返回合并后的设置', () => {
    const dir = tmpDir('commit_ok');
    const store = new SettingsStore({ dir });
    const current = Object.assign({}, DEFAULT_SETTINGS);
    const r = commitSettings(store, { pet_scale: 1.3 }, current);
    assert.strictEqual(r.ok, true);
    assert.strictEqual(r.saved, true);
    assert.strictEqual(r.error, null);
    assert.strictEqual(r.settings.pet_scale, 1.3);
    // 真的落盘了
    const disk = JSON.parse(fs.readFileSync(path.join(dir, SETTINGS_FILE), 'utf8'));
    assert.strictEqual(disk.pet_scale, 1.3);
});

// ====== S16: commitSettings 失败路径 (R179 核心) ======
test('S16 commitSettings: 落盘失败 ⇒ ok=false, 设置保持原值, 错误原因明确', () => {
    const dir = tmpDir('commit_fail');
    // 把存储目录指到一个**普通文件**上 ⇒ 写入必然失败 (ENOTDIR), 模拟磁盘/权限问题
    const notADir = path.join(dir, 'not_a_dir');
    fs.writeFileSync(notADir, 'x', 'utf8');
    const store = new SettingsStore({ dir: notADir });

    const current = Object.assign({}, DEFAULT_SETTINGS);
    const r = commitSettings(store, { pet_scale: 1.3 }, current);
    assert.strictEqual(r.ok, false, '落盘失败时 ok 必须是 false (旧实现会误报 true)');
    assert.strictEqual(r.saved, false);
    assert.ok(r.error && String(r.error).length > 0, '失败必须带错误原因');
    // 设置必须**保持原值** (没存上就不能当成改了)
    assert.strictEqual(r.settings.pet_scale, current.pet_scale);
    assert.deepStrictEqual(r.settings, current);
});

// ====== S17: 失败时磁盘上确实没写出文件 ======
test('S17 落盘失败时磁盘上确实没有写出设置文件', () => {
    const dir = tmpDir('commit_fail2');
    const notADir = path.join(dir, 'not_a_dir');
    fs.writeFileSync(notADir, 'x', 'utf8');
    const store = new SettingsStore({ dir: notADir });
    const r = commitSettings(store, { activity_rate: 'high' }, Object.assign({}, DEFAULT_SETTINGS));
    assert.strictEqual(r.ok, false);
    assert.strictEqual(fs.existsSync(path.join(notADir, SETTINGS_FILE)), false);
});

// ====== S18: store 不存在时也不能谎报成功 ======
test('S18 store 未就绪 ⇒ ok=false 而不是 ok=true', () => {
    const r = commitSettings(null, { pet_scale: 1.1 }, Object.assign({}, DEFAULT_SETTINGS));
    assert.strictEqual(r.ok, false);
    assert.strictEqual(r.saved, false);
    assert.ok(r.error);
    assert.strictEqual(r.settings.pet_scale, DEFAULT_SETTINGS.pet_scale);
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R177 设置存储 单元测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) {
        console.log(`  - ${r.name}: ${r.error}`);
    }
    process.exit(1);
}
process.exit(0);
