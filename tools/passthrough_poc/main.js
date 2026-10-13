// R67 INDEPENDENT passthrough proof-of-concept
//
// Task book §三 / §六:
//   THREE INDEPENDENT WINDOWS — control panel NEVER enters ignore state.
//
//   Window 1 (control panel): frame=true, non-transparent, regular z-order.
//     Has [A] [B] [C1] [C2] buttons + status line + counters. NEVER calls
//     setIgnoreMouseEvents(true). Always clickable. Not covered by the
//     transparent test window.
//
//   Window 2 (transparent test): frame=false, transparent=true, alwaysOnTop.
//     Contains the gold ball + 3 distinguishable test regions.
//     R67 Mode C1 / C2 toggle its setIgnoreMouseEvents from the control
//     panel via IPC.
//
//   Window 3 (underlay probe): frame=true, non-transparent, regular z-order.
//     Contains a single clickable button + click counter. Sits BELOW
//     window 2 spatially.
//
// R67 GUI automation hook: this PoC supports a deterministic self-test
// via `r67_automated_test` IPC channel that runs three clicks using
// osascript/AppleScript to inject REAL system mouse events. See
// tools/passthrough_poc/r67_mac_automation_test.sh.

const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const HERE = __dirname;

const RUN_ID = `r67_${Date.now()}`;
const QUIT_AFTER = parseFloat(process.env.POC_QUIT_AFTER || process.argv
    .filter(a => a.startsWith('--quit-after='))[0]?.split('=')[1] || '120') || 120;
const _modeArg = process.argv
    .filter(a => a.startsWith('--mode='))[0]?.split('=')[1]
    || process.env.POC_MODE
    || 'A';
const DEFAULT_MODE = _modeArg.toUpperCase();  // initial mode

// State.
let controlWindow = null;
let testWindow = null;
let probeWindow = null;
let currentMode = DEFAULT_MODE;
let topClicks = 0, underClicks = 0;
let transitions = 0;
let lastIgnoreState = false;
let dragActive = false;
let lastTransitionLog = [];

// Geometry (DIP, screen coords).
const TEST_X = 320, TEST_Y = 200, TEST_W = 256, TEST_H = 256;
const SPRITE_CX = TEST_X + 128, SPRITE_CY = TEST_Y + 128, SPRITE_R = 50;
const PROBE_X = 360, PROBE_Y = 320, PROBE_W = 360, PROBE_H = 180;
const CONTROL_X = 80, CONTROL_Y = 80, CONTROL_W = 360, CONTROL_H = 110;

// Pure state machine function (testable; no Electron deps).
function computeState({ cursor, winBounds, spriteBounds, dragging }) {
    if (!cursor || !winBounds) return { target: false, expected: 'UNKNOWN' };
    if (dragging) return { target: false, expected: 'DRAG_LOCKED' };
    const insideWindow =
        cursor.x >= winBounds.x && cursor.x < winBounds.x + winBounds.width &&
        cursor.y >= winBounds.y && cursor.y < winBounds.y + winBounds.height;
    if (!insideWindow) return { target: false, expected: 'OUTSIDE' };
    const dx = cursor.x - spriteBounds.cx;
    const dy = cursor.y - spriteBounds.cy;
    const inSprite = (dx*dx + dy*dy) < spriteBounds.r * spriteBounds.r;
    if (inSprite) return { target: false, expected: 'SPRITE_HOVER' };
    return { target: true, expected: 'WIN_HOVER_TRANSPARENT' };
}

function setMode(mode) {
    currentMode = mode;
    if (!testWindow) return;
    if (mode === 'A') {
        testWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
    } else if (mode === 'B') {
        testWindow.setIgnoreMouseEvents(true);
        lastIgnoreState = true;
    } else if (mode === 'C1') {
        testWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
        startStateMachine();
    } else if (mode === 'C2') {
        // COMPACT_WINDOW_FALLBACK: shrink test window to sprite bbox
        const compact = {
            x: SPRITE_CX - SPRITE_R,
            y: SPRITE_CY - SPRITE_R,
            width: SPRITE_R * 2,
            height: SPRITE_R * 2,
        };
        testWindow.setBounds(compact);
        testWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
        stopStateMachine();
    } else if (mode === 'C1' || mode === 'C2') {
        // (already handled)
    } else {
        // restore
        testWindow.setBounds({ x: TEST_X, y: TEST_Y, width: TEST_W, height: TEST_H });
        testWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
        stopStateMachine();
    }
    // Reset per-mode click counters.
    topClicks = 0;
    underClicks = 0;
    transitions = 0;
    lastTransitionLog = [];
    controlWindow.webContents.send('mode-changed', { mode, ignore: lastIgnoreState });
    console.log(`[R67 PoC] mode=${mode}  testWindow.ignore=${lastIgnoreState}`);
}

// Path 1 state machine.
let pollHandle = null;
function startStateMachine() {
    if (pollHandle) return;
    pollHandle = setInterval(() => {
        if (!testWindow || testWindow.isDestroyed()) return;
        if (currentMode !== 'C1') return;
        const cursor = screen.getCursorScreenPoint();
        const wb = testWindow.getBounds();
        const state = computeState({
            cursor, winBounds: wb,
            spriteBounds: { cx: SPRITE_CX, cy: SPRITE_CY, r: SPRITE_R },
            dragging: dragActive,
        });
        if (state.target === lastIgnoreState) return;
        try {
            testWindow.setIgnoreMouseEvents(state.target, state.target ? { forward: true } : undefined);
        } catch (e) {
            console.log(`[R67 PoC] setIgnore error: ${e && e.message}`);
            return;
        }
        lastIgnoreState = state.target;
        transitions++;
        const entry = {
            n: transitions,
            t: Date.now(),
            cursor: { x: Math.round(cursor.x), y: Math.round(cursor.y) },
            target: state.target,
            expected: state.expected,
        };
        lastTransitionLog.push(entry);
        console.log(`[R67 PoC] transition #${transitions}: cursor=(${entry.cursor.x},${entry.cursor.y}) expected=${state.expected} actual=${state.target}`);
    }, 50);
}
function stopStateMachine() {
    if (pollHandle) {
        clearInterval(pollHandle);
        pollHandle = null;
    }
}

// --- Three windows ---
function createControlWindow() {
    controlWindow = new BrowserWindow({
        x: CONTROL_X, y: CONTROL_Y,
        width: CONTROL_W, height: CONTROL_H,
        frame: true,
        transparent: false,
        alwaysOnTop: false,
        skipTaskbar: false,
        title: `R67 Control Panel (run_id=${RUN_ID})`,
        webPreferences: { nodeIntegration: true, contextIsolation: false },
    });
    controlWindow.setOpacity(1.0);  // opaque
    // CRITICAL: control window never gets setIgnoreMouseEvents(true)
    controlWindow.loadFile(path.join(HERE, 'control.html'));
    controlWindow.webContents.on('console-message', (...args) => {
        const ev = args[0];
        const msg = (ev && ev.message) || args[2] || '';
        console.log(`[control] ${msg}`);
    });
    return controlWindow;
}

function createTestWindow() {
    testWindow = new BrowserWindow({
        x: TEST_X, y: TEST_Y,
        width: TEST_W, height: TEST_H,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        hasShadow: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        resizable: false,
        webPreferences: { nodeIntegration: true, contextIsolation: false },
    });
    testWindow.setOpacity(0.999);
    testWindow.loadFile(path.join(HERE, 'test.html'));
    testWindow.webContents.on('console-message', (...args) => {
        const ev = args[0];
        const msg = (ev && ev.message) || args[2] || '';
        console.log(`[test] ${msg}`);
    });
    return testWindow;
}

function createProbeWindow() {
    probeWindow = new BrowserWindow({
        x: PROBE_X, y: PROBE_Y,
        width: PROBE_W, height: PROBE_H,
        frame: true,
        transparent: false,
        alwaysOnTop: false,
        skipTaskbar: false,
        title: `R67 Underlay Probe (run_id=${RUN_ID})`,
        webPreferences: { nodeIntegration: true, contextIsolation: false },
    });
    probeWindow.loadFile(path.join(HERE, 'probe.html'));
    probeWindow.webContents.on('console-message', (...args) => {
        const ev = args[0];
        const msg = (ev && ev.message) || args[2] || '';
        console.log(`[probe] ${msg}`);
    });
    return probeWindow;
}

// --- IPC handlers ---
ipcMain.on('set-mode', (_e, m) => {
    console.log(`[R67 PoC] set-mode IPC: ${m}`);
    setMode(m);
});
ipcMain.on('top-click', (_e, info) => {
    topClicks++;
    console.log(`[R67 PoC] TEST click #${topClicks} at (${info.x},${info.y}) where=${info.where} mode=${currentMode}`);
});
ipcMain.on('under-click', (_e, info) => {
    underClicks++;
    console.log(`[R67 PoC] PROBE click #${underClicks} at (${info.x},${info.y}) mode=${currentMode}`);
});
ipcMain.on('drag-state', (_e, d) => {
    dragActive = !!d;
});
ipcMain.on('r67_get_state', (e) => {
    e.sender.send('r67_state', {
        run_id: RUN_ID,
        mode: currentMode,
        test_window: testWindow ? testWindow.getBounds() : null,
        probe_window: probeWindow ? probeWindow.getBounds() : null,
        control_window: controlWindow ? controlWindow.getBounds() : null,
        ignore: lastIgnoreState,
        top_clicks: topClicks,
        under_clicks: underClicks,
        transitions,
        transition_log: lastTransitionLog,
    });
});

// --- Result + lifecycle ---
function checkGeometry() {
    const tb = testWindow.getBounds();
    const ub = probeWindow.getBounds();
    const cb = controlWindow.getBounds();
    const overlap = !(
        tb.x + tb.width  < ub.x || tb.x > ub.x + ub.width ||
        tb.y + tb.height < ub.y || tb.y > ub.y + ub.height
    );
    return { tb, ub, cb, overlap };
}

function writeResult() {
    if (!testWindow || !probeWindow || !controlWindow) return;
    const geo = checkGeometry();
    const result = {
        run_id: RUN_ID,
        mode: currentMode,
        recorded_at: new Date().toISOString(),
        test_window: geo.tb,
        probe_window: geo.ub,
        control_window: geo.cb,
        geometry_overlap: geo.overlap,
        counts: { top_clicks: topClicks, under_clicks: underClicks, state_transitions: transitions },
        transition_log: lastTransitionLog,
    };
    const base = `/tmp/passthrough_poc_${RUN_ID}_${currentMode}`;
    const txt = [
        '=== R67 Passthrough PoC Result ===',
        `run_id:        ${RUN_ID}`,
        `mode:          ${currentMode}`,
        `recorded_at:   ${result.recorded_at}`,
        `test_window:   ${JSON.stringify(geo.tb)}`,
        `probe_window:  ${JSON.stringify(geo.ub)}`,
        `control_window:${JSON.stringify(geo.cb)}`,
        `overlap:       ${geo.overlap}`,
        `top_clicks:    ${topClicks}`,
        `under_clicks:  ${underClicks}`,
        `transitions:   ${transitions}`,
        `transition_log: ${JSON.stringify(lastTransitionLog)}`,
    ];
    fs.writeFileSync(`${base}.txt`, txt.join('\n') + '\n');
    fs.writeFileSync(`${base}.json`, JSON.stringify(result, null, 2));
    fs.writeFileSync(`${base}.csv`,
        'run_id,mode,recorded_at,test_x,test_y,test_w,test_h,probe_x,probe_y,probe_w,probe_h,overlap,top_clicks,under_clicks,transitions\n' +
        [
            RUN_ID, currentMode, result.recorded_at,
            geo.tb.x, geo.tb.y, geo.tb.width, geo.tb.height,
            geo.ub.x, geo.ub.y, geo.ub.width, geo.ub.height,
            geo.overlap ? 1 : 0,
            topClicks, underClicks, transitions,
        ].join(',') + '\n');
    console.log(`[R67 PoC] wrote ${base}.{txt,json,csv}`);
}

let quitTimer = null;
// R71: stdout tick — every 200ms, emit a single-line JSON to stdout with
// current bounds + click counters + mode. This lets the external Swift
// test runner (r69_gui_test_runner.swift) read these values in real-time
// without IPC.
// R71: probe button screen rect reported by probe.html via IPC.
let probeButtonScreen = null;
let probeButtonIpCount = 0;
ipcMain.on('probe-button-rect', (_e, b) => {
    probeButtonScreen = b;
    probeButtonIpCount++;
    console.log(`[R67 PoC] probe button screen rect: ${JSON.stringify(b)} (ip #${probeButtonIpCount})`);
});
ipcMain.on('probe-ready', () => { console.log('[R67 PoC] probe ready'); });

let stdoutTickHandle = null;
function emitStdoutTick() {
    if (!testWindow || testWindow.isDestroyed()) return;
    try {
        const tb = testWindow.getBounds();
        const ub = probeWindow.getBounds();
        const cb = controlWindow.getBounds();
        const tick = {
            type: 'poc-tick',
            run_id: RUN_ID,
            mode: currentMode,
            ignore: lastIgnoreState,
            test_window: { x: Math.round(tb.x), y: Math.round(tb.y), w: Math.round(tb.width), h: Math.round(tb.height) },
            probe_window: { x: Math.round(ub.x), y: Math.round(ub.y), w: Math.round(ub.width), h: Math.round(ub.height) },
            control_window: { x: Math.round(cb.x), y: Math.round(cb.y), w: Math.round(cb.width), h: Math.round(cb.height) },
            sprite: { cx: SPRITE_CX, cy: SPRITE_CY, r: SPRITE_R },
            probe_button: probeButtonScreen,
            clicks: { test: topClicks, probe: underClicks },
            transitions,
        };
        process.stdout.write(JSON.stringify(tick) + '\n');
    } catch (e) {
        // ignore
    }
}

app.whenReady().then(() => {
    console.log(`[R67 PoC] run_id=${RUN_ID} quit-after=${QUIT_AFTER}s`);
    createControlWindow();
    createTestWindow();
    createProbeWindow();
    setTimeout(() => {
        setMode(DEFAULT_MODE);
        const geo = checkGeometry();
        console.log(`[R67 PoC] control bounds: ${JSON.stringify(geo.cb)}`);
        console.log(`[R67 PoC] test    bounds: ${JSON.stringify(geo.tb)}`);
        console.log(`[R67 PoC] probe   bounds: ${JSON.stringify(geo.ub)}`);
        console.log(`[R67 PoC] test/probe overlap: ${geo.overlap}`);
        console.log('[R67 PoC] READY — three windows: control (always clickable), test (transparent), probe (underlay)');
        // R71: emit real-time state tick every 200 ms (so Swift runner reads live)
        stdoutTickHandle = setInterval(emitStdoutTick, 200);
        quitTimer = setTimeout(() => {
            console.log('[R67 PoC] timeout, quitting');
            if (stdoutTickHandle) clearInterval(stdoutTickHandle);
            try { writeResult(); } catch (e) {}
            app.quit();
        }, QUIT_AFTER * 1000);
    }, 1500);
});

app.on('window-all-closed', () => {
    if (stdoutTickHandle) clearInterval(stdoutTickHandle);
    try { writeResult(); } catch (e) {}
    app.quit();
});
app.on('before-quit', () => {
    if (stdoutTickHandle) clearInterval(stdoutTickHandle);
    try { writeResult(); } catch (e) {}
});

// --- Self-test (state machine math only) ---
function selfTest() {
    const win = { x: TEST_X, y: TEST_Y, width: TEST_W, height: TEST_H };
    const sb = { cx: SPRITE_CX, cy: SPRITE_CY, r: SPRITE_R };
    const cases = [
        ['OUTSIDE', { x: 0, y: 0 }, false, 'OUTSIDE', false],
        ['WIN_HOVER_CORNER', { x: TEST_X + 20, y: TEST_Y + 20 }, false, 'WIN_HOVER_TRANSPARENT', true],
        ['SPRITE_CENTER', { x: SPRITE_CX, y: SPRITE_CY }, false, 'SPRITE_HOVER', false],
        ['SPRITE_INSIDE_NEAR_EDGE', { x: SPRITE_CX + 49, y: SPRITE_CY }, false, 'SPRITE_HOVER', false],
        ['SPRITE_OUTSIDE_EDGE', { x: SPRITE_CX + 51, y: SPRITE_CY }, false, 'WIN_HOVER_TRANSPARENT', true],
        ['DRAG_LOCK', { x: SPRITE_CX, y: SPRITE_CY }, true, 'DRAG_LOCKED', false],
    ];
    let pass = 0, fail = 0;
    for (const [name, cur, dr, exp, tgt] of cases) {
        const s = computeState({ cursor: cur, winBounds: win, spriteBounds: sb, dragging: dr });
        if (s.expected === exp && s.target === tgt) pass++;
        else { fail++; console.log(`  FAIL ${name}: expected ${exp}/${tgt} got ${s.expected}/${s.target}`); }
    }
    console.log(`[R67 PoC] self-test: ${pass} pass, ${fail} fail`);
    return fail === 0;
}

if (process.env.POC_SELFTEST === '1') {
    const ok = selfTest();
    process.exit(ok ? 0 : 1);
}
