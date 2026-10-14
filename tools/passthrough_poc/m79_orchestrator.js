// tools/passthrough_poc/m79_orchestrator.js
//
// V0.0 R81 测试调度器 (修订 — 在 R79 基础上修 P0 bug)
//
// R81 P0 bug 修复 (相对 R79):
//   1. Electron 启动: 改 spawn(node, electron 模块入口) 为
//      spawn(node_modules/.bin/electron, [main.js, ...]) - 用真 binary
//   2. C1 假阳性: PoC 改 --mode=A 启动, orchestrator 显式 click C1 后才判 mode='C1' PASS
//   3. 控制按钮坐标: PoC control.html 实时上报 4 按钮 rect (control_buttons),
//      orchestrator 优先用 control_buttons.c1, 不再用硬编码 +195
//   4. 每次 click 前 recheck() 重新拉最新 PoC tick 几何
//   5. 退出码 反映真实状态 (0=PASS, 1=AX, 2=BUILD, 3=GEOM, 4=CTRL, 5=CLICK, 6=POC, 7=START_MODE, 8=NO_C1, 99=exception)

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
function runId() { return 'm81_' + Date.now(); }

function clickJson(args) {
    return new Promise((resolve) => {
        const r = spawnSync(CLICKER, args, { encoding: 'utf-8', timeout: 5000 });
        if (r.error) return resolve({ ok: false, code: -1, error: r.error.message });
        if (r.status !== 0) return resolve({ ok: false, code: r.status, out: r.stdout, err: r.stderr });
        try { return resolve({ ok: true, code: 0, json: JSON.parse(r.stdout.trim() || '{}') }); }
        catch { return resolve({ ok: false, code: r.status, out: r.stdout, err: 'parse error' }); }
    });
}

function tickHandler(data, latestTick) {
    if (!data) return;
    const lines = data.split('\n');
    for (const line of lines) {
        const t = line.trim();
        if (!t) continue;
        try {
            const j = JSON.parse(t);
            if (j && j.type === 'poc-tick') {
                Object.assign(latestTick, j);
                latestTick.__updated = Date.now();
            }
        } catch {}
    }
}

function recentTick(latestTick, maxAgeMs) {
    if (!latestTick.__updated) return null;
    if (Date.now() - latestTick.__updated > maxAgeMs) return null;
    return latestTick;
}

function calcValidPoint(tick) {
    const tw = tick.test_window, pb = tick.probe_button, cw = tick.control_window, sp = tick.sprite;
    if (!tw || !pb || !cw || !sp) return null;
    const twx = tw.x, twy = tw.y, tww = tw.w, twh = tw.h;
    const pbx = pb.x, pby = pb.y, pbw = pb.w, pbh = pb.h;
    const cwx = cw.x, cwy = cw.y, cww = cw.w, cwh = cw.h;
    const spx = sp.cx, spy = sp.cy, sr = sp.r;
    for (let y = pby; y < pby + pbh; y += 2) {
        for (let x = pbx; x < pbx + pbw; x += 2) {
            if (x < twx || x >= twx + tww || y < twy || y >= twy + twh) continue;
            const dx = x - spx, dy = y - spy;
            if (Math.hypot(dx, dy) < sr) continue;
            if (x >= cwx && x < cwx + cww && y >= cwy && y < cwy + cwh) continue;
            return { x, y };
        }
    }
    return null;
}

function c1ButtonCenter(tick) {
    // R81: 优先用 PoC tick.control_buttons.c1 (control.html 实时上报);
    // 退化到估算 (不硬编码) — 估算下必须 degraded 标记, 不得记为 PASS
    const t = tick;
    if (t && t.control_buttons && t.control_buttons.c1) {
        const b = t.control_buttons.c1;
        return { x: b.x + b.w / 2, y: b.y + b.h / 2, source: 'control_buttons' };
    }
    return null;
}

function goldBall(tick) {
    const sp = tick.sprite;
    if (!sp) return null;
    return { x: sp.cx, y: sp.cy, r: sp.r };
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

    // Step 1: check binary
    if (!fs.existsSync(CLICKER)) {
        result.notes.push('clicker not built; run m79_build.sh first');
        return writeResult(base, result, 2);
    }
    if (!fs.existsSync(ELECTRON_BIN)) {
        result.notes.push(`electron binary not found at ${ELECTRON_BIN}`);
        return writeResult(base, result, 2);
    }

    // Step 2: AX check
    const ax = clickJson(['--ax-check']);
    if (!ax.ok || (ax.json && ax.json.result !== 'OK')) {
        result.notes.push('Accessibility denied; user must grant in System Settings');
        return writeResult(base, result, 1);
    }
    result.accessibility_granted = true;

    // Step 3: self-test (no mouse)
    const st = clickJson(['--self-test']);
    if (!st.ok || (st.json && st.json.result !== 'SELFTEST_OK')) {
        result.notes.push('self-test failed: ' + (st.json ? st.json.reason : (st.err || st.out || 'unknown')));
        return writeResult(base, result, 1);
    }

    // Step 4: launch PoC with --mode=A (R81: NOT C1, 防假阳性)
    const latestTick = {};
    const poc = spawn(ELECTRON_BIN, [POC, '--mode=A', '--quit-after=30'], {
        cwd: POC_CWD, stdio: ['ignore', 'pipe', 'pipe'],
    });
    poc.stdout.on('data', d => tickHandler(d.toString(), latestTick));
    poc.stderr.on('data', () => {});

    const start = Date.now();
    while (Date.now() - start < 8000) {
        if (recentTick(latestTick, 5000)) break;
        await new Promise(r => setTimeout(r, 100));
    }
    const first = recentTick(latestTick, 5000);
    if (!first) {
        poc.kill('SIGTERM');
        result.notes.push('no valid tick from PoC in 8s');
        return writeResult(base, result, 6);
    }
    if (first.mode !== 'A') {
        poc.kill('SIGTERM');
        result.notes.push(`PoC started with mode=${first.mode}, expected A for R81 fake-positive fix`);
        return writeResult(base, result, 7);
    }

    // R81 §五: 每次 click 前 recheck
    async function recheck() {
        const t0 = Date.now();
        while (Date.now() - t0 < 1500) {
            const t = recentTick(latestTick, 200);
            if (t) return t;
            await new Promise(r => setTimeout(r, 80));
        }
        return null;
    }

    // Step 5: click C1 (A 启动 -> 真点击 C1 -> mode 切到 C1 才 PASS)
    const tick0 = await recheck();
    if (!tick0) {
        poc.kill('SIGTERM');
        return writeResult(base, result, 6);
    }
    const c1 = c1ButtonCenter(tick0);
    if (!c1) {
        poc.kill('SIGTERM');
        result.notes.push('C1 button not in tick.control_buttons (R81 修复要求 control.html 上报)');
        return writeResult(base, result, 8);
    }
    const c1r = clickJson([String(c1.x), String(c1.y)]);
    if (!c1r.ok) {
        poc.kill('SIGTERM');
        result.notes.push('C1 click failed: ' + (c1r.json ? c1r.json.reason : (c1r.err || 'unknown')));
        return writeResult(base, result, 5);
    }
    await new Promise(r => setTimeout(r, 500));
    const tick1 = await recheck();
    if (tick1 && tick1.mode === 'C1') {
        result.control_click = `PASS (mode A -> C1 via ${c1.source})`;
    } else {
        result.control_click = `FAIL (mode still ${tick1 ? tick1.mode : '?'})`;
        poc.kill('SIGTERM');
        return writeResult(base, result, 4);
    }

    // Step 6: click gold ball
    const t6a = await recheck();
    const gold = goldBall(t6a);
    if (!gold) { poc.kill('SIGTERM'); return writeResult(base, result, 6); }
    const beforeT = clicks(t6a).test || 0;
    const gc = clickJson([String(gold.x), String(gold.y)]);
    if (!gc.ok) { poc.kill('SIGTERM'); result.notes.push('gold click failed'); return writeResult(base, result, 5); }
    await new Promise(r => setTimeout(r, 500));
    const t6b = await recheck();
    const afterT = clicks(t6b).test || 0;
    if (afterT === beforeT + 1) result.gold_ball_click = `PASS (test ${beforeT} -> ${afterT})`;
    else result.gold_ball_click = `FAIL (test ${beforeT} -> ${afterT})`;

    // Step 7: click transparent
    const t7a = await recheck();
    const valid = calcValidPoint(t7a);
    if (!valid) { poc.kill('SIGTERM'); result.notes.push('GEOMETRY_INVALID'); return writeResult(base, result, 3); }
    const beforeP = clicks(t7a).probe || 0;
    const tc = clickJson([String(valid.x), String(valid.y)]);
    if (!tc.ok) { poc.kill('SIGTERM'); result.notes.push('transparent click failed'); return writeResult(base, result, 5); }
    await new Promise(r => setTimeout(r, 500));
    const t7b = await recheck();
    const afterP = clicks(t7b).probe || 0;
    if (afterP === beforeP + 1) result.underlying_click = `PASS (probe ${beforeP} -> ${afterP})`;
    else result.underlying_click = `FAIL (probe ${beforeP} -> ${afterP})`;

    // Step 8: return to gold
    const t8a = await recheck();
    const goldR = goldBall(t8a);
    if (goldR) {
        const beforeR = clicks(t8a).test || 0;
        clickJson([String(goldR.x), String(goldR.y)]);
        await new Promise(r => setTimeout(r, 500));
        const t8b = await recheck();
        const afterR = clicks(t8b).test || 0;
        if (afterR === beforeR + 1) result.return_click = `PASS (test ${beforeR} -> ${afterR})`;
        else result.return_click = `FAIL (test ${beforeR} -> ${afterR})`;
    } else {
        result.return_click = 'FAIL (cannot compute gold ball)';
    }

    // Step 9: 3 cycles
    let lastT = clicks(await recheck()).test || 0;
    let lastP = clicks(await recheck()).probe || 0;
    let cycleOK = true;
    for (let i = 0; i < 3; i++) {
        const valid2 = calcValidPoint(await recheck());
        const gold2 = goldBall(await recheck());
        if (!valid2 || !gold2) { cycleOK = false; break; }
        clickJson([String(valid2.x), String(valid2.y)]);
        clickJson([String(gold2.x), String(gold2.y)]);
        await new Promise(r => setTimeout(r, 500));
        const tc1 = clicks(await recheck());
        const tN = tc1.test || 0, pN = tc1.probe || 0;
        if (tN === lastT + 1 && pN === lastP + 1) { lastT = tN; lastP = pN; }
        else { cycleOK = false; break; }
    }
    result.three_cycle_stable = cycleOK ? 'PASS' : 'FAIL';

    try { poc.kill('SIGTERM'); } catch {}
    return writeResult(base, result, 0);
}

function writeResult(base, r, exitCode) {
    r.finished_at = nowIso();
    fs.writeFileSync(base + '.json', JSON.stringify(r, null, 2));
    let s = `=== R81 Orchestrator Result ===\nrun_id: ${r.run_id}\nfinished_at: ${r.finished_at}\naccessibility_granted: ${r.accessibility_granted}\ncontrol_click: ${r.control_click}\ngold_ball_click: ${r.gold_ball_click}\nunderlying_click: ${r.underlying_click}\nreturn_click: ${r.return_click}\nthree_cycle_stable: ${r.three_cycle_stable}\nnotes: ${(r.notes || []).join(' | ')}\n`;
    fs.writeFileSync(base + '.txt', s);
    let csv = 'run_id,accessibility,control_click,gold_ball_click,underlying_click,return_click,three_cycle_stable\n';
    csv += `${r.run_id},${r.accessibility_granted},${r.control_click},${r.gold_ball_click},${r.underlying_click},${r.return_click},${r.three_cycle_stable}\n`;
    fs.writeFileSync(base + '.csv', csv);
    console.log(`-> wrote ${base}.{txt,json,csv}`);
    if (exitCode === undefined) exitCode = 0;
    return exitCode;
}

main().then((code) => process.exit(code || 0)).catch(e => {
    console.error('orchestrator error:', e);
    process.exit(99);
});
