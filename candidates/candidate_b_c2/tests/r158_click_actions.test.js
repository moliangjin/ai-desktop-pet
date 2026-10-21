// R158 点击互动视觉质量 — 专项单元测试
//
// 覆盖 R158 任务书里**可自动化**的硬约束:
//
//   1. 点击互动池 ≥5 种"视觉上明确、动作含义清晰"的互动 (实际 6 种)
//   2. **禁止用压缩/平移/重命名冒充新动作** ⇒ 用**客观像素判据**逐条否证:
//      · 头身宽度比 (否证整体水平压缩)
//      · 头部水平质心位移 (否证整体水平平移)
//      · 手臂区/胸前区的像素级内容变化 (证明"手真的动了", 而不是只改了脸)
//   3. 6 个动作两两像素级不同, 且与 R138/R153/R156 既有帧都不重复
//   4. R138 原始 23 帧 SHA256 未变 (回归防线)
//   5. 18 张新帧在 200x240 / 256x256 下零裁切 (用生产布局算法核算)
//   6. 爱心特效道具齐全且不遮脸
//   7. 诚实性: 做不到的"背面转身"必须留在需新素材清单, 并有精确的新素材需求
//
// 判定不依赖坐标符号、动画名或本测试自身的 PASS —— 全部基于**真实像素**。

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const crypto = require('crypto');

const CAND = path.join(__dirname, '..');
const ASSETS = path.join(CAND, 'assets');
const MANIFEST = JSON.parse(fs.readFileSync(path.join(ASSETS, 'character_R141_manifest.json'), 'utf8'));

const {
    ACTION_CATALOG, CLICK_POOL, NEEDS_NEW_ASSETS, pickClickReaction,
} = require(path.join(CAND, 'src', 'action_library.js'));
const { computeLayout } = require(path.join(CAND, 'src', 'sprite_layout.js'));
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

const LIB_ACTIONS = (MANIFEST.action_library || {}).actions || {};
const PROPS = MANIFEST.props || {};
const PROPS_LIB = PROPS.library || {};
const PROPS_SCENES = PROPS.scenes || {};
const CLICK = MANIFEST.click_reactions || {};

const R158_ACTIONS = ['cheer_wave', 'cheer_hands_up', 'cheer_heart', 'cheer_clap',
    'cheer_jump', 'cheer_tilt'];
// R156 的几何形变动作 —— R158 规则下必须全部下架
const BANNED_ACTIONS = ['cheer_spin', 'cheer_sway', 'cheer_wink', 'cheer_hands'];

const BASE = 'character_R138/idle/idle_00_base.png';

// ---------------------------------------------------------------- 像素工具
function load(rel) {
    return decodePNG(path.join(ASSETS, rel));
}
function solidCount(img, x0, y0, x1, y1) {
    let n = 0;
    for (let y = y0; y < y1; y++) {
        if (y < 0 || y >= img.height) continue;
        for (let x = x0; x < x1; x++) {
            if (x < 0 || x >= img.width) continue;
            if (img.data[(y * img.width + x) * 4 + 3] > 40) n++;
        }
    }
    return n;
}
/** 肤色像素计数 (手部/脸部) */
function skinCount(img, x0, y0, x1, y1) {
    let n = 0;
    for (let y = y0; y < y1; y++) {
        if (y < 0 || y >= img.height) continue;
        for (let x = x0; x < x1; x++) {
            if (x < 0 || x >= img.width) continue;
            const i = (y * img.width + x) * 4;
            const R = img.data[i], G = img.data[i + 1], B = img.data[i + 2];
            if (img.data[i + 3] > 40 && R > 200 && G > 165 && B < 228 && (R - B) > 18) n++;
        }
    }
    return n;
}
/**
 * 胸区 (纹理 x400-640, y320-500) 里**两只手之间的空隙** (纹理 px)。
 * 做法: 取该区内的肤色像素, 做 8 邻域连通块标记, 找出**最靠左**与**最靠右**
 * 的两块 (各 ≥150px) 之间的水平间距; 若两块相接/重叠则返回 0。
 * 这就是"鼓掌"的客观定义 —— 两掌分开 vs 两掌贴合。
 */
function handGap(img) {
    // R165 修正测量盒 (意图不变: 仍然是"两掌之间的空隙"):
    //   旧盒 (400,320)-(640,500) 太窄 —— 合拢帧的手在胸口、 张开帧的手更靠外更低,
    //   手被盒边界裁掉后连通块只剩 1 个, 间距恒为 0, 判据对"真的没张开"和
    //   "张开但手在盒外"无法区分 (R165 实测: 用新盒时 a_s=±40/a_e=±96 的
    //   两掌间距 = 78px, 与 R162 当时记录的量级一致)。
    const X0 = 380, Y0 = 300, X1 = 660, Y1 = 560;
    const W = X1 - X0, H = Y1 - Y0;
    const on = new Uint8Array(W * H);
    for (let y = Y0; y < Y1; y++) {
        for (let x = X0; x < X1; x++) {
            const i = (y * img.width + x) * 4;
            const R = img.data[i], G = img.data[i + 1], B = img.data[i + 2];
            if (img.data[i + 3] > 40 && R > 200 && G > 165 && B < 228 && (R - B) > 18) {
                on[(y - Y0) * W + (x - X0)] = 1;
            }
        }
    }
    const seen = new Uint8Array(W * H);
    const comps = [];
    for (let s = 0; s < on.length; s++) {
        if (!on[s] || seen[s]) continue;
        const stack = [s]; seen[s] = 1; let n = 0, lo = 1e9, hi = -1, y0 = 1e9;
        while (stack.length) {
            const p = stack.pop();
            const py = (p / W) | 0, px = p - py * W;
            n++; if (px < lo) lo = px; if (px > hi) hi = px;
            if (py < y0) y0 = py;
            for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
                const ny = py + dy, nx = px + dx;
                if (ny < 0 || ny >= H || nx < 0 || nx >= W) continue;
                const q = ny * W + nx;
                if (on[q] && !seen[q]) { seen[q] = 1; stack.push(q); }
            }
        }
        // R165: 排除**脸/脖子**块 —— 测量盒放宽后下巴/脖子也进了盒,
        //   它们与"手"无关, 会造出一个假的大间距。
        if (n >= 150 && y0 + Y0 >= 400) comps.push({ n, lo, hi });
    }
    if (comps.length < 2) return 0;
    comps.sort((a, b) => a.lo - b.lo);
    const left = comps[0], right = comps[comps.length - 1];
    if (left === right) return 0;
    return Math.max(0, right.lo - left.hi);
}
/** 角色**实心像素总面积** —— 整体水平压缩会等比缩小它, 旋转/平移不会。 */
function areaOf(img) {
    let n = 0;
    for (let i = 3; i < img.data.length; i += 4) if (img.data[i] > 40) n++;
    return n;
}
/** 脚底 (纹理 y 870..1000) 的实心像素中心 x —— 整体水平平移会移动它,
 *  头部旋转 / 手臂抬起 / 跳跃压扁 (支点在脚底) 都不会。 */
function feetCenter(img) {
    let lo = Infinity, hi = -Infinity, n = 0, sx = 0;
    for (let y = 870; y < 1000 && y < img.height; y++) {
        for (let x = 0; x < img.width; x++) {
            if (img.data[(y * img.width + x) * 4 + 3] > 40) {
                if (x < lo) lo = x;
                if (x > hi) hi = x;
                sx += x; n++;
            }
        }
    }
    if (!n) return null;
    return { lo, hi, cx: sx / n };
}
/** 头顶冠部 (纹理 y=60 一行) 上包含 x=512 的连续实心段。
 *  选这一行的原因: 抬手/举臂的手最��只到 y≈180, 绝不会进 y=60 这一行,
 *  所以这一行只量到"头/头发", 不会被抬起的手臂干扰。
 *  整体水平压缩会改变这一段的宽度; 整体水平平移会改变这一段的中心 —— 两者都能被客观测到。 */
function crownRow(img, y = 60) {
    const row = (x) => img.data[(y * img.width + x) * 4 + 3] > 40;
    if (!row(512)) return null;
    let lo = 512, hi = 512;
    while (lo - 1 >= 0 && row(lo - 1)) lo--;
    while (hi + 1 < img.width && row(hi + 1)) hi++;
    return { lo, hi, w: hi - lo, cx: (lo + hi) / 2 };
}
/** 头部区域 (纹理 y 37..340) 的包围盒 —— 用于"头身宽度比"与"头部水平质心" */
function headBox(img) {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (let y = 30; y < 340; y++) {
        for (let x = 0; x < img.width; x++) {
            if (img.data[(y * img.width + x) * 4 + 3] > 40) {
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
            }
        }
    }
    if (minX === Infinity) return null;
    return { minX, maxX, minY, maxY, w: maxX - minX, cx: (minX + maxX) / 2 };
}
/** 整幅剪影的左右边界 */
function silhouetteWidth(img) {
    let minX = Infinity, maxX = -Infinity;
    for (let y = 0; y < img.height; y++) {
        for (let x = 0; x < img.width; x++) {
            if (img.data[(y * img.width + x) * 4 + 3] > 40) {
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
            }
        }
    }
    return maxX - minX;
}
/** 两帧的像素差异占比 */
function diffRatio(a, b) {
    let diff = 0, total = 0;
    for (let i = 0; i < a.data.length; i += 4) {
        const av = a.data[i + 3] > 40, bv = b.data[i + 3] > 40;
        if (av || bv) {
            total++;
            if (av !== bv) { diff++; continue; }
            if (Math.abs(a.data[i] - b.data[i]) > 24 || Math.abs(a.data[i + 1] - b.data[i + 1]) > 24
                || Math.abs(a.data[i + 2] - b.data[i + 2]) > 24) diff++;
        }
    }
    return total ? diff / total : 0;
}

const BASE_IMG = load(BASE);
const BASE_HEAD = headBox(BASE_IMG);
const BASE_CROWN = crownRow(BASE_IMG);
const R158_FRAMES = R158_ACTIONS.flatMap((a) => LIB_ACTIONS[a].frames);

// ======================================================================
// A. 点击池构成
// ======================================================================
test('A1 点击互动池 = 6 种 R158 真实动作, 且不含被禁的几何形变动作', () => {
    const pool = CLICK_POOL.map((p) => p.action);
    assert.strictEqual(pool.length, 6, `点击池应为 6 个动作, 实际 ${pool.length}: ${pool}`);
    for (const a of R158_ACTIONS) {
        assert.ok(pool.includes(a), `点击池缺少 ${a}`);
    }
    for (const b of BANNED_ACTIONS) {
        assert.ok(!pool.includes(b), `${b} 必须下架 (R158 禁止用压缩/平移/重命名冒充新动作)`);
        assert.ok(!ACTION_CATALOG[b], `${b} 不应再出现在已实现动作表里`);
    }
});

test('A2 点击池与运行时 action_library 的 CLICK_POOL 完全一致 (生产代码与测试同一份)', () => {
    assert.deepStrictEqual(CLICK_POOL.map((p) => p.action),
        CLICK.pool.map((p) => p.action), 'src/action_library.js 与 manifest 的点击池不一致');
    assert.ok(CLICK.no_repeat_last, '点击池必须"短时间内不重复上一次"');
});

test('A3 随机触发: 6 个动作都可达, 且不重复最近一次', () => {
    let seed = 12345;
    const rng = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
    const seen = new Set();
    let last = null;
    for (let i = 0; i < 400; i++) {
        const a = pickClickReaction(rng, last);
        assert.ok(R158_ACTIONS.includes(a), `随机到了池外动作 ${a}`);
        assert.notStrictEqual(a, last, '不应连续两次同一个动作');
        seen.add(a);
        last = a;
    }
    assert.strictEqual(seen.size, 6, `6 个动作都应可达, 实际只触达 ${seen.size} 个`);
});

// ======================================================================
// B. 帧资源与唯一性
// ======================================================================
test('B1 6 个动作 × 3 帧 = 18 张新帧全部存在且为 1024x1024 RGBA', () => {
    assert.strictEqual(R158_FRAMES.length, 18, `应有 18 张新帧, 实际 ${R158_FRAMES.length}`);
    for (const rel of R158_FRAMES) {
        const p = path.join(ASSETS, rel);
        assert.ok(fs.existsSync(p), `帧缺失: ${rel}`);
        const img = decodePNG(p);
        assert.strictEqual(img.width, 1024, `${rel} 宽度应为 1024`);
        assert.strictEqual(img.height, 1024, `${rel} 高度应为 1024`);
    }
});

test('B2 每个动作的 3 帧"开始/中间/结束"彼此不同 (像素级)', () => {
    for (const a of R158_ACTIONS) {
        const [f0, f1, f2] = LIB_ACTIONS[a].frames;
        const i0 = load(f0), i1 = load(f1), i2 = load(f2);
        assert.ok(diffRatio(i0, i1) > 0.004, `${a}: 第 0/1 帧差异过小 (${diffRatio(i0, i1).toFixed(4)})`);
        assert.ok(diffRatio(i1, i2) > 0.004, `${a}: 第 1/2 帧差异过小 (${diffRatio(i1, i2).toFixed(4)})`);
        assert.ok(diffRatio(i0, i2) > 0.004, `${a}: 第 0/2 帧差异过小`);
    }
});

test('B3 18 张新帧两两不同, 且与 R138/R153/R156 既有帧都不同 (像素级)', () => {
    const olds = [];
    for (const d of ['character_R138', 'character_R153', 'character_R156']) {
        const dir = path.join(ASSETS, d);
        if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) continue;
        for (const fn of fs.readdirSync(dir)) {
            if (fn.endsWith('.png')) olds.push(`${d}/${fn}`);
        }
    }
    const newImgs = R158_FRAMES.map((rel) => ({ rel, img: load(rel) }));
    for (let i = 0; i < newImgs.length; i++) {
        for (let j = i + 1; j < newImgs.length; j++) {
            const r = diffRatio(newImgs[i].img, newImgs[j].img);
            assert.ok(r > 0.002,
                `新帧重复: ${newImgs[i].rel} vs ${newImgs[j].rel} 差异仅 ${r.toFixed(4)}`);
        }
        for (const o of olds) {
            const r = diffRatio(newImgs[i].img, load(o));
            assert.ok(r > 0.002,
                `新帧与既有帧重复: ${newImgs[i].rel} vs ${o} 差异仅 ${r.toFixed(4)}`);
        }
    }
});

test('B4 R138 原始 23 帧 SHA256 与基线完全一致 (回归防线)', () => {
    const base = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R138_derived', 'r138_source_checksums.json'), 'utf8'));
    const keys = Object.keys(base.files);
    assert.strictEqual(keys.length, 23, `基线应含 23 帧, 实际 ${keys.length}`);
    for (const rel of keys) {
        const p = path.join(ASSETS, rel);
        assert.ok(fs.existsSync(p), `源帧缺失: ${rel}`);
        assert.strictEqual(sha256(p), base.files[rel], `源帧被改动: ${rel}`);
    }
    // 23 个帧槽位也必须互不相同 (R148 资产门禁口径不变)
    const slots = [];
    for (const a of MANIFEST.animation_order) slots.push(...MANIFEST.actions[a].frames);
    assert.strictEqual(slots.length, 23, `帧槽位应为 23, 实际 ${slots.length}`);
    assert.strictEqual(new Set(slots).size, 23, '23 个帧槽位必须互不相同');
});

// ======================================================================
// C. 反"压缩/平移/重命名冒充"的客观判据
// ======================================================================
test('C1 无整体水平压缩: 每个动作 3 帧的实心面积中位数与基准帧偏差 <15% (R156 的 cheer_spin 中位帧是 64%)', () => {
    const baseArea = areaOf(BASE_IMG);
    // R165 修正判据的**度量方式** (意图不变: 仍然否证"用整体压缩冒充新动作"):
    //   跳跃动作 cheer_jump 的三帧是**故意纵向压扁**的 (蓄力 0.80 / 腾空 1.0 / 落地 0.84),
    //   实心面积本来就该按同样的比例变小 —— 实测中位帧 182192 / 基准 214814 = 0.848,
    //   与 scale_y=0.84 几乎一致 (说明没有额外的水平压缩)。
    //   旧口径直接拿面积比基准, 于是把"合法的纵向压扁"误判成"整体压缩"。
    //   修正: 面积比要先除掉该动作的纵向压扁系数, 再看是否偏离 1。
    const report = JSON.parse(fs.readFileSync(
        path.join(ASSETS, 'character_R158', 'bake_report.json'), 'utf8'));
    const scaleOf = {};
    for (const it of report.items) {
        if (!it.file || !it.file.endsWith('.png')) continue;
        scaleOf[it.file] = (it.scale_y === null || it.scale_y === undefined) ? 1.0 : it.scale_y;
    }
    for (const a of R158_ACTIONS) {
        const files = LIB_ACTIONS[a].frames;
        const rows = files.map((f) => {
            const base = f.split('/').pop();
            return { area: areaOf(load(f)), scale: scaleOf[base] || 1.0 };
        }).sort((x, y) => x.area - y.area);
        const med = rows[1];
        const ratio = med.area / (baseArea * med.scale);
        assert.ok(Math.abs(ratio - 1) < 0.15,
            `${a}: 面积中位数 ${med.area} (纵向压扁系数 ${med.scale}) 与基准 ${baseArea} `
            + `偏差 ${((ratio - 1) * 100).toFixed(1)}% → 疑似整体压缩`);
    }
});

test('C2 无整体水平平移: 每个动作任一帧的脚底中心位移 <24 纹理 px (R156 的 cheer_sway 移了 46)', () => {
    const baseFeet = feetCenter(BASE_IMG);
    assert.ok(baseFeet, '基准帧脚底为空');
    for (const a of R158_ACTIONS) {
        for (const f of LIB_ACTIONS[a].frames) {
            const fc = feetCenter(load(f));
            assert.ok(fc, `${f} 脚底为空`);
            const d = Math.abs(fc.cx - baseFeet.cx);
            assert.ok(d < 24,
                `${f}: 脚底中心位移 ${d.toFixed(1)}px → 疑似整体平移`);
        }
    }
});

test('C3 cheer_wave: 右臂真的抬到了头侧 (手臂区像素从空变为有内容)', () => {
    // 基准帧里 R 臂垂在身侧 (x≤690), 头右侧 x[706,800] y[180,300] 区域必然是空的
    const before = solidCount(BASE_IMG, 706, 180, 800, 300);
    assert.strictEqual(before, 0, '基准帧该区域本应为空, 前提被破坏');
    for (const rel of LIB_ACTIONS.cheer_wave.frames) {
        const n = solidCount(load(rel), 706, 180, 800, 300);
        assert.ok(n > 200, `cheer_wave ${rel}: 头右侧手臂区只有 ${n} 个实心像素 → 手臂没抬起来`);
    }
});

test('C4 cheer_hands_up: 两条手臂都举高 (左右两侧**高处**都出现手部肤色)', () => {
    // R162 修正判据: 旧判据用固定矩形 (x210-300 / x720-810, y200-320) 当地基,
    //   手臂骨架重标定后手臂整体外移了十几个像素, 矩形只擦到手臂边缘 ⇒ 假失败
    //   (实测 R162 hands_up_1 左臂明明举着, 左臂举起区实心像素却只有 0)。
    //   改用**与坐标无关**的判据: 抬手时手是**皮肤**, 且必然高于头部下缘。
    //   ⇒ 判"y<300 且在左右两侧"是否都出现了皮肤像素。
    //   基准帧里手垂在髋部 (y>560), 所以这个判据不会被基准帧污染。
    //   注意要**避开脸的两侧脸颊**: 底图里脸颊肤色一直延伸到 x391 / x633,
    //   所以两翼只能取 x200-380 / x644-830 (那里底图 y<300 必定没有肤色,
    //   实测底图 0 像素), 而举起的手恰好落在这两翼里 (x273-375 / x649-751)。
    const skinAbove = (img, x0, x1) => skinCount(img, x0, 0, x1, 300);
    assert.strictEqual(skinAbove(BASE_IMG, 200, 380), 0, '基准帧左侧高处本应无手部肤色');
    assert.strictEqual(skinAbove(BASE_IMG, 644, 830), 0, '基准帧右侧高处本应无手部肤色');
    for (const rel of LIB_ACTIONS.cheer_hands_up.frames) {
        const img = load(rel);
        const l = skinAbove(img, 200, 380);
        const r = skinAbove(img, 644, 830);
        assert.ok(l > 300, `cheer_hands_up ${rel}: 左侧高处手部肤色只有 ${l} px → 左臂没举起来`);
        assert.ok(r > 300, `cheer_hands_up ${rel}: 右侧高处手部肤色只有 ${r} px → 右臂没举起来`);
    }
});

test('C5 cheer_heart: 手真的到了胸前 (胸前区的肤色像素大幅增加)', () => {
    const before = skinCount(BASE_IMG, 450, 400, 580, 520);
    for (const rel of LIB_ACTIONS.cheer_heart.frames) {
        const n = skinCount(load(rel), 450, 400, 580, 520);
        assert.ok(n > before + 150,
            `cheer_heart ${rel}: 胸前肤色像素 ${n} 相对基准 ${before} 增量不足 → 手没到胸前`);
    }
});

test('C6 cheer_clap: 双手**张开→合拢** (两只手之间的间距明显收窄并贴合)', () => {
    // R162 修正判据: 旧判据是"张开帧的**剪影宽度**比合拢帧大 60px",
    //   那对应的是 R158 旧参数 (a_s=±30/a_e=-34) —— 那是"双臂平举"而不是鼓掌,
    //   而且 6 个动作里"比心"和"鼓掌"两个帧几乎长得一样。
    //   R162 把鼓掌改成"手心相对、领口高度张开→合拢"后, 剪影宽度本来就不该差 60px。
    //   改用**鼓掌本身的定义**来判定: 胸区两只手之间的**空隙**必须显著收窄。
    //   实测 (纹理 px): 张开帧两掌间距 ≈78, 合拢帧 ≈0 (两掌相接连成一块)。
    const [f0, f1, f2] = LIB_ACTIONS.cheer_clap.frames;
    const gap0 = handGap(load(f0));
    const gap1 = handGap(load(f1));
    const gap2 = handGap(load(f2));
    assert.ok(gap0 >= 40,
        `cheer_clap 张开帧两掌间距只有 ${gap0.toFixed(1)}px → 根本没有"张开"`);
    assert.ok(gap1 <= gap0 - 25,
        `cheer_clap 合拢帧间距 ${gap1.toFixed(1)}px 应比张开帧 ${gap0.toFixed(1)}px 小 25px 以上`);
    assert.ok(gap2 >= 40,
        `cheer_clap 第三帧两掌间距只有 ${gap2.toFixed(1)}px → 没有"张开→合拢→张开"`);
});

test('C7 cheer_jump: 蓄力帧被压扁, 腾空帧靠 ground_tex_y 离地, 且腾空帧双臂上扬', () => {
    const spec = LIB_ACTIONS.cheer_jump;
    assert.ok(Array.isArray(spec.ground_tex_y) && spec.ground_tex_y.length === 3,
        'cheer_jump 的 ground_tex_y 必须是逐帧数组');
    const [g0, g1, g2] = spec.ground_tex_y;
    assert.strictEqual(g0, null, '蓄力帧应站在地面');
    assert.strictEqual(g2, null, '落地帧应站在地面');
    assert.ok(typeof g1 === 'number' && g1 > 987, `腾空帧地面行 ${g1} 应高于脚底 987`);
    // 压扁: 蓄力帧的剪影高度明显小于基准帧
    const baseH = BASE_IMG.height;
    const hCrouch = (() => {
        const img = load(LIB_ACTIONS.cheer_jump.frames[0]);
        let minY = Infinity, maxY = -Infinity;
        for (let y = 0; y < img.height; y++) {
            for (let x = 0; x < img.width; x++) {
                if (img.data[(y * img.width + x) * 4 + 3] > 40) {
                    if (y < minY) minY = y; if (y > maxY) maxY = y;
                }
            }
        }
        return maxY - minY;
    })();
    const baseBB = MANIFEST.layout.frame_bboxes.idle[0];
    const baseH2 = baseBB[3] - baseBB[1];
    assert.ok(hCrouch < baseH2 * 0.92,
        `蓄力帧高度 ${hCrouch} 应明显小于基准 ${baseH2} → 没有压扁对比`);
    // 腾空帧双臂上扬
    const air = load(LIB_ACTIONS.cheer_jump.frames[1]);
    assert.ok(solidCount(air, 210, 200, 300, 320) > 120, '腾空帧左臂没有上扬');
    assert.ok(solidCount(air, 720, 200, 810, 320) > 120, '腾空帧右臂没有上扬');
});

test('C8 cheer_tilt: 头部真的歪了 (头部包围盒左右边界随帧变化)', () => {
    const boxes = LIB_ACTIONS.cheer_tilt.frames.map((f) => headBox(load(f)));
    const centers = boxes.map((b) => b.cx);
    const widths = boxes.map((b) => b.w);
    assert.ok(Math.abs(centers[0] - centers[2]) > 3,
        `歪头帧与轻歪头帧的头部质心差 ${Math.abs(centers[0] - centers[2]).toFixed(1)}px → 头没歪`);
    assert.ok(Math.max(...widths) > Math.min(...widths),
        '歪头帧与轻歪头帧的头部宽度应有差异 (旋转后的包围盒)');
});

// ======================================================================
// D. 布局: 零裁切
// ======================================================================
test('D1 全部帧 (含 18 张新帧) 在 200x240 与 256x256 下零裁切', () => {
    const frames = [];
    for (const a of MANIFEST.animation_order) {
        MANIFEST.actions[a].frames.forEach((f, i) => frames.push({ action: a, index: i, bbox: null }));
    }
    // 用 manifest 里记录的实测 bbox 构造布局输入 (与 34_R156_runtime_verify 同一口径)
    const bb = MANIFEST.layout.frame_bboxes;
    const all = [];
    for (const a of MANIFEST.animation_order) {
        MANIFEST.actions[a].frames.forEach((f, i) => {
            all.push({ action: a, index: i, bbox: bb[a][i], skew_x: 0 });
        });
    }
    for (const a of Object.keys(LIB_ACTIONS)) {
        const gspec = LIB_ACTIONS[a].ground_tex_y;
        LIB_ACTIONS[a].frames.forEach((f, i) => {
            if (!bb[a] || !bb[a][i]) return;
            const g = Array.isArray(gspec) ? gspec[i] : gspec;
            all.push({
                action: a, index: i, bbox: bb[a][i], skew_x: 0,
                ground_tex_y: (typeof g === 'number') ? g : null,
            });
        });
    }
    for (const [w, h] of [[200, 240], [256, 256]]) {
        const layout = computeLayout({ canvasW: w, canvasH: h, textureW: 1024, textureH: 1024, frames: all });
        for (const f of all) {
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
    }
});

test('D2 腾空帧真的离地 (屏幕像素, 用生产布局算法核算)', () => {
    const all = [];
    const bb = MANIFEST.layout.frame_bboxes;
    for (const a of Object.keys(LIB_ACTIONS)) {
        const gspec = LIB_ACTIONS[a].ground_tex_y;
        LIB_ACTIONS[a].frames.forEach((f, i) => {
            if (!bb[a] || !bb[a][i]) return;
            const g = Array.isArray(gspec) ? gspec[i] : gspec;
            all.push({
                action: a, index: i, bbox: bb[a][i], skew_x: 0,
                ground_tex_y: (typeof g === 'number') ? g : null,
            });
        });
    }
    const layout = computeLayout({ canvasW: 256, canvasH: 256, textureW: 1024, textureH: 1024, frames: all });
    const g = layout.groundTexYByAction.cheer_jump[1];
    const r = layout.rectsByAction.cheer_jump[1];
    const footY = layout.groundY + layout.scale * (r.bottom - g);
    const lift = layout.groundY - footY;
    assert.ok(lift > 3, `腾空帧离地量 ${lift.toFixed(2)} 屏幕 px, 应 >3`);
    // 离地量不得超过窗口高度允许的上限 (头顶不越界)
    const headTop = layout.groundY + layout.scale * (r.top - g);
    assert.ok(headTop >= -0.5, `腾空帧头顶越界 top=${headTop.toFixed(2)}`);
});

// ======================================================================
// E. 爱心特效道具
// ======================================================================
test('E1 prop_heart 存在, 是有效 PNG, 且有实际内容', () => {
    assert.ok(PROPS_LIB.prop_heart, '道具库缺少 prop_heart');
    const p = path.join(ASSETS, PROPS_LIB.prop_heart.file);
    assert.ok(fs.existsSync(p), `prop_heart 文件缺失: ${PROPS_LIB.prop_heart.file}`);
    const img = decodePNG(p);
    assert.strictEqual(img.width, 1024, 'prop_heart 纹理尺寸应为 1024');
    let n = 0;
    for (let i = 3; i < img.data.length; i += 4) if (img.data[i] > 40) n++;
    assert.ok(n > 2000, `prop_heart 有效像素只有 ${n} → 几乎是空图`);
});

test('E2 比心场景登记完整: 有 front 层特效, 地面行与动作一致, 特效不遮脸', () => {
    const scene = PROPS_SCENES.cheer_heart;
    assert.ok(scene, '缺少 cheer_heart 的道具场景');
    assert.ok((scene.front || []).includes('prop_heart'), 'cheer_heart 场景必须有 prop_heart');
    assert.strictEqual(scene.floor_tex_y, LIB_ACTIONS.cheer_heart.ground_tex_y,
        '场景地面行与动作 ground_tex_y 必须一致');
    // 不遮脸: 脸部区域 y[37,330] 的特效像素必须为 0
    const img = decodePNG(path.join(ASSETS, PROPS_LIB.prop_heart.file));
    const inFace = solidCount(img, 380, 37, 660, 330);
    assert.strictEqual(inFace, 0, `prop_heart 侵入了脸部区域 (${inFace}px)`);
});

test('E3 R156 的 7 个道具与场景原样保留 (本轮不重做场景)', () => {
    for (const n of ['prop_bed', 'prop_quilt', 'prop_moon', 'prop_sofa',
        'prop_chair', 'prop_desk', 'prop_screen_glow']) {
        assert.ok(PROPS_LIB[n], `R156 的道具 ${n} 被删掉了`);
        assert.ok(fs.existsSync(path.join(ASSETS, PROPS_LIB[n].file)), `道具文件缺失: ${PROPS_LIB[n].file}`);
    }
    for (const s of ['sleep_breath', 'sleep_loop', 'sit_rest', 'doze', 'work']) {
        assert.ok(PROPS_SCENES[s], `R156 的场景 ${s} 被删掉了`);
    }
    assert.ok(LIB_ACTIONS.work, 'R156 的 work 办公待机动作必须保留');
});

// ======================================================================
// F. 诚实性: 做不到的必须如实登记
// ======================================================================
test('F1 真正的背面转身仍在"需要新素材"清单, 且没有被任何动作冒充', () => {
    const need = NEEDS_NEW_ASSETS.find((x) => x.action === 'spin_180');
    assert.ok(need, 'spin_180 必须留在需新素材清单');
    assert.ok(/背面素材/.test(need.desc), 'spin_180 必须写明缺的是背面素材');
    assert.ok(!LIB_ACTIONS.cheer_spin, 'cheer_spin 必须下架');
    const r158 = MANIFEST.r158_click_actions;
    assert.ok(r158 && Array.isArray(r158.new_asset_requests), 'manifest 必须登记新素材需求');
    const turn = r158.new_asset_requests.find((x) => x.action === 'cheer_turn_180');
    assert.ok(turn, '必须登记"真正的原地 180° 转身"的新素材需求');
    assert.ok(/背面/.test(turn.need + turn.spec), '转身需求必须写明需要背面视图');
    assert.ok(turn.spec && /1024/.test(turn.spec), '转身需求必须给出分辨率/帧数规格');
    assert.ok(turn.acceptance, '转身需求必须给出验收口径');
});

test('F2 手指级比心的可读性上限被如实登记 (不得虚报"真比心")', () => {
    const need = NEEDS_NEW_ASSETS.find((x) => x.action === 'heart_hands_true');
    assert.ok(need, 'heart_hands_true 必须留在需新素材清单');
    assert.ok(/不可读|显示尺寸/.test(need.desc + need.note || ''),
        '必须如实写明手指级比心在显示尺寸下不可读');
    const heart = LIB_ACTIONS.cheer_heart.desc;
    assert.ok(/不可读/.test(heart), 'cheer_heart 的描述必须如实写明手指级比心不可读');
    assert.ok(/爱心特效/.test(heart), 'cheer_heart 的描述必须写明用了爱心特效');
});

test('F3 素材可行性结论被记录 (R138 有手部素材 / 全库无背面素材)', () => {
    const r158 = MANIFEST.r158_click_actions;
    assert.ok(r158 && Array.isArray(r158.asset_feasibility), '必须登记素材可行性评估');
    const txt = r158.asset_feasibility.join(' ');
    assert.ok(/手部素材/.test(txt) && /漏切/.test(txt),
        '必须如实写明 R153/R156 的"无手部素材"结论是错的 (R138 切层脚本漏切)');
    assert.ok(/只有\*\*正面\*\*素材|只有正面素材/.test(txt),
        '必须如实写明全库只有正面素材');
});

// ======================================================================
// G. 反"髋部虚线鬼影" —— 抬手后原手轮廓必须彻底消失 (R158 交付前自检抓到并修掉的缺陷)
// ======================================================================
//
// 判据 (全部基于真实像素, 不看动作名):
//   1. 在底图里取"手的皮肤外沿 5 纹理 px 以内"的带 = 手的描边所在位置
//      (实测几何: 手的描边就画在皮肤外沿 0~4 px; 大褂门襟竖线离皮肤 ≥6 px)
//   2. 该带里底图为暗色 (lum<230, 含抗锯齿浅晕) 且**新帧里仍是暗色不透明**的像素
//      ⇒ 就是没擦干净的**原手轮廓残留** (肉眼看到的那圈虚线)
//   3. 只检查"这一帧真的动了手的那一侧" —— 没动的那侧手还在髋部, 轮廓是正常的
//   4. 整体竖向压缩的帧 (跳跃蓄力/落地) 跳过: 身体像素整体移位, 无法与未缩放的底图同坐标比对
//
// 阈值: ≤60 像素/帧。干净基线实测 22 (大褂门襟线的正常残留), 修复前实测 169 ⇒ 判 FAIL。

const BAKE_REPORT = JSON.parse(fs.readFileSync(
    path.join(ASSETS, 'character_R158', 'bake_report.json'), 'utf8'));
const HAND_ZONES = {
    L: [328, 572, 390, 676],
    R: [620, 572, 700, 676],
};
/** 放宽肤色判定 (与 36_R158_arm_rig.py 的 skin_relaxed **同口径**:
 *  Al>60, R>=195, G>=160, B>=140, (R-B)>=12, (R-G)>=-8
 *  —— 判据必须一致, 否则测出来的"带"会偏宽, 把大褂门襟误判成手的描边) */
function skinLoose(img) {
    const m = new Uint8Array(img.width * img.height);
    for (let y = 0; y < img.height; y++) {
        for (let x = 0; x < img.width; x++) {
            const i = (y * img.width + x) * 4;
            if (img.data[i + 3] <= 60) continue;
            const R = img.data[i], G = img.data[i + 1], B = img.data[i + 2];
            if (R >= 195 && G >= 160 && B >= 140 && (R - B) >= 12 && (R - G) >= -8) {
                m[y * img.width + x] = 1;
            }
        }
    }
    return m;
}
/** 膨胀 (4 邻域 / 曼哈顿距离) —— 必须与 36_R158_arm_rig.py 的 dilate() **同口径**,
 *  否则测出来的"带"会比修复逻辑里的更宽, 把大褂门襟误判成手的描边 (实测踩过) */
function dilateMask(m, w, h, r) {
    let cur = m;
    for (let k = 0; k < r; k++) {
        const out = new Uint8Array(w * h);
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                if (!cur[y * w + x]) continue;
                out[y * w + x] = 1;
                if (y > 0) out[(y - 1) * w + x] = 1;
                if (y + 1 < h) out[(y + 1) * w + x] = 1;
                if (x > 0) out[y * w + x - 1] = 1;
                if (x + 1 < w) out[y * w + x + 1] = 1;
            }
        }
        cur = out;
    }
    return cur;
}
function lumOf(img, x, y) {
    const i = (y * img.width + x) * 4;
    return 0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2];
}

test('G1 抬手后髋部没有残留的原手轮廓 (虚线鬼影), 且大褂门襟未被误伤', () => {
    const base = load(BASE);
    const baseSkin = skinLoose(base);
    const w = base.width, h = base.height;
    // 每侧: 手的皮肤外沿 5px 带 (= 手的描边位置), 以及底图里该带的暗像素
    const sideBand = {};
    for (const side of ['L', 'R']) {
        const [zx0, zy0, zx1, zy1] = HAND_ZONES[side];
        const skin = new Uint8Array(w * h);
        for (let y = zy0; y < zy1; y++) {
            for (let x = zx0; x < zx1; x++) {
                if (baseSkin[y * w + x]) skin[y * w + x] = 1;
            }
        }
        const near = dilateMask(skin, w, h, 5);
        const band = new Uint8Array(w * h);
        for (let y = zy0; y < zy1; y++) {
            for (let x = zx0; x < zx1; x++) {
                const i = y * w + x;
                if (near[i] && !skin[i]) band[i] = 1;
            }
        }
        sideBand[side] = band;
    }

    const GHOST_MAX = 60;   // 干净基线 22, 修复前 169
    let worst = 0;
    for (const item of BAKE_REPORT.items) {
        if (!item.file.endsWith('.png')) continue;
        if (item.file.startsWith('prop_')) continue;
        const scale = item.scale_y;
        if (scale !== null && scale !== undefined && Math.abs(scale - 1) > 1e-6) continue;
        const sides = Object.keys(item.pose || {});
        if (!sides.length) continue;
        const img = load(`character_R158/${item.file}`);
        for (const side of sides) {
            const band = sideBand[side];
            let n = 0;
            for (let y = 0; y < h; y++) {
                for (let x = 0; x < w; x++) {
                    if (!band[y * w + x]) continue;
                    const bi = (y * base.width + x) * 4;
                    if (base.data[bi + 3] <= 40) continue;                 // 底图这里本来就是透明
                    if (lumOf(base, x, y) >= 230) continue;              // 底图这里不是暗线
                    const i = (y * img.width + x) * 4;
                    if (img.data[i + 3] <= 40) continue;                // 已擦成透明 ✔
                    if (lumOf(img, x, y) >= 230) continue;                // 已擦成亮色 ✔
                    n++;
                }
            }
            worst = Math.max(worst, n);
            assert.ok(n <= GHOST_MAX,
                `${item.file} (${side}): 原手轮廓残留 ${n} 像素 → 髋部出现虚线鬼影 (门槛 ${GHOST_MAX})`);
        }
    }
    // R165 修正元检查的**度量方式** (意图不变: 判据本身必须能测到东西):
    //   旧写法是"当前这 18 帧里最坏帧残留必须 > 0" —— 那等于要求**缺陷必须存在**,
    //   缺陷真被修好之后判据反而"失效"。R165 把缺陷修干净后残留就是 0。
    //   正确做法: 拿一张**已知坏样本**当输入自检判据是否有效 —— 这里用底图本身
    //   (底图没做任何修复 ⇒ 原手轮廓描边必然还在), 判据必须测得到。
    let selftest = 0;
    {
        const band = sideBand['L'];
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                if (!band[y * w + x]) continue;
                const bi = (y * base.width + x) * 4;
                if (base.data[bi + 3] <= 40) continue;
                if (lumOf(base, x, y) >= 230) continue;
                selftest++;
            }
        }
    }
    assert.ok(selftest > GHOST_MAX,
        `判据自检失败: 拿底图当"未修复帧"时只测到 ${selftest} px (门槛 ${GHOST_MAX}) `
        + '→ 判据本身失效, 测不出东西');
    console.log(`      ↳ 最坏帧残留 ${worst} px (门槛 ${GHOST_MAX}); 判据自检(底图当坏样本) ${selftest} px`);
});

test('G2 修复动作必须落在 arm_rig 里 (鬼影修复不能只靠手工改图)', () => {
    const src = fs.readFileSync(path.join(CAND, '36_R158_arm_rig.py'), 'utf8');
    // R162: 衣身还原机制整体重写 —— 旧的"大褂外缘之外整段清透明"换成了
    //   "按**实测接缝线**重建衣身边缘 + 保留底图剪影描边带"。
    //   断言随之更新为检查新机制的关键标记 (仍然要求修复落在 arm_rig 里)。
    assert.ok(/SEAM_L|seam_x/.test(src),
        'arm_rig 必须包含"按实测接缝线 (seam) 重建衣身边缘"的逻辑');
    assert.ok(/OUT_KEEP/.test(src),
        'arm_rig 必须保留底图剪影描边带 (否则衣身边缘会退化成虚线)');
    assert.ok(/near_skin|skin_relaxed/.test(src),
        'arm_rig 必须用"紧贴手部皮肤"的几何判据来清原手轮廓');
});

// ======================================================================
test('汇总', () => {
    const passed = results.filter((r) => r.pass).length;
    const failed = results.length - passed;
    console.log(`\nR158 点击互动视觉质量测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
    if (failed) {
        for (const r of results.filter((x) => !x.pass)) console.log(`  ❌ ${r.name}: ${r.error}`);
    }
    process.exitCode = failed ? 1 : 0;
});
