// R147 点击 / 拖拽判定 (纯逻辑模块, 无 Electron 依赖)
//
// 背景 (R147 P0):
//   用户真实 Mac 验收反馈"鼠标点击角色没有任何可感知反馈"。
//   R141/R144 的 renderer 在 pointerdown 时进入拖拽态, pointerup 一律 endDrag,
//   没有任何独立的"点击"行为; 而且 sprite 与 canvas 两层 pointerup
//   都会调用 endDrag, 存在重复执行的风险。
//
// 本模块把"一次按下结束到底是什么"抽成纯函数, renderer 与自动化测试调用同一份代码。
//
// 判定规则 (R147 §三 可验收标准):
//   · 短按 + 几乎没有位移          → CLICK  (触发可见反馈)
//   · 累计位移达到拖拽阈值 (3px)  → DRAG   (窗口拖拽, 不触发点击反馈)
//   · 按住超过 400ms 但没移动      → HOLD   (松开即可, 不触发点击反馈)
//   · 鼠标取消 / 离开角色区域松开  → CANCEL (安全清理, 不触发点击反馈)
//
// 硬约束: 同一次操作**只能**得到一个结论 —— 不会既触发点击反馈又触发拖拽结束。

'use strict';

const CLICK_MAX_MS = 400;        // 超过这个按住时长就不算"短按"
const CLICK_MAX_PX = 3;          // 短按允许的累计位移上限
const DRAG_THRESHOLD_PX = 3;     // 达到这个累计位移就判定为拖拽

/**
 * 判定一次"按下结束"的性质。
 *
 * @param {object} input
 * @param {'up'|'outside'|'cancel'} input.reason 结束原因
 * @param {number} input.elapsedMs      从按下到松开的时长 (ms)
 * @param {number} input.distancePx     从按下到松开的累计位移 (px)
 * @param {boolean} input.wasWindowDrag 是否已经进入窗口拖拽
 * @returns {'CLICK'|'DRAG'|'HOLD'|'CANCEL'}
 */
function classifyPress(input) {
    const i = input || {};
    const reason = i.reason || 'up';
    const elapsedMs = (typeof i.elapsedMs === 'number' && Number.isFinite(i.elapsedMs)) ? i.elapsedMs : Infinity;
    const distancePx = (typeof i.distancePx === 'number' && Number.isFinite(i.distancePx)) ? i.distancePx : Infinity;
    const wasWindowDrag = !!i.wasWindowDrag;

    if (reason === 'cancel') return 'CANCEL';
    if (reason === 'outside') return 'CANCEL';
    if (wasWindowDrag) return 'DRAG';
    if (distancePx >= DRAG_THRESHOLD_PX) return 'DRAG';
    if (elapsedMs > CLICK_MAX_MS) return 'HOLD';
    if (distancePx < CLICK_MAX_PX) return 'CLICK';
    return 'HOLD';
}

/**
 * 该结论是否应当触发"点击反馈" (可见反应)。
 */
function isClickReaction(kind) {
    return kind === 'CLICK';
}

/**
 * 该结论是否属于"拖拽结束" (需要通知主进程结束窗口拖拽 / 释放按住态)。
 */
function isDragEnd(kind) {
    return kind === 'DRAG';
}

/**
 * 该结论是否应当释放"按住"状态 (结束引擎的 DRAGGING 态)。
 * CLICK 走独立的 character-click 通道, 由主进程统一收尾。
 */
function releasesPress(kind) {
    return kind === 'DRAG' || kind === 'HOLD' || kind === 'CANCEL';
}

module.exports = {
    CLICK_MAX_MS,
    CLICK_MAX_PX,
    DRAG_THRESHOLD_PX,
    classifyPress,
    isClickReaction,
    isDragEnd,
    releasesPress,
};
