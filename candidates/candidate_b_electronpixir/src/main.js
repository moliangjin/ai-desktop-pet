// AI Pet Candidate B — Electron main process.
// Loads manifest, creates transparent+frameless BrowserWindow,
// launches the renderer with PixiJS sprite animation.
//
// CLI flags:
//   --manifest <path>    (required)
//   --size <px>          (default 256)
//   --x <px>, --y <px>   (window origin in macOS screen coords)
//   --quit-after <sec>   (auto-quit after N seconds; useful for tests)
//   --perf-out <path>    (write CSV perf samples here)
//
// Notes:
//   - WebPreferences: nodeIntegration=true because we need fs/path in renderer
//     for the V0.0 manifest interface test (T09). For V1.0/V2.0 this should
//     become a sandboxed IPC bridge (PRD FR-G.1 / FR-G.4).
//   - Transparent window requires frame:false, transparent:true,
//     backgroundColor with 0 alpha; on macOS 14 + Electron 33 the OS still
//     sometimes composites the window as opaque. The same workaround used
//     in candidate A (alphaValue / setOpacity) is applied here via
//     setOpacity(0.999).
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

const args = process.argv.slice(1);
let manifestPath = null, winSize = 256, winX = 200, winY = 200;
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
    // T01 workaround: force the window into a translucent backing.
    mainWindow.setOpacity(0.999);
    // R53 passthrough: keep the BrowserWindow in standard event-receiving
    // mode. The transparent-area click forwarding is now handled entirely
    // by PIXI (stage.eventMode='none' + sprite.eventMode='static') plus
    // macOS's native transparent-window alpha forwarding.
    // We do NOT use setIgnoreMouseEvents(true,{forward:true}) anymore —
    // R53 real-Mac test confirmed that flip caused click losses.
    mainWindow.setIgnoreMouseEvents(false);

    // Diagnostic: log window lifecycle.
    mainWindow.on('ready-to-show', () => {
        console.log('[main] window ready-to-show');
    });
    mainWindow.on('show', () => {
        console.log('[main] window show');
    });
    mainWindow.on('blur', () => {
        console.log('[main] window blur');
    });
    mainWindow.on('focus', () => {
        console.log('[main] window focus');
    });
    mainWindow.on('closed', () => {
        console.log('[main] window closed');
    });

    mainWindow.loadFile(path.join(__dirname, 'renderer.html'));
    mainWindow.webContents.on('did-finish-load', () => {
        // Inject manifest content into the renderer rather than letting it
        // re-read the file, so the test T09 can swap manifests without
        // shipping extra files into the asar.
        const data = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
        const manifestBase = path.dirname(manifestPath);
        mainWindow.webContents.send('manifest', { manifest: data, baseDir: manifestBase });
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

// V0.0 R54 passthrough state machine.
//
// Three stable states:
//
//   SPRITE_HOVER (ignore=false)
//       cursor inside the BrowserWindow AND inside the sprite hitbox.
//       BrowserWindow receives events; PIXI sprite reacts to click/drag.
//
//   WIN_HOVER (ignore=true, forward=true)
//       cursor inside the BrowserWindow BUT outside the sprite hitbox.
//       BrowserWindow does NOT receive events; macOS forwards them to
//       the underlying window (ClickThroughProbe, Finder, etc.).
//
//   OUTSIDE (ignore=false)
//       cursor outside the BrowserWindow. We keep ignore=false so if
//       the user moves back into the window we receive the mouse event
//       that re-enters.
//
// Transitions are driven by a 20 Hz main-process loop using
// screen.getCursorScreenPoint() — no renderer IPC needed once the
// renderer pushes the sprite bounds once on resize/move.
//
// Anti-jitter rules:
//  * Only call setIgnoreMouseEvents when the desired state changes.
//  * While the user is dragging (drag-active IPC), force ignore=false.
//  * The transition log caps at 1 line per change.

const { screen } = require('electron');

let spriteBounds = null;     // {x,y,width,height} in screen DIP coordinates
let dragActive = false;
let ignoreState = false;     // last applied state
let transitions = 0;

ipcMain.on('sprite-bounds', (_evt, b) => {
    if (b && typeof b.x === 'number') spriteBounds = b;
});

ipcMain.on('drag-state', (_evt, d) => {
    dragActive = !!d;
});

function setIfChanged(wantIgnore) {
    if (!mainWindow || wantIgnore === ignoreState) return;
    ignoreState = wantIgnore;
    transitions++;
    try {
        if (wantIgnore) {
            mainWindow.setIgnoreMouseEvents(true, { forward: true });
        } else {
            mainWindow.setIgnoreMouseEvents(false);
        }
    } catch (e) {
        console.log('[main] setIgnoreMouseEvents error:', e && e.message);
    }
    console.log(`[main] transition ${transitions}: setIgnoreMouseEvents(${wantIgnore})`);
}

function step() {
    if (!mainWindow) return;
    if (dragActive) { setIfChanged(false); return; }
    const cursor = screen.getCursorScreenPoint();  // DIP
    const wb = mainWindow.getBounds();              // DIP (electron returns DIP for non-scaling)
    if (!wb) return;
    const insideWindow =
        cursor.x >= wb.x && cursor.x < wb.x + wb.width &&
        cursor.y >= wb.y && cursor.y < wb.y + wb.height;
    if (!insideWindow) {
        // User left BrowserWindow. Keep ignore=false so the re-enter
        // event lands back in this window.
        setIfChanged(false);
        return;
    }
    let insideSprite = false;
    if (spriteBounds) {
        insideSprite =
            cursor.x >= spriteBounds.x &&
            cursor.x <  spriteBounds.x + spriteBounds.width &&
            cursor.y >= spriteBounds.y &&
            cursor.y <  spriteBounds.y + spriteBounds.height;
    }
    setIfChanged(!insideSprite);
}

setInterval(step, 50);  // 20 Hz
console.log('[main] R54 passthrough state machine started (20 Hz)');

// Diagnostic: expose transition count and current state to renderer for the
// GUI perf overlay (kept lightweight — no per-tick log to syslog).
ipcMain.handle('passthrough-stats', () => {
    return {
        transitions: transitions,
        ignore: ignoreState,
        bounds: mainWindow ? mainWindow.getBounds() : null,
    };
});
