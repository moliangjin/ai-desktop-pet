// AI Pet Candidate B-C2 — Electron main process.
// Loads manifest, creates transparent+frameless BrowserWindow,
// launches the renderer with PixiJS sprite animation.
//
// V0.0 R98: C2 compact window mode (临时替代真透明穿透).
//   - --mode standard   → 256x256 (原 R60 基线)
//   - --mode compact    → 200x200 (C2 紧凑, 减少桌面遮挡)
//   模式切换经 set-mode IPC 实时调整, 配套 canvas/sprite 重置.
//
// CLI flags:
//   --manifest <path>    (required)
//   --size <px>          (default 256)
//   --mode standard|compact (default standard)
//   --x <px>, --y <px>   (window origin in macOS screen coords)
//   --quit-after <sec>   (auto-quit after N seconds; useful for tests)
//   --perf-out <path>    (write CSV perf samples here)

const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');
const fs = require('fs');
// R141: 最小自主生活行为引擎 (纯逻辑, main 与测试共用同一份代码)
const { BehaviorEngine, STATES } = require('./behavior_engine');
// R144: 资源就绪判定 (main 与测试共用同一份代码)
const { evaluateAssetReadiness, REQUIRED_ACTIONS } = require('./asset_gate');
// R177: 本地心情系统 + 本地设置存储 (纯离线 —— 不联网、不调模型、不上传任何数据)
const { MoodEngine } = require('./mood_engine');
const { SettingsStore, DEFAULT_SETTINGS, rateEffects, SCALE_MIN, SCALE_MAX, RATES, commitSettings } = require('./settings_store');
// R177: 右键菜单要用 Electron 原生 Menu (模板本身在纯模块里, 可单测)
const { Menu } = require('electron');
const { buildMenuTemplate } = require('./menu_template');

const args = process.argv.slice(1);
// R170: 行为状态日志的相对时间基准 (ms) —— 让"持续了多久/间隔多久"能从日志直接算
const R170_T0_ = Date.now();
let manifestPath = null, winSize = 256, winX = 200, winY = 200;
let initialMode = 'standard';
let quitAfter = null, perfOut = null;
let acceptanceMode = false;    // R141 §九: 验收加速模式 (不改变正式状态机逻辑)
let sleepProbabilityOverride = null;   // R144: 行为概率覆盖 (0=只走, 1=只睡), 供确定性验收脚本使用
let previewDir_ = null;        // R147: 运行时预览采集目录 (仅验收/预览用, 正式运行为 null)
let demoScene_ = null;         // R170: 验收专用入口 —— 直接进入某个场景 (work / eat_fruit / ...)
                              //   与"正式自主行为"**完全分离**: 自主决策被暂停, 不会随机跑掉
// ====== R177: 验收专用入口 (仅用于自动化验证, 正式运行不触发) ======
let r177Command_ = null;       // --r177-command <kind>       走**菜单同一条**代码路径触发行为
let r177ApplySettings_ = null; // --r177-apply-settings <json> 走**设置面板同一条**代码路径改设置
let r177DumpSettings_ = false; // --r177-dump-settings        启动后打印本地设置与心情状态
let r177OpenPanel_ = false;    // --r177-panel                启动后打开设置面板
let r177FaultSettings_ = false;// --r177-fault-settings       故障注入: 让本地存储写入必然失败
for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--manifest' && args[i+1]) manifestPath = args[++i];
    else if (a === '--size' && args[i+1]) winSize = parseInt(args[++i], 10);
    else if (a === '--mode' && args[i+1]) initialMode = args[++i];
    else if (a === '--x' && args[i+1]) winX = parseInt(args[++i], 10);
    else if (a === '--y' && args[i+1]) winY = parseInt(args[++i], 10);
    else if (a === '--quit-after' && args[i+1]) quitAfter = parseFloat(args[++i]);
    // R102 P0-5: 兼容 --quit-after=<value> 形式 (e.g. --quit-after=1800)
    else if (a.startsWith('--quit-after=')) quitAfter = parseFloat(a.split('=')[1], 10);
    else if (a === '--perf-out' && args[i+1]) perfOut = args[++i];
    // R147: 运行时预览采集 (输出 PNG 帧序列, 供生成可观看 GIF)
    else if (a === '--preview' && args[i+1]) previewDir_ = args[++i];
    // R170: 验收专用入口 —— 直接锁定在某个生活场景 (办公 / 吃水果), 自主行为暂停
    else if (a === '--demo-scene' && args[i+1]) demoScene_ = args[++i];
    // R141 §九: 验收加速模式 (只缩短时长参数, 不改变状态机逻辑)
    else if (a === '--acceptance') acceptanceMode = true;
    else if (a === '--acceptance-mode' && args[i+1]) acceptanceMode = (args[++i] !== 'off');
    // R144: 行为概率覆盖 — 只改 manifest 配置里的概率值, 不改状态机逻辑
    else if (a === '--sleep-probability' && args[i+1]) sleepProbabilityOverride = parseFloat(args[++i]);
    // ====== R177 验收专用入口 ======
    else if (a === '--r177-command' && args[i+1]) r177Command_ = args[++i];
    else if (a === '--r177-apply-settings' && args[i+1]) r177ApplySettings_ = args[++i];
    else if (a === '--r177-dump-settings') r177DumpSettings_ = true;
    else if (a === '--r177-panel') r177OpenPanel_ = true;
    else if (a === '--r177-fault-settings') r177FaultSettings_ = true;
}

// ====== R182: 单实例锁 ======
// 桌面图标被连着双击 / 用户重复启动时, 第二个实例必须**复用已有实例**,
// 绝不能拉起第二个桌宠进程 (两个透明窗口叠在一起, 行为引擎也会跑双份)。
//   · 必须在 app.whenReady() 之前申请
//   · 拿不到锁就安静退出 (退出码 0), 不再往下做任何初始化 (连 manifest 都不查)
//   · 第二个实例触发 second-instance ⇒ 把已有窗口叫到前面来
const singleInstanceLock_ = app.requestSingleInstanceLock();
if (!singleInstanceLock_) {
    console.log('[main] R182 SINGLE_INSTANCE 已有实例在运行, 本实例退出 (code 0)');
    app.exit(0);
} else {
    app.on('second-instance', (_event, _argv, _workingDirectory) => {
        console.log('[main] R182 SECOND_INSTANCE 已有实例在运行, 聚焦已有窗口');
        if (mainWindow && !mainWindow.isDestroyed()) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            mainWindow.show();
            mainWindow.focus();
        }
    });
}

if (!manifestPath) {
    // R182: 桌面 .app 由 LaunchServices 双击启动时**没有命令行参数** ⇒ 用项目内的默认 manifest。
    //   仍然优先用 --manifest 传入的路径 (验收脚本 / 命令行启动都走这一条, 行为不变)。
    const defaultManifest = path.join(__dirname, '..', 'assets', 'character_R141_manifest.json');
    if (fs.existsSync(defaultManifest)) {
        manifestPath = defaultManifest;
        console.log(`[main] R182 MANIFEST_DEFAULT ${manifestPath}`);
    }
}
if (!manifestPath) {
    console.error('[main] FATAL: --manifest required');
    app.exit(2);
}
if (!fs.existsSync(manifestPath)) {
    console.error(`[main] FATAL: manifest not found: ${manifestPath}`);
    app.exit(3);
}

// R100 尺寸档位: 基于 26 帧 alpha 边界分析 (113x190 联合可见)
//   选 200x240: 容纳 jump 顶部 (y=30 in 256 frame) + 必要 padding, 减小 27% 横向 + 6% 纵向
const STANDARD_SIZE = parseInt(process.env.STANDARD_SIZE || '256', 10);
const COMPACT_SIZE = parseInt(process.env.COMPACT_SIZE || '200', 10);
const COMPACT_HEIGHT = parseInt(process.env.COMPACT_HEIGHT || '240', 10);

let mainWindow = null;
let currentMode = initialMode === 'compact' ? 'compact' : 'standard';

// ====== R177: 本地状态 (设置 + 心情) ======
//   · 只落在本机 userData 目录, 不联网、不上传
//   · 设置 = 用户偏好; 心情状态 = "基础心情", 不是长期记忆
let settingsStore_ = null;
let settings_ = null;
let moodEngine_ = null;
let settingsWindow_ = null;
let moodTimer_ = null;
// R177: 启动时从磁盘读到的**原始**心情状态 (未重算) —— 用于"重启后正确恢复"的客观取证
let moodLoadedRaw_ = null;
// R177: 上次已生效的视口尺寸 (窗口 + 画布); 用来判断"要不要重建画布"
let lastViewport_ = null;
// R179: "开机自动启动"最后一次应用的结果 —— 失败时必须能告诉界面, 不能让开关显示"已开"却没生效
let loginItemResult_ = { ok: true, reason: null };

// ====== R141: 自主行为引擎接入 ======
// 行为引擎只负责"决定做什么"; 窗口坐标/边界由 main 侧 adapter 提供.
let behaviorEngine = null;
let behaviorConfig = null;
let lastWindowBounds = null;   // 上次写入的窗口位置 (避免无变化时重复 setBounds)
let moveWindowLogAt_ = 0;      // 移动日志节流
// R144 P1: 小数位移累计器 (低速移动时避免每次取整把位移吃掉)
let moveRemainder_ = { x: 0, y: 0 };

function clampToWorkArea(x, y, w, h) {
    const rect = mainWindow.getBounds();
    const display = screen.getDisplayMatching(rect);
    const wa = display.workArea;
    const margin = (behaviorConfig && behaviorConfig.edge_margin_px) || 4;
    const maxX = wa.x + wa.width - w - margin;
    const maxY = wa.y + wa.height - h - margin;
    const minX = wa.x + margin;
    const minY = wa.y + margin;
    return {
        x: Math.max(minX, Math.min(x, Math.max(minX, maxX))),
        y: Math.max(minY, Math.min(y, Math.max(minY, maxY))),
        wa,
        minX, minX_end: maxX, minY, minY_end: maxY,
    };
}

// R141 §六 4/5: 平滑移动 + 不高频写入无变化位置
// R144 P1 修复:
//   1) 引擎给的是小数位移 (30px/s * 33ms ≈ 0.99px), 原来直接 setBounds(小数)
//      会被系统取整 → 窗口几乎不动 (低速丢步). 现在先累计, 凑够 1px 才移动.
//   2) setBounds 之后用 getBounds 复核**真实**位置, 日志与边界判定都用真实值.
function moveWindowBy(dx, dy) {
    if (!mainWindow) return { blocked: true, reason: 'no window' };
    if (behaviorEngine && behaviorEngine.getState() === STATES.DRAGGING) {
        return { blocked: true, reason: 'dragging' };
    }
    const rect = mainWindow.getBounds();
    // R144 P1: 小数位移累计 — Electron setBounds 需要整数坐标
    moveRemainder_.x += dx;
    moveRemainder_.y += dy;
    const stepX = Math.trunc(moveRemainder_.x);
    const stepY = Math.trunc(moveRemainder_.y);
    moveRemainder_.x -= stepX;
    moveRemainder_.y -= stepY;
    if (stepX === 0 && stepY === 0) {
        // 不足 1px: 保留到下一次累计, 不产生无效 setBounds
        return { blocked: false, moved: 0, accumulated: true, x: rect.x, y: rect.y };
    }
    const targetX = rect.x + stepX;
    const targetY = rect.y + stepY;
    const clamped = clampToWorkArea(targetX, targetY, rect.width, rect.height);
    // 撞边检测: 目标位置被夹住, 说明到达屏幕边缘
    const wouldBlock = Math.abs(clamped.x - targetX) > 0.5 || Math.abs(clamped.y - targetY) > 0.5;
    // 无变化则不写 (避免高频无意义 setBounds)
    if (lastWindowBounds &&
        lastWindowBounds.x === clamped.x && lastWindowBounds.y === clamped.y) {
        return { blocked: wouldBlock, moved: 0, clamped: true, x: clamped.x, y: clamped.y };
    }
    mainWindow.setBounds({ x: clamped.x, y: clamped.y, width: rect.width, height: rect.height });
    // R144 P1: setBounds 之后立即 getBounds 复核真实位置 (系统可能再取整/夹紧)
    const actual = mainWindow.getBounds();
    const movedX = actual.x - rect.x;
    const movedY = actual.y - rect.y;
    lastWindowBounds = { x: actual.x, y: actual.y, width: actual.width, height: actual.height };
    // R144 P1: 边界判定基于**复核后的真实窗口位置** —— 实际没动 = 撞到屏幕边缘。
    //   (不再用"目标被夹住"判定, 否则起点在区外时第一步行走会被误判成撞边)
    const actualBlocked = (movedX === 0 && movedY === 0);
    // R141: 移动日志 (节流 200ms) — 记录真实位置与真实位移
    const now = Date.now();
    if (!moveWindowLogAt_ || (now - moveWindowLogAt_) > 200) {
        moveWindowLogAt_ = now;
        console.log(`[main] R144 MOVE x=${actual.x} y=${actual.y} target=(${clamped.x},${clamped.y}) actual=(${actual.x},${actual.y}) moved=(${movedX},${movedY}) step=(${stepX},${stepY}) dx=${dx.toFixed(3)} blocked=${actualBlocked} state=${behaviorEngine ? behaviorEngine.getState() : 'n/a'}`);
    }
    return { blocked: actualBlocked, moved: movedX, requested: stepX, x: actual.x, y: actual.y };
}

// ====== R177: 本地状态初始化 / 菜单 / 设置面板 ======

/**
 * R177: 读取本地设置与心情状态。
 * 启动时调用; 读不到/损坏 ⇒ 用默认值 (绝不拖垮启动)。
 */
function initLocalState() {
    try {
        const storeDir = app.getPath('userData');
        if (r177FaultSettings_) {
            // R179 故障注入: 把存储目录指到一个**普通文件**上 ⇒ 写入必然 ENOTDIR 失败。
            //   用来客观验证"保存失败时不会谎报已保存"。
            try {
                fs.mkdirSync(storeDir, { recursive: true });
                const faultPath = path.join(storeDir, 'r177_fault_dir');
                fs.writeFileSync(faultPath, 'R179 fault injection: this is a file, not a directory');
                settingsStore_ = new SettingsStore({ dir: faultPath });
                console.log(`[main] R179 FAULT_INJECTION settings-dir=${faultPath} (写入将失败)`);
            } catch (e) {
                console.error('[main] R179 FAULT_INJECTION_FAILED', e && e.message);
                settingsStore_ = new SettingsStore({ dir: storeDir });
            }
        } else {
            settingsStore_ = new SettingsStore({ dir: storeDir });
        }
        const loaded = settingsStore_.loadAll();
        settings_ = loaded.settings;
        moodLoadedRaw_ = loaded.mood;
        moodEngine_ = new MoodEngine({ state: loaded.mood });
        moodEngine_.noteAwake();
        console.log(`[main] R177 LOCAL_STATE dir=${settingsStore_.dir} mood=${moodEngine_.getMood()} settings=${JSON.stringify(settings_)}`);
    } catch (e) {
        console.error('[main] R177 LOCAL_STATE_INIT_FAILED', e && e.message);
        settings_ = Object.assign({}, DEFAULT_SETTINGS);
        moodEngine_ = new MoodEngine({});
    }
}

/** 当前心情的快照 (给渲染器/设置面板用)。 */
function moodPayload() {
    if (!moodEngine_) return { mood: 'calm', label: '平静', energy: 1, click_weights: {}, suppress_click: false };
    const mood = moodEngine_.getMood();
    return {
        mood,
        label: moodEngine_.getLabel(),
        energy: moodEngine_.getEnergy(),
        // R177: 点击动作池的权重乘子 (渲染器用它挑动作) + 是否禁用点击反馈
        click_weights: Object.assign({}, moodEngine_.config.click_weights[mood] || {}),
        suppress_click: moodEngine_.shouldSuppressClick(mood),
    };
}

/** 心情适配器 (交给行为引擎; null ⇒ 系数全为 1)。 */
function moodAdapter() {
    if (!moodEngine_) return null;
    return {
        getMood: () => moodEngine_.getMood(),
        activityWeight: (kind, mood) => moodEngine_.activityWeight(kind, mood),
        idleIntervalScale: (mood) => moodEngine_.idleIntervalScale(mood),
        clickWeight: (action, mood) => moodEngine_.clickWeight(action, mood),
        shouldSuppressClick: (mood) => moodEngine_.shouldSuppressClick(mood),
    };
}

/**
 * R177: 心情变化时广播给渲染器 (渲染器用它给点击反馈加权) 并落盘。
 */
function refreshMood(reason) {
    if (!moodEngine_) return;
    const snap = moodEngine_.update();
    if (snap.changed) {
        console.log(`[main] R177 MOOD ${snap.prev} -> ${snap.mood} (${reason || 'tick'}) scores=${JSON.stringify(snap.scores)}`);
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('mood-changed', moodPayload());
        }
        if (settingsWindow_ && !settingsWindow_.isDestroyed() && settingsWindow_.webContents) {
            settingsWindow_.webContents.send('mood-changed', moodPayload());
        }
    }
    try { if (settingsStore_) settingsStore_.saveMoodState(moodEngine_.toJSON()); } catch (e) { /* 忽略 */ }
    return snap;
}

/** 每 30 秒重判一次心情 (规则驱动, 不烧 CPU)。 */
function startMoodTicker() {
    if (moodTimer_) clearInterval(moodTimer_);
    moodTimer_ = setInterval(() => {
        if (!moodEngine_) return;
        refreshMood('tick');
    }, 30000);
}

/** 开机自动启动是否可用 (macOS/Windows 有登录项 API; Linux 没有)。 */
function canLaunchAtLogin() {
    return process.platform === 'darwin' || process.platform === 'win32';
}

/**
 * 应用"开机自动启动"。失败只记录, 不影响其它功能。
 *
 * R179: 返回**真实结果** —— macOS 上从源码直接跑 (不是打包后的 .app) 时,
 *   setLoginItemSettings 会报 "Operation not permitted"。这时绝不能让界面显示
 *   "开机自动启动: 已开启" —— 那是在骗用户。
 *
 * @returns {{ok:boolean, reason:?string}}
 */
function applyLaunchAtLogin() {
    if (!settings_ || !canLaunchAtLogin()) {
        loginItemResult_ = { ok: false, reason: '当前系统不支持开机自启 (仅 macOS / Windows 支持)' };
        return loginItemResult_;
    }
    const want = !!settings_.launch_at_login;
    try {
        app.setLoginItemSettings({ openAtLogin: want, openAsHidden: true });
        loginItemResult_ = { ok: true, reason: null };
        console.log(`[main] R177 LOGIN_ITEM set=${want} applied=true`);
        return loginItemResult_;
    } catch (e) {
        loginItemResult_ = {
            ok: false,
            reason: `系统拒绝设置登录项 (${(e && e.message) || 'unknown'}) —— 通常是因为当前不是打包后的 .app`,
        };
        console.error(`[main] R177 LOGIN_ITEM_FAILED ${loginItemResult_.reason}`);
        return loginItemResult_;
    }
}

/**
 * R177: 当前模式下的**实际视口尺寸** = 基础尺寸 × 桌宠大小倍率。
 * 窗口与渲染画布必须用同一个尺寸, 否则角色会被拉伸/裁切。
 */
function getViewportSize(mode) {
    const base = getModeSize(mode);
    const s = settings_ ? (Number(settings_.pet_scale) || 1) : 1;
    return {
        w: Math.max(120, Math.round(base.w * s)),
        h: Math.max(120, Math.round(base.h * s)),
        scale: s,
    };
}

/** 桌宠大小: 基础尺寸 × 倍率 (窗口与渲染画布同步)。 */
function applyPetScale(force) {
    if (!mainWindow || mainWindow.isDestroyed() || !settings_) return;
    const { w, h, scale } = getViewportSize(currentMode);
    const b = mainWindow.getBounds();
    const cx = b.x + b.width / 2;
    const cy = b.y + b.height / 2;
    mainWindow.setBounds({ x: Math.round(cx - w / 2), y: Math.round(cy - h / 2), width: w, height: h });
    const after = mainWindow.getBounds();
    // R177: 尺寸没变就不必让渲染器重建画布 (重建 = 销毁再重建 Pixi 应用,
    //   启动时多来一次会看到一瞬间的闪烁)
    const unchanged = !force && lastViewport_ && lastViewport_.w === w && lastViewport_.h === h;
    if (!unchanged) {
        lastViewport_ = { w, h, scale };
        if (mainWindow.webContents) {
            mainWindow.webContents.send('set-viewport', { w, h, scale, mode: currentMode });
        }
    }
    // 日志里带上**真实窗口 bounds** —— 这样验收判据看的是实际尺寸, 而不是日志措辞
    console.log(`[main] R177 PET_SCALE scale=${scale} viewport=${w}x${h} ` +
        `bounds=(${after.x},${after.y},${after.width},${after.height}) ` +
        `${unchanged ? 'unchanged(跳过画布重建)' : 'rebuild'}`);
}

/**
 * R177: 把设置整体应用到运行时。
 *   · 频率档位 → 行为引擎 config (只改数值, 不改状态机逻辑)
 *   · 点击反馈 → 渲染器
 *   · 桌宠大小 → 窗口 + 渲染画布
 *   · 开机自启 → 系统登录项
 */
function applySettingsToRuntime() {
    if (!settings_) return;
    const fx = rateEffects(settings_.activity_rate, settings_.sleep_rate);
    if (behaviorEngine) {
        behaviorEngine.applyConfig({
            activity_rate_interval_scale: fx.idle_interval,
            activity_weight_scale: fx.activity_weight,
            sleep_weight_scale: fx.sleep_weight,   // 注意键名是 sleep_weight (rateEffects 的返回键)
        });
        console.log(`[main] R177 RATE activity=${settings_.activity_rate} sleep=${settings_.sleep_rate} fx=${JSON.stringify(fx)}`);
    }
    // R179: 先应用开机自启, 再把结果一起发出去 (否则界面拿到的是上一次的旧结果)
    applyLaunchAtLogin();
    const payload = {
        settings: settings_,
        click_feedback: !!settings_.click_feedback,
        launch_at_login: !!settings_.launch_at_login,
        login_item: loginItemResult_,
        rate_effects: fx,
        mood: moodPayload(),
    };
    if (mainWindow && !mainWindow.isDestroyed() && mainWindow.webContents) {
        mainWindow.webContents.send('settings-changed', payload);
    }
    // R177: 设置面板也跟着刷新 (它开着的时候要显示最新值)
    if (settingsWindow_ && !settingsWindow_.isDestroyed() && settingsWindow_.webContents) {
        settingsWindow_.webContents.send('settings-changed', payload);
    }
    applyPetScale();
}

/**
 * R177: 设置变更的唯一入口 (设置面板 IPC 与验收专用入口都走这里)。
 *   ① 逐字段夹紧 (非法值回退默认, 绝不写坏数据)
 *   ② 原子落盘到本机 userData
 *   ③ 应用到运行时 (引擎参数 / 渲染器 / 窗口尺寸 / 登录项)
 *
 * @param {object} patch 设置补丁
 * @returns {{ok:boolean, settings:object, saved:boolean, error?:string}}
 */
function applySettingsPatch(patch) {
    // R179: 落盘失败 ⇒ 返回 ok=false, **并且不应用**到运行时, 也不改内存里的设置。
    //   否则会出现"界面显示已保存, 重启后却全丢" —— 看起来成功, 实际没保存。
    const res = commitSettings(settingsStore_, patch || {}, settings_);
    if (!res.ok) {
        console.error(`[main] R177 SETTINGS_SAVE_FAILED error=${res.error} (未应用到运行时, 设置保持原值)`);
        return res;
    }
    settings_ = res.settings;
    applySettingsToRuntime();
    console.log(`[main] R177 SETTINGS saved=true settings=${JSON.stringify(settings_)}`);
    return res;
}

// ====== R177: 验收专用入口 (仅自动化验证用; 正式运行不触发) ======
// 这些入口存在的唯一目的: 让"菜单命令真的走正式行为系统"和
// "重启后设置/心情真的恢复"能被**客观**取证, 而不是靠一句口头声明。
// 它们调用的是与真机完全相同的函数 (sendMenuCommand / applySettingsPatch)。

/** 打印本地状态 (一行 JSON, 供验收脚本解析)。 */
function dumpLocalState(tag) {
    const payload = {
        tag: tag || 'dump',
        dir: settingsStore_ ? settingsStore_.dir : null,
        settings: settings_ || null,
        mood: moodPayload(),
        mood_scores: moodEngine_ ? moodEngine_.getScores() : null,
        mood_restored_raw: moodLoadedRaw_,
        mood_state_now: moodEngine_ ? moodEngine_.toJSON() : null,
        settings_file: settingsStore_ ? settingsStore_.settingsPath : null,
        mood_file: settingsStore_ ? settingsStore_.moodPath : null,
        platform: process.platform,
    };
    console.log(`[main] R177 DUMP ${JSON.stringify(payload)}`);
    return payload;
}

/** 启动阶段的验收钩子 (应用设置 / 打印本地状态 / 打开设置面板)。 */
function runR177StartupHooks() {
    // ① 应用设置 —— 走 applySettingsPatch (与设置面板 IPC 完全同一条路径)
    if (r177ApplySettings_) {
        let patch = null;
        try { patch = JSON.parse(r177ApplySettings_); }
        catch (e) { console.error('[main] R177 APPLY_SETTINGS_BAD_JSON', e && e.message); }
        if (patch && typeof patch === 'object') {
            const r = applySettingsPatch(patch);
            console.log(`[main] R177 APPLY_SETTINGS ok=${r.ok} saved=${r.saved} error=${r.error || 'none'} settings=${JSON.stringify(r.settings)}`);
        }
    }
    // ② 打印本地状态 (重启恢复取证)
    if (r177DumpSettings_) {
        dumpLocalState('startup');
    }
    // ③ 打开设置面板 (验收"面板能真实打开并读到本地设置")
    if (r177OpenPanel_) {
        setTimeout(() => {
            try { openSettingsWindow(); }
            catch (e) { console.error('[main] R177 PANEL_FAILED', e && e.message); }
        }, 800);
    }
}

/**
 * R177: 右键菜单 —— 每一项都走**正式行为系统** (behaviorEngine.command),
 * 不是播演示图片。菜单里没有"调试"项, 不会污染桌宠外观。
 * 模板本身在 src/menu_template.js (纯模块), 可被单元测试逐项断言。
 */
function buildContextMenu() {
    const label = moodEngine_ ? moodEngine_.getLabel() : '平静';
    return Menu.buildFromTemplate(buildMenuTemplate({
        moodLabel: label,
        onCommand: (kind) => sendMenuCommand(kind),
        onOpenSettings: () => openSettingsWindow(),
        onQuit: () => app.quit(),
    }));
}

/**
 * R177: 把菜单命令交给行为引擎。
 * 引擎走的是自主决策**完全相同**的内部路径 ⇒ 状态转移/计时器/道具挂载全部复用。
 */
function sendMenuCommand(kind) {
    if (!behaviorEngine) {
        console.log(`[main] R177 MENU command=${kind} ignored (engine not started)`);
        return { ok: false, error: 'engine not started' };
    }
    const res = behaviorEngine.command(kind);
    console.log(`[main] R177 MENU command=${kind} ok=${res.ok} state=${res.state || behaviorEngine.getState()} error=${res.error || ''}`);
    if (moodEngine_) {
        moodEngine_.noteInteraction();
        refreshMood('menu');
    }
    return res;
}

/** R177: 设置面板窗口 (独立窗口, 不叠在桌宠上)。 */
function openSettingsWindow() {
    if (settingsWindow_ && !settingsWindow_.isDestroyed()) {
        settingsWindow_.focus();
        return settingsWindow_;
    }
    settingsWindow_ = new BrowserWindow({
        width: 340,
        height: 486,
        title: '桌宠设置',
        titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
        resizable: false,
        minimizable: false,
        maximizable: false,
        fullscreenable: false,
        backgroundColor: '#f4f7fc',
        show: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        },
    });
    settingsWindow_.loadFile(path.join(__dirname, 'settings_panel.html'));
    settingsWindow_.once('ready-to-show', () => settingsWindow_.show());
    // R177: 把设置面板的 console 输出转发到主进程日志 (验收证据)
    settingsWindow_.webContents.on('console-message', (...args) => {
        const event = args[0];
        const legacyMessage = args[2];
        const msg = (event && event.message) || legacyMessage || '(no-message)';
        console.log(`[settings:${(event && event.level) || 'log'}] ${msg}`);
    });
    settingsWindow_.on('closed', () => { settingsWindow_ = null; });
    console.log('[main] R177 SETTINGS_WINDOW opened');
    return settingsWindow_;
}

function createBehaviorEngine(config) {
    behaviorConfig = config;
    const engine = new BehaviorEngine({
        config,
        // R177: 心情适配器 (null ⇒ 行为与 R176 完全一致)
        moodAdapter: moodAdapter(),
        onAction: (action, state) => {
            if (!mainWindow) return;
            console.log(`[main] R141 BEHAVIOR action=${action} state=${state}`);
            mainWindow.webContents.send('set-action', action);
        },
        onMove: (dx, state) => moveWindowBy(dx, 0),
        onState: (from, to, reason) => {
            // R170: 带相对时间戳 —— 这样"办公场景持续了多久""两次间隔多久"可以从日志
            //   直接算出来 (之前只有顺序, 算不出时长, 也就无法证明"没有刚出现就消失")。
            console.log(`[main] R141 STATE ${from} -> ${to} (${reason}) t=${Date.now() - R170_T0_}ms`);
            // R177: 自主活动切换 ⇒ 更新心情 (无聊看的是"既没交互也没活动")
            if (moodEngine_ && from !== to) {
                const kind = to === 'WORK' ? 'work'
                    : to === 'EAT_FRUIT' ? 'eat_fruit'
                        : to === 'SIT' ? 'sit'
                            : to === 'DOZE' ? 'doze'
                                : to === 'SLEEP_LOOP' ? 'sleep'
                                    : to === 'SLEEP_ENTER' ? 'sleep'
                                        : to === 'GESTURE' ? 'gesture'
                                            : to === 'WALK_LEFT' || to === 'WALK_RIGHT' ? 'walk' : null;
                if (kind) moodEngine_.noteActivity(kind);
                else if (to === 'WAKE_UP') moodEngine_.noteAwake();
            }
        },
    });
    return engine;
}

function applyMode(mode) {
    // R100 P0-4 修复: 模式切换保持角色屏幕中心稳定
    //   不再用固定 winX/winY, 而是用当前窗口中心算切换后位置
    // R102 P0-1: 用统一 getModeSize (compact=200x240, standard=256x256)
    // R177: 叠加"桌宠大小"倍率 —— 窗口与画布必须同尺寸
    currentMode = mode;
    if (!mainWindow) return;
    const { w, h, scale } = getViewportSize(mode);
    // R100 P0-4: 用当前实际 bounds 算中心, 保持角色视觉位置稳定
    const oldBounds = mainWindow.getBounds();
    const oldCenterX = oldBounds.x + oldBounds.width / 2;
    const oldCenterY = oldBounds.y + oldBounds.height / 2;
    const newX = Math.round(oldCenterX - w / 2);
    const newY = Math.round(oldCenterY - h / 2);
    mainWindow.setBounds({ x: newX, y: newY, width: w, height: h });
    // R177: 模式切换后的视口尺寸 = 新的"已生效视口"
    lastViewport_ = { w, h, scale };
    // 保持可点击
    mainWindow.setIgnoreMouseEvents(false);
    // R100 P0-4: 传 centerX/centerY 给 renderer, 角色锚点对齐
    if (mainWindow.webContents) {
        mainWindow.webContents.send('set-mode', {
            mode,
            size: { w, h },
            centerX: w / 2,
            centerY: h,  // anchor 0.9 → sprite 中心 y = h
            scale,
        });
    }
    console.log(`[main] R100 mode=${mode} bounds=(${newX},${newY},${w},${h}) center=(${oldCenterX},${oldCenterY}) preserved scale=${scale}`);
}

// R102 P0-1: 统一用 size 对象 — compact=200x240, standard=256x256
function getModeSize(mode) {
    if (mode === 'compact') return { w: COMPACT_SIZE, h: COMPACT_HEIGHT };
    return { w: STANDARD_SIZE, h: STANDARD_SIZE };
}

function createWindow() {
    // R177: 初始窗口 = 基础尺寸 × 桌宠大小倍率 (与渲染画布同尺寸)
    const startSize = getViewportSize(currentMode);
    // 渲染器会用同一个尺寸建首帧画布 (manifest IPC 里带 viewport), 这里先记下来
    lastViewport_ = { w: startSize.w, h: startSize.h, scale: startSize.scale };
    mainWindow = new BrowserWindow({
        x: winX, y: winY,
        width: startSize.w, height: startSize.h,
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        hasShadow: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        resizable: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            offscreen: false,
        },
    });
    mainWindow.setOpacity(0.999);
    mainWindow.setIgnoreMouseEvents(false);

    // R144 P1: 初始位置先夹进屏幕工作区。
    //   否则"起点在区外"会让第一步行走被边界判定误当成撞边 (表现为开局莫名掉头)。
    try {
        const wa = screen.getDisplayMatching({
            x: winX, y: winY, width: startSize.w, height: startSize.h,
        }).workArea;
        const margin = 4;
        const maxX = Math.max(wa.x + margin, wa.x + wa.width - startSize.w - margin);
        const maxY = Math.max(wa.y + margin, wa.y + wa.height - startSize.h - margin);
        const initX = Math.max(wa.x + margin, Math.min(winX, maxX));
        const initY = Math.max(wa.y + margin, Math.min(winY, maxY));
        if (initX !== winX || initY !== winY) {
            mainWindow.setBounds({ x: initX, y: initY, width: startSize.w, height: startSize.h });
            console.log(`[main] R144 initial position clamped (${winX},${winY}) -> (${initX},${initY}) workArea=(${wa.x},${wa.y},${wa.width},${wa.height})`);
        }
        lastWindowBounds = { x: initX, y: initY, width: startSize.w, height: startSize.h };
    } catch (e) {
        console.error(`[main] R144 initial position clamp failed: ${e?.message}`);
    }

    mainWindow.on('ready-to-show', () => {
        console.log('[main] window ready-to-show');
    });
    mainWindow.on('show', () => {
        console.log('[main] window show');
    });
    mainWindow.on('blur', () => {
        console.log('[main] window blur');
    });
    mainWindow.on('focus', () => {
        console.log('[main] window focus');
    });
    mainWindow.on('closed', () => {
        console.log('[main] window closed');
    });

    mainWindow.loadFile(path.join(__dirname, 'renderer.html'));

    mainWindow.webContents.on('console-message', (...args) => {
        const event = args[0];
        const legacyMessage = args[2];
        const msg = (event && event.message) || legacyMessage || '(no-message)';
        const level = (event && event.level) || args[1] || 'log';
        console.log(`[renderer:${level}] ${msg}`);
    });
    mainWindow.webContents.on('did-finish-load', () => {
        const data = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
        const manifestBase = path.dirname(manifestPath);
        mainWindow.webContents.send('manifest', {
            manifest: data,
            baseDir: manifestBase,
            initialMode: currentMode,
            compactSize: { w: COMPACT_SIZE, h: COMPACT_HEIGHT },
            standardSize: { w: STANDARD_SIZE, h: STANDARD_SIZE },
            // R177: 桌宠大小倍率 + 生效视口 (renderer 首帧就按这个尺寸建画布, 不闪一下)
            petScale: settings_ ? (Number(settings_.pet_scale) || 1) : 1,
            viewport: getViewportSize(currentMode),
            clickFeedback: settings_ ? !!settings_.click_feedback : true,
            mood: moodPayload(),
        });

        // R144 P0-3: 这里**不再**启动行为引擎。
        //   renderer 仍在异步加载 23 帧, 必须等它上报 assets-ready 且通过
        //   asset_gate 判定后才启动, 否则状态机可能在资源就绪前要求切动作。
        manifestBehaviorConfig_ = data;
        console.log('[main] R144 manifest sent, waiting for renderer assets-ready');

        // R144: 看门狗 — renderer 迟迟不上报资源就绪时明确报错 (不静默等待)
        assetsWatchdog_ = setTimeout(() => {
            if (!assetsReadyHandled_) {
                console.error(`[main] R144 ASSETS_TIMEOUT renderer 20s 内未上报 assets-ready, 自主行为未启动`);
            }
        }, 20000);
    });

    if (quitAfter) {
        setTimeout(() => {
            console.log('[main] quit-after elapsed, terminating');
            app.quit();
        }, quitAfter * 1000);
    }
}

app.whenReady().then(() => {
    // R182: 没拿到单实例锁 ⇒ 绝不创建窗口 (双保险: app.exit(0) 之外的第二道闸)
    if (!singleInstanceLock_) return;
    // R177: 先读本地设置与心情状态 (窗口尺寸要按"桌宠大小"来开, 所以必须早于 createWindow)
    initLocalState();
    runR177StartupHooks();
    createWindow();
    // R177: 30 秒一次心情重判 (纯规则, 不烧 CPU)
    startMoodTicker();
});

app.on('window-all-closed', () => {
    // R141 §六 7/§七: 关闭前清理所有定时器
    if (behaviorEngine) {
        behaviorEngine.stop();
        behaviorEngine = null;
        console.log('[main] R141 behavior engine stopped (window-all-closed)');
    }
    if (assetsWatchdog_) { clearTimeout(assetsWatchdog_); assetsWatchdog_ = null; }
    stopDragPolling();
    app.quit();
});

// R141 §六 7: 退出前清理 (before-quit 是最可靠的清理点)
app.on('before-quit', () => {
    if (behaviorEngine) {
        behaviorEngine.stop();
        behaviorEngine = null;
        console.log('[main] R141 behavior engine stopped (before-quit)');
    }
    if (assetsWatchdog_) { clearTimeout(assetsWatchdog_); assetsWatchdog_ = null; }
    if (moodTimer_) { clearInterval(moodTimer_); moodTimer_ = null; }
    stopDragPolling();
    // R177: 退出前保存心情状态 (重启后能恢复"基础心情")
    try {
        if (moodEngine_ && settingsStore_) {
            settingsStore_.saveMoodState(moodEngine_.toJSON());
            console.log(`[main] R177 MOOD_SAVED mood=${moodEngine_.getMood()}`);
        }
    } catch (e) {
        console.error('[main] R177 MOOD_SAVE_FAILED', e && e.message);
    }
});

ipcMain.on('renderer-ready', (_evt, info) => {
    console.log(`[main] renderer-ready: pixi=${info && info.version}`);
});

ipcMain.on('perf-sample', (_evt, sample) => {
    if (!perfOut) return;
    const dir = path.dirname(perfOut);
    fs.mkdirSync(dir, { recursive: true });
    const exists = fs.existsSync(perfOut);
    const line = [
        sample.timestamp, sample.action, sample.fps.toFixed(2),
        sample.frame_ms_p50.toFixed(2), sample.frame_ms_p95.toFixed(2),
        sample.rss_mb.toFixed(2), sample.cpu_percent.toFixed(2)
    ].join(',') + '\n';
    if (!exists) {
        fs.writeFileSync(perfOut,
            'timestamp,action,fps,frame_ms_p50,frame_ms_p95,rss_mb,cpu_percent\n');
    }
    fs.appendFileSync(perfOut, line);
});

ipcMain.on('asset-report', (_evt, report) => {
    console.log(`[main] asset-report: ${report.action} loaded=${report.loaded} failed=${report.failed}`);
});

// ====== R144 P0-3: 资源就绪握手 ======
// renderer 加载完 6 组 23 帧并确认可播放后上报 assets-ready;
// main 通过 asset_gate 判定后才启动自主行为状态机。
// 缺帧 → 明确报错并拒绝启动 (拒绝虚假 PASS); 重复 ready → 忽略。
let assetsReadyHandled_ = false;
let assetsWatchdog_ = null;
let manifestBehaviorConfig_ = null;
let assetsError_ = null;

function startBehaviorEngine() {
    if (behaviorEngine) return false;   // 幂等: 重复 ready 不得重复启动
    const behavior = (manifestBehaviorConfig_ && manifestBehaviorConfig_.behavior) || {};
    const cfg = Object.assign({}, behavior.config || {});
    if (acceptanceMode) {
        // R141 §九: 验收模式只加速状态触发, 不改状态机逻辑 (只缩短时长参数)
        cfg.idle_min_ms = 1200; cfg.idle_max_ms = 2500;
        cfg.sleep_min_ms = 4000; cfg.sleep_max_ms = 7000;
        cfg.walk_min_distance_px = 40; cfg.walk_max_distance_px = 120;
        console.log('[main] R141 ACCEPTANCE_MODE (加速参数, 状态机逻辑不变)');
    }
    if (sleepProbabilityOverride !== null) {
        // R144: 概率覆盖 (只改配置值, 不改状态机逻辑), 让验收脚本可确定性复现
        cfg.sleep_probability = sleepProbabilityOverride;
        console.log(`[main] R144 sleep-probability override=${sleepProbabilityOverride}`);
    }
    behaviorEngine = createBehaviorEngine(cfg);
    // R147: 预览模式下暂停自主决策, 由预览脚本显式驱动场景 (正式运行不受影响)
    if (previewDir_) behaviorEngine.setAutonomousPaused(true);
    // R170: 验收专用入口 —— 锁定在指定场景, 自主决策暂停。
    //   与"正式自主行为"完全分离: 不会随机走开/睡着, 场景会一直停在原地供验收观看。
    if (demoScene_) behaviorEngine.setAutonomousPaused(true);
    behaviorEngine.start();
    console.log(`[main] R144 behavior engine started state=${behaviorEngine.getState()}`);
    // R177: 引擎起来后把本地设置里的频率档位应用上去 (只改数值, 不改状态机逻辑)
    applySettingsToRuntime();
    return true;
}

ipcMain.on('assets-ready', (_evt, report) => {
    if (assetsReadyHandled_) {
        console.log(`[main] R144 ASSETS_READY_DUPLICATE ignored (loaded=${report && report.loaded})`);
        return;
    }
    assetsReadyHandled_ = true;
    if (assetsWatchdog_) { clearTimeout(assetsWatchdog_); assetsWatchdog_ = null; }
    const verdict = evaluateAssetReadiness(report, REQUIRED_ACTIONS);
    if (!verdict.ok) {
        assetsError_ = report;
        console.error(`[main] R144 ASSETS_ERROR 资源未就绪, 拒绝启动自主行为: ${verdict.errors.join(' | ')}`);
        console.error(`[main] R144 ASSETS_ERROR report=${JSON.stringify(report)}`);
        return;   // 明确报错, 拒绝虚假 PASS
    }
    console.log(`[main] R144 ASSETS_READY loaded=${verdict.loaded}/${verdict.total} actions=${REQUIRED_ACTIONS.join(',')}`);
    startBehaviorEngine();
    // R170: 验收专用入口 —— 直接把角色切到指定场景并**停在那儿**。
    //   渲染器的 set-action 会顺带 applyPropsFor(action) ⇒ 该场景的道具(桌子/键盘/
    //   小凳/果盘)自动挂载, 与正式自主行为走的是同一条渲染路径。
    if (demoScene_) {
        console.log(`[main] R170 DEMO_SCENE action=${demoScene_} (自主决策已暂停, 场景锁定供验收)`);
        setTimeout(() => {
            if (mainWindow) mainWindow.webContents.send('set-action', demoScene_);
        }, 250);
    }
    // R147: 运行时预览采集 (仅 --preview <dir> 时启用; 不影响正式运行)
    if (previewDir_) {
        setTimeout(() => { runPreviewSequence().catch((e) => console.error('[main] R147 PREVIEW_ERROR', e && e.message)); }, 900);
    }
    // R177: 验收专用入口 —— 用**菜单同一条**代码路径 (sendMenuCommand) 触发行为,
    //   以便客观证明"菜单命令确实驱动了正式行为系统"。
    if (r177Command_) {
        setTimeout(() => {
            const res = sendMenuCommand(r177Command_);
            console.log(`[main] R177 ACCEPTANCE_COMMAND kind=${r177Command_} result=${JSON.stringify(res)}`);
            if (r177DumpSettings_) dumpLocalState('after-command');
        }, 500);
    }
});

ipcMain.on('action-switch', (_evt, action) => {
    if (mainWindow) {
        mainWindow.webContents.send('set-action', action);
    }
});

// ====== R147: 运行时预览采集 (仅 --preview <dir>) ======
// 采集的是**真实运行**的 Electron 窗口像素 (webContents.capturePage),
// 并同时记录窗口的真实 x 位移 → 用来生成"左右行走 / 点击反馈 / 自然待机"的可观看 GIF。
// 正式运行不受影响 (previewDir_ 为 null 时整段不执行)。
const previewPending_ = new Map();
let previewSeq_ = 0;

ipcMain.on('preview-result', (_evt, payload) => {
    const id = payload && payload.id;
    if (id && previewPending_.has(id)) {
        const resolve = previewPending_.get(id);
        previewPending_.delete(id);
        resolve(payload);
    }
});

function previewCommand(payload, timeoutMs = 4000) {
    return new Promise((resolve) => {
        if (!mainWindow) { resolve({ ok: false, error: 'no window' }); return; }
        const id = ++previewSeq_;
        const timer = setTimeout(() => {
            if (previewPending_.has(id)) { previewPending_.delete(id); resolve({ ok: false, error: 'timeout' }); }
        }, timeoutMs);
        previewPending_.set(id, (res) => { clearTimeout(timer); resolve(res); });
        mainWindow.webContents.send('preview-command', Object.assign({ id }, payload));
    });
}

const sleep_ = (ms) => new Promise((r) => setTimeout(r, ms));

async function captureFrames(scene, count, intervalMs) {
    const dir = previewDir_;
    const x0 = mainWindow.getBounds().x;
    const meta = [];
    for (let i = 0; i < count; i++) {
        const img = await mainWindow.webContents.capturePage();
        const file = path.join(dir, `${scene}_${String(i).padStart(3, '0')}.png`);
        fs.writeFileSync(file, img.toPNG());
        const b = mainWindow.getBounds();
        meta.push({ file, winX: b.x, dx: b.x - x0, winY: b.y });
        await sleep_(intervalMs);
    }
    return meta;
}

async function runPreviewSequence() {
    if (!previewDir_ || !mainWindow) return;
    fs.mkdirSync(previewDir_, { recursive: true });
    console.log(`[main] R147 PREVIEW start dir=${previewDir_}`);
    const summary = {};
    const quiet = async (ms) => {
        // 让引擎保持安静 (不走不睡), 用于待机场景
        if (behaviorEngine) behaviorEngine.holdBriefly(ms || 60000);
        await previewCommand({ cmd: 'action', action: 'idle' });
        await sleep_(400);
    };

    // --- 场景 1: 向左行走 (窗口真的向左移动 + walk_left 动作 + 向左倾斜) ---
    await previewCommand({ cmd: 'action', action: 'idle' });
    await sleep_(300);
    if (behaviorEngine) behaviorEngine.startWalk(-1, 300);
    await sleep_(150);
    summary.walk_left = await captureFrames('walk_left', 32, 65);

    // --- 场景 2: 向右行走 ---
    await previewCommand({ cmd: 'action', action: 'idle' });
    await sleep_(300);
    if (behaviorEngine) behaviorEngine.startWalk(1, 300);
    await sleep_(150);
    summary.walk_right = await captureFrames('walk_right', 32, 65);

    // --- 场景 3: 自然待机 (稳定站姿 + 自然眨眼, 无胸腔膨胀) ---
    await quiet();
    summary.idle = await captureFrames('idle', 90, 70);

    // --- 场景 4: 鼠标单击反馈 (真实 pointer 事件路径) ---
    await quiet();
    const clickRes = await previewCommand({ cmd: 'click' });
    summary.click_result = clickRes;
    console.log(`[main] R147 PREVIEW click result=${JSON.stringify(clickRes)}`);
    summary.click = await captureFrames('click', 26, 45);

    // --- 场景 5: 睡眠点击唤醒 (sleep_loop → wake_up → idle) ---
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sleep_loop' });
    await sleep_(900);
    const wakeRes = await previewCommand({ cmd: 'click' });
    summary.wake_result = wakeRes;
    console.log(`[main] R147 PREVIEW wake result=${JSON.stringify(wakeRes)}`);
    summary.wake = await captureFrames('wake', 34, 60);

    // --- 场景 6 (R148): 撞边转向后的连续动作 ---
    // 把窗口挪到接近左缘 → 向左走 → 必然撞到屏幕左缘 → 引擎自动反向 (edge-turn)
    //   → 全身朝向与步态必须同步切换为 walk_right, 且**连续**不中断。
    // 采集的是真实运行帧, 每帧同时记录窗口真实 x, 便于在 GIF 上直接看出"撞边→反向"。
    await quiet();
    if (mainWindow) {
        const b = mainWindow.getBounds();
        const display = screen.getDisplayMatching(b);
        const margin = (behaviorConfig && behaviorConfig.edge_margin_px) || 4;
        // 离左缘约 100px: 留出自然走向边缘的过程, 撞边后还有余量继续向右
        const targetX = Math.min(display.workArea.x + margin + 100,
            display.workArea.x + display.workArea.width - b.width - margin);
        mainWindow.setBounds({ x: targetX, y: b.y, width: b.width, height: b.height });
        console.log(`[main] R148 PREVIEW edge-turn place x=${targetX} (workArea.x=${display.workArea.x})`);
    }
    await sleep_(250);
    if (behaviorEngine) behaviorEngine.startWalk(-1, 900);
    await sleep_(150);
    summary.edge_turn = await captureFrames('edge_turn', 90, 55);

    // ====== 场景 7 (R153): 动作库巡礼 — 9 个新增动作逐个采集真实运行帧 =====
    // 目的: 让用户能**看到**每个新动作在真实运行时 (200x240 紧凑窗口) 长什么样,
    //       而不是只信一份"动作表"。
    // [动作, 采集帧数, 帧间隔ms, 应用后先等多久再采]
    //   前置等待必须 < 该动作的时长, 否则会错过一次性动作 (例: 眨眼半闭帧只有 ~130ms)
    const LIB_SCENES = [
        ['look_around', 16, 90, 250],
        ['tilt_head', 14, 100, 250],
        ['head_nod', 12, 70, 30],
        ['happy', 10, 90, 60],
        ['blink_soft', 14, 40, 20],
        ['stretch', 12, 110, 250],
        ['sit_rest', 12, 150, 250],
        ['doze', 12, 150, 250],
        ['sleep_breath', 14, 160, 250],
        // R156: 办公待机 (2 帧循环, 每帧 2.8s → 多采一会儿才能看到两帧都出现)
        ['work', 26, 280, 250],
        // R170: 吃水果 (5 帧循环, 帧间隔 0.7~1.15s → 采够一个完整"拿果→吃→满足"周期)
        ['eat_fruit', 30, 160, 300],
    ];
    for (const [action, count, interval, preDelay] of LIB_SCENES) {
        await quiet();
        const res = await previewCommand({ cmd: 'action', action });
        console.log(`[main] R153 PREVIEW lib action=${action} ok=${res && res.ok}`);
        await sleep_(preDelay);
        summary[`lib_${action}`] = await captureFrames(`lib_${action}`, count, interval);
    }

    // ====== 场景 8 (R153): 坐 → 躺 的交叉溶解过渡 =====
    // 采集 sit_rest → sleep_enter 切换瞬间的帧, 验证"坐下瞬间躺下"已变成溶解过渡。
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sit_rest' });
    await sleep_(500);
    await previewCommand({ cmd: 'action', action: 'sleep_enter' });
    summary.lib_transition = await captureFrames('lib_transition', 18, 40);

    // ====== 场景 9 (R153): 坐 → 打盹 (不躺下) =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sit_rest' });
    await sleep_(400);
    await previewCommand({ cmd: 'action', action: 'doze' });
    summary.lib_sit_to_doze = await captureFrames('lib_sit_to_doze', 16, 90);

    // ====== 场景 10 (R158): 点击互动池 — 6 个**真实**动作逐个采集 (每个动作 3 帧全过程) =====
    // 目的: 让用户能**看到**每个点击动作的完整"开始/中间/结束", 而不是只信一份动作表。
    const CLICK_ACTIONS = ['cheer_wave', 'cheer_hands_up', 'cheer_heart', 'cheer_clap', 'cheer_jump', 'cheer_tilt'];
    for (const act of CLICK_ACTIONS) {
        await quiet();
        const res = await previewCommand({ cmd: 'click', action: act });
        console.log(`[main] R156 PREVIEW click-pool action=${act} picked=${res && res.action} ok=${res && res.ok}`);
        summary[`click_${act}`] = await captureFrames(`click_${act}`, 16, 55);
        summary[`click_${act}_result`] = res;
    }

    // ====== 场景 11 (R156): 点击池随机性 — 连点 10 次, 记录每次实际触发的动作 =====
    // 这是"点击时随机触发 + 短时间内不重复"的**真实运行证据** (走的是与用户真机点击完全相同的代码路径)。
    await quiet();
    const randomClicks = [];
    for (let i = 0; i < 10; i++) {
        const r = await previewCommand({ cmd: 'click' });
        randomClicks.push(r && r.action);
        await sleep_(260);
    }
    summary.click_pool_random = randomClicks;
    console.log(`[main] R156 PREVIEW click-pool random sequence = ${randomClicks.join(',')}`);

    // ====== 场景 12 (R156): 睡觉场景 (床 + 月亮夜晚氛围 + 被子) =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sleep_breath' });
    await sleep_(700);
    summary.scene_sleep = await captureFrames('scene_sleep', 18, 160);

    // ====== 场景 13 (R156): 坐下沙发场景 =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sit_rest' });
    await sleep_(500);
    summary.scene_sofa = await captureFrames('scene_sofa', 14, 150);

    // ====== 场景 14 (R156): 办公待机场景 (小桌子 + 笔记本 + 屏幕微光) =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'work' });
    await sleep_(600);
    summary.scene_work = await captureFrames('scene_work', 26, 280);

    // ====== 场景 14b (R170): 吃水果场景 (小凳 + 小边桌 + 果盘) =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'eat_fruit' });
    await sleep_(600);
    summary.scene_eat_fruit = await captureFrames('scene_eat_fruit', 30, 160);

    // ====== 场景 15 (R156): 道具退出验证 — 从睡觉切回站立, 床与月亮必须一起退出 =====
    await quiet();
    await previewCommand({ cmd: 'action', action: 'sleep_breath' });
    await sleep_(600);
    await previewCommand({ cmd: 'action', action: 'idle' });
    summary.scene_prop_exit = await captureFrames('scene_prop_exit', 14, 90);

    const metaFile = path.join(previewDir_, 'preview_meta.json');
    fs.writeFileSync(metaFile, JSON.stringify(summary, null, 2));
    console.log(`[main] R147 PREVIEW done meta=${metaFile}`);
    if (quitAfter !== null) {
        setTimeout(() => { try { app.quit(); } catch (e) {} }, 600);
    }
}

// ====== R141: 行为引擎 IPC ======

// renderer 播完一次性动画 (sleep_enter / wake_up) 后回报, 主进程推进状态机
ipcMain.on('animation-finished', (_evt, action) => {
    if (!behaviorEngine) return;
    const ok = behaviorEngine.onAnimationFinished(action);
    console.log(`[main] R141 animation-finished ${action} handled=${ok} state=${behaviorEngine.getState()}`);
});

// 拖拽与自主行为协调 (R141 §四)
ipcMain.on('behavior-drag-state', (_evt, dragging) => {
    // R144 P1: 拖拽打断后清空小数位移累计, 避免拖拽期间的残留位移被继续使用
    if (dragging) { moveRemainder_.x = 0; moveRemainder_.y = 0; }
    if (!behaviorEngine) return;
    behaviorEngine.setDragging(!!dragging);
    console.log(`[main] R141 behavior drag-state=${!!dragging} state=${behaviorEngine.getState()}`);
});

// ====== R147: 鼠标单击角色 ======
// renderer 判定为 CLICK (短按 + 位移 < 3px) 后发来, 带按下之前的动作名。
// 主进程负责: ①结束"按住"态 ②睡眠时走 wake_up 过渡 ③暂缓自主行为计时器,
// 保证点击反馈不会立刻被 walk 覆盖。
ipcMain.on('character-click', (_evt, payload) => {
    if (!behaviorEngine) return;
    const prevAction = (payload && payload.action) || '';
    const holdMs = (payload && typeof payload.holdMs === 'number') ? payload.holdMs : 700;
    const result = behaviorEngine.onUserClick(prevAction, holdMs);
    console.log(`[main] R147 character-click prev=${prevAction} result=${result} state=${behaviorEngine.getState()} hold=${holdMs}ms`);
});

// ====== R177: 右键菜单 / 设置面板 IPC ======

// renderer 右键角色 → 主进程弹出原生菜单 (菜单项全部走正式行为系统)
ipcMain.on('context-menu', (_evt, payload) => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    try {
        const menu = buildContextMenu();
        menu.popup({ window: mainWindow });
        console.log(`[main] R177 CONTEXT_MENU opened payload=${JSON.stringify(payload || {})}`);
    } catch (e) {
        console.error('[main] R177 CONTEXT_MENU_FAILED', e && e.message);
    }
});

// 设置面板读取当前设置 + 心情 + 能力边界
ipcMain.handle('settings-get', async () => {
    return {
        ok: true,
        settings: settings_ || Object.assign({}, DEFAULT_SETTINGS),
        mood: moodPayload(),
        capabilities: {
            // 开机自启只在有登录项 API 的系统上提供 (macOS / Windows)
            launch_at_login: canLaunchAtLogin(),
            scale_min: SCALE_MIN,
            scale_max: SCALE_MAX,
            rates: RATES.slice(),
        },
        // R179: 开机自启上一次是否真的生效 (失败时界面必须如实显示)
        login_item: loginItemResult_,
    };
});

// 设置面板写回设置 (与验收入口 applySettingsPatch 同一条路径)
ipcMain.handle('settings-set', async (_evt, patch) => {
    const r = applySettingsPatch(patch || {});
    console.log(`[main] R177 SETTINGS_SET ok=${r.ok} saved=${r.saved} error=${r.error || 'none'}`);
    return {
        ok: r.ok,            // R179: ok 严格等于"落盘成功"
        saved: r.saved,
        settings: r.settings,
        error: r.error || null,
        mood: moodPayload(),
        login_item: loginItemResult_,
    };
});

// 行为状态查询 (测试/诊断)
ipcMain.handle('behavior-state', async () => {
    if (!behaviorEngine) return { ok: false, error: 'engine not started' };
    return { ok: true, ...behaviorEngine.snapshot() };
});

// 强制切换行为 (验收脚本用, 不改变状态机内部逻辑)
ipcMain.handle('behavior-force', async (_evt, payload) => {
    if (!behaviorEngine) return { ok: false, error: 'engine not started' };
    const action = payload && payload.action;
    if (!action) return { ok: false, error: 'action required' };
    if (mainWindow) mainWindow.webContents.send('set-action', action);
    console.log(`[main] R141 behavior-force ${action}`);
    return { ok: true, action, state: behaviorEngine.getState() };
});

// V0.0 R39: renderer-driven transparent-area passthrough.
let lastPassthrough = null;
ipcMain.on('set-passthrough', (_evt, ignore) => {
    if (!mainWindow) return;
    if (lastPassthrough === ignore) return;
    lastPassthrough = ignore;
    mainWindow.setIgnoreMouseEvents(!!ignore, { forward: true });
    console.log(`[main] setIgnoreMouseEvents(${!!ignore}, forward=true) (R39 passthrough)`);
});

// R100 P0-2 修复: request-mode 走 ipcMain.handle (invoke 同步模式) 等 renderer ack
//   协议: renderer.invoke('request-mode', {mode}) → main 调 applyMode → 发 set-mode IPC
//   → renderer.applyModeToScene → 渲 renderer-mode-ready → main.resolve(invoke)
//   不允许只改 canvas 不改 BrowserWindow (R98 漏洞)
let pendingModeResolvers = new Map();
ipcMain.handle('request-mode', async (_evt, payload) => {
    const mode = payload && payload.mode;
    if (mode !== 'standard' && mode !== 'compact') {
        return { ok: false, error: 'invalid mode' };
    }
    console.log(`[main] R100 request-mode=${mode} (await renderer-mode-ready)`);
    const requestId = `mode-${Date.now()}-${Math.random()}`;
    return new Promise((resolve) => {
        pendingModeResolvers.set(requestId, { mode, resolve, startTs: Date.now() });
        applyMode(mode);
        // 超时保护: 5s 未收到 renderer ack 视为失败
        setTimeout(() => {
            if (pendingModeResolvers.has(requestId)) {
                const r = pendingModeResolvers.get(requestId);
                pendingModeResolvers.delete(requestId);
                console.warn(`[main] R100 request-mode=${mode} timeout (renderer-mode-ready not received)`);
                r.resolve({ ok: false, error: 'timeout: renderer-mode-ready not received' });
            }
        }, 5000);
    });
});

// R100 P0-2 修复: main 收 renderer-mode-ready 后 resolve invoke
ipcMain.on('renderer-mode-ready', (_evt, ack) => {
    // 找到最早的 pending resolver (只支持同时一个 mode 切换)
    if (pendingModeResolvers.size === 0) {
        console.warn(`[main] R100 unexpected renderer-mode-ready:`, ack);
        return;
    }
    const [requestId, r] = pendingModeResolvers.entries().next().value;
    pendingModeResolvers.delete(requestId);
    // R100 P0-2 协议断言: BrowserWindow 实际尺寸 + Canvas 尺寸 + 中心
    const actualBounds = mainWindow ? mainWindow.getBounds() : null;
    const expectedSize = ack && ack.size;
    const match = actualBounds && expectedSize &&
        actualBounds.width === expectedSize.w &&
        actualBounds.height === expectedSize.h;
    console.log(`[main] R100 renderer-mode-ready mode=${ack?.mode} expected=${JSON.stringify(expectedSize)} actual=${JSON.stringify(actualBounds && {w: actualBounds.width, h: actualBounds.height})} match=${match}`);
    r.resolve({
        ok: ack && ack.ok && match,
        mode: ack?.mode,
        size: expectedSize,
        actualBounds: actualBounds && { x: actualBounds.x, y: actualBounds.y, w: actualBounds.width, h: actualBounds.height },
        centerX: ack?.centerX,
        centerY: ack?.centerY,
        protocolMatch: match,
    });
});

// R104 P0-1: 真正 BrowserWindow 拖拽 — 鼠标按桌宠 → 整个 Electron 窗口跟随移动
//   renderer drag-start: 记录 dragStart 时的窗口 bounds + 鼠标屏幕坐标
//   renderer drag-move: 每次移动发 mouse 屏幕坐标, main 算 delta, setBounds 移动窗口
//   renderer drag-end: 清理 dragStart
//   使用 Electron 原生 BrowserWindow.setBounds (不需要 AX/Screen Recording)
//
// R107 修复: 原 line 286 `screen.getDisplayMatching(bounds)` 引用未定义变量 bounds
// R108 修复: screen.getDisplayMatching 接收 Rectangle (非 BrowserWindow)
// R111 修复: 坐标系混用 (R104 dragStart.mouseScreenX 是屏幕坐标, R108 mouse.x 是 renderer ev.clientX viewport 坐标)
// R113 修复: 快速拖拽不连续 (R111 依赖 renderer pointermove 触发 IPC, 鼠标离开 200x240 窗口后 pointermove 收不到)
//   新方案: main 端 setInterval 持续轮询 mouse 位置 (~60Hz), 不依赖 renderer pointermove
//   renderer 只发 start/end/cancel IPC (轻量), 真正的 setBounds 间隔由 main 决定
let dragStart = null;  // {winX, winY, width, height, mouseStartX, mouseStartY, dragStarted}
let dragPollInterval = null;  // R113: setInterval 句柄, drag 期间每 16ms 轮询 mouse 位置

// R113: 实际计算 dx/dy + setBounds 的核心函数 (interval 调, IPC move 也调, 重复无害 idempotent)
function performDragMove() {
    if (!mainWindow || !dragStart) return;
    try {
        const mouse = screen.getCursorScreenPoint();
        const dx = mouse.x - dragStart.mouseStartX;
        const dy = mouse.y - dragStart.mouseStartY;
        if (!dragStart.dragStarted) {
            if (Math.abs(dx) < 3 && Math.abs(dy) < 3) return;  // 3px 容忍, 仍算点击
            dragStart.dragStarted = true;
            console.log(`[main] R113 DRAG_REAL_START dx=${dx}dy=${dy} (3px 容忍通过)`);
        }
        const newX = Math.round(dragStart.winX + dx);
        const newY = Math.round(dragStart.winY + dy);
        const rect = mainWindow.getBounds();
        const display = screen.getDisplayMatching(rect);
        const wa = display.workArea;
        const clampedX = Math.max(wa.x, Math.min(newX, wa.x + wa.width - dragStart.width));
        const clampedY = Math.max(wa.y, Math.min(newY, wa.y + wa.height - dragStart.height));
        const beforeX = rect.x, beforeY = rect.y;
        mainWindow.setBounds({
            x: clampedX, y: clampedY,
            width: dragStart.width, height: dragStart.height,
        });
        // R113: 间隔节流 log (避免每 16ms 都打, 改为每 100ms 一次)
        const now = Date.now();
        if (!dragStart.lastLogAt || (now - dragStart.lastLogAt) > 100) {
            dragStart.lastLogAt = now;
            const afterRect = mainWindow.getBounds();
            console.log(`[main] R113 DRAG_POLL dx=${dx}dy=${dy} before=(${beforeX},${beforeY}) after=(${afterRect.x},${afterRect.y}) mouseNow=(${mouse.x},${mouse.y})`);
        }
    } catch (e) {
        console.error(`[main] R113 DRAG_MOVE_ERROR: ${e?.message}; clearing drag`);
        stopDragPolling();
        dragStart = null;
    }
}

function startDragPolling() {
    // R113: 启动 setInterval (~60Hz, 16ms 间隔) 持续轮询 mouse 位置
    //   解决快速拖拽跟随不连续: 不依赖 renderer pointermove
    //   鼠标在 200x240 窗口内/外都能拿到 screen.getCursorScreenPoint()
    if (dragPollInterval) clearInterval(dragPollInterval);
    dragPollInterval = setInterval(performDragMove, 16);
    console.log('[main] R113 DRAG_POLL_START intervalId=' + dragPollInterval);
}

function stopDragPolling() {
    // R113: drag-end/cancel/blur 必须清理 interval, 防泄漏
    if (dragPollInterval) {
        clearInterval(dragPollInterval);
        console.log('[main] R113 DRAG_POLL_STOP intervalId=' + dragPollInterval);
        dragPollInterval = null;
    }
}

ipcMain.handle('window-drag-start', (_evt) => {
    if (!mainWindow) return { ok: false, error: 'no main window' };
    let bounds, mouse;
    try {
        bounds = mainWindow.getBounds();
        mouse = screen.getCursorScreenPoint();
    } catch (e) {
        console.error(`[main] R113 DRAG_START_ERROR: ${e?.message}`);
        return { ok: false, error: 'drag-start setup failed' };
    }
    dragStart = {
        winX: bounds.x,
        winY: bounds.y,
        width: bounds.width,
        height: bounds.height,
        mouseStartX: mouse.x,
        mouseStartY: mouse.y,
        dragStarted: false,
        lastLogAt: 0,
    };
    // R113: drag-start 时启动 setInterval 轮询
    startDragPolling();
    // R141 §四: 拖拽期间暂停自主漫游 (与 renderer 的 pointerdown 通知互为双保险)
    if (behaviorEngine) behaviorEngine.setDragging(true);
    console.log(`[main] R113 DRAG_START win=(${bounds.x},${bounds.y},${bounds.width},${bounds.height}) mouseStart=(${mouse.x},${mouse.y})`);
    return { ok: true, start: dragStart };
});

// R113: window-drag-move IPC 保留 (renderer 偶尔触发, 调 performDragMove 重复无害)
ipcMain.on('window-drag-move', (_evt, _unused) => {
    if (!dragStart) return;
    performDragMove();
});

function stopDrag() {
    // R113: drag-end/cancel 清理 setInterval + dragStart
    stopDragPolling();
    if (dragStart) {
        const final = mainWindow ? mainWindow.getBounds() : null;
        console.log(`[main] R113 DRAG_STOP final=(${final?.x},${final?.y}) size=${final?.width}x${final?.height} dragStarted=${dragStart.dragStarted}`);
        dragStart = null;
        // R141: 拖拽结束 -> 同步窗口位置缓存 + 恢复自主行为 (带过渡延迟)
        if (final) lastWindowBounds = { x: final.x, y: final.y, width: final.width, height: final.height };
        if (behaviorEngine && behaviorEngine.isDragging()) {
            behaviorEngine.setDragging(false);
        }
    } else {
        console.log('[main] R113 DRAG_STOP (no active drag)');
    }
}

ipcMain.on('window-drag-end', (_evt) => {
    stopDrag();
});

ipcMain.on('window-drag-cancel', (_evt) => {
    // R113: 显式 cancel IPC (pointercancel / blur 触发)
    if (dragStart) {
        console.log('[main] R113 DRAG_CANCEL (renderer reported)');
    }
    stopDrag();
});


// R113: 监听 window blur 强制结束拖拽 (避免拖到其他应用时卡住) + 清理 setInterval
if (typeof app !== 'undefined' && app.on) {
    app.on('browser-window-blur', () => {
        if (dragStart) {
            console.log('[main] R113 window blur, clearing drag state + interval');
            stopDrag();
        }
    });
}

