// Renderer process — loads manifest frames, plays the current action,
// measures frame stats, emits perf samples to main.
const { ipcRenderer } = require('electron');
const PIXI = require('pixi.js');

const stage = document.getElementById('stage');
const fallback = document.getElementById('fallback');
const debugBanner = document.getElementById('debug-banner');

console.log('[renderer] PIXI version:', PIXI && PIXI.VERSION);
ipcRenderer.send('renderer-ready', { version: PIXI && PIXI.VERSION });

let app_ = null;
let spritesByAction = {};   // { idle: [Texture, ...], walk: [...], ... }
let sprite_ = null;
let currentAction = 'idle';
let frameIdx = 0;
let lastTickAt = performance.now();
let fpsWindowFrames = 0;
let fpsWindowStart = performance.now();
let lastSecondFps = 0;

// Drag state
let dragging = false;
let dragOffsetX = 0;   // sprite-local offset between sprite anchor and pointer at drag start
let dragOffsetY = 0;
let stageCssWidth = 0;
let stageCssHeight = 0;

const frameDeltas = []; // ms
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
        console.log('[renderer] fps window: ' + lastSecondFps);
    }
}

function percentile(arr, p) {
    if (!arr.length) return 0;
    const sorted = arr.slice().sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.floor(p * (sorted.length - 1)))];
}

function rssMB() {
    // Approximate: process.memoryUsage returns rss in bytes.
    try {
        return process.memoryUsage().rss / (1024 * 1024);
    } catch (e) {
        return -1;
    }
}

function cpuPercent() {
    try {
        const c = process.cpuUsage();
        return ((c.user + c.system) / 1000000) / ((performance.now() - perfStart) / 1000) * 100;
    } catch (e) {
        return -1;
    }
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

    // Lazy load frames per action. Use path module from main to join paths
    // would be cleaner, but renderer has nodeIntegration on, so we can.
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
            // Reject absolute paths and ".." segments (PRD §4 FR-E.2 security).
            if (rel.startsWith('/') || rel.split('/').includes('..')) {
                failed++;
                continue;
            }
            const abs = path.join(baseDir, rel);
            try {
                // Use PIXI.Assets or loadAsync; PIXI v8 uses Assets
                const texture = await PIXI.Assets.load(abs);
                frames.push(texture);
            } catch (e) {
                failed++;
            }
        }
        spritesByAction[action] = { frames, fps: a.fps || 8, loop: !!a.loop, failed };
        const msg = `[renderer] action ${action}: ${frames.length} loaded, ${failed} failed`;
        fallback.textContent = msg;
        console.log(msg);
        ipcRenderer.send('asset-report', { action, loaded: frames.length, failed });
    }

    // Initialise PIXI Application (transparent background, sized to window).
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
    sprite_.anchor.set(0.5, 0.9);   // matches manifest anchor_normalized
    sprite_.x = w / 2;
    sprite_.y = h;
    // V0.0 R38 fix: enable PIXI event listening on the sprite
    sprite_.interactive = true;
    sprite_.buttonMode = true;
    app_.stage.addChild(sprite_);
    console.log('[renderer] sprite enabled: interactive=', sprite_.interactive,
                'buttonMode=', sprite_.buttonMode,
                'hitArea=', sprite_.getBounds());

    // Drag-to-move: track the offset between pointer and sprite anchor at mousedown,
    // then move the sprite by the pointer delta each frame.
    sprite_.on('pointerdown', (ev) => {
        console.log('[renderer] pointerdown sprite at', ev.data.global.x, ev.data.global.y);
        dragging = true;
        dragOffsetX = sprite_.x - ev.data.global.x;
        dragOffsetY = sprite_.y - ev.data.global.y;
        currentAction = 'drag';
        frameIdx = 0;
        fallback.textContent = 'drag';
    });
    sprite_.on('pointerup', () => {
        console.log('[renderer] pointerup sprite');
        dragging = false;
        currentAction = 'idle';
        frameIdx = 0;
        fallback.textContent = 'idle';
    });
    sprite_.on('pointerupoutside', () => {
        console.log('[renderer] pointerupoutside sprite');
        dragging = false;
        currentAction = 'idle';
        frameIdx = 0;
        fallback.textContent = 'idle';
    });

    // Start animation loop.
    let lastAdvanceAt = performance.now();
    app_.ticker.add(() => {
        tick();
        if (dragging && sprite_) {
            // Re-anchor on mouse position. We use app_.renderer.events.rootBoundary
            // mouse position which is the most reliable way to get global pointer
            // coords without depending on an event firing.
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

    // Track pointer globally so drag continues even when pointer leaves the sprite hitbox.
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
            console.log('[renderer] global pointerup -> end drag');
            dragging = false;
            currentAction = 'idle';
            frameIdx = 0;
            fallback.textContent = 'idle';
        }
    });

    fallback.textContent = '[renderer] playing ' + currentAction;
    if (debugBanner) debugBanner.textContent = 'PIXI ' + (PIXI && PIXI.VERSION) + ' ready · ' + w + 'x' + h;
});

ipcRenderer.on('set-action', (_evt, action) => {
    if (spritesByAction[action]) {
        currentAction = action;
        frameIdx = 0;
        fallback.textContent = '[renderer] switched to ' + action;
    }
});

// ============================================================================
// V0.0 R39: Transparent-area passthrough — real hit-test based.
// ============================================================================
//
// The BrowserWindow is frameless+transparent so the user can see through
// transparent pixels to the desktop. But by default a BrowserWindow eats
// every click inside its bounds, so the user cannot click anything underneath.
//
// The fix is `mainWindow.setIgnoreMouseEvents(true, { forward: true })`.
// We flip that flag from a 5 Hz loop that asks PIXI whether the cursor is
// over the visible sprite hitbox or over transparent canvas pixels.
//
// Why 5 Hz and not 60 Hz: faster loops were tried in R37 and they raced
// with PIXI's pointerdown delivery — clicks were lost. 5 Hz is fast enough
// that a user resting the cursor on a transparent pixel starts passing
// clicks through within ~200 ms, but slow enough that it never competes
// with a click that the user is in the middle of pressing.
let lastCursorX = -1;
let lastCursorY = -1;
let cursorInsideSprite = false;
let lastPassthrough = null;

function spriteHitboxContains(globalX, globalY) {
    if (!sprite_) return false;
    // Use PIXI's getBounds() — expressed in stage (canvas) coordinates.
    const b = sprite_.getBounds();
    return globalX >= b.x && globalX <= b.x + b.width &&
           globalY >= b.y && globalY <= b.y + b.height;
}

setInterval(() => {
    if (!app_ || !sprite_ || dragging) {
        // While the user is actively dragging, always accept events.
        if (lastPassthrough !== false) {
            lastPassthrough = false;
            ipcRenderer.send('set-passthrough', false);
        }
        return;
    }
    // Compare against the most recent cursor coords captured by listener.
    const inside = (lastCursorX >= 0) && spriteHitboxContains(lastCursorX, lastCursorY);
    if (inside === cursorInsideSprite) return;
    cursorInsideSprite = inside;
    ipcRenderer.send('set-passthrough', !inside);
}, 1000 / 5);  // 5 Hz

document.addEventListener('mousemove', (ev) => {
    const rect = app_.view.getBoundingClientRect();
    lastCursorX = ev.clientX - rect.left;
    lastCursorY = ev.clientY - rect.top;
});
document.addEventListener('pointermove', (ev) => {
    const rect = app_.view.getBoundingClientRect();
    lastCursorX = ev.clientX - rect.left;
    lastCursorY = ev.clientY - rect.top;
});
