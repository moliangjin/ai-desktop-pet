// R64 INDEPENDENT passthrough proof-of-concept
//
// Task book §三/§四/§五/§七:
//
//   **TRUE_PASSTHROUGH** vs **COMPACT_WINDOW** vs **FULL_WINDOW_IGNORE**
//   - TRUE_PASSTHROUGH: alpha=0 click forwards to underlying window via the
//     macOS WindowServer + Electron setIgnoreMouseEvents(true, {forward:true}).
//   - COMPACT_WINDOW: shrink BrowserWindow bounds to sprite bbox. NO
//     per-pixel forwarding inside the window rect — outside the rect is
//     simply not part of the window.
//   - FULL_WINDOW_IGNORE: setIgnoreMouseEvents(true) on the whole window
//     including the sprite. Useful as a control test (the sprite ALSO loses
//     click). NOT what we want.
//
//   The three are distinct. R62 conflated "compact window" with
//   "passthrough"; R64 fixes that by naming them separately.
//
//   Single-launch test runner (task book §五):
//     - One Electron process launches once with all windows.
//     - The top window has 3 buttons: [A] [B] [C1] (Path 1) and the
//       user clicks the gold ball + transparent corner as instructed.
//     - The buttons switch the mode at runtime without restarting the
//       process. State transitions are recorded in a per-run JSON file.
//     - Timeout: 90 s default, configurable.
//
//   Per-run file isolation (task book §五):
//     - Each run gets a unique run_id; results go to
//       /tmp/passthrough_poc_<run_id>_<mode>.{txt,json,csv}.
//     - Old run files are preserved; we do NOT overwrite them.

const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const HERE = __dirname;

const RUN_ID = `r64_${Date.now()}`;
const QUIT_AFTER = parseFloat(process.env.POC_QUIT_AFTER || process.argv
    .filter(a => a.startsWith('--quit-after='))[0]?.split('=')[1] || '90') || 90;

// Parse --mode=A|B|C1|C2 from argv (more reliable than process.env in Electron).
const _argv = process.argv.join('|');
const _modeArg = process.argv
    .filter(a => a.startsWith('--mode='))[0]?.split('=')[1]
    || process.env.POC_MODE
    || 'A';
const POC_MODE = _modeArg.toUpperCase();  // A | B | C1 | C2
const PATH_FOR_C = (POC_MODE === 'C1' || POC_MODE === 'C2')
    ? (POC_MODE === 'C1' ? '1' : '3')
    : '1';
console.log(`[R64 PoC] argv=${_argv}  env.POC_MODE=${process.env.POC_MODE || '<unset>'}  mode=${POC_MODE}`);

// --- Geometry (DIP, screen coords) ---
// Top window is 256x256 at (200, 200) for Mode A/B/C1. Mode C2 uses 100x100
// at (228, 228) so the sprite fits.
const TOP_X = 200, TOP_Y = 200, TOP_W = 256, TOP_H = 256;
const SPRITE_CX = TOP_X + 128, SPRITE_CY = TOP_Y + 128, SPRITE_R = 50;
const UNDER_X = 240, UNDER_Y = 280, UNDER_W = 360, UNDER_H = 180;

// --- State (main process) ---
let topWindow = null, underWindow = null;
let currentMode = POC_MODE;  // default to CLI/env mode; user can switch at runtime
let topClicks = 0, underClicks = 0;
let transitions = 0;
let lastIgnoreState = null;
let dragActive = false;     // toggled by IPC from renderer when sprite is being dragged
let lastTransitionLog = []; // for per-transition evidence

// Pure state machine function (testable; no Electron deps).
// Returns { target: bool, expected: 'SPRITE_HOVER'|'WIN_HOVER'|'OUTSIDE' }
//   target = true means setIgnoreMouseEvents(true, {forward:true})
//   target = false means setIgnoreMouseEvents(false)
function computeState({ cursor, winBounds, spriteBounds, dragging }) {
    if (!cursor || !winBounds) {
        return { target: false, expected: 'UNKNOWN' };
    }
    if (dragging) {
        return { target: false, expected: 'DRAG_LOCKED' };
    }
    const insideWindow =
        cursor.x >= winBounds.x && cursor.x < winBounds.x + winBounds.width &&
        cursor.y >= winBounds.y && cursor.y < winBounds.y + winBounds.height;
    if (!insideWindow) {
        return { target: false, expected: 'OUTSIDE' };
    }
    const dx = cursor.x - spriteBounds.cx;
    const dy = cursor.y - spriteBounds.cy;
    const inSprite = (dx*dx + dy*dy) < spriteBounds.r * spriteBounds.r;
    if (inSprite) return { target: false, expected: 'SPRITE_HOVER' };
    return { target: true, expected: 'WIN_HOVER_TRANSPARENT' };
}

function setMode(mode) {
    currentMode = mode;
    if (!topWindow) return;
    if (mode === 'A') {
        topWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
    } else if (mode === 'B') {
        topWindow.setIgnoreMouseEvents(true);
        lastIgnoreState = true;
    } else if (mode === 'C1') {
        topWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
        startStateMachine();
    } else if (mode === 'C2') {
        // COMPACT_WINDOW_FALLBACK: window already 100x100 (compact).
        topWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
        stopStateMachine();
    }
    // Reset counters when mode changes (per-run state, not per-process).
    topClicks = 0;
    underClicks = 0;
    transitions = 0;
    lastTransitionLog = [];
    // Inform renderer so the UI can reflect the new mode.
    topWindow.webContents.send('mode-changed', { mode, ignore: lastIgnoreState });
    console.log(`[R64 PoC] mode=${mode}  setIgnore=${lastIgnoreState}`);
}

// --- State machine (Path 1) ---
let pollHandle = null;
function startStateMachine() {
    if (pollHandle) return;
    pollHandle = setInterval(() => {
        if (!topWindow || topWindow.isDestroyed()) return;
        if (currentMode !== 'C1') return;
        const cursor = screen.getCursorScreenPoint();
        const wb = topWindow.getBounds();
        const state = computeState({
            cursor, winBounds: wb,
            spriteBounds: { cx: SPRITE_CX, cy: SPRITE_CY, r: SPRITE_R },
            dragging: dragActive,
        });
        if (state.target === lastIgnoreState) return;
        try {
            topWindow.setIgnoreMouseEvents(state.target, state.target ? { forward: true } : undefined);
        } catch (e) {
            console.log(`[R64 PoC] setIgnore error: ${e && e.message}`);
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
            actual: state.target,
        };
        lastTransitionLog.push(entry);
        console.log(`[R64 PoC] transition #${transitions}: cursor=(${entry.cursor.x},${entry.cursor.y}) expected=${state.expected} actual=${state.target}`);
    }, 50);  // 20Hz
}
function stopStateMachine() {
    if (pollHandle) {
        clearInterval(pollHandle);
        pollHandle = null;
    }
}

// --- Windows ---
function createTopWindow() {
    // Mode-dependent bounds; we start at the full 256x256 and let the user
    // switch via the on-screen buttons.
    let geom = { x: TOP_X, y: TOP_Y, width: TOP_W, height: TOP_H };
    if (currentMode === 'C2') {
        // COMPACT_WINDOW_FALLBACK: 100x100 centered on sprite.
        geom = { x: SPRITE_CX - SPRITE_R, y: SPRITE_CY - SPRITE_R, width: SPRITE_R * 2, height: SPRITE_R * 2 };
    }
    const top = new BrowserWindow({
        x: geom.x, y: geom.y,
        width: geom.width, height: geom.height,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        hasShadow: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        resizable: false,
        webPreferences: { nodeIntegration: true, contextIsolation: false },
    });
    top.setOpacity(0.999);
    top.loadFile(path.join(HERE, 'index.html'));
    top.webContents.on('console-message', (...args) => {
        const ev = args[0];
        const msg = (ev && ev.message) || args[2] || '';
        console.log(`[top] ${msg}`);
    });
    ipcMain.on('top-click', (_e, info) => {
        topClicks++;
        console.log(`[R64 PoC] TOP click #${topClicks} at (${info.x},${info.y}) where=${info.where} mode=${currentMode}`);
    });
    ipcMain.on('set-mode', (_e, m) => setMode(m));
    ipcMain.on('drag-state', (_e, d) => {
        dragActive = !!d;
        console.log(`[R64 PoC] drag-state=${dragActive} (renderer reports)`);
    });
    return top;
}

function createUnderWindow() {
    const under = new BrowserWindow({
        x: UNDER_X, y: UNDER_Y,
        width: UNDER_W, height: UNDER_H,
        frame: true,
        transparent: false,
        alwaysOnTop: false,
        title: `UNDERLAY (run_id=${RUN_ID}) — click under top window`,
        webPreferences: { nodeIntegration: true },
    });
    under.loadFile(path.join(HERE, 'probe.html'));
    under.webContents.on('console-message', (...args) => {
        const ev = args[0];
        const msg = (ev && ev.message) || args[2] || '';
        console.log(`[under] ${msg}`);
    });
    ipcMain.on('under-click', (_e, info) => {
        underClicks++;
        console.log(`[R64 PoC] UNDER click #${underClicks} at (${info.x},${info.y}) mode=${currentMode}`);
    });
    return under;
}

// --- Geometry & result ---
function checkGeometry() {
    const tb = topWindow.getBounds();
    const ub = underWindow.getBounds();
    const overlap = !(
        tb.x + tb.width  < ub.x || tb.x > ub.x + ub.width ||
        tb.y + tb.height < ub.y || tb.y > ub.y + ub.height
    );
    return { tb, ub, overlap };
}

function writeResultPerMode(mode) {
    const geo = checkGeometry();
    const result = {
        run_id: RUN_ID,
        mode,
        recorded_at: new Date().toISOString(),
        top_window: geo.tb,
        under_window: geo.ub,
        geometry_overlap: geo.overlap,
        counts: { top_clicks: topClicks, under_clicks: underClicks, state_transitions: transitions },
        transition_log: lastTransitionLog,
        verdict: computeVerdict(mode),
    };
    const base = `/tmp/passthrough_poc_${RUN_ID}_${mode}`;
    const txt = [
        `=== R64 Passthrough PoC Result ===`,
        `run_id:        ${RUN_ID}`,
        `mode:          ${mode}`,
        `recorded_at:   ${result.recorded_at}`,
        `top_window:    ${JSON.stringify(geo.tb)}`,
        `under_window:  ${JSON.stringify(geo.ub)}`,
        `overlap:       ${geo.overlap}`,
        `top_clicks:    ${topClicks}`,
        `under_clicks:  ${underClicks}`,
        `transitions:   ${transitions}`,
        `transition_log: ${JSON.stringify(lastTransitionLog)}`,
        `verdict:       ${result.verdict}`,
    ];
    fs.writeFileSync(`${base}.txt`, txt.join('\n') + '\n');
    fs.writeFileSync(`${base}.json`, JSON.stringify(result, null, 2));
    fs.writeFileSync(`${base}.csv`,
        'run_id,mode,recorded_at,top_x,top_y,top_w,top_h,under_x,under_y,under_w,under_h,overlap,top_clicks,under_clicks,transitions,verdict\n' +
        [
            RUN_ID, mode, result.recorded_at,
            geo.tb.x, geo.tb.y, geo.tb.width, geo.tb.height,
            geo.ub.x, geo.ub.y, geo.ub.width, geo.ub.height,
            geo.overlap ? 1 : 0,
            topClicks, underClicks, transitions,
            `"${result.verdict}"`,
        ].join(',') + '\n');
    console.log(`[R64 PoC] wrote ${base}.{txt,json,csv}`);
    return base;
}

function computeVerdict(mode) {
    if (mode === 'A') {
        return topClicks >= 1 && underClicks === 0
            ? 'AUTO_PASS_A (top only)'
            : `NEED_MORE_CLICKS (top=${topClicks} under=${underClicks})`;
    }
    if (mode === 'B') {
        return topClicks === 0 && underClicks >= 1
            ? 'AUTO_PASS_B (under only)'
            : `NEED_MORE_CLICKS (top=${topClicks} under=${underClicks})`;
    }
    if (mode === 'C1') {
        return transitions >= 1 && topClicks >= 1 && underClicks >= 1
            ? 'GUI_VERIFICATION_REQUIRED (state machine fired but cross-window click needs real mouse on Mac mini)'
            : `NEED_MORE_CLICKS (transitions=${transitions} top=${topClicks} under=${underClicks})`;
    }
    if (mode === 'C2') {
        return 'COMPACT_WINDOW_FALLBACK — see R64 §七; not a per-pixel passthrough';
    }
    return 'UNKNOWN';
}

// --- App lifecycle ---
let quitTimer = null;
app.whenReady().then(() => {
    console.log(`[R64 PoC] run_id=${RUN_ID} quit-after=${QUIT_AFTER}s`);
    underWindow = createUnderWindow();
    topWindow = createTopWindow();
    // Don't gate on did-finish-load (it can be slow in mavis shell).
    setMode(currentMode);
    const geo = checkGeometry();
    console.log(`[R64 PoC] top   bounds: ${JSON.stringify(geo.tb)}`);
    console.log(`[R64 PoC] under bounds: ${JSON.stringify(geo.ub)}`);
    console.log(`[R64 PoC] overlap: ${geo.overlap}`);
    console.log('[R64 PoC] READY — user clicks [A][B][C1][C2] in top window to switch mode');
    console.log('[R64 PoC] 1. Click the gold ball (sprite area)');
    console.log('[R64 PoC] 2. Click on transparent corner (outside sprite, inside top window)');
    console.log('[R64 PoC] 3. Read the under window counter for forwarding evidence');
    quitTimer = setTimeout(() => {
        console.log('[R64 PoC] timeout, quitting');
        try { writeResultPerMode(currentMode); } catch (e) {}
        app.quit();
    }, QUIT_AFTER * 1000);
});

app.on('window-all-closed', () => {
    try { writeResultPerMode(currentMode); } catch (e) {}
    app.quit();
});
app.on('before-quit', () => {
    try { writeResultPerMode(currentMode); } catch (e) {}
});

// ---- Self-test (run without GUI to verify state machine math) ----
function selfTest() {
    const win = { x: 200, y: 200, width: 256, height: 256 };
    const sb = { cx: 328, cy: 328, r: 50 };
    const cases = [
        // [name, cursor, dragging, expected, target]
        ['OUTSIDE', { x: 0, y: 0 }, false, 'OUTSIDE', false],
        ['WIN_HOVER_CORNER', { x: 220, y: 220 }, false, 'WIN_HOVER_TRANSPARENT', true],
        ['SPRITE_CENTER', { x: 328, y: 328 }, false, 'SPRITE_HOVER', false],
        // Strict < means a point exactly on the radius (dx*dx == r*r) is OUTSIDE.
        ['SPRITE_INSIDE_NEAR_EDGE', { x: 377, y: 328 }, false, 'SPRITE_HOVER', false],  // dx=49, inside
        ['SPRITE_OUTSIDE_EDGE', { x: 379, y: 328 }, false, 'WIN_HOVER_TRANSPARENT', true],  // dx=51
        ['DRAG_LOCK', { x: 328, y: 328 }, true, 'DRAG_LOCKED', false],
    ];
    let pass = 0, fail = 0;
    for (const [name, cur, dr, exp, tgt] of cases) {
        const s = computeState({ cursor: cur, winBounds: win, spriteBounds: sb, dragging: dr });
        if (s.expected === exp && s.target === tgt) { pass++; }
        else { fail++; console.log(`  FAIL ${name}: expected ${exp}/${tgt} got ${s.expected}/${s.target}`); }
    }
    console.log(`[R64 PoC] self-test: ${pass} pass, ${fail} fail`);
    return fail === 0;
}

if (process.env.POC_SELFTEST === '1') {
    // Skip Electron entirely; just run the math.
    const ok = selfTest();
    process.exit(ok ? 0 : 1);
}
