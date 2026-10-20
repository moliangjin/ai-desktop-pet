// R144 测试辅助: 纯 Node PNG 解码器 (无第三方依赖)
// 只支持本项目素材用到的格式: 8bit / RGBA(colortype 6) / 非隔行
// 用于在测试中直接测量**真实 PNG** 的非透明像素范围, 不依赖 PIL/canvas。

'use strict';

const fs = require('fs');
const zlib = require('zlib');

function paeth(a, b, c) {
    const p = a + b - c;
    const pa = Math.abs(p - a);
    const pb = Math.abs(p - b);
    const pc = Math.abs(p - c);
    if (pa <= pb && pa <= pc) return a;
    if (pb <= pc) return b;
    return c;
}

function decodeRGBA(filePath) {
    const buf = fs.readFileSync(filePath);
    if (buf.length < 8 || buf.readUInt32BE(0) !== 0x89504e47) {
        throw new Error(`not a PNG: ${filePath}`);
    }
    let off = 8;
    let ihdr = null;
    const idat = [];
    while (off + 8 <= buf.length) {
        const len = buf.readUInt32BE(off);
        const type = buf.toString('ascii', off + 4, off + 8);
        const data = buf.slice(off + 8, off + 8 + len);
        if (type === 'IHDR') ihdr = data;
        else if (type === 'IDAT') idat.push(data);
        else if (type === 'IEND') break;
        off += 12 + len;
    }
    if (!ihdr) throw new Error(`missing IHDR: ${filePath}`);
    const width = ihdr.readUInt32BE(0);
    const height = ihdr.readUInt32BE(4);
    const bitDepth = ihdr[8];
    const colorType = ihdr[9];
    const interlace = ihdr[12];
    if (bitDepth !== 8 || colorType !== 6 || interlace !== 0) {
        throw new Error(`unsupported PNG format (depth=${bitDepth} colorType=${colorType} interlace=${interlace}): ${filePath}`);
    }
    const raw = zlib.inflateSync(Buffer.concat(idat));
    const bpp = 4;
    const stride = width * bpp;
    const out = Buffer.alloc(height * stride);
    let pos = 0;
    for (let y = 0; y < height; y++) {
        const filter = raw[pos++];
        const line = raw.slice(pos, pos + stride);
        pos += stride;
        const cur = out.slice(y * stride, (y + 1) * stride);
        const prev = y > 0 ? out.slice((y - 1) * stride, y * stride) : null;
        for (let x = 0; x < stride; x++) {
            const a = x >= bpp ? cur[x - bpp] : 0;
            const b = prev ? prev[x] : 0;
            const c = (prev && x >= bpp) ? prev[x - bpp] : 0;
            let v = line[x];
            switch (filter) {
                case 0: break;
                case 1: v = (v + a) & 0xff; break;
                case 2: v = (v + b) & 0xff; break;
                case 3: v = (v + ((a + b) >> 1)) & 0xff; break;
                case 4: v = (v + paeth(a, b, c)) & 0xff; break;
                default: throw new Error(`bad PNG filter ${filter}: ${filePath}`);
            }
            cur[x] = v;
        }
    }
    return { width, height, data: out };
}

/**
 * 测量非透明像素范围 (alpha != 0)。
 * 约定与 PIL Image.getbbox() 一致: [left, top, right, bottom], right/bottom 为开区间。
 */
function alphaBbox(img) {
    let left = img.width;
    let top = img.height;
    let right = -1;
    let bottom = -1;
    const d = img.data;
    for (let y = 0; y < img.height; y++) {
        const row = y * img.width * 4;
        for (let x = 0; x < img.width; x++) {
            if (d[row + x * 4 + 3] !== 0) {
                if (x < left) left = x;
                if (x > right) right = x;
                if (y < top) top = y;
                if (y > bottom) bottom = y;
            }
        }
    }
    if (right < 0) return null;
    return [left, top, right + 1, bottom + 1];
}

module.exports = { decodeRGBA, alphaBbox };
