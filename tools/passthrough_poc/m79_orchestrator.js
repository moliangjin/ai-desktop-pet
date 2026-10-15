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

// R87: MOCK 依赖注入. 当 MOCK_CLICKER 环境变量存在时, 用其作为 clicker
// (文件路径). 当 MOCK_POC 存在时, 用其作为 PoC subprocess (但 MOCK_POC 是
// shell 脚本, spawn 时作为 argv[0]). 默认 prod 模式用真实 binary.
const MOCK_CLICKER = process.env.MOCK_CLICKER || null;
const MOCK_POC = process.env.MOCK_POC || null;

function nowIso() { return new Date().toISOString(); }
function runId() { return 'm87_' + Date.now(); }

// R86: 同步 helper. 返回 {ok, code, json, stderr, error}
// 仅在 m79 CLI exit=0 且 stdout 是合法 JSON (且 result 不是 FAIL/BLOCKED) 时 ok=true.
// R89: ENOENT 显式识别为 CLICKER_NOT_FOUND (不让 spawn ENOENT 漏进 m79 result=FAIL 路径)
async function clickJson(args) {
    return new Promise((resolve) => {
        const bin = MOCK_CLICKER || CLICKER;
        const r = spawnSync(bin, args, { encoding: 'utf-8', timeout: 5000 });
        if (r.error) {
            const isENOENT = r.error.code === 'ENOENT';
            return resolve({
                ok: false,
                code: -1,
                json: null,
                stderr: isENOENT ? 'CLICKER_NOT_FOUND' : r.error.message,
                enoent: isENOENT,
                missingPath: isENOENT ? bin : null,
            });
        }
        const code = r.status;
        if (code !== 0) {
            return resolve({ ok: false, code, json: null, stderr: (r.stderr || r.stdout || '').trim() });
        }
        let parsed = null;
        try { parsed = JSON.parse((r.stdout || '').trim() || '{}'); }
        catch { return resolve({ ok: false, code, json: null, stderr: 'json parse error' }); }
        const result = parsed.result;
        if (result !== 'OK' && result !== 'SELFTEST_OK') {
            return resolve({ ok: false, code, json: parsed, stderr: `m79 result=${result}` });
        }
        return resolve({ ok: true, code, json: parsed, stderr: '' });
    });
}

// Tick handler — 跨数据块行缓冲, 不丢半个 JSON 行
// R88: 区分 firstTick (首次收到的 mode, 不被后续覆盖) 和 latestTick (最新状态).
//      PoC 启动 mode 检测要用 firstTick.mode — 因为 fake_poc 一次性发全套 tick
//      会把 latestTick.mode 覆盖成最后那个 (e.g. C1), 但 orchestrator 期望 firstTick=A.
function makeTickAccumulator(latestTick, firstTick) {
    let buf = '';
    let seenFirst = false;
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
                    if (!seenFirst) {
                        Object.assign(firstTick, j);
                        firstTick.__updated = Date.now();
                        seenFirst = true;
                    }
                    if (process.env.MOCK_ORCH_DEBUG_LOG) {
                        try { require('fs').appendFileSync(process.env.MOCK_ORCH_DEBUG_LOG, `[tick] mode=${j.mode} test=${j.clicks?.test} probe=${j.clicks?.probe} firstTick.mode=${firstTick.mode}\n`); } catch {}
                    }
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
        if (process.env.MOCK_ORCH_DEBUG_LOG) {
            try { require('fs').appendFileSync(process.env.MOCK_ORCH_DEBUG_LOG, `[fail] step=${step} code=${code} note=${note} t=${Date.now()}\n`); } catch {}
        }
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
    const firstTick = {};  // R88: 首次收到的 tick, 不被后续 Object.assign 覆盖
    const handle = makeTickAccumulator(latestTick, firstTick);
    // R89 debug
    const orchDebugLog = process.env.MOCK_ORCH_DEBUG_LOG || null;
    const orchLog = (msg) => { if (orchDebugLog) { require('fs').appendFileSync(orchDebugLog, msg + '\n'); } };
    // R89: 检测 MOCK_POC 扩展名 — .js 用 fork() + IPC, bash 用 spawn + pipe
    const MOCK_POC_IS_JS = MOCK_POC && MOCK_POC.endsWith('.js');
    const pocArgs = MOCK_POC
        ? (MOCK_POC_IS_JS ? [] : [MOCK_POC, POC, '--mode=A', '--quit-after=30'])
        : [POC, '--mode=A', '--quit-after=30'];
    const pocBin = MOCK_POC ? MOCK_POC : ELECTRON_BIN;
    const pocCwd = MOCK_POC ? HERE : POC_CWD;
    if (MOCK_POC_IS_JS) {
        // Node fork + IPC: tick 通过 process.send 传, 不依赖 stdout pipe
        const { fork } = require('child_process');
        poc = fork(MOCK_POC, [], { cwd: pocCwd, env: process.env, silent: false });
        poc.on('message', (m) => {
            if (m && m.type === 'tick' && m.tick) {
                const j = m.tick;
                Object.assign(latestTick, j);
                latestTick.__updated = Date.now();
                if (!firstTickSeen) {
                    Object.assign(firstTick, j);
                    firstTick.__updated = Date.now();
                    firstTickSeen = true;
                }
            }
        });
        // R90: 监听 PoC 提前退出 — 必须立即识别并中止后续
        poc.on('exit', (code, sig) => {
            if (orchDebugLog) { try { require('fs').appendFileSync(orchDebugLog, `[poc exit] code=${code} sig=${sig} t=${Date.now()}\n`); } catch {} }
            if (!result.poc_early_exit) {
                result.poc_early_exit = true;
                result.notes.push(`POC_EARLY_EXIT code=${code} sig=${sig}`);
            }
        });
        // 启动 fake_poc (startupDelay 让 orchestrator 先 AX check + 拿到 firstTick 时间)
        setTimeout(() => {
            try { poc.send({ type: 'start', mode: process.env.FAKE_POC_MODE || 'success', startupDelay: 1000 }); } catch (e) {}
        }, 300);
    } else {
        poc = spawn(pocBin, pocArgs, { cwd: pocCwd, stdio: ['ignore', 'pipe', 'pipe'] });
        poc.stdout.on('data', d => {
            if (orchDebugLog) { try { require('fs').appendFileSync(orchDebugLog, '[raw stdout] ' + d.toString().split('\n').filter(Boolean).join(' | ') + '\n'); } catch {} }
            handle(d.toString());
        });
        poc.stderr.on('data', (d) => {
            if (orchDebugLog) { try { require('fs').appendFileSync(orchDebugLog, '[stderr] ' + d.toString().trim() + '\n'); } catch {} }
        });
        // R90: bash spawn 模式同样监听 exit
        poc.on('exit', (code, sig) => {
            if (orchDebugLog) { try { require('fs').appendFileSync(orchDebugLog, `[poc exit] code=${code} sig=${sig} t=${Date.now()}\n`); } catch {} }
            if (!result.poc_early_exit) {
                result.poc_early_exit = true;
                result.notes.push(`POC_EARLY_EXIT code=${code} sig=${sig}`);
            }
        });
    }
    let firstTickSeen = false;  // R89: fork 模式需要 firstTick 跟踪

    const start = Date.now();
    while (Date.now() - start < 8000) {
        if (recentTick(latestTick, 5000)) break;
        await new Promise(r => setTimeout(r, 100));
    }
    const first = recentTick(latestTick, 5000);
    if (!first) { result.notes.push('no tick in 8s'); return fail('PoC', 6, 'no tick'); }
    // R88: 检查 firstTick.mode (启动 mode), 不是 latestTick.mode (会被覆盖)
    const startMode = firstTick.mode || first.mode;
    if (startMode !== 'A') { result.notes.push(`PoC start mode=${startMode}, expected A`); return fail('PoC-start-mode', 7); }

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
    if (!gc.ok) {
        result.gold_ball_click = `FAIL (${gc.stderr})`;
        if (gc.enoent) { result.notes.push('CLICKER_NOT_FOUND: ' + gc.missingPath); return fail('CLICKER_NOT_FOUND', 12); }
        return fail('gold-click', 5);
    }
    await new Promise(r => setTimeout(r, 500));
    const t6b = await recheck();
    const afterT = clicks(t6b).test || 0;
    // R89: 严格 === beforeT+1 — 事件驱动计数保证 click→+1, 不再 MOCK_GTE 凑 PASS
    if (afterT === beforeT + 1) result.gold_ball_click = `PASS (test ${beforeT} -> ${afterT})`;
    else { result.gold_ball_click = `FAIL (test ${beforeT} -> ${afterT}, expected ${beforeT + 1})`; return fail('gold-count', 5, 'gold count mismatch'); }

    // Step 7: transparent
    const t7 = await recheck();
    const valid = calcValidPoint(t7);
    if (!valid) { result.notes.push('GEOMETRY_INVALID'); return fail('geom', 3); }
    const beforeP = clicks(t7).probe || 0;
    const tc = await clickJson([String(valid.x), String(valid.y)]);
    if (!tc.ok) {
        result.underlying_click = `FAIL (${tc.stderr})`;
        if (tc.enoent) { result.notes.push('CLICKER_NOT_FOUND: ' + tc.missingPath); return fail('CLICKER_NOT_FOUND', 12); }
        return fail('trans-click', 5);
    }
    await new Promise(r => setTimeout(r, 500));
    const t7b = await recheck();
    const afterP = clicks(t7b).probe || 0;
    if (afterP === beforeP + 1) result.underlying_click = `PASS (probe ${beforeP} -> ${afterP})`;
    else { result.underlying_click = `FAIL (probe ${beforeP} -> ${afterP}, expected ${beforeP + 1})`; return fail('probe-count', 5, 'probe count mismatch'); }

    // Step 8: return to gold
    const t8 = await recheck();
    const goldR = goldBall(t8);
    if (goldR) {
        const beforeR = clicks(t8).test || 0;
        const rc = await clickJson([String(goldR.x), String(goldR.y)]);
        if (!rc.ok) {
            result.return_click = `FAIL (${rc.stderr})`;
            if (rc.enoent) { result.notes.push('CLICKER_NOT_FOUND: ' + rc.missingPath); return fail('CLICKER_NOT_FOUND', 12); }
            return fail('return-click', 5);
        }
        await new Promise(r => setTimeout(r, 500));
        const t8b = await recheck();
        const afterR = clicks(t8b).test || 0;
        if (afterR === beforeR + 1) result.return_click = `PASS (test ${beforeR} -> ${afterR})`;
        else { result.return_click = `FAIL (test ${beforeR} -> ${afterR}, expected ${beforeR + 1})`; return fail('return-count', 5, 'return count mismatch'); }
    } else {
        result.return_click = 'FAIL (no gold)'; return fail('gold-geom', 6);
    }

    // Step 9: 3 cycles — 严格 +1
    let lastT = clicks(await recheck()).test || 0;
    let lastP = clicks(await recheck()).probe || 0;
    let cycleOK = true;
    for (let i = 0; i < 3; i++) {
        const v2 = calcValidPoint(await recheck());
        const g2 = goldBall(await recheck());
        if (!v2 || !g2) { cycleOK = false; break; }
        const tc1 = await clickJson([String(v2.x), String(v2.y)]);
        const gc1 = await clickJson([String(g2.x), String(g2.y)]);
        if (!tc1.ok || !gc1.ok) {
            cycleOK = false;
            if (tc1.enoent || gc1.enoent) { result.notes.push('CLICKER_NOT_FOUND'); return fail('CLICKER_NOT_FOUND', 12); }
            break;
        }
        // R89: 800ms 让 fake_poc emit_loop 至少跑 4 次 (200ms/次) 完全消费 signal
        await new Promise(r => setTimeout(r, 800));
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
