// R141 最小自主生活行为引擎 (纯逻辑模块, 无 Electron 依赖)
//
// 设计目标 (R141 §三):
//   - 简单、稳定的有限状态机
//   - 状态: IDLE / WALK_LEFT / WALK_RIGHT / SLEEP_ENTER / SLEEP_LOOP / WAKE_UP / DRAGGING
//   - 明确优先级, 避免多个行为同时控制窗口位置或动画
//   - 时间/速度/随机概率集中配置
//   - 本轮不引入 AI 决策
//
// 关键约束 (R141 §七):
//   - 单一计时器链, 不允许多个行为定时器并发
//   - 拖拽期间不移动窗口
//   - 停止时清理全部定时器
//
// 本模块不依赖 Electron, main.js 与自动测试 require 的是**同一份代码**,
// 满足 R141 §八 "测试必须调用真实生产代码".

'use strict';

// R153 新增: 生活化活动策略 (纯逻辑, 与渲染器/自动化测试共用同一份)
const {
    ACTION_CATALOG, GESTURE_DURATION_MS, pickGesture,
} = require('./action_library.js');

const DEFAULT_CONFIG = Object.freeze({
    idle_min_ms: 3000,
    idle_max_ms: 8000,
    walk_speed_px_per_sec: 30,
    walk_min_distance_px: 80,
    walk_max_distance_px: 250,
    walk_move_tick_ms: 33,
    sleep_min_ms: 20000,
    sleep_max_ms: 45000,
    // R153: 睡眠触发频率大幅降低 (0.3 → 0.10), 并与"短暂打盹"分层
    sleep_probability: 0.10,
    walk_probability: 0.62,
    drag_resume_delay_ms: 800,
    edge_margin_px: 4,
    // R153: 生活化活动参数
    // R156: 办公待机 (新 idle 类状态) —— 权重刻意压低, 且不与其它活动连着做
    //
    // R170 真机实测重标定 (权重 / 持续时长 / 冷却三项一起改):
    //   实测方式: 真实 Electron 连跑 180s, 统计 `[main] R141 STATE` 转移日志。
    //   实测结果: 180 秒里**空闲决策只有 9 次**, WORK 触发 **0 次** ⇒
    //     用户真机看到的就是"办公场景消失不见了"。
    //   根因 (三个数叠加):
    //     ① work_probability=0.10 与"总权重 2.00"(含 manifest 里被改回 0.3/0.7 的
    //        sleep/walk)竞争 ⇒ **单次决策命中率只有 5%**;
    //     ② 长活动吃掉了时间轴 (睡 20~45s / 打盹 7~15s / 坐 6~13s)
    //        ⇒ 空闲决策 ~20s 才发生一次;
    //     ③ 命中率 5% × 20s/次 ⇒ 期望 **~6.7 分钟才出现一次办公**, 每次还只有
    //        9~19s ⇒ 真机观感 = "闪一下就没了 / 根本没出现"。
    //   重标定后: 单次决策命中率 ~22%, 单次持续 16~28s, 冷却 60s。
    work_probability: 0.55,
    work_min_ms: 16000,
    work_max_ms: 28000,
    work_cooldown_ms: 60000,      // R170: 办公冷却 —— 防止"一直只办公"
    // R170: 吃水果 (新的生活行为, 与办公互斥)
    eat_fruit_probability: 0.36,
    eat_fruit_min_ms: 14000,
    eat_fruit_max_ms: 22000,
    eat_fruit_cooldown_ms: 50000, // R170: 吃水果冷却
    gesture_probability: 0.46,      // 站立小动作 (张望/歪头/点头/伸展/开心)
    sit_probability: 0.22,          // 坐下休息
    doze_probability: 0.22,         // 困倦打盹 (短暂, 不躺下)
    gesture_min_ms: 1600,
    gesture_max_ms: 3400,
    sit_min_ms: 6000,
    sit_max_ms: 13000,
    doze_min_ms: 7000,
    doze_max_ms: 15000,
    sleep_shift_min_ms: 7000,       // 睡眠中"偶尔姿态微调"的最小间隔
    sleep_shift_max_ms: 15000,      // 睡眠中"偶尔姿态微调"的最大间隔
    sleep_shift_duration_ms: 4200,  // 一次姿态微调持续时长
    stretch_after_wake: true,       // 醒来后伸个懒腰
    activity_repeat_penalty: 0.25,   // 连续做同一类活动的权重折扣
    no_sleep_after_wake_ms: 45000,  // 醒来后这段时间内不再触发睡眠 (避免 睡→醒→睡)
    // R177: 设置面板的频率档位换算成这三个乘子 (运行时可改, 见 applyConfig)
    //   activity_rate_interval_scale : 自主决策间隔乘子 (越大越迟钝)
    //   activity_weight_scale        : 非睡眠类自主活动权重乘子
    //   sleep_weight_scale           : 睡眠权重乘子
    activity_rate_interval_scale: 1.0,
    activity_weight_scale: 1.0,
    sleep_weight_scale: 1.0,
});

const STATES = Object.freeze({
    IDLE: 'IDLE',
    WALK_LEFT: 'WALK_LEFT',
    WALK_RIGHT: 'WALK_RIGHT',
    SLEEP_ENTER: 'SLEEP_ENTER',
    SLEEP_LOOP: 'SLEEP_LOOP',
    WAKE_UP: 'WAKE_UP',
    DRAGGING: 'DRAGGING',
    // R153: 生活化状态
    GESTURE: 'GESTURE',   // 站立小动作 (张望/歪头/点头/伸展/开心)
    SIT: 'SIT',           // 坐下休息
    DOZE: 'DOZE',         // 困倦打盹 (坐着)
    WORK: 'WORK',         // R156: 在电脑前办公 (新的 idle 类状态)
    EAT_FRUIT: 'EAT_FRUIT', // R170: 吃水果 (新的 idle 类状态, 与办公互斥)
});

// 状态优先级: 数值越大优先级越高. DRAGGING 最高 (用户操作永远优先).
const STATE_PRIORITY = Object.freeze({
    IDLE: 0,
    SLEEP_LOOP: 1,
    SLEEP_ENTER: 2,
    WAKE_UP: 2,
    GESTURE: 2,
    SIT: 2,
    DOZE: 2,
    WORK: 2,
    EAT_FRUIT: 2,
    WALK_LEFT: 3,
    WALK_RIGHT: 3,
    DRAGGING: 10,
});

// 一次性动画 (播完必须回调), 持续循环动画
const ONE_SHOT_ACTIONS = Object.freeze(['sleep_enter', 'wake_up']);
const LOOP_ACTIONS = Object.freeze(['idle', 'walk_left', 'walk_right', 'sleep_loop']);

/**
 * 自主活动池的**固定顺序**。
 * 权重来自 config, 但顺序固定 → 随机阈值可复现, 自动化测试能反推"想触发某类活动
 * 该喂哪个随机数", 不必把阈值写死在测试里。
 * R156 新增 work (办公待机), 放在 sleep 之前, 让"睡觉"仍落在随机区间的末端。
 * R170 新增 eat_fruit (吃水果), 放在 work 之后 —— 两者都是"坐着"的生活行为,
 * 顺序固定 ⇒ 测试阈值可反推。
 */
const ACTIVITY_KINDS = Object.freeze(['gesture', 'walk', 'sit', 'doze', 'work', 'eat_fruit', 'sleep']);

// 状态 -> 动画名
const STATE_ACTION = Object.freeze({
    IDLE: 'idle',
    WALK_LEFT: 'walk_left',
    WALK_RIGHT: 'walk_right',
    SLEEP_ENTER: 'sleep_enter',
    SLEEP_LOOP: 'sleep_breath',
    WAKE_UP: 'wake_up',
    DRAGGING: 'idle',
    // R153
    GESTURE: 'idle',     // 实际动作由 _startGesture 单独下发
    SIT: 'sit_rest',
    DOZE: 'doze',
    WORK: 'work',        // R156: 办公待机 (小桌子 + 笔记本 + 屏幕微光)
    EAT_FRUIT: 'eat_fruit', // R170: 吃水果 (小凳 + 小桌 + 果盘)
});

class BehaviorEngine {
    /**
     * @param {object} opts
     * @param {object} [opts.config]      行为参数 (覆盖 DEFAULT_CONFIG)
     * @param {function} [opts.onAction]  (actionName, state) => void   切换动画
     * @param {function} [opts.onMove]    (dxPixels, state) => void     请求移动窗口
     * @param {function} [opts.onState]   (from, to) => void           状态变化通知
     * @param {function} [opts.random]    () => number                注入随机源 (测试用)
     * @param {function} [opts.now]       () => number                注入时钟 (测试用)
     * @param {function} [opts.setTimeout]/[opts.clearTimeout]        注入定时器
     * @param {function} [opts.setInterval]/[opts.clearInterval]
     */
    constructor(opts = {}) {
        this.config = Object.assign({}, DEFAULT_CONFIG, opts.config || {});
        this.onAction = opts.onAction || (() => {});
        this.onMove = opts.onMove || (() => {});
        this.onState = opts.onState || (() => {});
        this._random = opts.random || Math.random;
        this._now = opts.now || (() => Date.now());

        this._setTimeout = opts.setTimeout || ((fn, ms) => setTimeout(fn, ms));
        this._clearTimeout = opts.clearTimeout || ((h) => clearTimeout(h));
        this._setInterval = opts.setInterval || ((fn, ms) => setInterval(fn, ms));
        this._clearInterval = opts.clearInterval || ((h) => clearInterval(h));

        // R177: 心情适配器 (纯逻辑, 由 mood_engine.js 提供)
        //   接口: { getMood(), activityWeight(kind, mood), idleIntervalScale(mood) }
        //   传 null ⇒ 全部系数为 1 (行为与 R176 完全一致, 不影响既有测试)
        this._moodAdapter = opts.moodAdapter || null;

        this.state = STATES.IDLE;
        this._timer = null;          // 唯一的行为计时器
        this._moveTimer = null;      // 行走位移计时器
        this._running = false;
        this._dragging = false;
        this._pendingResume = null;  // 拖拽结束后待恢复的计时器
        this._holdTimer = null;      // R147: 点击反馈期间的短暂按住计时器
        this._movePaused = false;    // R147: 行走位移是否被点击反馈暂停
        this._autonomousPaused = false; // R147: 预览/验收模式下暂停自主决策
        this._walkRemaining = 0;     // 剩余行走距离 (px)
        this._walkDirection = 0;     // -1 左 / +1 右
        this._walkStartedAt = 0;
        this._walkTarget = 0;
        this._lastMoveAt = 0;
        // R153: 生活化状态记忆 (避免连续重复同一种活动)
        this._lastActivity = null;      // 上一次的活动类别 (gesture/walk/sit/doze/work/eat_fruit/sleep)
        this._lastGesture = null;       // 上一次的站立小动作
        this._wokeAt = -Infinity;       // 最近一次醒来的时间戳 (-Infinity = 从未醒来)
        this._sleepShiftTimer = null;   // 睡眠中"偶尔姿态微调"的计时器
        // R170: 办公/吃水果各自的冷却计时基准
        this._lastWorkAt = -Infinity;       // 最近一次开始办公的时间戳
        this._lastEatFruitAt = -Infinity;   // 最近一次开始吃水果的时间戳
        // R170: "有时长"状态的计时器种类与到期时刻 (点击反馈打断后按剩余时间恢复)
        this._stateTimerKind = null;
        this._stateDeadline = 0;
        this.transitionLog = [];
    }

    // ---------- 生命周期 ----------

    start() {
        if (this._running) return;
        this._running = true;
        this._transition(STATES.IDLE, 'engine-start');
        this._scheduleIdle();
    }

    stop() {
        this._running = false;
        this._clearAllTimers();
        this.state = STATES.IDLE;
    }

    _clearAllTimers() {
        if (this._timer !== null) { this._clearTimeout(this._timer); this._timer = null; }
        if (this._moveTimer !== null) { this._clearInterval(this._moveTimer); this._moveTimer = null; }
        if (this._pendingResume !== null) { this._clearTimeout(this._pendingResume); this._pendingResume = null; }
        if (this._holdTimer !== null) { this._clearTimeout(this._holdTimer); this._holdTimer = null; }
        if (this._sleepShiftTimer !== null) { this._clearTimeout(this._sleepShiftTimer); this._sleepShiftTimer = null; }
        // R170: 状态计时器的"种类/到期时刻"也要清, 否则恢复逻辑会误判
        this._stateTimerKind = null;
        this._stateDeadline = 0;
    }

    // ---------- 内部工具 ----------

    _randInt(min, max) {
        const lo = Math.min(min, max);
        const hi = Math.max(min, max);
        return lo + Math.floor(this._random() * (hi - lo + 1));
    }

    _transition(next, reason) {
        const from = this.state;
        if (from === next) return false;
        this.state = next;
        this.transitionLog.push({ from, to: next, reason, at: this._now() });
        if (this.transitionLog.length > 200) this.transitionLog.splice(0, 100);
        try { this.onState(from, next, reason); } catch (e) { /* 通知失败不阻塞引擎 */ }
        return true;
    }

    _setAction(action) {
        try { this.onAction(action, this.state); } catch (e) { /* 忽略 */ }
    }

    // ---------- 各状态的调度 ----------

    _scheduleIdle() {
        if (!this._running || this._dragging) return;
        const ms = Math.round(this._randInt(this.config.idle_min_ms, this.config.idle_max_ms)
            * this._idleIntervalFactor());
        this._timer = this._setTimeout(() => {
            this._timer = null;
            this._decideNextFromIdle();
        }, ms);
    }

    /**
     * R177: 自主决策间隔系数 = 心情系数 × 设置里的"自主活动频率"系数。
     * 心情越开心/无聊 ⇒ 越活跃 (间隔越短); 越困 ⇒ 越迟钝。
     */
    _idleIntervalFactor() {
        const mood = this._moodAdapter ? this._moodAdapter.idleIntervalScale(this._moodAdapter.getMood()) : 1;
        const rate = this.config.activity_rate_interval_scale || 1;
        const v = mood * rate;
        return Number.isFinite(v) && v > 0 ? v : 1;
    }

    /** R177: 当前心情 (无适配器时返回 null)。 */
    getMood() {
        if (!this._moodAdapter) return null;
        try { return this._moodAdapter.getMood(); } catch (e) { return null; }
    }

    _decideNextFromIdle() {
        if (!this._running || this._dragging) return;
        // R147: 预览/验收模式下暂停自主决策 (仍可被显式 startWalk 驱动)
        if (this._autonomousPaused) {
            this._scheduleIdle();
            return;
        }
        // R153: 不再是"走/睡"二选一, 而是从 5 类生活活动里按权重挑 (会重复判定见 _pickActivity)
        const kind = this._pickActivity();
        switch (kind) {
            case 'gesture': this._startGesture(); break;
            case 'walk': {
                const dir = this._random() < 0.5 ? -1 : 1;
                this._startWalk(dir);
                break;
            }
            case 'sit': this._startSit(); break;
            case 'doze': this._startDoze(); break;
            case 'work': this._startWork(); break;
            case 'eat_fruit': this._startEatFruit(); break;
            case 'sleep': this._enterSleep(); break;
            default: this._scheduleIdle();
        }
    }

    /**
     * R153: 加权活动池。
     *   · 5 类生活活动: 站立小动作 / 散步 / 坐下休息 / 困倦打盹 / 躺下睡觉
     *   · 对"刚做过的同类活动"打折 (activity_repeat_penalty) → 不会连着做同一件事
     *   · 刚睡醒不久不再立刻睡 (避免 走→睡→醒→睡 的机械循环)
     * @returns {'gesture'|'walk'|'sit'|'doze'|'sleep'}
     */
    _pickActivity() {
        const cfg = this.config;
        const now = this._now();
        const items = [
            { kind: 'gesture', w: cfg.gesture_probability },
            { kind: 'walk', w: cfg.walk_probability },
            { kind: 'sit', w: cfg.sit_probability },
            { kind: 'doze', w: cfg.doze_probability },
            { kind: 'work', w: cfg.work_probability },
            { kind: 'eat_fruit', w: cfg.eat_fruit_probability },
            { kind: 'sleep', w: cfg.sleep_probability },
        ].map((it) => {
            let w = it.w;
            if (it.kind === this._lastActivity) w *= cfg.activity_repeat_penalty;
            if (it.kind === 'sleep' && (now - this._wokeAt) < cfg.no_sleep_after_wake_ms) w = 0;
            // R156: 办公待机**不与其它活动连着做** —— 上一项是办公时权重直接归零,
            //       保证它与普通待机/打盹/行走/睡眠错开, 不会一直只办公
            if (it.kind === 'work' && this._lastActivity === 'work') w = 0;
            // R170: 办公/吃水果各自的**冷却期** —— 冷却期内权重归零。
            //   单靠"上一项是同类就归零"只能挡住"连着做", 挡不住"隔一项又做";
            //   真机观感是"刚吃完又吃 / 刚放下电脑又坐下", 所以要真正的冷却。
            if (it.kind === 'work' && (now - this._lastWorkAt) < cfg.work_cooldown_ms) w = 0;
            if (it.kind === 'eat_fruit' && (now - this._lastEatFruitAt) < cfg.eat_fruit_cooldown_ms) w = 0;
            // R177: 心情调制 (开心→爱动 / 困倦→爱打盹 / 无聊→想找事做)
            if (this._moodAdapter) {
                const mood = this._moodAdapter.getMood();
                w *= this._moodAdapter.activityWeight(it.kind, mood);
            }
            // R177: 设置面板的频率档位 (自主活动频率 / 睡眠频率分别缩放)
            w *= (it.kind === 'sleep')
                ? (cfg.sleep_weight_scale || 1)
                : (cfg.activity_weight_scale || 1);
            return { kind: it.kind, w };
        });
        const total = items.reduce((s, it) => s + it.w, 0);
        if (total <= 0) return 'gesture';
        let r = this._random() * total;
        for (const it of items) {
            r -= it.w;
            if (r <= 0) return it.kind;
        }
        return items[items.length - 1].kind;
    }

    /**
     * R153: 站立小动作 (张望/歪头/点头/伸懒腰/开心)。
     * 动作由 action_library.pickGesture 决定 —— 带权重且不重复上一次。
     */
    _startGesture(actionName) {
        const action = actionName || pickGesture(this._random, this._lastGesture);
        this._lastGesture = action;
        this._lastActivity = 'gesture';
        this._transition(STATES.GESTURE, 'idle-decision');
        this._setAction(action);
        const spec = ACTION_CATALOG[action] || {};
        const base = GESTURE_DURATION_MS[action] || 1200;
        // 一次性动作播完即止; 循环动作至少跑满一个周期, 再叠加随机时长
        const ms = spec.loop === false
            ? Math.round(base * 1.15)
            : Math.round(base + this._randInt(0, this.config.gesture_max_ms - this.config.gesture_min_ms) * 0.5);
        this._timer = this._setTimeout(() => {
            this._timer = null;
            if (!this._running || this._dragging) return;
            if (this.state !== STATES.GESTURE) return;
            this._transition(STATES.IDLE, 'gesture-complete');
            this._setAction('idle');
            this._scheduleIdle();
        }, ms);
        return action;
    }

    /**
     * R170: 给"有时长"的状态装计时器, 并**记住到期时刻**。
     *
     * 为什么要记到期时刻 —— R170 修掉的一个真 bug:
     *   点击反馈 (holdBriefly) 会清掉状态计时器, 旧实现清掉后**没人重新排程**
     *   ⇒ 状态被永久卡住: 办公中点一下角色, 引擎永远停在 WORK
     *   (场景"不消失", 但也永远走不了 —— 与 R170 用户报的"办公场景消失"同源的一类问题)。
     *   记住剩余时间, 点击反馈结束后按**剩余时间原样恢复**, 场景既不被打断也不卡死。
     *
     * @param {string} kind 状态类别 (work/eat_fruit/sit/doze)
     * @param {number} ms   时长
     * @param {function} done 到期回调
     */
    _armStateTimer(kind, ms, done) {
        this._stateTimerKind = kind;
        this._stateDeadline = this._now() + ms;
        this._timer = this._setTimeout(() => {
            this._timer = null;
            this._stateTimerKind = null;
            this._stateDeadline = 0;
            done();
        }, ms);
    }

    /**
     * R170: 恢复被点击反馈打断的"有时长"状态 (按剩余时间)。
     * @returns {boolean} 是否成功恢复
     */
    _resumeStateTimer(kind, remaining) {
        const done = {
            work: () => this._completeWork(),
            eat_fruit: () => this._completeEatFruit(),
            sit: () => this._completeSit(),
            doze: () => this._completeDoze(),
        }[kind];
        if (!done) return false;
        this._armStateTimer(kind, remaining, done);
        return true;
    }

    /** R153: 坐下休息 (可衔接打盹) */
    _startSit() {
        this._lastActivity = 'sit';
        this._transition(STATES.SIT, 'idle-decision');
        this._setAction('sit_rest');
        const ms = this._randInt(this.config.sit_min_ms, this.config.sit_max_ms);
        this._armStateTimer('sit', ms, () => this._completeSit());
    }

    _completeSit() {
        if (!this._running || this._dragging) return;
        if (this.state !== STATES.SIT) return;
        // 坐久了有时会迷糊过去 (打盹), 否则起身回到站立
        if (this._random() < 0.45) {
            this._startDoze();
        } else {
            this._transition(STATES.IDLE, 'sit-complete');
            this._setAction('idle');
            this._scheduleIdle();
        }
    }

    /**
     * R156: 在电脑前办公 (新的 idle 类状态)。
     *   · 表现: 坐在转椅上, 上半身前倾看屏幕 / 抬头思考 (work 动作自带 2 帧循环)
     *   · 频率: R170 真机实测重标定 (见 DEFAULT_CONFIG 注释) —— 命中 5% ⇒ 真机 180s
     *     触发 0 次, 用户看到的就是"场景消失了"; 现为 ~22% + 16~28s + 60s 冷却
     *   · 道具: 引擎只下发动作名, 具体的小桌子/笔记本/屏幕微光由渲染器按动作挂载
     */
    _startWork() {
        this._lastActivity = 'work';
        this._lastWorkAt = this._now();
        this._transition(STATES.WORK, 'idle-decision');
        this._setAction('work');
        const ms = this._randInt(this.config.work_min_ms, this.config.work_max_ms);
        this._armStateTimer('work', ms, () => this._completeWork());
    }

    _completeWork() {
        if (!this._running || this._dragging) return;
        if (this.state !== STATES.WORK) return;
        this._transition(STATES.IDLE, 'work-complete');
        this._setAction('idle');
        this._scheduleIdle();
    }

    /**
     * R170: 吃水果 (新的 idle 类状态, 与办公互斥 —— 状态机同一时刻只有一个状态,
     *   两者天然不会同时运行; 这里额外保证"吃水果"与"办公"不会连着做)。
     *   道具: 小凳 + 小桌 + 果盘, 由渲染器按动作名挂载。
     */
    _startEatFruit() {
        this._lastActivity = 'eat_fruit';
        this._lastEatFruitAt = this._now();
        this._transition(STATES.EAT_FRUIT, 'idle-decision');
        this._setAction('eat_fruit');
        const ms = this._randInt(this.config.eat_fruit_min_ms, this.config.eat_fruit_max_ms);
        this._armStateTimer('eat_fruit', ms, () => this._completeEatFruit());
    }

    _completeEatFruit() {
        if (!this._running || this._dragging) return;
        if (this.state !== STATES.EAT_FRUIT) return;
        this._transition(STATES.IDLE, 'eat_fruit-complete');
        this._setAction('idle');
        this._scheduleIdle();
    }

    /** R153: 困倦打盹 (坐着闭眼, 短暂) —— 与"躺下长睡"区分 */
    _startDoze() {
        this._lastActivity = 'doze';
        this._transition(STATES.DOZE, 'idle-decision');
        this._setAction('doze');
        const ms = this._randInt(this.config.doze_min_ms, this.config.doze_max_ms);
        this._armStateTimer('doze', ms, () => this._completeDoze());
    }

    _completeDoze() {
        if (!this._running || this._dragging) return;
        if (this.state !== STATES.DOZE) return;
        this._transition(STATES.IDLE, 'doze-complete');
        this._setAction('idle');
        this._scheduleIdle();
    }

    /**
     * 暂停/恢复自主决策 (预览采集与验收脚本用)。
     * 暂停时不会自行决定去走或去睡, 但状态机仍可被 startWalk 等显式驱动。
     */
    setAutonomousPaused(paused) {
        this._autonomousPaused = !!paused;
        return this._autonomousPaused;
    }

    _startWalk(dir, distancePx) {
        this._lastActivity = 'walk';
        this._walkDirection = dir >= 0 ? 1 : -1;
        // 新的一次行走不受此前"点击反馈暂停"的影响 (否则会走不起来)
        this._movePaused = false;
        this._walkTarget = (typeof distancePx === 'number' && distancePx > 0)
            ? distancePx
            : this._randInt(this.config.walk_min_distance_px, this.config.walk_max_distance_px);
        this._walkRemaining = this._walkTarget;
        this._walkStartedAt = this._now();
        this._lastMoveAt = this._now();
        this._transition(this._walkDirection < 0 ? STATES.WALK_LEFT : STATES.WALK_RIGHT, 'idle-decision');
        this._setAction(STATE_ACTION[this.state]);
        this._startMoveTimer();
    }

    /**
     * 强制开始一次行走 (验收脚本 / 预览采集用)。
     * 走的是与自主决策**完全相同**的 _startWalk 路径, 不另开逻辑。
     * @param {number} dir -1 左 / +1 右
     * @param {number} [distancePx] 指定行走距离 (默认用配置里的随机区间)
     */
    startWalk(dir, distancePx) {
        if (!this._running) return false;
        this._startWalk(dir >= 0 ? 1 : -1, distancePx);
        return true;
    }

    _startMoveTimer() {
        this._stopMoveTimer();
        this._moveTimer = this._setInterval(() => this._walkTick(), this.config.walk_move_tick_ms);
    }

    _stopMoveTimer() {
        if (this._moveTimer !== null) {
            this._clearInterval(this._moveTimer);
            this._moveTimer = null;
        }
    }

    _walkTick() {
        if (!this._running || this._dragging || this._movePaused) { this._stopMoveTimer(); return; }
        if (this.state !== STATES.WALK_LEFT && this.state !== STATES.WALK_RIGHT) {
            this._stopMoveTimer();
            return;
        }
        const now = this._now();
        const dtSec = Math.min((now - this._lastMoveAt) / 1000, 0.25); // 防止卡顿后一次跳太远
        this._lastMoveAt = now;
        if (dtSec <= 0) return;

        const step = this.config.walk_speed_px_per_sec * dtSec;
        const move = step * this._walkDirection;

        let edgeTurned = false;
        let actualMoved = null;
        try {
            // onMove 返回 { blocked: true } 表示撞到屏幕边界
            const res = this.onMove(move, this.state);
            if (res) {
                if (res.blocked) {
                    edgeTurned = true;
                }
                // R144 P1: 优先采用主进程 setBounds 后 getBounds 复核出的**真实**位移.
                //   小数位移累计后可能为 0 (还没凑够 1px), 此时不应凭空扣减剩余距离.
                if (typeof res.moved === 'number') {
                    actualMoved = Math.abs(res.moved);
                }
            }
        } catch (e) {
            // 异常时保持原有行为 (不误判撞边), 距离按请求步长计
        }
        this._walkRemaining -= (actualMoved === null) ? step : actualMoved;

        if (edgeTurned) {
            // 撞边: 转向 (反向继续走), 重新计算剩余距离
            this._walkDirection = -this._walkDirection;
            this._walkRemaining = this.config.walk_min_distance_px;
            const newState = this._walkDirection < 0 ? STATES.WALK_LEFT : STATES.WALK_RIGHT;
            this._transition(newState, 'edge-turn');
            this._setAction(STATE_ACTION[newState]);
            return;
        }

        if (this._walkRemaining <= 0) {
            this._stopMoveTimer();
            this._walkRemaining = 0;
            this._transition(STATES.IDLE, 'walk-complete');
            this._setAction('idle');
            this._scheduleIdle();
        }
    }

    _enterSleep() {
        this._lastActivity = 'sleep';
        this._transition(STATES.SLEEP_ENTER, 'idle-decision');
        this._setAction('sleep_enter');
        // 注意: sleep_enter 是一次性动画, 等 renderer 回调 onAnimationFinished('sleep_enter')
    }

    _onSleepEnterFinished() {
        if (this.state !== STATES.SLEEP_ENTER) return false;
        this._transition(STATES.SLEEP_LOOP, 'sleep_enter-finished');
        // R153: 用"躺姿呼吸"(胸口局部微缩)作为睡眠主循环, 取代原来 3 个大幅换姿势的帧
        //       (原来 700ms 一换, 观感是"睡姿乱抽动", 且用户反馈"几乎没有变化")
        this._setAction('sleep_breath');
        this._scheduleSleepShift();
        const ms = this._randInt(this.config.sleep_min_ms, this.config.sleep_max_ms);
        this._timer = this._setTimeout(() => {
            this._timer = null;
            this._clearSleepShift();
            if (this.state !== STATES.SLEEP_LOOP) return;
            this._transition(STATES.WAKE_UP, 'sleep-duration-elapsed');
            this._setAction('wake_up');
            // wake_up 是一次性动画, 等 renderer 回调
        }, ms);
        return true;
    }

    /**
     * R153: 睡眠期间"偶尔姿态微调" —— 隔一段时间换成另一组睡姿, 几秒后换回呼吸。
     * 这样长时间睡眠不再是"一张图不动", 也不是"每 0.7s 抽动一次"。
     */
    _scheduleSleepShift() {
        this._clearSleepShift();
        const wait = this._randInt(this.config.sleep_shift_min_ms, this.config.sleep_shift_max_ms);
        this._sleepShiftTimer = this._setTimeout(() => {
            this._sleepShiftTimer = null;
            if (!this._running || this.state !== STATES.SLEEP_LOOP) return;
            this._setAction('sleep_loop');          // R138 的 3 个睡姿 (偶尔换个睡姿)
            this._sleepShiftTimer = this._setTimeout(() => {
                this._sleepShiftTimer = null;
                if (!this._running || this.state !== STATES.SLEEP_LOOP) return;
                this._setAction('sleep_breath');
                this._scheduleSleepShift();
            }, this.config.sleep_shift_duration_ms);
        }, wait);
    }

    _clearSleepShift() {
        if (this._sleepShiftTimer !== null) {
            this._clearTimeout(this._sleepShiftTimer);
            this._sleepShiftTimer = null;
        }
    }

    _onWakeUpFinished() {
        if (this.state !== STATES.WAKE_UP) return false;
        this._wokeAt = this._now();
        // R153: 醒来后伸个懒腰 (有语义的收尾动作), 再回到站立
        if (this.config.stretch_after_wake) {
            this._transition(STATES.GESTURE, 'wake_up-finished');
            this._setAction('stretch');
            const ms = Math.round((GESTURE_DURATION_MS.stretch || 1000) * 1.2);
            this._timer = this._setTimeout(() => {
                this._timer = null;
                if (!this._running || this._dragging) return;
                if (this.state !== STATES.GESTURE) return;
                this._transition(STATES.IDLE, 'stretch-complete');
                this._setAction('idle');
                this._scheduleIdle();
            }, ms);
            return true;
        }
        this._transition(STATES.IDLE, 'wake_up-finished');
        this._setAction('idle');
        this._scheduleIdle();
        return true;
    }

    // ---------- 外部事件 ----------

    /**
     * renderer 播放完一次性动画后的回调
     * @param {string} action 动画名 (sleep_enter / wake_up)
     */
    onAnimationFinished(action) {
        if (action === 'sleep_enter') return this._onSleepEnterFinished();
        if (action === 'wake_up') return this._onWakeUpFinished();
        return false;
    }

    /**
     * 用户拖拽状态变化
     * @param {boolean} dragging
     */
    setDragging(dragging) {
        if (this._dragging === dragging) return false;
        this._dragging = dragging;
        if (dragging) {
            // 拖拽优先: 停掉所有行为计时器和位移
            if (this._timer !== null) { this._clearTimeout(this._timer); this._timer = null; }
            if (this._holdTimer !== null) { this._clearTimeout(this._holdTimer); this._holdTimer = null; }
            this._stopMoveTimer();
            this._movePaused = false;
            this._transition(STATES.DRAGGING, 'user-drag-start');
            this._setAction('idle');
        } else {
            // R147: 醒来动画进行中时, 松手不得把状态打回 idle (否则会闪一下站姿)
            if (this.state === STATES.WAKE_UP) {
                this._dragging = false;
                return true;
            }
            this._transition(STATES.IDLE, 'user-drag-end');
            this._setAction('idle');
            // 短暂过渡后恢复自主行为
            if (this._pendingResume !== null) { this._clearTimeout(this._pendingResume); }
            this._pendingResume = this._setTimeout(() => {
                this._pendingResume = null;
                if (this._running && !this._dragging) this._scheduleIdle();
            }, this.config.drag_resume_delay_ms);
        }
        return true;
    }

    isDragging() { return this._dragging; }

    // ---------- R147: 点击反馈与睡眠唤醒 ----------

    /**
     * 用户单击角色 (不是拖拽)。
     *
     * 职责:
     *   1) 结束"按住"状态 (拖拽态), 但**不**先切回 idle 再切别的动作
     *      —— 睡眠点击时直接进入 wake_up, 避免闪一下站姿 (不瞬移, 走完整过渡动画)
     *   2) 非睡眠场景: 暂缓自主行为计时器, 保证点击反馈期间不会被 walk 立刻覆盖
     *
     * @param {string} prevAction 按下之前的动作名 (idle / walk_* / sleep_*)
     * @param {number} [holdMs] 暂缓时长
     * @returns {'react'|'wake'|'ignored'}
     */
    onUserClick(prevAction, holdMs) {
        if (!this._running) return 'ignored';
        const wasSleeping = (prevAction === 'sleep_loop' || prevAction === 'sleep_enter');
        // 结束拖拽态 (用户仍按着角色 → 引擎进入 DRAGGING)
        if (this._dragging) {
            this._dragging = false;
            if (this.state === STATES.DRAGGING) {
                if (wasSleeping) {
                    // 睡眠被点击 → 直接进入醒来流程 (wake_up 一次性动画负责过渡)
                    this._clearPendingTimers();
                    this._transition(STATES.WAKE_UP, 'user-click-wake');
                    this._setAction('wake_up');
                    return 'wake';
                }
                this._transition(STATES.IDLE, 'user-click');
                this._setAction('idle');
            }
        }
        if (wasSleeping) {
            this._clearPendingTimers();
            // R147: 已经在醒来流程中 → 不得重复下发 wake_up (否则会重播醒来动画)
            if (this.state === STATES.WAKE_UP) return 'wake';
            this._transition(STATES.WAKE_UP, 'user-click-wake');
            this._setAction('wake_up');
            return 'wake';
        }
        this.holdBriefly(holdMs);
        return 'react';
    }

    /**
     * 暂缓自主行为 (点击反馈期间), 期间结束后恢复原有排程。
     * 绝不消耗随机源 —— 原有随机序列不受影响。
     * @param {number} [ms]
     */
    holdBriefly(ms) {
        if (!this._running) return false;
        const delay = (typeof ms === 'number' && ms > 0) ? ms : 700;
        // R170: 记住被打断的"有时长"状态 (办公/吃水果/坐/打盹) 及其**剩余时间**。
        //   旧实现只是把计时器清掉, 之后没人重新排程 ⇒ 状态被永久卡死
        //   (例如办公中点一下角色, 引擎永远停在 WORK, 场景再也走不了)。
        const heldKind = this._stateTimerKind;
        const heldState = this.state;
        const heldRemaining = heldKind
            ? Math.max(500, (this._stateDeadline || 0) - this._now())
            : null;
        if (this._timer !== null) { this._clearTimeout(this._timer); this._timer = null; }
        this._stateTimerKind = null;
        this._stateDeadline = 0;
        if (this._holdTimer !== null) { this._clearTimeout(this._holdTimer); this._holdTimer = null; }
        // 行走中 → 暂停位移计时器, 保留剩余距离, 反馈结束后继续走完
        if (this.state === STATES.WALK_LEFT || this.state === STATES.WALK_RIGHT) {
            this._stopMoveTimer();
            this._movePaused = true;
        }
        this._holdTimer = this._setTimeout(() => {
            this._holdTimer = null;
            if (!this._running || this._dragging) return;
            if (this._movePaused) {
                this._movePaused = false;
                if (this.state === STATES.WALK_LEFT || this.state === STATES.WALK_RIGHT) {
                    this._lastMoveAt = this._now();
                    this._startMoveTimer();
                }
                return;
            }
            // R170: 按剩余时间**恢复**被打断的状态 (办公/吃水果不会被点击打断掉)
            if (heldKind && heldRemaining !== null
                && this.state === heldState && this._stateTimerKind === null) {
                this._resumeStateTimer(heldKind, heldRemaining);
                return;
            }
            if (this.state === STATES.IDLE) this._scheduleIdle();
        }, delay);
        return true;
    }

    /**
     * 用户点击唤醒 (sleep_loop → wake_up → idle)。
     * 必须走 wake_up 一次性动画, 不得直接瞬移成站姿。
     */
    wakeUpByUser() {
        if (!this._running) return false;
        this._clearPendingTimers();
        if (this.state === STATES.WAKE_UP) return true;
        this._transition(STATES.WAKE_UP, 'user-click-wake');
        this._setAction('wake_up');
        return true;
    }

    // ====== R177: 桌宠控制菜单的命令入口 ======
    //
    // 【硬约束】菜单里的每一项都必须走**正式行为系统**:
    //   调用的就是自主决策用的那几条内部路径 (_enterSleep / _startSit / _startWork /
    //   _startEatFruit / _startGesture / wakeUpByUser),
    //   因此状态转移、冷却、计时器、道具挂载、动作结束后的回落**全部复用**,
    //   **不存在"只播一张演示图"的旁路**。
    //   与自主决策的差别只有两点:
    //     ① 不受"同类冷却"限制 (用户明确要求, 就该立刻生效);
    //     ② 接管当前排程 (清掉待触发的计时器), 否则会被下一次自主决策立刻覆盖。

    /**
     * 手动触发一类活动。
     * @param {'sleep'|'wake'|'sit'|'doze'|'work'|'eat_fruit'|'gesture'} kind
     * @returns {{ok:boolean, kind?:string, state?:string, error?:string}}
     */
    command(kind) {
        if (!this._running) return { ok: false, error: 'engine not running' };
        if (this._dragging) return { ok: false, error: 'dragging' };
        const sleeping = (this.state === STATES.SLEEP_ENTER || this.state === STATES.SLEEP_LOOP);
        if (kind === 'sleep' && sleeping) return { ok: false, error: 'already sleeping' };
        if (kind === 'wake' && !sleeping && this.state !== STATES.WAKE_UP) {
            return { ok: false, error: 'not sleeping' };
        }
        // 接管排程: 清掉待触发的行为计时器 + 停掉行走位移 (否则会边走边做)
        this._clearPendingTimers();
        if (this._moveTimer !== null) { this._stopMoveTimer(); this._movePaused = false; }
        switch (kind) {
            case 'sleep': this._enterSleep(); break;
            case 'wake': this.wakeUpByUser(); break;
            case 'sit': this._startSit(); break;
            case 'doze': this._startDoze(); break;
            case 'work': this._startWork(); break;
            case 'eat_fruit': this._startEatFruit(); break;
            case 'gesture': this._startGesture(); break;
            default: return { ok: false, error: `unknown command: ${kind}` };
        }
        return { ok: true, kind, state: this.state };
    }

    /**
     * R177: 运行时更新行为参数 (设置面板改频率档位时调用)。
     * 只改数值, **不改状态机逻辑**。
     * @param {object} patch
     * @returns {object} 合并后的 config
     */
    applyConfig(patch) {
        if (patch && typeof patch === 'object') {
            for (const [k, v] of Object.entries(patch)) {
                if (typeof v === 'number' && Number.isFinite(v)) this.config[k] = v;
                else if (typeof v === 'boolean') this.config[k] = v;
            }
        }
        return Object.assign({}, this.config);
    }

    _clearPendingTimers() {
        if (this._timer !== null) { this._clearTimeout(this._timer); this._timer = null; }
        if (this._holdTimer !== null) { this._clearTimeout(this._holdTimer); this._holdTimer = null; }
        this._clearSleepShift();
        if (this._pendingResume !== null) { this._clearTimeout(this._pendingResume); this._pendingResume = null; }
        this._stateTimerKind = null;   // R170
        this._stateDeadline = 0;       // R170
    }

    getState() { return this.state; }

    getStatePriority() { return STATE_PRIORITY[this.state] || 0; }

    // 供测试与诊断
    snapshot() {
        return {
            state: this.state,
            running: this._running,
            dragging: this._dragging,
            walkRemaining: Math.round(this._walkRemaining),
            walkTarget: this._walkTarget,
            walkDirection: this._walkDirection,
            hasTimer: this._timer !== null,
            hasMoveTimer: this._moveTimer !== null,
            hasHoldTimer: this._holdTimer !== null,
            movePaused: this._movePaused,
            lastActivity: this._lastActivity,
            lastGesture: this._lastGesture,
            // R170: 冷却基准与状态计时器 (供运行时证据/诊断)
            lastWorkAt: this._lastWorkAt,
            lastEatFruitAt: this._lastEatFruitAt,
            stateTimerKind: this._stateTimerKind,
            stateDeadline: this._stateDeadline,
            hasSleepShiftTimer: this._sleepShiftTimer !== null,
            // R177: 当前心情与生效的频率系数 (供设置面板/诊断读取)
            mood: this.getMood(),
            activityRateIntervalScale: this.config.activity_rate_interval_scale,
            activityWeightScale: this.config.activity_weight_scale,
            sleepWeightScale: this.config.sleep_weight_scale,
            pendingTimerCount: [this._timer, this._moveTimer, this._holdTimer, this._pendingResume]
                .filter((t) => t !== null).length,
            transitionLog: this.transitionLog.slice(-20),
        };
    }
}

module.exports = {
    BehaviorEngine,
    ACTIVITY_KINDS,
    STATES,
    STATE_ACTION,
    STATE_PRIORITY,
    ONE_SHOT_ACTIONS,
    LOOP_ACTIONS,
    DEFAULT_CONFIG,
};
