// R61 INDEPENDENT passthrough proof-of-concept — 3-mode switchable.
//
// Task book §四 (R61):
//   Mode A — full interception:   setIgnoreMouseEvents(false)  → top window
//                                   receives all clicks; underlay receives none.
//   Mode B — full passthrough:    setIgnoreMouseEvents(true)   → top window
//                                   receives NO clicks; underlay receives all.
//   Mode C — regional selective:  setIgnoreMouseEvents(false)  + PIXI stage
//                                   eventMode='none' (R56 attempt) → top only
//                                   intercepts on sprite; underlay intercepts
//                                   alpha=0. **REQUIRES REAL MAC TEST**
//                                   to confirm cross-window click forwarding.
//
// R61 explicitly forbids merging C back into candidate B until real-Mac
// evidence is collected.
//
// Toggle mode via env: POC_MODE=A | B | C (default A as control test)
// Optional: --quit-after=<sec> (default 60)

const { app, BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs');
const HERE = __dirname;

// ---- CLI / env parsing ----
const POC_MODE = (process.env.POC_MODE || 'A').toUpperCase();
const QUIT_AFTER = parseFloat(process.env.POC_QUIT_AFTER || process.argv
    .filter(a => a.startsWith('--quit-after='))[0]?.split('=')[1]) || 60;

// ---- 0/1 click counter for the underlay window ----
let topClicks = 0;       // top window count
let underClicks = 0;     // underlay window count
let topAt = [];          // [{x, y, t}] for clicks the top window received
let underAt = [];        // same for underlay

// ---- Build the top (transparent) window with a gold-ball sprite ----
function createTopWindow() {
    const top = new BrowserWindow({
        x: 200, y: 200,
        width: 256, height: 256,
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
        const level = (ev && ev.level) || args[1] || 'log';
        console.log(`[top:console:${level}] ${msg}`);
    });
    // R61: based on POC_MODE, configure setIgnoreMouseEvents + IPC channel.
    // The IPC channel `report-click` lets the top window push its hit tests
    // back to main for evidence collection.
    // Mode A: setIgnore(false)  → top ALWAYS receives (no forwarding)
    // Mode B: setIgnore(true)   → top NEVER receives (full forwarding)
    // Mode C: setIgnore(false)  + stage.eventMode='none' (PIXI controls)
    const ipcSetting = {
        A: false,
        B: true,
        C: false,
    }[POC_MODE];
    if (ipcSetting !== undefined) {
        top.setIgnoreMouseEvents(ipcSetting);
        console.log(`[R61 PoC] mode=${POC_MODE}  setIgnoreMouseEvents=${ipcSetting}`);
    } else {
        console.log(`[R61 PoC] mode=${POC_MODE}  (unknown mode, defaulting to A)`);
        top.setIgnoreMouseEvents(false);
    }
    // Forward renderer click events to main.
    const { ipcMain } = require('electron');
    ipcMain.on('top-click', (_e, info) => {
        topClicks++;
        topAt.push({ x: info.x, y: info.y, t: Date.now() });
        console.log(`[R61 PoC] TOP click #${topClicks} at (${info.x},${info.y}) mode=${POC_MODE}`);
    });
    return top;
}

// ---- Build the underlay (non-transparent) window with a click counter ----
function createUnderWindow() {
    const under = new BrowserWindow({
        x: 240, y: 280,
        width: 360, height: 180,
        frame: true,
        transparent: false,
        alwaysOnTop: false,
        title: `UNDERLAY (mode=${POC_MODE}) — clicks here increment under counter`,
        webPreferences: { nodeIntegration: true },
    });
    under.loadFile(path.join(HERE, 'probe.html'));
    under.webContents.on('console-message', (...args) => {
        const ev = args[0];
        const msg = (ev && ev.message) || args[2] || '';
        const level = (ev && ev.level) || args[1] || 'log';
        console.log(`[under:console:${level}] ${msg}`);
    });
    const { ipcMain } = require('electron');
    ipcMain.on('under-click', (_e, info) => {
        underClicks++;
        underAt.push({ x: info.x, y: info.y, t: Date.now() });
        console.log(`[R61 PoC] UNDER click #${underClicks} at (${info.x},${info.y})`);
    });
    return under;
}

// ---- Geometry verifier ----
function checkGeometry(top, under) {
    const tb = top.getBounds();
    const ub = under.getBounds();
    const overlap = !(
        tb.x + tb.width  < ub.x || tb.x > ub.x + ub.width ||
        tb.y + tb.height < ub.y || tb.y > ub.y + ub.height
    );
    const topOverlaysUnder = (tb.x <= ub.x) && (tb.y <= ub.y) &&
                              (tb.x + tb.width >= ub.x) && (tb.y + tb.height >= ub.y);
    return { tb, ub, overlap, topOverlaysUnder };
}

// ---- Result writer ----
function writeResult(top, under) {
    const geo = checkGeometry(top, under);
    const result = {
        run_id: `r61_${Date.now()}`,
        mode: POC_MODE,
        quit_after_sec: QUIT_AFTER,
        started_at: new Date().toISOString(),
        top_window: {
            bounds: geo.tb,
            alwaysOnTop: true,
            transparent: true,
            frame: false,
        },
        under_window: {
            bounds: geo.ub,
            alwaysOnTop: false,
            transparent: false,
            frame: true,
        },
        geometry: {
            overlap_rects: geo.overlap,
            top_overlays_under: geo.topOverlaysUnder,
        },
        counts: {
            top_clicks: topClicks,
            under_clicks: underClicks,
        },
        top_click_log: topAt,
        under_click_log: underAt,
        verdict_by_mode: {
            A: topClicks >= 1 && underClicks === 0
                ? 'AUTO_PASS (top only)'
                : 'NEED MORE CLICKS',
            B: topClicks === 0 && underClicks >= 1
                ? 'AUTO_PASS (under only)'
                : 'NEED MORE CLICKS',
            C: 'REQUIRES_GUI_TEST — agent environment cannot simulate real cross-window mouse events; user must click gold center + transparent corner on Mac mini',
        },
    };

    // TXT
    const txt = [];
    txt.push('=== R61 Passthrough PoC Result ===');
    txt.push(`mode:         ${POC_MODE}`);
    txt.push(`started_at:   ${result.started_at}`);
    txt.push(`run_id:       ${result.run_id}`);
    txt.push(`top bounds:   ${JSON.stringify(geo.tb)}`);
    txt.push(`under bounds: ${JSON.stringify(geo.ub)}`);
    txt.push(`overlap:      ${geo.overlap}`);
    txt.push(`top_overlays_under: ${geo.topOverlaysUnder}`);
    txt.push(`top_clicks:   ${topClicks}`);
    txt.push(`under_clicks: ${underClicks}`);
    txt.push(`top log:    ${JSON.stringify(topAt)}`);
    txt.push(`under log:  ${JSON.stringify(underAt)}`);
    txt.push(`verdict:    ${result.verdict_by_mode[POC_MODE] || 'n/a'}`);
    fs.writeFileSync('/tmp/passthrough_poc_result.txt', txt.join('\n') + '\n');

    // JSON
    fs.writeFileSync('/tmp/passthrough_poc_result.json', JSON.stringify(result, null, 2));

    // CSV (single row)
    const csvRow = [
        result.run_id, POC_MODE, result.started_at,
        geo.tb.x, geo.tb.y, geo.tb.width, geo.tb.height,
        geo.ub.x, geo.ub.y, geo.ub.width, geo.ub.height,
        geo.overlap ? 1 : 0,
        topClicks, underClicks,
        result.verdict_by_mode[POC_MODE] || '',
    ].join(',');
    fs.writeFileSync('/tmp/passthrough_poc_result.csv',
        'run_id,mode,started_at,top_x,top_y,top_w,top_h,under_x,under_y,under_w,under_h,overlap,top_clicks,under_clicks,verdict\n' + csvRow + '\n');

    console.log('[R61 PoC] wrote /tmp/passthrough_poc_result.{txt,json,csv}');
}

// ---- Lifecycle ----
let topWindow = null;
let underWindow = null;
let quitTimer = null;

app.whenReady().then(() => {
    console.log(`[R61 PoC] mode=${POC_MODE}  quit-after=${QUIT_AFTER}s`);
    underWindow = createUnderWindow();
    setTimeout(() => {
        topWindow = createTopWindow();
        setTimeout(() => {
            const geo = checkGeometry(topWindow, underWindow);
            console.log(`[R61 PoC] top   bounds: ${JSON.stringify(geo.tb)}`);
            console.log(`[R61 PoC] under bounds: ${JSON.stringify(geo.ub)}`);
            console.log(`[R61 PoC] overlap: ${geo.overlap}  top_overlays_under: ${geo.topOverlaysUnder}`);
            console.log(`[R61 PoC] READY for user manual click test`);
            if (POC_MODE === 'A') {
                console.log('  → click on the gold ball (sprite area) AND on transparent corner.');
                console.log('  → expected: top count goes up, under count stays 0');
            } else if (POC_MODE === 'B') {
                console.log('  → click on the gold ball (sprite area) AND on transparent corner.');
                console.log('  → expected: under count goes up, top count stays 0');
            } else {
                console.log('  → click on gold ball centre (top should receive) AND');
                console.log('    on transparent corner (under should receive).');
                console.log('  → expected: both counts increment, top should match sprite clicks only.');
            }
            quitTimer = setTimeout(() => {
                console.log('[R61 PoC] quitting...');
                writeResult(topWindow, underWindow);
                app.quit();
            }, QUIT_AFTER * 1000);
        }, 1500);
    }, 300);
});

app.on('window-all-closed', () => {
    if (topWindow) writeResult(topWindow, underWindow);
    app.quit();
});

app.on('before-quit', () => {
    if (topWindow && underWindow) writeResult(topWindow, underWindow);
});
