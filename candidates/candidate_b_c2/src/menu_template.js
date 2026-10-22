// R177 桌宠右键菜单模板 (纯逻辑模块, 可单元测试)
//
// 【为什么单独抽出来】
//   Electron 原生 Menu.buildFromTemplate 只能在 Electron 运行时构造, 无法在 node 单测里
//   直接断言"菜单里到底有哪些项、每项接到哪个命令"。这里把**模板本身**做成纯数据 +
//   纯函数, main.js 只负责 `Menu.buildFromTemplate(buildMenuTemplate({...}))`,
//   于是"菜单项 → 行为系统命令"的映射可以被自动化测试逐项断言。
//
// 【硬约束】
//   · 菜单里**只有** 6 个行为命令 + 设置 + 退出, 没有任何调试项 —— 不污染桌宠外观。
//   · 6 个命令与行为引擎 `BehaviorEngine.command(kind)` 支持的 kind 一一对应,
//     走的是自主决策**完全相同**的内部路径 (不是播一张演示图)。
//   · 心情那一项是**只读**的: 只显示当前心情, 不可点击 (它是信息, 不是命令)。

'use strict';

// 菜单可触发的行为命令 (顺序即菜单里的显示顺序)
const MENU_COMMANDS = Object.freeze(['sleep', 'wake', 'sit', 'work', 'eat_fruit', 'gesture']);

// 命令 → 中文菜单名 (与任务书 §一.2 的措辞一致)
const MENU_LABELS = Object.freeze({
    sleep: '睡觉',
    wake: '醒来',
    sit: '坐沙发休息',
    work: '电脑办公',
    eat_fruit: '吃水果',
    gesture: '随机可爱动作',
});

// 心情只读项的前缀
const MOOD_ITEM_PREFIX = '心情：';

/**
 * 构造右键菜单模板。
 *
 * @param {object} opts
 * @param {string} [opts.moodLabel]     当前心情中文名 (如 '开心')
 * @param {function} opts.onCommand     (kind) => void —— 触发行为系统命令
 * @param {function} opts.onOpenSettings () => void —— 打开设置面板
 * @param {function} opts.onQuit        () => void —— 退出桌宠
 * @returns {Array<object>} Electron Menu 模板
 */
function buildMenuTemplate(opts = {}) {
    const {
        moodLabel = '平静',
        onCommand = () => {},
        onOpenSettings = () => {},
        onQuit = () => {},
    } = opts;

    const items = [
        // 心情只读 (enabled: false ⇒ 不可点击, 不产生命令)
        { label: `${MOOD_ITEM_PREFIX}${moodLabel}`, enabled: false },
        { type: 'separator' },
    ];
    for (const kind of MENU_COMMANDS) {
        items.push({
            label: MENU_LABELS[kind],
            click: () => onCommand(kind),
        });
    }
    items.push({ type: 'separator' });
    items.push({ label: '设置…', click: () => onOpenSettings() });
    items.push({ label: '退出桌宠', click: () => onQuit() });
    return items;
}

/** 取模板里所有"可点击命令项"的 label (用于测试断言菜单没有调试项)。 */
function menuCommandLabels(template) {
    return (template || [])
        .filter((it) => it && it.type !== 'separator' && it.enabled !== false)
        .map((it) => it.label);
}

/** 取模板里所有被接上的命令 kind (点击后传给 onCommand 的值)。 */
function menuCommandKinds(template) {
    const kinds = [];
    for (const kind of MENU_COMMANDS) {
        const item = (template || []).find((it) => it && it.label === MENU_LABELS[kind]);
        if (item && typeof item.click === 'function') kinds.push(kind);
    }
    return kinds;
}

module.exports = {
    MENU_COMMANDS,
    MENU_LABELS,
    MOOD_ITEM_PREFIX,
    buildMenuTemplate,
    menuCommandLabels,
    menuCommandKinds,
};
