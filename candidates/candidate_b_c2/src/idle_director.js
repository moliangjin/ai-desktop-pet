// R147 自然待机导演 (纯逻辑模块, 无 Electron 依赖)
//
// 背景 (R147 P1):
//   R138 的 idle_01_inhale_peak 胸腔剧烈外扩 (实测轮廓宽度 375→401px, +26px),
//   用户实际观感是"待机时胸部剧烈向外突起、膨胀, 明显不像自然呼吸"。
//   idle_02/03 与 base 的胸区宽度完全相同 (295px), 属于"回落"帧, 不构成呼吸。
//
// 本模块的取舍 (按任务书建议的保守方案):
//   "如果不能可靠制作局部呼吸动画, 宁愿暂时采用稳定站姿加自然眨眼,
//    也不保留剧烈胸部膨胀"
//   → 待机 = 稳定站姿 (base 帧) + 自然眨眼 (长间隔, 略带随机性)。
//   → 膨胀帧 (index 1) 与回落帧 (index 2/3) 不再进入播放序列。
//
// 眨眼节奏: 间隔 1.6s~3.4s 随机, 眨眼半闭 90ms + 全闭 110ms。
//   远慢于 R141 的 1.2s 机械循环, 且不会每 1.2 秒重复一次。

'use strict';

class IdleDirector {
    /**
     * @param {object} [opts]
     * @param {object} [opts.spec]  manifest 里 idle.director 段
     * @param {function} [opts.random]
     * @param {function} [opts.now]
     */
    constructor(opts = {}) {
        this.spec = opts.spec || null;
        this.random = opts.random || Math.random;
        this.now = opts.now || (() => Date.now());
        this.action = null;
        this.phase = 'hold';       // hold | blink
        this.phaseUntil = 0;
        this.blinkIndex = 0;
        this.frameIndex = 0;
        this.blinkCount = 0;
        this.holdCount = 0;
    }

    get enabled() {
        return !!(this.spec && this.spec.enabled &&
            typeof this.spec.base_index === 'number' &&
            Array.isArray(this.spec.blink_sequence) && this.spec.blink_sequence.length > 0);
    }

    /** 站姿保持时长 (随机, 略带不规则) */
    nextHoldMs() {
        const r = (this.spec && this.spec.blink_interval_ms) || [1600, 3400];
        const lo = Math.min(r[0], r[1]);
        const hi = Math.max(r[0], r[1]);
        return lo + Math.floor(this.random() * (hi - lo + 1));
    }

    /** 开始/重置待机 (动作切换或反应结束后调用) */
    setAction(action, nowMs) {
        const now = nowMs !== undefined ? nowMs : this.now();
        this.action = action;
        this.phase = 'hold';
        this.blinkIndex = 0;
        this.frameIndex = this.spec ? this.spec.base_index : 0;
        this.phaseUntil = now + this.nextHoldMs();
        this.holdCount++;
        return this.frameIndex;
    }

    /**
     * 推进待机时间轴。
     * @returns {{changed:boolean, frameIndex:number, phase:string}}
     */
    tick(nowMs) {
        const now = nowMs !== undefined ? nowMs : this.now();
        const out = { changed: false, frameIndex: this.frameIndex, phase: this.phase };
        if (!this.enabled) return out;
        const spec = this.spec;

        if (this.phase === 'hold') {
            if (now >= this.phaseUntil) {
                this.phase = 'blink';
                this.blinkIndex = 0;
                this.frameIndex = spec.blink_sequence[0];
                const durs = spec.blink_frame_ms || [];
                this.phaseUntil = now + (durs[0] || 90);
                this.blinkCount++;
                out.changed = true;
            }
        } else {
            const next = this.blinkIndex + 1;
            if (now >= this.phaseUntil) {
                if (next < spec.blink_sequence.length) {
                    this.blinkIndex = next;
                    this.frameIndex = spec.blink_sequence[next];
                    const durs = spec.blink_frame_ms || [];
                    this.phaseUntil = now + (durs[next] || 110);
                } else {
                    this.phase = 'hold';
                    this.frameIndex = spec.base_index;
                    this.phaseUntil = now + this.nextHoldMs();
                }
                out.changed = true;
            }
        }
        out.frameIndex = this.frameIndex;
        out.phase = this.phase;
        return out;
    }
}

module.exports = { IdleDirector };
