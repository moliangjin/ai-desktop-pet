// R177 设置面板 (独立窗口, 不叠在桌宠上, 不污染桌宠外观)
//
// 【边界】
//   · 只读写**本机**设置文件 (主进程 SettingsStore), 不联网、不上传。
//   · 所有修改都走主进程的 'settings-set' → applySettingsPatch → 落盘 + 应用到运行时,
//     面板自己**不碰**磁盘, 也不自己改行为引擎。
//   · 面板只做"输入 → 发给主进程 → 拿回权威值 → 刷新显示"。

'use strict';

const { ipcRenderer } = require('electron');

const $ = (id) => document.getElementById(id);

const el = {
    scale: $('scale'),
    scaleValue: $('scaleValue'),
    activityRate: $('activityRate'),
    sleepRate: $('sleepRate'),
    clickFeedback: $('clickFeedback'),
    launchAtLogin: $('launchAtLogin'),
    loginDesc: $('loginDesc'),
    moodDot: $('moodDot'),
    moodName: $('moodName'),
    energyBar: $('energyBar'),
    moodNote: $('moodNote'),
    status: $('status'),
};

const MOOD_DOT_COLORS = {
    happy: '#ffb020',
    calm: '#3f8cff',
    sleepy: '#9b8cff',
    bored: '#8fa0b5',
};

const MOOD_NOTES = {
    happy: '刚被你逗过，心情不错，动作会更活泼。',
    calm: '状态平稳，按你设的频率过日子。',
    sleepy: '困了，动作变少，更想打盹或睡觉。',
    bored: '好久没人理，有点无聊，会自己找点事做。',
};

let current_ = null;      // 主进程返回的权威设置
let capabilities_ = null;  // 主进程返回的能力边界 (如是否支持开机自启)
let loginItem_ = null;    // R179: 主进程返回的"开机自启是否真的生效"
let busy_ = false;

function setStatus(text, isError) {
    el.status.textContent = text || '';
    el.status.style.color = isError ? '#e05a5a' : '#3f8cff';
    if (text) {
        clearTimeout(setStatus._t);
        setStatus._t = setTimeout(() => { el.status.textContent = ''; }, 2200);
    }
}

/** 把权威设置渲染到界面上。 */
function render(settings, mood, capabilities, loginItem) {
    current_ = settings;
    if (capabilities) capabilities_ = capabilities;
    if (loginItem) loginItem_ = loginItem;

    // 桌宠大小
    const pct = Math.round((Number(settings.pet_scale) || 1) * 100);
    el.scale.value = String(pct);
    el.scaleValue.textContent = `${pct}%`;

    // 分段选择器
    for (const [container, key] of [[el.activityRate, 'activity_rate'], [el.sleepRate, 'sleep_rate']]) {
        for (const btn of container.querySelectorAll('button')) {
            btn.classList.toggle('on', btn.dataset.v === settings[key]);
        }
    }

    // 开关
    el.clickFeedback.checked = !!settings.click_feedback;

    const canLogin = !capabilities_ || capabilities_.launch_at_login !== false;
    el.launchAtLogin.checked = !!settings.launch_at_login;
    el.launchAtLogin.disabled = !canLogin;
    // R179: 开关打开但系统实际没接受 ⇒ 如实说明, 不能让用户以为已经生效
    if (!canLogin) {
        el.loginDesc.textContent = '当前系统不支持开机自启（macOS / Windows 支持）';
    } else if (settings.launch_at_login && loginItem_ && loginItem_.ok === false) {
        el.loginDesc.textContent = `⚠️ ${loginItem_.reason || '开机自启未生效'}`;
        el.loginDesc.style.color = '#e05a5a';
    } else {
        el.loginDesc.textContent = '开机后自动在桌面出现';
        el.loginDesc.style.color = '';
    }

    // 心情
    if (mood) {
        el.moodName.textContent = mood.label || '平静';
        el.moodDot.style.background = MOOD_DOT_COLORS[mood.mood] || MOOD_DOT_COLORS.calm;
        const energy = Math.max(0, Math.min(1, typeof mood.energy === 'number' ? mood.energy : 1));
        el.energyBar.style.width = `${Math.round(energy * 100)}%`;
        el.moodNote.textContent = MOOD_NOTES[mood.mood] || MOOD_NOTES.calm;
    }
}

/** 改一个设置项 → 发给主进程 → 用返回的权威值重绘。 */
async function patch(partial) {
    if (busy_) return;
    busy_ = true;
    try {
        const res = await ipcRenderer.invoke('settings-set', partial);
        if (res && res.ok) {
            render(res.settings, res.mood, capabilities_, res.login_item);
            // R179: 设置存上了, 但"开机自启"可能被系统拒绝 ⇒ 必须如实提示
            if (res.login_item && res.login_item.ok === false && res.settings.launch_at_login) {
                setStatus(`已保存，但开机自启未生效：${res.login_item.reason}`, true);
            } else {
                setStatus('已保存');
            }
        } else {
            // R179: 落盘失败时**不能**显示"已保存"。
            //   这里把界面按主进程返回的权威值重画一遍 (控件回到真实状态),
            //   再明确告诉用户"没存上"。
            const why = (res && res.error) || '未知错误';
            if (res && res.settings) render(res.settings, res.mood, capabilities_, res.login_item);
            setStatus(`保存失败（设置未改动）：${why}`, true);
            console.error('[settings] R177 SAVE_FAILED', why);
        }
    } catch (e) {
        setStatus(`保存失败：${(e && e.message) || e}`, true);
    } finally {
        busy_ = false;
    }
}

// ====== 事件绑定 ======

el.scale.addEventListener('input', () => {
    // 拖动时只更新数字, 松手才落盘 (避免写几十次文件)
    el.scaleValue.textContent = `${el.scale.value}%`;
});
el.scale.addEventListener('change', () => {
    patch({ pet_scale: Number(el.scale.value) / 100 });
});

for (const [container, key] of [[el.activityRate, 'activity_rate'], [el.sleepRate, 'sleep_rate']]) {
    container.addEventListener('click', (ev) => {
        const btn = ev.target.closest('button');
        if (!btn || !btn.dataset.v) return;
        const partial = {};
        partial[key] = btn.dataset.v;
        patch(partial);
    });
}

el.clickFeedback.addEventListener('change', () => {
    patch({ click_feedback: el.clickFeedback.checked });
});

el.launchAtLogin.addEventListener('change', () => {
    if (el.launchAtLogin.disabled) return;
    patch({ launch_at_login: el.launchAtLogin.checked });
});

// ====== 主进程推送 (设置/心情变化) → 面板跟着刷新 =====
ipcRenderer.on('settings-changed', (_evt, payload) => {
    if (!payload) return;
    render(payload.settings, payload.mood, capabilities_, payload.login_item);
});
ipcRenderer.on('mood-changed', (_evt, payload) => {
    if (!payload) return;
    render(current_ || {}, payload, capabilities_);
});

// ====== 启动: 读一次权威状态 =====
(async () => {
    try {
        const res = await ipcRenderer.invoke('settings-get');
        if (res && res.ok) {
            render(res.settings, res.mood, res.capabilities, res.login_item);
            console.log(`[settings] R177 PANEL_READY settings=${JSON.stringify(res.settings)} mood=${res.mood && res.mood.mood}`);
        } else {
            setStatus('读取设置失败', true);
            console.error('[settings] R177 PANEL_READY_FAILED', res && res.error);
        }
    } catch (e) {
        setStatus(`读取设置失败：${(e && e.message) || e}`, true);
        console.error('[settings] R177 PANEL_READY_ERROR', e && e.message);
    }
})();
