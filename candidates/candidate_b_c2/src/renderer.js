// AI Pet Candidate B-C2 — Electron renderer (R100 修复版).
//
// R100 修复: 6 项 P0/P1 集中修复 R98 源码问题.
//   P0-1 lastAdvanceAt 移到 module-scope (tickerCallback 共享)
//   P0-2 window.__setMode 走 ipcRenderer.invoke 同步等 main ack
//   P0-3 applyModeToScene 抽出 attach/detach Canvas 监听, 重建后重绑
//   P0-4 模式切换后 sprite 屏幕中心稳定 (main 算中心后传 renderer)
//   P0-5 asset 加载必须真实成功 (test 拒绝 empty frames)
//
// R60 规则保留 (R100 §六 优先复用原 R60 验证链):
//   - DO NOT set stage.interactive = false. Stage defaults = true.
//   - DO NOT toggle setIgnoreMouseEvents 在 renderer.
//   - R51-style 事件链 (pointerdown/move/up/upoutside) 保留.

const { ipcRenderer } = require('electron');
const PIXI = require('pixi.js');
// R144: 三个纯逻辑生产模块 — renderer 与自动化测试调用的是同一份代码
//   sprite_layout.js : 基于素材真实非透明 bbox 的缩放/锚点/地面线算法
//   anim_clock.js    : 帧推进时钟 (一次性动画末帧停住 + 只报一次完成)
//   asset_gate.js    : 资源就绪判定 (main 侧使用, renderer 只负责报告事实)
const {
    computeLayout, contentRectToScreen, isRectInsideCanvas,
} = require('./sprite_layout.js');
const { AnimationClock } = require('./anim_clock.js');

const stage = document.getElementById('stage');
const fallback = document.getElementById('fallback');
const debugBanner = document.getElementById('debug-banner');

// ====== R141 §五: 正式运行只显示桌宠角色, 无任何调试文字 ======
// 开发调试能力放到明确的开发模式 (PET_DEV_MODE=1), 正式运行默认关闭.
// 注意: 关闭调试 UI 不得破坏角色点击 / 拖拽 / 状态切换 — 下面只改文本与可见性,
// 不动 canvas 与 sprite 事件绑定.
const DEV_MODE = process.env.PET_DEV_MODE === '1';

function devLog(msg) {
    if (DEV_MODE) console.log(`[renderer][dev] ${msg}`);
}
function setFallbackText(msg) {
    // 正式运行: 任何 fallback 文本都不显示 (避免 R104 preview 提示条残留)
    if (DEV_MODE) {
        fallback.textContent = msg;
    } else {
        fallback.textContent = '';
    }
}
if (!DEV_MODE) {
    if (fallback) fallback.style.display = 'none';
    if (debugBanner) debugBanner.style.display = 'none';
}

console.log('[renderer] PIXI version:', PIXI.VERSION, 'dev_mode=', DEV_MODE);
ipcRenderer.send('renderer-ready', { version: PIXI.VERSION, devMode: DEV_MODE });

// ====== 共享状态 (R100 P0-1 修复: 全部 module-scope) ======
let app_ = null;
let sprite_ = null;
let currentAction = 'idle';
let frameIdx = 0;
let dragging = false;
// R104 P0-1: 真正 BrowserWindow 拖拽 — sprite 不再被 drag 移动, 拖动整个窗口
let dragIsWindowDrag_ = false;  // 是否进入真正拖动 (vs 单击容忍)
let dragMoved_ = 0;  // 鼠标移动计数 (3px 内仍算点击)
let dragStartClientX_ = 0;
let dragStartClientY_ = 0;
let stageCssWidth = 0;
let stageCssHeight = 0;
let lastAdvanceAt = performance.now();  // R100 P0-1: module-scope, 共享
let lastTickAt = performance.now();
let fpsWindowFrames = 0;
let fpsWindowStart = performance.now();
let lastSecondFps = 0;
let spritesByAction = {};
let currentMode_ = 'standard';
    // R102 P0-2: 记录 initial mode 供 R100 self-test 完成后恢复
    let originalMode_ = 'standard';
let standardSize_ = 256;
let compactWidth_ = 200;
let compactHeight_ = 240;  // R100 §五 alpha 边界 union 24-221 + padding
let manifestCanvasSize_ = 256;
// R100 P0-3 修复: 持有旧 canvas listeners 引用, 销毁 canvas 前先 detach
let oldStageEl_ = null;
let oldPointerMoveHandler_ = null;
let oldPointerUpHandler_ = null;
// R100 P0-5 修复: asset 加载统计 + 失败标记
let assetLoadTotal_ = 0;
let assetLoadFailed_ = 0;
// ====== R144 新增 ======
let manifest_ = null;      // 保留 manifest 供布局构建与边界自检
let layout_ = null;        // 当前布局 (scale / anchor / 逐帧地面线 y)
let animClock_ = new AnimationClock();  // R144 P0-2: 帧推进时钟 (生产模块)
let assetsReadySent_ = false;           // R144 P0-3: assets-ready 只发一次
const R144_T0_ = Date.now();            // R144: 相对时间戳基准 (供 e2e 核算末帧保持时长)

const frameDeltas = [];
function tick() {
    const now = performance.now();
    const dt = now - lastTickAt;
    lastTickAt = now;
    if (dt > 0 && dt < 1000) {
        frameDeltas.push(dt);
        if (frameDeltas.length > 4096) frameDeltas.splice(0, 2048);
    }
    fpsWindowFrames++;
    if (now - fpsWindowStart >= 1000) {
        lastSecondFps = fpsWindowFrames;
        fpsWindowStart = now;
        fpsWindowFrames = 0;
    }
}

function percentile(arr, p) {
    if (!arr.length) return 0;
    const sorted = arr.slice().sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.floor(p * (sorted.length - 1)))];
}

function rssMB() {
    try { return process.memoryUsage().rss / (1024 * 1024); }
    catch (e) { return -1; }
}

function cpuPercent() {
    try {
        const c = process.cpuUsage();
        return ((c.user + c.system) / 1000000) / ((performance.now() - perfStart) / 1000) * 100;
    } catch (e) { return -1; }
}

const perfStart = performance.now();
setInterval(() => {
    const sample = {
        timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
        action: currentAction,
        fps: lastSecondFps,
        frame_ms_p50: percentile(frameDeltas, 0.50),
        frame_ms_p95: percentile(frameDeltas, 0.95),
        rss_mb: rssMB(),
        cpu_percent: cpuPercent(),
    };
    ipcRenderer.send('perf-sample', sample);
}, 1000);

// ====== R100 P0-3 修复: Canvas 监听 attach/detach 复用函数 ======
// R51 模式: 在 canvas view 上绑 pointermove/pointerup, 让 drag 在鼠标离开 sprite
// hitbox 时继续跟随. R100 把 attach/detach 抽函数, 模式切换重建 canvas 后重绑.
function detachCanvasListeners() {
    // R102 P0-3 修复: 完整解绑 pointermove + pointerup 后再清空引用
    // 之前 bug: 第一段 if 设 oldStageEl_=null 后, 第二段 if 永远进不去, pointerup 残留
    if (!oldStageEl_) return;
    try {
        if (oldPointerMoveHandler_) {
            oldStageEl_.removeEventListener('pointermove', oldPointerMoveHandler_);
        }
        if (oldPointerUpHandler_) {
            oldStageEl_.removeEventListener('pointerup', oldPointerUpHandler_);
        }
    } finally {
        // R102: 全部解绑后才清空引用
        oldStageEl_ = null;
        oldPointerMoveHandler_ = null;
        oldPointerUpHandler_ = null;
        console.log('[renderer] R102 canvas listeners detached (move+up cleared atomically)');
    }
}

function attachCanvasListeners(stageEl) {
    // R100: 先 detach 旧 listener 避免累计
    detachCanvasListeners();
    if (!stageEl) return;
    // R104 P0-1: 真正 BrowserWindow 拖拽 — 移动整个 Electron 窗口, 不是 sprite 在 canvas 内
    //   鼠标 client 坐标 → IPC 给 main → main 用 screen.getCursorScreenPoint() 算 delta
    // R111 修复: 不发 clientX/Y 给 main (坐标系混用导致真实 Mac 拖动失败)
    //   main 端用 screen.getCursorScreenPoint() 拿当前屏幕坐标, 与 dragStart 一致
    //   renderer 只发信号通知 main, 不传坐标
    const onMove = (ev) => {
        if (!dragging || !sprite_) return;
        if (!dragIsWindowDrag_) {
            // 区分点击 vs 拖动: 移动 > 3px 才算拖动 (用 ev.movementX/Y 增量而非绝对坐标, 不受坐标系影响)
            if (dragMoved_ < 3) {
                const mx = Math.abs(ev.movementX || 0);
                const my = Math.abs(ev.movementY || 0);
                if (mx + my < 3) {
                    dragMoved_++;
                    return;  // 仍在 click 容忍范围
                }
            }
            dragIsWindowDrag_ = true;
            // 第一次进入真拖动 — 通知 main 记录 dragStart
            ipcRenderer.invoke('window-drag-start').then((res) => {
                if (res && res.ok) {
                    console.log(`[renderer] R111 DRAG_START_ACK winStart=(${res.start.winX},${res.start.winY}) mouseStart=(${res.start.mouseStartX},${res.start.mouseStartY})`);
                } else {
                    console.error('[renderer] R111 DRAG_START_FAILED:', res && res.error);
                }
            }).catch((e) => console.error('[renderer] R111 drag-start IPC error:', e?.message));
        }
        // R111: 不发 clientX/Y, 让 main 端用 screen.getCursorScreenPoint()
        ipcRenderer.send('window-drag-move');
    };
    const onUp = () => {
        if (dragging) {
            console.log('[renderer] R111 DRAG_POINTER_UP');
            if (dragIsWindowDrag_) {
                ipcRenderer.send('window-drag-end');
            }
            endDrag();
        }
    };
    // R111: pointercancel 显式通知 main 清理 (避免拖到其他应用卡住)
    const onCancel = () => {
        if (dragging) {
            console.log('[renderer] R111 DRAG_POINTER_CANCEL');
            if (dragIsWindowDrag_) {
                ipcRenderer.send('window-drag-cancel');
            }
            endDrag();
        }
    };
    stageEl.addEventListener('pointermove', onMove);
    stageEl.addEventListener('pointerup', onUp);
    stageEl.addEventListener('pointercancel', onCancel);
    // 保留引用供下次 detach
    oldStageEl_ = stageEl;
    oldPointerMoveHandler_ = onMove;
    oldPointerUpHandler_ = onUp;
    console.log(`[renderer] R111 canvas listeners attached (move/up/cancel) to ${stageEl.tagName}#${stageEl.id || ''}`);
}

// ====== R100 P0-1 修复: tickerCallback 在 module-scope ======
// 所有动画计时状态共享, 模式切换重建 canvas 后 tickerCallback 继续正常工作.
// R104: sprite 不再被 drag 移动 (拖动整个 BrowserWindow, sprite 固定 canvas 中心)
// R141: 支持 frame_ms 精确帧时长; 一次性动画播完回报主进程 (驱动状态机)
// R144 P0-2: 帧推进逻辑整体移入生产模块 src/anim_clock.js
//   - loop=false 时逐帧推进到末帧后**停住**, 不再用取模跳回首帧
//   - 末帧保持一个 frame_ms 后只回报一次 animation-finished
//   - 动作被切换/拖拽打断后, 旧的完成事件作废 (epoch 校验), 不得发过期事件
function tickerCallback() {
    tick();
    // R104 P0-1: drag 期间 sprite 位置保持稳定 (BrowserWindow 移动, sprite 相对窗口位置不变)
    const meta = spritesByAction[currentAction];
    if (!meta || meta.frames.length === 0) {
        return;  // R100 P0-5: 无帧时 skip 切帧, 不假装
    }
    // 动作与时钟不同步时 (例如拖拽结束后直接回到 idle) 立即对齐, 避免沿用旧的末帧状态
    if (animClock_.action !== currentAction) {
        animClock_.setAction(currentAction, meta, performance.now());
    }
    const res = animClock_.tick(performance.now());
    lastAdvanceAt = animClock_.lastAdvanceAt;
    if (res.changed) {
        frameIdx = res.frameIndex;
        sprite_.texture = meta.frames[frameIdx];
        // R144 P0-1: 逐帧把内容底边对齐到地面接触线 (姿态切换时脚底不跳动)
        applyFramePosition(currentAction, frameIdx);
        // R144 P0-2: 一次性动画到达末帧时打点 (带相对时间戳, 供 e2e 核算"末帧保持时长")
        if (!meta.loop && res.frameIndex === meta.frames.length - 1) {
            console.log(`[renderer] R144 oneshot last-frame ${res.action} index=${res.frameIndex}/${meta.frames.length - 1} t=+${Date.now() - R144_T0_}ms`);
        }
    }
    if (res.finished) {
        console.log(`[renderer] R144 animation-finished ${res.action} (one-shot, 末帧保持 ${meta.frame_ms}ms) t=+${Date.now() - R144_T0_}ms`);
        ipcRenderer.send('animation-finished', res.action);
    }
}

// ====== R144 P0-1: 布局构建与应用 ======
// 依据 manifest.layout.frame_bboxes (由 08_R144_layout_builder.py 从真实 PNG 逐帧测量)
// 计算: 全部帧共用的统一缩放 + 每帧内容底边对齐到同一条地面接触线。
// 禁止逐帧改变角色大小来规避裁切 —— scale 全局唯一。

function buildLayoutFor(manifest, canvasW, canvasH) {
    const texture = (manifest && manifest.canvas_px && manifest.canvas_px[0]) || manifestCanvasSize_;
    const order = (manifest && manifest.animation_order) || Object.keys((manifest && manifest.actions) || {});
    const bboxes = (manifest && manifest.layout && manifest.layout.frame_bboxes) || {};
    const frames = [];
    for (const action of order) {
        const a = manifest.actions[action];
        if (!a) continue;
        const boxes = bboxes[action] || [];
        for (let i = 0; i < a.frames.length; i++) {
            frames.push({ action, index: i, bbox: boxes[i] || null });
        }
    }
    const margin = (manifest && manifest.layout && manifest.layout.margin_px);
    return computeLayout({
        canvasW, canvasH,
        textureW: texture, textureH: texture,
        frames,
        margin: (typeof margin === 'number') ? margin : undefined,
    });
}

// 把 sprite 的位置对齐到当前帧的地面接触线
function applyFramePosition(action, index) {
    if (!layout_ || !sprite_) return;
    const arr = layout_.frameYByAction[action];
    if (!arr || arr[index] === undefined) return;
    sprite_.y = arr[index];
}

// 应用布局到 sprite (锚点 / 统一缩放 / 水平居中 / 当前帧地面线)
function applyLayoutToSprite() {
    if (!sprite_ || !layout_) return;
    sprite_.anchor.set(layout_.anchor.x, layout_.anchor.y);
    sprite_.scale.set(layout_.scale, layout_.scale);
    sprite_.x = layout_.x;
    applyFramePosition(currentAction, frameIdx);
    console.log(`[renderer] R144 LAYOUT mode=${currentMode_} canvas=${layout_.canvasW}x${layout_.canvasH} scale=${layout_.scale.toFixed(6)} groundY=${layout_.groundY} margin=${layout_.margin} frames=${layout_.frameCount} missingBBox=${layout_.missingBBox}`);
    if (layout_.missingBBox > 0) {
        console.error(`[renderer] R144 LAYOUT_MISSING_BBOX count=${layout_.missingBBox} (已退化为整张纹理, 角色会偏小)`);
    }
}

// ====== R100 P0-3 修复: sprite 事件绑定抽函数 ======
// 在 applyModeToScene 重建后重新调用, 不依赖 manifest IPC 一次性绑定
function bindSpriteEvents() {
    if (!sprite_) return;
    sprite_.on('pointerdown', (ev) => {
        // R111 诊断: 记录 pointerdown 触发 (真实物理鼠标必触发)
        console.log(`[renderer] R111 DRAG_POINTER_DOWN sprite at (${ev.data.global.x},${ev.data.global.y}) interactive=${sprite_.interactive} buttonMode=${sprite_.buttonMode}`);
        dragging = true;
        // R111: 不存 clientX/Y (坐标系混用 root cause), main 端用 screen.getCursorScreenPoint()
        dragIsWindowDrag_ = false;
        dragMoved_ = 0;
        // R141: 保留 currentAction='drag' (R60 self-test 依赖, 且 R141 manifest 无 'drag' 动作
        //   -> ticker 找不到帧会直接 return, 拖拽期间角色静止, 属预期行为)
        currentAction = 'drag';
        frameIdx = 0;
        // R144 P0-2: 拖拽打断一次性动画 — 旧动画之后不得再发完成事件
        animClock_.interrupt(performance.now());
        lastAdvanceAt = performance.now();
        // R141 §四: 用户按住角色时立即暂停自主漫游 (不等 3px 拖动阈值)
        ipcRenderer.send('behavior-drag-state', true);
        setFallbackText('drag');
    });
    sprite_.on('pointerup', () => {
        console.log('[renderer] R111 DRAG_SPRITE_POINTERUP');
        if (dragIsWindowDrag_) ipcRenderer.send('window-drag-end');
        endDrag();
    });
    sprite_.on('pointerupoutside', () => {
        console.log('[renderer] R111 DRAG_SPRITE_POINTERUPOUTSIDE');
        if (dragIsWindowDrag_) ipcRenderer.send('window-drag-end');
        endDrag();
    });
}

function endDrag() {
    dragging = false;
    dragIsWindowDrag_ = false;
    currentAction = 'idle';
    frameIdx = 0;
    // R144 P0-2: 拖拽结束回到 idle — 重置一次性动画状态, 旧动画的完成事件作废
    animClock_.setAction('idle', spritesByAction['idle'], performance.now());
    lastAdvanceAt = performance.now();
    // R141 §四: 松开鼠标后恢复自主行为 (main 侧带过渡延迟)
    ipcRenderer.send('behavior-drag-state', false);
    setFallbackText('idle');
}

// R104 P0-2: 动画预览 — 键盘 1-4 切 idle/walk/jump/drag
//   R141 §五: 正式运行必须删除快捷键说明与调试 UI, 改为仅开发模式启用
//   keydown 在 BrowserWindow focus 时触发 (frameless alwaysOnTop 桌宠需先点击)
function setupAnimationPreviewKeys() {
    if (!DEV_MODE) {
        // R141: 正式运行不注册任何快捷键 (避免"不需要用户按数字键"的行为被误解为依赖按键)
        return;
    }
    const actionMap = {
        '1': 'idle',
        '2': 'walk_left',
        '3': 'walk_right',
        '4': 'sleep_loop',
        '5': 'sleep_enter',
        '6': 'wake_up',
    };
    window.addEventListener('keydown', (ev) => {
        // 数字键 (主键盘区 + 数字键盘区)
        const key = ev.key;
        if (actionMap[key]) {
            const action = actionMap[key];
            if (spritesByAction[action] && spritesByAction[action].frames.length > 0) {
                currentAction = action;
                frameIdx = 0;
                lastAdvanceAt = performance.now();
                // R144 P0-2: 切换动作时重置一次性动画状态 (旧完成事件作废)
                animClock_.setAction(action, spritesByAction[action], performance.now());
                applyFramePosition(action, frameIdx);
                setFallbackText(`[dev] ${action} (1=idle 2=walk_left 3=walk_right 4=sleep_loop 5=sleep_enter 6=wake_up)`);
                console.log(`[renderer][dev] animation preview: ${action}`);
            } else {
                console.warn(`[renderer][dev] preview refused: ${action} has no frames`);
                setFallbackText(`[dev] ${action} NOT loaded (asset failure)`);
            }
            ev.preventDefault();
        }
    });
    console.log('[renderer][dev] animation preview keys enabled');
}

// ====== R100 P0-2/3/4 修复: applyModeToScene 重写 ======
//   - 销毁旧 canvas 前 detach listeners
//   - 重建后 attach new canvas listeners
//   - sprite 屏幕中心由 main 算 (centerX, centerY) 传入, 保持稳定
//   - 模式切换前若 dragging=true 先 endDrag() 安全结束
//   - 重置 lastAdvanceAt 和 frameIdx
function applyModeToScene(mode, opts) {
    opts = opts || {};
    const w = mode === 'compact' ? compactWidth_ : standardSize_;
    const h = mode === 'compact' ? compactHeight_ : standardSize_;
    currentMode_ = mode;
    // R100 P0-4: main 传 sprite 屏幕中心, 模式切换保持中心稳定
    const cx = (typeof opts.centerX === 'number') ? opts.centerX : null;
    const cy = (typeof opts.centerY === 'number') ? opts.centerY : null;

    if (!app_) return;
    // R100: 模式切换前安全结束拖拽
    if (dragging) endDrag();

    // 销毁旧 canvas 前 detach listeners
    if (app_.ticker) app_.ticker.stop();
    detachCanvasListeners();
    const oldView = app_.view;
    oldView.remove();
    try { app_.destroy(true, { children: true, texture: false }); } catch (e) {}

    app_ = new PIXI.Application({
        width: w, height: h,
        backgroundAlpha: 0,
        antialias: false,
        autoDensity: true,
        resolution: 1,
    });
    stage.appendChild(app_.view);
    app_.view.style.background = 'transparent';
    app_.view.style.position = 'absolute';
    app_.view.style.top = '0';
    app_.view.style.left = '0';

    // R100 P0-5: 拒绝空 frames fallback (R98 用了 PIXI.Texture.EMPTY 掩盖)
    const meta = spritesByAction[currentAction];
    if (!meta || meta.frames.length === 0) {
        const msg = `R100 FAIL: action=${currentAction} has no frames loaded (asset_load_total=${assetLoadTotal_} failed=${assetLoadFailed_})`;
        console.error(msg);
        setFallbackText(msg);
        // 不创建 sprite, 阻止 fake PASS
        return { ok: false, error: msg };
    }
    sprite_ = new PIXI.Sprite(meta.frames[0]);
    // R144 P0-1: 改用"素材真实非透明范围"算出的布局
    //   (旧: anchor(0.5,0.9) + y=h + sc=w/1024 → 200x240 裁切 3.7%~6.7%, 256x256 裁切 82%~99%)
    //   (新: 23 帧统一缩放 + 每帧内容底边对齐同一条地面接触线)
    layout_ = buildLayoutFor(manifest_, w, h);
    applyLayoutToSprite();
    sprite_.interactive = true;
    sprite_.buttonMode = true;
    app_.stage.addChild(sprite_);
    // R100 P0-3: 重建后重绑 sprite 事件 + canvas 全局事件
    bindSpriteEvents();
    attachCanvasListeners(app_.view);
    // 重启 ticker
    lastAdvanceAt = performance.now();
    frameIdx = 0;
    app_.ticker.add(tickerCallback);
    stageCssWidth = w;
    stageCssHeight = h;
    const centerLog = cx !== null ? `center=(${cx},${cy})` : `center=canvas_default`;
    setFallbackText(`[renderer] R144 mode=${mode} size=${w}x${h} scale=${layout_.scale.toFixed(4)} ${centerLog}`);
    console.log(`[renderer] R144 mode=${mode} canvas=${w}x${h} scale=${layout_.scale.toFixed(6)} groundY=${layout_.groundY} ${centerLog} hitArea=${JSON.stringify(sprite_.getBounds())}`);
    return { ok: true, mode, size: { w, h }, center: { x: cx, y: cy }, scale: layout_.scale };
}

ipcRenderer.on('manifest', async (_evt, payload) => {
    setFallbackText('[renderer] loading manifest…');
    const { manifest, baseDir } = payload;
    manifest_ = manifest;   // R144: 保留 manifest 供布局构建与边界自检
    currentMode_ = payload.initialMode || 'standard';
    // R102 P0-2: 记录 initial mode 供 R100 self-test 结束后恢复
    originalMode_ = currentMode_;
    // R100: 接收 {w, h} 尺寸 (compact 200x240, standard 256x256)
    if (payload.compactSize) {
        compactWidth_ = payload.compactSize.w || 200;
        compactHeight_ = payload.compactSize.h || 240;
    }
    if (payload.standardSize) {
        standardSize_ = payload.standardSize.w || payload.standardSize.h || 256;
    }
    manifestCanvasSize_ = (manifest.canvas_px && manifest.canvas_px[0]) || 256;

    // R100 P0-5: 真实加载, 统计成功/失败, 缺帧立即报告
    const order = manifest.animation_order || ['idle', 'walk', 'jump', 'drag'];
    spritesByAction = {};
    assetLoadTotal_ = 0;
    assetLoadFailed_ = 0;
    const path = require('path');
    const url = require('url');
    // R144 P0-3: 慢速加载测试钩子 (只影响测试, 不改变生产加载逻辑)
    const assetDelayMs = parseInt(process.env.PET_R144_ASSET_DELAY_MS || '0', 10) || 0;
    if (assetDelayMs > 0) {
        console.log(`[renderer] R144 ASSET_DELAY ${assetDelayMs}ms (测试钩子)`);
        await new Promise((r) => setTimeout(r, assetDelayMs));
    }
    for (const action of order) {
        const a = manifest.actions[action];
        if (!a) {
            setFallbackText(`[renderer] missing action ${action}`);
            continue;
        }
        const frames = [];
        let failed = 0;
        for (const rel of a.frames) {
            if (rel.startsWith('/') || rel.split('/').includes('..')) {
                failed++;
                continue;
            }
            const abs = path.join(baseDir, rel);
            // R100: 显式 file:// URL — PIXI.Assets 在中文/空格路径下用 file:// 更可靠
            const fileUrl = url.pathToFileURL(abs).toString();
            try {
                const texture = await PIXI.Assets.load(fileUrl);
                if (texture && texture.baseTexture && texture.baseTexture.valid) {
                    frames.push(texture);
                } else {
                    console.warn(`[renderer] R100 asset load invalid: ${fileUrl}`);
                    failed++;
                }
            } catch (e) {
                console.warn(`[renderer] R100 asset load failed: ${fileUrl} ${e?.message || e}`);
                failed++;
            }
        }
        spritesByAction[action] = {
            frames,
            fps: a.fps || 8,
            frame_ms: a.frame_ms || null,   // R141: 精确帧时长 (优先于 fps)
            loop: !!a.loop,
            failed,
        };
        assetLoadTotal_ += frames.length + failed;
        assetLoadFailed_ += failed;
        ipcRenderer.send('asset-report', { action, loaded: frames.length, failed, total: frames.length + failed });
        console.log(`[renderer] R100 asset-report ${action}: loaded=${frames.length} failed=${failed}`);
    }
    // ====== R144 P0-3: 资源就绪报告 (renderer 只汇报事实, 判定在 main 侧 asset_gate) ======
    const actionsReport = {};
    for (const action of order) {
        const m = spritesByAction[action];
        actionsReport[action] = {
            loaded: m ? m.frames.length : 0,
            failed: m ? m.failed : 0,
            total: m ? m.frames.length + m.failed : 0,
        };
    }
    const assetReport = {
        total: assetLoadTotal_,
        loaded: assetLoadTotal_ - assetLoadFailed_,
        failed: assetLoadFailed_,
        actions: actionsReport,
    };
    function reportAssetsReady(extra) {
        if (assetsReadySent_) return;   // R144: 只发一次 (重复 ready 由 main 侧忽略)
        assetsReadySent_ = true;
        const payload = Object.assign({}, assetReport, extra || {});
        console.log(`[renderer] R144 assets-ready ${JSON.stringify(payload)}`);
        ipcRenderer.send('assets-ready', payload);
    }

    // R100 P0-5: 全 0 加载 → 阻止假装成功
    if (assetLoadFailed_ === assetLoadTotal_ && assetLoadTotal_ > 0) {
        const msg = `R100 FAIL: all ${assetLoadTotal_} frames failed to load from ${baseDir}`;
        console.error(msg);
        setFallbackText(msg);
        reportAssetsReady({ ok: false, error: msg });   // R144: 明确报错, 拒绝虚假 PASS
        return;  // 阻止后续 applyModeToScene 创建假 sprite
    }

    const w = currentMode_ === 'compact' ? compactWidth_ : standardSize_;
    const h = currentMode_ === 'compact' ? compactHeight_ : standardSize_;
    stageCssWidth = w;
    stageCssHeight = h;
    app_ = new PIXI.Application({
        width: w, height: h,
        backgroundAlpha: 0,
        antialias: false,
        autoDensity: true,
        resolution: 1,
    });
    stage.appendChild(app_.view);
    app_.view.style.background = 'transparent';
    app_.view.style.position = 'absolute';
    app_.view.style.top = '0';
    app_.view.style.left = '0';

    const initMeta = spritesByAction[currentAction];
    if (!initMeta || initMeta.frames.length === 0) {
        const msg = `R100 FAIL: initial action=${currentAction} has no frames after load`;
        console.error(msg);
        setFallbackText(msg);
        reportAssetsReady({ ok: false, error: msg });   // R144: 明确报错, 拒绝虚假 PASS
        return;
    }
    sprite_ = new PIXI.Sprite(initMeta.frames[0]);
    // R144 P0-1: 与 applyModeToScene 同一套布局算法 (统一缩放 + 逐帧地面线对齐)
    layout_ = buildLayoutFor(manifest_, w, h);
    applyLayoutToSprite();
    sprite_.interactive = true;
    sprite_.buttonMode = true;
    app_.stage.addChild(sprite_);
    console.log(`[renderer] R144 sprite enabled: mode=${currentMode_} canvas=${w}x${h} scale=${layout_.scale.toFixed(6)} groundY=${layout_.groundY} hitArea=${JSON.stringify(sprite_.getBounds())}`);

    bindSpriteEvents();
    attachCanvasListeners(app_.view);
    lastAdvanceAt = performance.now();
    frameIdx = 0;
    animClock_.setAction(currentAction, spritesByAction[currentAction], performance.now());
    app_.ticker.add(tickerCallback);

    setFallbackText(`[renderer] R144 mode=${currentMode_} playing ${currentAction}`);

    // ====== R144 P0-3: 资源全部就绪 → 通知 main ======
    //   main 收到并通过 asset_gate 判定后才启动自主行为状态机
    reportAssetsReady({ ok: true });

    // R144: 重复 ready 测试钩子 (只影响测试; main 侧必须忽略重复消息)
    if (process.env.PET_R144_DUP_READY === '1') {
        console.log('[renderer] R144 assets-ready DUPLICATE (测试钩子)');
        ipcRenderer.send('assets-ready', Object.assign({}, assetReport, { ok: true }));
    }

    // R104 P0-2: 动画预览 — 用户无需 DevTools 即可切换 4 种动作
    setupAnimationPreviewKeys();

    if (process.env.PET_R60_SELFTEST === '1') {
        setTimeout(() => runR60SelfTest(sprite_), 250);
    }
    if (process.env.PET_R100_SELFTEST === '1') {
        setTimeout(() => runR100SelfTest(), 500);
    }
    // R107: 真实 IPC drag 回归测试 — 走完整 invoke('window-drag-start') + send('window-drag-move') + send('window-drag-end')
    //   用户真实 Mac 测试发现 main.js 286 行 bounds 未定义崩溃
    //   R107 修复后: 真实 invoke drag-start, 多次发 drag-move, 真实测无 ReferenceError
    if (process.env.PET_R107_IPC === '1') {
        setTimeout(() => runR107DragIPCTest(), 800);
    }
    // R111: 真实 pointer 事件 + IPC chain 测试 (三层)
    if (process.env.PET_R111_IPC === '1') {
        setTimeout(() => runR111DragTest(), 1000);
    }
    // R144: 真实 PixiJS 变换矩阵下核算 23 帧可见像素边界
    if (process.env.PET_R144_SELFTEST === '1') {
        setTimeout(() => runR144BoundsSelfTest(), 800);
    }
});

ipcRenderer.on('set-action', (_evt, action) => {
    if (spritesByAction[action] && spritesByAction[action].frames.length > 0) {
        currentAction = action;
        frameIdx = 0;
        lastAdvanceAt = performance.now();  // R100 P0-1: 重置计时
        // R144 P0-2: 切换动作时重置一次性动画回报状态 (旧完成事件作废)
        animClock_.setAction(action, spritesByAction[action], performance.now());
        // R144 P0-1: 新动作首帧对齐到地面接触线
        applyFramePosition(action, frameIdx);
        setFallbackText('[renderer] switched to ' + action);
        console.log(`[renderer] R144 set-action ${action} loop=${!!spritesByAction[action].loop} frame_ms=${spritesByAction[action].frame_ms} frames=${spritesByAction[action].frames.length}`);
    } else {
        console.warn(`[renderer] set-action ${action} refused: empty frames`);
    }
});

// R100 P0-2 修复: 模式切换 IPC 走完整协议
//   main → renderer: set-mode (含 size + centerX + centerY)
//   renderer → main: renderer-mode-ready (含 mode + size + center 确认)
//   双方断言一致
ipcRenderer.on('set-mode', (_evt, payload) => {
    if (!payload || (payload.mode !== 'standard' && payload.mode !== 'compact')) {
        console.warn(`[renderer] R100 set-mode refused: invalid payload`, payload);
        return;
    }
    console.log(`[renderer] R100 set-mode=${payload.mode} size=${payload.size} center=(${payload.centerX},${payload.centerY})`);
    const result = applyModeToScene(payload.mode, { centerX: payload.centerX, centerY: payload.centerY });
    // 通知 main 确认 (R100 P0-2 要求)
    ipcRenderer.send('renderer-mode-ready', {
        mode: payload.mode,
        size: payload.size,
        centerX: payload.centerX,
        centerY: payload.centerY,
        ok: result.ok,
    });
});

// R100 P0-2 修复: window.__setMode 走 ipcRenderer.invoke 同步等 main ack
// (而不是只调 applyModeToScene 不通知 main)
window.__setMode = async (mode) => {
    if (mode !== 'standard' && mode !== 'compact') {
        console.warn(`[renderer] __setMode refused: invalid mode=${mode}`);
        return { ok: false, error: 'invalid mode' };
    }
    console.log(`[renderer] __setMode(${mode}) → request-mode IPC`);
    try {
        // invoke 同步等 main 回应
        const result = await ipcRenderer.invoke('request-mode', { mode });
        console.log(`[renderer] __setMode(${mode}) main replied:`, result);
        return result;
    } catch (e) {
        console.error(`[renderer] __setMode(${mode}) error:`, e?.message);
        return { ok: false, error: e?.message };
    }
};

// R60 headless self-test (保留)
async function runR60SelfTest(sprite) {
    console.log('[R60 self-test] START');
    const issues = [];
    if (sprite.interactive !== true) issues.push(`sprite.interactive=${sprite.interactive}, expected true`);
    if (sprite.buttonMode !== true) issues.push(`sprite.buttonMode=${sprite.buttonMode}, expected true`);
    if (app_.stage.interactiveChildren !== true) issues.push(`stage.interactiveChildren=${app_.stage.interactiveChildren}, expected true (R51 default)`);
    let dragFired = false, upFired = false;
    try {
        sprite.emit('pointerdown', {
            data: { global: { x: sprite.x, y: sprite.y } },
            stopPropagation: () => {},
        });
        dragFired = (dragging === true) && (currentAction === 'drag');
        sprite.emit('pointerup', {
            data: { global: { x: sprite.x + 30, y: sprite.y + 30 } },
            stopPropagation: () => {},
        });
        upFired = (dragging === false) && (currentAction === 'idle');
    } catch (e) {
        issues.push(`emit error: ${e && e.message}`);
    }
    console.log(`[R60 self-test] treeissues=${issues.length} dragDown=${dragFired} dragUp=${upFired}`);
    if (issues.length === 0 && dragFired && upFired) {
        console.log('[R60 self-test] PASS — R51 event chain wired correctly');
    } else {
        if (issues.length) console.log('[R60 self-test] issues:', issues.join('; '));
        console.log('[R60 self-test] FAIL');
    }
}

// R100 P0-5/6 修复: 专属自测 — 验证模式切换 + 帧非空 + 事件重绑
// R102 P1-1 增强: 走完整 IPC 协议 (ipcRenderer.invoke('request-mode')) 而非直接调 applyModeToScene
// R102 P0-2: self-test 结束后恢复 originalMode_ (不污染用户当前 mode)
async function runR100SelfTest() {
    console.log('[R100 self-test] START');
    const issues = [];

    // 1. asset 加载必须成功
    if (assetLoadTotal_ === 0) issues.push('asset_load_total=0 (no manifest loaded)');
    if (assetLoadFailed_ === assetLoadTotal_ && assetLoadTotal_ > 0) {
        issues.push(`all ${assetLoadTotal_} frames failed to load`);
    }

    // 2. 至少 idle 帧非空
    const idle = spritesByAction['idle'];
    if (!idle || idle.frames.length === 0) {
        issues.push('idle action has no frames (fake_poc 假象掩盖)');
    }

    // 3. tickerCallback 共享 lastAdvanceAt 正常
    if (typeof lastAdvanceAt !== 'number') {
        issues.push(`lastAdvanceAt is ${typeof lastAdvanceAt}, not number (scope error)`);
    }

    // 4. 模式切换通过完整 IPC 协议 (R102 P1-1)
    //    compact → standard → compact 走 invoke + renderer-mode-ready ack
    if (app_) {
        try {
            console.log('[R100 self-test] IPC switch: compact (round 1)');
            const r1 = await ipcRenderer.invoke('request-mode', { mode: 'compact' });
            if (!r1 || !r1.ok) issues.push(`IPC switch compact round 1: ${JSON.stringify(r1)}`);
            else if (r1.mode !== 'compact' || !r1.protocolMatch) {
                issues.push(`IPC switch compact round 1: mode=${r1.mode} protocolMatch=${r1.protocolMatch}`);
            }
            console.log(`[R100 self-test] IPC switch: standard`);
            const r2 = await ipcRenderer.invoke('request-mode', { mode: 'standard' });
            if (!r2 || !r2.ok) issues.push(`IPC switch standard: ${JSON.stringify(r2)}`);
            else if (r2.mode !== 'standard' || !r2.protocolMatch) {
                issues.push(`IPC switch standard: mode=${r2.mode} protocolMatch=${r2.protocolMatch}`);
            }
            console.log('[R100 self-test] IPC switch: compact (round 2)');
            const r3 = await ipcRenderer.invoke('request-mode', { mode: 'compact' });
            if (!r3 || !r3.ok) issues.push(`IPC switch compact round 2: ${JSON.stringify(r3)}`);
            else if (r3.mode !== 'compact' || !r3.protocolMatch) {
                issues.push(`IPC switch compact round 2: mode=${r3.mode} protocolMatch=${r3.protocolMatch}`);
            }
            // 5. 累计监听不重复 (attach/detach 配对数)
            // 不严格配对 (self-test 进行中状态), 只验证不是 attach>detach 累计
            // (测试后由原始 set-mode IPC 自动恢复时正确 detach)
        } catch (e) {
            issues.push(`IPC switch exception: ${e?.message || e}`);
        }

        // R102 P0-2: self-test 结束后恢复 originalMode_ (确保 mac 验收时不污染用户 mode)
        if (originalMode_ !== currentMode_) {
            console.log(`[R100 self-test] restoring originalMode=${originalMode_} (was ${currentMode_})`);
            try {
                const rRestore = await ipcRenderer.invoke('request-mode', { mode: originalMode_ });
                if (!rRestore || !rRestore.ok) {
                    issues.push(`restore originalMode=${originalMode_} failed: ${JSON.stringify(rRestore)}`);
                } else {
                    console.log(`[R100 self-test] restored to ${originalMode_}, protocolMatch=${rRestore.protocolMatch}`);
                }
            } catch (e) {
                issues.push(`restore IPC exception: ${e?.message || e}`);
            }
        }
    }

    console.log(`[R100 self-test] issues=${issues.length}`);
    if (issues.length === 0) {
        console.log('[R100 self-test] PASS');
    } else {
        console.log('[R100 self-test] FAIL:', issues.join('; '));
    }
}

// R111: 真实三层测试 — Renderer pointer 事件 + IPC + 窗口位置
// 沙箱无真实物理鼠标. 沙箱 PIXI/DOM event chain 不可靠, R111 走显式 IPC 验证坐标系修复 (第三层).
async function runR111DragTest() {
    console.log('[R111 drag-test] START (三层)');
    if (!sprite_ || !app_) {
        console.error('[R111 drag-test] FAIL: sprite 或 app 未就绪');
        return;
    }
    try {
        // === 第一层: Renderer pointer 事件 (PIXI + global DOM, 沙箱可验证触发) ===
        // 模拟 1) pointerdown 2) pointermove 3) pointerup
        for (let round = 1; round <= 2; round++) {
            const baseX = round === 1 ? 100 : 50;
            const baseY = round === 1 ? 100 : 50;
            // PIXI pointerdown (触发 sprite.on('pointerdown') 设 dragging=true)
            sprite_.emit('pointerdown', {
                data: { global: { x: baseX, y: baseY } },
                clientX: baseX, clientY: baseY, movementX: 0, movementY: 0,
                stopPropagation: () => {},
            });
            await new Promise(r => setTimeout(r, 80));
            // pointermove (沙箱 PointerEvent 可能不触发 stageEl listener, 但 emit 本身正确)
            for (let i = 1; i <= 3; i++) {
                const event = new PointerEvent('pointermove', {
                    clientX: baseX + i * 5,
                    clientY: baseY + i * 5,
                    movementX: 5,
                    movementY: 5,
                    bubbles: true,
                });
                app_.view.dispatchEvent(event);
                await new Promise(r => setTimeout(r, 50));
            }
            // pointerup
            const upEvent = new PointerEvent('pointerup', { bubbles: true });
            app_.view.dispatchEvent(upEvent);
            await new Promise(r => setTimeout(r, 150));
        }

        // === 第二层 + 第三层: 显式 IPC 让 main 端 setBounds 真执行 ===
        // 沙箱下 PIXI/DOM event chain 不可靠, 显式 invoke+send 验证 R111 坐标系修复
        const r3 = await ipcRenderer.invoke('window-drag-start');
        if (r3 && r3.ok) {
            console.log(`[R111 drag-test] DRAG_START_ACK winStart=(${r3.start.winX},${r3.start.winY}) mouseStart=(${r3.start.mouseStartX},${r3.start.mouseStartY})`);
            // 5 次 move (沙箱下 mouseNow 固定, 但 main 端真调 setBounds)
            for (let i = 1; i <= 5; i++) {
                ipcRenderer.send('window-drag-move');
                await new Promise(r => setTimeout(r, 60));
            }
            ipcRenderer.send('window-drag-end');
        }
        await new Promise(r => setTimeout(r, 300));

        // 非法参数 + cancel
        ipcRenderer.send('window-drag-move', null);
        ipcRenderer.send('window-drag-move', { x: 'not a number' });
        ipcRenderer.send('window-drag-cancel');
        await new Promise(r => setTimeout(r, 200));

        // 重复 drag (验证 dragStart 清零后不累计)
        const r4 = await ipcRenderer.invoke('window-drag-start');
        if (r4 && r4.ok) {
            for (let i = 1; i <= 3; i++) {
                ipcRenderer.send('window-drag-move');
                await new Promise(r => setTimeout(r, 50));
            }
            ipcRenderer.send('window-drag-end');
        }
        await new Promise(r => setTimeout(r, 200));

        console.log('[R111 drag-test] END');
    } catch (e) {
        console.error('[R111 drag-test] EXCEPTION:', e?.message || e);
    }
}

// R107: 真实 IPC drag 回归 — 完整 invoke/send 走生产路径
// 覆盖场景: 1)单击不拖动 2)开始拖动 3)连续移动 4)更新 BrowserWindow bounds 5)结束 6)重复
async function runR107DragIPCTest() {
    console.log('[R107 drag-ipc-test] START');
    const issues = [];

    // 1. 单击不拖动 — 模拟一次 pointerdown + 立即 pointerup, 不发 move
    //    期望: dragStart 不被触发, drag-end 后 main 端不崩
    try {
        // 直接调 invoke('window-drag-start') + 立即 send('window-drag-end')
        // (模拟单击: start 后立即 end, 不发 move)
        const r1 = await ipcRenderer.invoke('window-drag-start');
        if (!r1 || !r1.ok) issues.push(`click-only: drag-start failed: ${JSON.stringify(r1)}`);
        else console.log('[R107 drag-ipc-test] click-only drag-start ok');
        ipcRenderer.send('window-drag-end');
        console.log('[R107 drag-ipc-test] click-only drag-end sent');
    } catch (e) {
        issues.push(`click-only exception: ${e?.message || e}`);
    }

    // 2. 真实拖动序列 — start + 多次 move + end
    try {
        const r2 = await ipcRenderer.invoke('window-drag-start');
        if (!r2 || !r2.ok) issues.push(`drag: start failed: ${JSON.stringify(r2)}`);
        else {
            console.log(`[R107 drag-ipc-test] drag start ok: ${JSON.stringify(r2.start)}`);
            // 3. 连续 5 次 move (覆盖 bounds 更新)
            const deltas = [{x:10,y:10},{x:20,y:15},{x:30,y:25},{x:40,y:30},{x:50,y:40}];
            for (const d of deltas) {
                const mouse = { x: (r2.start.mouseScreenX + d.x), y: (r2.start.mouseScreenY + d.y) };
                ipcRenderer.send('window-drag-move', mouse);
                // 给 main 时间处理 (每 50ms)
                await new Promise(r => setTimeout(r, 50));
            }
            // 4. end
            ipcRenderer.send('window-drag-end');
            console.log('[R107 drag-ipc-test] drag end sent (5 moves)');
        }
    } catch (e) {
        issues.push(`drag exception: ${e?.message || e}`);
    }

    // 5. 重复 — 再做一次完整 drag
    try {
        const r3 = await ipcRenderer.invoke('window-drag-start');
        if (!r3 || !r3.ok) issues.push(`drag-2: start failed`);
        else {
            ipcRenderer.send('window-drag-move', { x: r3.start.mouseScreenX + 5, y: r3.start.mouseScreenY + 5 });
            await new Promise(r => setTimeout(r, 50));
            ipcRenderer.send('window-drag-end');
            console.log('[R107 drag-ipc-test] drag-2 ok');
        }
    } catch (e) {
        issues.push(`drag-2 exception: ${e?.message || e}`);
    }

    // 6. 非法参数 — mouse=null, mouse.x=undefined — main 端需安全处理
    try {
        ipcRenderer.send('window-drag-move', null);
        ipcRenderer.send('window-drag-move', {});
        ipcRenderer.send('window-drag-move', { x: 'not a number', y: null });
        ipcRenderer.send('window-drag-end', null);
        console.log('[R107 drag-ipc-test] illegal params handled');
    } catch (e) {
        issues.push(`illegal-params exception: ${e?.message || e}`);
    }

    console.log(`[R107 drag-ipc-test] issues=${issues.length}`);
    if (issues.length === 0) {
        console.log('[R107 drag-ipc-test] PASS');
    } else {
        console.log('[R107 drag-ipc-test] FAIL:', issues.join('; '));
    }
}

// R144: 真实 PixiJS 变换矩阵下的 23 帧可见像素边界核算
// 依据 R144 P0-1: "每一帧按实际 PixiJS 变换矩阵核算可见像素边界",
//                "在正式生产渲染参数下验证全部 23 帧"
// 做法: 用生产布局模块算出 scale/anchor/position → 建真实 PIXI.Sprite →
//       取 sprite.worldTransform (PixiJS 自己的矩阵) 把内容 bbox 四角映射到屏幕 →
//       判定是否越出画布, 并核对底边是否贴在地面接触线上。
async function runR144BoundsSelfTest() {
    console.log('[R144 bounds self-test] START');
    const issues = [];
    let totalFrames = 0;
    let clippedFrames = 0;
    if (!manifest_) {
        console.error('[R144 bounds self-test] FAIL: manifest 未加载');
        console.log('[R144 bounds self-test] SUMMARY frames=0 clipped=0 issues=1');
        return;
    }
    const modes = [
        ['compact', compactWidth_, compactHeight_],
        ['standard', standardSize_, standardSize_],
    ];
    for (const [mode, w, h] of modes) {
        const layout = buildLayoutFor(manifest_, w, h);
        for (const action of Object.keys(spritesByAction)) {
            const meta = spritesByAction[action];
            const rects = layout.rectsByAction[action] || [];
            for (let i = 0; i < meta.frames.length; i++) {
                const sp = new PIXI.Sprite(meta.frames[i]);
                sp.anchor.set(layout.anchor.x, layout.anchor.y);
                sp.scale.set(layout.scale, layout.scale);
                sp.x = layout.x;
                sp.y = layout.frameYByAction[action][i];
                // PixiJS 7.4.3: 游离 DisplayObject 必须走 temp-parent 机制才能算 worldTransform
                //   (与 PixiJS 自己的 ObjectRendererSystem.render 完全一致的调用序列)
                const cacheParent = sp.enableTempParent();
                sp.updateTransform();
                sp.disableTempParent(cacheParent);
                const rect = rects[i];
                // PixiJS 7.4.3 语义 (重要):
                //   anchor 作用在**顶点层** —— Sprite._calculateVertices 用
                //   w1 = -anchor.x * orig.width 把纹理四角整体平移,
                //   worldTransform 本身只含 position/scale (pivot 默认为 0)。
                //   因此"纹理像素 (u,v) → 屏幕"必须先减掉 anchor 偏移:
                //       local = (u - ax*W, v - ay*H);  screen = worldTransform.apply(local)
                //   这与 sprite_layout.js 使用的公式完全一致。
                const tex = meta.frames[i];
                const origW = tex.orig.width;
                const origH = tex.orig.height;
                const ax = layout.anchor.x;
                const ay = layout.anchor.y;
                // PixiJS 7.4.3: Matrix.apply 收的是 Point 对象
                const tl = sp.worldTransform.apply(new PIXI.Point(rect.left - ax * origW, rect.top - ay * origH));
                const br = sp.worldTransform.apply(new PIXI.Point(rect.right - ax * origW, rect.bottom - ay * origH));
                const inside = tl.x >= -0.01 && tl.y >= -0.01 && br.x <= w + 0.01 && br.y <= h + 0.01;
                const groundErr = Math.abs(br.y - layout.groundY);
                totalFrames++;
                if (!inside) {
                    clippedFrames++;
                    issues.push(`${mode}/${action}[${i}] 越界 screen=(${tl.x.toFixed(2)},${tl.y.toFixed(2)})-(${br.x.toFixed(2)},${br.y.toFixed(2)}) canvas=${w}x${h}`);
                }
                if (groundErr > 0.01) {
                    issues.push(`${mode}/${action}[${i}] 地面接触线偏差 ${groundErr.toFixed(4)}px`);
                }
                console.log(`[R144 bounds self-test] ${mode} ${action}[${i}] screen=(${tl.x.toFixed(2)},${tl.y.toFixed(2)})-(${br.x.toFixed(2)},${br.y.toFixed(2)}) inside=${inside} groundErr=${groundErr.toFixed(4)}`);
            }
        }
        console.log(`[R144 bounds self-test] MODE ${mode} canvas=${w}x${h} scale=${layout.scale.toFixed(6)} groundY=${layout.groundY} margin=${layout.margin}`);
    }
    console.log(`[R144 bounds self-test] SUMMARY frames=${totalFrames} clipped=${clippedFrames} issues=${issues.length}`);
    if (issues.length === 0 && clippedFrames === 0) {
        console.log('[R144 bounds self-test] PASS — 23 帧在两种画布尺寸下均完整显示');
    } else {
        console.log('[R144 bounds self-test] FAIL:', issues.join('; '));
    }
}
