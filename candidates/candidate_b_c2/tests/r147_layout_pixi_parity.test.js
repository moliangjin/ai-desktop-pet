// R147 布局算法与真实 PixiJS 变换矩阵的一致性验证
//
// 目的: 证明 src/sprite_layout.js 里 contentRectToScreen / frameScreenRect 的公式
//       与 PixiJS 7.4.3 **实际渲染**用的顶点矩阵完全一致 (不是"自己算一套近似")。
//
// 做法: 用 @pixi/math 的真实 Transform 类 (renderer 用的同一个库) 构造
//       position/scale/skew, 取 localTransform, 把纹理点 (u,v) 经 anchor 偏移后
//       映射到屏幕, 与 sprite_layout.js 的结果逐点比对。
//
// 运行: node tests/r147_layout_pixi_parity.test.js
'use strict';

const path = require('path');
const assert = require('assert');

const CAND = path.join(__dirname, '..');
const PIXI_ROOT = path.join(CAND, '..', 'candidate_b_electronpixir', 'node_modules');
const { Transform } = require(path.join(PIXI_ROOT, '@pixi', 'math', 'lib', 'Transform.js'));

const {
    computeLayout, contentRectToScreen, frameScreenRect, skewAngleX, skewCosFactor,
} = require(path.join(CAND, 'src', 'sprite_layout.js'));

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

/** 用真实 PixiJS Transform 把纹理点映射到屏幕 */
function pixiMap(t, u, v, W, H) {
    const lx = u - t.anchorX * W;
    const ly = v - t.anchorY * H;
    const lt = t.transform.localTransform;
    return {
        x: lt.a * lx + lt.c * ly + lt.tx,
        y: lt.b * lx + lt.d * ly + lt.ty,
    };
}

function makeTransform(px, py, scale, skewX, anchorX, anchorY) {
    const transform = new Transform();
    transform.position.x = px;
    transform.position.y = py;
    transform.scale.set(scale, scale);
    transform.skew.x = skewX;
    transform.updateLocalTransform();
    return { transform, anchorX, anchorY };
}

const W = 1024, H = 1024;
const rect = { left: 300, top: 250, right: 700, bottom: 986, w: 400, h: 736 };

// ====== T1: 错切因子与 PixiJS 角度的换算关系 (k = sin(skew.x)) ======
test('T1 skewAngleX(k) 满足 PixiJS 的 k = sin(skew.x) 语义', () => {
    for (const k of [-0.15, -0.075, -0.02, 0, 0.085, 0.2]) {
        const theta = skewAngleX(k);
        assert.ok(Math.abs(Math.sin(theta) - k) < 1e-12,
            `k=${k} → sin(skewAngleX)=${Math.sin(theta)} 不等于 k`);
    }
    // 竖直压缩系数也必须一致
    for (const k of [-0.15, 0, 0.085, 0.2]) {
        const theta = skewAngleX(k);
        assert.ok(Math.abs(skewCosFactor(k) - Math.cos(theta)) < 1e-12,
            `k=${k} 的 cosθ 不一致`);
    }
});

// ====== T2: contentRectToScreen 与真实 PixiJS 顶点矩阵逐点一致 ======
test('T2 contentRectToScreen 与真实 PixiJS Transform 逐点一致 (含错切)', () => {
    const cases = [
        { k: 0, scale: 0.2, x: 100, y: 150 },
        { k: 0.085, scale: 0.2, x: 100, y: 150 },
        { k: -0.075, scale: 0.2, x: 100, y: 150 },
        { k: 0.12, scale: 0.33, x: 128, y: 200 },
    ];
    for (const c of cases) {
        const layout = {
            scale: c.scale, anchor: { x: 0.5, y: 0.9 }, x: c.x, groundY: c.y,
            textureW: W, textureH: H,
        };
        const scr = contentRectToScreen(rect, layout, c.k);
        // sprite 的 position.y 由地面线反推 (与 computeLayout 同一公式)
        const cosT = skewCosFactor(c.k);
        const spriteY = c.y - cosT * (rect.bottom - 0.9 * H) * c.scale;
        const t = makeTransform(c.x, spriteY, c.scale, skewAngleX(c.k), 0.5, 0.9);
        const corners = [
            [rect.left, rect.top], [rect.right, rect.top],
            [rect.left, rect.bottom], [rect.right, rect.bottom],
        ];
        const pts = corners.map(([u, v]) => pixiMap(t, u, v, W, H));
        const expLeft = Math.min(...pts.map(p => p.x));
        const expRight = Math.max(...pts.map(p => p.x));
        const expTop = Math.min(...pts.map(p => p.y));
        const expBottom = Math.max(...pts.map(p => p.y));
        assert.ok(Math.abs(scr.left - expLeft) < 1e-9 && Math.abs(scr.right - expRight) < 1e-9
            && Math.abs(scr.top - expTop) < 1e-9 && Math.abs(scr.bottom - expBottom) < 1e-9,
            `k=${c.k} 不一致: layout=(${scr.left.toFixed(6)},${scr.top.toFixed(6)})-(${scr.right.toFixed(6)},${scr.bottom.toFixed(6)}) ` +
            `pixi=(${expLeft.toFixed(6)},${expTop.toFixed(6)})-(${expRight.toFixed(6)},${expBottom.toFixed(6)})`);
    }
});

// ====== T3: 错切后角色确实朝指定方向倾斜 (头偏移方向) ======
test('T3 错切方向正确: k>0 上半身左移, k<0 上半身右移', () => {
    const layout = {
        scale: 0.2, anchor: { x: 0.5, y: 0.9 }, x: 100, groundY: 200,
        textureW: W, textureH: H,
    };
    const leftLean = contentRectToScreen(rect, layout, 0.085);
    const rightLean = contentRectToScreen(rect, layout, -0.085);
    const neutral = contentRectToScreen(rect, layout, 0);
    assert.ok(leftLean.left < neutral.left - 1, `k>0 应左移, 实际 left=${leftLean.left} vs ${neutral.left}`);
    assert.ok(rightLean.right > neutral.right + 1, `k<0 应右移, 实际 right=${rightLean.right} vs ${neutral.right}`);
    // 上半身 (顶端) 偏移应大于下半身偏移
    const headShiftLeft = neutral.left - leftLean.left;
    const headShiftRight = rightLean.right - neutral.right;
    assert.ok(Math.abs(headShiftLeft - headShiftRight) < 1e-9, '左右倾斜幅度应对称');
    assert.ok(headShiftLeft > 3, `上半身左移量应明显 (>3px), 实际 ${headShiftLeft.toFixed(2)}`);
});

// ====== T4: 地面接触线在错切下仍然精确对齐 ======
test('T4 错切时 23 帧底边仍精确落在同一条地面接触线', () => {
    const frames = [];
    for (let i = 0; i < 23; i++) {
        frames.push({
            action: 'walk_left', index: i % 4,
            bbox: [300, 250 + i, 700, 986 - (i % 3) * 4],
            skew_x: 0.085,
        });
    }
    const layout = computeLayout({
        canvasW: 200, canvasH: 240, textureW: W, textureH: H, frames, margin: 4,
    });
    for (let i = 0; i < 23; i++) {
        const scr = frameScreenRect(layout, 'walk_left', i % 4);
        assert.ok(Math.abs(scr.bottom - layout.groundY) < 1e-9,
            `第 ${i} 帧底边 ${scr.bottom} 未对齐地面线 ${layout.groundY}`);
    }
});

// ====== T5: 错切后仍不裁切 (布局把错切纳入缩放核算) ======
test('T5 错切纳入缩放核算后, 200x240 画布内零裁切', () => {
    const frames = [];
    for (let i = 0; i < 23; i++) {
        frames.push({
            action: 'a', index: i,
            bbox: [260, 200 + i * 5, 740, 986 - (i % 5) * 6],
            skew_x: (i % 2 === 0) ? 0.085 : -0.075,
        });
    }
    const layout = computeLayout({
        canvasW: 200, canvasH: 240, textureW: W, textureH: H, frames, margin: 4,
    });
    for (let i = 0; i < 23; i++) {
        const rectI = layout.rectsByAction['a'][i];
        const k = layout.frameSkewByAction['a'][i];
        const scr = contentRectToScreen(rectI, layout, k);
        assert.ok(scr.left >= layout.margin - 1e-6 && scr.right <= layout.canvasW - layout.margin + 1e-6
            && scr.top >= layout.margin - 1e-6 && scr.bottom <= layout.canvasH - layout.margin + 1e-6,
            `第 ${i} 帧越界: (${scr.left.toFixed(3)},${scr.top.toFixed(3)})-(${scr.right.toFixed(3)},${scr.bottom.toFixed(3)})`);
    }
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R147 布局/PixiJS 一致性测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) console.log(`  - ${r.name}: ${r.error}`);
    process.exit(1);
}
process.exit(0);
