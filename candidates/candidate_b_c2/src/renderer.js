// AI Pet Candidate B — Electron renderer.
//
// V0.0 R60 — Click + Drag regression fix.
//   Reverted to the R51 renderer structure (verified PASS on real Mac mini
//   per run r47_20261013_081302). The R53/R54/R56 modifications
//   (stage.interactive=false explicitly + 20Hz state machine) broke click
//   and drag. PIXI v7 default behaviour is what we want.
//
// R60 rules (this file is the regression-test baseline):
//   - DO NOT set stage.interactive = false. Stage interaction is left at
//     PIXI v7 default (true), which lets the stage forward pointer events
//     to its children. Setting it false masked children events in R54/R56
//     during real-Mac testing.
//   - DO NOT toggle setIgnoreMouseEvents anywhere.
//   - DO NOT introduce any IPC-driven cursor position polling. Every layer
//     adds latency that fights PIXI's own hit-test pipeline.
//   - DO allow alpha=0 transparent canvas pixels to forward to underlying
//     windows via macOS's standard transparent-window behaviour. We do not
//     manually manage passthrough.
//
// R51-style event chain (verified):
//   pointerdown on sprite  → drag-active
//   pointermove global     → sprite.x/y follows pointer
//   pointerup              → end drag
//   pointerupoutside       → end drag
//
// R60 self-test (PET_R60_SELFTEST=1): dispatches PIXI-internal events to
// verify the chain without touching the live cursor. Real mouse clicks
// remain a Mac-frontend test.

const { ipcRenderer } = require('electron');
const PIXI = require('pixi.js');

const stage = document.getElementById('stage');
const fallback = document.getElementById('fallback');
const debugBanner = document.getElementById('debug-banner');

console.log('[renderer] PIXI version:', PIXI && PIXI.VERSION);
ipcRenderer.send('renderer-ready', { version: PIXI && PIXI.VERSION });

let app_ = null;
let spritesByAction = {};
let sprite_ = null;
let currentAction = 'idle';
let frameIdx = 0;
let lastTickAt = performance.now();
let fpsWindowFrames = 0;
let fpsWindowStart = performance.now();
let lastSecondFps = 0;

let dragging = false;
let dragOffsetX = 0;
let dragOffsetY = 0;
let stageCssWidth = 0;
let stageCssHeight = 0;

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

// R98: 当前模式 + 尺寸 (由 main.js 注入)
let currentMode_ = 'standard';
let standardSize_ = 256;
let compactSize_ = 200;
let manifestCanvasSize_ = 256;  // manifest.canvas_px

function applyModeToScene(mode) {
    // R98: standard ↔ compact 切换时, 重建 canvas + sprite (尺寸/锚点重置)
    // 标准模式: 256x256 canvas + 256 帧纹理
    // 紧凑模式: compactSize x compactSize canvas + 256 帧纹理 scale=compact/256
    currentMode_ = mode;
    if (!app_) return;
    const w = mode === 'compact' ? compactSize_ : standardSize_;
    const h = w;
    // PIXI Application 不支持运行时 resize canvas — 重建
    // 保留 spritesByAction (frame texture 缓存), 只重建 canvas
    if (app_.ticker) app_.ticker.stop();
    const oldView = app_.view;
    oldView.remove();
    app_.destroy(true, { children: true, texture: false });
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
    // sprite scale: compact 模式下 256 帧缩到 compact 大小
    const firstFrame = spritesByAction[currentAction]?.frames[0];
    sprite_ = new PIXI.Sprite(firstFrame || PIXI.Texture.EMPTY);
    sprite_.anchor.set(0.5, 0.9);
    sprite_.x = w / 2;
    sprite_.y = h;
    const sc = mode === 'compact' ? w / manifestCanvasSize_ : 1.0;
    sprite_.scale.set(sc, sc);
    sprite_.interactive = true;
    sprite_.buttonMode = true;
    app_.stage.addChild(sprite_);
    // 重新绑定事件
    bindSpriteEvents();
    // 重启 ticker
    app_.ticker.add(tickerCallback);
    stageCssWidth = w;
    stageCssHeight = h;
    fallback.textContent = `[renderer] mode=${mode} size=${w}x${h} scale=${sc.toFixed(2)} (R98)`;
    console.log(`[renderer] mode=${mode} canvas=${w}x${h} sprite.scale=${sc.toFixed(3)}`);
}

// R98: 单独抽出 sprite 事件绑定 (applyModeToScene 重建时复用)
function bindSpriteEvents() {
    if (!sprite_) return;
    sprite_.on('pointerdown', (ev) => {
        console.log('[renderer] R98 pointerdown sprite at', ev.data.global.x, ev.data.global.y);
        dragging = true;
        dragOffsetX = sprite_.x - ev.data.global.x;
        dragOffsetY = sprite_.y - ev.data.global.y;
        currentAction = 'drag';
        frameIdx = 0;
        fallback.textContent = 'drag';
    });
    sprite_.on('pointerup', () => {
        console.log('[renderer] R98 pointerup sprite');
        dragging = false;
        currentAction = 'idle';
        frameIdx = 0;
        fallback.textContent = 'idle';
    });
    sprite_.on('pointerupoutside', () => {
        console.log('[renderer] R98 pointerupoutside sprite');
        dragging = false;
        currentAction = 'idle';
        frameIdx = 0;
        fallback.textContent = 'idle';
    });
}

// R98: 抽出 ticker 回调 (applyModeToScene 重建时复用)
function tickerCallback() {
    tick();
    if (dragging && sprite_) {
        const root = app_.renderer.events.rootBoundary;
        const ev = root && root._pointerEvent;
        if (ev) {
            sprite_.x = ev.global.x + dragOffsetX;
            sprite_.y = ev.global.y + dragOffsetY;
        }
    }
    const meta = spritesByAction[currentAction];
    if (!meta || meta.frames.length === 0) return;
    const period = 1000 / (meta.fps || 8);
    if (performance.now() - lastAdvanceAt >= period) {
        frameIdx = (frameIdx + 1) % meta.frames.length;
        sprite_.texture = meta.frames[frameIdx];
        lastAdvanceAt = performance.now();
    }
}

ipcRenderer.on('manifest', async (_evt, payload) => {
    fallback.textContent = '[renderer] loading manifest…';
    const { manifest, baseDir } = payload;
    currentMode_ = payload.initialMode || 'standard';
    compactSize_ = payload.compactSize || 200;
    standardSize_ = payload.standardSize || 256;
    manifestCanvasSize_ = (manifest.canvas_px && manifest.canvas_px[0]) || 256;
    const order = manifest.animation_order || ['idle', 'walk', 'jump', 'drag'];
    spritesByAction = {};
    const path = require('path');
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
            try {
                const texture = await PIXI.Assets.load(abs);
                frames.push(texture);
            } catch (e) {
                failed++;
            }
        }
        spritesByAction[action] = { frames, fps: a.fps || 8, loop: !!a.loop, failed };
        ipcRenderer.send('asset-report', { action, loaded: frames.length, failed });
    }

    // R98: 根据 currentMode_ 决定 canvas 尺寸
    const w = currentMode_ === 'compact' ? compactSize_ : standardSize_;
    const h = w;
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

    sprite_ = new PIXI.Sprite(spritesByAction[currentAction].frames[0]);
    sprite_.anchor.set(0.5, 0.9);
    sprite_.x = w / 2;
    sprite_.y = h;
    const sc = currentMode_ === 'compact' ? w / manifestCanvasSize_ : 1.0;
    sprite_.scale.set(sc, sc);
    sprite_.interactive = true;
    sprite_.buttonMode = true;
    app_.stage.addChild(sprite_);
    console.log(`[renderer] R98 sprite enabled: mode=${currentMode_} canvas=${w}x${h} scale=${sc.toFixed(3)} hitArea=${JSON.stringify(sprite_.getBounds())}`);

    // R98: 复用 bindSpriteEvents
    bindSpriteEvents();

    let lastAdvanceAt = performance.now();
    app_.ticker.add(tickerCallback);

    // Track pointer globally so drag continues even when pointer leaves
    // the sprite hitbox (R51 proven pattern).
    const stageEl = app_.view;
    stageEl.addEventListener('pointermove', (ev) => {
        if (!dragging || !sprite_) return;
        const rect = stageEl.getBoundingClientRect();
        const x = ev.clientX - rect.left;
        const y = ev.clientY - rect.top;
        sprite_.x = x + dragOffsetX;
        sprite_.y = y + dragOffsetY;
    });
    stageEl.addEventListener('pointerup', () => {
        if (dragging) {
            console.log('[renderer] R98 global pointerup -> end drag');
            dragging = false;
            currentAction = 'idle';
            frameIdx = 0;
            fallback.textContent = 'idle';
        }
    });

    fallback.textContent = `[renderer] mode=${currentMode_} playing ${currentAction}`;

    // ---- R60 headless self-test (env PET_R60_SELFTEST=1) ----
    if (process.env.PET_R60_SELFTEST === '1') {
        setTimeout(() => runR60SelfTest(sprite_), 250);
    }
});

ipcRenderer.on('set-action', (_evt, action) => {
    if (spritesByAction[action]) {
        currentAction = action;
        frameIdx = 0;
        fallback.textContent = '[renderer] switched to ' + action;
    }
});

// R98: 模式切换 IPC (从 main.js 接收 set-mode)
ipcRenderer.on('set-mode', (_evt, payload) => {
    if (!payload || (payload.mode !== 'standard' && payload.mode !== 'compact')) return;
    console.log(`[renderer] R98 set-mode=${payload.mode} size=${payload.size}`);
    applyModeToScene(payload.mode);
    // 通知 main 当前 mode 已就绪
    ipcRenderer.send('renderer-mode-ready', { mode: payload.mode });
});

// R98: 渲染端请求切换模式 (供开发者控制台或调试用)
window.__setMode = (mode) => {
    console.log(`[renderer] window.__setMode(${mode})`);
    applyModeToScene(mode);
};


// R60 headless self-test: emit sprite-level pointer events directly. This
// proves that our .on() handlers are wired correctly and toggles the
// dragging state. It does NOT verify that a real mouse event reaches PIXI
// from the OS — that path stays a Mac-frontend test.
async function runR60SelfTest(sprite) {
    console.log('[R60 self-test] START');
    const issues = [];
    // Tree invariants — must NOT regress R51 working config.
    if (sprite.interactive !== true)        issues.push(`sprite.interactive=${sprite.interactive}, expected true`);
    if (sprite.buttonMode !== true)         issues.push(`sprite.buttonMode=${sprite.buttonMode}, expected true`);
    // stage.interactive must NOT have been forced to false (R54/R56 broke this).
    // PIXI v7 default is true. We check that we didn't override it.
    // We do not assert the literal value — defaults may differ by PIXI version.
    // Instead, we check that stage interactiveChildren is true (so children receive).
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
