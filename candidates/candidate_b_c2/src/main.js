// AI Pet Candidate B-C2 — Electron main process.
// Loads manifest, creates transparent+frameless BrowserWindow,
// launches the renderer with PixiJS sprite animation.
//
// V0.0 R98: C2 compact window mode (临时替代真透明穿透).
//   - --mode standard   → 256x256 (原 R60 基线)
//   - --mode compact    → 200x200 (C2 紧凑, 减少桌面遮挡)
//   模式切换经 set-mode IPC 实时调整, 配套 canvas/sprite 重置.
//
// CLI flags:
//   --manifest <path>    (required)
//   --size <px>          (default 256)
//   --mode standard|compact (default standard)
//   --x <px>, --y <px>   (window origin in macOS screen coords)
//   --quit-after <sec>   (auto-quit after N seconds; useful for tests)
//   --perf-out <path>    (write CSV perf samples here)

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

const args = process.argv.slice(1);
let manifestPath = null, winSize = 256, winX = 200, winY = 200;
let initialMode = 'standard';
let quitAfter = null, perfOut = null;
for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--manifest' && args[i+1]) manifestPath = args[++i];
    else if (a === '--size' && args[i+1]) winSize = parseInt(args[++i], 10);
    else if (a === '--mode' && args[i+1]) initialMode = args[++i];
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

// R98: 紧凑模式尺寸档位 (默认 200x200, 比 256x256 减小 39% 遮挡面积)
const STANDARD_SIZE = parseInt(process.env.STANDARD_SIZE || '256', 10);
const COMPACT_SIZE = parseInt(process.env.COMPACT_SIZE || '200', 10);

let mainWindow = null;
let currentMode = initialMode === 'compact' ? 'compact' : 'standard';

function applyMode(mode) {
    // R98: standard ↔ compact 模式切换, BrowserWindow + 通知 renderer 重置 canvas
    currentMode = mode;
    if (!mainWindow) return;
    const sz = mode === 'compact' ? COMPACT_SIZE : STANDARD_SIZE;
    mainWindow.setBounds({ x: winX, y: winY, width: sz, height: sz });
    // 保持可点击 (C2 紧凑窗口不穿透 — 全部事件走本窗口)
    mainWindow.setIgnoreMouseEvents(false);
    if (mainWindow.webContents) {
        mainWindow.webContents.send('set-mode', { mode, size: sz });
    }
    console.log(`[main] mode=${mode} size=${sz} (R98 compact window)`);
}

function createWindow() {
    const startSize = currentMode === 'compact' ? COMPACT_SIZE : STANDARD_SIZE;
    mainWindow = new BrowserWindow({
        x: winX, y: winY,
        width: startSize, height: startSize,
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
    mainWindow.setIgnoreMouseEvents(false);

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

    mainWindow.webContents.on('console-message', (...args) => {
        const event = args[0];
        const legacyMessage = args[2];
        const msg = (event && event.message) || legacyMessage || '(no-message)';
        const level = (event && event.level) || args[1] || 'log';
        console.log(`[renderer:${level}] ${msg}`);
    });
    mainWindow.webContents.on('did-finish-load', () => {
        const data = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
        const manifestBase = path.dirname(manifestPath);
        mainWindow.webContents.send('manifest', {
            manifest: data,
            baseDir: manifestBase,
            initialMode: currentMode,
            compactSize: COMPACT_SIZE,
            standardSize: STANDARD_SIZE,
        });
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

// V0.0 R39: renderer-driven transparent-area passthrough.
let lastPassthrough = null;
ipcMain.on('set-passthrough', (_evt, ignore) => {
    if (!mainWindow) return;
    if (lastPassthrough === ignore) return;
    lastPassthrough = ignore;
    mainWindow.setIgnoreMouseEvents(!!ignore, { forward: true });
    console.log(`[main] setIgnoreMouseEvents(${!!ignore}, forward=true) (R39 passthrough)`);
});

// R98: 模式切换 IPC (standard ↔ compact) — C2 紧凑窗口控制
ipcMain.on('request-mode', (_evt, mode) => {
    if (mode !== 'standard' && mode !== 'compact') return;
    console.log(`[main] request-mode=${mode}`);
    applyMode(mode);
});

