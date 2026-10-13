// AI Pet Candidate B — Electron main process.
//
// V0.0 R56 fail-isolation:
//   R54 introduced a 20Hz setIgnoreMouseEvents state machine that successfully
//   broke BOTH click and drag, even though R51 had click/drag working (per
//   real Mac mini test). The state machine's cursor-in-sprite polling fought
//   with PIXI's own hit-test, dropped pointerup events, and locked windows
//   out of event delivery in subtle ways.
//
//   Strategy: revert to R51-style architecture (no setIgnoreMouseEvents flip)
//   and add a feature-flag B_STATE_MACHINE_DISABLED=1 that *fully* disables
//   the R54 state machine. Default = DISABLED. PIXI's own hit-test decides
//   whether the cursor is over the sprite; macOS transparent BrowserWindow's
//   standard behaviour (NOT R54's flip) handles alpha=0 click forwarding.
//
//   Future direction documented: R56 re-enables the state machine only if
//   we can prove (with headless + Mac evidence) that `setIgnoreMouseEvents`
//   can be safely toggled around PIXI drag events. Until then, disabled by
//   default.
//
// CLI flags:
//   --manifest <path>
//   --size <px>          (default 256)
//   --x <px>, --y <px>   (window origin in macOS screen coords)
//   --quit-after <sec>
//   --perf-out <path>

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

const args = process.argv.slice(1);
let manifestPath = null, winSize = 256, winX = 1100, winY = 600;
let quitAfter = null, perfOut = null;
for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--manifest' && args[i+1]) manifestPath = args[++i];
    else if (a === '--size' && args[i+1]) winSize = parseInt(args[++i], 10);
    else if (a === '--x' && args[i+1]) winX = parseInt(args[++i], 10);
    else if (a === '--y' && args[i+1]) winY = parseInt(args[++i], 10);
    else if (a === '--quit-after' && args[i+1]) quitAfter = parseFloat(args[++i]);
    else if (a === '--perf-out' && args[i+1]) perfOut = args[++i];
}

if (!manifestPath) {
    console.error('[main] FATAL: --manifest required');
    app.exit(2);
}
if (!fs.existsSync(manifestPath)) {
    console.error(`[main] FATAL: manifest not found: ${manifestPath}`);
    app.exit(3);
}

let mainWindow = null;

// R56 state machine — DISABLED by default to restore R51 click/drag behaviour.
// Set B_STATE_MACHINE_ENABLED=1 only after comprehensive evidence is collected.
const STATE_MACHINE_ENABLED = process.env.B_STATE_MACHINE_ENABLED === '1';
let ignoreState = false, transitions = 0;

function createWindow() {
    mainWindow = new BrowserWindow({
        x: winX, y: winY,
        width: winSize, height: winSize,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        hasShadow: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        resizable: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            offscreen: false,
        },
    });
    mainWindow.setOpacity(0.999);

    // R56 critical fix: never toggle setIgnoreMouseEvents in default mode.
    // PIXI's hit-test (stage.interactiveChildren=true + sprite hitArea) does
    // the click discrimination; macOS transparent window's standard behavior
    // forwards alpha=0 clicks to underlying windows automatically.
    mainWindow.setIgnoreMouseEvents(false);

    console.log(`[main] B_STATE_MACHINE_ENABLED=${STATE_MACHINE_ENABLED ? 1 : 0} (R56 default off)`);

    // Diagnostic: log window lifecycle.
    mainWindow.on('ready-to-show', () => console.log('[main] window ready-to-show'));
    mainWindow.on('show', () => console.log('[main] window show'));
    mainWindow.on('blur', () => console.log('[main] window blur'));
    mainWindow.on('focus', () => console.log('[main] window focus'));
    mainWindow.on('closed', () => console.log('[main] window closed'));

    mainWindow.loadFile(path.join(__dirname, 'renderer.html'));
    mainWindow.webContents.on('did-finish-load', () => {
        const data = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
        const manifestBase = path.dirname(manifestPath);
        mainWindow.webContents.send('manifest', { manifest: data, baseDir: manifestBase });
        // R56 self-test: forward env flag to renderer (Electron sandboxes
        // process.env so we cannot read it from the renderer side).
        mainWindow.webContents.send('env', {
            PET_R56_SELFTEST: process.env.PET_R56_SELFTEST === '1' ? 1 : 0,
        });
    });

    // R56: forward renderer console.log → main stdout so the self-test is
    // visible in the same log file as the main process diagnostics.
    mainWindow.webContents.on('console-message', (...args) => {
        // Electron 33: (event, level, message, line, sourceId)
        const event = args[0];
        const legacyMessage = args[2];
        const msg = (event && event.message) || legacyMessage || '(no-message)';
        const level = (event && event.level) || args[1] || 'log';
        console.log(`[renderer:${level}] ${msg}`);
    });

    if (quitAfter) {
        setTimeout(() => {
            console.log('[main] quit-after elapsed, terminating');
            app.quit();
        }, quitAfter * 1000);
    }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    app.quit();
});

ipcMain.on('renderer-ready', (_evt, info) => {
    console.log(`[main] renderer-ready: pixi=${info && info.version}`);
});

ipcMain.on('perf-sample', (_evt, sample) => {
    if (!perfOut) return;
    const dir = path.dirname(perfOut);
    fs.mkdirSync(dir, { recursive: true });
    const exists = fs.existsSync(perfOut);
    const line = [
        sample.timestamp, sample.action, sample.fps.toFixed(2),
        sample.frame_ms_p50.toFixed(2), sample.frame_ms_p95.toFixed(2),
        sample.rss_mb.toFixed(2), sample.cpu_percent.toFixed(2)
    ].join(',') + '\n';
    if (!exists) {
        fs.writeFileSync(perfOut,
            'timestamp,action,fps,frame_ms_p50,frame_ms_p95,rss_mb,cpu_percent\n');
    }
    fs.appendFileSync(perfOut, line);
});

ipcMain.on('asset-report', (_evt, report) => {
    console.log(`[main] asset-report: ${report.action} loaded=${report.loaded} failed=${report.failed}`);
});

ipcMain.on('action-switch', (_evt, action) => {
    if (mainWindow) {
        mainWindow.webContents.send('set-action', action);
    }
});

// R56: R54 state machine is dead by default. If you must re-enable it,
// set B_STATE_MACHINE_ENABLED=1 and uncomment the block. Heed the warning
// in KNOWN_ISSUES.md — R54 broke click/drag on real Mac.

function r54DisabledStateMachineNote() {
    /* original R54 code removed intentionally — see commit 7cd8c4d */
}
