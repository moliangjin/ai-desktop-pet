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

ipcRenderer.on('manifest', async (_evt, payload) => {
    fallback.textContent = '[renderer] loading manifest…';
    const { manifest, baseDir } = payload;
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

    const w = window.innerWidth || 256;
    const h = window.innerHeight || 256;
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

    // R60: kept R51 proven config verbatim. PIXI v7 defaults for
    // stage.interactive/interactiveChildren drive event propagation.
    sprite_.interactive = true;
    sprite_.buttonMode = true;
    // No sprite.hitArea override: PIXI uses the sprite's natural bounds.
    // No app_.stage.interactive = false; do not touch stage defaults.
    // No app_.stage.interactiveChildren override: defaults are good.
    app_.stage.addChild(sprite_);
    console.log('[renderer] R60 sprite enabled: interactive=', sprite_.interactive,
                ' buttonMode=', sprite_.buttonMode,
                ' hitArea=', sprite_.getBounds());

    // ---- R51 event chain (proven on real Mac) ----
    sprite_.on('pointerdown', (ev) => {
        console.log('[renderer] R60 pointerdown sprite at', ev.data.global.x, ev.data.global.y);
        dragging = true;
        dragOffsetX = sprite_.x - ev.data.global.x;
        dragOffsetY = sprite_.y - ev.data.global.y;
        currentAction = 'drag';
        frameIdx = 0;
        fallback.textContent = 'drag';
    });
    sprite_.on('pointerup', () => {
        console.log('[renderer] R60 pointerup sprite');
        dragging = false;
        currentAction = 'idle';
        frameIdx = 0;
        fallback.textContent = 'idle';
    });
    sprite_.on('pointerupoutside', () => {
        console.log('[renderer] R60 pointerupoutside sprite');
        dragging = false;
        currentAction = 'idle';
        frameIdx = 0;
        fallback.textContent = 'idle';
    });

    let lastAdvanceAt = performance.now();
    app_.ticker.add(() => {
        tick();
        if (dragging && sprite_) {
            // Re-anchor on mouse position. Use PIXI's rootBoundary mouse
            // position which works even when our own stage listeners don't
            // see the move event (canvas-level).
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
    });

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
            console.log('[renderer] R60 global pointerup -> end drag');
            dragging = false;
            currentAction = 'idle';
            frameIdx = 0;
            fallback.textContent = 'idle';
        }
    });

    fallback.textContent = '[renderer] playing ' + currentAction;

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
