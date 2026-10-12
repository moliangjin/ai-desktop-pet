#!/usr/bin/env node
// T08: 20× clean start/stop loop for candidate B.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = '/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0';
const EXT = path.join(ROOT, 'candidates/candidate_b_electronpixir');
const LOG_DIR = path.join(ROOT, 'evidence/build_logs/loop_b');
fs.mkdirSync(LOG_DIR, { recursive: true });

let pass = 0, fail = 0;
for (let i = 1; i <= 20; i++) {
    const log = path.join(LOG_DIR, `iter_${String(i).padStart(2,'0')}.log`);
    const r = spawnSync('./node_modules/.bin/electron', [
        'src/main.js',
        '--manifest', path.join(ROOT, 'assets/prototype_chibi/manifest.json'),
        '--size', '256', '--x', '600', '--y', '600',
        '--perf-out', path.join(ROOT, `evidence/perf_samples/loop_b_${i}.csv`),
        '--quit-after', '1',
    ], { cwd: EXT });
    fs.writeFileSync(log, (r.stdout || '') + (r.stderr || ''));
    if (r.status === 0) pass++;
    else fail++;
}

const zombies = require('child_process').execSync('pgrep -f "Electron.*candidate_b" 2>/dev/null | wc -l', { encoding: 'utf8' }).trim();

console.log(`[T08 loop] pass=${pass} fail=${fail} zombies=${zombies}`);
if (fail === 0 && zombies === '0') {
    console.log('[T08] PASS — 20/20 clean exits, no zombie processes.');
    process.exit(0);
}
console.log('[T08] FAIL');
process.exit(1);
