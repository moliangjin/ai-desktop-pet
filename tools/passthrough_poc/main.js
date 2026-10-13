// R62 INDEPENDENT passthrough proof-of-concept — 3 paths, MODE A/B/C.
//
// Task book §二/§三/§六:
//
//   Mode A — full interception (control):
//     setIgnoreMouseEvents(false)  — top window receives all clicks
//                                    underlay receives NONE in overlap area
//
//   Mode B — full passthrough (control):
//     setIgnoreMouseEvents(true)   — top window receives NO clicks
//                                    underlay receives ALL clicks
//
//   Mode C — regional selective (task book §三 target):
//     Two R62 implementations, user-selectable via inner radio in HTML:
//
//     Path 1 — Electron main polling:
//       Main process polls screen.getCursorScreenPoint() at 50ms (20Hz),
//       compares against BrowserWindow.getBounds() (DIP) and a fixed
//       sprite rect, and toggles setIgnoreMouseEvents(true, {forward:true})
//       only when cursor is OUTSIDE the sprite. Throttled to state changes
//       only (no per-tick setIgnore call). R54's broken version had:
//         - IPC lag (sprite-bounds/drag-state, 50-150ms) that flipped state
//           mid-drag and dropped pointerup;
//         - 5Hz not 20Hz.
//       R62 Path 1 fixes both.
//
//     Path 3 — Compact window:
//       Use a smaller alwaysOnTop+transparent BrowserWindow whose
//       bounds exactly match the visible sprite (no transparent 0-alpha
//       margin around the sprite). macOS's standard transparent-window
//       click-forwarding is the entire mechanism — no
//       setIgnoreMouseEvents flip required. This trades a small visual
//       design change for guaranteed cross-window click delivery.
//
// R61 Mode C (stage.eventMode='none' + sprite.eventMode='static') was
// re-evaluated in R62 and judged INVALID as a system-level passthrough
// mechanism: stage.eventMode only governs PIXI v7's INTERNAL event
// dispatch; it cannot control whether macOS delivers OS-level clicks to
// the transparent BrowserWindow. We keep that config in the file as a
// labelled "R61 WRONG" baseline for evidence-collection purposes.

const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const HERE = __dirname;

const POC_MODE = (process.env.POC_MODE || 'A').toUpperCase();  // A | B | C
const PATH_FOR_C = (process.env.POC_PATH || '1').toUpperCase();  // 1 | 3
const QUIT_AFTER = parseFloat(process.env.POC_QUIT_AFTER || '60') || 60;

// Top window sprite rect (in DIP, relative to BrowserWindow). Fixed for
// the 256x256 window and the centred gold ball.
const SPRITE_CX = 128, SPRITE_CY = 128, SPRITE_R = 50;
// Path 1: cursor-in-sprite? setIgnore(false); else setIgnore(true, {forward:true})
// Path 3: window size = sprite-bbox-only (no transparent margin)

let topWindow = null;
let underWindow = null;
let topClicks = 0;
let underClicks = 0;
let topAt = [];
let underAt = [];
let transitions = 0;
let lastIgnoreState = null;

function modeCWindowGeometry() {
    if (PATH_FOR_C === '3') {
        // Path 3: shrink window to sprite bbox. No alpha=0 margin.
        return {
            x: 220, y: 220,
            width: 2 * SPRITE_R,
            height: 2 * SPRITE_R,
        };
    }
    // Path 1: full 256x256 — main process polls + toggles.
    return { x: 200, y: 200, width: 256, height: 256 };
}

function createTopWindow() {
    const geom = modeCWindowGeometry();
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
        topAt.push({ x: info.x, y: info.y, t: Date.now() });
        console.log(`[R62 PoC] TOP click #${topClicks} at (${info.x},${info.y}) mode=${POC_MODE} path=${PATH_FOR_C}`);
    });
    return top;
}

function createUnderWindow() {
    const under = new BrowserWindow({
        x: 240, y: 280,
        width: 360, height: 180,
        frame: true,
        transparent: false,
        alwaysOnTop: false,
        title: `UNDERLAY (mode=${POC_MODE}${POC_MODE==='C'?'/'+PATH_FOR_C:''}) — click under transparent area`,
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
        underAt.push({ x: info.x, y: info.y, t: Date.now() });
        console.log(`[R62 PoC] UNDER click #${underClicks} at (${info.x},${info.y}) mode=${POC_MODE} path=${PATH_FOR_C}`);
    });
    return under;
}

function applyMode() {
    if (POC_MODE === 'A') {
        topWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
        console.log('[R62 PoC] Mode A: setIgnoreMouseEvents(false) — top intercepts all');
    } else if (POC_MODE === 'B') {
        topWindow.setIgnoreMouseEvents(true);
        lastIgnoreState = true;
        console.log('[R62 PoC] Mode B: setIgnoreMouseEvents(true) — full passthrough');
    } else if (POC_MODE === 'C' && PATH_FOR_C === '1') {
        // Path 1: never set ignore=true here. Start with false; main poll will
        // toggle as needed.
        topWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
        console.log('[R62 PoC] Mode C Path 1: main poll toggles setIgnore based on cursor/sprite');
    } else if (POC_MODE === 'C' && PATH_FOR_C === '3') {
        // Path 3: never toggle. The window bounds already cover only the
        // sprite; transparent-window click forwarding is left to macOS.
        topWindow.setIgnoreMouseEvents(false);
        lastIgnoreState = false;
        console.log('[R62 PoC] Mode C Path 3: window bounds = sprite bbox; macOS default forwarding');
    }
}

// Path 1: 20Hz main process poll. Throttled to state changes only.
let pollHandle = null;
function startPath1Polling() {
    if (pollHandle) return;
    pollHandle = setInterval(() => {
        if (!topWindow || topWindow.isDestroyed()) return;
        const cursor = screen.getCursorScreenPoint();
        const wb = topWindow.getBounds();
        if (!wb) return;
        const insideWindow =
            cursor.x >= wb.x && cursor.x < wb.x + wb.width &&
            cursor.y >= wb.y && cursor.y < wb.y + wb.height;
        let wantIgnore;
        if (!insideWindow) {
            wantIgnore = false;  // cursor outside: keep top accepting for re-enter event
        } else {
            // Inside window: ignore=true unless cursor is inside the sprite bbox
            const cx = wb.x + SPRITE_CX;
            const cy = wb.y + SPRITE_CY;
            const dx = cursor.x - cx;
            const dy = cursor.y - cy;
            const inSprite = (dx*dx + dy*dy) < SPRITE_R*SPRITE_R;
            wantIgnore = !inSprite;
        }
        if (wantIgnore === lastIgnoreState) return;
        lastIgnoreState = wantIgnore;
        transitions++;
        try {
            topWindow.setIgnoreMouseEvents(wantIgnore, wantIgnore ? { forward: true } : undefined);
        } catch (e) {
            console.log(`[R62 PoC] setIgnore error: ${e && e.message}`);
        }
        console.log(`[R62 PoC] transition ${transitions}: cursor inside=${insideWindow} → setIgnore=${wantIgnore}`);
    }, 50);  // 20Hz
}

function checkGeometry(top, under) {
    const tb = top.getBounds();
    const ub = under.getBounds();
    const overlap = !(
        tb.x + tb.width  < ub.x || tb.x > ub.x + ub.width ||
        tb.y + tb.height < ub.y || tb.y > ub.y + ub.height
    );
    return { tb, ub, overlap };
}

function writeResult() {
    if (!topWindow || !underWindow) return;
    const geo = checkGeometry(topWindow, underWindow);
    const result = {
        run_id: `r62_${Date.now()}`,
        mode: POC_MODE,
        path_for_C: POC_MODE === 'C' ? PATH_FOR_C : null,
        started_at: new Date().toISOString(),
        top_window: geo.tb,
        under_window: geo.ub,
        geometry_overlap: geo.overlap,
        counts: { top_clicks: topClicks, under_clicks: underClicks, state_transitions: transitions },
        top_log: topAt,
        under_log: underAt,
        verdict: computeVerdict(),
    };

    const txt = [
        '=== R62 Passthrough PoC Result ===',
        `mode:                ${POC_MODE}`,
        `path_for_C:          ${result.path_for_C || 'n/a'}`,
        `started_at:          ${result.started_at}`,
        `top_window bounds:   ${JSON.stringify(geo.tb)}`,
        `under_window bounds: ${JSON.stringify(geo.ub)}`,
        `geometry_overlap:    ${geo.overlap}`,
        `top_clicks:          ${topClicks}`,
        `under_clicks:        ${underClicks}`,
        `state_transitions:   ${transitions}`,
        `top_log:             ${JSON.stringify(topAt)}`,
        `under_log:           ${JSON.stringify(underAt)}`,
        `verdict:             ${result.verdict}`,
    ];
    fs.writeFileSync('/tmp/passthrough_poc_result.txt', txt.join('\n') + '\n');
    fs.writeFileSync('/tmp/passthrough_poc_result.json', JSON.stringify(result, null, 2));
    const csv = [
        'run_id,mode,path,started_at,top_x,top_y,top_w,top_h,under_x,under_y,under_w,under_h,overlap,top_clicks,under_clicks,transitions,verdict',
        [
            result.run_id, POC_MODE, result.path_for_C || '', result.started_at,
            geo.tb.x, geo.tb.y, geo.tb.width, geo.tb.height,
            geo.ub.x, geo.ub.y, geo.ub.width, geo.ub.height,
            geo.overlap ? 1 : 0,
            topClicks, underClicks, transitions,
            `"${result.verdict}"`,
        ].join(','),
    ].join('\n');
    fs.writeFileSync('/tmp/passthrough_poc_result.csv', csv + '\n');
    console.log('[R62 PoC] wrote /tmp/passthrough_poc_result.{txt,json,csv}');
}

function computeVerdict() {
    if (POC_MODE === 'A') {
        return topClicks >= 1 && underClicks === 0
            ? 'AUTO_PASS_A (top only — control)'
            : 'NEED_MORE_CLICKS (Mode A)';
    }
    if (POC_MODE === 'B') {
        return topClicks === 0 && underClicks >= 1
            ? 'AUTO_PASS_B (under only — control)'
            : 'NEED_MORE_CLICKS (Mode B)';
    }
    if (POC_MODE === 'C' && PATH_FOR_C === '1') {
        // Path 1: GUI verification REQUIRED for real cross-window click
        // delivery. Agent cannot simulate system mouse events.
        return 'GUI_VERIFICATION_REQUIRED (Path 1: main poll + setIgnore)';
    }
    if (POC_MODE === 'C' && PATH_FOR_C === '3') {
        return 'GUI_VERIFICATION_REQUIRED (Path 3: compact window; macOS default)';
    }
    return 'UNKNOWN';
}

// ---- App lifecycle ----
let quitTimer = null;
app.whenReady().then(() => {
    console.log(`[R62 PoC] mode=${POC_MODE} path=${PATH_FOR_C} quit-after=${QUIT_AFTER}s`);
    underWindow = createUnderWindow();
    setTimeout(() => {
        topWindow = createTopWindow();
        topWindow.webContents.once('did-finish-load', () => {
            setTimeout(() => {
                applyMode();
                if (POC_MODE === 'C' && PATH_FOR_C === '1') {
                    startPath1Polling();
                }
                const geo = checkGeometry(topWindow, underWindow);
                console.log(`[R62 PoC] top   bounds: ${JSON.stringify(geo.tb)}`);
                console.log(`[R62 PoC] under bounds: ${JSON.stringify(geo.ub)}`);
                console.log(`[R62 PoC] overlap: ${geo.overlap}`);
                console.log(`[R62 PoC] READY for user manual click test (mode=${POC_MODE})`);
                printModeHints();
                quitTimer = setTimeout(() => {
                    console.log('[R62 PoC] quitting...');
                    writeResult();
                    app.quit();
                }, QUIT_AFTER * 1000);
            }, 600);
        });
    }, 300);
});

function printModeHints() {
    if (POC_MODE === 'A') {
        console.log('  → click the gold ball (sprite) AND on transparent corner.');
        console.log('  → expected: top count up, under count = 0');
    } else if (POC_MODE === 'B') {
        console.log('  → click the gold ball AND on transparent corner.');
        console.log('  → expected: under count up, top count = 0');
    } else if (POC_MODE === 'C') {
        if (PATH_FOR_C === '1') {
            console.log('  → Path 1: top window 256x256, sprite in centre.');
            console.log('  → click gold ball (sprite) — top should count +1');
            console.log('  → click transparent corner — main process poll toggles ignore=true → under should count +1');
            console.log('  → GUI test required — agent environment cannot simulate real system mouse');
        } else {
            console.log('  → Path 3: top window 100x100 (sprite bbox ONLY, no transparent margin).');
            console.log('  → click the gold ball — top should count +1');
            console.log('  → click OUTSIDE the gold ball (still inside top 100x100 bbox) — under should count +1');
            console.log('  → GUI test required — macOS transparent window default forwarding');
        }
    }
}

app.on('window-all-closed', () => {
    writeResult();
    app.quit();
});
app.on('before-quit', () => {
    writeResult();
});
