// R144 渲染边界回归测试
//
// R144 P0-1 要求:
//   "每一帧按实际 PixiJS 变换矩阵核算可见像素边界"
//   "在正式生产渲染参数下验证全部 23 帧, 而非使用另一套预览缩放算法"
//   "不通过逐帧随意改变人物大小来规避裁切"
//
// 本测试:
//   1) 用纯 Node PNG 解码器**直接读取 23 张真实 PNG**, 测量非透明像素范围
//   2) 与运行时 manifest 里记录的 bbox 逐帧比对 (防止元数据与素材脱节)
//   3) 调用**生产布局模块** src/sprite_layout.js (renderer 用的是同一份代码)
//      在 compact 200x240 与 standard 256x256 下核算 23 帧可见边界
//   4) 验证全部帧共用同一缩放倍率 (没有逐帧改大小)
//   5) 验证全部帧内容底边落在同一条地面接触线 (脚底/地面接触点稳定)
//   6) 用遗留算法做对照, 证明 R141 的算法确实会裁切 (修复是有效的, 不是空改)

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { decodeRGBA, alphaBbox } = require('./lib/png_reader.js');

const CAND = path.join(__dirname, '..');
const MANIFEST_PATH = path.join(CAND, 'assets', 'character_R141_manifest.json');
const MANIFEST = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
const ASSET_BASE = path.dirname(MANIFEST_PATH);

// ★ 生产布局模块 (renderer.js require 的就是这一个)
const {
    computeLayout, contentRectToScreen, isRectInsideCanvas, legacyLayout,
} = require(path.join(CAND, 'src', 'sprite_layout.js'));

const MODES = [['compact', 200, 240], ['standard', 256, 256]];
const TEXTURE = MANIFEST.canvas_px[0];

const results = [];
function test(name, fn) {
    try {
        fn();
        results.push({ name, pass: true });
        console.log(`  ✅ ${name}`);
    } catch (e) {
        results.push({ name, pass: false, error: e.message });
        console.log(`  ❌ ${name}\n      ${e.message}`);
    }
}

// ====== 真实素材测量 ======
const measured = {};   // action -> [bbox]
const frameFiles = []; // {action, index, file}
for (const action of MANIFEST.animation_order) {
    const info = MANIFEST.actions[action];
    measured[action] = [];
    info.frames.forEach((rel, i) => {
        const abs = path.join(ASSET_BASE, rel);
        frameFiles.push({ action, index: i, rel, abs });
        const img = decodeRGBA(abs);
        const bb = alphaBbox(img);
        measured[action].push(bb);
    });
}
const TOTAL_FRAMES = frameFiles.length;
console.log(`  (已解码 ${TOTAL_FRAMES} 张真实 PNG, ${TEXTURE}x${TEXTURE} RGBA)`);

// ====== 布局输入 (与 renderer 的 buildLayoutFor 完全同构) ======
function layoutInput() {
    const frames = [];
    for (const action of MANIFEST.animation_order) {
        const info = MANIFEST.actions[action];
        for (let i = 0; i < info.frames.length; i++) {
            frames.push({ action, index: i, bbox: measured[action][i] });
        }
    }
    return frames;
}
const FRAMES = layoutInput();

function layoutFor(w, h) {
    return computeLayout({
        canvasW: w, canvasH: h,
        textureW: TEXTURE, textureH: TEXTURE,
        frames: FRAMES,
        margin: MANIFEST.layout && MANIFEST.layout.margin_px,
    });
}

// ====== 测试 1: 23 帧素材路径全部真实有效 ======
test('T1 manifest 23 帧资源路径全部真实存在且可解码', () => {
    assert.strictEqual(TOTAL_FRAMES, 23, `帧数应为 23, 实际 ${TOTAL_FRAMES}`);
    assert.strictEqual(MANIFEST.animation_order.length, 6, '动作组数应为 6');
    for (const f of frameFiles) {
        assert.ok(fs.existsSync(f.abs), `文件不存在: ${f.rel}`);
        assert.ok(measured[f.action][f.index], `${f.rel} 全透明 (无有效像素)`);
    }
});

// ====== 测试 2: manifest 记录的 bbox 与真实 PNG 完全一致 ======
test('T2 manifest layout 记录的 bbox 与真实 PNG 逐帧一致 (元数据未脱节)', () => {
    const recorded = MANIFEST.layout && MANIFEST.layout.frame_bboxes;
    assert.ok(recorded, 'manifest 缺少 layout.frame_bboxes');
    for (const action of MANIFEST.animation_order) {
        assert.ok(recorded[action], `manifest 缺少动作 ${action} 的 bbox`);
        assert.strictEqual(recorded[action].length, measured[action].length,
            `动作 ${action} 的 bbox 数量与帧数不符`);
        for (let i = 0; i < measured[action].length; i++) {
            assert.deepStrictEqual(recorded[action][i], measured[action][i],
                `动作 ${action} 第 ${i} 帧 bbox 不一致`);
        }
    }
});

// ====== 测试 3/4: 两种画布尺寸下 23 帧完整显示 ======
for (const [mode, w, h] of MODES) {
    test(`T${mode === 'compact' ? 3 : 4} ${mode} ${w}x${h} 下 23 帧全部完整显示 (零裁切)`, () => {
        const layout = layoutFor(w, h);
        let checked = 0;
        for (const f of FRAMES) {
            const rect = layout.rectsByAction[f.action][f.index];
            const scr = contentRectToScreen(rect, layout);
            assert.ok(isRectInsideCanvas(scr, layout),
                `${mode}/${f.action}[${f.index}] 越界: screen=(${scr.left.toFixed(2)},${scr.top.toFixed(2)})-(${scr.right.toFixed(2)},${scr.bottom.toFixed(2)}) canvas=${w}x${h}`);
            checked++;
        }
        assert.strictEqual(checked, 23, `核算帧数应为 23, 实际 ${checked}`);
    });
}

// ====== 测试 5: 全部帧共用同一缩放倍率 (禁止逐帧改大小) ======
test('T5 全部 23 帧共用同一缩放倍率 (未逐帧改人物大小)', () => {
    for (const [mode, w, h] of MODES) {
        const layout = layoutFor(w, h);
        const scales = new Set();
        for (const f of FRAMES) {
            const rect = layout.rectsByAction[f.action][f.index];
            const scr = contentRectToScreen(rect, layout);
            scales.add(Math.round((scr.right - scr.left) / (rect.right - rect.left) * 1e6));
        }
        assert.strictEqual(scales.size, 1, `${mode} 出现多种缩放倍率 (逐帧改大小): ${[...scales].join(',')}`);
    }
});

// ====== 测试 6: 地面接触线稳定 (脚底/地面接触点不跳动) ======
test('T6 全部 23 帧内容底边落在同一条地面接触线 (姿态切换不跳动)', () => {
    for (const [mode, w, h] of MODES) {
        const layout = layoutFor(w, h);
        for (const f of FRAMES) {
            const rect = layout.rectsByAction[f.action][f.index];
            const scr = contentRectToScreen(rect, layout);
            assert.ok(Math.abs(scr.bottom - layout.groundY) < 0.01,
                `${mode}/${f.action}[${f.index}] 底边 ${scr.bottom.toFixed(3)} 未对齐地面线 ${layout.groundY}`);
        }
    }
});

// ====== 测试 7: 缩放是最紧可行值 (没有被无谓缩小) ======
test('T7 缩放倍率取到最紧可行值 (至少一帧贴住留白边界)', () => {
    for (const [mode, w, h] of MODES) {
        const layout = layoutFor(w, h);
        let minSlack = Infinity;
        for (const f of FRAMES) {
            const rect = layout.rectsByAction[f.action][f.index];
            const scr = contentRectToScreen(rect, layout);
            const slack = Math.min(
                scr.left - layout.margin,
                layout.canvasW - layout.margin - scr.right,
                scr.top - layout.margin,
                layout.canvasH - layout.margin - scr.bottom,
            );
            minSlack = Math.min(minSlack, slack);
        }
        assert.ok(minSlack >= -0.01, `${mode} 有帧越过留白边界 (slack=${minSlack.toFixed(3)})`);
        assert.ok(minSlack < 0.5, `${mode} 缩放未取到最紧 (minSlack=${minSlack.toFixed(3)}px, 说明被无谓缩小)`);
    }
});

// ====== 测试 8: 遗留算法对照 (证明 R141 确实裁切) ======
test('T8 对照: R141 遗留算法在两种尺寸下均会裁切 (修复真实有效)', () => {
    for (const [mode, w, h] of MODES) {
        const legacy = legacyLayout({ canvasW: w, canvasH: h, textureW: TEXTURE, mode });
        let clipped = 0;
        for (const f of FRAMES) {
            const bb = f.bbox;
            const x0 = legacy.x + (bb[0] - legacy.anchor.x * TEXTURE) * legacy.scale;
            const x1 = legacy.x + (bb[2] - legacy.anchor.x * TEXTURE) * legacy.scale;
            const y0 = legacy.y + (bb[1] - legacy.anchor.y * TEXTURE) * legacy.scale;
            const y1 = legacy.y + (bb[3] - legacy.anchor.y * TEXTURE) * legacy.scale;
            const out = Math.max(0, -x0) + Math.max(0, x1 - w) + Math.max(0, -y0) + Math.max(0, y1 - h);
            if (out > 0.5) clipped++;
        }
        assert.ok(clipped > 0, `${mode} 遗留算法竟未裁切, 对照失效 (scale=${legacy.scale})`);
    }
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R144 渲染边界测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) {
        console.log(`  - ${r.name}: ${r.error}`);
    }
    process.exit(1);
}
process.exit(0);
