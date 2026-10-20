// R153 动作库 — 桌宠的"生活动作"目录 (纯逻辑模块, 无 Electron 依赖)
//
// 背景 (R153 用户真机验收):
//   "现有动作太少、行为重复, 桌宠非常无聊" —— 此前运行时只有 6 组基础动画,
//   自主行为是机械循环: 走 → 停 → 睡 → 醒。
//
// 本模块定义:
//   1) 动作目录 (每个动作的类别/是否一次性/归属的资源组)
//   2) 站立小动作池 (带权重 + 不重复上一次, 避免"总做同一个动作")
//   3) 动作过渡策略 (哪些姿态切换需要溶解过渡, 避免"瞬间变成躺姿")
//
// 动作帧资源由 manifest 的 action_library 段提供 (R153 烘焙的新帧 + 现有 R138 帧)。
// 本模块**不含像素**, 只含"做什么/多久/怎么过渡"的策略, 便于自动化测试。
//
// 硬约束 (R153 任务书):
//   · 不得靠"重命名/重复播放/整体旋转/强行缩放"虚增动作数量
//     → 每个动作在 catalog 里必须有独立的帧资源与独立的语义类别
//   · 现有素材做不到的动作必须如实列为"需要新素材", 不得伪报完成

'use strict';

/**
 * 动作类别
 *   rest     : 静止/低活动 (待机、坐下、打盹、呼吸)
 *   gesture  : 站立小动作 (张望、歪头、点头、伸懒腰、开心回应)
 *   move     : 位移动作 (向左/向右走)
 *   oneShot  : 一次性过渡动画 (坐下躺下、醒来)
 */
const ACTION_CATALOG = Object.freeze({
    // —— 基础 6 组 (R138/R141 原有) ——
    idle: Object.freeze({ kind: 'rest', group: 'core', loop: true, desc: '自然站立待机' }),
    walk_left: Object.freeze({ kind: 'move', group: 'core', loop: true, desc: '向左行走' }),
    walk_right: Object.freeze({ kind: 'move', group: 'core', loop: true, desc: '向右行走' }),
    sleep_enter: Object.freeze({ kind: 'oneShot', group: 'core', loop: false, desc: '躺下入睡' }),
    sleep_loop: Object.freeze({ kind: 'rest', group: 'core', loop: true, desc: '睡眠姿态微调' }),
    wake_up: Object.freeze({ kind: 'oneShot', group: 'core', loop: false, desc: '自然醒来' }),

    // —— R153 新增 (动作库) ——
    look_around: Object.freeze({ kind: 'gesture', group: 'library', loop: true, desc: '左右张望' }),
    tilt_head: Object.freeze({ kind: 'gesture', group: 'library', loop: true, desc: '歪头观察' }),
    head_nod: Object.freeze({ kind: 'gesture', group: 'library', loop: false, desc: '点头回应' }),
    happy: Object.freeze({ kind: 'gesture', group: 'library', loop: false, desc: '开心反馈 (歪头眯眼笑)' }),
    blink_soft: Object.freeze({ kind: 'gesture', group: 'library', loop: false, desc: '柔和眨眼' }),
    stretch: Object.freeze({ kind: 'gesture', group: 'library', loop: false, desc: '伸懒腰' }),
    sit_rest: Object.freeze({ kind: 'rest', group: 'library', loop: true, desc: '坐下休息' }),
    doze: Object.freeze({ kind: 'rest', group: 'library', loop: true, desc: '困倦打盹 (坐着)' }),
    sleep_breath: Object.freeze({ kind: 'rest', group: 'library', loop: true, desc: '躺姿呼吸' }),
});

/**
 * 站立小动作池 (权重越大越常出现)。
 * 权重是**相对值**, 由 pickGesture 归一化; 不含 walk/sit/sleep (那些是"日程活动", 不是小动作)。
 */
const GESTURE_POOL = Object.freeze([
    { action: 'look_around', weight: 3 },
    { action: 'tilt_head', weight: 3 },
    { action: 'head_nod', weight: 2 },
    { action: 'stretch', weight: 1 },
    { action: 'happy', weight: 1 },
]);

/**
 * 站立小动作的建议时长 (ms)。实际播放由动画自身时长决定, 这里给引擎一个"该做多久"的上限参考。
 */
const GESTURE_DURATION_MS = Object.freeze({
    look_around: 2600,
    tilt_head: 2600,
    head_nod: 700,
    stretch: 1100,
    happy: 900,
    blink_soft: 320,
});

/**
 * 动作过渡: 哪些切换需要交叉溶解, 避免姿态"瞬切"。
 * key = `${from}>${to}`, 值为溶解时长 (ms)。未列出的组合 = 立即切换 (同姿态族, 无需溶解)。
 */
const TRANSITION_BLEND_MS = Object.freeze({
    'sit_rest>sleep_enter': 320,
    'doze>sleep_enter': 320,
    'sit_rest>doze': 260,
    'sleep_loop>wake_up': 260,
    'sleep_breath>wake_up': 260,
    'idle>stretch': 160,
    'walk_left>walk_right': 0,     // 撞边掉头: 姿态族相同, 立即切换更利落
    'walk_right>walk_left': 0,
});

/**
 * 取两个动作之间的过渡时长。
 * @param {string} from 切换前动作名
 * @param {string} to   切换后动作名
 * @returns {number} 溶解毫秒数 (0 = 立即切换)
 */
function transitionBlendMs(from, to) {
    if (!from || !to || from === to) return 0;
    const key = `${from}>${to}`;
    if (Object.prototype.hasOwnProperty.call(TRANSITION_BLEND_MS, key)) {
        return TRANSITION_BLEND_MS[key];
    }
    // 同类别之间不做溶解 (避免无谓的糊化); 跨类别(尤其坐↔躺)默认溶解
    const a = ACTION_CATALOG[from], b = ACTION_CATALOG[to];
    if (!a || !b) return 0;
    if (a.kind === b.kind) return 0;
    return 220;
}

/**
 * 从站立小动作池里挑一个动作。
 * 规则:
 *   · 按权重随机
 *   · **不重复上一次** (若候选多于 1 个, 排除上一个后重挑) → 避免"总做同一个动作"
 *   · `exclude` 里的动作不参与 (例如刚做完 stretch, 短时间内不重复)
 *
 * @param {function} random () => [0,1)
 * @param {string} [lastAction] 上一次做的动作
 * @param {string[]} [exclude] 额外排除的动作
 * @returns {string} 动作名
 */
function pickGesture(random, lastAction, exclude = []) {
    const rng = typeof random === 'function' ? random : Math.random;
    let pool = GESTURE_POOL.filter((g) => g.action !== lastAction);
    const blocked = new Set([...(exclude || []), lastAction].filter(Boolean));
    if (pool.length > 1) {
        const filtered = pool.filter((g) => !blocked.has(g.action));
        if (filtered.length > 0) pool = filtered;
    }
    const total = pool.reduce((s, g) => s + g.weight, 0);
    let r = rng() * total;
    for (const g of pool) {
        r -= g.weight;
        if (r <= 0) return g.action;
    }
    return pool[pool.length - 1].action;
}

/**
 * 动作是否属于"素材受限"清单 (R153 如实标注: 这些动作需要新素材, 当前用近似实现)。
 * 引擎遇到这些动作时不应把它们算作"完整实现", 报告里要分开列。
 */
const NEEDS_NEW_ASSETS = Object.freeze([
    Object.freeze({ action: 'turn_around', desc: '原地转身 (360° 转身) — R138 无背面素材, 只能用左右步态交替近似' }),
    Object.freeze({ action: 'walk_backward', desc: '后退走 — R138 无后退步态素材' }),
    Object.freeze({ action: 'run', desc: '奔跑 — R138 无奔跑素材, 当前只有 30px/s 散步' }),
    Object.freeze({ action: 'wave_hand', desc: '挥手打招呼 — R138 无挥手素材' }),
    Object.freeze({ action: 'eat_drink', desc: '进食/喝水 — R138 无道具与手部动作素材' }),
]);

/**
 * 统计"视觉上确实不同"的动作数 (用于报告, 避免虚报)。
 * 判据: 每个动作必须有**自己的帧资源**, 且帧内容互不相同。
 * @param {object} manifest
 * @returns {{total:number, byKind:object, detail:Array}}
 */
function countDistinctActions(manifest) {
    const core = (manifest.actions || {});
    const lib = ((manifest.action_library || {}).actions) || {};
    const all = Object.assign({}, core, lib);
    const detail = [];
    const byKind = {};
    // 收集每个动作用到的帧文件
    const used = new Map();
    for (const [name, spec] of Object.entries(all)) {
        const frames = (spec && spec.frames) || [];
        for (const f of frames) {
            if (!used.has(f)) used.set(f, []);
            used.get(f).push(name);
        }
        const kind = (ACTION_CATALOG[name] || {}).kind || 'unknown';
        byKind[kind] = (byKind[kind] || 0) + 1;
        detail.push({ action: name, kind, frames: frames.length, group: (ACTION_CATALOG[name] || {}).group || 'unknown' });
    }
    // 共享同一批帧的动作视为**同一视觉**(例如 stretch 直接复用 idle_01)
    const frameSets = new Map();
    for (const [name, spec] of Object.entries(all)) {
        const key = ((spec && spec.frames) || []).slice().sort().join('|');
        if (!frameSets.has(key)) frameSets.set(key, []);
        frameSets.get(key).push(name);
    }
    const shared = [];
    for (const [key, names] of frameSets) {
        if (names.length > 1) shared.push({ actions: names, sameFrames: true });
    }
    // R153: 逐帧统计"同一个帧文件被几个动作引用" —— 如实披露哪些动作
    //        复用了已有素材里**恰好就是那个姿势**的帧 (stretch / sit_rest),
    //        避免报告把它们混进"全新烘焙动作"里虚增数量。
    const frameOwners = new Map();
    for (const [name, spec] of Object.entries(all)) {
        for (const f of ((spec && spec.frames) || [])) {
            if (!frameOwners.has(f)) frameOwners.set(f, []);
            frameOwners.get(f).push(name);
        }
    }
    const reusedFrames = [];
    for (const [frame, owners] of frameOwners) {
        if (owners.length > 1) reusedFrames.push({ frame, owners });
    }
    // 专有帧数量: 至少被一个动作独占使用
    const dedicated = new Set();
    for (const [frame, owners] of frameOwners) {
        if (owners.length === 1) dedicated.add(owners[0]);
    }
    return {
        total: all ? Object.keys(all).length : 0,
        distinctFrameSets: frameSets.size,
        byKind,
        detail,
        sharedFrameSets: shared,
        reusedFrames,
        dedicatedActionCount: dedicated.size,
        needsNewAssets: NEEDS_NEW_ASSETS.map((x) => x.desc),
    };
}

module.exports = {
    ACTION_CATALOG,
    GESTURE_POOL,
    GESTURE_DURATION_MS,
    TRANSITION_BLEND_MS,
    NEEDS_NEW_ASSETS,
    transitionBlendMs,
    pickGesture,
    countDistinctActions,
};
