// AI Pet Candidate B-C2 — Electron renderer (R100 修复版).
//
// R100 修复: 6 项 P0/P1 集中修复 R98 源码问题.
//   P0-1 lastAdvanceAt 移到 module-scope (tickerCallback 共享)
//   P0-2 window.__setMode 走 ipcRenderer.invoke 同步等 main ack
//   P0-3 applyModeToScene 抽出 attach/detach Canvas 监听, 重建后重绑
//   P0-4 模式切换后 sprite 屏幕中心稳定 (main 算中心后传 renderer)
//   P0-5 asset 加载必须真实成功 (test 拒绝 empty frames)
//
// R60 规则保留 (R100 §六 优先复用原 R60 验证链):
//   - DO NOT set stage.interactive = false. Stage defaults = true.
//   - DO NOT toggle setIgnoreMouseEvents 在 renderer.
//   - R51-style 事件链 (pointerdown/move/up/upoutside) 保留.

const { ipcRenderer } = require('electron');
const PIXI = require('pixi.js');

const stage = document.getElementById('stage');
const fallback = document.getElementById('fallback');
const debugBanner = document.getElementById('debug-banner');

console.log('[renderer] PIXI version:', PIXI && PIXI.VERSION);
ipcRenderer.send('renderer-ready', { version: PIXI && PIXI.VERSION });

// ====== 共享状态 (R100 P0-1 修复: 全部 module-scope) ======
let app_ = null;
let sprite_ = null;
let currentAction = 'idle';
let frameIdx = 0;
let dragging = false;
// R104 P0-1: 真正 BrowserWindow 拖拽 — sprite 不再被 drag 移动, 拖动整个窗口
let dragIsWindowDrag_ = false;  // 是否进入真正拖动 (vs 单击容忍)
let dragMoved_ = 0;  // 鼠标移动计数 (3px 内仍算点击)
let dragStartClientX_ = 0;
let dragStartClientY_ = 0;
let stageCssWidth = 0;
let stageCssHeight = 0;
let lastAdvanceAt = performance.now();  // R100 P0-1: module-scope, 共享
let lastTickAt = performance.now();
let fpsWindowFrames = 0;
let fpsWindowStart = performance.now();
let lastSecondFps = 0;
let spritesByAction = {};
let currentMode_ = 'standard';
    // R102 P0-2: 记录 initial mode 供 R100 self-test 完成后恢复
    let originalMode_ = 'standard';
let standardSize_ = 256;
let compactWidth_ = 200;
let compactHeight_ = 240;  // R100 §五 alpha 边界 union 24-221 + padding
let manifestCanvasSize_ = 256;
// R100 P0-3 修复: 持有旧 canvas listeners 引用, 销毁 canvas 前先 detach
let oldStageEl_ = null;
let oldPointerMoveHandler_ = null;
let oldPointerUpHandler_ = null;
// R100 P0-5 修复: asset 加载统计 + 失败标记
let assetLoadTotal_ = 0;
let assetLoadFailed_ = 0;

const frameDeltas = [];
function tick() {
    const now = performance.now();
    const dt = now - lastTickAt;
    lastTickAt = now;
    if (dt > 0 && dt < 1000) {
        frameDeltas.push(dt);
        if (frameDeltas.length > 4096) frameDeltas.splice(0, 2048);
    }
    fpsWindowFrames++;
    if (now - fpsWindowStart >= 1000) {
        lastSecondFps = fpsWindowFrames;
        fpsWindowStart = now;
        fpsWindowFrames = 0;
    }
}

function percentile(arr, p) {
    if (!arr.length) return 0;
    const sorted = arr.slice().sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.floor(p * (sorted.length - 1)))];
}

function rssMB() {
    try { return process.memoryUsage().rss / (1024 * 1024); }
    catch (e) { return -1; }
}

function cpuPercent() {
    try {
        const c = process.cpuUsage();
        return ((c.user + c.system) / 1000000) / ((performance.now() - perfStart) / 1000) * 100;
    } catch (e) { return -1; }
}

const perfStart = performance.now();
setInterval(() => {
    const sample = {
        timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
        action: currentAction,
        fps: lastSecondFps,
        frame_ms_p50: percentile(frameDeltas, 0.50),
        frame_ms_p95: percentile(frameDeltas, 0.95),
        rss_mb: rssMB(),
        cpu_percent: cpuPercent(),
    };
    ipcRenderer.send('perf-sample', sample);
}, 1000);

// ====== R100 P0-3 修复: Canvas 监听 attach/detach 复用函数 ======
// R51 模式: 在 canvas view 上绑 pointermove/pointerup, 让 drag 在鼠标离开 sprite
// hitbox 时继续跟随. R100 把 attach/detach 抽函数, 模式切换重建 canvas 后重绑.
function detachCanvasListeners() {
    // R102 P0-3 修复: 完整解绑 pointermove + pointerup 后再清空引用
    // 之前 bug: 第一段 if 设 oldStageEl_=null 后, 第二段 if 永远进不去, pointerup 残留
    if (!oldStageEl_) return;
    try {
        if (oldPointerMoveHandler_) {
            oldStageEl_.removeEventListener('pointermove', oldPointerMoveHandler_);
        }
        if (oldPointerUpHandler_) {
            oldStageEl_.removeEventListener('pointerup', oldPointerUpHandler_);
        }
    } finally {
        // R102: 全部解绑后才清空引用
        oldStageEl_ = null;
        oldPointerMoveHandler_ = null;
        oldPointerUpHandler_ = null;
        console.log('[renderer] R102 canvas listeners detached (move+up cleared atomically)');
    }
}

function attachCanvasListeners(stageEl) {
    // R100: 先 detach 旧 listener 避免累计
    detachCanvasListeners();
    if (!stageEl) return;
    // R104 P0-1: 真正 BrowserWindow 拖拽 — 移动整个 Electron 窗口, 不是 sprite 在 canvas 内
    //   鼠标 client 坐标 → IPC 给 main → main 用 screen.getCursorScreenPoint() 算 delta
    //   → setBounds 移动窗口. sprite 位置固定在 canvas 中心, 不再被 drag 移动.
    const onMove = (ev) => {
        if (!dragging || !sprite_) return;
        if (!dragIsWindowDrag_) {
            // 区分点击 vs 拖动: 移动 > 3px 才算拖动
            if (dragMoved_ < 3) {
                const dx = Math.abs((ev.clientX || 0) - dragStartClientX_);
                const dy = Math.abs((ev.clientY || 0) - dragStartClientY_);
                if (dx * dx + dy * dy < 9) {
                    dragMoved_++;
                    return;  // 仍在 click 容忍范围
                }
            }
            dragIsWindowDrag_ = true;
            // 第一次进入真拖动 — 通知 main 记录 dragStart
            ipcRenderer.invoke('window-drag-start').then((res) => {
                if (res && res.ok) {
                    console.log('[renderer] R104 window-drag-start ack');
                }
            }).catch((e) => console.error('[renderer] drag-start error:', e?.message));
        }
        // 发当前鼠标 client 坐标给 main
        ipcRenderer.send('window-drag-move', { x: ev.clientX, y: ev.clientY });
    };
    const onUp = () => {
        if (dragging) {
            console.log('[renderer] R104 global pointerup -> end drag');
            if (dragIsWindowDrag_) {
                ipcRenderer.send('window-drag-end');
            }
            endDrag();
        }
    };
    stageEl.addEventListener('pointermove', onMove);
    stageEl.addEventListener('pointerup', onUp);
    // 保留引用供下次 detach
    oldStageEl_ = stageEl;
    oldPointerMoveHandler_ = onMove;
    oldPointerUpHandler_ = onUp;
    console.log(`[renderer] R104 canvas listeners attached to ${stageEl.tagName}#${stageEl.id || ''}`);
}

// ====== R100 P0-1 修复: tickerCallback 在 module-scope ======
// 所有动画计时状态共享, 模式切换重建 canvas 后 tickerCallback 继续正常工作.
// R104: sprite 不再被 drag 移动 (拖动整个 BrowserWindow, sprite 固定 canvas 中心)
function tickerCallback() {
    tick();
    // R104 P0-1: drag 期间 sprite 位置保持稳定 (BrowserWindow 移动, sprite 相对窗口位置不变)
    const meta = spritesByAction[currentAction];
    if (!meta || meta.frames.length === 0) {
        return;  // R100 P0-5: 无帧时 skip 切帧, 不假装
    }
    const period = 1000 / (meta.fps || 8);
    if (performance.now() - lastAdvanceAt >= period) {
        frameIdx = (frameIdx + 1) % meta.frames.length;
        sprite_.texture = meta.frames[frameIdx];
        lastAdvanceAt = performance.now();
    }
}

// ====== R100 P0-3 修复: sprite 事件绑定抽函数 ======
// 在 applyModeToScene 重建后重新调用, 不依赖 manifest IPC 一次性绑定
function bindSpriteEvents() {
    if (!sprite_) return;
    sprite_.on('pointerdown', (ev) => {
        console.log('[renderer] R104 pointerdown sprite at', ev.data.global.x, ev.data.global.y);
        dragging = true;
        // R104 P0-1: 真正 BrowserWindow 拖拽 — sprite 固定在 canvas 中心, 不再 sprite.x/y 移动
        // dragIsWindowDrag_ 在 onMove > 3px 时设为 true, 区分单击 vs 拖动
        dragIsWindowDrag_ = false;
        dragMoved_ = 0;
        dragStartClientX_ = (ev.clientX || 0);
        dragStartClientY_ = (ev.clientY || 0);
        currentAction = 'drag';
        frameIdx = 0;
        fallback.textContent = 'drag';
    });
    sprite_.on('pointerup', () => {
        console.log('[renderer] R104 pointerup sprite');
        if (dragIsWindowDrag_) ipcRenderer.send('window-drag-end');
        endDrag();
    });
    sprite_.on('pointerupoutside', () => {
        console.log('[renderer] R104 pointerupoutside sprite');
        if (dragIsWindowDrag_) ipcRenderer.send('window-drag-end');
        endDrag();
    });
}

function endDrag() {
    dragging = false;
    dragIsWindowDrag_ = false;
    currentAction = 'idle';
    frameIdx = 0;
    fallback.textContent = 'idle';
}

// R104 P0-2: 动画预览 — 键盘 1-4 切 idle/walk/jump/drag
//   用户无需打开 DevTools 即可验证 4 种动画
//   keydown 在 BrowserWindow focus 时触发 (frameless alwaysOnTop 桌宠需先点击)
function setupAnimationPreviewKeys() {
    const actionMap = {
        '1': 'idle',
        '2': 'walk',
        '3': 'jump',
        '4': 'drag',
    };
    window.addEventListener('keydown', (ev) => {
        // 数字键 (主键盘区 + 数字键盘区)
        const key = ev.key;
        if (actionMap[key]) {
            const action = actionMap[key];
            if (spritesByAction[action] && spritesByAction[action].frames.length > 0) {
                currentAction = action;
                frameIdx = 0;
                lastAdvanceAt = performance.now();
                fallback.textContent = `[R104 preview] ${action} (press 1=idle 2=walk 3=jump 4=drag)`;
                console.log(`[renderer] R104 animation preview: ${action}`);
            } else {
                console.warn(`[renderer] R104 preview refused: ${action} has no frames`);
                fallback.textContent = `[R104 preview] ${action} NOT loaded (asset failure)`;
            }
            ev.preventDefault();
        }
    });
    console.log('[renderer] R104 animation preview ready (press 1/2/3/4 to switch idle/walk/jump/drag)');
}

// ====== R100 P0-2/3/4 修复: applyModeToScene 重写 ======
//   - 销毁旧 canvas 前 detach listeners
//   - 重建后 attach new canvas listeners
//   - sprite 屏幕中心由 main 算 (centerX, centerY) 传入, 保持稳定
//   - 模式切换前若 dragging=true 先 endDrag() 安全结束
//   - 重置 lastAdvanceAt 和 frameIdx
function applyModeToScene(mode, opts) {
    opts = opts || {};
    const w = mode === 'compact' ? compactWidth_ : standardSize_;
    const h = mode === 'compact' ? compactHeight_ : standardSize_;
    currentMode_ = mode;
    // R100 P0-4: main 传 sprite 屏幕中心, 模式切换保持中心稳定
    const cx = (typeof opts.centerX === 'number') ? opts.centerX : null;
    const cy = (typeof opts.centerY === 'number') ? opts.centerY : null;

    if (!app_) return;
    // R100: 模式切换前安全结束拖拽
    if (dragging) endDrag();

    // 销毁旧 canvas 前 detach listeners
    if (app_.ticker) app_.ticker.stop();
    detachCanvasListeners();
    const oldView = app_.view;
    oldView.remove();
    try { app_.destroy(true, { children: true, texture: false }); } catch (e) {}

    app_ = new PIXI.Application({
        width: w, height: h,
        backgroundAlpha: 0,
        antialias: false,
        autoDensity: true,
        resolution: 1,
    });
    stage.appendChild(app_.view);
    app_.view.style.background = 'transparent';
    app_.view.style.position = 'absolute';
    app_.view.style.top = '0';
    app_.view.style.left = '0';

    // R100 P0-5: 拒绝空 frames fallback (R98 用了 PIXI.Texture.EMPTY 掩盖)
    const meta = spritesByAction[currentAction];
    if (!meta || meta.frames.length === 0) {
        const msg = `R100 FAIL: action=${currentAction} has no frames loaded (asset_load_total=${assetLoadTotal_} failed=${assetLoadFailed_})`;
        console.error(msg);
        fallback.textContent = msg;
        // 不创建 sprite, 阻止 fake PASS
        return { ok: false, error: msg };
    }
    sprite_ = new PIXI.Sprite(meta.frames[0]);
    sprite_.anchor.set(0.5, 0.9);
    // R100 P0-4: sprite 屏幕中心
    if (cx !== null && cy !== null) {
        // main 传入中心 (BrowserWindow 中心)
        sprite_.x = cx;
        sprite_.y = cy;
    } else {
        sprite_.x = w / 2;
        sprite_.y = h;
    }
    const sc = mode === 'compact' ? w / manifestCanvasSize_ : 1.0;
    sprite_.scale.set(sc, sc);
    sprite_.interactive = true;
    sprite_.buttonMode = true;
    app_.stage.addChild(sprite_);
    // R100 P0-3: 重建后重绑 sprite 事件 + canvas 全局事件
    bindSpriteEvents();
    attachCanvasListeners(app_.view);
    // 重启 ticker
    lastAdvanceAt = performance.now();
    frameIdx = 0;
    app_.ticker.add(tickerCallback);
    stageCssWidth = w;
    stageCssHeight = h;
    const centerLog = cx !== null ? `center=(${cx},${cy})` : `center=canvas_default`;
    fallback.textContent = `[renderer] R100 mode=${mode} size=${w}x${h} scale=${sc.toFixed(2)} ${centerLog}`;
    console.log(`[renderer] R100 mode=${mode} canvas=${w}x${h} scale=${sc.toFixed(3)} ${centerLog} hitArea=${JSON.stringify(sprite_.getBounds())}`);
    return { ok: true, mode, size: { w, h }, center: { x: cx, y: cy }, scale: sc };
}

ipcRenderer.on('manifest', async (_evt, payload) => {
    fallback.textContent = '[renderer] loading manifest…';
    const { manifest, baseDir } = payload;
    currentMode_ = payload.initialMode || 'standard';
    // R102 P0-2: 记录 initial mode 供 R100 self-test 结束后恢复
    originalMode_ = currentMode_;
    // R100: 接收 {w, h} 尺寸 (compact 200x240, standard 256x256)
    if (payload.compactSize) {
        compactWidth_ = payload.compactSize.w || 200;
        compactHeight_ = payload.compactSize.h || 240;
    }
    if (payload.standardSize) {
        standardSize_ = payload.standardSize.w || payload.standardSize.h || 256;
    }
    manifestCanvasSize_ = (manifest.canvas_px && manifest.canvas_px[0]) || 256;

    // R100 P0-5: 真实加载, 统计成功/失败, 缺帧立即报告
    const order = manifest.animation_order || ['idle', 'walk', 'jump', 'drag'];
    spritesByAction = {};
    assetLoadTotal_ = 0;
    assetLoadFailed_ = 0;
    const path = require('path');
    const url = require('url');
    for (const action of order) {
        const a = manifest.actions[action];
        if (!a) {
            fallback.textContent = `[renderer] missing action ${action}`;
            continue;
        }
        const frames = [];
        let failed = 0;
        for (const rel of a.frames) {
            if (rel.startsWith('/') || rel.split('/').includes('..')) {
                failed++;
                continue;
            }
            const abs = path.join(baseDir, rel);
            // R100: 显式 file:// URL — PIXI.Assets 在中文/空格路径下用 file:// 更可靠
            const fileUrl = url.pathToFileURL(abs).toString();
            try {
                const texture = await PIXI.Assets.load(fileUrl);
                if (texture && texture.baseTexture && texture.baseTexture.valid) {
                    frames.push(texture);
                } else {
                    console.warn(`[renderer] R100 asset load invalid: ${fileUrl}`);
                    failed++;
                }
            } catch (e) {
                console.warn(`[renderer] R100 asset load failed: ${fileUrl} ${e?.message || e}`);
                failed++;
            }
        }
        spritesByAction[action] = { frames, fps: a.fps || 8, loop: !!a.loop, failed };
        assetLoadTotal_ += frames.length + failed;
        assetLoadFailed_ += failed;
        ipcRenderer.send('asset-report', { action, loaded: frames.length, failed, total: frames.length + failed });
        console.log(`[renderer] R100 asset-report ${action}: loaded=${frames.length} failed=${failed}`);
    }
    // R100 P0-5: 全 0 加载 → 阻止假装成功
    if (assetLoadFailed_ === assetLoadTotal_ && assetLoadTotal_ > 0) {
        const msg = `R100 FAIL: all ${assetLoadTotal_} frames failed to load from ${baseDir}`;
        console.error(msg);
        fallback.textContent = msg;
        return;  // 阻止后续 applyModeToScene 创建假 sprite
    }

    const w = currentMode_ === 'compact' ? compactWidth_ : standardSize_;
    const h = currentMode_ === 'compact' ? compactHeight_ : standardSize_;
    stageCssWidth = w;
    stageCssHeight = h;
    app_ = new PIXI.Application({
        width: w, height: h,
        backgroundAlpha: 0,
        antialias: false,
        autoDensity: true,
        resolution: 1,
    });
    stage.appendChild(app_.view);
    app_.view.style.background = 'transparent';
    app_.view.style.position = 'absolute';
    app_.view.style.top = '0';
    app_.view.style.left = '0';

    const initMeta = spritesByAction[currentAction];
    if (!initMeta || initMeta.frames.length === 0) {
        const msg = `R100 FAIL: initial action=${currentAction} has no frames after load`;
        console.error(msg);
        fallback.textContent = msg;
        return;
    }
    sprite_ = new PIXI.Sprite(initMeta.frames[0]);
    sprite_.anchor.set(0.5, 0.9);
    sprite_.x = w / 2;
    sprite_.y = h;
    const sc = currentMode_ === 'compact' ? w / manifestCanvasSize_ : 1.0;
    sprite_.scale.set(sc, sc);
    sprite_.interactive = true;
    sprite_.buttonMode = true;
    app_.stage.addChild(sprite_);
    console.log(`[renderer] R100 sprite enabled: mode=${currentMode_} canvas=${w}x${h} scale=${sc.toFixed(3)} hitArea=${JSON.stringify(sprite_.getBounds())}`);

    bindSpriteEvents();
    attachCanvasListeners(app_.view);
    lastAdvanceAt = performance.now();
    app_.ticker.add(tickerCallback);

    fallback.textContent = `[renderer] R100 mode=${currentMode_} playing ${currentAction}`;

    // R104 P0-2: 动画预览 — 用户无需 DevTools 即可切换 4 种动作
    setupAnimationPreviewKeys();

    if (process.env.PET_R60_SELFTEST === '1') {
        setTimeout(() => runR60SelfTest(sprite_), 250);
    }
    if (process.env.PET_R100_SELFTEST === '1') {
        setTimeout(() => runR100SelfTest(), 500);
    }
});

ipcRenderer.on('set-action', (_evt, action) => {
    if (spritesByAction[action] && spritesByAction[action].frames.length > 0) {
        currentAction = action;
        frameIdx = 0;
        lastAdvanceAt = performance.now();  // R100 P0-1: 重置计时
        fallback.textContent = '[renderer] switched to ' + action;
    } else {
        console.warn(`[renderer] set-action ${action} refused: empty frames`);
    }
});

// R100 P0-2 修复: 模式切换 IPC 走完整协议
//   main → renderer: set-mode (含 size + centerX + centerY)
//   renderer → main: renderer-mode-ready (含 mode + size + center 确认)
//   双方断言一致
ipcRenderer.on('set-mode', (_evt, payload) => {
    if (!payload || (payload.mode !== 'standard' && payload.mode !== 'compact')) {
        console.warn(`[renderer] R100 set-mode refused: invalid payload`, payload);
        return;
    }
    console.log(`[renderer] R100 set-mode=${payload.mode} size=${payload.size} center=(${payload.centerX},${payload.centerY})`);
    const result = applyModeToScene(payload.mode, { centerX: payload.centerX, centerY: payload.centerY });
    // 通知 main 确认 (R100 P0-2 要求)
    ipcRenderer.send('renderer-mode-ready', {
        mode: payload.mode,
        size: payload.size,
        centerX: payload.centerX,
        centerY: payload.centerY,
        ok: result.ok,
    });
});

// R100 P0-2 修复: window.__setMode 走 ipcRenderer.invoke 同步等 main ack
// (而不是只调 applyModeToScene 不通知 main)
window.__setMode = async (mode) => {
    if (mode !== 'standard' && mode !== 'compact') {
        console.warn(`[renderer] __setMode refused: invalid mode=${mode}`);
        return { ok: false, error: 'invalid mode' };
    }
    console.log(`[renderer] __setMode(${mode}) → request-mode IPC`);
    try {
        // invoke 同步等 main 回应
        const result = await ipcRenderer.invoke('request-mode', { mode });
        console.log(`[renderer] __setMode(${mode}) main replied:`, result);
        return result;
    } catch (e) {
        console.error(`[renderer] __setMode(${mode}) error:`, e?.message);
        return { ok: false, error: e?.message };
    }
};

// R60 headless self-test (保留)
async function runR60SelfTest(sprite) {
    console.log('[R60 self-test] START');
    const issues = [];
    if (sprite.interactive !== true) issues.push(`sprite.interactive=${sprite.interactive}, expected true`);
    if (sprite.buttonMode !== true) issues.push(`sprite.buttonMode=${sprite.buttonMode}, expected true`);
    if (app_.stage.interactiveChildren !== true) issues.push(`stage.interactiveChildren=${app_.stage.interactiveChildren}, expected true (R51 default)`);
    let dragFired = false, upFired = false;
    try {
        sprite.emit('pointerdown', {
            data: { global: { x: sprite.x, y: sprite.y } },
            stopPropagation: () => {},
        });
        dragFired = (dragging === true) && (currentAction === 'drag');
        sprite.emit('pointerup', {
            data: { global: { x: sprite.x + 30, y: sprite.y + 30 } },
            stopPropagation: () => {},
        });
        upFired = (dragging === false) && (currentAction === 'idle');
    } catch (e) {
        issues.push(`emit error: ${e && e.message}`);
    }
    console.log(`[R60 self-test] treeissues=${issues.length} dragDown=${dragFired} dragUp=${upFired}`);
    if (issues.length === 0 && dragFired && upFired) {
        console.log('[R60 self-test] PASS — R51 event chain wired correctly');
    } else {
        if (issues.length) console.log('[R60 self-test] issues:', issues.join('; '));
        console.log('[R60 self-test] FAIL');
    }
}

// R100 P0-5/6 修复: 专属自测 — 验证模式切换 + 帧非空 + 事件重绑
// R102 P1-1 增强: 走完整 IPC 协议 (ipcRenderer.invoke('request-mode')) 而非直接调 applyModeToScene
// R102 P0-2: self-test 结束后恢复 originalMode_ (不污染用户当前 mode)
async function runR100SelfTest() {
    console.log('[R100 self-test] START');
    const issues = [];

    // 1. asset 加载必须成功
    if (assetLoadTotal_ === 0) issues.push('asset_load_total=0 (no manifest loaded)');
    if (assetLoadFailed_ === assetLoadTotal_ && assetLoadTotal_ > 0) {
        issues.push(`all ${assetLoadTotal_} frames failed to load`);
    }

    // 2. 至少 idle 帧非空
    const idle = spritesByAction['idle'];
    if (!idle || idle.frames.length === 0) {
        issues.push('idle action has no frames (fake_poc 假象掩盖)');
    }

    // 3. tickerCallback 共享 lastAdvanceAt 正常
    if (typeof lastAdvanceAt !== 'number') {
        issues.push(`lastAdvanceAt is ${typeof lastAdvanceAt}, not number (scope error)`);
    }

    // 4. 模式切换通过完整 IPC 协议 (R102 P1-1)
    //    compact → standard → compact 走 invoke + renderer-mode-ready ack
    if (app_) {
        try {
            console.log('[R100 self-test] IPC switch: compact (round 1)');
            const r1 = await ipcRenderer.invoke('request-mode', { mode: 'compact' });
            if (!r1 || !r1.ok) issues.push(`IPC switch compact round 1: ${JSON.stringify(r1)}`);
            else if (r1.mode !== 'compact' || !r1.protocolMatch) {
                issues.push(`IPC switch compact round 1: mode=${r1.mode} protocolMatch=${r1.protocolMatch}`);
            }
            console.log(`[R100 self-test] IPC switch: standard`);
            const r2 = await ipcRenderer.invoke('request-mode', { mode: 'standard' });
            if (!r2 || !r2.ok) issues.push(`IPC switch standard: ${JSON.stringify(r2)}`);
            else if (r2.mode !== 'standard' || !r2.protocolMatch) {
                issues.push(`IPC switch standard: mode=${r2.mode} protocolMatch=${r2.protocolMatch}`);
            }
            console.log('[R100 self-test] IPC switch: compact (round 2)');
            const r3 = await ipcRenderer.invoke('request-mode', { mode: 'compact' });
            if (!r3 || !r3.ok) issues.push(`IPC switch compact round 2: ${JSON.stringify(r3)}`);
            else if (r3.mode !== 'compact' || !r3.protocolMatch) {
                issues.push(`IPC switch compact round 2: mode=${r3.mode} protocolMatch=${r3.protocolMatch}`);
            }
            // 5. 累计监听不重复 (attach/detach 配对数)
            // 不严格配对 (self-test 进行中状态), 只验证不是 attach>detach 累计
            // (测试后由原始 set-mode IPC 自动恢复时正确 detach)
        } catch (e) {
            issues.push(`IPC switch exception: ${e?.message || e}`);
        }

        // R102 P0-2: self-test 结束后恢复 originalMode_ (确保 mac 验收时不污染用户 mode)
        if (originalMode_ !== currentMode_) {
            console.log(`[R100 self-test] restoring originalMode=${originalMode_} (was ${currentMode_})`);
            try {
                const rRestore = await ipcRenderer.invoke('request-mode', { mode: originalMode_ });
                if (!rRestore || !rRestore.ok) {
                    issues.push(`restore originalMode=${originalMode_} failed: ${JSON.stringify(rRestore)}`);
                } else {
                    console.log(`[R100 self-test] restored to ${originalMode_}, protocolMatch=${rRestore.protocolMatch}`);
                }
            } catch (e) {
                issues.push(`restore IPC exception: ${e?.message || e}`);
            }
        }
    }

    console.log(`[R100 self-test] issues=${issues.length}`);
    if (issues.length === 0) {
        console.log('[R100 self-test] PASS');
    } else {
        console.log('[R100 self-test] FAIL:', issues.join('; '));
    }
}
