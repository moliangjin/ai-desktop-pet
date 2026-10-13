// R60 INDEPENDENT passthrough proof-of-concept.
//
// Task book §五:
//   "本轮只需交付穿透可行性结论或最小原型,不允许直接把未经验证的新
//    穿透方案重新合入已恢复的稳定版本。"
//
// This is a STANDALONE Electron BrowserWindow pair (NOT the candidate B
// pet). It loads plain HTML files (no PIXI) and checks whether, on
// macOS 14 + Electron 33, alpha=0 clicks from an alwaysOnTop transparent
// BrowserWindow forward onto an underlying non-transparent BrowserWindow.
//
// USAGE:
//   ./node_modules/.bin/electron tools/passthrough_poc/main.js
//
// VERDICT criteria:
//   - click on gold ball centre (sprite area):     front counts sprite +1
//   - click on transparent corner area:             underlay counts underlay +1
//   PASS only if BOTH counters increment.

const { app, BrowserWindow } = require('electron');
const path = require('path');

const HERE = __dirname;

let probeWindow = null;
let passthroughWindow = null;

function createProbeWindow() {
    probeWindow = new BrowserWindow({
        x: 200, y: 300,
        width: 360, height: 180,
        frame: true,
        transparent: false,
        alwaysOnTop: false,
        title: 'PROBE — underlay',
        webPreferences: { nodeIntegration: true },
    });
    probeWindow.loadFile(path.join(HERE, 'probe.html'));
}

function createPassthroughWindow() {
    passthroughWindow = new BrowserWindow({
        x: 350, y: 200,
        width: 256, height: 256,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        hasShadow: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        resizable: false,
        webPreferences: { nodeIntegration: true, contextIsolation: false },
    });
    passthroughWindow.setOpacity(0.999);
    passthroughWindow.loadFile(path.join(HERE, 'index.html'));
    // NEVER call setIgnoreMouseEvents — let macOS standard transparent-window
    // forwarding decide.
    passthroughWindow.setIgnoreMouseEvents(false);
}

app.whenReady().then(() => {
    console.log('[PoC] creating probe (underlay, alwaysOnTop=false)');
    createProbeWindow();
    setTimeout(() => {
        console.log('[PoC] creating passthrough (alwaysOnTop=true, transparent)');
        createPassthroughWindow();
        setTimeout(() => {
            const probeBounds = probeWindow.getBounds();
            const passtBounds = passthroughWindow.getBounds();
            console.log('[PoC] probe bounds:', JSON.stringify(probeBounds));
            console.log('[PoC] passt bounds:', JSON.stringify(passtBounds));
            const overlap = !(
                probeBounds.x + probeBounds.width  < passtBounds.x ||
                probeBounds.x > passtBounds.x + passtBounds.width  ||
                probeBounds.y + probeBounds.height < passtBounds.y ||
                probeBounds.y > passtBounds.y + passtBounds.height
            );
            console.log('[PoC] geometry_overlap=' + overlap);
            console.log('[PoC] READY for user manual click test');
            console.log('[PoC] user: click gold ball centre, then click corner');
            console.log('[PoC] watch titles: probe=click count, front=sprite/transparent count');
            setTimeout(() => {
                console.log('[PoC] terminating after 30s');
                app.quit();
            }, 30000);
        }, 1000);
    }, 200);
});

app.on('window-all-closed', () => app.quit());
