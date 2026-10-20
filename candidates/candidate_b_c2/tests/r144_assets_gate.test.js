// R144 资源就绪握手回归测试
//
// R144 P0-3 要求:
//   "Renderer 完成六组 23 帧加载及纹理解码"
//   "检查所有必要动作均可播放"
//   "Renderer 通过明确的 IPC 通知 Main 资源就绪"
//   "Main 收到确认后才正式启动自主行为状态机"
//   "任何必要动作缺帧, 应明确报错并拒绝虚假 PASS"
//   "测试慢速资源加载、部分资源失败及重复 ready 消息"
//
// 本测试直接 require 生产模块 src/asset_gate.js (main.js 用的就是这一份),
// 并用真实 R141 manifest 构造"全量就绪"报告, 验证判定与错误信息。

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const CAND = path.join(__dirname, '..');
const MANIFEST = JSON.parse(fs.readFileSync(path.join(CAND, 'assets', 'character_R141_manifest.json'), 'utf8'));

// ★ 生产门禁模块
const {
    evaluateAssetReadiness, summarizeReport, REQUIRED_ACTIONS,
} = require(path.join(CAND, 'src', 'asset_gate.js'));

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

// 按真实 manifest 构造一份"全部加载成功"的报告
function fullReport() {
    const actions = {};
    let total = 0;
    let loaded = 0;
    for (const action of MANIFEST.animation_order) {
        const n = MANIFEST.actions[action].frames.length;
        actions[action] = { loaded: n, failed: 0, total: n };
        total += n;
        loaded += n;
    }
    return { ok: true, total, loaded, failed: 0, actions };
}

// ====== 测试 1: 必要动作清单 = 6 组 ======
test('T1 必要动作清单为行为引擎所需的 6 组', () => {
    assert.deepStrictEqual([...REQUIRED_ACTIONS],
        ['idle', 'walk_left', 'walk_right', 'sleep_enter', 'sleep_loop', 'wake_up']);
});

// ====== 测试 2: 真实 manifest 全量就绪 → 通过 ======
test('T2 23 帧全部就绪时判定通过 (loaded=23/23)', () => {
    const report = fullReport();
    assert.strictEqual(report.loaded, 23, `真实 manifest 应为 23 帧, 实际 ${report.loaded}`);
    const v = evaluateAssetReadiness(report, REQUIRED_ACTIONS);
    assert.ok(v.ok, `应通过但未通过: ${v.errors.join(' | ')}`);
    assert.strictEqual(v.errors.length, 0);
    assert.strictEqual(v.loaded, 23);
    assert.strictEqual(v.total, 23);
});

// ====== 测试 3: 缺少整组动作 → 拒绝 + 明确报错 ======
test('T3 必要动作整组缺失时拒绝启动并给出明确错误', () => {
    const report = fullReport();
    delete report.actions.sleep_loop;
    const v = evaluateAssetReadiness(report, REQUIRED_ACTIONS);
    assert.ok(!v.ok, '缺组时竟判定通过 (虚假 PASS)');
    assert.ok(v.errors.some(e => e.includes('sleep_loop')), `错误信息未指出缺失动作: ${v.errors.join('|')}`);
});

// ====== 测试 4: 某动作 0 帧 → 拒绝 ======
test('T4 必要动作 0 帧时拒绝启动并给出明确错误', () => {
    const report = fullReport();
    report.actions.wake_up = { loaded: 0, failed: 3, total: 3 };
    report.loaded -= 3;
    const v = evaluateAssetReadiness(report, REQUIRED_ACTIONS);
    assert.ok(!v.ok, '0 帧时竟判定通过');
    assert.ok(v.errors.some(e => e.includes('wake_up')), `错误信息未指出动作: ${v.errors.join('|')}`);
});

// ====== 测试 5: 部分资源失败 → 拒绝 ======
test('T5 部分帧加载失败时拒绝启动 (不假装全好)', () => {
    const report = fullReport();
    report.actions.idle = { loaded: 5, failed: 1, total: 6 };
    report.loaded -= 1;
    report.failed = 1;
    const v = evaluateAssetReadiness(report, REQUIRED_ACTIONS);
    assert.ok(!v.ok, '有失败帧时竟判定通过');
    assert.ok(v.errors.some(e => e.includes('失败')), `错误信息未说明失败: ${v.errors.join('|')}`);
});

// ====== 测试 6: 帧数不完整 → 拒绝 ======
test('T6 帧数与 manifest 不一致时拒绝启动', () => {
    const report = fullReport();
    report.actions.idle = { loaded: 6, failed: 0, total: 9 };
    const v = evaluateAssetReadiness(report, REQUIRED_ACTIONS);
    assert.ok(!v.ok, '帧数不完整时竟判定通过');
    assert.ok(v.errors.some(e => e.includes('不完整')), `错误信息未说明不完整: ${v.errors.join('|')}`);
});

// ====== 测试 7: 空报告 / 总数为 0 → 拒绝 ======
test('T7 空报告或总帧数为 0 时拒绝启动', () => {
    const v1 = evaluateAssetReadiness(null, REQUIRED_ACTIONS);
    assert.ok(!v1.ok, '空报告竟判定通过');
    const v2 = evaluateAssetReadiness({ total: 0, loaded: 0, actions: {} }, REQUIRED_ACTIONS);
    assert.ok(!v2.ok, '总帧数 0 竟判定通过');
    assert.ok(v2.errors.some(e => e.includes('0')), `错误信息未说明: ${v2.errors.join('|')}`);
});

// ====== 测试 8: 慢速加载不影响判定 (只是晚到) ======
test('T8 慢速加载场景: 迟到的就绪报告仍能正确放行', () => {
    // 模拟: 先来一份"还没加载完"的报告 (不应放行), 再来一份完整的 (应放行)
    const partial = { ok: true, total: 23, loaded: 0, failed: 0, actions: {} };
    const v1 = evaluateAssetReadiness(partial, REQUIRED_ACTIONS);
    assert.ok(!v1.ok, '未加载完却放行');
    const v2 = evaluateAssetReadiness(fullReport(), REQUIRED_ACTIONS);
    assert.ok(v2.ok, '加载完成后未放行');
});

// ====== 测试 9: 汇总函数 ======
test('T9 summarizeReport 正确汇总每动作帧数', () => {
    const s = summarizeReport(fullReport());
    assert.strictEqual(Object.keys(s).length, 6);
    assert.strictEqual(s.idle.loaded, 6);
    assert.strictEqual(s.sleep_enter.loaded, 3);
    assert.strictEqual(s.sleep_enter.failed, 0);
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R144 资源就绪握手测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) {
        console.log(`  - ${r.name}: ${r.error}`);
    }
    process.exit(1);
}
process.exit(0);
