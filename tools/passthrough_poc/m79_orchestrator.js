// tools/passthrough_poc/m79_orchestrator.js
//
// V0.0 R86 测试调度器 (R82 基础 + 真实 bug 修复)
//
// R86 修复 (基于 GPT 独立源码审计):
//   1. clickJson 改 async, 所有调用 await, 避免 Promise 未解析错
//   2. 任何 FAIL 路径不写 exit 0 — 退出码与 JSON 状态一致
//   3. control_buttons 键名统一小写 (与 control.html 一致)
//   4. IPC r67_get_state 改 handle (匹配 renderer invoke)
//   5. 跨 stdout 数据块 JSON 行缓冲 (R85 之后)
//   6. 每次 click 前 recheck 几何
//   7. 任何必测 FAIL → exit 非 0, 拒绝假 PASS

const { spawn, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const HERE = __dirname;
const REPO = path.resolve(HERE, '..', '..');
const POC = path.join(HERE, 'main.js');
const CLICKER = path.join(HERE, 'build', 'm79_native_click');
const POC_CWD = path.join(REPO, 'candidates', 'candidate_b_electronpixir');
const ELECTRON_BIN = path.join(POC_CWD, 'node_modules', '.bin', 'electron');

function nowIso() { return new Date().toISOString(); }
function runId() { return 'm86_' + Date.now(); }

// R86: 同步 helper. 返回 {ok, code, json, stderr, error}
// 仅在 m79 CLI exit=0 且 stdout 是合法 JSON (且 result 不是 FAIL/BLOCKED) 时 ok=true.
async function clickJson(args) {
    return new Promise((resolve) => {
        const r = spawnSync(CLICKER, args, { encoding: 'utf-8', timeout: 5000 });
        if (r.error) {
            return resolve({ ok: false, code: -1, json: null, stderr: r.error.message });
        }
        const code = r.status;
        if (code !== 0) {
            return resolve({ ok: false, code, json: null, stderr: (r.stderr || r.stdout || '').trim() });
        }
        let parsed = null;
        try { parsed = JSON.parse((r.stdout || '').trim() || '{}'); }
        catch { return resolve({ ok: false, code, json: null, stderr: 'json parse error' }); }
        // R86: 严格按 json.result 判断 OK / FAIL / BLOCKED
        const result = parsed.result;
        if (result !== 'OK' && result !== 'SELFTEST_OK') {
            return resolve({ ok: false, code, json: parsed, stderr: `m79 result=${result}` });
        }
        return resolve({ ok: true, code, json: parsed, stderr: '' });
    });
}

// Tick handler — 跨数据块行缓冲, 不丢半个 JSON 行
function makeTickAccumulator(latestTick) {
    let buf = '';
    return (data) => {
        if (!data) return;
        buf += data;
        let nl;
        while ((nl = buf.indexOf('\n')) >= 0) {
            const line = buf.slice(0, nl).trim();
            buf = buf.slice(nl + 1);
            if (!line) continue;
            try {
                const j = JSON.parse(line);
                if (j && j.type === 'poc-tick') {
                    Object.assign(latestTick, j);
                    latestTick.__updated = Date.now();
                }
            } catch (e) {
                // ignore partial JSON
            }
        }
    };
}

function recentTick(latestTick, maxAgeMs) {
    if (!latestTick.__updated) return null;
    if (Date.now() - latestTick.__updated > maxAgeMs) return null;
    return latestTick;
}

function calcValidPoint(tick) {
    const tw = tick.test_window, pb = tick.probe_button, cw = tick.control_window, sp = tick.sprite;
    if (!tw || !pb || !cw || !sp) return null;
    for (let y = pb.y; y < pb.y + pb.h; y += 2) {
        for (let x = pb.x; x < pb.x + pb.w; x += 2) {
            if (x < tw.x || x >= tw.x + tw.w || y < tw.y || y >= tw.y + tw.h) continue;
            const dx = x - sp.cx, dy = y - sp.cy;
            if (Math.hypot(dx, dy) < sp.r) continue;
            if (x >= cw.x && x < cw.x + cw.w && y >= cw.y && y < cw.y + cw.h) continue;
            return { x, y };
        }
    }
    return null;
}

function c1ButtonCenter(tick) {
    // R86: 统一小写键名 (control.html map[b.dataset.mode] 实际写 C1, 但
    // 我们 orchestrator 与 control.html 都统一用小写, control.html 已
    // 改为小写数据键. 兼容小写 + 大写 两种 case.)
    if (tick && tick.control_buttons) {
        const c1 = tick.control_buttons.c1 || tick.control_buttons.C1;
        if (c1) return { x: c1.x + c1.w / 2, y: c1.y + c1.h / 2, source: 'control_buttons' };
    }
    return null;
}

function goldBall(tick) {
    const sp = tick.sprite;
    return sp ? { x: sp.cx || 448, y: sp.cy || 328, r: sp.r || 50 } : { x: 448, y: 328, r: 50 };
}

function clicks(p) { return p.clicks || {}; }

async function main() {
    const rid = runId();
    const base = `/tmp/${rid}`;
    const result = {
        run_id: rid, started_at: nowIso(), finished_at: '',
        accessibility_granted: false, input_monitoring_required: false,
        control_click: 'NOT_TESTED', gold_ball_click: 'NOT_TESTED',
        underlying_click: 'NOT_TESTED', return_click: 'NOT_TESTED',
        three_cycle_stable: 'NOT_TESTED', notes: [],
    };
    let exitCode = 0;
    let poc = null;

    function fail(step, code, note) {
        if (note) result.notes.push(note);
        try { if (poc) poc.kill('SIGTERM'); } catch {}
        return writeResult(base, result, code, step);
    }

    // Step 1: check binary
    if (!fs.existsSync(CLICKER)) { result.notes.push('clicker not built'); return writeResult(base, result, 2, 'binary'); }
    if (!fs.existsSync(ELECTRON_BIN)) { result.notes.push('electron not found'); return writeResult(base, result, 2, 'electron'); }

    // Step 2: AX check (await)
    const ax = await clickJson(['--ax-check']);
    if (!ax.ok) { result.notes.push('AX: ' + (ax.stderr || 'failed')); return writeResult(base, result, 1, 'AX'); }
    result.accessibility_granted = true;

    // Step 3: self-test (await)
    const st = await clickJson(['--self-test']);
    if (!st.ok) { result.notes.push('self-test: ' + (st.stderr || 'failed')); return writeResult(base, result, 1, 'self-test'); }

    // Step 4: launch PoC with --mode=A
    const latestTick = {};
    const handle = makeTickAccumulator(latestTick);
    poc = spawn(ELECTRON_BIN, [POC, '--mode=A', '--quit-after=30'], { cwd: POC_CWD, stdio: ['ignore', 'pipe', 'pipe'] });
    poc.stdout.on('data', d => handle(d.toString()));
    poc.stderr.on('data', () => {});

    const start = Date.now();
    while (Date.now() - start < 8000) {
        if (recentTick(latestTick, 5000)) break;
        await new Promise(r => setTimeout(r, 100));
    }
    const first = recentTick(latestTick, 5000);
    if (!first) { result.notes.push('no tick in 8s'); return fail('PoC', 6, 'no tick'); }
    if (first.mode !== 'A') { result.notes.push(`PoC mode=${first.mode}, expected A`); return fail('PoC-start-mode', 7); }

    async function recheck(maxMs = 1500) {
        const t0 = Date.now();
        while (Date.now() - t0 < maxMs) {
            const t = recentTick(latestTick, 200);
            if (t) return t;
            await new Promise(r => setTimeout(r, 80));
        }
        return null;
    }

    // Step 5: C1 click
    const t0 = await recheck();
    if (!t0) { result.notes.push('no tick recheck'); return fail('recheck', 6); }
    const c1 = c1ButtonCenter(t0);
    if (!c1) { result.notes.push('C1 button rect not in tick.control_buttons (R82 §三 真实 bug 修复后应 OK)'); return fail('C1-rect', 8); }
    const c1r = await clickJson([String(c1.x), String(c1.y)]);
    if (!c1r.ok) {
        result.control_click = `FAIL (${c1r.stderr})`;
        return fail('C1-click', 5, `C1 click failed: ${c1r.stderr}`);
    }
    await new Promise(r => setTimeout(r, 500));
    const t1 = await recheck();
    if (t1 && t1.mode === 'C1') {
        result.control_click = 'PASS (mode A -> C1)';
    } else {
        result.control_click = `FAIL (mode=${t1 ? t1.mode : '?'})`;
        return fail('mode-switch', 4, 'mode did not switch to C1');
    }

    // Step 6: gold click
    const t6 = await recheck();
    const gold = goldBall(t6);
    if (!gold) { result.notes.push('no gold ball geometry'); return fail('gold-geom', 6); }
    const beforeT = clicks(t6).test || 0;
    const gc = await clickJson([String(gold.x), String(gold.y)]);
    if (!gc.ok) { result.gold_ball_click = `FAIL (${gc.stderr})`; return fail('gold-click', 5); }
    await new Promise(r => setTimeout(r, 500));
    const t6b = await recheck();
    const afterT = clicks(t6b).test || 0;
    if (afterT === beforeT + 1) result.gold_ball_click = `PASS (test ${beforeT} -> ${afterT})`;
    else { result.gold_ball_click = `FAIL (test ${beforeT} -> ${afterT})`; return fail('gold-count', 5, 'gold count mismatch'); }

    // Step 7: transparent
    const t7 = await recheck();
    const valid = calcValidPoint(t7);
    if (!valid) { result.notes.push('GEOMETRY_INVALID'); return fail('geom', 3); }
    const beforeP = clicks(t7).probe || 0;
    const tc = await clickJson([String(valid.x), String(valid.y)]);
    if (!tc.ok) { result.underlying_click = `FAIL (${tc.stderr})`; return fail('trans-click', 5); }
    await new Promise(r => setTimeout(r, 500));
    const t7b = await recheck();
    const afterP = clicks(t7b).probe || 0;
    if (afterP === beforeP + 1) result.underlying_click = `PASS (probe ${beforeP} -> ${afterP})`;
    else { result.underlying_click = `FAIL (probe ${beforeP} -> ${afterP})`; return fail('probe-count', 5, 'probe count mismatch'); }

    // Step 8: return to gold
    const t8 = await recheck();
    const goldR = goldBall(t8);
    if (goldR) {
        const beforeR = clicks(t8).test || 0;
        const rc = await clickJson([String(goldR.x), String(goldR.y)]);
        if (!rc.ok) { result.return_click = `FAIL (${rc.stderr})`; return fail('return-click', 5); }
        await new Promise(r => setTimeout(r, 500));
        const t8b = await recheck();
        const afterR = clicks(t8b).test || 0;
        if (afterR === beforeR + 1) result.return_click = `PASS (test ${beforeR} -> ${afterR})`;
        else { result.return_click = `FAIL (test ${beforeR} -> ${afterR})`; return fail('return-count', 5, 'return count mismatch'); }
    } else {
        result.return_click = 'FAIL (no gold)'; return fail('gold-geom', 6);
    }

    // Step 9: 3 cycles
    let lastT = clicks(await recheck()).test || 0;
    let lastP = clicks(await recheck()).probe || 0;
    let cycleOK = true;
    for (let i = 0; i < 3; i++) {
        const v2 = calcValidPoint(await recheck());
        const g2 = goldBall(await recheck());
        if (!v2 || !g2) { cycleOK = false; break; }
        const tc1 = await clickJson([String(v2.x), String(v2.y)]);
        const gc1 = await clickJson([String(g2.x), String(g2.y)]);
        if (!tc1.ok || !gc1.ok) { cycleOK = false; break; }
        await new Promise(r => setTimeout(r, 500));
        const tN = clicks(await recheck());
        const tn = tN.test || 0, pn = tN.probe || 0;
        if (tn === lastT + 1 && pn === lastP + 1) { lastT = tn; lastP = pn; }
        else { cycleOK = false; break; }
    }
    result.three_cycle_stable = cycleOK ? 'PASS' : 'FAIL';
    if (!cycleOK) { result.notes.push('3-cycle stability failed'); return fail('cycle', 5, '3-cycle failed'); }

    try { if (poc) poc.kill('SIGTERM'); } catch {}
    return writeResult(base, result, 0, 'OK');
}

function writeResult(base, r, exitCode, label) {
    r.finished_at = nowIso();
    if (label) r.notes.push(`stage=${label}`);
    fs.writeFileSync(base + '.json', JSON.stringify(r, null, 2));
    let s = `=== R86 Orchestrator Result ===\nrun_id: ${r.run_id}\nfinished_at: ${r.finished_at}\naccessibility_granted: ${r.accessibility_granted}\ncontrol_click: ${r.control_click}\ngold_ball_click: ${r.gold_ball_click}\nunderlying_click: ${r.underlying_click}\nreturn_click: ${r.return_click}\nthree_cycle_stable: ${r.three_cycle_stable}\nexit_code: ${exitCode}\nnotes: ${(r.notes || []).join(' | ')}\n`;
    fs.writeFileSync(base + '.txt', s);
    let csv = 'run_id,accessibility,control_click,gold_ball_click,underlying_click,return_click,three_cycle_stable,exit_code\n';
    csv += `${r.run_id},${r.accessibility_granted},${r.control_click},${r.gold_ball_click},${r.underlying_click},${r.return_click},${r.three_cycle_stable},${exitCode}\n`;
    fs.writeFileSync(base + '.csv', csv);
    console.log(`-> wrote ${base}.{txt,json,csv} exit=${exitCode}`);
    return exitCode;
}

main().then(code => process.exit(code || 0)).catch(e => {
    console.error('orchestrator error:', e);
    process.exit(99);
});
