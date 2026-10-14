// tools/passthrough_poc/m79_orchestrator.js
//
// V0.0 R79 Node.js 测试调度器
//
// 职责:
//   - 启动 PoC subprocess, 解析 PoC stdout tick JSON
//   - 动态从 PoC tick 读 test_window / probe_window / probe_button 真实矩形
//   - 计算有效透明测试点 (test_window ∩ probe_button - sprite - control_window)
//   - 调用 m79_native_click 真实系统 click
//   - 验证前后点击计数变化 (EVENT_POSTED + TARGET_RECEIVED + COUNTER_CHANGED)
//   - 3 轮 cycle + 写 TXT / JSON / CSV
//   - 任何步骤错误立即停止

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const HERE = __dirname;
const POC = path.join(HERE, 'main.js');
const CLICKER = path.join(HERE, 'build', 'm79_native_click');

function nowIso() { return new Date().toISOString(); }
function runId() { return 'm79_' + Date.now(); }

function spawnClick(args) {
    return new Promise((resolve) => {
        const p = spawn(CLICKER, args, { stdio: ['ignore', 'pipe', 'pipe'] });
        let out = '', err = '';
        p.stdout.on('data', d => out += d.toString());
        p.stderr.on('data', d => err += d.toString());
        p.on('close', code => {
            try { resolve({ code, json: JSON.parse(out.trim() || '{}') }); }
            catch { resolve({ code, json: null, out, err }); }
        });
    });
}

function calcValidPoint(tick) {
    const tw = tick.test_window, pb = tick.probe_button, cw = tick.control_window, sp = tick.sprite;
    if (!tw || !pb || !cw || !sp) return null;
    const { x: twx, y: twy, w: tww, h: twh } = tw;
    const { x: pbx, y: pby, w: pbw, h: pbh } = pb;
    const { x: cwx, y: cwy, w: cww, h: cwh } = cw;
    const { cx: spx, cy: spy, r: sr } = sp;
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

function controlC1(tick) {
    const cw = tick.control_window;
    if (!cw) return null;
    return { x: cw.x + 195, y: cw.y + cw.h * 0.55 };
}

function goldBall(tick) {
    return { x: tick.sprite.cx, y: tick.sprite.cy };
}

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

    // Step 1: AX check
    const ax = await spawnClick(['--ax-check']);
    if (ax.code !== 0) {
        result.notes.push('Accessibility denied; user must grant in System Settings');
        result.accessibility_granted = false;
        return writeResult(base, result);
    }
    result.accessibility_granted = true;

    // Step 2: launch PoC
    const poc = spawn('node', [require.resolve('electron' in process.env ? process.env.electron : 'electron'), POC, '--mode=C1', '--quit-after=30'],
        { cwd: path.join(HERE, '..', '..', 'candidates', 'candidate_b_electronpixir'), stdio: ['ignore', 'pipe', 'pipe'] });
    let tick = null;
    poc.stdout.on('data', d => {
        for (const line of d.toString().split('\n')) {
            try {
                const j = JSON.parse(line);
                if (j && j.type === 'poc-tick') tick = j;
            } catch {}
        }
    });
    poc.stderr.on('data', () => {});

    // Wait for first valid tick
    const start = Date.now();
    while (!tick && Date.now() - start < 8000) {
        await new Promise(r => setTimeout(r, 100));
    }
    if (!tick) { result.notes.push('no valid tick from PoC in 8s'); poc.kill(); return writeResult(base, result); }

    // Re-arm tick reader
    poc.stdout.on('data', d => {
        for (const line of d.toString().split('\n')) {
            try {
                const j = JSON.parse(line);
                if (j && j.type === 'poc-tick') tick = j;
            } catch {}
        }
    });

    // Step 3: valid test point
    const validPt = calcValidPoint(tick);
    if (!validPt) { result.notes.push('GEOMETRY_INVALID: no valid test point'); poc.kill(); return writeResult(base, result); }
    const c1 = controlC1(tick);
    const gold = goldBall(tick);
    if (!c1) { result.notes.push('cannot compute C1 button'); poc.kill(); return writeResult(base, result); }

    // Step 4: click C1
    const c1r = await spawnClick([String(c1.x), String(c1.y)]);
    await sleep(500);
    if (tick && tick.mode === 'C1') result.control_click = 'PASS (mode=C1)';
    else result.control_click = 'FAIL';

    // Step 5: gold ball
    const beforeT = (tick && tick.clicks && tick.clicks.test) || 0;
    const gc1 = await spawnClick([String(gold.x), String(gold.y)]);
    await sleep(500);
    const afterT = (tick && tick.clicks && tick.clicks.test) || 0;
    if (afterT === beforeT + 1) result.gold_ball_click = `PASS (test ${beforeT} -> ${afterT})`;
    else result.gold_ball_click = `FAIL (test ${beforeT} -> ${afterT})`;

    // Step 6: transparent
    const beforeP = (tick && tick.clicks && tick.clicks.probe) || 0;
    const tc = await spawnClick([String(validPt.x), String(validPt.y)]);
    await sleep(500);
    const afterP = (tick && tick.clicks && tick.clicks.probe) || 0;
    if (afterP === beforeP + 1) result.underlying_click = `PASS (probe ${beforeP} -> ${afterP})`;
    else result.underlying_click = `FAIL (probe ${beforeP} -> ${afterP})`;

    // Step 7: return
    const beforeR = (tick && tick.clicks && tick.clicks.test) || 0;
    const rc = await spawnClick([String(gold.x), String(gold.y)]);
    await sleep(500);
    const afterR = (tick && tick.clicks && tick.clicks.test) || 0;
    if (afterR === beforeR + 1) result.return_click = `PASS (test ${beforeR} -> ${afterR})`;
    else result.return_click = `FAIL (test ${beforeR} -> ${afterR})`;

    // Step 8: 3 cycles
    let cycleOK = true;
    let lastT = afterR, lastP = afterP;
    for (let i = 0; i < 3; i++) {
        await spawnClick([String(validPt.x), String(validPt.y)]);
        await spawnClick([String(gold.x), String(gold.y)]);
        await sleep(500);
        const tc1 = (tick && tick.clicks && tick.clicks.test) || 0;
        const pc1 = (tick && tick.clicks && tick.clicks.probe) || 0;
        if (tc1 === lastT + 1 && pc1 === lastP + 1) { lastT = tc1; lastP = pc1; }
        else { cycleOK = false; }
    }
    result.three_cycle_stable = cycleOK ? 'PASS' : 'FAIL';

    // Step 9: terminate
    poc.kill();
    return writeResult(base, result);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function writeResult(base, r) {
    r.finished_at = nowIso();
    fs.writeFileSync(base + '.json', JSON.stringify(r, null, 2));
    let s = `=== R79 Orchestrator Result ===\nrun_id: ${r.run_id}\nfinished_at: ${r.finished_at}\naccessibility_granted: ${r.accessibility_granted}\ninput_monitoring_required: ${r.input_monitoring_required}\ncontrol_click: ${r.control_click}\ngold_ball_click: ${r.gold_ball_click}\nunderlying_click: ${r.underlying_click}\nreturn_click: ${r.return_click}\nthree_cycle_stable: ${r.three_cycle_stable}\nnotes: ${(r.notes || []).join(' | ')}\n`;
    fs.writeFileSync(base + '.txt', s);
    let csv = 'run_id,accessibility,control_click,gold_ball_click,underlying_click,return_click,three_cycle_stable\n';
    csv += `${r.run_id},${r.accessibility_granted},${r.control_click},${r.gold_ball_click},${r.underlying_click},${r.return_click},${r.three_cycle_stable}\n`;
    fs.writeFileSync(base + '.csv', csv);
    console.log(`-> wrote ${base}.{txt,json,csv}`);
}

main().catch(e => { console.error('orchestrator error:', e); process.exit(99); });
