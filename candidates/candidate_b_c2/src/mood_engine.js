// R177 本地性格与心情系统 (纯逻辑模块, 无 Electron 依赖, 可单元测试)
//
// 【边界声明 —— 必须写在最前面】
//   · 纯**规则驱动**: 心情只由**真实运行时事件**推导 (用户交互次数/闲置时长/
//     清醒时长/本地时段/睡眠次数), 不含任何预置对话文本、不调用任何模型或网络。
//   · 心情**不产生台词**。它只影响: ①自主活动的权重与节奏 ②点击反馈的动作偏好
//     ③点击反馈是否启用。桌宠不会"说话", 也就不会用预设文字冒充 AI 人格。
//   · 心情状态可以持久化 (本地 JSON), 但它**不是**长期记忆, 只是"基础心情状态"。
//
// 【心情是怎么判出来的】(全部可复算, 无随机)
//   happy  开心 : 最近 3 分钟内用户交互次数多 (点击/菜单/拖拽)
//   sleepy 困倦 : 本地深夜时段 (23:00~06:00) 或连续清醒很久没睡
//   bored  无聊 : 长时间既没有用户交互、也没有自主活动
//   calm   平静 : 基准 (其它心情分数都没超过它时)
//
// 【心情怎么影响行为】
//   activity_weights : 各类自主活动的权重乘子 (开心 → 爱动; 困倦 → 爱打盹; 无聊 → 想找事做)
//   idle_interval    : 自主决策间隔乘子 (越小越活跃)
//   click_weights    : 点击反馈动作池权重乘子 (开心 → 偏活泼; 困倦 → 偏轻量)

'use strict';

const MOODS = Object.freeze({
    HAPPY: 'happy',
    CALM: 'calm',
    SLEEPY: 'sleepy',
    BORED: 'bored',
});

// R177: 合法心情值集合 (注意 MOODS 的键是大写、值是小写, 判断"值是否合法"必须用值集合)
const MOOD_VALUES = Object.freeze(Object.values(MOODS));

const MOOD_LABELS = Object.freeze({
    happy: '开心',
    calm: '平静',
    sleepy: '困倦',
    bored: '无聊',
});

const DEFAULT_MOOD_CONFIG = Object.freeze({
    // —— 分数阈值 ——
    calm_base: 0.6,
    happy_window_ms: 180000,        // 互动计数窗口 = 3 分钟
    happy_per_interaction: 0.8,
    happy_max: 1.6,
    bored_idle_per_minute: 0.35,
    bored_max: 1.8,
    sleepy_night_start_hour: 23,
    sleepy_night_end_hour: 6,
    sleepy_night_score: 1.2,
    sleepy_awake_per_hour: 0.4,
    sleepy_max: 2.0,
    // —— 心情对行为的调制 ——
    // idle_interval 越小 = 自主决策越频繁 (越活跃)
    idle_interval: Object.freeze({ happy: 0.7, calm: 1.0, sleepy: 1.5, bored: 0.6 }),
    activity_weights: Object.freeze({
        happy: Object.freeze({ gesture: 1.6, walk: 1.3, sit: 0.8, doze: 0.5, work: 1.0, eat_fruit: 1.2, sleep: 0.5 }),
        calm: Object.freeze({ gesture: 1.0, walk: 1.0, sit: 1.0, doze: 1.0, work: 1.0, eat_fruit: 1.0, sleep: 1.0 }),
        sleepy: Object.freeze({ gesture: 0.6, walk: 0.5, sit: 1.4, doze: 2.2, work: 0.4, eat_fruit: 0.6, sleep: 2.0 }),
        bored: Object.freeze({ gesture: 1.5, walk: 1.4, sit: 0.6, doze: 0.5, work: 1.2, eat_fruit: 1.3, sleep: 0.6 }),
    }),
    click_weights: Object.freeze({
        happy: Object.freeze({ cheer_wave: 1.5, cheer_hands_up: 1.5, cheer_heart: 1.8, cheer_clap: 1.4, cheer_jump: 1.3, cheer_tilt: 1.2 }),
        calm: Object.freeze({ cheer_wave: 1.0, cheer_hands_up: 1.0, cheer_heart: 1.0, cheer_clap: 1.0, cheer_jump: 1.0, cheer_tilt: 1.0 }),
        sleepy: Object.freeze({ cheer_wave: 0.8, cheer_hands_up: 0.6, cheer_heart: 0.7, cheer_clap: 0.5, cheer_jump: 0.3, cheer_tilt: 0.6 }),
        bored: Object.freeze({ cheer_wave: 1.1, cheer_hands_up: 1.0, cheer_heart: 1.0, cheer_clap: 1.0, cheer_jump: 1.0, cheer_tilt: 1.2 }),
    }),
    // R177: 困倦时是否**完全禁用**点击反馈。
    //   默认 false —— 这是刻意改的: R156/R162 有一条既有产品不变量
    //   "点击必须产生可见反馈"(e2e 的 TG2/TH5/TI1_1/TI1_2/TI1_24 五组判据都在守它)。
    //   心情对"互动反馈"的影响**只用权重表达**(困倦 ⇒ 偏轻量动作), 不做静默吞掉,
    //   否则夜里点她没反应会被当成 bug。保留这个开关是为了将来可能需要显式关闭。
    sleepy_suppress_click: false,
});

/**
 * 心情引擎。
 *
 * 用法 (主进程持有唯一实例):
 *   const mood = new MoodEngine({ state: loadedState });
 *   mood.noteInteraction();            // 用户点了角色 / 用了菜单 / 拖了桌宠
 *   mood.noteActivity('work');         // 引擎切换到某类自主活动
 *   mood.noteSleep();                  // 睡了一觉 (精力恢复)
 *   const snap = mood.update();        // 重新判定心情 (可定期调用)
 *   mood.getMood();                    // 'happy' | 'calm' | 'sleepy' | 'bored'
 */
class MoodEngine {
    constructor(opts = {}) {
        this.config = Object.assign({}, DEFAULT_MOOD_CONFIG, opts.config || {});
        this._now = opts.now || (() => Date.now());
        const st = opts.state || {};
        this.state = {
            mood: MOOD_VALUES.includes(st.mood) ? st.mood : MOODS.CALM,
            energy: typeof st.energy === 'number' ? Math.max(0, Math.min(1, st.energy)) : 1,
            interactionCount: Number.isFinite(st.interactionCount) ? st.interactionCount : 0,
            interactionWindowStart: Number.isFinite(st.interactionWindowStart) ? st.interactionWindowStart : 0,
            lastInteractionAt: Number.isFinite(st.lastInteractionAt) ? st.lastInteractionAt : 0,
            lastActivityAt: Number.isFinite(st.lastActivityAt) ? st.lastActivityAt : 0,
            lastSleepAt: Number.isFinite(st.lastSleepAt) ? st.lastSleepAt : 0,
            awakeSince: Number.isFinite(st.awakeSince) ? st.awakeSince : 0,
            sleepCount: Number.isFinite(st.sleepCount) ? st.sleepCount : 0,
        };
        this._scores = null;
    }

    // ---------- 事件输入 (全部来自真实运行时) ----------

    /** 用户与桌宠发生了一次交互 (点击/菜单/拖拽)。 */
    noteInteraction(at) {
        const now = typeof at === 'number' ? at : this._now();
        const st = this.state;
        if (!st.interactionWindowStart || (now - st.interactionWindowStart) > this.config.happy_window_ms) {
            st.interactionWindowStart = now;
            st.interactionCount = 0;
        }
        st.interactionCount += 1;
        st.lastInteractionAt = now;
        // 有交互 ⇒ 不再"无聊" (无聊看的是"既没交互也没活动")
        return this.update(now);
    }

    /** 引擎切换到了某类自主活动。 */
    noteActivity(kind, at) {
        const now = typeof at === 'number' ? at : this._now();
        this.state.lastActivityAt = now;
        if (kind === 'sleep') this.noteSleep(now);
        return this.update(now);
    }

    /** 睡了一觉 ⇒ 精力恢复。 */
    noteSleep(at) {
        const now = typeof at === 'number' ? at : this._now();
        this.state.lastSleepAt = now;
        this.state.sleepCount += 1;
        this.state.awakeSince = 0;
        this.state.energy = 1;
        return this.update(now);
    }

    /** 醒着 ⇒ 记录清醒起点 (第一次唤醒时初始化)。 */
    noteAwake(at) {
        const now = typeof at === 'number' ? at : this._now();
        if (!this.state.awakeSince) this.state.awakeSince = now;
        return this.update(now);
    }

    // ---------- 判定 ----------

    /**
     * 重新判定心情。
     * @param {number} [at] 时间戳 (默认用注入时钟)
     * @param {number} [hour] 本地小时 (0-23, 默认由时间戳推出)
     * @returns {object} { mood, prev, changed, scores, label }
     */
    update(at, hour) {
        const now = typeof at === 'number' ? at : this._now();
        const cfg = this.config;
        const st = this.state;
        const localHour = typeof hour === 'number'
            ? hour
            : new Date(now).getHours();

        // 互动窗口过期 ⇒ 计数清零
        if (st.interactionWindowStart && (now - st.interactionWindowStart) > cfg.happy_window_ms) {
            st.interactionCount = 0;
            st.interactionWindowStart = now;
        }

        const scores = {};
        scores.calm = cfg.calm_base;

        // 开心: 窗口内交互次数
        scores.happy = Math.min(cfg.happy_max, st.interactionCount * cfg.happy_per_interaction);

        // 困倦: 深夜时段 + 连续清醒时长
        const night = (localHour >= cfg.sleepy_night_start_hour) || (localHour < cfg.sleepy_night_end_hour);
        const awakeSince = st.awakeSince || (st.lastSleepAt || now);
        const awakeHours = Math.max(0, (now - awakeSince) / 3600000);
        scores.sleepy = Math.min(cfg.sleepy_max,
            (night ? cfg.sleepy_night_score : 0) + awakeHours * cfg.sleepy_awake_per_hour);

        // 无聊: 既没交互也没自主活动的时长
        //   基准: 有过交互/活动 ⇒ 从最后一次算起; 从来没有过 ⇒ 从"醒来时刻"算起
        //   (否则刚启动、用户还没碰过她时 idleMinutes 恒为 0 ⇒ 永远不会无聊)
        const lastSocial = Math.max(st.lastInteractionAt || 0, st.lastActivityAt || 0);
        const idleBase = lastSocial > 0 ? lastSocial : (st.awakeSince || 0);
        const idleMinutes = idleBase > 0 ? Math.max(0, (now - idleBase) / 60000) : 0;
        scores.bored = Math.min(cfg.bored_max, idleMinutes * cfg.bored_idle_per_minute);

        // 精力随清醒时间缓慢下降 (睡眠恢复)
        st.energy = Math.max(0, Math.min(1, st.energy - awakeHours * 0.05));

        // 选最高分; 平分时**平静**优先 (基准最稳)
        let mood = MOODS.CALM;
        for (const m of [MOODS.HAPPY, MOODS.SLEEPY, MOODS.BORED]) {
            if (scores[m] > scores[mood]) mood = m;
        }
        const prev = st.mood;
        st.mood = mood;
        this._scores = scores;
        return {
            mood, prev, changed: prev !== mood, scores: Object.assign({}, scores),
            label: MOOD_LABELS[mood],
        };
    }

    getMood() { return this.state.mood; }
    getLabel() { return MOOD_LABELS[this.state.mood] || MOOD_LABELS.calm; }
    getScores() { return Object.assign({}, this._scores || {}); }
    getEnergy() { return this.state.energy; }

    // ---------- 心情 → 行为调制 ----------

    /** 自主决策间隔乘子 (越小越活跃)。 */
    idleIntervalScale(mood) {
        const m = this.config.idle_interval[mood || this.getMood()];
        return typeof m === 'number' ? m : 1;
    }

    /** 某类自主活动的权重乘子。 */
    activityWeight(kind, mood) {
        const table = this.config.activity_weights[mood || this.getMood()] || {};
        const w = table[kind];
        return typeof w === 'number' ? w : 1;
    }

    /** 点击反馈动作池权重乘子。 */
    clickWeight(action, mood) {
        const table = this.config.click_weights[mood || this.getMood()] || {};
        const w = table[action];
        return typeof w === 'number' ? w : 1;
    }

    /** 当前心情是否应该抑制点击反馈 (困倦 ⇒ 只想睡)。 */
    shouldSuppressClick(mood) {
        const m = mood || this.getMood();
        return !!this.config.sleepy_suppress_click && m === MOODS.SLEEPY;
    }

    // ---------- 持久化 ----------

    toJSON() {
        return {
            version: 1,
            mood: this.state.mood,
            energy: this.state.energy,
            interactionCount: this.state.interactionCount,
            interactionWindowStart: this.state.interactionWindowStart,
            lastInteractionAt: this.state.lastInteractionAt,
            lastActivityAt: this.state.lastActivityAt,
            lastSleepAt: this.state.lastSleepAt,
            awakeSince: this.state.awakeSince,
            sleepCount: this.state.sleepCount,
            savedAt: this._now(),
        };
    }

    /** 从持久化数据恢复 (重启后正确恢复基础心情状态)。 */
    restore(state) {
        if (!state || typeof state !== 'object') return false;
        const st = this.state;
        if (MOOD_VALUES.includes(state.mood)) st.mood = state.mood;
        for (const k of ['energy', 'interactionCount', 'interactionWindowStart',
            'lastInteractionAt', 'lastActivityAt', 'lastSleepAt', 'awakeSince', 'sleepCount']) {
            if (Number.isFinite(state[k])) st[k] = state[k];
        }
        return true;
    }
}

module.exports = {
    MOODS,
    MOOD_VALUES,
    MOOD_LABELS,
    DEFAULT_MOOD_CONFIG,
    MoodEngine,
};
