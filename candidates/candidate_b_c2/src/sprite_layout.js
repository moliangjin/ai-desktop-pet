// R144 桌宠 sprite 布局算法 (纯逻辑模块, 无 Electron 依赖)
//
// 背景 (R144 P0-1):
//   R141 的 renderer 用固定参数摆放角色:
//       anchor.set(0.5, 0.9); sprite.y = h; sc = mode==='compact' ? w/manifestCanvasSize_ : 1.0;
//   R138 素材是 1024x1024 且角色只占画布一部分, 于是:
//       - compact 200x240: 角色像素超出窗口底部 (实测裁切 3.7%~6.7%)
//       - standard 256x256: sc=1.0 直接把 1024 画布塞进 256 窗口 (实测裁切 82%~99%)
//
// 本模块给出替代算法, 生产渲染 (renderer.js) 与自动化测试 (tests/r144_*.test.js)
// 调用的是**同一份代码**, 保证测试核算的就是运行时真正使用的几何。
//
// 算法 (三条硬约束):
//   1. 统一缩放: 全部 23 帧共用同一个 scale, 由"最紧的那一帧"决定。
//      禁止逐帧改大小来规避裁切。
//   2. 地面接触线: 每一帧内容的**底边**都落在同一条屏幕线 (canvasH - margin),
//      因此站立/行走/坐/躺之间切换时脚底与地面接触点不跳动。
//   3. 水平参考线: 纹理中心 (anchor.x=0.5) 固定落在画布正中, 角色不左右漂移。
//
// 坐标系:
//   纹理坐标 (u,v) — PNG 像素, 原点在纹理左上角, 纹理尺寸 textureW x textureH
//   屏幕坐标 (x,y) — PixiJS stage 逻辑像素
//   PixiJS sprite 变换: screen = position + (texture - anchor * textureSize) * scale
//   故 anchor 固定时, 内容底边 b 落在 groundY 的解为:
//       position.y = groundY - (b - anchor.y * textureH) * scale

'use strict';

const DEFAULT_MARGIN_PX = 4;
const DEFAULT_ANCHOR = Object.freeze({ x: 0.5, y: 0.9 });

/**
 * 把 manifest 里的 bbox [left, top, right, bottom] 转成内容矩形。
 * bbox 采用与 PIL Image.getbbox() 一致的约定 (right/bottom 为开区间)。
 */
function toContentRect(bbox) {
    if (!Array.isArray(bbox) || bbox.length < 4) return null;
    const left = Number(bbox[0]);
    const top = Number(bbox[1]);
    const right = Number(bbox[2]);
    const bottom = Number(bbox[3]);
    if (![left, top, right, bottom].every(Number.isFinite)) return null;
    if (!(right > left) || !(bottom > top)) return null;
    return { left, top, right, bottom, w: right - left, h: bottom - top };
}

/**
 * 计算覆盖全部帧的**统一**缩放倍率。
 *
 * @param {Array<{left,top,right,bottom,w,h}>} rects 各帧内容矩形 (纹理坐标)
 * @param {number} canvasW 画布宽 (屏幕像素)
 * @param {number} canvasH 画布高 (屏幕像素)
 * @param {number} textureW 纹理宽
 * @param {number} textureH 纹理高
 * @param {number} margin 画布四周留白
 */
function computeUniformScale(rects, canvasW, canvasH, textureW, textureH, margin) {
    const anchor = DEFAULT_ANCHOR;
    const refX = anchor.x * textureW;      // 水平参考线 (纹理中心)
    const halfW = canvasW / 2 - margin;    // 参考线到画布左右边界的可用空间
    const availH = canvasH - 2 * margin;   // 地面线以上的可用高度
    let scale = Infinity;
    for (const r of rects) {
        if (!r || !(r.w > 0) || !(r.h > 0)) continue;
        // 竖直: 底边贴地面线, 顶边不得越过上边界
        let s = availH / r.h;
        // 水平: 内容不得越过左右边界 (参考线固定在画布正中, 故左右可用空间相同)
        if (r.left < refX) s = Math.min(s, halfW / (refX - r.left));
        if (r.right > refX) s = Math.min(s, halfW / (r.right - refX));
        if (s < scale) scale = s;
    }
    if (!Number.isFinite(scale) || scale <= 0) return 1;
    return scale;
}

/**
 * 计算完整布局。
 *
 * @param {object} opts
 * @param {number} opts.canvasW
 * @param {number} opts.canvasH
 * @param {number} opts.textureW
 * @param {number} opts.textureH
 * @param {Array<{action:string,index:number,bbox:number[]}>} opts.frames
 * @param {number} [opts.margin]
 */
function computeLayout(opts) {
    const {
        canvasW, canvasH, textureW, textureH, frames,
        margin = DEFAULT_MARGIN_PX,
    } = opts || {};

    const rects = [];
    const frameY = [];
    const frameYByAction = {};
    const rectsByAction = {};
    let missingBBox = 0;

    for (const f of (frames || [])) {
        const rect = toContentRect(f.bbox);
        if (!rect) {
            // 缺 bbox → 退化为整张纹理 (保守: 不会裁切, 但角色会偏小)
            missingBBox++;
            const full = { left: 0, top: 0, right: textureW, bottom: textureH, w: textureW, h: textureH };
            rects.push(full);
            rectsByAction[f.action] = rectsByAction[f.action] || [];
            rectsByAction[f.action][f.index] = full;
        } else {
            rects.push(rect);
            rectsByAction[f.action] = rectsByAction[f.action] || [];
            rectsByAction[f.action][f.index] = rect;
        }
        frameY.push(0);
        frameYByAction[f.action] = frameYByAction[f.action] || [];
    }

    const scale = computeUniformScale(rects, canvasW, canvasH, textureW, textureH, margin);
    const anchor = { x: DEFAULT_ANCHOR.x, y: DEFAULT_ANCHOR.y };
    const groundY = canvasH - margin;   // 地面接触线 (屏幕坐标)
    const x = canvasW / 2;              // 水平参考线落点

    for (let i = 0; i < rects.length; i++) {
        const f = frames[i];
        const r = rects[i];
        const y = groundY - (r.bottom - anchor.y * textureH) * scale;
        frameY[i] = y;
        frameYByAction[f.action][f.index] = y;
    }

    return {
        scale,
        anchor,
        x,
        groundY,
        margin,
        canvasW,
        canvasH,
        textureW,
        textureH,
        frameY,
        frameYByAction,
        rects,
        rectsByAction,
        missingBBox,
        frameCount: frames ? frames.length : 0,
    };
}

/**
 * 把内容矩形 (纹理坐标) 映射到屏幕矩形 — 供测试与 renderer 自检核算裁切。
 * 与 PixiJS 的 sprite 变换完全一致 (anchor 固定, 底边贴 groundY)。
 */
function contentRectToScreen(rect, layout) {
    const s = layout.scale;
    const x0 = layout.x + (rect.left - layout.anchor.x * layout.textureW) * s;
    const x1 = layout.x + (rect.right - layout.anchor.x * layout.textureW) * s;
    const y1 = layout.groundY;
    const y0 = layout.groundY - (rect.bottom - rect.top) * s;
    return { left: x0, top: y0, right: x1, bottom: y1 };
}

/**
 * 判定屏幕矩形是否完整落在画布内 (含 margin 判定开关)。
 */
function isRectInsideCanvas(rect, layout, tolerance = 0.01) {
    return rect.left >= layout.margin - tolerance &&
        rect.top >= layout.margin - tolerance &&
        rect.right <= layout.canvasW - layout.margin + tolerance &&
        rect.bottom <= layout.canvasH - layout.margin + tolerance;
}

/**
 * R141 遗留算法 (仅供回归对比, 证明旧参数确实会裁切)。
 */
function legacyLayout(opts) {
    const { canvasW, canvasH, textureW, mode } = opts;
    const scale = mode === 'compact' ? canvasW / textureW : 1.0;
    return {
        scale,
        anchor: { x: 0.5, y: 0.9 },
        x: canvasW / 2,
        y: canvasH,
        canvasW,
        canvasH,
        textureW,
        textureH: textureW,
        margin: 0,
    };
}

module.exports = {
    DEFAULT_MARGIN_PX,
    DEFAULT_ANCHOR,
    toContentRect,
    computeUniformScale,
    computeLayout,
    contentRectToScreen,
    isRectInsideCanvas,
    legacyLayout,
};
