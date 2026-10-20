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
// R141: 最小自主生活行为引擎 (纯逻辑, main 与测试共用同一份代码)
const { BehaviorEngine, STATES } = require('./behavior_engine');
// R144: 资源就绪判定 (main 与测试共用同一份代码)
const { evaluateAssetReadiness, REQUIRED_ACTIONS } = require('./asset_gate');

const args = process.argv.slice(1);
let manifestPath = null, winSize = 256, winX = 200, winY = 200;
let initialMode = 'standard';
let quitAfter = null, perfOut = null;
let acceptanceMode = false;    // R141 §九: 验收加速模式 (不改变正式状态机逻辑)
let sleepProbabilityOverride = null;   // R144: 行为概率覆盖 (0=只走, 1=只睡), 供确定性验收脚本使用
let previewDir_ = null;        // R147: 运行时预览采集目录 (仅验收/预览用, 正式运行为 null)
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
    // R147: 运行时预览采集 (输出 PNG 帧序列, 供生成可观看 GIF)
    else if (a === '--preview' && args[i+1]) previewDir_ = args[++i];
    // R141 §九: 验收加速模式 (只缩短时长参数, 不改变状态机逻辑)
    else if (a === '--acceptance') acceptanceMode = true;
    else if (a === '--acceptance-mode' && args[i+1]) acceptanceMode = (args[++i] !== 'off');
    // R144: 行为概率覆盖 — 只改 manifest 配置里的概率值, 不改状态机逻辑
    else if (a === '--sleep-probability' && args[i+1]) sleepProbabilityOverride = parseFloat(args[++i]);
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

// ====== R141: 自主行为引擎接入 ======
// 行为引擎只负责"决定做什么"; 窗口坐标/边界由 main 侧 adapter 提供.
let behaviorEngine = null;
let behaviorConfig = null;
let lastWindowBounds = null;   // 上次写入的窗口位置 (避免无变化时重复 setBounds)
let moveWindowLogAt_ = 0;      // 移动日志节流
// R144 P1: 小数位移累计器 (低速移动时避免每次取整把位移吃掉)
let moveRemainder_ = { x: 0, y: 0 };

function clampToWorkArea(x, y, w, h) {
    const rect = mainWindow.getBounds();
    const display = screen.getDisplayMatching(rect);
    const wa = display.workArea;
    const margin = (behaviorConfig && behaviorConfig.edge_margin_px) || 4;
    const maxX = wa.x + wa.width - w - margin;
    const maxY = wa.y + wa.height - h - margin;
    const minX = wa.x + margin;
    const minY = wa.y + margin;
    return {
        x: Math.max(minX, Math.min(x, Math.max(minX, maxX))),
        y: Math.max(minY, Math.min(y, Math.max(minY, maxY))),
        wa,
        minX, minX_end: maxX, minY, minY_end: maxY,
    };
}

// R141 §六 4/5: 平滑移动 + 不高频写入无变化位置
// R144 P1 修复:
//   1) 引擎给的是小数位移 (30px/s * 33ms ≈ 0.99px), 原来直接 setBounds(小数)
//      会被系统取整 → 窗口几乎不动 (低速丢步). 现在先累计, 凑够 1px 才移动.
//   2) setBounds 之后用 getBounds 复核**真实**位置, 日志与边界判定都用真实值.
function moveWindowBy(dx, dy) {
    if (!mainWindow) return { blocked: true, reason: 'no window' };
    if (behaviorEngine && behaviorEngine.getState() === STATES.DRAGGING) {
        return { blocked: true, reason: 'dragging' };
    }
    const rect = mainWindow.getBounds();
    // R144 P1: 小数位移累计 — Electron setBounds 需要整数坐标
    moveRemainder_.x += dx;
    moveRemainder_.y += dy;
    const stepX = Math.trunc(moveRemainder_.x);
    const stepY = Math.trunc(moveRemainder_.y);
    moveRemainder_.x -= stepX;
    moveRemainder_.y -= stepY;
    if (stepX === 0 && stepY === 0) {
        // 不足 1px: 保留到下一次累计, 不产生无效 setBounds
        return { blocked: false, moved: 0, accumulated: true, x: rect.x, y: rect.y };
    }
    const targetX = rect.x + stepX;
    const targetY = rect.y + stepY;
    const clamped = clampToWorkArea(targetX, targetY, rect.width, rect.height);
    // 撞边检测: 目标位置被夹住, 说明到达屏幕边缘
    const wouldBlock = Math.abs(clamped.x - targetX) > 0.5 || Math.abs(clamped.y - targetY) > 0.5;
    // 无变化则不写 (避免高频无意义 setBounds)
    if (lastWindowBounds &&
        lastWindowBounds.x === clamped.x && lastWindowBounds.y === clamped.y) {
        return { blocked: wouldBlock, moved: 0, clamped: true, x: clamped.x, y: clamped.y };
    }
    mainWindow.setBounds({ x: clamped.x, y: clamped.y, width: rect.width, height: rect.height });
    // R144 P1: setBounds 之后立即 getBounds 复核真实位置 (系统可能再取整/夹紧)
    const actual = mainWindow.getBounds();
    const movedX = actual.x - rect.x;
    const movedY = actual.y - rect.y;
    lastWindowBounds = { x: actual.x, y: actual.y, width: actual.width, height: actual.height };
    // R144 P1: 边界判定基于**复核后的真实窗口位置** —— 实际没动 = 撞到屏幕边缘。
    //   (不再用"目标被夹住"判定, 否则起点在区外时第一步行走会被误判成撞边)
    const actualBlocked = (movedX === 0 && movedY === 0);
    // R141: 移动日志 (节流 200ms) — 记录真实位置与真实位移
    const now = Date.now();
    if (!moveWindowLogAt_ || (now - moveWindowLogAt_) > 200) {
        moveWindowLogAt_ = now;
        console.log(`[main] R144 MOVE x=${actual.x} y=${actual.y} target=(${clamped.x},${clamped.y}) actual=(${actual.x},${actual.y}) moved=(${movedX},${movedY}) step=(${stepX},${stepY}) dx=${dx.toFixed(3)} blocked=${actualBlocked} state=${behaviorEngine ? behaviorEngine.getState() : 'n/a'}`);
    }
    return { blocked: actualBlocked, moved: movedX, requested: stepX, x: actual.x, y: actual.y };
}

function createBehaviorEngine(config) {
    behaviorConfig = config;
    const engine = new BehaviorEngine({
        config,
        onAction: (action, state) => {
            if (!mainWindow) return;
            console.log(`[main] R141 BEHAVIOR action=${action} state=${state}`);
            mainWindow.webContents.send('set-action', action);
        },
        onMove: (dx, state) => moveWindowBy(dx, 0),
        onState: (from, to, reason) => {
            console.log(`[main] R141 STATE ${from} -> ${to} (${reason})`);
        },
    });
    return engine;
}

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

    // R144 P1: 初始位置先夹进屏幕工作区。
    //   否则"起点在区外"会让第一步行走被边界判定误当成撞边 (表现为开局莫名掉头)。
    try {
        const wa = screen.getDisplayMatching({
            x: winX, y: winY, width: startSize.w, height: startSize.h,
        }).workArea;
        const margin = 4;
        const maxX = Math.max(wa.x + margin, wa.x + wa.width - startSize.w - margin);
        const maxY = Math.max(wa.y + margin, wa.y + wa.height - startSize.h - margin);
        const initX = Math.max(wa.x + margin, Math.min(winX, maxX));
        const initY = Math.max(wa.y + margin, Math.min(winY, maxY));
        if (initX !== winX || initY !== winY) {
            mainWindow.setBounds({ x: initX, y: initY, width: startSize.w, height: startSize.h });
            console.log(`[main] R144 initial position clamped (${winX},${winY}) -> (${initX},${initY}) workArea=(${wa.x},${wa.y},${wa.width},${wa.height})`);
        }
        lastWindowBounds = { x: initX, y: initY, width: startSize.w, height: startSize.h };
    } catch (e) {
        console.error(`[main] R144 initial position clamp failed: ${e?.message}`);
    }

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

        // R144 P0-3: 这里**不再**启动行为引擎。
        //   renderer 仍在异步加载 23 帧, 必须等它上报 assets-ready 且通过
        //   asset_gate 判定后才启动, 否则状态机可能在资源就绪前要求切动作。
        manifestBehaviorConfig_ = data;
        console.log('[main] R144 manifest sent, waiting for renderer assets-ready');

        // R144: 看门狗 — renderer 迟迟不上报资源就绪时明确报错 (不静默等待)
        assetsWatchdog_ = setTimeout(() => {
            if (!assetsReadyHandled_) {
                console.error(`[main] R144 ASSETS_TIMEOUT renderer 20s 内未上报 assets-ready, 自主行为未启动`);
            }
        }, 20000);
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
    // R141 §六 7/§七: 关闭前清理所有定时器
    if (behaviorEngine) {
        behaviorEngine.stop();
        behaviorEngine = null;
        console.log('[main] R141 behavior engine stopped (window-all-closed)');
    }
    if (assetsWatchdog_) { clearTimeout(assetsWatchdog_); assetsWatchdog_ = null; }
    stopDragPolling();
    app.quit();
});

// R141 §六 7: 退出前清理 (before-quit 是最可靠的清理点)
app.on('before-quit', () => {
    if (behaviorEngine) {
        behaviorEngine.stop();
        behaviorEngine = null;
        console.log('[main] R141 behavior engine stopped (before-quit)');
    }
    if (assetsWatchdog_) { clearTimeout(assetsWatchdog_); assetsWatchdog_ = null; }
    stopDragPolling();
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

// ====== R144 P0-3: 资源就绪握手 ======
// renderer 加载完 6 组 23 帧并确认可播放后上报 assets-ready;
// main 通过 asset_gate 判定后才启动自主行为状态机。
// 缺帧 → 明确报错并拒绝启动 (拒绝虚假 PASS); 重复 ready → 忽略。
let assetsReadyHandled_ = false;
let assetsWatchdog_ = null;
let manifestBehaviorConfig_ = null;
let assetsError_ = null;

function startBehaviorEngine() {
    if (behaviorEngine) return false;   // 幂等: 重复 ready 不得重复启动
    const behavior = (manifestBehaviorConfig_ && manifestBehaviorConfig_.behavior) || {};
    const cfg = Object.assign({}, behavior.config || {});
    if (acceptanceMode) {
        // R141 §九: 验收模式只加速状态触发, 不改状态机逻辑 (只缩短时长参数)
        cfg.idle_min_ms = 1200; cfg.idle_max_ms = 2500;
        cfg.sleep_min_ms = 4000; cfg.sleep_max_ms = 7000;
        cfg.walk_min_distance_px = 40; cfg.walk_max_distance_px = 120;
        console.log('[main] R141 ACCEPTANCE_MODE (加速参数, 状态机逻辑不变)');
    }
    if (sleepProbabilityOverride !== null) {
        // R144: 概率覆盖 (只改配置值, 不改状态机逻辑), 让验收脚本可确定性复现
        cfg.sleep_probability = sleepProbabilityOverride;
        console.log(`[main] R144 sleep-probability override=${sleepProbabilityOverride}`);
    }
    behaviorEngine = createBehaviorEngine(cfg);
    // R147: 预览模式下暂停自主决策, 由预览脚本显式驱动场景 (正式运行不受影响)
    if (previewDir_) behaviorEngine.setAutonomousPaused(true);
    behaviorEngine.start();
    console.log(`[main] R144 behavior engine started state=${behaviorEngine.getState()}`);
    return true;
}

ipcMain.on('assets-ready', (_evt, report) => {
    if (assetsReadyHandled_) {
        console.log(`[main] R144 ASSETS_READY_DUPLICATE ignored (loaded=${report && report.loaded})`);
        return;
    }
    assetsReadyHandled_ = true;
    if (assetsWatchdog_) { clearTimeout(assetsWatchdog_); assetsWatchdog_ = null; }
    const verdict = evaluateAssetReadiness(report, REQUIRED_ACTIONS);
    if (!verdict.ok) {
        assetsError_ = report;
        console.error(`[main] R144 ASSETS_ERROR 资源未就绪, 拒绝启动自主行为: ${verdict.errors.join(' | ')}`);
        console.error(`[main] R144 ASSETS_ERROR report=${JSON.stringify(report)}`);
        return;   // 明确报错, 拒绝虚假 PASS
    }
    console.log(`[main] R144 ASSETS_READY loaded=${verdict.loaded}/${verdict.total} actions=${REQUIRED_ACTIONS.join(',')}`);
    startBehaviorEngine();
    // R147: 运行时预览采集 (仅 --preview <dir> 时启用; 不影响正式运行)
    if (previewDir_) {
        setTimeout(() => { runPreviewSequence().catch((e) => console.error('[main] R147 PREVIEW_ERROR', e && e.message)); }, 900);
    }
});

ipcMain.on('action-switch', (_evt, action) => {
    if (mainWindow) {
        mainWindow.webContents.send('set-action', action);
    }
});

// ====== R147: 运行时预览采集 (仅 --preview <dir>) ======
// 采集的是**真实运行**的 Electron 窗口像素 (webContents.capturePage),
// 并同时记录窗口的真实 x 位移 → 用来生成"左右行走 / 点击反馈 / 自然待机"的可观看 GIF。
// 正式运行不受影响 (previewDir_ 为 null 时整段不执行)。
const previewPending_ = new Map();
let previewSeq_ = 0;

ipcMain.on('preview-result', (_evt, payload) => {
    const id = payload && payload.id;
    if (id && previewPending_.has(id)) {
        const resolve = previewPending_.get(id);
        previewPending_.delete(id);
        resolve(payload);
    }
});

function previewCommand(payload, timeoutMs = 4000) {
    return new Promise((resolve) => {
        if (!mainWindow) { resolve({ ok: false, error: 'no window' }); return; }
        const id = ++previewSeq_;
        const timer = setTimeout(() => {
            if (previewPending_.has(id)) { previewPending_.delete(id); resolve({ ok: false, error: 'timeout' }); }
        }, timeoutMs);
        previewPending_.set(id, (res) => { clearTimeout(timer); resolve(res); });
        mainWindow.webContents.send('preview-command', Object.assign({ id }, payload));
    });
}

const sleep_ = (ms) => new Promise((r) => setTimeout(r, ms));

async function captureFrames(scene, count, intervalMs) {
    const dir = previewDir_;
    const x0 = mainWindow.getBounds().x;
    const meta = [];
    for (let i = 0; i < count; i++) {
        const img = await mainWindow.webContents.capturePage();
        const file = path.join(dir, `${scene}_${String(i).padStart(3, '0')}.png`);
        fs.writeFileSync(file, img.toPNG());
        const b = mainWindow.getBounds();
        meta.push({ file, winX: b.x, dx: b.x - x0, winY: b.y });
        await sleep_(intervalMs);
    }
    return meta;
}

async function runPreviewSequence() {
    if (!previewDir_ || !mainWindow) return;
    fs.mkdirSync(previewDir_, { recursive: true });
    console.log(`[main] R147 PREVIEW start dir=${previewDir_}`);
    const summary = {};
    const quiet = async (ms) => {
        // 让引擎保持安静 (不走不睡), 用于待机场景
        if (behaviorEngine) behaviorEngine.holdBriefly(ms || 60000);
        await previewCommand({ cmd: 'action', action: 'idle' });
        await sleep_(400);
    };

    // --- 场景 1: 向左行走 (窗口真的向左移动 + walk_left 动作 + 向左倾斜) ---
    await previewCommand({ cmd: 'action', action: 'idle' });
    await sleep_(300);
    if (behaviorEngine) behaviorEngine.startWalk(-1, 300);
    await sleep_(150);
    summary.walk_left = await captureFrames('walk_left', 32, 65);

    // --- 场景 2: 向右行走 ---
    await previewCommand({ cmd: 'action', action: 'idle' });
    await sleep_(300);
    if (behaviorEngine) behaviorEngine.startWalk(1, 300);
    await sleep_(150);
    summary.walk_right = await captureFrames('walk_right', 32, 65);

    // --- 场景 3: 自然待机 (稳定站姿 + 自然眨眼, 无胸腔膨胀) ---
    await quiet();
    summary.idle = await captureFrames('idle', 90, 70);

    // --- 场景 4: 鼠标单击反馈 (真实 pointer 事件路径) ---
    await quiet();
    const clickRes = await previewCommand({ cmd: 'click' });
    summary.click_result = clickRes;
    console.log(`[main] R147 PREVIEW click result=${JSON.stringify(clickRes)}`);
    summary.click = await captureFrames('click', 26, 45);

    // --- 场景 5: 睡眠点击唤醒 (sleep_loop → wake_up → idle) ---
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sleep_loop' });
    await sleep_(900);
    const wakeRes = await previewCommand({ cmd: 'click' });
    summary.wake_result = wakeRes;
    console.log(`[main] R147 PREVIEW wake result=${JSON.stringify(wakeRes)}`);
    summary.wake = await captureFrames('wake', 34, 60);

    // --- 场景 6 (R148): 撞边转向后的连续动作 ---
    // 把窗口挪到接近左缘 → 向左走 → 必然撞到屏幕左缘 → 引擎自动反向 (edge-turn)
    //   → 全身朝向与步态必须同步切换为 walk_right, 且**连续**不中断。
    // 采集的是真实运行帧, 每帧同时记录窗口真实 x, 便于在 GIF 上直接看出"撞边→反向"。
    await quiet();
    if (mainWindow) {
        const b = mainWindow.getBounds();
        const display = screen.getDisplayMatching(b);
        const margin = (behaviorConfig && behaviorConfig.edge_margin_px) || 4;
        // 离左缘约 100px: 留出自然走向边缘的过程, 撞边后还有余量继续向右
        const targetX = Math.min(display.workArea.x + margin + 100,
            display.workArea.x + display.workArea.width - b.width - margin);
        mainWindow.setBounds({ x: targetX, y: b.y, width: b.width, height: b.height });
        console.log(`[main] R148 PREVIEW edge-turn place x=${targetX} (workArea.x=${display.workArea.x})`);
    }
    await sleep_(250);
    if (behaviorEngine) behaviorEngine.startWalk(-1, 900);
    await sleep_(150);
    summary.edge_turn = await captureFrames('edge_turn', 90, 55);

    // ====== 场景 7 (R153): 动作库巡礼 — 9 个新增动作逐个采集真实运行帧 =====
    // 目的: 让用户能**看到**每个新动作在真实运行时 (200x240 紧凑窗口) 长什么样,
    //       而不是只信一份"动作表"。
    // [动作, 采集帧数, 帧间隔ms, 应用后先等多久再采]
    //   前置等待必须 < 该动作的时长, 否则会错过一次性动作 (例: 眨眼半闭帧只有 ~130ms)
    const LIB_SCENES = [
        ['look_around', 16, 90, 250],
        ['tilt_head', 14, 100, 250],
        ['head_nod', 12, 70, 30],
        ['happy', 10, 90, 60],
        ['blink_soft', 14, 40, 20],
        ['stretch', 12, 110, 250],
        ['sit_rest', 12, 150, 250],
        ['doze', 12, 150, 250],
        ['sleep_breath', 14, 160, 250],
        // R156: 办公待机 (2 帧循环, 每帧 2.8s → 多采一会儿才能看到两帧都出现)
        ['work', 26, 280, 250],
    ];
    for (const [action, count, interval, preDelay] of LIB_SCENES) {
        await quiet();
        const res = await previewCommand({ cmd: 'action', action });
        console.log(`[main] R153 PREVIEW lib action=${action} ok=${res && res.ok}`);
        await sleep_(preDelay);
        summary[`lib_${action}`] = await captureFrames(`lib_${action}`, count, interval);
    }

    // ====== 场景 8 (R153): 坐 → 躺 的交叉溶解过渡 =====
    // 采集 sit_rest → sleep_enter 切换瞬间的帧, 验证"坐下瞬间躺下"已变成溶解过渡。
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sit_rest' });
    await sleep_(500);
    await previewCommand({ cmd: 'action', action: 'sleep_enter' });
    summary.lib_transition = await captureFrames('lib_transition', 18, 40);

    // ====== 场景 9 (R153): 坐 → 打盹 (不躺下) =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sit_rest' });
    await sleep_(400);
    await previewCommand({ cmd: 'action', action: 'doze' });
    summary.lib_sit_to_doze = await captureFrames('lib_sit_to_doze', 16, 90);

    // ====== 场景 10 (R156): 点击互动池 — 6 个动作逐个采集 (每个动作 3 帧全过程) =====
    // 目的: 让用户能**看到**每个点击动作的完整"开始/中间/结束", 而不是只信一份动作表。
    const CLICK_ACTIONS = ['cheer_heart', 'cheer_jump', 'cheer_spin', 'cheer_wink', 'cheer_hands', 'cheer_sway'];
    for (const act of CLICK_ACTIONS) {
        await quiet();
        const res = await previewCommand({ cmd: 'click', action: act });
        console.log(`[main] R156 PREVIEW click-pool action=${act} picked=${res && res.action} ok=${res && res.ok}`);
        summary[`click_${act}`] = await captureFrames(`click_${act}`, 16, 55);
        summary[`click_${act}_result`] = res;
    }

    // ====== 场景 11 (R156): 点击池随机性 — 连点 10 次, 记录每次实际触发的动作 =====
    // 这是"点击时随机触发 + 短时间内不重复"的**真实运行证据** (走的是与用户真机点击完全相同的代码路径)。
    await quiet();
    const randomClicks = [];
    for (let i = 0; i < 10; i++) {
        const r = await previewCommand({ cmd: 'click' });
        randomClicks.push(r && r.action);
        await sleep_(260);
    }
    summary.click_pool_random = randomClicks;
    console.log(`[main] R156 PREVIEW click-pool random sequence = ${randomClicks.join(',')}`);

    // ====== 场景 12 (R156): 睡觉场景 (床 + 月亮夜晚氛围 + 被子) =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sleep_breath' });
    await sleep_(700);
    summary.scene_sleep = await captureFrames('scene_sleep', 18, 160);

    // ====== 场景 13 (R156): 坐下沙发场景 =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sit_rest' });
    await sleep_(500);
    summary.scene_sofa = await captureFrames('scene_sofa', 14, 150);

    // ====== 场景 14 (R156): 办公待机场景 (小桌子 + 笔记本 + 屏幕微光) =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'work' });
    await sleep_(600);
    summary.scene_work = await captureFrames('scene_work', 26, 280);

    // ====== 场景 15 (R156): 道具退出验证 — 从睡觉切回站立, 床与月亮必须一起退出 =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sleep_breath' });
    await sleep_(600);
    await previewCommand({ cmd: 'action', action: 'idle' });
    summary.scene_prop_exit = await captureFrames('scene_prop_exit', 14, 90);

    const metaFile = path.join(previewDir_, 'preview_meta.json');
    fs.writeFileSync(metaFile, JSON.stringify(summary, null, 2));
    console.log(`[main] R147 PREVIEW done meta=${metaFile}`);
    if (quitAfter !== null) {
        setTimeout(() => { try { app.quit(); } catch (e) {} }, 600);
    }
}

// ====== R141: 行为引擎 IPC ======

// renderer 播完一次性动画 (sleep_enter / wake_up) 后回报, 主进程推进状态机
ipcMain.on('animation-finished', (_evt, action) => {
    if (!behaviorEngine) return;
    const ok = behaviorEngine.onAnimationFinished(action);
    console.log(`[main] R141 animation-finished ${action} handled=${ok} state=${behaviorEngine.getState()}`);
});

// 拖拽与自主行为协调 (R141 §四)
ipcMain.on('behavior-drag-state', (_evt, dragging) => {
    // R144 P1: 拖拽打断后清空小数位移累计, 避免拖拽期间的残留位移被继续使用
    if (dragging) { moveRemainder_.x = 0; moveRemainder_.y = 0; }
    if (!behaviorEngine) return;
    behaviorEngine.setDragging(!!dragging);
    console.log(`[main] R141 behavior drag-state=${!!dragging} state=${behaviorEngine.getState()}`);
});

// ====== R147: 鼠标单击角色 ======
// renderer 判定为 CLICK (短按 + 位移 < 3px) 后发来, 带按下之前的动作名。
// 主进程负责: ①结束"按住"态 ②睡眠时走 wake_up 过渡 ③暂缓自主行为计时器,
// 保证点击反馈不会立刻被 walk 覆盖。
ipcMain.on('character-click', (_evt, payload) => {
    if (!behaviorEngine) return;
    const prevAction = (payload && payload.action) || '';
    const holdMs = (payload && typeof payload.holdMs === 'number') ? payload.holdMs : 700;
    const result = behaviorEngine.onUserClick(prevAction, holdMs);
    console.log(`[main] R147 character-click prev=${prevAction} result=${result} state=${behaviorEngine.getState()} hold=${holdMs}ms`);
});

// 行为状态查询 (测试/诊断)
ipcMain.handle('behavior-state', async () => {
    if (!behaviorEngine) return { ok: false, error: 'engine not started' };
    return { ok: true, ...behaviorEngine.snapshot() };
});

// 强制切换行为 (验收脚本用, 不改变状态机内部逻辑)
ipcMain.handle('behavior-force', async (_evt, payload) => {
    if (!behaviorEngine) return { ok: false, error: 'engine not started' };
    const action = payload && payload.action;
    if (!action) return { ok: false, error: 'action required' };
    if (mainWindow) mainWindow.webContents.send('set-action', action);
    console.log(`[main] R141 behavior-force ${action}`);
    return { ok: true, action, state: behaviorEngine.getState() };
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
    // R141 §四: 拖拽期间暂停自主漫游 (与 renderer 的 pointerdown 通知互为双保险)
    if (behaviorEngine) behaviorEngine.setDragging(true);
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
        // R141: 拖拽结束 -> 同步窗口位置缓存 + 恢复自主行为 (带过渡延迟)
        if (final) lastWindowBounds = { x: final.x, y: final.y, width: final.width, height: final.height };
        if (behaviorEngine && behaviorEngine.isDragging()) {
            behaviorEngine.setDragging(false);
        }
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

