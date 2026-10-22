// R177 本地数据保存 (纯 Node 模块, 可单元测试)
//
// 【边界声明】
//   · 只写**本机文件** (Electron app.getPath('userData')), 不联网、不上传、不注册云端。
//   · 保存的是**桌宠设置**与**基础心情状态**, 不是"AI 长期记忆"。
//   · 写入用**临时文件 + rename** (原子), 避免写一半断电导致文件损坏。
//   · 读回时做**结构校验**: 字段缺失/类型不对/文件损坏 ⇒ 回退默认值, 绝不抛异常拖垮启动。

'use strict';

const fs = require('fs');
const path = require('path');

const SETTINGS_FILE = 'pet_settings.json';
const MOOD_FILE = 'pet_mood_state.json';

// —— 设置默认值 ——
// activity_rate / sleep_rate: 'low' | 'normal' | 'high'
const DEFAULT_SETTINGS = Object.freeze({
    pet_scale: 1.0,             // 桌宠大小倍率 (0.6 ~ 1.6)
    activity_rate: 'normal',     // 自主活动频率
    sleep_rate: 'normal',        // 睡眠频率
    click_feedback: true,        // 点击反馈开关
    launch_at_login: false,      // 开机自动启动
});

const SCALE_MIN = 0.6;
const SCALE_MAX = 1.6;
const RATES = Object.freeze(['low', 'normal', 'high']);

// 频率档位 → 实际参数
//   interval: 自主决策间隔乘子 (越小越频繁)
//   weight:   自主活动权重乘子 (不含睡眠)
//   sleep:    睡眠权重乘子
const ACTIVITY_RATE_TABLE = Object.freeze({
    low: Object.freeze({ interval: 1.8, weight: 0.6 }),
    normal: Object.freeze({ interval: 1.0, weight: 1.0 }),
    high: Object.freeze({ interval: 0.6, weight: 1.4 }),
});
const SLEEP_RATE_TABLE = Object.freeze({
    low: Object.freeze({ sleep: 0.35 }),
    normal: Object.freeze({ sleep: 1.0 }),
    high: Object.freeze({ sleep: 2.0 }),
});

/** 把任意输入夹成合法设置 (逐字段, 不做整体替换)。 */
function sanitizeSettings(input) {
    const src = (input && typeof input === 'object') ? input : {};
    const out = Object.assign({}, DEFAULT_SETTINGS);
    if (typeof src.pet_scale === 'number' && Number.isFinite(src.pet_scale)) {
        out.pet_scale = Math.min(SCALE_MAX, Math.max(SCALE_MIN, Math.round(src.pet_scale * 100) / 100));
    }
    if (RATES.includes(src.activity_rate)) out.activity_rate = src.activity_rate;
    if (RATES.includes(src.sleep_rate)) out.sleep_rate = src.sleep_rate;
    if (typeof src.click_feedback === 'boolean') out.click_feedback = src.click_feedback;
    if (typeof src.launch_at_login === 'boolean') out.launch_at_login = src.launch_at_login;
    return out;
}

/** 频率档位 → 行为参数 (引擎用)。 */
function rateEffects(activityRate, sleepRate) {
    const a = ACTIVITY_RATE_TABLE[activityRate] || ACTIVITY_RATE_TABLE.normal;
    const s = SLEEP_RATE_TABLE[sleepRate] || SLEEP_RATE_TABLE.normal;
    return {
        idle_interval: a.interval,
        activity_weight: a.weight,
        sleep_weight: s.sleep,
    };
}

class SettingsStore {
    /**
     * @param {object} opts
     * @param {string} opts.dir  存储目录 (Electron: app.getPath('userData'))
     * @param {object} [opts.fs] 文件系统实现 (测试注入)
     */
    constructor(opts = {}) {
        this.dir = opts.dir || process.cwd();
        this.fs = opts.fs || fs;
        this.settingsPath = path.join(this.dir, SETTINGS_FILE);
        this.moodPath = path.join(this.dir, MOOD_FILE);
        this.lastError = null;
    }

    _ensureDir() {
        try {
            if (!this.fs.existsSync(this.dir)) this.fs.mkdirSync(this.dir, { recursive: true });
            return true;
        } catch (e) {
            this.lastError = e && e.message;
            return false;
        }
    }

    _readJson(file) {
        try {
            if (!this.fs.existsSync(file)) return null;
            const raw = this.fs.readFileSync(file, 'utf8');
            if (!raw || !raw.trim()) return null;
            return JSON.parse(raw);
        } catch (e) {
            // 损坏/不可读 ⇒ 当作没有, 回退默认值 (绝不抛异常拖垮启动)
            this.lastError = e && e.message;
            return null;
        }
    }

    _writeJsonAtomic(file, data) {
        if (!this._ensureDir()) return false;
        const tmp = `${file}.tmp`;
        try {
            this.fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf8');
            this.fs.renameSync(tmp, file);
            this.lastError = null;
            return true;
        } catch (e) {
            this.lastError = e && e.message;
            try { if (this.fs.existsSync(tmp)) this.fs.unlinkSync(tmp); } catch (e2) { /* 忽略 */ }
            return false;
        }
    }

    /** 读取设置 (缺失/损坏 ⇒ 默认值)。 */
    loadSettings() {
        const raw = this._readJson(this.settingsPath);
        return sanitizeSettings(raw);
    }

    /** 保存设置 (逐字段夹紧后写入)。 */
    saveSettings(patch) {
        const merged = sanitizeSettings(Object.assign({}, this.loadSettings(), patch || {}));
        const ok = this._writeJsonAtomic(this.settingsPath, merged);
        return { ok, settings: merged };
    }

    /** 读取心情状态 (缺失/损坏 ⇒ null)。 */
    loadMoodState() {
        const raw = this._readJson(this.moodPath);
        if (!raw || typeof raw !== 'object') return null;
        return raw;
    }

    /** 保存心情状态。 */
    saveMoodState(state) {
        if (!state || typeof state !== 'object') return false;
        return this._writeJsonAtomic(this.moodPath, state);
    }

    /** 一次性读出全部 (启动时用)。 */
    loadAll() {
        return {
            settings: this.loadSettings(),
            mood: this.loadMoodState(),
        };
    }
}

module.exports = {
    DEFAULT_SETTINGS,
    SCALE_MIN,
    SCALE_MAX,
    RATES,
    ACTIVITY_RATE_TABLE,
    SLEEP_RATE_TABLE,
    SETTINGS_FILE,
    MOOD_FILE,
    SettingsStore,
    sanitizeSettings,
    rateEffects,
};
