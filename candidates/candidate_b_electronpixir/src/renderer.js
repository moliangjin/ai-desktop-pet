// Renderer process — loads manifest frames, plays the current action,
// measures frame stats, emits perf samples to main.
const { ipcRenderer } = require('electron');
const PIXI = require('pixi.js');

const stage = document.getElementById('stage');
const fallback = document.getElementById('fallback');

console.log('[renderer] PIXI version:', PIXI && PIXI.VERSION);

let app_ = null;
let spritesByAction = {};   // { idle: [Texture, ...], walk: [...], ... }
let sprite_ = null;
let currentAction = 'idle';
let frameIdx = 0;
let lastTickAt = performance.now();
let fpsWindowFrames = 0;
let fpsWindowStart = performance.now();
let lastSecondFps = 0;

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
    app_ = new PIXI.Application({
        width: w, height: h,
        backgroundAlpha: 0,
        antialias: false,
        autoDensity: true,
        resolution: 1,
    });
    stage.appendChild(app_.view);
    app_.view.style.background = 'transparent';

    sprite_ = new PIXI.Sprite(spritesByAction[currentAction].frames[0]);
    sprite_.anchor.set(0.5, 0.9);   // matches manifest anchor_normalized
    sprite_.x = w / 2;
    sprite_.y = h;
    app_.stage.addChild(sprite_);

    // Start animation loop.
    let lastAdvanceAt = performance.now();
    app_.ticker.add(() => {
        tick();
        const meta = spritesByAction[currentAction];
        if (!meta || meta.frames.length === 0) return;
        const period = 1000 / (meta.fps || 8);
        if (performance.now() - lastAdvanceAt >= period) {
            frameIdx = (frameIdx + 1) % meta.frames.length;
            sprite_.texture = meta.frames[frameIdx];
            lastAdvanceAt = performance.now();
        }
    });

    fallback.textContent = '[renderer] playing ' + currentAction;
});

ipcRenderer.on('set-action', (_evt, action) => {
    if (spritesByAction[action]) {
        currentAction = action;
        frameIdx = 0;
        fallback.textContent = '[renderer] switched to ' + action;
    }
});
