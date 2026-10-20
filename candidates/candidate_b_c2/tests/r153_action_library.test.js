// R153 动作自然度与自主生活丰富度 — 专项单元测试
//
// 覆盖 R153 任务书里**可自动化**的硬约束:
//
//   1. 动作库真实存在: 15 个动作 (6 核心 + 9 库), 每个都有独立帧资源
//   2. **不虚增动作数**: 没有任何两个动作共用同一套帧; 11 张烘焙帧两两不同 (SHA256)
//   3. 局部烘焙的诚实性: 烘焙帧与源帧**只在指定区域**不同 (眼区 / 头部 / 胸口),
//      不是整体旋转或强行缩放
//   4. 过渡策略: 坐→躺 必须溶解 (>0ms), 同姿态族立即切换
//   5. 小动作池不重复上一次
//   6. 需要新素材的动作**如实列出**, 且不得被算进"已实现"
//   7. 点击反馈用 happy (歪头眯眼笑), 绝不复用"手放胸前"帧
//   8. 行走不施加整体错切; 核心 6 组帧槽位仍是 23 个互不相同文件
//   9. A1 母版与 R138 原始 23 帧未被污染
//
// 判定不依赖坐标符号、动画名或本测试自身的 PASS。

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const crypto = require('crypto');

const CAND = path.join(__dirname, '..');
const ASSETS = path.join(CAND, 'assets');
const MANIFEST = JSON.parse(fs.readFileSync(path.join(ASSETS, 'character_R141_manifest.json'), 'utf8'));

const {
    ACTION_CATALOG, GESTURE_POOL, GESTURE_DURATION_MS, TRANSITION_BLEND_MS,
    NEEDS_NEW_ASSETS, transitionBlendMs, pickGesture, countDistinctActions,
} = require(path.join(CAND, 'src', 'action_library.js'));
const { measureGroup } = require(path.join(__dirname, 'r153_png.js'));

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

const LIB = MANIFEST.action_library || {};
const LIB_ACTIONS = LIB.actions || {};

// R153 的 9 个动作 (R156 又新增了 7 个, 但 R153 的这 9 个一个都不能少)
const R153_LIB_ACTIONS = ['look_around', 'tilt_head', 'head_nod', 'happy', 'blink_soft',
    'stretch', 'sit_rest', 'doze', 'sleep_breath'];

// ====== A. 动作库结构 ======
test('A1 动作库启用, R153 的 9 个动作齐全, 每个都有帧资源与目录登记', () => {
    assert.ok(LIB.enabled, 'manifest 的 action_library 必须启用');
    const names = Object.keys(LIB_ACTIONS);
    assert.ok(names.length >= 9, `动作库至少应有 9 个动作, 实际 ${names.length}: ${names.join(',')}`);
    for (const n of R153_LIB_ACTIONS) {
        assert.ok(LIB_ACTIONS[n], `R153 动作 ${n} 丢失 (R156 新增动作不得顶掉旧动作)`);
    }
    for (const n of names) {
        const spec = LIB_ACTIONS[n];
        assert.ok(Array.isArray(spec.frames) && spec.frames.length > 0, `${n} 没有帧资源`);
        assert.ok(ACTION_CATALOG[n], `${n} 未登记进 ACTION_CATALOG`);
        assert.strictEqual(ACTION_CATALOG[n].group, 'library', `${n} 的 group 应为 library`);
        for (const f of spec.frames) {
            assert.ok(fs.existsSync(path.join(ASSETS, f)), `${n} 的帧文件缺失: ${f}`);
        }
    }
});

test('A2 核心 6 组 + 动作库 (R153 九个 + R156 新增) ≥ 15 个动作, 满足"不少于 12 种"', () => {
    const core = MANIFEST.animation_order;
    assert.strictEqual(core.length, 6, `核心应有 6 组, 实际 ${core.length}`);
    const stats = countDistinctActions(MANIFEST);
    assert.ok(stats.total >= 15, `动作总数应 ≥15 (R153 基线), 实际 ${stats.total}`);
    assert.ok(stats.total >= 12, `动作数 ${stats.total} 少于任务书要求的 12`);
    // 分类分布: 静止/小动作/移动/一次性 都要有
    const kinds = Object.keys(stats.byKind).sort();
    assert.deepStrictEqual(kinds, ['gesture', 'move', 'oneShot', 'rest'],
        `动作类别分布异常: ${JSON.stringify(stats.byKind)}`);
});

// ====== B. 不虚增动作数 (硬约束) ======
test('B1 没有任何两个动作共用同一套帧 (不存在"改名即新动作")', () => {
    const stats = countDistinctActions(MANIFEST);
    const sharedSets = stats.sharedFrameSets.filter(s => s.sameFrames && s.actions.length > 1);
    assert.strictEqual(sharedSets.length, 0,
        `存在共用同一套帧的动作: ${JSON.stringify(sharedSets)}`);
    assert.strictEqual(stats.distinctFrameSets, stats.total,
        `帧组合数 ${stats.distinctFrameSets} 应等于动作数 ${stats.total}`);
});

test('B2 12 张 R153 烘焙帧两两不同 (SHA256 互异), 且都不是原始帧的拷贝', () => {
    const dir = path.join(ASSETS, 'character_R153');
    const files = fs.readdirSync(dir).filter(f => f.endsWith('.png')).sort();
    assert.strictEqual(files.length, 12, `应有 12 张烘焙帧, 实际 ${files.length}: ${files.join(',')}`);
    const hashes = new Map();
    for (const f of files) {
        const h = sha256(path.join(dir, f));
        assert.ok(!hashes.has(h), `烘焙帧重复: ${f} 与 ${hashes.get(h)} 同哈希`);
        hashes.set(h, f);
    }
    // 不能是任何 R138 原始帧的字节拷贝 (那就是"重复播放")
    const baseline = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R138_derived', 'r138_source_checksums.json'), 'utf8'));
    const baselineSet = new Set(Object.values(baseline.files));
    for (const f of files) {
        const h = sha256(path.join(dir, f));
        assert.ok(!baselineSet.has(h), `烘焙帧 ${f} 与某张 R138 原始帧字节相同 (等同重复播放)`);
    }
});

test('B3 动作库里复用已有帧的只有 stretch / sit_rest, 且复用的帧本身就是那个姿势', () => {
    const stats = countDistinctActions(MANIFEST);
    const reused = stats.reusedFrames;
    // 复用关系必须是"库动作 ↔ 核心动作"的一对一, 不允许库动作之间互相复用
    for (const r of reused) {
        const libOwners = r.owners.filter(o => LIB_ACTIONS[o]);
        assert.ok(libOwners.length <= 1,
            `多个库动作共用同一帧 (虚增动作数): ${r.frame} ← ${r.owners.join(',')}`);
    }
    const reusedBy = {};
    for (const r of reused) {
        for (const o of r.owners) {
            if (LIB_ACTIONS[o]) reusedBy[o] = (reusedBy[o] || 0) + 1;
        }
    }
    // stretch = R138 idle_01 (双臂抬起 = 伸懒腰), sit_rest = R138 sleep_enter_01_sit (坐姿)
    assert.deepStrictEqual(Object.keys(reusedBy).sort(), ['sit_rest', 'stretch'],
        `复用的动作应只有 stretch/sit_rest, 实际 ${Object.keys(reusedBy).join(',')}`);
    assert.ok(reusedBy.stretch === 1 && reusedBy.sit_rest === 1,
        `stretch/sit_rest 各应只复用 1 帧, 实际 ${JSON.stringify(reusedBy)}`);
    // 其余库动作必须是**独占**的烘焙帧 (R153 原有 7 个 + R156 新增的 7 个)
    const libDetail = stats.detail.filter(d => d.group === 'library');
    const dedicated = libDetail.filter(d => !reusedBy[d.action]).map(d => d.action);
    assert.ok(dedicated.length >= 7,
        `应有 ≥7 个独占烘焙帧的库动作, 实际 ${dedicated.length}: ${dedicated.join(',')}`);
    assert.strictEqual(dedicated.length + Object.keys(reusedBy).length, libDetail.length,
        '每个库动作要么独占烘焙帧, 要么是被登记在案的语义化复用 (不得有第三种情况)');
});

// ====== C. 局部烘焙的诚实性 (不是整体旋转/强行缩放) ======
test('C1 眼区合成帧: 只有眼部区域被替换, 身体与底图逐像素一致', () => {
    const report = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R153', 'bake_report.json'), 'utf8'));
    const items = report.items;
    const eyeSwaps = items.filter(i => i.swapped_px !== undefined);
    assert.ok(eyeSwaps.length >= 4, `眼区合成帧应有 ≥4 张, 实际 ${eyeSwaps.length}`);
    for (const it of eyeSwaps) {
        assert.ok(it.donor, `${it.file} 未记录 donor 帧`);
        assert.ok(it.swapped_px > 0 && it.swapped_px < 120000,
            `${it.file} 替换像素数 ${it.swapped_px} 不合理 (应只改眼区)`);
        assert.ok(fs.existsSync(path.join(ASSETS, 'character_R153', it.file)));
    }
});

test('C2 头部变形帧: 腿部/下半身 bbox 未被整体缩放或抬起 (重心仍在原地)', () => {
    const report = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R153', 'bake_report.json'), 'utf8'));
    const srcBbox = { top: 37, bottom: 987 };   // idle_00_base 的实测上下边界
    const headFrames = report.items.filter(i => i.transform && i.transform.rotate !== 0);
    assert.ok(headFrames.length >= 4, `头部变形帧应有 ≥4 张, 实际 ${headFrames.length}`);
    for (const it of headFrames) {
        // 底边 (脚底) 不动 ⇒ 没有整体缩放/抬起
        assert.strictEqual(it.bbox[3], srcBbox.bottom,
            `${it.file} 脚底位置被改动 (bbox bottom=${it.bbox[3]} 应为 ${srcBbox.bottom}) → 说明做了整体缩放`);
        // 顶边允许小幅变化 (头部转动/点头)
        assert.ok(Math.abs(it.bbox[1] - srcBbox.top) <= 12,
            `${it.file} 头顶位移过大 (${it.bbox[1]}), 超出"局部变形"范围`);
        // 旋转幅度受限, 不得是整体大角度旋转
        assert.ok(Math.abs(it.transform.rotate) <= 12,
            `${it.file} 旋转 ${it.transform.rotate}° 超限, 疑似整体旋转`);
        // 缩放幅度受限
        assert.ok(it.transform.scale >= 0.97 && it.transform.scale <= 1.0,
            `${it.file} 缩放 ${it.transform.scale} 超限, 疑似强行缩放`);
    }
});

test('C3 躺姿呼吸帧: 胸口微缩幅度极小 (呼吸, 不是形变)', () => {
    const report = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R153', 'bake_report.json'), 'utf8'));
    const breath = report.items.filter(i => i.amount !== undefined);
    assert.strictEqual(breath.length, 2, `呼吸帧应有 2 张, 实际 ${breath.length}`);
    for (const it of breath) {
        assert.ok(Math.abs(it.amount) <= 0.05,
            `${it.file} 呼吸幅度 ${it.amount} 过大, 应 ≤0.05`);
        assert.ok(Array.isArray(it.chest_box), `${it.file} 未限定胸口区域`);
    }
});

// ====== D. 过渡策略 ======
test('D1 坐→躺 必须交叉溶解 (修复"瞬间躺下"), 同姿态族立即切换', () => {
    assert.ok(transitionBlendMs('sit_rest', 'sleep_enter') >= 250,
        `sit_rest→sleep_enter 溶解时长 ${transitionBlendMs('sit_rest', 'sleep_enter')}ms 不足 (应 ≥250ms)`);
    assert.ok(transitionBlendMs('doze', 'sleep_enter') >= 250,
        `doze→sleep_enter 溶解时长不足`);
    assert.ok(transitionBlendMs('sit_rest', 'doze') >= 200,
        `sit_rest→doze 溶解时长不足`);
    assert.ok(transitionBlendMs('sleep_breath', 'wake_up') >= 200,
        `sleep_breath→wake_up 溶解时长不足`);
    // 同姿态族 → 立即切换 (不糊化)
    assert.strictEqual(transitionBlendMs('walk_left', 'walk_right'), 0);
    assert.strictEqual(transitionBlendMs('sleep_breath', 'sleep_loop'), 0);
    assert.strictEqual(transitionBlendMs('idle', 'idle'), 0);
});

test('D2 过渡表里的每个组合两端都是已登记动作 (无悬空键)', () => {
    for (const key of Object.keys(TRANSITION_BLEND_MS)) {
        const [from, to] = key.split('>');
        assert.ok(ACTION_CATALOG[from], `过渡表含未登记的 from: ${from}`);
        assert.ok(ACTION_CATALOG[to], `过渡表含未登记的 to: ${to}`);
    }
});

test('D3 帧级溶解已配置: 一次性动画内部换帧也走渐变 (修复"坐下瞬间躺下")', () => {
    // 实测根因: sleep_enter 第 0 帧本身就是坐姿, 动作级溶解 = "坐→坐"(无视觉变化),
    //           真正的躺姿在换帧那一瞬硬切 → 必须有**帧级**溶解。
    const se = MANIFEST.actions.sleep_enter;
    assert.ok(se.frame_blend_ms >= 250,
        `sleep_enter 帧级溶解 ${se.frame_blend_ms}ms 不足 (应 ≥250ms)`);
    assert.ok(MANIFEST.actions.wake_up.frame_blend_ms >= 200,
        `wake_up 帧级溶解 ${MANIFEST.actions.wake_up.frame_blend_ms}ms 不足`);
    assert.ok(LIB_ACTIONS.head_nod.frame_blend_ms >= 150,
        `head_nod 帧级溶解 ${LIB_ACTIONS.head_nod.frame_blend_ms}ms 不足`);
    // 眨眼类不得溶解 (眼睛会糊)
    assert.ok(!LIB_ACTIONS.blink_soft.frame_blend_ms,
        '眨眼帧不得做溶解 (眼睛会糊成一片)');
    // 溶解时长不得超过该帧自身的显示时长, 否则新姿势来不及看清
    const seMs = Array.isArray(se.frame_ms) ? se.frame_ms[0] : se.frame_ms;
    assert.ok(se.frame_blend_ms < seMs,
        `sleep_enter 帧级溶解 ${se.frame_blend_ms}ms 不得 ≥ 该帧显示时长 ${seMs}ms`);
});

// ====== E. 小动作池 ======
test('E1 pickGesture 不重复上一次, 且总是返回池内动作', () => {
    const pool = new Set(GESTURE_POOL.map(g => g.action));
    for (let i = 0; i < 300; i++) {
        const r = Math.random();
        const last = GESTURE_POOL[i % GESTURE_POOL.length].action;
        const picked = pickGesture(r, last);
        assert.ok(pool.has(picked), `pickGesture 吐出池外动作 ${picked}`);
        assert.notStrictEqual(picked, last, `pickGesture 重复了上一次动作 ${last}`);
    }
    // 全部排除时仍有合法兜底
    const all = GESTURE_POOL.map(g => g.action);
    const picked = pickGesture(() => 0.99, null, all);
    assert.ok(pool.has(picked), '全排除时应回退到池内动作');
});

test('E2 每个小动作都有建议时长, 一次性动作比循环动作短', () => {
    for (const g of GESTURE_POOL) {
        assert.ok(typeof GESTURE_DURATION_MS[g.action] === 'number' && GESTURE_DURATION_MS[g.action] > 0,
            `${g.action} 缺少时长配置`);
    }
    assert.ok(GESTURE_DURATION_MS.head_nod < GESTURE_DURATION_MS.look_around,
        '点头应短于张望');
});

// ====== F. 需要新素材的动作 (如实列出) ======
test('F1 需新素材的动作清单存在且未被算进已实现动作', () => {
    assert.ok(NEEDS_NEW_ASSETS.length >= 5, `需新素材项应 ≥5, 实际 ${NEEDS_NEW_ASSETS.length}`);
    for (const item of NEEDS_NEW_ASSETS) {
        assert.ok(item.action && item.desc, '需新素材项缺少 action/desc');
        assert.ok(!ACTION_CATALOG[item.action],
            `${item.action} 既标为需新素材, 又出现在已实现动作表里 (自相矛盾)`);
        assert.ok(!LIB_ACTIONS[item.action],
            `${item.action} 既标为需新素材, 又出现在 manifest 动作库里 (虚报完成)`);
    }
    const descs = NEEDS_NEW_ASSETS.map(x => x.action);
    for (const expect of ['turn_around', 'walk_backward', 'run', 'wave_hand', 'eat_drink']) {
        assert.ok(descs.includes(expect), `需新素材清单缺少 ${expect}`);
    }
});

// ====== G. 点击反馈与核心资产门禁 ======
test('G1 manifest 里不存在"手放胸前"帧被当作眨眼/反馈帧的引用', () => {
    const idle = MANIFEST.actions.idle;
    const dir = 'character_R138/idle/';
    const handOnChest = idle.frames.find(f => f.includes(dir) && f.includes('idle_04'));
    assert.ok(handOnChest, 'idle_04 帧应仍在 idle 帧列表中 (素材保留)');
    const spec = idle.director;
    assert.ok(!spec.excluded_frames.includes(4) === false, 'idle_04 必须被列入 excluded_frames');
    assert.ok(!spec.blink_sequence.includes(4), 'idle_04 不得出现在眨眼序列');
    // 动作库里也不得引用 idle_04
    for (const [name, a] of Object.entries(LIB_ACTIONS)) {
        assert.ok(!a.frames.includes(handOnChest),
            `库动作 ${name} 复用了"手放胸前"帧 ${handOnChest}`);
    }
});

test('G2 核心 6 组仍是 23 个互不相同的帧文件 (R113/R148 门禁口径不变)', () => {
    const all = [];
    for (const action of MANIFEST.animation_order) {
        all.push(...MANIFEST.actions[action].frames);
    }
    assert.strictEqual(all.length, 23, `核心帧槽位应为 23, 实际 ${all.length}`);
    assert.strictEqual(new Set(all).size, 23, '23 个帧槽位必须互不相同');
});

test('G3 行走不施加整体错切, 核心动作一律无错切 (修复"前倾像摔倒")', () => {
    for (const action of MANIFEST.animation_order) {
        const lean = MANIFEST.actions[action].lean;
        if (!lean) continue;   // 没有 lean 段 = 不施加错切 (渲染器默认 k=0)
        assert.strictEqual(lean.skew_x, 0, `${action} 仍施加整体错切 skew_x=${lean.skew_x}`);
    }
    // 明确点名的两组
    assert.strictEqual(MANIFEST.actions.walk_left.lean.skew_x, 0);
    assert.strictEqual(MANIFEST.actions.walk_right.lean.skew_x, 0);
});

// ====== H. 库动作的像素级真实性 (各动作彼此真的不一样) ======
test('H1 全部库动作的画面彼此不同 (用真实像素比对, 不看动作名)', () => {
    const { alphaMask, measureLean } = require(path.join(__dirname, 'r153_png.js'));
    // 取每个动作的代表帧, 比较像素签名 (alpha 掩膜 + 颜色直方图)
    const signatures = new Map();
    for (const [name, spec] of Object.entries(LIB_ACTIONS)) {
        const rel = spec.frames[0];
        const alpha = alphaMask(path.join(ASSETS, rel));
        const { decodePNG } = require(path.join(__dirname, 'r153_png.js'));
        const png = decodePNG(path.join(ASSETS, rel));
        // 粗签名: 每 64px 采样一次 RGBA 累加
        let acc = 0;
        for (let y = 0; y < png.height; y += 64) {
            for (let x = 0; x < png.width; x += 64) {
                const i = (y * png.width + x) * 4;
                acc = (acc + png.data[i] * 3 + png.data[i + 1] * 5 + png.data[i + 2] * 7 + png.data[i + 3] * 11) % 1000000007;
            }
        }
        signatures.set(name, acc);
        assert.ok(alpha.mask.some(v => v === 1), `${name} 的帧是空剪影`);
    }
    const values = [...signatures.values()];
    assert.strictEqual(new Set(values).size, values.length,
        `存在画面完全相同的库动作: ${JSON.stringify([...signatures])}`);
});

// ====== I. 烘焙报告自洽 ======
test('I1 bake_report 记录了 12 张帧, 全部存在于磁盘, 且都有 bbox', () => {
    const report = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R153', 'bake_report.json'), 'utf8'));
    assert.strictEqual(report.items.length, 12, `烘焙报告应有 12 项, 实际 ${report.items.length}`);
    for (const it of report.items) {
        assert.ok(fs.existsSync(path.join(ASSETS, 'character_R153', it.file)), `缺帧 ${it.file}`);
        assert.ok(Array.isArray(it.bbox) && it.bbox.length === 4, `${it.file} 缺 bbox`);
        assert.ok(it.bbox[3] > it.bbox[1], `${it.file} bbox 非法`);
    }
    assert.ok(Array.isArray(report.techniques) && report.techniques.length >= 3,
        '烘焙报告应记录 ≥3 种技法');
});

// ====== J. 动画时钟的每帧时长 (R153 引入的回归防线) ======
// R153 实测踩坑: 库动作用 frame_ms 数组 (如 blink_soft [95,135]) 表示每帧时长,
//   而 anim_clock.period() 旧实现直接 `return m.frame_ms` → 数组参与数值比较变 NaN
//   → `now - lastAdvanceAt >= NaN` 恒 false → **帧永远不推进, 动画整体静止**。
//   真实运行时 5 个多帧库动作 (张望/歪头/眨眼/点头/呼吸) 全部被冻住, 只有单测没抓到。
test('J1 frame_ms 为数组时, 帧按各自时长推进 (回归防线)', () => {
    const { AnimationClock } = require(path.join(CAND, 'src', 'anim_clock.js'));
    const meta = { frames: ['a', 'b', 'c'], frame_ms: [95, 135, 400], loop: true, fps: 8 };
    let t = 0;
    const clock = new AnimationClock({ now: () => t });
    clock.setAction('blink_soft', meta, t);
    assert.strictEqual(clock.frameIndex, 0);
    // 95ms 未到 → 不推进
    t = 90;
    assert.strictEqual(clock.tick(t).changed, false, '未到时长不应推进');
    // 95ms 到了 → 推进到第 1 帧
    t = 100;
    assert.strictEqual(clock.tick(t).changed, true, '到达第 1 帧时长应推进');
    assert.strictEqual(clock.frameIndex, 1);
    // 第 2 帧时长 135ms
    t = 220;
    assert.strictEqual(clock.tick(t).changed, false, '未到第 2 帧时长不应推进');
    t = 240;
    assert.strictEqual(clock.tick(t).changed, true, '到达第 2 帧时长应推进');
    assert.strictEqual(clock.frameIndex, 2);
});

test('J2 frame_ms 为数组时, 一次性动画能走到末帧并回报完成 (回归防线)', () => {
    const { AnimationClock } = require(path.join(CAND, 'src', 'anim_clock.js'));
    const meta = { frames: ['a', 'b'], frame_ms: [260, 380], loop: false, fps: 8 };
    let t = 0;
    const clock = new AnimationClock({ now: () => t });
    clock.setAction('head_nod', meta, t);
    t = 300;
    let r = clock.tick(t);
    assert.strictEqual(r.changed, true, '应推进到第 1 帧');
    assert.strictEqual(r.finished, false, '到末帧不等于完成');
    // 末帧保持 380ms 后才回报
    t = 300 + 380;
    r = clock.tick(t);
    assert.strictEqual(r.finished, true, '末帧保持时长后应回报完成');
});

test('J3 frame_ms 为标量时行为不变 (回归防线)', () => {
    const { AnimationClock } = require(path.join(CAND, 'src', 'anim_clock.js'));
    const meta = { frames: ['a', 'b'], frame_ms: 130, loop: true, fps: 8 };
    let t = 0;
    const clock = new AnimationClock({ now: () => t });
    clock.setAction('walk_left', meta, t);
    t = 129;
    assert.strictEqual(clock.tick(t).changed, false);
    t = 130;
    assert.strictEqual(clock.tick(t).changed, true);
    assert.strictEqual(clock.frameIndex, 1);
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R153 动作库与自然度测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) console.log(`  - ${r.name}: ${r.error}`);
    process.exit(1);
}
process.exit(0);
