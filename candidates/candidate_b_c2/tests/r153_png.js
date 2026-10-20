// R153 共享测试助手: PNG 像素解码 + 像素级姿态测量
//
// 为什么需要它 (R153 用户反馈):
//   "行走时身体明显前倾, 像要摔倒"
// 方向/姿态的判定**不能**靠 x 坐标正负、动画名或测试脚本自身的 PASS。
// 必须对**真实像素**做几何测量。
//
// 本模块提供:
//   · decodePNG(file)        : 解码 8bit RGBA PNG (Node 无内置解码, 用 zlib 自行实现)
//   · alphaMask(file)        : 取 alpha 通道掩膜
//   · measureLean(mask)      : 像素级测量"上半身重心相对下半身重心的水平偏移 / 身高"
//
// measureLean 的物理含义:
//   身体偏离垂直轴的程度。绝对值越大 = 越"歪" = 观感越像要摔倒。
//   水平镜像会把该值整体取反 ⇒ 左右两组步态的符号必然相反 (可用于交叉校验)

'use strict';

const fs = require('fs');
const zlib = require('zlib');

/** 解码 8bit RGBA PNG → { width, height, data } */
function decodePNG(file) {
    const buf = fs.readFileSync(file);
    let pos = 8;
    let width = 0, height = 0, bitDepth = 0, colorType = 0;
    const idat = [];
    while (pos < buf.length) {
        const len = buf.readUInt32BE(pos);
        const type = buf.toString('ascii', pos + 4, pos + 8);
        const data = buf.slice(pos + 8, pos + 8 + len);
        if (type === 'IHDR') {
            width = data.readUInt32BE(0);
            height = data.readUInt32BE(4);
            bitDepth = data[8];
            colorType = data[9];
        } else if (type === 'IDAT') {
            idat.push(data);
        } else if (type === 'IEND') {
            break;
        }
        pos += 12 + len;
    }
    if (bitDepth !== 8) throw new Error('仅支持 8bit PNG');
    if (colorType !== 6) throw new Error('仅支持 RGBA (colorType=6)');
    const raw = zlib.inflateSync(Buffer.concat(idat));
    const bpp = 4;
    const stride = width * bpp;
    const out = Buffer.alloc(height * stride);
    let rp = 0;
    for (let y = 0; y < height; y++) {
        const filter = raw[rp++];
        const line = raw.slice(rp, rp + stride);
        rp += stride;
        const cur = out.slice(y * stride, (y + 1) * stride);
        const prev = y > 0 ? out.slice((y - 1) * stride, y * stride) : Buffer.alloc(stride);
        for (let i = 0; i < stride; i++) {
            const a = i >= bpp ? cur[i - bpp] : 0;
            const b = prev[i];
            const c = i >= bpp ? prev[i - bpp] : 0;
            let v = line[i];
            switch (filter) {
                case 0: break;
                case 1: v = (v + a) & 0xff; break;
                case 2: v = (v + b) & 0xff; break;
                case 3: v = (v + ((a + b) >> 1)) & 0xff; break;
                case 4: {
                    const p = a + b - c;
                    const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
                    const pr = (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
                    v = (v + pr) & 0xff;
                    break;
                }
                default: throw new Error(`未知 filter ${filter}`);
            }
            cur[i] = v;
        }
    }
    return { width, height, data: out };
}

/** 取 PNG 的 alpha 掩膜 → { width, height, mask: Uint8Array(0|1) } */
function alphaMask(file, threshold = 24) {
    const png = decodePNG(file);
    const mask = new Uint8Array(png.width * png.height);
    for (let i = 0; i < mask.length; i++) {
        mask[i] = png.data[i * 4 + 3] > threshold ? 1 : 0;
    }
    return { width: png.width, height: png.height, mask };
}

/**
 * 像素级测量"上半身重心相对下半身重心的水平偏移 / 身高"。
 * 上半身带 = 剪影竖直范围顶部 30%; 下半身带 = 底部 30%。
 * @returns {{height:number, upperCx:number, lowerCx:number, leanPx:number, leanRatio:number}}
 */
function measureLean(alpha) {
    const { width, height, mask } = alpha;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    let n = 0;
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            if (mask[y * width + x]) {
                n++;
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
            }
        }
    }
    if (!n) throw new Error('空剪影');
    const bodyH = maxY - minY;
    if (bodyH <= 0) throw new Error('剪影高度为 0');

    const bandCentroid = (y0, y1) => {
        let sx = 0, c = 0;
        for (let y = y0; y < y1; y++) {
            if (y < 0 || y >= height) continue;
            for (let x = 0; x < width; x++) {
                if (mask[y * width + x]) { sx += x; c++; }
            }
        }
        return c < 8 ? null : sx / c;
    };
    const upper = bandCentroid(minY, Math.round(minY + bodyH * 0.30));
    const lower = bandCentroid(Math.round(maxY - bodyH * 0.30), maxY + 1);
    if (upper === null || lower === null) throw new Error('分带重心计算失败');
    const leanPx = upper - lower;
    return {
        height: bodyH,
        upperCx: upper,
        lowerCx: lower,
        leanPx,
        leanRatio: leanPx / bodyH,
    };
}

/** 对一组帧路径逐帧测量, 返回聚合结果 */
function measureGroup(files, root) {
    const rows = [];
    for (const rel of files) {
        const m = measureLean(alphaMask(require('path').join(root, rel)));
        m.file = rel;
        rows.push(m);
    }
    const ratios = rows.map(r => r.leanRatio);
    const mean = ratios.reduce((a, b) => a + b, 0) / ratios.length;
    return {
        rows,
        meanRatio: mean,
        maxAbsRatio: Math.max(...ratios.map(Math.abs)),
        signs: rows.map(r => Math.sign(r.leanRatio)),
    };
}

module.exports = { decodePNG, alphaMask, measureLean, measureGroup };
