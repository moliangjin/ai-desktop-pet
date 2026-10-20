#!/usr/bin/env node
// R144 布局探针 — 供 08_R144_layout_builder.py 调用
// 输入: stdin JSON {frames, canvasW, canvasH, textureW, textureH, margin}
// 输出: stdout JSON (生产布局模块 src/sprite_layout.js 的计算结果)
//
// 这里只做"进程边界适配", 布局算法全部来自生产模块, 不做任何二次实现。

'use strict';

const path = require('path');
const { computeLayout, contentRectToScreen, isRectInsideCanvas } = require(
    path.join(__dirname, '..', 'src', 'sprite_layout.js')
);

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
    const input = JSON.parse(raw);
    const layout = computeLayout(input);
    const screenRects = [];
    for (let i = 0; i < input.frames.length; i++) {
        const f = input.frames[i];
        const rect = layout.rects[i];
        const scr = contentRectToScreen(rect, layout);
        screenRects.push({
            action: f.action,
            index: f.index,
            screen_rect: scr,
            inside: isRectInsideCanvas(scr, layout),
        });
    }
    process.stdout.write(JSON.stringify({ ...layout, screenRects }));
});
