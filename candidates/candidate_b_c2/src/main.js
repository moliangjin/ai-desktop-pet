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

const { app, BrowserWindow, ipcMain, screen } = require('electron');
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
    // R102 P0-5: 兼容 --quit-after=<value> 形式 (e.g. --quit-after=1800)
    else if (a.startsWith('--quit-after=')) quitAfter = parseFloat(a.split('=')[1], 10);
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

// R100 尺寸档位: 基于 26 帧 alpha 边界分析 (113x190 联合可见)
//   选 200x240: 容纳 jump 顶部 (y=30 in 256 frame) + 必要 padding, 减小 27% 横向 + 6% 纵向
const STANDARD_SIZE = parseInt(process.env.STANDARD_SIZE || '256', 10);
const COMPACT_SIZE = parseInt(process.env.COMPACT_SIZE || '200', 10);
const COMPACT_HEIGHT = parseInt(process.env.COMPACT_HEIGHT || '240', 10);

let mainWindow = null;
let currentMode = initialMode === 'compact' ? 'compact' : 'standard';

function applyMode(mode) {
    // R100 P0-4 修复: 模式切换保持角色屏幕中心稳定
    //   不再用固定 winX/winY, 而是用当前窗口中心算切换后位置
    // R102 P0-1: 用统一 getModeSize (compact=200x240, standard=256x256)
    currentMode = mode;
    if (!mainWindow) return;
    const { w, h } = getModeSize(mode);
    // R100 P0-4: 用当前实际 bounds 算中心, 保持角色视觉位置稳定
    const oldBounds = mainWindow.getBounds();
    const oldCenterX = oldBounds.x + oldBounds.width / 2;
    const oldCenterY = oldBounds.y + oldBounds.height / 2;
    const newX = Math.round(oldCenterX - w / 2);
    const newY = Math.round(oldCenterY - h / 2);
    mainWindow.setBounds({ x: newX, y: newY, width: w, height: h });
    // 保持可点击
    mainWindow.setIgnoreMouseEvents(false);
    // R100 P0-4: 传 centerX/centerY 给 renderer, 角色锚点对齐
    if (mainWindow.webContents) {
        mainWindow.webContents.send('set-mode', {
            mode,
            size: { w, h },
            centerX: w / 2,
            centerY: h,  // anchor 0.9 → sprite 中心 y = h
        });
    }
    console.log(`[main] R100 mode=${mode} bounds=(${newX},${newY},${w},${h}) center=(${oldCenterX},${oldCenterY}) preserved`);
}

// R102 P0-1: 统一用 size 对象 — compact=200x240, standard=256x256
function getModeSize(mode) {
    if (mode === 'compact') return { w: COMPACT_SIZE, h: COMPACT_HEIGHT };
    return { w: STANDARD_SIZE, h: STANDARD_SIZE };
}

function createWindow() {
    const startSize = getModeSize(currentMode);
    mainWindow = new BrowserWindow({
        x: winX, y: winY,
        width: startSize.w, height: startSize.h,
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
            compactSize: { w: COMPACT_SIZE, h: COMPACT_HEIGHT },
            standardSize: { w: STANDARD_SIZE, h: STANDARD_SIZE },
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

// R100 P0-2 修复: request-mode 走 ipcMain.handle (invoke 同步模式) 等 renderer ack
//   协议: renderer.invoke('request-mode', {mode}) → main 调 applyMode → 发 set-mode IPC
//   → renderer.applyModeToScene → 渲 renderer-mode-ready → main.resolve(invoke)
//   不允许只改 canvas 不改 BrowserWindow (R98 漏洞)
let pendingModeResolvers = new Map();
ipcMain.handle('request-mode', async (_evt, payload) => {
    const mode = payload && payload.mode;
    if (mode !== 'standard' && mode !== 'compact') {
        return { ok: false, error: 'invalid mode' };
    }
    console.log(`[main] R100 request-mode=${mode} (await renderer-mode-ready)`);
    const requestId = `mode-${Date.now()}-${Math.random()}`;
    return new Promise((resolve) => {
        pendingModeResolvers.set(requestId, { mode, resolve, startTs: Date.now() });
        applyMode(mode);
        // 超时保护: 5s 未收到 renderer ack 视为失败
        setTimeout(() => {
            if (pendingModeResolvers.has(requestId)) {
                const r = pendingModeResolvers.get(requestId);
                pendingModeResolvers.delete(requestId);
                console.warn(`[main] R100 request-mode=${mode} timeout (renderer-mode-ready not received)`);
                r.resolve({ ok: false, error: 'timeout: renderer-mode-ready not received' });
            }
        }, 5000);
    });
});

// R100 P0-2 修复: main 收 renderer-mode-ready 后 resolve invoke
ipcMain.on('renderer-mode-ready', (_evt, ack) => {
    // 找到最早的 pending resolver (只支持同时一个 mode 切换)
    if (pendingModeResolvers.size === 0) {
        console.warn(`[main] R100 unexpected renderer-mode-ready:`, ack);
        return;
    }
    const [requestId, r] = pendingModeResolvers.entries().next().value;
    pendingModeResolvers.delete(requestId);
    // R100 P0-2 协议断言: BrowserWindow 实际尺寸 + Canvas 尺寸 + 中心
    const actualBounds = mainWindow ? mainWindow.getBounds() : null;
    const expectedSize = ack && ack.size;
    const match = actualBounds && expectedSize &&
        actualBounds.width === expectedSize.w &&
        actualBounds.height === expectedSize.h;
    console.log(`[main] R100 renderer-mode-ready mode=${ack?.mode} expected=${JSON.stringify(expectedSize)} actual=${JSON.stringify(actualBounds && {w: actualBounds.width, h: actualBounds.height})} match=${match}`);
    r.resolve({
        ok: ack && ack.ok && match,
        mode: ack?.mode,
        size: expectedSize,
        actualBounds: actualBounds && { x: actualBounds.x, y: actualBounds.y, w: actualBounds.width, h: actualBounds.height },
        centerX: ack?.centerX,
        centerY: ack?.centerY,
        protocolMatch: match,
    });
});

// R104 P0-1: 真正 BrowserWindow 拖拽 — 鼠标按桌宠 → 整个 Electron 窗口跟随移动
//   renderer drag-start: 记录 dragStart 时的窗口 bounds + 鼠标屏幕坐标
//   renderer drag-move: 每次移动发 mouse 屏幕坐标, main 算 delta, setBounds 移动窗口
//   renderer drag-end: 清理 dragStart
//   使用 Electron 原生 BrowserWindow.setBounds (不需要 AX/Screen Recording)
//
// R107 修复: 原 line 286 `screen.getDisplayMatching(bounds)` 引用未定义变量 bounds
//   (drag-start 中 const bounds = mainWindow.getBounds() 作用域只在该 handler 内)
//   现在统一从 mainWindow 拿 bounds, 并加 try/catch 防护.
let dragStart = null;  // {winX, winY, width, height, mouseScreenX, mouseScreenY}
ipcMain.handle('window-drag-start', (_evt) => {
    if (!mainWindow) return { ok: false, error: 'no main window' };
    let bounds;
    try {
        bounds = mainWindow.getBounds();
    } catch (e) {
        console.error(`[main] R107 window-drag-start getBounds error: ${e?.message}`);
        return { ok: false, error: 'getBounds failed' };
    }
    const mouse = screen.getCursorScreenPoint();
    dragStart = {
        winX: bounds.x,
        winY: bounds.y,
        width: bounds.width,
        height: bounds.height,
        mouseScreenX: mouse.x,
        mouseScreenY: mouse.y,
    };
    console.log(`[main] R108 window-drag-start bounds=(${bounds.x},${bounds.y},${bounds.width},${bounds.height}) mouse=(${mouse.x},${mouse.y})`);
    return { ok: true, start: dragStart };
});
ipcMain.on('window-drag-move', (_evt, mouse) => {
    // R108 防护: 多重 null check (单击不拖动 / drag-end 后 / window 失焦后)
    if (!mainWindow || !dragStart || !mouse || typeof mouse.x !== 'number' || typeof mouse.y !== 'number') return;
    try {
        const dx = mouse.x - dragStart.mouseScreenX;
        const dy = mouse.y - dragStart.mouseScreenY;
        const newX = Math.round(dragStart.winX + dx);
        const newY = Math.round(dragStart.winY + dy);
        // R108 修复: screen.getDisplayMatching 必须接收 Rectangle (非 BrowserWindow)
        //   原 R107 传 mainWindow 是错的 Electron API 调用
        const rect = mainWindow.getBounds();
        const display = screen.getDisplayMatching(rect);
        const wa = display.workArea;
        const clampedX = Math.max(wa.x, Math.min(newX, wa.x + wa.width - dragStart.width));
        const clampedY = Math.max(wa.y, Math.min(newY, wa.y + wa.height - dragStart.height));
        // R108: 记录 before bounds 用于 R108 测试断言
        const beforeX = rect.x, beforeY = rect.y;
        mainWindow.setBounds({
            x: clampedX, y: clampedY,
            width: dragStart.width, height: dragStart.height,
        });
        // R108: 立即读 after bounds 断言实际变化 (避免 catch 吞掉 setBounds 异常)
        const afterRect = mainWindow.getBounds();
        console.log(`[main] R108 window-drag-move dx=${dx}dy=${dy} before=(${beforeX},${beforeY}) after=(${afterRect.x},${afterRect.y}) new=(${clampedX},${clampedY})`);
    } catch (e) {
        // R108: 异常必须 log (不能吞), 但 drag 状态清零避免后续误移动
        console.error(`[main] R108 window-drag-move ERROR: ${e?.message}; drag state cleared`);
        dragStart = null;
    }
});
ipcMain.on('window-drag-end', (_evt) => {
    if (dragStart) {
        const final = mainWindow ? mainWindow.getBounds() : null;
        console.log(`[main] R108 window-drag-end final=(${final?.x},${final?.y}) boundsSize=${final?.width}x${final?.height}`);
    }
    // R108: drag-end 后清理, 之后 send drag-move 不移动窗口
    dragStart = null;
});

// R104: 监听 window blur 强制结束拖拽 (避免拖到其他应用时卡住)
if (typeof app !== 'undefined' && app.on) {
    app.on('browser-window-blur', () => {
        if (dragStart) {
            console.log('[main] R104 window blur, clearing drag state');
            dragStart = null;
        }
    });
}

