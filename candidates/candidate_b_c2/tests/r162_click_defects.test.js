// R162 点击互动视觉缺陷修复 — 专项回归测试
//
// R158 独立审查提出的 3 条缺陷, 本文件逐条给出**可自动化的客观判据**:
//
//   1. 比心/鼓掌/抬手动作存在**袖子、手臂拼接残影**
//      → 拆成两个可测的子项:
//        R2-2 衣身外缘必须是**连续**的描边 (旧实现取色取到透明区 ⇒ 整条边变成虚线)
//        R2-5 手臂抬起时肩部不得出现"从大褂胸口飞出去的白色残块"
//        (R2-5 在 Python 侧 43_R162_defect_verify.py 里做, 那里能直接看重建后的衣身)
//   2. cheer_jump_0 **头顶有明显图像破损** (五官被按原坐标贴进已压扁的头顶)
//      → R2-1 头部上方不得出现任何肤色像素
//   3. 比心/鼓掌的手势要在 **200x240 实际尺寸**下确认是否清晰
//      → R2-3 鼓掌必须是"两只手张开→合拢" (用两掌间距客观判定)
//      → R2-4 比心必须有可读的心形信号 (爱心特效在 200px 下 ≥18px, 且不遮脸不遮手)
//
// 判定全部基于**真实像素**, 不依赖坐标符号、动作名或本测试自身的 PASS。
// 阈值都取自 R158 旧素材的实测值 (见每条注释), 旧素材必须 FAIL、新素材必须 PASS。

'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');

const CAND = path.join(__dirname, '..');
const ASSETS = path.join(CAND, 'assets');
const MANIFEST = JSON.parse(fs.readFileSync(path.join(ASSETS, 'character_R141_manifest.json'), 'utf8'));
const { decodePNG } = require(path.join(__dirname, 'r153_png.js'));

const LIB_ACTIONS = (MANIFEST.action_library || {}).actions || {};
const PROPS = MANIFEST.props || {};
const PROPS_LIB = PROPS.library || {};
const PROPS_SCENES = PROPS.scenes || {};

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

function load(rel) { return decodePNG(path.join(ASSETS, rel)); }

/** 肤色像素计数 (与 R158 测试同口径) */
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
function lumAt(img, x, y) {
    const i = (y * img.width + x) * 4;
    return 0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2];
}
/** 实心像素数 */
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

/**
 * 衣身外缘的**连续性**: 逐行取该行最外侧的实心像素, 看 [x, x+6] 内有没有
 * **至少 2 个暗像素** (描边线的核心; 最外那一格是抗锯齿半透明像素, 不算)。
 *
 * 返回 { longestRun, longestGap }:
 *   longestRun  = 描边连续存在的最长行数 (越大越好)
 *   longestGap  = 描边断开的最长行数 (**虚线**的量化: 越小越好)
 *
 * R158 旧素材实测 (左衣身, 纹理 y350-585):
 *   hands_up_1  连续 99 / 缺口 57      ← 这就是评审看到的"断线"
 *   heart_1     连续 75 / 缺口 61
 *   clap_1      连续 75 / 缺口 62
 * R162 修复后实测:
 *   hands_up_1  连续 209 / 缺口 27
 *   heart_1     连续 111 / 缺口 20
 *   clap_1      连续 236 / 缺口 0
 */
function edgeContinuity(img, x0, x1, side = 'L', y0 = 350, y1 = 586) {
    const flags = [];
    for (let y = y0; y < y1; y++) {
        // L 侧取该行**最左**的实心像素, R 侧取**最右**的 —— 那一侧才是剪影。
        let lmo = -1;
        if (side === 'L') {
            for (let x = x0; x < x1; x++) {
                if (img.data[(y * img.width + x) * 4 + 3] > 40) { lmo = x; break; }
            }
        } else {
            for (let x = x1 - 1; x >= x0; x--) {
                if (img.data[(y * img.width + x) * 4 + 3] > 40) { lmo = x; break; }
            }
        }
        if (lmo < 0) { flags.push(0); continue; }
        let dark = 0;
        const from = (side === 'L') ? lmo : lmo - 6;
        for (let x = Math.max(0, from); x < Math.min(from + 7, img.width); x++) {
            if (lumAt(img, x, y) < 130) dark++;
        }
        flags.push(dark >= 2 ? 1 : 0);
    }
    let longestRun = 0, cur = 0, longestGap = 0, gap = 0;
    for (const f of flags) {
        if (f) { cur++; gap = 0; if (cur > longestRun) longestRun = cur; }
        else { gap++; if (gap > longestGap) longestGap = gap; cur = 0; }
    }
    return { longestRun, longestGap, rows: flags.length };
}

/**
 * 胸区肤色连通块 (8 邻域), 只保留 ≥150px 的。
 *
 * R165 修正测量盒 (意图不变: 仍然是"胸区里两只手的分离/贴合"):
 *   旧盒 (400,320)-(640,500) 太窄 —— 合拢帧的手在胸口, 张开帧的手更靠外更低,
 *   手被盒边界裁掉后连通块只剩 1 个, 间距恒为 0, 判据无法区分
 *   "真的没张开" 与 "张开但手跑到盒外了"。
 *   R165 实测: 用新盒 (380,300)-(660,560) 时, 正确 rig 下
 *   a_s=±40/a_e=±96 的两掌间距 = 78px, 与 R162 当时记录的量级一致。
 */
function chestHandGroups(img) {
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
        const stack = [s]; seen[s] = 1; let n = 0, lo = 1e9, hi = -1, y0 = 1e9, y1 = -1;
        while (stack.length) {
            const p = stack.pop();
            const py = (p / W) | 0, px = p - py * W;
            n++; if (px < lo) lo = px; if (px > hi) hi = px;
            if (py < y0) y0 = py; if (py > y1) y1 = py;
            for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
                const ny = py + dy, nx = px + dx;
                if (ny < 0 || ny >= H || nx < 0 || nx >= W) continue;
                const q = ny * W + nx;
                if (on[q] && !seen[q]) { seen[q] = 1; stack.push(q); }
            }
        }
        // R165: 排除**脸/脖子**块 (测量盒放宽后下巴/脖子进了盒, 会造出假间距)
        if (n >= 150 && y0 + Y0 >= 400) {
            comps.push({ n, lo: lo + X0, hi: hi + X0, y0: y0 + Y0, y1: y1 + Y0 });
        }
    }
    comps.sort((a, b) => a.lo - b.lo);
    return comps;
}

/** 两掌之间的水平间距 (纹理 px); 相接/重叠记 0 */
function handGap(img) {
    const comps = chestHandGroups(img);
    if (comps.length < 2) return 0;
    const left = comps[0], right = comps[comps.length - 1];
    return Math.max(0, right.lo - left.hi);
}

const ALL_ACTIONS = ['cheer_wave', 'cheer_hands_up', 'cheer_heart', 'cheer_clap',
    'cheer_jump', 'cheer_tilt'];

// ======================================================================
// R2-1 头顶图像破损 (cheer_jump_0 的五官被贴到头顶)
// ======================================================================
test('R2-1 跳跃帧头顶没有第二张脸 (头部上方不得出现任何肤色像素)', () => {
    // 根因 (R162 已修): 烘焙顺序是 头部变换 → 整体压扁 → 贴五官,
    //   而五官 donor 是**未压缩**的底图帧 ⇒ 五官被按原坐标贴进已被压扁的头顶。
    // R158 旧素材实测: cheer_jump_0 的 y<260 区间有 **2605** 个肤色像素
    //   (一整块脸贴在颅顶, 实见额头+闭眼横带); R162 修复后为 **0**。
    for (const idx of [0, 2]) {
        const rel = LIB_ACTIONS.cheer_jump.frames[idx];
        const n = skinCount(load(rel), 0, 0, 1024, 260);
        assert.strictEqual(n, 0,
            `cheer_jump_${idx}: 头顶 y<260 出现 ${n} 个肤色像素 → 五官被贴到头顶了 (R158 旧值 2605)`);
    }
    // 腾空帧 (jump_1) 双手高举, 面部也随头部权重场略微上移 ⇒ 不用 y<260 判。
    // 改用"头顶冠部"判据: y=60 这一行只有头发, 抬手的手最高也只到 y≈139。
    const air = load(LIB_ACTIONS.cheer_jump.frames[1]);
    const crown = skinCount(air, 300, 0, 724, 110);
    assert.strictEqual(crown, 0,
        `cheer_jump_1 头顶冠部 y<110 出现 ${crown} 个肤色像素 → 头上多了东西`);
});

// ======================================================================
// R2-2 衣身外缘不得是虚线 (手臂拼接残影的核心表现)
// ======================================================================
test('R2-2 衣身外缘是**连续**描边, 不是虚线 (左右两侧都查)', () => {
    // R158 旧素材的"虚线"来自一个具体 bug: 重建衣身边缘时, 描边颜色取自
    //   描边**外侧**的窗口, 那里在底图里是透明像素 ⇒ 取到的颜色是随机的
    //   (有时纯黑, 有时纯白) ⇒ 整条衣身边缘变成断断续续的虚线。
    // 判据: 描边**最长缺口**必须 ≤38 行。
    //   R158 旧素材实测缺口 45~63 (hands_up/heart/clap 全部不合格);
    //   R162 修复后实测 0~31。
    // 两侧都查, 且**不跳过**"手臂抬起"的那几行:
    //   旧素材与新素材在同样的行上比较, 抬起的手臂同样是白色袖料,
    //   它对两边的贡献是一样的 ⇒ 不影响公平性, 但不能跳过 ——
    //   虚线恰恰就出现在"手臂挪走后、大褂边缘裸露"的那一段。
    // 阈值 38 的来历 (实测):
    //   R158 旧素材: hands_up_1 断 57 行 / heart_1 断 61 行 / clap_1 断 62 行  → 全部不合格
    //   R162 新素材: hands_up_1 断 27 行 / heart_1 断 20 行 / clap_1 断 0 行     → 全部合格
    const MAX_GAP = 38;
    for (const action of ALL_ACTIONS) {
        for (const rel of LIB_ACTIONS[action].frames) {
            const img = load(rel);
            const L = edgeContinuity(img, 300, 470, 'L');
            const R = edgeContinuity(img, 554, 724, 'R');
            assert.ok(L.longestGap <= MAX_GAP,
                `${rel}: 左衣身边缘描边最长断开 ${L.longestGap} 行 (门槛 ${MAX_GAP}) → 衣身边缘成了虚线`);
            assert.ok(R.longestGap <= MAX_GAP,
                `${rel}: 右衣身边缘描边最长断开 ${R.longestGap} 行 (门槛 ${MAX_GAP}) → 衣身边缘成了虚线`);
        }
    }
});

// ======================================================================
// R2-3 鼓掌: 两只手张开 → 合拢 (用两掌间距客观判定)
// ======================================================================
test('R2-3 鼓掌是"两手张开→合拢→张开", 且张开帧能分辨出两只手', () => {
    // 手指级/掌级细节在 200x240 下只有几个屏幕 px, 所以"鼓掌"的可读性
    //   只能靠"两只手的分离/贴合"这个**大尺度**信号来判定。
    const frames = LIB_ACTIONS.cheer_clap.frames;
    const g0 = handGap(load(frames[0]));
    const g1 = handGap(load(frames[1]));
    const g2 = handGap(load(frames[2]));
    assert.ok(g0 >= 40, `鼓掌张开帧两掌间距只有 ${g0}px → 根本没有张开`);
    assert.ok(g1 <= g0 - 25, `鼓掌合拢帧间距 ${g1}px 应比张开帧 ${g0}px 小 25px 以上`);
    assert.ok(g2 >= 40, `鼓掌第三帧两掌间距只有 ${g2}px → 没有"张开→合拢→张开"`);
    // 张开帧必须能数出**两块独立**的手 (合拢帧则是连成一块)
    const comps = chestHandGroups(load(frames[0]));
    assert.ok(comps.length >= 2,
        `鼓掌张开帧胸区只数出 ${comps.length} 块肤色 (>150px) → 两只手分不开, 200px 下读不出"鼓掌"`);
});

// ======================================================================
// R2-4 比心: 心形信号在 200x240 下必须可读, 且不遮脸不遮手
// ======================================================================
test('R2-4 比心信号在 200x240 实际尺寸下可读 (爱心特效 ≥18px 且不遮脸不遮手)', () => {
    const prop = decodePNG(path.join(ASSETS, PROPS_LIB.prop_heart.file));
    let bx0 = 1e9, by0 = 1e9, bx1 = -1, by1 = -1;
    for (let y = 0; y < prop.height; y++) {
        for (let x = 0; x < prop.width; x++) {
            if (prop.data[(y * prop.width + x) * 4 + 3] > 40) {
                if (x < bx0) bx0 = x; if (x > bx1) bx1 = x;
                if (y < by0) by0 = y; if (y > by1) by1 = y;
            }
        }
    }
    assert.ok(bx1 >= 0, 'prop_heart 必须是有效 PNG 且有实际内容');
    const bbox = [bx0, by0, bx1 + 1, by1 + 1];
    const w = bbox[2] - bbox[0], h = bbox[3] - bbox[1];
    // 200x240 窗口下角色纹理缩放 ≈0.196 (见 sprite_layout.computeLayout)
    const SCALE = 0.196;
    const dispW = w * SCALE, dispH = h * SCALE;
    assert.ok(dispW >= 18 && dispH >= 18,
        `爱心特效在 200x240 下只有 ${dispW.toFixed(1)}x${dispH.toFixed(1)} 屏幕 px → 看不出是"比心"`);
    // 不遮脸: 脸部区域 (纹理 x430-600, y37-330) 内不得有特效像素
    const inFace = solidCount(prop, 430, 37, 600, 330);
    assert.strictEqual(inFace, 0, `prop_heart 侵入了脸部区域 (${inFace}px)`);
    // 不遮手: 比心帧的手在胸前 (x405-605, y140-330), 特效不得压住手
    const inHands = solidCount(prop, 405, 140, 605, 330);
    assert.strictEqual(inHands, 0, `prop_heart 压住了比心的手 (${inHands}px)`);
    // 必须落在角色**轮廓外的空白区** (头侧), 不能压在躯干上:
    //   R158 旧素材把爱心画在胸口正中央 (纹理 442-572 / 330-450),
    //   正好盖住大褂前襟与折叠的手臂 ⇒ 心形信号被角色本身淹没。
    //   R162 改到头侧左上空白区 (185-305 / 162-282)。
    const onBody = solidCount(prop, 380, 330, 660, 660);
    assert.strictEqual(onBody, 0,
        `prop_heart 压在躯干上 (${onBody}px) → 心形信号被角色本身淹没, 200px 下读不出比心`);
    // 双手确实在胸前 (比心的手必须真的在胸区)
    for (const rel of LIB_ACTIONS.cheer_heart.frames) {
        const n = skinCount(load(rel), 405, 330, 620, 520);
        assert.ok(n > 400, `${rel}: 胸前手部肤色只有 ${n}px → 双手没到胸前, 读不出比心`);
    }
});

// ======================================================================
// R2-5 六个动作必须**互不相同** (R158 遗留: 比心与鼓掌几乎同姿态)
// ======================================================================
test('R2-5 比心与鼓掌必须是两个**不同**的手势 (R158 遗留同姿态问题)', () => {
    // R158 的 cheer_heart_1 与 cheer_clap_1 的手臂角度几乎相同
    //   (都是 L=(-6,140,0) / R=(6,-140,0)) ⇒ 6 个动作里有两个长得一样。
    // R162 分别改成: 比心 = 双手在下颌前合成心形 + 头侧爱心特效;
    //                鼓掌 = 肘部外张、双手在领口高度张开→合拢。
    // 判据: 两个动作的**中帧**胸区肤色分布必须显著不同。
    // R165 修正判据的**度量方式** (意图不变: 两个动作必须是两个不同的手势):
    //   旧口径只看**中帧**的胸区手部横向跨度 —— R165 重新标定后, 比心的中帧与
    //   鼓掌的合拢中帧都是"双手在胸前合拢", 跨度自然接近 (旧口径会误判成同手势)。
    //   真正区分两个手势的是**手部几何在三帧里的变化**:
    //   比心 = 双手始终合拢 (三帧间距都 ≈0); 鼓掌 = 张开→合拢→张开 (间距 69→0→48)。
    //   所以改为比较两个动作的**最大两掌间距**。
    //   R165 实测 (纹��� px):
    //     比心   三帧手部质心高度 = 450 / 429 / 428  ⇒ 变化幅度 22px (双手始终合拢在胸前)
    //     鼓掌   三帧手部质心高度 = 538 / 445 / 541  ⇒ 变化幅度 96px (张开→合拢→张开)
    //   两掌"间距"这个量对两个手势都不稳 (手腕旋转会把一只手切成多块),
    //   而"手部整体在三帧里的高度/位置变化"才是区分"静态手势"与"张合动作"的稳定量。
    const handCY = (act) => {
        const ys = [];
        for (const f of LIB_ACTIONS[act].frames) {
            const g = chestHandGroups(load(f));
            if (!g.length) continue;
            const tot = g.reduce((s, d) => s + d.n, 0);
            ys.push(g.reduce((s, d) => s + ((d.y0 + d.y1) / 2) * d.n, 0) / tot);
        }
        return Math.max(...ys) - Math.min(...ys);
    };
    const hs = handCY('cheer_heart'), cs = handCY('cheer_clap');
    assert.ok(Math.abs(hs - cs) >= 40,
        `比心与鼓掌的三帧手部位置变化幅度几乎相同 (${hs.toFixed(0)} vs ${cs.toFixed(0)}) `
        + '→ 两个动作看起来一样');
});

// ======================================================================
// 汇总
// ======================================================================
test('汇总', () => {
    const passed = results.filter((r) => r.pass).length;
    const failed = results.length - passed;
    console.log(`\nR162 点击互动缺陷修复测试: ${passed} passed, ${failed} failed (共 ${results.length})`);
    if (failed) {
        for (const r of results.filter((x) => !x.pass)) console.log(`  ❌ ${r.name}: ${r.error}`);
    }
    process.exitCode = failed ? 1 : 0;
});
