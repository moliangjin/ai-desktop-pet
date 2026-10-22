// R156 点击互动扩展 + 场景道具 + 办公待机 — 专项单元测试
//
// 覆盖 R156 任务书里**可自动化**的硬约束:
//
//   1. 点击互动动作池 ≥5 个 (实际 6 个), 每个都有 3 帧 (开始/中间/结束), 不是单张定格
//   2. **不虚增动作数**: R156 的 20 张新帧两两不同, 且与 R138/R153 既有帧无字节重复
//   3. 随机触发: pickClickReaction 不重复最近用过的, 且 6 个动作都可达
//   4. 场景道具: 7 个程序化道具文件齐全; 动作→场景的 back/front 分层登记完整
//   5. 道具不遮脸: front 层道具的包围盒不得侵入角色脸部区域
//   6. 道具不出画布: 用**生产布局算法**核算, 所有道具与角色帧在 200x240 / 256x256 下零裁切
//   7. 地面行 (ground_tex_y): 有道具的动作, 角色踩在道具底上; 腾空帧真的离地
//   8. 办公待机: 行为引擎有 WORK 状态, 权重低, 不与其它活动连着做
//   9. 诚实性: 素材做不到的动作仍在"需要新素材"清单里, 不得硬标完成
//  10. 核心 6 组 23 帧与 R138 原始字节仍未被污染
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
    ACTION_CATALOG, CLICK_POOL, NEEDS_NEW_ASSETS, pickClickReaction, countDistinctActions,
} = require(path.join(CAND, 'src', 'action_library.js'));
const { computeLayout, groundRowY } = require(path.join(CAND, 'src', 'sprite_layout.js'));
const {
    BehaviorEngine, STATES, ACTIVITY_KINDS, DEFAULT_CONFIG,
} = require(path.join(CAND, 'src', 'behavior_engine.js'));
const { decodePNG } = require(path.join(__dirname, 'r153_png.js'));

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
const PROPS = MANIFEST.props || {};
const PROPS_LIB = PROPS.library || {};
const PROPS_SCENES = PROPS.scenes || {};
const CLICK = MANIFEST.click_reactions || {};

// 角色脸部区域 (纹理坐标, 实测: 头顶 37 / 下巴 300 / 脸宽 320~710)
// —— 道具的 front 层绝不能侵入这个区域, 否则会挡脸
const FACE_BOX = { x0: 320, y0: 30, x1: 712, y1: 305 };

function alphaBBox(rel) {
    const png = decodePNG(path.join(ASSETS, rel));
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let y = 0; y < png.height; y++) {
        for (let x = 0; x < png.width; x++) {
            const a = png.data[(y * png.width + x) * 4 + 3];
            if (a > 24) {
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
            }
        }
    }
    if (minX === Infinity) return null;
    return [minX, minY, maxX + 1, maxY + 1];
}

// ====== A. 点击互动池结构 ======
test('A1 点击池启用, 至少 5 个动作 (实际 6 个), 且与代码里的 CLICK_POOL 一致', () => {
    assert.ok(CLICK.enabled, 'manifest 的 click_reactions 必须启用');
    const pool = CLICK.pool || [];
    assert.ok(pool.length >= 5, `点击池应 ≥5 个动作, 实际 ${pool.length}`);
    assert.strictEqual(pool.length, CLICK_POOL.length,
        `manifest 池 (${pool.length}) 与 action_library.CLICK_POOL (${CLICK_POOL.length}) 数量不一致`);
    const libNames = CLICK_POOL.map(x => x.action).sort().join(',');
    const manNames = pool.map(x => x.action).sort().join(',');
    assert.strictEqual(manNames, libNames, `manifest 池与 CLICK_POOL 动作不一致: ${manNames} vs ${libNames}`);
    for (const p of pool) {
        assert.ok(ACTION_CATALOG[p.action], `点击动作 ${p.action} 未登记进 ACTION_CATALOG`);
        assert.ok(typeof p.weight === 'number' && p.weight > 0, `${p.action} 缺少有效权重`);
    }
});

test('A2 每个点击动作都有 ≥3 帧 (开始/中间/结束), 帧文件真实存在且互不相同', () => {
    for (const p of CLICK.pool) {
        const spec = LIB_ACTIONS[p.action];
        assert.ok(spec, `点击动作 ${p.action} 不在动作库里`);
        assert.ok(Array.isArray(spec.frames) && spec.frames.length >= 3,
            `${p.action} 只有 ${spec.frames ? spec.frames.length : 0} 帧 (必须 ≥3: 开始/中间/结束)`);
        assert.ok(!spec.loop, `${p.action} 必须是一次性动作 (loop=false), 否则点击反馈会卡在末帧`);
        const hashes = new Set();
        for (const f of spec.frames) {
            assert.ok(fs.existsSync(path.join(ASSETS, f)), `${p.action} 的帧缺失: ${f}`);
            const h = sha256(path.join(ASSETS, f));
            assert.ok(!hashes.has(h), `${p.action} 的两帧字节相同 (等于定格): ${f}`);
            hashes.add(h);
        }
        // 每帧时长必须声明 (多帧动作靠它推进)
        assert.ok(Array.isArray(spec.frame_ms) && spec.frame_ms.length === spec.frames.length,
            `${p.action} 的 frame_ms 必须与帧数一致`);
        for (const ms of spec.frame_ms) assert.ok(ms > 0, `${p.action} 有非法帧时长 ${ms}`);
    }
});

test('A3 点击动作不与其它动作共用同一套帧 (不靠重命名虚增)', () => {
    const stats = countDistinctActions(MANIFEST);
    const shared = stats.sharedFrameSets.filter(s => s.sameFrames && s.actions.length > 1);
    assert.strictEqual(shared.length, 0,
        `存在共用同一套帧的动作: ${JSON.stringify(shared)}`);
    // 点击动作的帧必须是**独占**的 (不被别的动作引用)
    const clickFrames = new Set();
    for (const p of CLICK.pool) for (const f of LIB_ACTIONS[p.action].frames) clickFrames.add(f);
    for (const r of stats.reusedFrames) {
        assert.ok(!clickFrames.has(r.frame),
            `点击动作的帧 ${r.frame} 被其它动作复用: ${r.owners.join(',')}`);
    }
});

test('A4 25 张 R156 新帧两两不同, 且与 R138/R153 既有帧无字节重复 (唯一性)', () => {
    const dir = path.join(ASSETS, 'character_R156');
    const allFiles = fs.readdirSync(dir).filter(f => f.endsWith('.png')).sort();
    const propFiles = new Set(Object.values(PROPS_LIB).map(s => s.file.split('/').pop()));
    const files = allFiles.filter(f => !propFiles.has(f));   // 角色动作帧 (道具另算)
    // R170: 新增吃水果 5 帧 ⇒ 角色动作帧 20 → 25
    assert.strictEqual(files.length, 25,
        `应有 25 张 R156 角色动作帧 (6 点击动作 ×3 + 办公 2 + 吃水果 5), 实际 ${files.length}: ${files.join(',')}`);
    // R165: 办公桌拆成 back(台面) / front(前沿+桌腿) 两个道具 ⇒ 道具 7 → 8, PNG 27 → 28
    // R167: 新增 prop_keyboard (办公键盘, back 层) ⇒ R156 目录道具 8 → 9, PNG 28 → 29
    // R170: 新增 prop_stool / prop_fruit_table (吃水果场景) ⇒ R156 目录道具 9 → 11, PNG 29 → 36
    //   (36 = 25 角色动作帧 + 11 道具; R170 新增 5 张 eat_fruit 帧 + 2 个道具)
    // 注意: PROPS_LIB 里 prop_heart 放在 character_R153 目录, 不在 R156 目录,
    //   所以"落在 R156 目录的道具"要按磁盘实况数, 不能直接用 PROPS_LIB 的条数。
    const propOnDisk = [...propFiles].filter(f => fs.existsSync(path.join(dir, f)));
    assert.strictEqual(propOnDisk.length, 11,
        `R156 目录应放 11 个道具 PNG (含 R170 新增 prop_stool / prop_fruit_table), 实际 ${propOnDisk.length}: ${propOnDisk.join(',')}`);
    // 目录里不允许出现既不是角色帧也不是道具的野文件
    const known = new Set([...files, ...propOnDisk]);
    const stray = allFiles.filter(f => !known.has(f));
    assert.strictEqual(stray.length, 0, `R156 目录有未登记的 PNG: ${stray.join(',')}`);
    assert.strictEqual(allFiles.length, files.length + propOnDisk.length,
        `R156 目录 PNG 总数应 = 角色动作帧 ${files.length} + 道具 ${propOnDisk.length} = ${files.length + propOnDisk.length}, 实际 ${allFiles.length}`);
    const mine = new Map();
    for (const f of files) {
        const h = sha256(path.join(dir, f));
        assert.ok(!mine.has(h), `R156 帧重复: ${f} 与 ${mine.get(h)} 同哈希`);
        mine.set(h, f);
    }
    const baseline = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R138_derived', 'r138_source_checksums.json'), 'utf8'));
    const baseSet = new Set(Object.values(baseline.files));
    for (const d of ['character_R153', 'character_R138']) {
        const dd = path.join(ASSETS, d);
        if (!fs.existsSync(dd)) continue;
        for (const f of fs.readdirSync(dd).filter(x => x.endsWith('.png'))) {
            const h = sha256(path.join(dd, f));
            assert.ok(!mine.has(h), `R156 帧与既有帧 ${d}/${f} 字节相同 (等同重复播放)`);
        }
    }
    assert.ok(baseSet.size > 0, 'R138 基线校验和缺失');
});

// ====== B. 随机触发 ======
test('B1 pickClickReaction 不重复最近用过的, 且总返回池内动作', () => {
    const pool = new Set(CLICK_POOL.map(x => x.action));
    for (let i = 0; i < 500; i++) {
        const last = CLICK_POOL[i % CLICK_POOL.length].action;
        const picked = pickClickReaction(Math.random, [last], CLICK_POOL);
        assert.ok(pool.has(picked), `pickClickReaction 吐出池外动作 ${picked}`);
        assert.notStrictEqual(picked, last, `pickClickReaction 重复了上一次动作 ${last}`);
    }
    // 全部被排除时仍要有合法兜底
    const all = CLICK_POOL.map(x => x.action);
    const fallback = pickClickReaction(() => 0.99, all, CLICK_POOL);
    assert.ok(pool.has(fallback), '全排除时应回退到池内动作');
});

test('B2 6 个点击动作在随机触发下都可达 (不是永远只出同一个)', () => {
    const seen = new Set();
    for (let i = 0; i < 3000; i++) {
        seen.add(pickClickReaction(Math.random, [], CLICK_POOL));
    }
    assert.strictEqual(seen.size, CLICK_POOL.length,
        `只有 ${seen.size}/${CLICK_POOL.length} 个动作可达: ${[...seen].join(',')}`);
});

test('B3 权重生效: 高权重动作出现频率更高 (不是等概率)', () => {
    const counts = new Map();
    for (let i = 0; i < 6000; i++) {
        const a = pickClickReaction(Math.random, [], CLICK_POOL);
        counts.set(a, (counts.get(a) || 0) + 1);
    }
    const heart = counts.get('cheer_heart') || 0;
    const jump = counts.get('cheer_jump') || 0;
    assert.ok(heart > jump, `权重 3 的 cheer_heart (${heart}) 应多于权重 2 的 cheer_jump (${jump})`);
});

// ====== C. 场景道具 ======
test('C1 14 个道具文件齐全 (R156 8 + R158 爱心 + R167 键盘 + R170 吃水果 2 + R172 办公转椅/显示器), 场景登记的 back/front 道具都在库里', () => {
    assert.ok(PROPS.enabled, 'manifest 的 props 段必须启用');
    // R158: 在 R156 的 7 个道具基础上新增 prop_heart (比心爱心特效)
    // R165: 新增 prop_desk_surface (办公桌台面, back 层) ⇒ 道具 8 → 9
    // R167: 新增 prop_keyboard (办公键盘, back 层) ⇒ 道具 9 → 10
    // R170: 新增 prop_stool / prop_fruit_table (吃水果场景) ⇒ 道具 10 → 12
    // R172: 新增 prop_office_chair / prop_office_monitor (办公构图重做) ⇒ 道具 12 → 14
    assert.strictEqual(Object.keys(PROPS_LIB).length, 14,
        `应有 14 个道具, 实际 ${Object.keys(PROPS_LIB).length}: ${Object.keys(PROPS_LIB).join(',')}`);
    for (const need of ['prop_bed', 'prop_quilt', 'prop_moon', 'prop_sofa',
                        'prop_chair', 'prop_desk', 'prop_desk_surface',
                        'prop_keyboard', 'prop_screen_glow', 'prop_heart',
                        'prop_stool', 'prop_fruit_table',
                        'prop_office_chair', 'prop_office_monitor']) {
        assert.ok(PROPS_LIB[need], `道具库缺少 ${need}`);
    }
    for (const [name, spec] of Object.entries(PROPS_LIB)) {
        assert.ok(spec.file, `道具 ${name} 缺 file`);
        assert.ok(fs.existsSync(path.join(ASSETS, spec.file)), `道具文件缺失: ${spec.file}`);
        assert.ok(spec.desc, `道具 ${name} 缺 desc`);
    }
    assert.ok(Object.keys(PROPS_SCENES).length >= 5,
        `至少要有 5 个道具场景 (睡觉/坐下/打盹/办公...), 实际 ${Object.keys(PROPS_SCENES).length}`);
    for (const [action, scene] of Object.entries(PROPS_SCENES)) {
        assert.ok(typeof scene.floor_tex_y === 'number' && scene.floor_tex_y > 0,
            `场景 ${action} 缺 floor_tex_y`);
        for (const n of (scene.back || []).concat(scene.front || [])) {
            assert.ok(PROPS_LIB[n], `场景 ${action} 引用了未登记的道具 ${n}`);
        }
        // R158: 允许"纯 front 层特效"场景 (比心的爱心特效只有 front 层, 没有 back 层道具)
        if (!(scene.back || []).length) {
            assert.ok((scene.front || []).length > 0,
                `场景 ${action} 既没有 back 层也没有 front 层道具`);
            assert.ok(/特效/.test(scene.desc || ''),
                `场景 ${action} 没有 back 层道具时, 说明必须写清是纯特效`);
            continue;
        }
    }
});

test('C2 front 层道具不得侵入脸部区域 (不挡脸) — 用真实像素包围盒判定', () => {
    for (const [action, scene] of Object.entries(PROPS_SCENES)) {
        for (const n of (scene.front || [])) {
            const bb = alphaBBox(PROPS_LIB[n].file);
            assert.ok(bb, `道具 ${n} 是空图`);
            const overlapX = Math.min(bb[2], FACE_BOX.x1) - Math.max(bb[0], FACE_BOX.x0);
            const overlapY = Math.min(bb[3], FACE_BOX.y1) - Math.max(bb[1], FACE_BOX.y0);
            const hit = overlapX > 0 && overlapY > 0;
            assert.ok(!hit,
                `场景 ${action} 的 front 道具 ${n} 侵入脸部区域 (bbox=${bb.join(',')}) → 会挡脸`);
        }
    }
});

test('C3 睡觉有床 + 月亮, 坐下有沙发, 办公有转椅 + 可见内容的显示器 (R172 构图重做)', () => {
    const sleep = PROPS_SCENES.sleep_breath;
    assert.ok(sleep, '缺少 sleep_breath 道具场景 (睡觉必须有场景)');
    const sleepAll = (sleep.back || []).concat(sleep.front || []);
    assert.ok(sleepAll.includes('prop_bed'), '睡觉场景必须有床');
    assert.ok(sleepAll.includes('prop_moon'), '睡觉场景必须有月亮/夜晚氛围');
    const sit = PROPS_SCENES.sit_rest;
    assert.ok(sit, '缺少 sit_rest 道具场景 (坐下必须有场景)');
    assert.ok((sit.back || []).includes('prop_sofa'), '坐下场景必须有小沙发');
    const work = PROPS_SCENES.work;
    assert.ok(work, '缺少 work 道具场景 (办公必须有场景)');
    const workAll = (work.back || []).concat(work.front || []);
    // R172: 办公场景换了图层归属 —— 桌面/键盘/手画进角色帧, 场景里只留
    //       back=办公转椅, front=3/4 显示器 (R167 的"笔记本背板"被淘汰)。
    assert.ok(workAll.includes('prop_office_chair'), '办公场景必须有办公转椅');
    assert.ok(workAll.includes('prop_office_monitor'), '办公场景必须有显示器');
    assert.ok((work.back || []).includes('prop_office_chair'), '办公转椅必须在 back 层 (人坐在椅子上)');
    assert.ok((work.front || []).includes('prop_office_monitor'), '显示器必须在 front 层 (挡住桌沿才对)');
    // 显示器必须**真的有屏幕内容** (R172 的核心诉求: 不能再是笔记本背板)
    const mon = decodePNG(path.join(ASSETS, PROPS_LIB.prop_office_monitor.file));
    let bright = 0, dark = 0;
    for (let i = 0; i + 3 < mon.data.length; i += 4) {
        if (mon.data[i + 3] < 40) continue;
        const lum = (mon.data[i] + mon.data[i + 1] + mon.data[i + 2]) / 3;
        if (lum > 150) bright++;
        if (lum < 90) dark++;
    }
    assert.ok(bright >= 2000, `显示器屏幕必须有亮色界面内容 (实际亮像素 ${bright})`);
    assert.ok(dark >= 500, `显示器必须有深色边框/底座 (实际深色像素 ${dark})`);
});

test('C4 道具与角色帧在两种画布下都**零裁切** (用生产布局算法核算)', () => {
    const bboxes = MANIFEST.layout.frame_bboxes;
    const frames = [];
    for (const [action, spec] of Object.entries(MANIFEST.actions)) {
        (bboxes[action] || []).forEach((bb, i) => {
            frames.push({
                action, index: i, bbox: bb,
                ground_tex_y: Array.isArray(spec.ground_tex_y)
                    ? spec.ground_tex_y[i] : (spec.ground_tex_y || null),
            });
        });
    }
    for (const [action, spec] of Object.entries(LIB_ACTIONS)) {
        (bboxes[action] || []).forEach((bb, i) => {
            frames.push({
                action, index: i, bbox: bb,
                ground_tex_y: Array.isArray(spec.ground_tex_y)
                    ? spec.ground_tex_y[i] : (spec.ground_tex_y || null),
            });
        });
    }
    for (const [w, h] of [[200, 240], [256, 256]]) {
        const layout = computeLayout({
            canvasW: w, canvasH: h, textureW: 1024, textureH: 1024, frames,
        });
        // 角色帧: 内容矩形必须在画布内
        for (const f of frames) {
            const r = layout.rectsByAction[f.action][f.index];
            const g = layout.groundTexYByAction[f.action][f.index];
            const base = (typeof g === 'number') ? g : r.bottom;
            const s = layout.scale;
            const top = layout.groundY + s * (r.top - base);
            const bottom = layout.groundY + s * (r.bottom - base);
            const left = layout.x + s * (r.left - 512);
            const right = layout.x + s * (r.right - 512);
            assert.ok(top >= -0.5, `${w}x${h} ${f.action}[${f.index}] 顶部越界 top=${top.toFixed(2)}`);
            assert.ok(bottom <= h + 0.5, `${w}x${h} ${f.action}[${f.index}] 底部越界 bottom=${bottom.toFixed(2)}`);
            assert.ok(left >= -0.5, `${w}x${h} ${f.action}[${f.index}] 左越界 left=${left.toFixed(2)}`);
            assert.ok(right <= w + 0.5, `${w}x${h} ${f.action}[${f.index}] 右越界 right=${right.toFixed(2)}`);
        }
        // 道具: 用场景的地面行定位, 也必须在画布内
        for (const [action, scene] of Object.entries(PROPS_SCENES)) {
            const propY = groundRowY(layout, scene.floor_tex_y, 0);
            for (const n of (scene.back || []).concat(scene.front || [])) {
                const bb = alphaBBox(PROPS_LIB[n].file);
                const left = layout.x + layout.scale * (bb[0] - 512);
                const right = layout.x + layout.scale * (bb[2] - 512);
                const top = propY + layout.scale * (bb[1] - 921.6);
                const bottom = propY + layout.scale * (bb[3] - 921.6);
                assert.ok(left >= -0.5, `${w}x${h} 场景 ${action} 的道具 ${n} 左越界 left=${left.toFixed(2)}`);
                assert.ok(right <= w + 0.5, `${w}x${h} 场景 ${action} 的道具 ${n} 右越界 right=${right.toFixed(2)}`);
                assert.ok(top >= -0.5, `${w}x${h} 场景 ${action} 的道具 ${n} 顶越界 top=${top.toFixed(2)}`);
                assert.ok(bottom <= h + 0.5, `${w}x${h} 场景 ${action} 的道具 ${n} 底越界 bottom=${bottom.toFixed(2)}`);
            }
        }
    }
});

test('C5 有道具的动作, 角色踩在道具底上 (地面行 == 场景地面行)', () => {
    for (const [action, scene] of Object.entries(PROPS_SCENES)) {
        const spec = (MANIFEST.actions[action] || LIB_ACTIONS[action] || {});
        const g = spec.ground_tex_y;
        const gv = Array.isArray(g) ? g[0] : g;
        assert.strictEqual(gv, scene.floor_tex_y,
            `动作 ${action} 的 ground_tex_y (${gv}) 与场景地面行 (${scene.floor_tex_y}) 不一致 → 角色会陷进或悬空`);
    }
});

test('C6 腾空帧真的离地 (地面行高于脚底, 且离地量可量化)', () => {
    const spec = LIB_ACTIONS.cheer_jump;
    assert.ok(Array.isArray(spec.ground_tex_y) && spec.ground_tex_y.length === 3,
        'cheer_jump 的 ground_tex_y 必须是逐帧数组');
    const [g0, g1, g2] = spec.ground_tex_y;
    assert.strictEqual(g0, null, '蓄力帧应站在地面 (ground_tex_y=null)');
    assert.strictEqual(g2, null, '落地帧应站在地面 (ground_tex_y=null)');
    assert.ok(typeof g1 === 'number' && g1 > 987, `腾空帧的地面行 ${g1} 应高于脚底 987`);
    // 离地量换算成屏幕像素 (200x240 画布)
    const frames = [];
    for (const [action, sp] of Object.entries(LIB_ACTIONS)) {
        (MANIFEST.layout.frame_bboxes[action] || []).forEach((bb, i) => {
            frames.push({
                action, index: i, bbox: bb,
                ground_tex_y: Array.isArray(sp.ground_tex_y) ? sp.ground_tex_y[i] : (sp.ground_tex_y || null),
            });
        });
    }
    const layout = computeLayout({ canvasW: 200, canvasH: 240, textureW: 1024, textureH: 1024, frames });
    const bb = MANIFEST.layout.frame_bboxes.cheer_jump[1];
    const g = layout.groundTexYByAction.cheer_jump[1];
    const footY = layout.groundY + layout.scale * (bb[3] - g);
    const lift = layout.groundY - footY;
    // 离地量的上限由**窗口高度**决定: standard 模式 (256x256) 角色头顶只剩 11px 余量,
    // 离地必须 ≤7 屏幕 px 才不会顶出画布 → 这里断言"确实离地"而不是某个夸张数值。
    assert.ok(lift > 4, `腾空帧离地仅 ${lift.toFixed(1)}px (应 >4px, 否则完全看不出离地)`);
    assert.ok(lift < 60, `腾空帧离地 ${lift.toFixed(1)}px 过大 (会顶出画布)`);
});

// ====== D. 办公待机 (行为引擎) ======
test('D1 行为引擎有 WORK 状态, 且映射到 work 动作', () => {
    assert.ok(STATES.WORK, 'STATES 缺少 WORK');
    const engine = new BehaviorEngine({ config: { ...DEFAULT_CONFIG } });
    assert.strictEqual(engine.getState(), STATES.IDLE);
    const spec = ACTION_CATALOG.work;
    assert.ok(spec, 'work 未登记进 ACTION_CATALOG');
    assert.strictEqual(spec.kind, 'rest', 'work 应是 rest 类 (待机类)');
});

test('D2 办公待机的权重/时长/冷却按真机实测重标定, 且不与其它活动连着做', () => {
    // R170 改判据的依据 (不是"为了让测试变绿"而是**改的是产品行为**):
    //   R170 真机实测: 真实 Electron 连跑 180s, 空闲决策只有 9 次, WORK 触发 **0 次**
    //   ⇒ 用户真机看到的就是"电脑办公场景消失不见了"。
    //   根因: work_probability=0.10 在总权重 2.00 里只占 5% 命中率, 而长活动把
    //   空闲决策压到 ~20s 一次 ⇒ 期望 ~6.7 分钟才出现一次, 每次只有 9~19s。
    //   R170 重标定: 权重抬到 0.55 (命中率 ~22%), 时长 16~28s, 冷却 60s。
    //   下界保证"一定会出现"(≥0.3), 上界保证"不会一直只办公"(≤0.75),
    //   "不连着做"改由**冷却期**保证 (不只是"上一项是同类就归零")。
    assert.ok(DEFAULT_CONFIG.work_probability >= 0.30,
        `办公待机权重 ${DEFAULT_CONFIG.work_probability} 太低 (需 ≥0.30, 否则真机 180s 触发 0 次)`);
    assert.ok(DEFAULT_CONFIG.work_probability <= 0.75,
        `办公待机权重 ${DEFAULT_CONFIG.work_probability} 偏高 (需 ≤0.75, 避免一直只办公)`);
    assert.ok(DEFAULT_CONFIG.work_min_ms >= 12000,
        `办公单次持续 ${DEFAULT_CONFIG.work_min_ms}ms 太短 (需 ≥12s, 否则"刚出现就消失")`);
    assert.ok(DEFAULT_CONFIG.work_max_ms > DEFAULT_CONFIG.work_min_ms,
        '办公时长区间不合法');
    assert.ok(DEFAULT_CONFIG.work_cooldown_ms >= 30000,
        `办公冷却 ${DEFAULT_CONFIG.work_cooldown_ms}ms 太短 (需 ≥30s, 避免"一直只办公")`);
    assert.ok(ACTIVITY_KINDS.includes('work'), '活动池里必须有 work');
    // 连续两次都选到 work 的概率应为 0 (上一项是 work 时权重直接归零)
    let consecutive = 0;
    const trials = 4000;
    for (let i = 0; i < trials; i++) {
        const engine = new BehaviorEngine({
            config: { ...DEFAULT_CONFIG },
            random: () => 0.999,   // 落在随机区间末端 = sleep/work 段
        });
        engine._lastActivity = 'work';
        const kind = engine._pickActivity();
        if (kind === 'work') consecutive++;
    }
    assert.strictEqual(consecutive, 0, `上一项是 work 时仍选到 work ${consecutive} 次 (应恒为 0)`);
    // R170 新增: 冷却期内不得再选到 work (真机观感: 刚放下电脑又坐下 ⇒ 场景像坏了)
    let inCooldown = 0;
    for (let i = 0; i < trials; i++) {
        const engine = new BehaviorEngine({
            config: { ...DEFAULT_CONFIG },
            random: () => 0.999,
            now: () => 1000,      // 距上次办公 1s < 冷却 60s
        });
        engine._lastActivity = 'gesture';
        engine._lastWorkAt = 1000;
        if (engine._pickActivity() === 'work') inCooldown++;
    }
    assert.strictEqual(inCooldown, 0, `冷却期内仍选到 work ${inCooldown} 次 (应恒为 0)`);
});

// R170: 活动池的随机阈值**从引擎自己的权重反推** (不写死数字)
//   —— R170 给活动池加了 eat_fruit 一类并重标定了 work 权重, 写死的随机值会落到别的段上
//   (D3 曾经因此进了 EAT_FRUIT 而不是 WORK)。反推后新增活动不会再打坏旧用例。
const ACTIVITY_W_KEY = {
    gesture: 'gesture_probability', walk: 'walk_probability', sit: 'sit_probability',
    doze: 'doze_probability', work: 'work_probability', eat_fruit: 'eat_fruit_probability',
    sleep: 'sleep_probability',
};
function randomForKind(kind, cfg) {
    const c = cfg || DEFAULT_CONFIG;
    const total = ACTIVITY_KINDS.reduce((s, k) => s + (c[ACTIVITY_W_KEY[k]] || 0), 0);
    let acc = 0;
    for (const k of ACTIVITY_KINDS) {
        const w = c[ACTIVITY_W_KEY[k]] || 0;
        if (k === kind) return (acc + w / 2) / total;
        acc += w;
    }
    throw new Error(`未知活动类别 ${kind}`);
}

test('D3 引擎能进入 WORK 状态, 下发 work 动作, 结束后回到 idle', () => {
    const actions = [];
    const states = [];
    let timerFn = null;
    const engine = new BehaviorEngine({
        config: { ...DEFAULT_CONFIG, idle_min_ms: 10, idle_max_ms: 10, work_min_ms: 50, work_max_ms: 50 },
        random: () => randomForKind('work'),   // 落在 work 段 (阈值从配置反推)
        now: () => 0,
        setTimeout: (fn) => { timerFn = fn; return 1; },
        clearTimeout: () => { timerFn = null; },
        onAction: (a) => actions.push(a),
        onState: (from, to) => states.push(to),
    });
    engine.start();
    // 推进到"下一次决策"
    assert.ok(timerFn, '引擎未排定 idle 计时器');
    timerFn();
    assert.strictEqual(engine.getState(), STATES.WORK, `应进入 WORK 状态, 实际 ${engine.getState()}`);
    assert.ok(actions.includes('work'), `应下发 work 动作, 实际动作序列 ${JSON.stringify(actions)}`);
    // 办公结束 → 回到 idle
    timerFn();
    assert.strictEqual(engine.getState(), STATES.IDLE, `办公结束应回 idle, 实际 ${engine.getState()}`);
    assert.ok(actions[actions.length - 1] === 'idle', '办公结束应下发 idle');
});

// ====== E. 诚实性 ======
test('E1 素材做不到的动作仍在"需要新素材"清单里 (不得硬标完成)', () => {
    const descs = NEEDS_NEW_ASSETS.map(x => `${x.action}`).join(',');
    // R158: wave_hand 已由 arm_rig 真实实现 (cheer_wave)、clap_hands 已由 arm_rig 真实实现 (cheer_clap)
    // ⇒ 这两项不再需要新素材, 已从清单移除; 仍然做不到的必须留在清单里 (不得硬标完成)
    for (const need of ['heart_hands_true', 'typing', 'spin_180']) {
        assert.ok(descs.includes(need), `需新素材清单缺少 ${need}`);
    }
    assert.ok(!descs.includes('wave_hand'),
        'wave_hand 已由 R158 的 cheer_wave 真实实现, 不应再标为需新素材');
    assert.ok(!descs.includes('clap_hands'),
        'clap_hands 已由 R158 的 cheer_clap 真实实现, 不应再标为需新素材');
    for (const item of NEEDS_NEW_ASSETS) {
        assert.ok(!ACTION_CATALOG[item.action],
            `${item.action} 既标为需新素材, 又出现在已实现动作表里 (自相矛盾)`);
    }
});

test('E2 点击动作的说明里如实标注了做不到的部分 (比心可读性上限 / 转身缺背面素材)', () => {
    const heart = LIB_ACTIONS.cheer_heart.desc;
    // R158: 比心不再是"近似的手放胸前", 但必须如实写明"手指级心形在显示尺寸不可读"
    assert.ok(/不可读/.test(heart) || /如实说明/.test(heart),
        'cheer_heart 的说明必须如实写明手指级比心在桌宠显示尺寸下不可读');
    assert.ok(/爱心特效/.test(heart), 'cheer_heart 的说明必须写明用了爱心特效');
    // R158: cheer_spin 已下架 (水平压缩冒充转身) ⇒ 转身必须留在"需要新素材"清单里
    assert.ok(!LIB_ACTIONS.cheer_spin, 'cheer_spin 必须下架 (R158 禁止用压缩冒充转身)');
    const spinNeed = NEEDS_NEW_ASSETS.find(x => x.action === 'spin_180');
    assert.ok(spinNeed, '真正的 180° 背面转身必须留在需新素材清单里');
    assert.ok(/背面素材/.test(spinNeed.desc), 'spin_180 必须写明缺的是背面素材');
    const work = LIB_ACTIONS.work.desc;
    assert.ok(/屏幕/.test(work) || /电脑/.test(work), 'work 的说明必须写清是"在电脑前办公"');
});

test('E3 素材边界如实登记在烘焙报告里', () => {
    const rep = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R156', 'bake_report.json'), 'utf8'));
    assert.ok(Array.isArray(rep.material_limits) && rep.material_limits.length >= 3,
        '烘焙报告必须登记 ≥3 条素材边界');
    const text = rep.material_limits.join(' ');
    assert.ok(/手部素材/.test(text), '素材边界必须提到"无手部素材"');
    assert.ok(/转身/.test(text), '素材边界必须提到"转身不是背面"');
});

// ====== F. 既有资产门禁不变 ======
test('F1 核心 6 组仍是 23 个互不相同的帧文件, R138 原始字节未变', () => {
    const all = [];
    for (const action of MANIFEST.animation_order) all.push(...MANIFEST.actions[action].frames);
    assert.strictEqual(all.length, 23, `核心帧槽位应为 23, 实际 ${all.length}`);
    assert.strictEqual(new Set(all).size, 23, '23 个帧槽位必须互不相同');
    const baseline = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R138_derived', 'r138_source_checksums.json'), 'utf8'));
    for (const [rel, want] of Object.entries(baseline.files)) {
        const p = path.join(ASSETS, rel);
        if (!fs.existsSync(p)) continue;
        assert.strictEqual(sha256(p), want, `R138 原始帧被改动: ${rel}`);
    }
});

test('F2 道具段不改动任何角色帧 (道具是独立 PNG, 不覆盖角色素材)', () => {
    const propFiles = Object.values(PROPS_LIB).map(s => s.file);
    for (const f of propFiles) {
        // R158: 道具允许放在 character_R156/ (R156 的 7 个) 或 character_R158/ (R158 的爱心特效)
        // R172: 新增 character_R172/ (办公转椅 + 3/4 显示器)
        assert.ok(f.startsWith('character_R156/') || f.startsWith('character_R158/')
            || f.startsWith('character_R172/'),
            `道具 ${f} 必须放在 character_R156/ / character_R158/ / character_R172/ 目录`);
        assert.ok(fs.existsSync(path.join(ASSETS, f)), `道具缺失 ${f}`);
    }
    for (const action of MANIFEST.animation_order) {
        for (const f of MANIFEST.actions[action].frames) {
            assert.ok(!propFiles.includes(f), `核心动作 ${action} 误引用了道具文件 ${f}`);
        }
    }
});

// ====== 汇总 ======
const passed = results.filter(r => r.pass).length;
const failed = results.filter(r => !r.pass).length;
console.log('');
console.log(`R156 点击互动 + 场景道具 + 办公待机测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
if (failed > 0) {
    console.log('\n失败详情:');
    for (const r of results.filter(x => !x.pass)) console.log(`  - ${r.name}: ${r.error}`);
    process.exit(1);
}
process.exit(0);
