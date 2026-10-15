// tools/passthrough_poc/m87_fake_poc.js
//
// R89 Node.js fake PoC — 用 IPC 通信 (process.send) 而非 stdout pipe,
// 避免 bash fake_poc 的 stdout pipe / SIGTERM 时序问题.
//
// 协议:
//   - 启动: orchestrator fork() 此脚本. 收到 {type:'start'} 后开始 emit_loop
//   - 通信:
//       process.send({type:'tick', tick:{...poc-tick data...}})  // 发 tick
//       process.on('message', m => ...)  // 收 orchestrator 配置 / 停止
//   - sentinel: orchestrator click → fake_clicker 写 /tmp/m87_click_signals/click_*
//     fake_poc.js 用 setInterval(200ms) 读所有 click_* 文件, 几何判定 +1, 删文件
//
// 与 bash fake_poc.sh 等价, 但:
//   - tick 通过 IPC (process.send) 传, 不依赖 stdout pipe 缓冲
//   - setInterval 而非 sleep 循环, 更可控
//   - exit code 由 process.exit(0) 控制, 不依赖 bash set -e

const fs = require('fs');
const path = require('path');

const SIGNAL_DIR = process.env.MOCK_CLICK_SIGNAL_DIR || '/tmp/m87_click_signals';
const QUIT_AFTER_S = parseInt(process.env.QUIT_AFTER || '20', 10) * 1000;
const MODE = process.env.FAKE_POC_MODE || 'success';
const DEBUG_LOG = process.env.MOCK_POC_DEBUG_LOG || null;
const NO_MODE_SWITCH = process.env.MOCK_POC_NO_MODE_SWITCH === 'true';

if (!fs.existsSync(SIGNAL_DIR)) fs.mkdirSync(SIGNAL_DIR, { recursive: true });

const dbg = (msg) => {
    if (DEBUG_LOG) { try { fs.appendFileSync(DEBUG_LOG, msg + '\n'); } catch {} }
};

dbg(`[start] MODE=${MODE} PID=${process.pid} SIGNAL_DIR=${SIGNAL_DIR}`);

// 默认几何 (与 fake_poc.sh tick 输出对齐)
const GEOM = {
    test_window: { x: 320, y: 200, w: 256, h: 256 },
    probe_window: { x: 360, y: 320, w: 360, h: 180 },
    control_window: { x: 80, y: 80, w: 360, h: 220 },
    sprite: { cx: 448, cy: 328, r: 50 },
    probe_button: { x: 372, y: 414, w: 284, h: 36 },
    control_buttons: { a: { x: 92, y: 130, w: 60, h: 30 }, b: { x: 158, y: 130, w: 60, h: 30 }, c1: { x: 224, y: 130, w: 60, h: 30 }, c2: { x: 290, y: 130, w: 60, h: 30 } }
};

function inRect(x, y, r) { return r.x <= x && x < r.x + r.w && r.y <= y && y < r.y + r.h; }

function hitDetection(x, y) {
    const inC1 = inRect(x, y, GEOM.control_buttons.c1);
    const inCw = inRect(x, y, GEOM.control_window);
    const inTw = inRect(x, y, GEOM.test_window);
    const inPw = inRect(x, y, GEOM.probe_window);
    const inSprite = Math.hypot(x - GEOM.sprite.cx, y - GEOM.sprite.cy) < GEOM.sprite.r;
    const inPb = inRect(x, y, GEOM.probe_button);
    if (inC1 && inCw) return 'c1:hit';
    if (inTw && inSprite) return 'test:+1';
    if (inTw && inPb) return 'probe:+1';
    if (inTw) return 'test:+1';
    if (inPw) return 'probe:+1';
    return 'none';
}

function consumeSignals() {
    let hits = [];
    try {
        const files = fs.readdirSync(SIGNAL_DIR).filter(f => f.startsWith('click_'));
        for (const f of files) {
            const full = path.join(SIGNAL_DIR, f);
            try {
                const sig = JSON.parse(fs.readFileSync(full, 'utf-8'));
                fs.unlinkSync(full);
                hits.push(hitDetection(sig.x, sig.y));
                dbg(`[signal] ${f} -> ${hits[hits.length - 1]}`);
            } catch (e) { dbg(`[signal error] ${f} ${e.message}`); }
        }
    } catch (e) { dbg(`[consume error] ${e.message}`); }
    return hits;
}

function emitTick(mode, t, p, ignore, noC1) {
    const tick = {
        type: 'poc-tick',
        run_id: 'm87_fake_poc_js',
        mode: mode,
        ignore: ignore,
        test_window: GEOM.test_window,
        probe_window: GEOM.probe_window,
        control_window: GEOM.control_window,
        sprite: GEOM.sprite,
        probe_button: GEOM.probe_button,
        control_buttons: noC1
            ? { a: GEOM.control_buttons.a, b: GEOM.control_buttons.b, c2: GEOM.control_buttons.c2 }
            : GEOM.control_buttons,
        clicks: { test: t, probe: p },
        transitions: 0,
    };
    try { process.send({ type: 'tick', tick }); } catch (e) { dbg(`[send error] ${e.message}`); }
}

// 启动: orchestrator 发 {type:'start', mode:'...'}, 我们按 mode 决定行为
let started = false;

process.on('message', (m) => {
    if (!m) return;
    if (m.type === 'start') {
        started = true;
        const pocMode = m.mode || 'success';
        dbg(`[start msg] mode=${pocMode}`);
        runMode(pocMode, m);
    } else if (m.type === 'stop') {
        dbg(`[stop msg]`);
        process.exit(0);
    }
});

function runMode(pocMode, m) {
    if (pocMode === 'broken-json') {
        // R89: 不发任何 tick (raw stdout 也不行, fork 模式不走 stdout)
        // → orchestrator 8s 等 tick 超时 → exit 6 'no tick in 8s'
        const end = Date.now() + QUIT_AFTER_S;
        setTimeout(() => { dbg('[broken-json end]'); process.exit(0); }, QUIT_AFTER_S);
        return;
    }
    if (pocMode === 'no-tick') {
        // 不发任何 tick — orchestrator timeout exit 6
        setTimeout(() => { dbg('[no-tick end]'); process.exit(0); }, QUIT_AFTER_S);
        return;
    }
    if (pocMode === 'exit-early' || pocMode === 'early-exit') {
        // 发几个 tick 后立即退出 — 测 orchestrator 处理 partial
        emitTick('A', 0, 0, false, false);
        emitTick('A', 0, 0, false, false);
        setTimeout(() => process.exit(0), 1000);
        return;
    }
    if (pocMode === 'ignore-clicks') {
        // R89: 收到 click signal 消费但不 +1; c1:hit 切 C1 但不 +t/p (测 click OK 但 PoC 计数不变)
        for (let i = 0; i < 3; i++) emitTick('A', 0, 0, false, false);
        let mode = 'A';
        const end = Date.now() + QUIT_AFTER_S;
        const loop = () => {
            if (Date.now() >= end) { dbg('[ignore-clicks end]'); process.exit(0); }
            // 消费 signal 但不 +1, 但 c1:hit 切 C1
            try {
                const files = fs.readdirSync(SIGNAL_DIR).filter(f => f.startsWith('click_'));
                for (const f of files) {
                    const full = path.join(SIGNAL_DIR, f);
                    let sig = null;
                    try { sig = JSON.parse(fs.readFileSync(full, 'utf-8')); fs.unlinkSync(full); } catch { try { fs.unlinkSync(full); } catch {} }
                    if (sig && hitDetection(sig.x, sig.y) === 'c1:hit') mode = 'C1';
                }
            } catch {}
            emitTick(mode, 0, 0, true, false);
            setTimeout(loop, 200);
        };
        setTimeout(loop, 1000);
        return;
    }
    if (pocMode === 'wrong-target') {
        // R89: 收到 c1 click → 切 C1, 但其它 click → +1 到 probe (错)
        for (let i = 0; i < 3; i++) emitTick('A', 0, 0, false, false);
        let mode = 'A', t = 0, p = 0;
        const end = Date.now() + QUIT_AFTER_S;
        const loop = () => {
            if (Date.now() >= end) { dbg('[wrong-target end]'); process.exit(0); }
            try {
                const files = fs.readdirSync(SIGNAL_DIR).filter(f => f.startsWith('click_'));
                for (const f of files) {
                    const full = path.join(SIGNAL_DIR, f);
                    let sig = null;
                    try { sig = JSON.parse(fs.readFileSync(full, 'utf-8')); fs.unlinkSync(full); } catch { try { fs.unlinkSync(full); } catch {} }
                    if (sig && hitDetection(sig.x, sig.y) === 'c1:hit') {
                        mode = 'C1';
                        t += 1;
                        p += 1;
                    } else {
                        // 故意 +1 到 probe (错)
                        p += 1;
                    }
                }
            } catch {}
            emitTick(mode, t, p, true, false);
            setTimeout(loop, 200);
        };
        setTimeout(loop, 1000);
        return;
    }
    if (pocMode === 'no-c1-button') {
        // tick 省略 control_buttons.c1
        for (let i = 0; i < 3; i++) emitTick('A', 0, 0, false, true);  // noC1=true
        const end = Date.now() + QUIT_AFTER_S;
        const loop = () => {
            if (Date.now() >= end) { dbg('[no-c1-button end]'); process.exit(0); }
            const hits = consumeSignals();
            // 不切 mode 因为 c1 button 不存在
            emitTick('A', 0, 0, true, true);
            setTimeout(loop, 200);
        };
        setTimeout(loop, 1000);
        return;
    }
    if (pocMode === 'mode-a-only') {
        // 持续 A 不切 C1
        const noSwitch = true;
        for (let i = 0; i < 3; i++) emitTick('A', 0, 0, false, false);
        let mode = 'A', t = 0, p = 0;
        const end = Date.now() + QUIT_AFTER_S;
        const loop = () => {
            if (Date.now() >= end) { dbg('[mode-a-only end]'); process.exit(0); }
            const hits = consumeSignals();
            for (const hit of hits) {
                if (hit === 'test:+1') t += 1;
                else if (hit === 'probe:+1') p += 1;
                else if (hit === 'c1:hit') {
                    // mode-a-only: 收到 c1 signal 也不切 (测 orchestrator 判 FAIL)
                    t += 1; p += 1;
                }
            }
            emitTick(mode, t, p, true, false);
            setTimeout(loop, 200);
        };
        setTimeout(loop, 1000);
        return;
    }
    // success (default)
    for (let i = 0; i < 3; i++) emitTick('A', 0, 0, false, false);
    let mode = 'A', t = 0, p = 0;
    const end = Date.now() + QUIT_AFTER_S;
    const loop = () => {
        if (Date.now() >= end) { dbg('[success end]'); process.exit(0); }
        const hits = consumeSignals();
        for (const hit of hits) {
            if (hit === 'test:+1') t += 1;
            else if (hit === 'probe:+1') p += 1;
            else if (hit === 'c1:hit') {
                if (!NO_MODE_SWITCH) { mode = 'C1'; t += 1; p += 1; }
            }
        }
        emitTick(mode, t, p, true, false);
        dbg(`[tick] mode=${mode} test=${t} probe=${p} SECONDS=${Math.floor(process.uptime())}`);
        setTimeout(loop, 200);
    };
    setTimeout(loop, 1000);
}

// 兜底: orchestrator 没发 start 也跑默认 success 流程 (兼容老 spawn 用法)
setTimeout(() => {
    if (!started) {
        dbg('[auto-start]');
        runMode('success', {});
    }
}, 2000);
