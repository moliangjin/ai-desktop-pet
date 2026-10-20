// R144 资源就绪握手判定 (纯逻辑模块, 无 Electron 依赖)
//
// 背景 (R144 P0-3):
//   R141 的 main 在 did-finish-load 立刻启动 BehaviorEngine, 而 renderer 还在
//   异步加载 23 张 PNG —— 状态机可能在资源就绪前就要求切动作, 导致丢帧/空动作。
//
// 协议 (R144):
//   renderer 加载完 6 组共 23 帧并确认可播放后 → ipcRenderer.send('assets-ready', report)
//   main 收到 report 且通过本模块判定 → 才启动 BehaviorEngine
//   任一必要动作缺帧 → 明确报错, 拒绝启动 (拒绝虚假 PASS)
//
// main.js 与 tests/r144_assets_gate.test.js 调用同一份代码。

'use strict';

// 自主行为引擎运行所必需的动作 (与 behavior_engine.js 的 STATE_ACTION 对应)
const REQUIRED_ACTIONS = Object.freeze([
    'idle', 'walk_left', 'walk_right', 'sleep_enter', 'sleep_loop', 'wake_up',
]);

/**
 * 判定 renderer 上报的资产状态是否可以启动自主行为。
 *
 * @param {object} report renderer 上报的 { ok, total, loaded, failed, actions: {name:{loaded,failed,total}} }
 * @param {string[]} [requiredActions]
 * @returns {{ok:boolean, errors:string[], loaded:number, total:number, required:string[]}}
 */
function evaluateAssetReadiness(report, requiredActions) {
    const required = requiredActions || REQUIRED_ACTIONS;
    const errors = [];
    const actions = (report && report.actions) || {};

    for (const name of required) {
        const info = actions[name];
        if (!info) {
            errors.push(`必要动作 ${name} 未出现在资源报告中`);
            continue;
        }
        if (!(info.loaded > 0)) {
            errors.push(`必要动作 ${name} 没有任何可用帧 (loaded=${info.loaded})`);
        }
        if (info.failed > 0) {
            errors.push(`必要动作 ${name} 有 ${info.failed} 帧加载失败`);
        }
        const expect = info.total;
        if (typeof expect === 'number' && info.loaded !== expect) {
            errors.push(`必要动作 ${name} 帧数不完整 (loaded=${info.loaded}/${expect})`);
        }
    }

    const total = (report && typeof report.total === 'number') ? report.total : 0;
    const loaded = (report && typeof report.loaded === 'number') ? report.loaded : 0;
    if (total <= 0) {
        errors.push('资源总数为 0');
    } else if (loaded !== total) {
        errors.push(`总帧数不完整 (loaded=${loaded}/${total})`);
    }
    if (report && report.failed > 0) {
        errors.push(`共有 ${report.failed} 帧加载失败`);
    }

    return { ok: errors.length === 0, errors, loaded, total, required: required.slice() };
}

/**
 * 汇总 renderer 上报的每动作帧数 (供 main 打印与判定)。
 */
function summarizeReport(report) {
    const actions = (report && report.actions) || {};
    const out = {};
    for (const name of Object.keys(actions)) {
        const a = actions[name];
        out[name] = { loaded: a.loaded, failed: a.failed, total: a.total };
    }
    return out;
}

module.exports = { REQUIRED_ACTIONS, evaluateAssetReadiness, summarizeReport };
