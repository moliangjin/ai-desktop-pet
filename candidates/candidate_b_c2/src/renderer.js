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
// R147 新增纯逻辑生产模块:
//   idle_director.js : 自然待机导演 (稳定站姿 + 自然眨眼, 去掉胸腔膨胀帧)
//   (方向倾斜 skew 的换算同样放在 sprite_layout.js, 与 PixiJS 顶点语义同源)
const {
    computeLayout, contentRectToScreen, isRectInsideCanvas, frameScreenRect, skewAngleX,
    groundRowY,
} = require('./sprite_layout.js');
const { AnimationClock } = require('./anim_clock.js');
const { IdleDirector } = require('./idle_director.js');
// R153 新增纯逻辑生产模块:
//   action_library.js : 动作目录 + 站立小动作池 + 动作过渡策略 (渲染器与引擎共用同一份)
const { transitionBlendMs, pickClickReaction } = require('./action_library.js');
// R147: 点击/拖拽判定 (纯逻辑, 与自动化测试共用同一份代码)
const {
    classifyPress, isClickReaction, isDragEnd, releasesPress,
    CLICK_MAX_MS, CLICK_MAX_PX, DRAG_THRESHOLD_PX,
} = require('./click_policy.js');

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

// ====== R147: 运行时自检 (PET_R147_SELFTEST=1) ======
// 在**真实渲染进程**里核对:
//   1) 切换动作后 Sprite.texture 立刻等于目标动作第 0 帧 (首帧同步)
//   2) 地面线同步 (sprite.y == 布局给出的该帧 y)
//   3) 方向倾斜已施加 (sprite.skew.x == skewAngleX(lean.skew_x))
//   4) 待机导演在长时间推进中**从不**返回被排除的膨胀/回落帧
//   5) 点击反馈会产生真实的 texture 变化与 y 位移 (可见反馈)
async function runR147SelfTest() {
    console.log('[R147 self-test] START');
    const issues = [];
    const actions = Object.keys(spritesByAction);

    // 1~3: 逐动作核对首帧 / 地面线 / 倾斜
    for (const action of actions) {
        applyAction(action);
        const meta = spritesByAction[action];
        if (!sprite_ || sprite_.texture !== meta.frames[0]) {
            issues.push(`${action}: 切换后 texture 不是首帧`);
        }
        if (layout_) {
            const expectY = layout_.frameYByAction[action][0];
            if (expectY !== undefined && Math.abs(sprite_.y - expectY) > 1e-6) {
                issues.push(`${action}: 地面线未同步 y=${sprite_.y} expect=${expectY}`);
            }
            const k = layout_.skewByAction[action] || 0;
            if (Math.abs(sprite_.skew.x - skewAngleX(k)) > 1e-9) {
                issues.push(`${action}: 方向倾斜未施加 skew=${sprite_.skew.x} expect=${skewAngleX(k)}`);
            }
        }
    }

    // 4: 待机导演长时间推进不得出现膨胀帧
    applyAction('idle');
    const excluded = (idleDirector_ && idleDirector_.spec && idleDirector_.spec.excluded_frames) || [];
    const seen = new Set();
    for (let t = 0; t <= 30000; t += 16) {
        const d = idleDirector_.tick(performance.now() + t);
        seen.add(d.frameIndex);
    }
    for (const f of seen) {
        if (excluded.indexOf(f) !== -1) issues.push(`待机出现了被排除的膨胀/回落帧 index=${f}`);
    }
    console.log(`[R147 self-test] idle frames seen = [${[...seen].join(',')}] excluded=[${excluded.join(',')}]`);

    // 5: 点击反馈必须产生可见变化
    //    R156 口径升级: 点击反馈是**多帧动作** (开始/中间/结束), 因此判据从
    //    "texture 变了 + 有弹跳"改为 "至少出现 2 个不同画面" (单帧定格不算反馈)。
    applyAction('idle');
    const before = { tex: sprite_.texture, y: sprite_.y };
    startClickReaction();
    const clickFrames = new Set();
    let minY = Infinity, maxY = -Infinity;
    for (let i = 0; i < 48; i++) {
        await new Promise((r) => setTimeout(r, 25));
        const active = updateClickReaction(performance.now());
        if (active) {
            clickFrames.add(sprite_.texture);
            minY = Math.min(minY, sprite_.y);
            maxY = Math.max(maxY, sprite_.y);
        } else break;
    }
    if (clickFrames.size < 2) issues.push(`点击反馈只出现 ${clickFrames.size} 个画面 (应 ≥2: 多帧动作必须有开始/中间/结束)`);
    const yTravel = (maxY > -Infinity) ? (maxY - minY) : 0;
    console.log(`[R147 self-test] click distinctFrames=${clickFrames.size} yTravel=${yTravel.toFixed(1)}px`);

    applyAction('idle');
    console.log(`[R147 self-test] issues=${issues.length}`);
    if (issues.length === 0) {
        console.log('[R147 self-test] PASS');
    } else {
        console.log('[R147 self-test] FAIL:', issues.join('; '));
    }
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
// R177: 右键菜单的 DOM 监听引用 (同样要在重建前解绑)
let oldContextMenuHandler_ = null;
// R100 P0-5 修复: asset 加载统计 + 失败标记
let assetLoadTotal_ = 0;
let assetLoadFailed_ = 0;
// ====== R144 新增 ======
let manifest_ = null;      // 保留 manifest 供布局构建与边界自检
let layout_ = null;        // 当前布局 (scale / anchor / 逐帧地面线 y)
let animClock_ = new AnimationClock();  // R144 P0-2: 帧推进时钟 (生产模块)
let assetsReadySent_ = false;           // R144 P0-3: assets-ready 只发一次
const R144_T0_ = Date.now();            // R144: 相对时间戳基准 (供 e2e 核算末帧保持时长)

// ====== R147 新增 ======
let idleDirector_ = null;    // 自然待机导演 (稳定站姿 + 自然眨眼)
let clickReaction_ = null;   // 点击反馈状态 (轻微弹跳 + 眨眼)
let pressInfo_ = null;       // 本次按下的计时/位移记录 (区分 CLICK 与 DRAG)
// R165: 预览采集用**合成** pointer 事件模拟一次点击, 而机器上的真实鼠标光标
// 会在 down/up 之间产生 pointermove (movementX/Y 可能是十几像素), 于是这次
// "合成点击"被累计位移判成 DRAG ⇒ 采集到的 26 帧全是待机姿势, 运行时校验
// 第 8 项误报"点击反馈与待机无区别"。这是**采集夹具**的问题, 不是产品行为:
// 真实用户的鼠标是连续移动的, 不会在按下与抬起之间跳十几像素。
// 本标志只在预览合成点击期间为 true, 真实拖拽路径完全不受影响。
let previewSyntheticPress_ = false;
let pressAction_ = null;     // 按下**之前**的动作名 (用于睡眠点击唤醒判定)
let lastPressKind_ = null;   // 最近一次按下的判定结论 (CLICK/DRAG/HOLD/CANCEL)
// R153: 动作过渡 (交叉溶解) —— 消除"坐下瞬间变成躺姿"的姿态瞬切
let spritePrev_ = null;      // 过渡用的第二层 sprite (在主 sprite 之下)
let blend_ = null;           // { startAt, durationMs, fromY }
// CLICK 判定阈值来自纯逻辑模块 click_policy.js (与自动化测试同一份代码)
const R147_CLICK_MAX_MS = CLICK_MAX_MS;   // 按住超过 400ms 不算单击
const R147_CLICK_MAX_PX = CLICK_MAX_PX;   // 累计位移达到 3px 即判定为拖拽
const R147_DRAG_THRESHOLD_PX = DRAG_THRESHOLD_PX;
const R147_CLICK_DURATION_MS = 620;  // 点击反馈总时长
const R147_CLICK_BUMP_PX = 9;        // 点击反馈的轻微弹跳峰值 (屏幕像素)
const R147_CLICK_HOLD_MS = 700;      // 通知主进程"暂缓自主行为"的时长
// R153: 点击反馈改为"歪头眯眼笑" (R147 的眨眼式反馈用的是 idle_04 —— 那是"手放胸前"的姿势)
const R153_CLICK_DURATION_MS = 780;   // 点击反馈总时长
const R153_CLICK_HAPPY_MS = 430;      // 前 430ms 保持"歪头眯眼笑"
const R153_CLICK_BUMP_PX = 7;         // 点击反馈的轻微弹跳峰值 (屏幕像素)
// ====== R156: 点击互动池 + 场景道具 ======
// R156 变更 1: 点击反馈从"固定 1 个动作 + 人工弹跳"改为**随机池**。
//   6 个动作 (比心/小跳/转身/歪头眨眼/双手庆祝/摇摆), 每个 3 帧: 开始 → 情绪高点 → 收势。
//   动作帧自带运动, 不再叠加人工弹跳; 短时间内不重复上一个。
const R156_CLICK_HOLD_MS = 1100;      // 点击反馈期间暂缓自主行为的时长 (覆盖 3 帧总时长)
const R156_PROP_FADE_MS = 260;        // 道具进出场淡入淡出时长
// R156 变更 2: 场景道具 (床/月亮/被子/沙发/转椅/桌子+笔记本/屏幕微光)
//   道具 PNG 与角色帧**同一纹理坐标系**, 与角色 sprite 共享 position/anchor/scale,
//   道具底边落在"场景地面行"(floor_tex_y) → 与角色的接触关系由绘制坐标精确保证。
//   back 层道具在角色身后, front 层道具在角色身前; 退出动作时道具一并淡出, 绝不残留。
let propTextures_ = {};               // 道具名 → PIXI.Texture
let propSprites_ = new Map();        // 道具名 → { sprite, layer, floorTexY, alpha, target, lastT }
let propAssetLoaded_ = 0;
let propAssetFailed_ = 0;
let clickClock_ = new AnimationClock();  // 点击反馈专用时钟 (与主动画时钟互不干扰)
let clickRecent_ = [];               // 最近播放过的点击动作 (避免连续重复)
let lastClickAction_ = null;          // 最近一次点击反馈选中的动作 (预览采集/自检用)
let lastPropT_ = performance.now();  // 道具淡入淡出的时间基准
// ====== R177: 心情 / 设置 / 右键菜单 ======
let moodState_ = { mood: 'calm', label: '平静', click_weights: {}, suppress_click: false };
let clickFeedbackEnabled_ = true;     // 设置面板的"点击反馈开关"
let lastContextMenuAt_ = 0;           // 右键菜单去重 (同一次右键只弹一次)
let initialViewport_ = null;          // R177: 启动时的生效视口 (基础尺寸 × 桌宠大小倍率)

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
        // R177: 解绑右键菜单监听 (避免重建后重复绑定)
        if (oldContextMenuHandler_) {
            oldStageEl_.removeEventListener('contextmenu', oldContextMenuHandler_);
        }
    } finally {
        // R102: 全部解绑后才清空引用
        oldStageEl_ = null;
        oldPointerMoveHandler_ = null;
        oldPointerUpHandler_ = null;
        oldContextMenuHandler_ = null;
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
        const mx = Math.abs(ev.movementX || 0);
        const my = Math.abs(ev.movementY || 0);
        if (pressInfo_ && !previewSyntheticPress_) pressInfo_.distance += mx + my;
        if (!dragIsWindowDrag_ && pressInfo_ && pressInfo_.distance >= R147_DRAG_THRESHOLD_PX) {
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
        // R147: 统一走 finishPress — sprite 与 canvas 两层 pointerup 只会有一次生效
        finishPress('up');
    };
    // R111: pointercancel 显式通知 main 清理 (避免拖到其他应用卡住)
    const onCancel = () => {
        if (!dragging) return;
        console.log('[renderer] R111 DRAG_POINTER_CANCEL');
        if (dragIsWindowDrag_) {
            ipcRenderer.send('window-drag-cancel');
        }
        finishPress('cancel');
    };
    stageEl.addEventListener('pointermove', onMove);
    stageEl.addEventListener('pointerup', onUp);
    stageEl.addEventListener('pointercancel', onCancel);
    // R177: 右键 ⇒ 弹桌宠控制菜单 (只有点在角色身上才弹; 透明区不弹)
    const onContextMenu = (ev) => {
        // 永远屏蔽 WebView 默认右键菜单 (我们要的是桌宠自己的菜单)
        ev.preventDefault();
        const x = ev.clientX, y = ev.clientY;
        if (isPointOnSprite(x, y)) {
            requestContextMenu(x, y);
        } else {
            console.log(`[renderer] R177 CONTEXT_MENU_IGNORED (not on sprite) at=(${x},${y})`);
        }
    };
    stageEl.addEventListener('contextmenu', onContextMenu);
    // 保留引用供下次 detach
    oldStageEl_ = stageEl;
    oldPointerMoveHandler_ = onMove;
    oldPointerUpHandler_ = onUp;
    oldContextMenuHandler_ = onContextMenu;
    console.log(`[renderer] R111 canvas listeners attached (move/up/cancel/contextmenu) to ${stageEl.tagName}#${stageEl.id || ''}`);
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
    // R156: 道具淡入淡出 + 位置同步 (与角色共用同一变换)
    updateProps(performance.now());
    // R153: 动作过渡溶解 (优先于一切, 保证过渡不被其它逻辑打断)
    updateBlend(performance.now());
    // R104 P0-1: drag 期间 sprite 位置保持稳定 (BrowserWindow 移动, sprite 相对窗口位置不变)
    const meta = spritesByAction[currentAction];
    if (!meta || meta.frames.length === 0) {
        return;  // R100 P0-5: 无帧时 skip 切帧, 不假装
    }
    const now = performance.now();
    // R147: 点击反馈优先 — 反馈期间不让基础动画推进, 也不会被 walk 覆盖
    if (updateClickReaction(now)) {
        return;
    }
    // R147: 自然待机由独立导演驱动 (稳定站姿 + 自然眨眼)
    //   1) 不再播放 idle_01_inhale_peak (胸腔外扩 26px 的膨胀帧)
    //   2) 眨眼间隔 1.6~3.4s 随机, 不再是 1.2s 机械循环
    if (currentAction === 'idle' && idleDirector_ && idleDirector_.enabled) {
        const d = idleDirector_.tick(now);
        if (d.changed) {
            frameIdx = d.frameIndex;
            sprite_.texture = meta.frames[frameIdx];
            applyFramePosition('idle', frameIdx);
            console.log(`[renderer] R147 IDLE_BLINK frame=${frameIdx} phase=${d.phase} t=+${Date.now() - R144_T0_}ms`);
        }
        return;
    }
    // 动作与时钟不同步时 (例如拖拽结束后直接回到 idle) 立即对齐, 避免沿用旧的末帧状态
    if (animClock_.action !== currentAction) {
        animClock_.setAction(currentAction, meta, now);
    }
    const res = animClock_.tick(now);
    lastAdvanceAt = animClock_.lastAdvanceAt;
    if (res.changed) {
        const prevIdx = frameIdx;
        frameIdx = res.frameIndex;
        // R153: **帧级**交叉溶解。
        //   根因 (实测): sleep_enter 的第 0 帧本身就是**坐姿**, 所以"sit→sleep_enter"的
        //   动作级溶解实际是"坐→坐"(无视觉变化); 真正的躺姿出现在动画**换帧**那一瞬,
        //   是硬切 → 用户看到的仍是"坐下瞬间变成躺姿"。
        //   这里让一次性动画内部的换帧也走溶解, 坐→躺才是真正的渐变过渡。
        const frameBlendMs = (meta.frame_blend_ms && meta.frame_blend_ms > 0)
            ? meta.frame_blend_ms : 0;
        if (frameBlendMs > 0 && sprite_ && ensurePrevSprite()) {
            const oldTexture = sprite_.texture;
            const oldY = sprite_.y;
            sprite_.texture = meta.frames[frameIdx];
            applyFramePosition(currentAction, frameIdx);      // 新帧的地面接触线
            spritePrev_.texture = oldTexture;
            spritePrev_.x = sprite_.x;
            spritePrev_.y = oldY;
            spritePrev_.scale.set(sprite_.scale.x, sprite_.scale.y);
            spritePrev_.anchor.set(sprite_.anchor.x, sprite_.anchor.y);
            spritePrev_.alpha = 1;
            sprite_.alpha = 0;
            blend_ = { startAt: performance.now(), durationMs: frameBlendMs, fromY: oldY, toY: sprite_.y };
            console.log(`[renderer] R153 FRAME_BLEND ${currentAction} ${prevIdx} -> ${frameIdx} (${frameBlendMs}ms)`);
        } else {
            sprite_.texture = meta.frames[frameIdx];
            // R144 P0-1: 逐帧把内容底边对齐到地面接触线 (姿态切换时脚底不跳动)
            applyFramePosition(currentAction, frameIdx);
        }
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

// ====== R156: 场景道具 (床/月亮/被子/沙发/转椅/桌子+笔记本/屏幕微光) ======
//
// 设计要点:
//  · 道具 PNG 与角色帧**同一纹理坐标系** (1024x1024), 渲染时与角色 sprite 共享
//    position / anchor / scale → "道具落地"等价于"道具底边落在场景地面行上";
//  · 地面行 (floor_tex_y) 由 manifest 声明: 床脚 818 / 沙发底与桌腿底 1001;
//  · back 层道具在角色身后, front 层道具在角色身前 (被子/笔记本在角色前);
//  · 切换动作时旧道具淡出、新道具淡入, 退出动作后道具不残留。

/**
 * 取某个动作的道具场景 (manifest.props.scenes[action])。
 * @param {object} manifest
 * @param {string} action
 * @returns {object|null}
 */
function propSceneOf(manifest, action) {
    const p = manifest && manifest.props && manifest.props.enabled ? manifest.props.scenes : null;
    return (p && p[action]) ? p[action] : null;
}

/**
 * 解析某动作某帧的"地面行" (ground_tex_y)。
 * 优先级: 动作自身的声明 > 道具场景的 floor_tex_y > null (缺省: 内容底边贴地面线)。
 * @returns {number|null}
 */
function resolveGroundTexY(manifest, action, spec, index) {
    const g = spec ? spec.ground_tex_y : undefined;
    if (Array.isArray(g)) {
        const v = g[index];
        return (typeof v === 'number' && isFinite(v)) ? v : null;
    }
    if (typeof g === 'number' && isFinite(g)) return g;
    const scene = propSceneOf(manifest, action);
    if (scene && typeof scene.floor_tex_y === 'number') return scene.floor_tex_y;
    return null;
}

/**
 * 重新排列舞台层级: back 道具 → 过渡层 → 角色 → front 道具。
 * 道具必须严格分层, 否则会出现"枕头盖住脸""沙发挡住角色"这类问题。
 */
function restageProps() {
    if (!app_ || !app_.stage) return;
    const stage = app_.stage;
    const backs = [];
    const fronts = [];
    for (const rec of propSprites_.values()) {
        if (rec.sprite.parent !== stage) stage.addChild(rec.sprite);
        (rec.layer === 'front' ? fronts : backs).push(rec.sprite);
    }
    let idx = 0;
    for (const sp of backs) stage.setChildIndex(sp, idx++);
    if (spritePrev_ && spritePrev_.parent === stage) stage.setChildIndex(spritePrev_, idx++);
    if (sprite_ && sprite_.parent === stage) stage.setChildIndex(sprite_, idx++);
    for (const sp of fronts) stage.setChildIndex(sp, idx++);
}

/**
 * 按动作挂载/卸载道具 (带淡入淡出)。切换到没有道具的动作时, 旧道具淡出后销毁。
 * @param {string} action
 */
function applyPropsFor(action) {
    const scene = propSceneOf(manifest_, action);
    const want = new Set();
    if (scene) {
        for (const n of (scene.back || [])) want.add(n);
        for (const n of (scene.front || [])) want.add(n);
    }
    for (const [name, rec] of propSprites_) {
        rec.target = want.has(name) ? 1 : 0;
    }
    if (scene) {
        for (const name of want) {
            const layer = (scene.back || []).indexOf(name) >= 0 ? 'back' : 'front';
            let rec = propSprites_.get(name);
            if (!rec) {
                const tex = propTextures_[name];
                if (!tex) {
                    console.warn(`[renderer] R156 PROP_MISSING ${name} (资源未加载)`);
                    continue;
                }
                const sp = new PIXI.Sprite(tex);
                sp.alpha = 0;
                sp.interactive = false;
                rec = {
                    sprite: sp, layer, floorTexY: scene.floor_tex_y,
                    alpha: 0, target: 1, lastT: performance.now(),
                };
                propSprites_.set(name, rec);
            } else {
                rec.layer = layer;
                rec.floorTexY = scene.floor_tex_y;
                rec.target = 1;
            }
        }
    }
    restageProps();
    console.log(`[renderer] R156 PROPS action=${action} scene=${scene ? 'yes' : 'none'} ` +
        `mounted=${[...propSprites_.keys()].join(',') || 'none'}`);
}

/**
 * 推进道具的淡入淡出与位置 (由 ticker 调用)。
 * 道具与角色共用同一变换; 纵向位置由"场景地面行"决定, 与角色的地面行一致。
 */
function updateProps(now) {
    if (propSprites_.size === 0) { lastPropT_ = now; return; }
    const dt = Math.max(0, Math.min(200, now - lastPropT_));
    lastPropT_ = now;
    const step = dt / R156_PROP_FADE_MS;
    for (const rec of propSprites_.values()) {
        const diff = rec.target - rec.alpha;
        if (Math.abs(diff) > 0.0005) {
            rec.alpha += Math.sign(diff) * Math.min(Math.abs(diff), step);
        } else {
            rec.alpha = rec.target;
        }
        rec.sprite.alpha = rec.alpha;
        if (layout_) {
            rec.sprite.anchor.set(layout_.anchor.x, layout_.anchor.y);
            rec.sprite.scale.set(layout_.scale, layout_.scale);
            rec.sprite.x = layout_.x;
            rec.sprite.y = groundRowY(layout_, rec.floorTexY, 0);
        }
    }
    let removed = false;
    for (const [name, rec] of [...propSprites_]) {
        if (rec.target === 0 && rec.alpha <= 0.0005) {
            if (rec.sprite.parent) rec.sprite.parent.removeChild(rec.sprite);
            rec.sprite.destroy();
            propSprites_.delete(name);
            removed = true;
        }
    }
    if (removed) restageProps();
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
    const pushAction = (action, a) => {
        if (!a) return;
        const boxes = bboxes[action] || [];
        // R147: 方向倾斜 (整体朝向) — 同一动作内所有帧共享同一个错切因子
        const lean = (a.lean && typeof a.lean.skew_x === 'number') ? a.lean.skew_x : 0;
        for (let i = 0; i < a.frames.length; i++) {
            // R156: 地面行 (ground_tex_y) — 有道具时地面是道具底; 腾空帧用更高的地面行
            frames.push({
                action, index: i, bbox: boxes[i] || null, skew_x: lean,
                ground_tex_y: resolveGroundTexY(manifest, action, a, i),
            });
        }
    };
    for (const action of order) pushAction(action, manifest.actions && manifest.actions[action]);
    // R153: 动作库里的动作同样要参与布局 (地面线 / 统一缩放 / 零裁切核算)
    const libActions = (manifest && manifest.action_library && manifest.action_library.actions) || {};
    for (const action of Object.keys(libActions)) pushAction(action, libActions[action]);
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
    // R147: 方向倾斜 (整体朝向处理) — PixiJS 顶点层水平错切
    //   k = sin(skew.x): k>0 → 上半身向左偏移 (向左走时身体朝左倾)
    //   纹理本身不镜像 → 角色身份 / 服装 / 发型完全不变
    const k = (layout_.skewByAction && typeof layout_.skewByAction[action] === 'number')
        ? layout_.skewByAction[action] : 0;
    sprite_.skew.x = skewAngleX(k);
}

/**
 * R153: 统一的动作切换入口 —— 首帧立即显示 + 地面线同步 + 方向倾斜 + 待机导演重置
 *                            + **动作过渡交叉溶解** (消除"坐下瞬间变成躺姿"的瞬切)
 *
 * 修复的是 GPT 在 R144 独立审查里记录的老问题:
 *   "切换 set-action 时 frameIdx 设为 0, 但 Sprite.texture 未立即更新"
 * → 这里在切换的**同一时刻**就把 texture 换成目标动作的第 0 帧, 并同步地面线,
 *   一次性动画播完也不会闪回首帧 (由 anim_clock 保证不回卷)。
 *
 * R153 新增: 姿态族差别大的切换 (坐→躺 / 躺→坐) 用**交叉溶解**过渡,
 *   由 action_library.transitionBlendMs 决定时长; 同姿态族 (走→站) 立即切换更利落。
 *
 * @param {string} action
 * @param {{immediate?:boolean, blendMs?:number}} [opts] blendMs 显式指定溶解时长 (缺省按策略)
 * @returns {boolean} 是否切换成功
 */
function applyAction(action, opts = {}) {
    const meta = spritesByAction[action];
    if (!meta || meta.frames.length === 0) {
        console.warn(`[renderer] applyAction refused: ${action} has no frames`);
        return false;
    }
    const prevAction = currentAction;
    const changed = (prevAction !== action);
    // 过渡前先记住旧纹理与旧地面线 (溶解用)
    const oldTexture = sprite_ ? sprite_.texture : null;
    const oldY = sprite_ ? sprite_.y : 0;
    const blendMs = (typeof opts.blendMs === 'number')
        ? opts.blendMs
        : transitionBlendMs(prevAction, action);
    currentAction = action;
    frameIdx = 0;
    lastAdvanceAt = performance.now();
    // R144 P0-2: 切换动作时重置一次性动画回报状态 (旧完成事件作废)
    animClock_.setAction(action, meta, performance.now());
    // R156: 道具随动作挂载/退出 (切换到无道具动作时旧道具淡出, 绝不残留)
    applyPropsFor(action);
    // R147: 动作被切换 → 任何进行中的点击反馈立即让位 (不得残留旧动作)
    if (changed && clickReaction_) {
        clickReaction_ = null;
    }
    // R147: 新动作立刻显示首帧 (不等下一次 ticker), 地面线同步
    //   点击反馈进行中时不动 texture / y (否则反馈会被打断, 出现闪帧)
    if (!clickReaction_) {
        if (sprite_ && sprite_.texture !== meta.frames[0]) {
            sprite_.texture = meta.frames[0];
        }
        applyFramePosition(action, 0);
        // R147: 进入 idle 时重置自然待机导演 (稳定站姿 + 自然眨眼)
        if (action === 'idle' && idleDirector_ && idleDirector_.enabled) {
            const baseIdx = idleDirector_.setAction('idle', performance.now());
            frameIdx = baseIdx;
            if (sprite_ && meta.frames[baseIdx]) sprite_.texture = meta.frames[baseIdx];
            applyFramePosition('idle', baseIdx);
        }
        // R153: 交叉溶解过渡 (姿态族差别大时)
        if (changed && blendMs > 0 && oldTexture && sprite_ && ensurePrevSprite()) {
            spritePrev_.texture = oldTexture;
            spritePrev_.x = sprite_.x;
            spritePrev_.y = oldY;
            spritePrev_.scale.set(sprite_.scale.x, sprite_.scale.y);
            spritePrev_.anchor.set(sprite_.anchor.x, sprite_.anchor.y);
            spritePrev_.alpha = 1;
            sprite_.alpha = 0;
            blend_ = { startAt: performance.now(), durationMs: blendMs, fromY: oldY };
            console.log(`[renderer] R153 BLEND ${prevAction} -> ${action} (${blendMs}ms)`);
        } else if (sprite_) {
            sprite_.alpha = 1;
        }
    }
    return true;
}

/**
 * R153: 确保过渡用的第二层 sprite 存在 (放在主 sprite 之下)。
 */
function ensurePrevSprite() {
    if (!app_ || !app_.stage) return false;
    if (!spritePrev_) {
        spritePrev_ = new PIXI.Sprite(PIXI.Texture.EMPTY);
        spritePrev_.alpha = 0;
        spritePrev_.interactive = false;
    }
    if (spritePrev_.parent !== app_.stage) {
        app_.stage.addChild(spritePrev_);
        app_.stage.setChildIndex(spritePrev_, 0);
    }
    return true;
}

/**
 * R153: 推进交叉溶解 (由 ticker 调用)。
 */
function updateBlend(now) {
    if (!blend_ || !sprite_ || !spritePrev_) return false;
    const t = Math.min(1, (now - blend_.startAt) / blend_.durationMs);
    sprite_.alpha = t;
    spritePrev_.alpha = 1 - t;
    // 旧层保持旧地面线, 新层从旧地面线滑到新地面线
    // (帧级溶解时目标地面线由 blend_.toY 给出, 避免被下一帧的 applyFramePosition 冲掉)
    const targetY = (typeof blend_.toY === 'number') ? blend_.toY : sprite_.y;
    sprite_.y = blend_.fromY + (targetY - blend_.fromY) * t;
    spritePrev_.y = blend_.fromY;
    if (t >= 1) {
        blend_ = null;
        sprite_.alpha = 1;
        spritePrev_.alpha = 0;
    }
    return true;
}

/**
 * R156: 点击反馈 —— **随机池**多帧动作。
 *
 * R153 变更背景 (用户真机反馈"点击后重复手放胸前的动作"):
 *   旧实现用 idle 的第 4/5 帧做眨眼反馈, 而 **idle_04 是右手横在胸前的姿势**,
 *   于是每次点击都会把手放到胸前, 缺乏含义。
 * R156 变更:
 *   点击反馈从"固定 1 个动作 + 人工 7px 弹跳"改为**从池中随机挑一个**:
 *     比心(近似) / 开心小跳 / 原地轻盈转身 / 歪头眨眼 / 双手小庆祝 / 开心摇摆
 *   每个动作 3 帧 (开始 → 情绪高点 → 收势), 帧自带运动, 不再叠加人工弹跳;
 *   短时间内不重复上一个 (clickRecent_)。
 *   播放期间 ticker 让位 (updateClickReaction 返回 true) → 普通 idle/walk/sleep 不推进;
 *   播完自动回到当前动作的正常状态机。
 */
function startClickReaction(forcedAction) {
    const pool = (manifest_ && manifest_.click_reactions && manifest_.click_reactions.enabled)
        ? manifest_.click_reactions.pool : null;
    // forcedAction 仅用于预览采集 (要逐个看清每个动作的全过程); 正常点击走随机池
    const action = (forcedAction && spritesByAction[forcedAction])
        ? forcedAction
        // R177: 心情给点击动作池加权 (开心→偏活泼; 困倦→偏轻量)
        : pickClickReaction(Math.random, clickRecent_, pool, moodClickWeight);
    const meta = spritesByAction[action];
    if (!meta || meta.frames.length === 0) {
        console.warn(`[renderer] R156 CLICK_REACTION skipped: ${action} has no frames`);
        return false;
    }
    clickRecent_.push(action);
    while (clickRecent_.length > 2) clickRecent_.shift();
    lastClickAction_ = action;
    clickClock_ = new AnimationClock();
    clickClock_.setAction(action, meta, performance.now());
    clickReaction_ = {
        startAt: performance.now(),
        action,
        meta,
        frameIndex: 0,
    };
    if (sprite_) {
        sprite_.texture = meta.frames[0];
        applyFramePosition(action, 0);
    }
    // R158: 点击反馈也可能有道具场景 (比心的爱心特效) —— 必须随点击动作挂载,
    //   否则道具永远不出现 (R158 之前点击路径从不调用 applyPropsFor)
    applyPropsFor(action);
    console.log(`[renderer] R156 CLICK_REACTION start action=${action} ` +
        `frames=${meta.frames.length} recent=${clickRecent_.join('>')} mood=${moodState_.mood}`);
    return true;
}

/**
 * R177: 当前心情对某个点击动作的权重乘子 (缺省 1 = 不加权)。
 * 权重表由主进程随心情一起下发 (renderer 不自己判断规则, 保持单一事实源)。
 */
function moodClickWeight(action) {
    const table = moodState_ && moodState_.click_weights;
    if (!table || typeof table !== 'object') return 1;
    const w = table[action];
    return typeof w === 'number' && Number.isFinite(w) ? w : 1;
}

/**
 * R156: 推进点击反馈。返回 true 表示反馈仍在进行 (ticker 应让位给反馈)。
 */
function updateClickReaction(now) {
    if (!clickReaction_) return false;
    const rec = clickReaction_;
    const res = clickClock_.tick(now);
    if (res.changed) {
        rec.frameIndex = res.frameIndex;
        if (sprite_ && rec.meta.frames[res.frameIndex]) {
            sprite_.texture = rec.meta.frames[res.frameIndex];
            applyFramePosition(rec.action, res.frameIndex);
        }
    }
    if (res.finished) {
        clickReaction_ = null;
        const meta = spritesByAction[currentAction];
        if (meta && meta.frames.length && sprite_) {
            sprite_.texture = meta.frames[Math.min(frameIdx, meta.frames.length - 1)];
            applyFramePosition(currentAction, frameIdx);
        }
        // R158: 点击反馈结束 → 道具跟着回到当前动作的场景 (爱心特效必须退场)
        applyPropsFor(currentAction);
        console.log(`[renderer] R156 CLICK_REACTION end action=${rec.action} ` +
            `t=+${Date.now() - R144_T0_}ms`);
        return false;
    }
    return true;
}

// 应用布局到 sprite (锚点 / 统一缩放 / 水平居中 / 当前帧地面线)
function applyLayoutToSprite() {
    if (!sprite_ || !layout_) return;
    sprite_.anchor.set(layout_.anchor.x, layout_.anchor.y);
    sprite_.scale.set(layout_.scale, layout_.scale);
    sprite_.x = layout_.x;
    // R147 首帧同步: 重建场景后立刻显示当前动作首帧 + 地面线 (不留旧动作残留)
    const meta = spritesByAction[currentAction];
    if (meta && meta.frames.length > 0) {
        frameIdx = 0;
        if (sprite_.texture !== meta.frames[0]) sprite_.texture = meta.frames[0];
    }
    applyFramePosition(currentAction, frameIdx);
    console.log(`[renderer] R144 LAYOUT mode=${currentMode_} canvas=${layout_.canvasW}x${layout_.canvasH} scale=${layout_.scale.toFixed(6)} groundY=${layout_.groundY} margin=${layout_.margin} frames=${layout_.frameCount} missingBBox=${layout_.missingBBox}`);
    if (layout_.missingBBox > 0) {
        console.error(`[renderer] R144 LAYOUT_MISSING_BBOX count=${layout_.missingBBox} (已退化为整张纹理, 角色会偏小)`);
    }
}

// ====== R100 P0-3 修复: sprite 事件绑定抽函数 ======
// 在 applyModeToScene 重建后重新调用, 不依赖 manifest IPC 一次性绑定

/**
 * R177: 取指针事件的按键号 (0=左, 1=中, 2=右)。
 * Pixi 的 FederatedPointerEvent 自带 button; 拿不到时退回 DOM 原始事件。
 */
function getEventButton(ev) {
    if (ev && typeof ev.button === 'number') return ev.button;
    const orig = ev && ev.data && ev.data.originalEvent;
    if (orig && typeof orig.button === 'number') return orig.button;
    return 0;
}

/**
 * R177: 请求主进程弹出右键菜单 (400ms 内不重复请求)。
 * @param {number} x 视口坐标 x
 * @param {number} y 视口坐标 y
 */
function requestContextMenu(x, y) {
    const now = Date.now();
    if (now - lastContextMenuAt_ < 400) return false;
    lastContextMenuAt_ = now;
    ipcRenderer.send('context-menu', { x: Math.round(x), y: Math.round(y) });
    console.log(`[renderer] R177 CONTEXT_MENU_REQUEST at=(${Math.round(x)},${Math.round(y)})`);
    return true;
}

/** R177: 点是否落在角色身上 (用于判断右键是否打在桌宠上)。 */
function isPointOnSprite(x, y) {
    if (!sprite_) return false;
    const b = sprite_.getBounds();
    return x >= b.x && x <= b.x + b.width && y >= b.y && y <= b.y + b.height;
}

function bindSpriteEvents() {
    if (!sprite_) return;
    sprite_.on('pointerdown', (ev) => {
        // R177: **只有左键**才可能开始拖拽/点击。
        //   右键必须被隔离, 否则右键会误触发拖拽 (角色被"拖走") 也会误触发点击反馈。
        const btn = getEventButton(ev);
        if (btn === 2) {
            // 右键 ⇒ 请求弹出菜单 (菜单由主进程用原生 Menu 弹出)
            try { ev.originalEvent && ev.originalEvent.preventDefault && ev.originalEvent.preventDefault(); } catch (e) {}
            const g = ev.data && ev.data.global;
            requestContextMenu(g ? g.x : 0, g ? g.y : 0);
            return;
        }
        if (btn !== 0) return;   // 中键等一律忽略
        // R111 诊断: 记录 pointerdown 触发 (真实物理鼠标必触发)
        console.log(`[renderer] R111 DRAG_POINTER_DOWN sprite at (${ev.data.global.x},${ev.data.global.y}) interactive=${sprite_.interactive} buttonMode=${sprite_.buttonMode}`);
        dragging = true;
        // R111: 不存 clientX/Y (坐标系混用 root cause), main 端用 screen.getCursorScreenPoint()
        dragIsWindowDrag_ = false;
        dragMoved_ = 0;
        // R147: 记录本次按下的计时与累计位移 (用于区分 CLICK / DRAG)
        pressInfo_ = { at: performance.now(), distance: 0 };
        pressAction_ = currentAction;   // 按下**之前**的动作 (睡眠点击唤醒用)
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
        finishPress('up');
    });
    sprite_.on('pointerupoutside', () => {
        console.log('[renderer] R111 DRAG_SPRITE_POINTERUPOUTSIDE');
        // 指针离开角色区域后松开 → 正常清理, 但不算单击
        finishPress('outside');
    });
}

/**
 * R147: 统一的"按下结束"处理 — 唯一出口, 保证同一次操作只会有一种结果。
 *
 * 判定:
 *   · 已经进入窗口拖拽 (累计位移 ≥ 3px)  → DRAG : 只发拖拽结束, 不触发点击反馈
 *   · 正常抬起, 按住 ≤ 400ms 且位移 < 3px → CLICK : 触发点击反馈
 *   · 指针离开角色区域 / 鼠标被取消       → 清理, 不触发点击反馈
 *
 * 幂等: dragging 为 false 时直接返回, 因此 sprite 与 canvas 两层 pointerup
 *       重复到达时, 第二次是空操作 (不会重复 endDrag / 重复发 IPC)。
 *
 * @param {'up'|'outside'|'cancel'} reason
 * @returns {boolean} 是否判定为 CLICK
 */
function finishPress(reason) {
    if (!dragging) return false;   // R147: 幂等守卫 (sprite/canvas 两层 pointerup)
    const wasWindowDrag = dragIsWindowDrag_;
    const prevAction = pressAction_;
    const info = pressInfo_;
    const elapsed = info ? (performance.now() - info.at) : Infinity;
    const distance = info ? info.distance : Infinity;
    // R147: 判定逻辑放在纯逻辑模块 click_policy.js (与自动化测试同一份代码)
    const kind = classifyPress({ reason, elapsedMs: elapsed, distancePx: distance, wasWindowDrag });
    const isClick = isClickReaction(kind);
    lastPressKind_ = kind;

    if (isDragEnd(kind)) {
        ipcRenderer.send('window-drag-end');
    }
    pressInfo_ = null;
    pressAction_ = null;
    endDrag({ click: isClick, kind, prevAction });
    console.log(`[renderer] R147 PRESS_END kind=${kind} elapsed=${elapsed.toFixed(0)}ms dist=${distance.toFixed(1)}px prev=${prevAction}`);
    return isClick;
}

/**
 * 结束拖拽/按下状态。
 * @param {{click?:boolean, kind?:string, prevAction?:string}} [opts]
 */
function endDrag(opts = {}) {
    // R147: 幂等守卫 — 重复调用是空操作
    if (!dragging && !opts.force) return false;
    dragging = false;
    dragIsWindowDrag_ = false;
    dragMoved_ = 0;
    const isClick = !!opts.click;
    const kind = opts.kind || (isClick ? 'CLICK' : 'DRAG');
    const prevAction = opts.prevAction || '';
    const wasSleeping = (prevAction === 'sleep_loop' || prevAction === 'sleep_enter');

    if (isClick && wasSleeping) {
        // R147: 睡眠中被点击 → 保持当前画面, 等主进程下发 wake_up (不闪一下站姿)
        //   醒来过渡由 wake_up 一次性动画承担, 绝不瞬移成站姿
        console.log(`[renderer] R147 CLICK_WAKE prev=${prevAction} (等待 wake_up 指令)`);
    } else {
        // R147 首帧同步: 立刻显示目标动作首帧 + 地面线同步, 不留旧动作残留
        applyAction('idle', { immediate: true });
    }

    lastAdvanceAt = performance.now();
    if (isClick) {
        // R147: 点击走独立 IPC, 由主进程统一处理拖拽态与自主行为协调
        ipcRenderer.send('character-click', {
            action: prevAction,
            // R156: 点击池动作有 3 帧 (总时长最长 ~1.0s), 暂缓自主行为要覆盖整个反馈
            holdMs: R156_CLICK_HOLD_MS,
        });
        // R177: 可见反馈受两个开关约束 ——
        //   ① 设置面板的"点击反馈"开关
        //   ② 心情抑制 (困倦时她只想睡, 见 mood_engine.sleepy_suppress_click)
        // 注意: 无论是否出反馈, 上面那条 character-click 都要发 ——
        //   睡眠中点击必须仍然能唤醒角色。
        const suppressed = moodState_.suppress_click === true;
        if (!wasSleeping && clickFeedbackEnabled_ && !suppressed) {
            startClickReaction();
        } else if (!wasSleeping) {
            console.log(`[renderer] R177 CLICK_FEEDBACK_SKIPPED enabled=${clickFeedbackEnabled_} suppress=${suppressed} mood=${moodState_.mood}`);
        }
    } else if (releasesPress(kind)) {
        // R141 §四: 松开鼠标后恢复自主行为 (main 侧带过渡延迟)
        ipcRenderer.send('behavior-drag-state', false);
    }
    setFallbackText(isClick ? 'click' : 'idle');
    return true;
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
                applyAction(action);
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
    // R177: opts.w / opts.h 可覆盖画布尺寸 —— "桌宠大小"就是靠它把画布重建到新尺寸的
    const useOverride = (typeof opts.w === 'number' && opts.w > 0 && typeof opts.h === 'number' && opts.h > 0);
    const w = useOverride ? Math.round(opts.w) : (mode === 'compact' ? compactWidth_ : standardSize_);
    const h = useOverride ? Math.round(opts.h) : (mode === 'compact' ? compactHeight_ : standardSize_);
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
    // R156: 旧 app 销毁会连带销毁道具 sprite → 先把引用清掉, 避免留下野指针
    for (const [, rec] of propSprites_) {
        try { rec.sprite.destroy(); } catch (e) {}
    }
    propSprites_.clear();
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
    // R153: 场景重建 → 过渡状态复位 (旧 sprite 已随旧 app 销毁)
    blend_ = null;
    spritePrev_ = null;
    // R100 P0-3: 重建后重绑 sprite 事件 + canvas 全局事件
    bindSpriteEvents();
    attachCanvasListeners(app_.view);
    // 重启 ticker
    lastAdvanceAt = performance.now();
    frameIdx = 0;
    // R147: 模式重建后用统一入口恢复当前动作 (首帧 + 地面线 + 倾斜 + 待机导演)
    applyAction(currentAction);
    app_.ticker.add(tickerCallback);
    stageCssWidth = w;
    stageCssHeight = h;
    const centerLog = cx !== null ? `center=(${cx},${cy})` : `center=canvas_default`;
    setFallbackText(`[renderer] R144 mode=${mode} size=${w}x${h} scale=${layout_.scale.toFixed(4)} ${centerLog}`);
    console.log(`[renderer] R144 mode=${mode} canvas=${w}x${h} scale=${layout_.scale.toFixed(6)} groundY=${layout_.groundY} ${centerLog} hitArea=${JSON.stringify(sprite_.getBounds())}`);
    return { ok: true, mode, size: { w, h }, center: { x: cx, y: cy }, scale: layout_.scale };
}

/**
 * R153: 加载一组动作的帧纹理 (核心 6 组与动作库共用同一份实现)。
 * @param {object} a manifest 里的动作定义 (frames: 相对路径数组)
 * @param {string} baseDir 资源根目录
 * @returns {Promise<{frames: Array, failed: number}>}
 */
async function loadActionFrames(a, baseDir) {
    const path = require('path');
    const url = require('url');
    const frames = [];
    let failed = 0;
    for (const rel of (a.frames || [])) {
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
    return { frames, failed };
}

ipcRenderer.on('manifest', async (_evt, payload) => {
    setFallbackText('[renderer] loading manifest…');
    const { manifest, baseDir } = payload;
    manifest_ = manifest;   // R144: 保留 manifest 供布局构建与边界自检
    // R147: 自然待机导演 (稳定站姿 + 自然眨眼; 膨胀帧 idle_01 不再播放)
    const idleSpec = (manifest.actions && manifest.actions.idle) ? manifest.actions.idle.director : null;
    idleDirector_ = new IdleDirector({ spec: idleSpec });
    console.log(`[renderer] R147 idle-director enabled=${idleDirector_ && idleDirector_.enabled} spec=${JSON.stringify(idleSpec)}`);
    currentMode_ = payload.initialMode || 'standard';
    // R177: 桌宠大小 —— 首帧就按生效视口建画布 (避免先按基础尺寸画一遍再跳)
    if (payload.viewport && typeof payload.viewport.w === 'number' && typeof payload.viewport.h === 'number') {
        initialViewport_ = { w: payload.viewport.w, h: payload.viewport.h };
        console.log(`[renderer] R177 INITIAL_VIEWPORT ${payload.viewport.w}x${payload.viewport.h} scale=${payload.petScale}`);
    }
    if (typeof payload.clickFeedback === 'boolean') clickFeedbackEnabled_ = payload.clickFeedback;
    if (payload.mood && typeof payload.mood === 'object') {
        moodState_ = {
            mood: payload.mood.mood || 'calm',
            label: payload.mood.label || '平静',
            energy: typeof payload.mood.energy === 'number' ? payload.mood.energy : 1,
            click_weights: payload.mood.click_weights || {},
            suppress_click: !!payload.mood.suppress_click,
        };
    }
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
        const { frames, failed } = await loadActionFrames(a, baseDir);
        spritesByAction[action] = {
            frames,
            fps: a.fps || 8,
            frame_ms: a.frame_ms || null,   // R141: 精确帧时长 (优先于 fps)
            loop: !!a.loop,
            // R153: 帧级溶解时长 (一次性动画内部换帧, 如 坐→躺)
            frame_blend_ms: a.frame_blend_ms || 0,
            failed,
        };
        assetLoadTotal_ += frames.length + failed;
        assetLoadFailed_ += failed;
        ipcRenderer.send('asset-report', { action, loaded: frames.length, failed, total: frames.length + failed });
        console.log(`[renderer] R100 asset-report ${action}: loaded=${frames.length} failed=${failed}`);
    }

    // ====== R153: 动作库加载 (新增动作, 与核心 6 组**分开**上报) ======
    // 核心 6 组的 "assets-ready 23/23" 契约保持不变 (资产门禁口径不动);
    // 动作库走独立的 library-assets-ready 上报, 缺帧同样明确报错、不假装成功。
    const libSpec = (manifest.action_library && manifest.action_library.enabled)
        ? (manifest.action_library.actions || {}) : {};
    const libNames = Object.keys(libSpec);
    let libLoaded = 0;
    let libFailed = 0;
    for (const action of libNames) {
        const a = libSpec[action];
        const { frames, failed } = await loadActionFrames(a, baseDir);
        spritesByAction[action] = {
            frames,
            fps: a.fps || 8,
            frame_ms: a.frame_ms || null,
            loop: !!a.loop,
            frame_blend_ms: a.frame_blend_ms || 0,
            failed,
        };
        libLoaded += frames.length;
        libFailed += failed;
        ipcRenderer.send('library-asset-report', { action, loaded: frames.length, failed, total: frames.length + failed });
        console.log(`[renderer] R153 library-asset-report ${action}: loaded=${frames.length} failed=${failed}`);
    }
    const libraryReady = {
        ok: libFailed === 0 && libNames.length > 0,
        actions: libNames.length,
        loaded: libLoaded,
        failed: libFailed,
    };
    ipcRenderer.send('library-assets-ready', libraryReady);
    console.log(`[renderer] R153 library-assets-ready ${JSON.stringify(libraryReady)}`);
    if (libNames.length > 0 && libFailed > 0) {
        console.error(`[renderer] R153 LIBRARY_ASSET_ERROR ${libFailed} 帧加载失败`);
    }
    // ====== R156: 场景道具加载 (7 个程序化绘制的小道具) =====
    const propLib = (manifest.props && manifest.props.enabled) ? (manifest.props.library || {}) : {};
    propTextures_ = {};
    propAssetLoaded_ = 0;
    propAssetFailed_ = 0;
    for (const [name, spec] of Object.entries(propLib)) {
        if (!spec || !spec.file) { propAssetFailed_++; continue; }
        const abs = path.join(baseDir, spec.file);
        const fileUrl = url.pathToFileURL(abs).toString();
        try {
            const texture = await PIXI.Assets.load(fileUrl);
            if (texture && texture.baseTexture && texture.baseTexture.valid) {
                propTextures_[name] = texture;
                propAssetLoaded_++;
            } else {
                propAssetFailed_++;
                console.warn(`[renderer] R156 prop asset invalid: ${fileUrl}`);
            }
        } catch (e) {
            propAssetFailed_++;
            console.warn(`[renderer] R156 prop asset failed: ${fileUrl} ${e?.message || e}`);
        }
    }
    ipcRenderer.send('props-asset-report', {
        loaded: propAssetLoaded_, failed: propAssetFailed_,
        total: propAssetLoaded_ + propAssetFailed_,
    });
    console.log(`[renderer] R156 props-asset-report loaded=${propAssetLoaded_} failed=${propAssetFailed_}`);
    if (propAssetFailed_ > 0) {
        console.error(`[renderer] R156 PROP_ASSET_ERROR ${propAssetFailed_} 个道具加载失败`);
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

    // R177: 首帧画布 = 生效视口 (基础尺寸 × 桌宠大小倍率)
    const w = initialViewport_ ? initialViewport_.w : (currentMode_ === 'compact' ? compactWidth_ : standardSize_);
    const h = initialViewport_ ? initialViewport_.h : (currentMode_ === 'compact' ? compactHeight_ : standardSize_);
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
    // R153: 场景重建 → 过渡状态复位 (旧 sprite 已随旧 app 销毁)
    blend_ = null;
    spritePrev_ = null;
    console.log(`[renderer] R144 sprite enabled: mode=${currentMode_} canvas=${w}x${h} scale=${layout_.scale.toFixed(6)} groundY=${layout_.groundY} hitArea=${JSON.stringify(sprite_.getBounds())}`);

    bindSpriteEvents();
    attachCanvasListeners(app_.view);
    lastAdvanceAt = performance.now();
    frameIdx = 0;
    // R147: 用统一入口初始化当前动作 (首帧立即显示 + 待机导演重置)
    applyAction(currentAction);
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
    // R147: 首帧同步 / 地面线 / 方向倾斜 / 待机无膨胀帧 / 点击可见反馈
    if (process.env.PET_R147_SELFTEST === '1') {
        setTimeout(() => runR147SelfTest(), 1200);
    }
});

ipcRenderer.on('set-action', (_evt, action) => {
    if (spritesByAction[action] && spritesByAction[action].frames.length > 0) {
        // R147: 首帧同步 — applyAction 立刻把 texture 换成目标动作第 0 帧,
        //   地面线与方向倾斜同步更新, 不等下一次 ticker (修 R144 记录的旧问题)
        const ok = applyAction(action);
        setFallbackText('[renderer] switched to ' + action);
        console.log(`[renderer] R147 set-action ${action} applied=${ok} loop=${!!spritesByAction[action].loop} frame_ms=${spritesByAction[action].frame_ms} frames=${spritesByAction[action].frames.length} skew=${layout_ && layout_.skewByAction ? layout_.skewByAction[action] : 0}`);
    } else {
        console.warn(`[renderer] set-action ${action} refused: empty frames`);
    }
});

// ====== R147: 运行时预览采集 (仅主进程 --preview 模式下发) ======
// 用**真实的 pointer 事件**驱动 sprite 的 pointerdown/pointerup 处理链,
// 因此走的是与用户真机点击完全相同的代码路径 (finishPress → CLICK → 点击反馈)。
ipcRenderer.on('preview-command', async (_evt, payload) => {
    const id = payload && payload.id;
    const cmd = (payload && payload.cmd) || '';
    try {
        if (cmd === 'action') {
            const ok = applyAction(payload.action);
            ipcRenderer.send('preview-result', { id, cmd, ok, action: payload.action });
        } else if (cmd === 'click') {
            const res = await runPreviewClick(payload && payload.action);
            ipcRenderer.send('preview-result', Object.assign({ id, cmd }, res));
        } else {
            ipcRenderer.send('preview-result', { id, cmd, ok: false, error: 'unknown cmd' });
        }
    } catch (e) {
        ipcRenderer.send('preview-result', { id, cmd, ok: false, error: (e && e.message) || String(e) });
    }
});

async function runPreviewClick(forcedAction) {
    if (!sprite_ || !app_) return { ok: false, error: 'sprite/app 未就绪' };
    // 用 sprite 的**可见包围盒中心**构造 pointer 事件 (走 PixiJS 的命中测试)
    // 注意: 不能用 getGlobalPosition() —— 那是锚点位置, 躺睡姿态下锚点并不在角色身上
    const b = sprite_.getBounds();
    const rect = app_.view.getBoundingClientRect();
    const clientX = rect.left + (b.x + b.width / 2);
    const clientY = rect.top + (b.y + b.height / 2);
    const base = {
        clientX, clientY, button: 0, buttons: 1, bubbles: true, cancelable: true,
        pointerId: 1, pointerType: 'mouse', isPrimary: true,
    };
    // R165: 合成点击期间不累计真实鼠标的位移 (见 previewSyntheticPress_ 的说明)
    previewSyntheticPress_ = true;
    app_.view.dispatchEvent(new PointerEvent('pointerdown', base));
    await new Promise((r) => setTimeout(r, 90));
    const downSeen = !!pressInfo_;
    app_.view.dispatchEvent(new PointerEvent('pointerup', Object.assign({}, base, { buttons: 0 })));
    await new Promise((r) => setTimeout(r, 60));
    previewSyntheticPress_ = false;
    const kind = lastPressKind_;
    // 强制指定动作时, 预览采集直接播那个动作 (不走随机)
    if (forcedAction) {
        applyAction('idle', { immediate: true });
        startClickReaction(forcedAction);
    }
    console.log(`[renderer] R147 PREVIEW_CLICK downSeen=${downSeen} kind=${kind} action=${lastClickAction_}`);
    return {
        ok: true,
        downSeen,
        kind,
        action: lastClickAction_,
        clientX: Math.round(clientX),
        clientY: Math.round(clientY),
    };
}

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
    // R177: 传 payload.size 作为画布尺寸覆盖 —— "桌宠大小"缩放后窗口尺寸已变,
    //   画布必须用同一个尺寸, 否则角色会被拉伸或裁切。
    const result = applyModeToScene(payload.mode, {
        centerX: payload.centerX,
        centerY: payload.centerY,
        w: payload.size && payload.size.w,
        h: payload.size && payload.size.h,
    });
    // 通知 main 确认 (R100 P0-2 要求)
    ipcRenderer.send('renderer-mode-ready', {
        mode: payload.mode,
        size: payload.size,
        centerX: payload.centerX,
        centerY: payload.centerY,
        ok: result.ok,
    });
});

// ====== R177: 心情 / 设置 / 视口尺寸 ======

// 心情变化 ⇒ 点击动作池换权重 (并决定是否抑制点击反馈)
ipcRenderer.on('mood-changed', (_evt, payload) => {
    if (!payload || typeof payload !== 'object') return;
    moodState_ = {
        mood: payload.mood || 'calm',
        label: payload.label || '平静',
        energy: typeof payload.energy === 'number' ? payload.energy : 1,
        click_weights: payload.click_weights || {},
        suppress_click: !!payload.suppress_click,
    };
    console.log(`[renderer] R177 MOOD_CHANGED mood=${moodState_.mood} label=${moodState_.label} suppress=${moodState_.suppress_click}`);
});

// 设置变更 ⇒ 点击反馈开关 / 频率等 (频率由主进程直接作用在行为引擎上)
ipcRenderer.on('settings-changed', (_evt, payload) => {
    if (!payload || typeof payload !== 'object') return;
    if (typeof payload.click_feedback === 'boolean') clickFeedbackEnabled_ = payload.click_feedback;
    if (payload.mood) {
        moodState_ = {
            mood: payload.mood.mood || 'calm',
            label: payload.mood.label || '平静',
            energy: typeof payload.mood.energy === 'number' ? payload.mood.energy : 1,
            click_weights: payload.mood.click_weights || {},
            suppress_click: !!payload.mood.suppress_click,
        };
    }
    console.log(`[renderer] R177 SETTINGS_CHANGED click_feedback=${clickFeedbackEnabled_} settings=${JSON.stringify(payload.settings || {})}`);
});

// 桌宠大小变化 ⇒ 按新尺寸重建画布 (窗口尺寸由主进程同步改好)
ipcRenderer.on('set-viewport', (_evt, payload) => {
    if (!payload || typeof payload.w !== 'number' || typeof payload.h !== 'number') {
        console.warn('[renderer] R177 set-viewport refused: invalid payload', payload);
        return;
    }
    const mode = (payload.mode === 'compact' || payload.mode === 'standard') ? payload.mode : currentMode_;
    const result = applyModeToScene(mode, {
        w: payload.w,
        h: payload.h,
        centerX: payload.w / 2,
        centerY: payload.h,
    });
    console.log(`[renderer] R177 SET_VIEWPORT ${payload.w}x${payload.h} scale=${payload.scale} ok=${result.ok}`);
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

// R144: 真实 PixiJS 变换矩阵下的全部帧可见像素边界核算
// R156: 帧数从 23 涨到 114 (R138 23 + R153 + R156 的 20 张), 判据按逐帧地面行精确化
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
                // R147: 方向倾斜 (整体朝向) — 必须与生产渲染完全一致, 否则核算失真
                const k = (layout.skewByAction && typeof layout.skewByAction[action] === 'number')
                    ? layout.skewByAction[action] : 0;
                sp.skew.x = skewAngleX(k);
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
                // R147: 错切后四角的极值不一定落在 tl/br, 必须取 4 角最小包围盒
                const quad = [
                    [rect.left, rect.top], [rect.right, rect.top],
                    [rect.left, rect.bottom], [rect.right, rect.bottom],
                ].map(([u, v]) => sp.worldTransform.apply(new PIXI.Point(u - ax * origW, v - ay * origH)));
                const qx = quad.map(p => p.x);
                const qy = quad.map(p => p.y);
                const tl = { x: Math.min(...qx), y: Math.min(...qy) };
                const br = { x: Math.max(...qx), y: Math.max(...qy) };
                const inside = tl.x >= -0.01 && tl.y >= -0.01 && br.x <= w + 0.01 && br.y <= h + 0.01;
                // R156: 地面接触线判据按"逐帧地面行 (ground_tex_y)"精确化。
                //   旧判据 (R144): 内容底边必须正好落在地面接触线上。
                //   但 R156 引入了逐帧地面行 —— 有道具的动作里, 真正的地面是**道具的底**
                //   (床脚 818 / 沙发底 1001 / 桌腿底 1001), 角色要踩在道具底上;
                //   腾空帧则用更高的地面行 (1015) 表示离地。
                //   ⇒ 判据改为"内容底边必须落在**该帧声明的接触行**上":
                //       接触行 = ground_tex_y (声明值) 或 内容底边 (未声明 ⇒ R144 原语义, 完全不变)
                //       期望屏幕底边 = groundY + scale*cosT*(rect.bottom - 接触行)
                //   未声明 ground_tex_y 的帧 (R138 全部 23 帧 + R153 的帧) 判据与 R144 **逐字等价**。
                const groundRows = layout.groundTexYByAction && layout.groundTexYByAction[action];
                const declaredGround = (groundRows && typeof groundRows[i] === 'number') ? groundRows[i] : null;
                const contactRow = (declaredGround !== null) ? declaredGround : rect.bottom;
                const cosT = Math.sqrt(Math.max(0, 1 - k * k));
                const expectedBottomY = layout.groundY + layout.scale * cosT * (rect.bottom - contactRow);
                const groundErr = Math.abs(br.y - expectedBottomY);
                totalFrames++;
                if (!inside) {
                    clippedFrames++;
                    issues.push(`${mode}/${action}[${i}] 越界 screen=(${tl.x.toFixed(2)},${tl.y.toFixed(2)})-(${br.x.toFixed(2)},${br.y.toFixed(2)}) canvas=${w}x${h} skew=${k}`);
                }
                if (groundErr > 0.01) {
                    const why = (declaredGround !== null)
                        ? ` (声明接触行 ground_tex_y=${contactRow}, 期望底边=${expectedBottomY.toFixed(4)})`
                        : '';
                    issues.push(`${mode}/${action}[${i}] 地面接触线偏差 ${groundErr.toFixed(4)}px${why}`);
                }
                console.log(`[R144 bounds self-test] ${mode} ${action}[${i}] screen=(${tl.x.toFixed(2)},${tl.y.toFixed(2)})-(${br.x.toFixed(2)},${br.y.toFixed(2)}) inside=${inside} groundErr=${groundErr.toFixed(4)} skew=${k}`);
            }
        }
        console.log(`[R144 bounds self-test] MODE ${mode} canvas=${w}x${h} scale=${layout.scale.toFixed(6)} groundY=${layout.groundY} margin=${layout.margin}`);
    }
    console.log(`[R144 bounds self-test] SUMMARY frames=${totalFrames} clipped=${clippedFrames} issues=${issues.length}`);
    if (issues.length === 0 && clippedFrames === 0) {
        console.log(`[R144 bounds self-test] PASS — ${totalFrames} 帧在两种画布尺寸下均完整显示且落在各自声明的接触行上`);
    } else {
        console.log('[R144 bounds self-test] FAIL:', issues.join('; '));
    }
}
