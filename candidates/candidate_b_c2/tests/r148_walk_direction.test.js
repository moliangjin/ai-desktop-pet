// R148 左右行走方向修复 — 单元测试
//
// 覆盖 R148 任务书里**可自动化**的硬约束:
//
//   1. R138 原始 23 帧**逐字节不变** (派生镜像不得污染源素材)
//   2. walk_right 使用**派生镜像帧**, 且派生帧文件真实存在
//   3. 派生帧与"整体水平镜像"一致 (源帧水平翻转的 SHA256) —— 证明是**整体**镜像,
//      不是"只翻转双腿" (若只翻腿, 翻转整帧的哈希必然对不上)
//   4. 徽章等**非对称细节**未被镜像 (胸口烧瓶徽章仍需留在角色自己的左胸)
//      → 纯 JS 无法解码 PNG, 该项由 18_R148_direction_verify.py 逐像素校验,
//         本测试负责确认该校验产物存在且结论为 PASS
//   5. manifest 的 walk_right bbox 与派生帧真实 bbox 一致 (地面线/缩放核算基础)
//   6. 倾斜方向仍然相反 (walk_left 向左 / walk_right 向右)
//   7. 23 个帧槽位仍然是 23 个**互不相同**的文件 (资产门禁口径不变)
//
// 视觉方向的最终判定以 18_R148_direction_verify.py 的鞋尖几何测量 + GIF 预览为准,
// 本测试**不**以坐标符号/动画名/自身 PASS 作为方向正确的依据。

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const crypto = require('crypto');
const zlib = require('zlib');

const CAND = path.join(__dirname, '..');
const ASSETS = path.join(CAND, 'assets');
const MANIFEST = JSON.parse(fs.readFileSync(path.join(ASSETS, 'character_R141_manifest.json'), 'utf8'));
const BASELINE = JSON.parse(fs.readFileSync(
    path.join(ASSETS, 'character_R138_derived', 'r138_source_checksums.json'), 'utf8'));

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

function sha256(p) {
    return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

// PNG IHDR → 宽高 (只读文件头, 不解码像素)
function pngSize(p) {
    const fd = fs.openSync(p, 'r');
    const buf = Buffer.alloc(24);
    fs.readSync(fd, buf, 0, 24, 0);
    fs.closeSync(fd);
    return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

const wl = MANIFEST.actions.walk_left;
const wr = MANIFEST.actions.walk_right;

// ====== T1: R138 原始 23 帧逐字节不变 ======
test('T1 R138 原始 23 帧 SHA256 与基线完全一致 (源素材未被污染)', () => {
    const keys = Object.keys(BASELINE.files);
    assert.strictEqual(keys.length, 23, `基线应含 23 帧, 实际 ${keys.length}`);
    for (const rel of keys) {
        const p = path.join(ASSETS, rel);
        assert.ok(fs.existsSync(p), `源帧缺失: ${rel}`);
        const h = sha256(p);
        assert.strictEqual(h, BASELINE.files[rel], `源帧被改动: ${rel}`);
    }
});

// ====== T2: walk_right 指向派生镜像帧, 文件全部存在 ======
test('T2 walk_right 使用派生镜像帧且 4 个文件均存在 (1024x1024 RGBA)', () => {
    assert.strictEqual(wr.frames.length, 4);
    for (const rel of wr.frames) {
        assert.ok(rel.includes('character_R138_derived/walk_right_mirror/'),
            `walk_right 帧必须来自派生目录: ${rel}`);
        const p = path.join(ASSETS, rel);
        assert.ok(fs.existsSync(p), `派生帧缺失: ${rel}`);
        const s = pngSize(p);
        assert.strictEqual(s.w, 1024, `派生帧宽度应为 1024: ${rel}`);
        assert.strictEqual(s.h, 1024, `派生帧高度应为 1024: ${rel}`);
    }
});

// ====== T3: 派生帧 = 源帧"整体水平镜像"的像素结果 (证明是整体镜像) ======
// 判定方式: 源帧 PNG 解码后水平翻转 → 与派生帧逐像素比较。
// Node 无内置 PNG 解码, 这里用 zlib 自行解码 (PNG 为 zlib 压缩的 scanline)。
function decodePNG(file) {
    const buf = fs.readFileSync(file);
    let pos = 8;
    let width = 0, height = 0, bitDepth = 0, colorType = 0;
    const idat = [];
    while (pos < buf.length) {
        const len = buf.readUInt32BE(pos);
        const type = buf.toString('ascii', pos + 4, pos + 8);
        const data = buf.slice(pos + 8, pos + 8 + len);
        if (type === 'IHDR') {
            width = data.readUInt32BE(0);
            height = data.readUInt32BE(4);
            bitDepth = data[8];
            colorType = data[9];
        } else if (type === 'IDAT') {
            idat.push(data);
        } else if (type === 'IEND') {
            break;
        }
        pos += 12 + len;
    }
    assert.strictEqual(bitDepth, 8, '仅支持 8bit PNG');
    assert.strictEqual(colorType, 6, '仅支持 RGBA (colorType=6)');
    const raw = zlib.inflateSync(Buffer.concat(idat));
    const bpp = 4;
    const stride = width * bpp;
    const out = Buffer.alloc(height * stride);
    let rp = 0;
    for (let y = 0; y < height; y++) {
        const filter = raw[rp++];
        const line = raw.slice(rp, rp + stride);
        rp += stride;
        const cur = out.slice(y * stride, (y + 1) * stride);
        const prev = y > 0 ? out.slice((y - 1) * stride, y * stride) : Buffer.alloc(stride);
        for (let i = 0; i < stride; i++) {
            const a = i >= bpp ? cur[i - bpp] : 0;
            const b = prev[i];
            const c = i >= bpp ? prev[i - bpp] : 0;
            let v = line[i];
            switch (filter) {
                case 0: break;
                case 1: v = (v + a) & 0xff; break;
                case 2: v = (v + b) & 0xff; break;
                case 3: v = (v + ((a + b) >> 1)) & 0xff; break;
                case 4: {
                    const p = a + b - c;
                    const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
                    const pr = (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
                    v = (v + pr) & 0xff;
                    break;
                }
                default: throw new Error(`未知 filter ${filter}`);
            }
            cur[i] = v;
        }
    }
    return { width, height, data: out };
}

test('T3 派生帧在徽章区外与源帧"整体水平镜像"逐像素一致 (证明是整体镜像, 非单独镜像腿)', () => {

    const derived = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R138_derived', 'walk_right_mirror', 'derive_report.json'), 'utf8'));
    for (const info of derived.frames) {
        const srcPath = path.join(CAND, info.src);
        const derPath = path.join(CAND, info.out);
        const src = decodePNG(srcPath);
        const der = decodePNG(derPath);
        assert.strictEqual(src.width, der.width);
        // 徽章涉及的两个区域: 徽章原位 + 镜像后残留位 (羽化只可能影响这两块)
        const [ex0, ey0, ex1, ey1] = info.emblem_box;
        const W = src.width;
        const boxes = [[ex0, ey0, ex1, ey1], [W - ex1, ey0, W - ex0, ey1]];
        let diffOutside = 0;
        let maxOutside = 0;
        let diffInside = 0;
        for (let y = 0; y < src.height; y++) {
            for (let x = 0; x < W; x++) {
                // 水平镜像: 源帧 (x,y) → 派生帧 (W-1-x, y)
                const si = (y * W + x) * 4;
                const di = (y * W + (W - 1 - x)) * 4;
                const inEmblem = boxes.some(b => x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]);
                for (let c = 0; c < 4; c++) {
                    const d = Math.abs(src.data[si + c] - der.data[di + c]);
                    if (inEmblem) { if (d > 0) diffInside++; }
                    else { if (d > 0) diffOutside++; if (d > maxOutside) maxOutside = d; }
                }
            }
        }
        assert.strictEqual(diffOutside, 0,
            `${info.out}: 徽章区外应与镜像逐像素一致, 实际 ${diffOutside} 个字节不一致 (max=${maxOutside})`);
        assert.ok(diffInside > 0,
            `${info.out}: 徽章区应被修复过 (区内与纯镜像存在差异), 实际 0 → 说明徽章被一起镜像了`);
    }
});

// ====== T4: 方向几何校验产物存在且结论为 PASS ======
test('T4 鞋尖几何客观测量产物存在: walk_left/walk_right 均为 PASS, 旧 walk_right 为 FAIL', () => {
    const p = path.join(CAND, 'evidence_r148_direction.json');
    assert.ok(fs.existsSync(p), '缺少 18_R148_direction_verify.py 的测量产物');
    const r = JSON.parse(fs.readFileSync(p, 'utf8'));
    assert.strictEqual(r.groups.walk_left.verdict, 'PASS', 'walk_left 鞋尖方向应判定 PASS');
    assert.strictEqual(r.groups.walk_right_R148.verdict, 'PASS', 'walk_right(R148) 鞋尖方向应判定 PASS');
    assert.strictEqual(r.groups.walk_right_OLD.verdict, 'FAIL',
        '旧 walk_right 必须被判定 FAIL (客观复现用户反馈的倒退问题)');
    assert.ok(r.mirror_exact_outside_emblem, '徽章区外必须与镜像逐像素一致');
    assert.ok(r.emblem_not_mirrored_all, '徽章必须未被镜像');
    assert.ok(r.emblem_on_character_left_chest, '徽章必须仍在角色自己的左胸');
});

// ====== T5: manifest 的 walk_right bbox 与派生帧真实 bbox 一致 ======
test('T5 manifest 的 walk_right bbox 与派生帧真实 bbox 一致 (地面线/缩放核算基础)', () => {
    const boxes = MANIFEST.layout.frame_bboxes.walk_right;
    assert.strictEqual(boxes.length, 4);
    for (let i = 0; i < 4; i++) {
        const rel = wr.frames[i];
        const rep = JSON.parse(fs.readFileSync(
            path.join(ASSETS, 'character_R138_derived', 'walk_right_mirror', 'derive_report.json'), 'utf8'));
        const info = rep.frames[i];
        assert.deepStrictEqual(boxes[i], info.bbox,
            `第 ${i} 帧 bbox 不一致: manifest=${JSON.stringify(boxes[i])} 实际=${JSON.stringify(info.bbox)}`);
        assert.strictEqual(boxes[i][3], 987, '所有帧底边应贴同一地面接触线');
    }
});

// ====== T6: 行走不再施加整体错切 (R153) + 像素级站姿端正 ======
// R153 用户真机反馈: "行走时身体明显前倾, 像要摔倒"
// 根因: R147/R148 用**整体水平错切** (skew_x = ±0.085/±0.11) 表达行走方向,
//       整个身体偏离垂直轴, 在 200x240 紧凑窗口里观感就是"上半身往前栽"。
// R148 已经用**派生镜像帧**把"迈步方向"修对了 (鞋尖几何客观测量 PASS),
//       方向表达不再依赖错切 ⇒ R153 把 walk_*.lean.skew_x 归零。
//
// 判定方式: 对**真实像素**测量"上半身重心相对下半身重心的水平偏移 / 身高",
//           不依赖坐标符号、动画名或本测试自身的 PASS。
test('T6 行走不施加整体错切 (k=0), 且像素级测量左右两组躯干偏心相反且站姿端正', () => {
    // 1) manifest 层: 错切归零, 方向元数据保留
    assert.strictEqual(wl.lean.skew_x, 0, 'walk_left 不应再施加整体错切 (R153 修复"前倾像摔倒")');
    assert.strictEqual(wr.lean.skew_x, 0, 'walk_right 不应再施加整体错切');
    assert.strictEqual(wl.lean.direction, -1, 'walk_left 方向元数据应保留为 -1');
    assert.strictEqual(wr.lean.direction, 1, 'walk_right 方向元数据应保留为 1');

    // 2) 像素层: 真实帧的躯干偏心
    const { measureGroup } = require(path.join(CAND, 'tests', 'r153_png.js'));
    const L = measureGroup(wl.frames, ASSETS);
    const R = measureGroup(wr.frames, ASSETS);

    // 站姿端正门槛: 上半身偏心 < 身高的 3%
    assert.ok(L.maxAbsRatio < 0.03,
        `walk_left 躯干偏心过大 ${(L.maxAbsRatio * 100).toFixed(2)}% 身高 (门槛 3%)`);
    assert.ok(R.maxAbsRatio < 0.03,
        `walk_right 躯干偏心过大 ${(R.maxAbsRatio * 100).toFixed(2)}% 身高 (门槛 3%)`);

    // 左右两组符号必须相反 (walk_right 是 walk_left 的整体镜像派生 ⇒ 偏心必然反号)
    // 这是**独立几何测量**得到的交叉校验, 不是"看动画名"
    assert.ok(L.signs.every(s => s === -1),
        `walk_left 各帧偏心应同号, 实际 ${L.signs.join(',')}`);
    assert.ok(R.signs.every(s => s === 1),
        `walk_right 各帧偏心应同号, 实际 ${R.signs.join(',')}`);
    assert.ok(Math.abs(L.meanRatio + R.meanRatio) < 1e-6,
        `镜像派生两组偏心应严格反号: L=${L.meanRatio} R=${R.meanRatio}`);
});

// ====== T7: 23 个帧槽位仍是 23 个互不相同的文件 ======
test('T7 manifest 仍是 23 个互不相同的帧文件 (资产门禁口径不变)', () => {
    const all = [];
    for (const action of MANIFEST.animation_order) {
        all.push(...MANIFEST.actions[action].frames);
    }
    assert.strictEqual(all.length, 23, `帧槽位应为 23, 实际 ${all.length}`);
    assert.strictEqual(new Set(all).size, 23, '23 个帧槽位必须互不相同');
    for (const rel of all) {
        assert.ok(fs.existsSync(path.join(ASSETS, rel)), `帧文件缺失: ${rel}`);
    }
});

// ====== T8: 原 R138 walk_right 4 帧仍在磁盘上且未改动 (仅不再被引用) ======
test('T8 原 R138 walk_right 4 帧保留在磁盘且字节未变 (仅不再被 manifest 引用)', () => {
    const old = MANIFEST.r148_walk_direction_fix.original_walk_right_frames.paths;
    assert.strictEqual(old.length, 4);
    for (const rel of old) {
        const p = path.join(ASSETS, rel);
        assert.ok(fs.existsSync(p), `原 walk_right 帧应保留: ${rel}`);
        assert.strictEqual(sha256(p), BASELINE.files[rel], `原 walk_right 帧被改动: ${rel}`);
    }
    const referenced = new Set();
    for (const action of MANIFEST.animation_order) {
        MANIFEST.actions[action].frames.forEach(f => referenced.add(f));
    }
    for (const rel of old) {
        assert.ok(!referenced.has(rel), `原 walk_right 帧不应再被引用: ${rel}`);
    }
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R148 行走方向测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) {
        console.log(`  - ${r.name}: ${r.error}`);
    }
    process.exit(1);
}
process.exit(0);
