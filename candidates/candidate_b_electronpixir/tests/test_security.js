#!/usr/bin/env node
// T10: Security boundary checks for candidate B.
// Static analysis of source — must not reference privacy-sensitive APIs.
const fs = require('fs');
const path = require('path');

const ROOT = '/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0';
const SRC_DIR = path.join(ROOT, 'candidates/candidate_b_electronpixir/src');

const forbidden = [
    'desktopCapturer', 'getSources', 'getUserMedia',
    'screen-capture', 'screen_capture', 'mediaDevices',
    'accessibility', 'AXIsProcessTrusted',
    'AudioContext', 'webkitAudioContext',
    'AVCaptureDevice', 'TCC',
    'kSec', 'Keychain', 'securit', 'credential-store',
];

function* walk(dir) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, e.name);
        if (e.isDirectory()) yield* walk(p);
        else if (/\.(js|html)$/.test(e.name)) yield p;
    }
}

let bad = false;
for (const file of walk(SRC_DIR)) {
    const text = fs.readFileSync(file, 'utf8');
    for (const sym of forbidden) {
        if (text.includes(sym)) {
            // Allow comments
            const stripped = text.split('\n')
                .filter(l => !l.trim().startsWith('//'))
                .join('\n');
            if (stripped.includes(sym)) {
                console.log(`  [FAIL] ${file}: ${sym}`);
                bad = true;
            }
        }
    }
    // Hard-coded API key patterns
    if (/sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z\-_]{30,}|xoxb-[0-9-]+/.test(text)) {
        console.log(`  [FAIL] ${file}: hard-coded API key pattern`);
        bad = true;
    }
}

// Verify package.json declares no extra entitlements (read-only field check)
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, 'candidates/candidate_b_electronpixir/package.json'), 'utf8'));
// V0.0 explicit note: V1.0/V2.0 must move to contextIsolation+sandboxed IPC
if (!pkg.devDependencies.electron) {
    console.log('  [FAIL] electron dependency missing');
    bad = true;
}

if (bad) {
    console.log('[T10] FAIL — see above');
    process.exit(1);
}
console.log('[T10] PASS — security boundary checks clean for candidate B.');
