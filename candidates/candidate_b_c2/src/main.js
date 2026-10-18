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
// R108 修复: screen.getDisplayMatching 接收 Rectangle (非 BrowserWindow)
// R111 修复: 坐标系混用 (R104 dragStart.mouseScreenX 是屏幕坐标, R108 mouse.x 是 renderer ev.clientX viewport 坐标)
// R113 修复: 快速拖拽不连续 (R111 依赖 renderer pointermove 触发 IPC, 鼠标离开 200x240 窗口后 pointermove 收不到)
//   新方案: main 端 setInterval 持续轮询 mouse 位置 (~60Hz), 不依赖 renderer pointermove
//   renderer 只发 start/end/cancel IPC (轻量), 真正的 setBounds 间隔由 main 决定
let dragStart = null;  // {winX, winY, width, height, mouseStartX, mouseStartY, dragStarted}
let dragPollInterval = null;  // R113: setInterval 句柄, drag 期间每 16ms 轮询 mouse 位置

// R113: 实际计算 dx/dy + setBounds 的核心函数 (interval 调, IPC move 也调, 重复无害 idempotent)
function performDragMove() {
    if (!mainWindow || !dragStart) return;
    try {
        const mouse = screen.getCursorScreenPoint();
        const dx = mouse.x - dragStart.mouseStartX;
        const dy = mouse.y - dragStart.mouseStartY;
        if (!dragStart.dragStarted) {
            if (Math.abs(dx) < 3 && Math.abs(dy) < 3) return;  // 3px 容忍, 仍算点击
            dragStart.dragStarted = true;
            console.log(`[main] R113 DRAG_REAL_START dx=${dx}dy=${dy} (3px 容忍通过)`);
        }
        const newX = Math.round(dragStart.winX + dx);
        const newY = Math.round(dragStart.winY + dy);
        const rect = mainWindow.getBounds();
        const display = screen.getDisplayMatching(rect);
        const wa = display.workArea;
        const clampedX = Math.max(wa.x, Math.min(newX, wa.x + wa.width - dragStart.width));
        const clampedY = Math.max(wa.y, Math.min(newY, wa.y + wa.height - dragStart.height));
        const beforeX = rect.x, beforeY = rect.y;
        mainWindow.setBounds({
            x: clampedX, y: clampedY,
            width: dragStart.width, height: dragStart.height,
        });
        // R113: 间隔节流 log (避免每 16ms 都打, 改为每 100ms 一次)
        const now = Date.now();
        if (!dragStart.lastLogAt || (now - dragStart.lastLogAt) > 100) {
            dragStart.lastLogAt = now;
            const afterRect = mainWindow.getBounds();
            console.log(`[main] R113 DRAG_POLL dx=${dx}dy=${dy} before=(${beforeX},${beforeY}) after=(${afterRect.x},${afterRect.y}) mouseNow=(${mouse.x},${mouse.y})`);
        }
    } catch (e) {
        console.error(`[main] R113 DRAG_MOVE_ERROR: ${e?.message}; clearing drag`);
        stopDragPolling();
        dragStart = null;
    }
}

function startDragPolling() {
    // R113: 启动 setInterval (~60Hz, 16ms 间隔) 持续轮询 mouse 位置
    //   解决快速拖拽跟随不连续: 不依赖 renderer pointermove
    //   鼠标在 200x240 窗口内/外都能拿到 screen.getCursorScreenPoint()
    if (dragPollInterval) clearInterval(dragPollInterval);
    dragPollInterval = setInterval(performDragMove, 16);
    console.log('[main] R113 DRAG_POLL_START intervalId=' + dragPollInterval);
}

function stopDragPolling() {
    // R113: drag-end/cancel/blur 必须清理 interval, 防泄漏
    if (dragPollInterval) {
        clearInterval(dragPollInterval);
        console.log('[main] R113 DRAG_POLL_STOP intervalId=' + dragPollInterval);
        dragPollInterval = null;
    }
}

ipcMain.handle('window-drag-start', (_evt) => {
    if (!mainWindow) return { ok: false, error: 'no main window' };
    let bounds, mouse;
    try {
        bounds = mainWindow.getBounds();
        mouse = screen.getCursorScreenPoint();
    } catch (e) {
        console.error(`[main] R113 DRAG_START_ERROR: ${e?.message}`);
        return { ok: false, error: 'drag-start setup failed' };
    }
    dragStart = {
        winX: bounds.x,
        winY: bounds.y,
        width: bounds.width,
        height: bounds.height,
        mouseStartX: mouse.x,
        mouseStartY: mouse.y,
        dragStarted: false,
        lastLogAt: 0,
    };
    // R113: drag-start 时启动 setInterval 轮询
    startDragPolling();
    console.log(`[main] R113 DRAG_START win=(${bounds.x},${bounds.y},${bounds.width},${bounds.height}) mouseStart=(${mouse.x},${mouse.y})`);
    return { ok: true, start: dragStart };
});

// R113: window-drag-move IPC 保留 (renderer 偶尔触发, 调 performDragMove 重复无害)
ipcMain.on('window-drag-move', (_evt, _unused) => {
    if (!dragStart) return;
    performDragMove();
});

function stopDrag() {
    // R113: drag-end/cancel 清理 setInterval + dragStart
    stopDragPolling();
    if (dragStart) {
        const final = mainWindow ? mainWindow.getBounds() : null;
        console.log(`[main] R113 DRAG_STOP final=(${final?.x},${final?.y}) size=${final?.width}x${final?.height} dragStarted=${dragStart.dragStarted}`);
        dragStart = null;
    } else {
        console.log('[main] R113 DRAG_STOP (no active drag)');
    }
}

ipcMain.on('window-drag-end', (_evt) => {
    stopDrag();
});

ipcMain.on('window-drag-cancel', (_evt) => {
    // R113: 显式 cancel IPC (pointercancel / blur 触发)
    if (dragStart) {
        console.log('[main] R113 DRAG_CANCEL (renderer reported)');
    }
    stopDrag();
});


// R113: 监听 window blur 强制结束拖拽 (避免拖到其他应用时卡住) + 清理 setInterval
if (typeof app !== 'undefined' && app.on) {
    app.on('browser-window-blur', () => {
        if (dragStart) {
            console.log('[main] R113 window blur, clearing drag state + interval');
            stopDrag();
        }
    });
}

