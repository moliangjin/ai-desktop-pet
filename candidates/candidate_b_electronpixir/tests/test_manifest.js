#!/usr/bin/env node
// T09: Resource interface test for candidate B.
// Swap manifest action frames without engine change; verify swap loads.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = '/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0';
const SRC = path.join(ROOT, 'assets/prototype_chibi');
const EXT = path.join(ROOT, 'candidates/candidate_b_electronpixir');
const LOG = path.join(ROOT, 'evidence/build_logs/candidate_b_t09.log');
const PERF = path.join(ROOT, 'evidence/perf_samples/candidate_b_t09.csv');
const TMP = path.join(SRC, 'manifest_t09_test.json');

const manifest = JSON.parse(fs.readFileSync(path.join(SRC, 'manifest.json'), 'utf8'));
// swap: idle now points at walk's frames; walk points at idle's
manifest.actions.idle.frames = [
    'animations/walk/000.png',
    'animations/walk/002.png',
    'animations/walk/004.png',
    'animations/walk/006.png',
];
manifest.actions.walk.frames = [
    'animations/idle/000.png',
    'animations/idle/001.png',
    'animations/idle/002.png',
    'animations/idle/003.png',
    'animations/idle/004.png',
    'animations/idle/005.png',
];
manifest.actions.idle.fps = 6;
manifest.actions.walk.fps = 8;
fs.writeFileSync(TMP, JSON.stringify(manifest, null, 2));

const r = spawnSync('./node_modules/.bin/electron', [
    'src/main.js',
    '--manifest', TMP,
    '--size', '256',
    '--x', '600', '--y', '600',
    '--perf-out', PERF,
    '--quit-after', '5',
], {
    cwd: EXT,
    env: { ...process.env, ELECTRON_ENABLE_LOGGING: '1' },
    stdio: ['ignore', fs.openSync(LOG, 'w'), fs.openSync(LOG, 'a')],
});

fs.unlinkSync(TMP);

const logText = fs.readFileSync(LOG, 'utf8');
// Renderer logs action=idle/4, action=walk/6 etc.
const idleOk = /asset-report: idle loaded=4/.test(logText);
const walkOk = /asset-report: walk loaded=6/.test(logText);
if (idleOk && walkOk) {
    console.log('[T09] PASS — engine loaded swapped frame lists without code change.');
    console.log('       evidence:', LOG);
    process.exit(0);
}
console.log('[T09] FAIL — manifest swap did not load expected frame counts.');
console.log('       idle=' + idleOk + ' walk=' + walkOk);
console.log('       evidence:', LOG);
process.exit(1);
