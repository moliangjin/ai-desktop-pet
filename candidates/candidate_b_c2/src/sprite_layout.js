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
 * 计算覆盖全部帧的**统一**缩放倍率 (R147: 纳入方向倾斜 skew)。
 *
 * 水平错切发生在**顶点层** (PixiJS 语义):
 *     local = (u - ax*W, v - ay*H)   →   x' = lx + k*ly
 * 因此错切后每帧的水平占位要按 x' 的极值计算, 否则倾斜会把角色推出画布。
 *
 * @param {Array<{rect:object, skewX:number}>} entries 各帧内容矩形 + 该帧倾斜因子
 * @param {number} canvasW 画布宽 (屏幕像素)
 * @param {number} canvasH 画布高 (屏幕像素)
 * @param {number} textureW 纹理宽
 * @param {number} textureH 纹理高
 * @param {number} margin 画布四周留白
 */
function computeUniformScaleWithSkew(entries, canvasW, canvasH, textureW, textureH, margin) {
    const anchor = DEFAULT_ANCHOR;
    const halfW = canvasW / 2 - margin;    // 参考线到画布左右边界的可用空间
    const availH = canvasH - 2 * margin;   // 地面线以上的可用高度
    let scale = Infinity;
    for (const e of (entries || [])) {
        const r = e && e.rect;
        if (!r || !(r.w > 0) || !(r.h > 0)) continue;
        const k = (e && typeof e.skewX === 'number') ? e.skewX : 0;
        const cosT = skewCosFactor(k);
        // 竖直: 底边贴地面线, 顶边不得越过上边界 (错切会按 cosθ 压缩竖直)
        let s = availH / (cosT * r.h);
        // 水平: 按错切后的 x' 极值核算
        const ext = shearedLocalExtent(r, anchor, textureW, textureH, k);
        if (ext.minLX < 0) s = Math.min(s, halfW / (-ext.minLX));
        if (ext.maxLX > 0) s = Math.min(s, halfW / ext.maxLX);
        if (s < scale) scale = s;
    }
    if (!Number.isFinite(scale) || scale <= 0) return 1;
    return scale;
}

/**
 * 错切后某一帧在局部坐标 (post-anchor) 下的水平占位范围。
 */
function shearedLocalExtent(rect, anchor, textureW, textureH, skewX) {
    const ax = anchor.x;
    const ay = anchor.y;
    const k = skewX || 0;
    const corners = [
        [rect.left, rect.top], [rect.right, rect.top],
        [rect.left, rect.bottom], [rect.right, rect.bottom],
    ];
    let minLX = Infinity, maxLX = -Infinity;
    for (const [u, v] of corners) {
        const lx = u - ax * textureW;
        const ly = v - ay * textureH;
        const lx2 = lx + k * ly;
        if (lx2 < minLX) minLX = lx2;
        if (lx2 > maxLX) maxLX = lx2;
    }
    return { minLX, maxLX };
}

/**
 * 竖直压缩系数。
 *   PixiJS 7.4.3 顶点矩阵 (rotation=0, skew.y=0, 均匀缩放 s):
 *       a = s, b = 0, c = s·sinθ, d = s·cosθ      (θ = skew.x)
 *       screen_x = tx + s·(lx + sinθ·ly)
 *       screen_y = ty + s·cosθ·ly
 *   即: 水平错切因子 k = sinθ; 竖直方向同时被 cosθ 压缩。
 *   ⇒ 缩放/地面线核算必须乘上 cosθ, 否则会有 ~0.4% 的高度误差。
 */
function skewCosFactor(skewX) {
    const k = (typeof skewX === 'number' && Number.isFinite(skewX)) ? skewX : 0;
    const c = Math.sqrt(Math.max(0, 1 - k * k));
    return c;
}

/**
 * 计算覆盖全部帧的**统一**缩放倍率 (无错切的兼容入口)。
 *
 * @param {Array<{left,top,right,bottom,w,h}>} rects 各帧内容矩形 (纹理坐标)
 * @param {number} canvasW 画布宽 (屏幕像素)
 * @param {number} canvasH 画布高 (屏幕像素)
 * @param {number} textureW 纹理宽
 * @param {number} textureH 纹理高
 * @param {number} margin 画布四周留白
 */
function computeUniformScale(rects, canvasW, canvasH, textureW, textureH, margin) {
    return computeUniformScaleWithSkew(
        (rects || []).map((r) => ({ rect: r, skewX: 0 })),
        canvasW, canvasH, textureW, textureH, margin,
    );
}

/**
 * 计算完整布局。
 *
 * @param {object} opts
 * @param {number} opts.canvasW
 * @param {number} opts.canvasH
 * @param {number} opts.textureW
 * @param {number} opts.textureH
 * @param {Array<{action:string,index:number,bbox:number[],skew_x?:number}>} opts.frames
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
    const skewByAction = {};
    const frameSkewByAction = {};
    const scaleEntries = [];
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
        // R147: 方向倾斜 (整体朝向处理) — 水平错切因子, 作用在顶点层, 与 PixiJS 语义一致
        const k = (typeof f.skew_x === 'number') ? f.skew_x : 0;
        skewByAction[f.action] = k;
        frameSkewByAction[f.action] = frameSkewByAction[f.action] || [];
        frameSkewByAction[f.action][f.index] = k;
        scaleEntries.push({ rect: rects[rects.length - 1], skewX: k });
        frameY.push(0);
        frameYByAction[f.action] = frameYByAction[f.action] || [];
    }

    const scale = computeUniformScaleWithSkew(
        scaleEntries, canvasW, canvasH, textureW, textureH, margin,
    );
    const anchor = { x: DEFAULT_ANCHOR.x, y: DEFAULT_ANCHOR.y };
    const groundY = canvasH - margin;   // 地面接触线 (屏幕坐标)
    const x = canvasW / 2;              // 水平参考线落点

    for (let i = 0; i < rects.length; i++) {
        const f = frames[i];
        const r = rects[i];
        const k = (typeof f.skew_x === 'number') ? f.skew_x : 0;
        const cosT = skewCosFactor(k);
        const y = groundY - cosT * (r.bottom - anchor.y * textureH) * scale;
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
        skewByAction,
        frameSkewByAction,
        missingBBox,
        frameCount: frames ? frames.length : 0,
    };
}

/**
 * 把内容矩形 (纹理坐标) 映射到屏幕矩形 — 供测试与 renderer 自检核算裁切。
 * 与 PixiJS 的 sprite 变换完全一致 (anchor 固定, 底边贴 groundY)。
 *
 * R147: skewX 为水平错切因子 (整体方向倾斜)。
 *   PixiJS 7.4.3 顶点语义: 纹理像素 (u,v) → 局部 (u-ax*W, v-ay*H)
 *   → screen_x = pos.x + s*(lx + k*ly)      (k = sin(skew.x))
 *   → screen_y = pos.y + s*cosθ*ly          (cosθ = sqrt(1-k²))
 */
function contentRectToScreen(rect, layout, skewX = 0) {
    const s = layout.scale;
    const ax = layout.anchor.x;
    const ay = layout.anchor.y;
    const W = layout.textureW;
    const H = layout.textureH;
    const k = skewX || 0;
    const cosT = skewCosFactor(k);
    const corners = [
        [rect.left, rect.top], [rect.right, rect.top],
        [rect.left, rect.bottom], [rect.right, rect.bottom],
    ];
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const [u, v] of corners) {
        const lx = u - ax * W;
        const ly = v - ay * H;
        const sx = layout.x + s * (lx + k * ly);
        const sy = layout.groundY + s * cosT * (v - rect.bottom);
        if (sx < minX) minX = sx;
        if (sx > maxX) maxX = sx;
        if (sy < minY) minY = sy;
        if (sy > maxY) maxY = sy;
    }
    return { left: minX, top: minY, right: maxX, bottom: maxY };
}

/**
 * 取出某动作某帧在屏幕上的矩形 (自动带上该帧的方向倾斜)。
 */
function frameScreenRect(layout, action, index) {
    const rect = layout.rectsByAction[action] && layout.rectsByAction[action][index];
    if (!rect) return null;
    const skews = layout.frameSkewByAction && layout.frameSkewByAction[action];
    const k = (skews && typeof skews[index] === 'number') ? skews[index] : 0;
    return contentRectToScreen(rect, layout, k);
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

/**
 * R147: 把水平错切因子 k 换算成 PixiJS 的 skew.x 角度 (弧度)。
 *   PixiJS 7.4.3 (Transform.updateSkew):
 *       _cx = cos(rot+skew.y), _sx = sin(rot+skew.y)
 *       _cy = -sin(rot-skew.x), _sy = cos(rot-skew.x)
 *   rotation=0, skew.y=0, 均匀缩放 s 时:
 *       screen_x = tx + s*(lx + sin(skew.x)*ly)
 *       screen_y = ty + s*cos(skew.x)*ly
 *   ⇒ k = sin(skew.x) ⇒ skew.x = asin(k)
 *   k > 0 → 上半身 (ly<0) 向左偏移 → 向左倾。
 */
function skewAngleX(skewX) {
    const k = (typeof skewX === 'number' && Number.isFinite(skewX)) ? skewX : 0;
    const clamped = Math.max(-1, Math.min(1, k));
    return Math.asin(clamped);
}

module.exports = {
    DEFAULT_MARGIN_PX,
    DEFAULT_ANCHOR,
    toContentRect,
    computeUniformScale,
    computeUniformScaleWithSkew,
    shearedLocalExtent,
    skewCosFactor,
    computeLayout,
    contentRectToScreen,
    frameScreenRect,
    isRectInsideCanvas,
    legacyLayout,
    skewAngleX,
};
