// R144 动画帧推进时钟 (纯逻辑模块, 无 Electron 依赖)
//
// 背景 (R144 P0-2):
//   R141 的 renderer 用取模推进帧:
//       frameIdx = (frameIdx + 1) % meta.frames.length;
//   对 loop=false 的 sleep_enter / wake_up, 播到最后一帧后会**跳回首帧**,
//   造成"闪一下第一帧", 且完成事件可能重复或过期。
//
// 本模块给出替代状态机, renderer 的 ticker 与自动化测试调用同一份代码。
//
// 规则:
//   loop=true  : 正常循环 (取模回卷, 这是循环动画的正常行为)
//   loop=false : 逐帧推进到最后一帧后**停住**;
//                 末帧保持一个 frame_ms 后回报一次 finished;
//                 绝不回卷, 绝不重复回报;
//                 动作被切换/打断 (epoch 变化) 后, 旧的完成事件作废丢弃。

'use strict';

class AnimationClock {
    /**
     * @param {object} [opts]
     * @param {function} [opts.now] 注入时钟 (测试用)
     */
    constructor(opts = {}) {
        this.now = opts.now || (() => Date.now());
        this.action = null;
        this.meta = null;
        this.frameIndex = 0;
        this.lastAdvanceAt = 0;
        this.oneShotReported = false;
        this.oneShotHoldUntil = 0;
        this.epoch = 0;          // 切换动作/打断时自增 → 旧完成事件失效
        this.oneShotEpoch = -1;  // 当前一次性动画所属的 epoch
    }

    /**
     * 切换到新动作 (重置帧号与一次性动画状态)。
     * @param {string} action
     * @param {object} meta { frames:[], frame_ms, fps, loop }
     * @param {number} [nowMs]
     */
    setAction(action, meta, nowMs) {
        this.action = action;
        this.meta = meta || null;
        this.frameIndex = 0;
        this.epoch += 1;
        this.oneShotReported = false;
        this.oneShotHoldUntil = 0;
        this.oneShotEpoch = -1;
        this.lastAdvanceAt = (nowMs !== undefined ? nowMs : this.now());
        return this.frameIndex;
    }

    /**
     * 打断当前动画 (例如用户拖拽打断 sleep_enter):
     * 旧动画之后不得再发送完成事件。
     */
    interrupt(nowMs) {
        this.epoch += 1;
        this.oneShotReported = true;   // 视作已处理, 阻断回报
        this.oneShotHoldUntil = 0;
        this.oneShotEpoch = -1;
        this.lastAdvanceAt = (nowMs !== undefined ? nowMs : this.now());
    }

    /**
     * 帧时长 (ms): 优先 frame_ms, 回退 fps
     *
     * R153 修复: frame_ms 允许是**每帧时长数组** (如 blink_soft [95,135] = 闭眼快/睁眼慢)。
     *   旧实现直接 `return m.frame_ms` → 数组参与数值比较会变成 NaN,
     *   `now - lastAdvanceAt >= NaN` 恒为 false ⇒ **帧永远不推进, 动画静止**。
     *   (R153 实测: 9 个库动作里有 5 个多帧动作全部被冻住)
     *
     * @param {object} [meta]
     * @param {number} [frameIndex] 取哪一帧的时长 (缺省取当前帧)
     */
    period(meta, frameIndex) {
        const m = meta || this.meta;
        if (!m) return 0;
        const fm = m.frame_ms;
        if (Array.isArray(fm)) {
            const idx = (frameIndex === undefined || frameIndex === null)
                ? (this.frameIndex || 0) : frameIndex;
            const v = fm[idx];
            if (typeof v === 'number' && isFinite(v) && v > 0) return v;
            return 1000 / (m.fps || 8);
        }
        if (typeof fm === 'number' && isFinite(fm) && fm > 0) return fm;
        return 1000 / (m.fps || 8);
    }

    /**
     * 推进时钟。
     * @param {number} [nowMs]
     * @returns {{changed:boolean, frameIndex:number, finished:boolean, action:string}}
     */
    tick(nowMs) {
        const now = (nowMs !== undefined ? nowMs : this.now());
        const meta = this.meta;
        const out = {
            changed: false,
            frameIndex: this.frameIndex,
            finished: false,
            action: this.action,
        };
        if (!meta || !Array.isArray(meta.frames) || meta.frames.length === 0) {
            return out;
        }
        const period = this.period(meta, this.frameIndex);
        const last = meta.frames.length - 1;

        if (now - this.lastAdvanceAt >= period) {
            if (meta.loop) {
                // 循环动画: 正常回卷
                this.frameIndex = (this.frameIndex + 1) % meta.frames.length;
                this.lastAdvanceAt = now;
                out.changed = true;
            } else if (this.frameIndex < last) {
                // 一次性动画: 逐帧推进 (不回卷)
                this.frameIndex += 1;
                this.lastAdvanceAt = now;
                out.changed = true;
                if (this.frameIndex === last) {
                    // 到达末帧 → 保持一个 frame_ms 后回报完成
                    // (保持时长取**末帧自己**的时长, 数组 frame_ms 时才正确)
                    this.oneShotHoldUntil = now + this.period(meta, this.frameIndex);
                    this.oneShotReported = false;
                    this.oneShotEpoch = this.epoch;
                }
            } else {
                // 已在末帧: 停住, 保持末帧, 不再推进
                this.lastAdvanceAt = now;
            }
        }
        out.frameIndex = this.frameIndex;

        // 一次性动画完成回报 (只报一次; epoch 不匹配 = 过期事件, 丢弃)
        if (!meta.loop && !this.oneShotReported && this.oneShotHoldUntil > 0 && now >= this.oneShotHoldUntil) {
            if (this.oneShotEpoch === this.epoch) {
                this.oneShotReported = true;
                this.oneShotHoldUntil = 0;
                out.finished = true;
            } else {
                this.oneShotHoldUntil = 0;
            }
        }
        return out;
    }
}

module.exports = { AnimationClock };
