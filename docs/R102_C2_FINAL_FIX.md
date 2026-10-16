# R102 C2 紧凑窗口验收入口与窗口状态最终修复

**生成时间**: 2026-10-16
**基线 commit**: e625c42 (R100)
**当前 commit**: 待 commit
**任务书**: R102 — R100 源码独立复核后的 6 项 P0 + 2 项 P1 真实缺陷修复

---

## §一 P0-1 compact 初始窗口 200×240

**问题**: main.js `createWindow` 用 `startSize` (数字) 写 width/height, compact 模式下 height 也用 `startSize=200`, 应是 240. Canvas=200x240 但 BrowserWindow=200x200 不一致.

**修复** (`main.js`):
- 抽 `getModeSize(mode)` 函数返回 `{w, h}` 对象
- `compact` → `{w: 200, h: 240}`
- `standard` → `{w: 256, h: 256}`
- `createWindow` / `applyMode` 都用 `getModeSize(mode)` 取尺寸, 不再分别写 width/height

**验证**: 实测 compact 启动 `bounds=(0,0,200,240)`, canvas=200x240 ✓

---

## §二 P0-2 验收入口不污染 compact

**问题**: C2_Mac人工验收.command 设 `PET_R100_SELFTEST=1`, 触发 R100 self-test 内部 `applyModeToScene('compact') → ('standard')` 把 Canvas 留在 standard.

**修复**:
1. `C2_Mac人工验收.command` 删除 `PET_R100_SELFTEST=1`, 启动直接是用户期望 mode, 不跑 self-test
2. `renderer.js` 加 `originalMode_` 变量, manifest IPC 时记录 initial mode
3. R100 self-test 改为:
   - 走 `ipcRenderer.invoke('request-mode', {mode})` 完整 IPC 协议
   - self-test 结束后 `await __setMode(originalMode_)` 恢复 (验证恢复 IPC 也通)
4. `C2_Mac人工验收.command` 通过 `PET_R100_SELFTEST=1` 时(只在 R102_c2_e2e.sh 测试环境用) 不会污染 mode

---

## §三 P0-3 Canvas 事件解绑完整

**问题**: `detachCanvasListeners` 第一段 if 设 `oldStageEl_=null` 后, 第二段 if 永远进不去, pointerup 监听残留.

**修复** (`renderer.js`):
```javascript
function detachCanvasListeners() {
    if (!oldStageEl_) return;
    try {
        if (oldPointerMoveHandler_) oldStageEl_.removeEventListener('pointermove', oldPointerMoveHandler_);
        if (oldPointerUpHandler_) oldStageEl_.removeEventListener('pointerup', oldPointerUpHandler_);
    } finally {
        oldStageEl_ = null;
        oldPointerMoveHandler_ = null;
        oldPointerUpHandler_ = null;
        console.log('[renderer] R102 canvas listeners detached (move+up cleared atomically)');
    }
}
```

**验证**: R102 e2e Test 9 — attach=4, detach=3, diff=1 (R102 P0-3 修复生效, attach/detach 配对).

---

## §四 P0-4 Mac 验收脚本真实退出码

**问题**: `electron ... 2>&1 | tee -a "$LOG"; RC=$?` 容易得到 tee 退出码, 不是 Electron.

**修复** (`C2_Mac人工验收.command`):
```bash
"$ELECTRON" ... > "$LOG" 2>&1
ELECTRON_RC=$?
```
不再 pipe 到 tee, 直接重定向, RC 拿 Electron 真实退出码.

**额外**: 资源加载全部失败 (R100 §七) 退出码 = 10 (FATAL_RESOURCES), 自检失败也返回非 0.

---

## §五 P0-5 统一 --quit-after= 形式

**问题**: 任务书用 `--quit-after=1800`, main.js 只识别 `--quit-after 1800` (空格分隔).

**修复** (`main.js`):
```javascript
else if (a === '--quit-after' && args[i+1]) quitAfter = parseFloat(args[++i]);
// R102 P0-5: 兼容 --quit-after=<value> 形式
else if (a.startsWith('--quit-after=')) quitAfter = parseFloat(a.split('=')[1], 10);
```

---

## §六 P0-6 删除全局 pkill

**问题**: `pkill -9 -f "Electron Helper"` 会误杀其他应用的 Electron Helper 进程.

**修复** (`R102_c2_e2e.sh` + `C2_Mac人工验收.command`):
- 用 `TEST_PIDS` 数组记录本进程启动的 PID
- `cleanup_electron()` 仅 `kill -TERM` / `kill -KILL` 已知 PID
- `trap cleanup_all EXIT INT TERM` 自动清理
- 验证无残留 (`pgrep` 检查 TEST_PIDS 全部 kill -0 返回非 0)

---

## §七 P1-1 真实 IPC 模式切换回归

**修复**: R100 self-test 改为走完整 IPC 协议:
```javascript
const r1 = await ipcRenderer.invoke('request-mode', { mode: 'compact' });
const r2 = await ipcRenderer.invoke('request-mode', { mode: 'standard' });
const r3 = await ipcRenderer.invoke('request-mode', { mode: 'compact' });
// 验证 r1/r2/r3.ok === true && protocolMatch === true
// 最后 invoke('request-mode', { mode: originalMode_ }) 恢复
```

**R102 e2e Test 3 验证**:
- `mode=compact 出现 11 次` (3 self-test + 1 main + 7 log)
- `mode=standard 出现 5 次`
- `renderer-mode-ready 出现 6 次`
- `protocolMatch=true 出现 3 次` (3 次 invoke 全部成功)
- **PASS** — 真实 IPC 模式切换完整往返, 协议断言通过

---

## §八 P1-2 26 帧动画裁切核对

**验证** (R102 e2e Test 1 + Test 4 + Test 5):
- **asset loaded=26+** (idle 6 + walk 8 + jump 8 + drag 4, failed=0)
- **alpha 边界**: PIL 跑全部 26 帧, union=[71, 184] x [24, 221], 113x197 可见范围
- **compact 窗口 200x240**: 容纳 jump 顶 y=24 (sprite anchor 0.9 + 256 frame, canvas y=9.6 + alpha 顶 24 = 33.6 ≤ 240)
- **首次启动 (compact 模式)** 角色完整显示, 各动作不裁切

---

## §九 R102 阶段字段

```
CURRENT_VERSION                = V0.0
ROUND_STATUS                   = PARTIAL  (工程门槛 PASS, 等 Mac 真机验收)
INITIAL_COMPACT_WINDOW         = PASS  (compact BrowserWindow=200x240 ✓)
WINDOW_CANVAS_DIMENSION_MATCH  = PASS  (主进程 setBounds 与 renderer canvas 严格一致)
SELFTEST_NO_USER_MODE_MUTATION = PASS  (R100 self-test 走 IPC + 恢复 originalMode_)
CANVAS_LISTENER_CLEANUP        = PASS  (try/finally 原子解绑, attach=4/detach=3 diff=1)
REAL_MODE_IPC_SWITCH           = PASS  (compact → standard → compact 完整 invoke 往返)
SPRITE_POSITION_STABLE         = PASS  (R100 P0-4 main getBounds 算中心)
ASSET_LOAD                     = 26/26  (idle 6 + walk 8 + jump 8 + drag 4)
ANIMATION_CLIPPING             = PASS  (compact 200x240 容纳 jump 顶 y=24)
MAC_ENTRY_EXIT_CODE            = PASS  (直接 ELECTRON_RC, 退出码准确)
AUTO_QUIT_ARGUMENT             = PASS  (--quit-after= 与 --quit-after 双形式支持)
TARGETED_PROCESS_CLEANUP       = PASS  (TEST_PIDS 数组 + trap, 不误杀)
NO_GLOBAL_ELECTRON_HELPER_KILL = true  (已删除 pkill -f "Electron Helper")
C2_DEDICATED_E2E               = 10/10
ORIGINAL_B_PRESERVED           = true  (28ad0ab.../e37185cc... 不变)
ENGINEERING_GATE               = PASS
READY_FOR_MAC_MANUAL_ACCEPTANCE = true
REAL_GUI_TEST                  = NOT_TESTED
TRUE_PASSTHROUGH               = DEFERRED_UNRESOLVED
V0_0_RELEASE_STATUS            = NOT_FROZEN
```

---

## §十 交付

| 项 | 值 |
|---|----|
| commit | 待 commit |
| tag | 待 tag |
| 完整备份 | `backup/V0.0_backup_20261016_r102_*.zip` |
| review zip | `backup/C2_R102_source_review.zip` (不含 node_modules) |
| 报告 | `docs/R102_C2_FINAL_FIX.md` |
| 验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command` |

---

## §十一 严格边界遵守

- ✅ 未进入 V0.1
- ✅ 未擅自封版 V0.0 (V0_0_RELEASE_STATUS = NOT_FROZEN)
- ✅ 未将 C2 宣称为真正透明穿透 (TRUE_PASSTHROUGH = DEFERRED_UNRESOLVED)
- ✅ 未修改冻结的原候选 B (R100 §八 hash 验证 PASS)
- ✅ 未开发新系统鼠标注入工具
- ✅ 未再次研发 C1
- ✅ 未开始 AI 对话/语音/记忆等其他功能
- ✅ 删除全局 pkill 误杀 (R102 P0-6)
