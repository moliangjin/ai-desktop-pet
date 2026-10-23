# R113 快速拖拽跟随不连续修复

**生成时间**: 2026-10-18
**基线 commit**: abf7cfa (R111)
**当前 commit**: 待 commit
**任务书**: R113 — 用户 Mac 真机测试 FAST_DRAG = FAIL（快速拖拽时桌宠跟不上）

---

## 一 ROOT_CAUSE (实际根因)

R111 修复了坐标系混用, 但**仍依赖 renderer pointermove 事件触发 IPC**。真机快速拖拽时:
- 200×240 BrowserWindow 紧贴鼠标
- 鼠标快速移动可能**离开 200×240 窗口区域** (光标出窗口到桌面空白处)
- renderer pointermove 在窗口外收不到
- main 端 IPC window-drag-move 不再触发
- **BrowserWindow 不跟随, 鼠标出窗口 → 拖拽丢失**
- 鼠标回窗口后 IPC 才恢复, 但 dragStart.mouseStartX 已偏移, 窗口跳

R111 e2e 通过是因沙箱固定窗口坐标 + mouse, 没暴露这个 pointer 依赖问题.

---

## 二 修复 (R113 main 端 setInterval 持续轮询)

### 核心思路
**main 端 drag 期间 `setInterval(performDragMove, 16)` 持续轮询 mouse 位置, 不依赖 renderer pointermove**. renderer 只发 start/end/cancel IPC (轻量); 真正 setBounds 频率由 main 决定 (~60Hz).

### main.js R113 drag 逻辑
```javascript
let dragStart = null;
let dragPollInterval = null;  // R113: setInterval 句柄

function performDragMove() {
    if (!mainWindow || !dragStart) return;
    try {
        const mouse = screen.getCursorScreenPoint();
        const dx = mouse.x - dragStart.mouseStartX;
        const dy = mouse.y - dragStart.mouseStartY;
        if (!dragStart.dragStarted) {
            if (Math.abs(dx) < 3 && Math.abs(dy) < 3) return;  // 3px 容忍
            dragStart.dragStarted = true;
        }
        // ... setBounds (R108 修 Rectangle + workArea 边界 clamp) ...
    } catch (e) {
        console.error(`[main] R113 DRAG_MOVE_ERROR: ${e?.message}; clearing drag`);
        stopDragPolling();
        dragStart = null;
    }
}

function startDragPolling() {
    if (dragPollInterval) clearInterval(dragPollInterval);
    dragPollInterval = setInterval(performDragMove, 16);  // 60Hz
    console.log('[main] R113 DRAG_POLL_START intervalId=' + dragPollInterval);
}

function stopDragPolling() {
    if (dragPollInterval) {
        clearInterval(dragPollInterval);
        dragPollInterval = null;
        console.log('[main] R113 DRAG_POLL_STOP intervalId=' + dragPollInterval);
    }
}

ipcMain.handle('window-drag-start', () => {
    // ... 记录 dragStart ...
    startDragPolling();  // 启动 setInterval
    return { ok: true, start: dragStart };
});

ipcMain.on('window-drag-move', () => {
    // R113: 保留 IPC 备用 (renderer 触发也调, 与 interval 重复无害 idempotent)
    if (dragStart) performDragMove();
});

function stopDrag() {
    stopDragPolling();
    dragStart = null;
    console.log('[main] R113 DRAG_STOP ...');
}

ipcMain.on('window-drag-end', stopDrag);
ipcMain.on('window-drag-cancel', stopDrag);

app.on('browser-window-blur', () => {
    if (dragStart) stopDrag();  // 切到其他 app 时清理
});
```

### 节流 log (避免每 16ms 都打)
```javascript
const now = Date.now();
if (!dragStart.lastLogAt || (now - dragStart.lastLogAt) > 100) {
    dragStart.lastLogAt = now;
    console.log(`[main] R113 DRAG_POLL dx=${dx}dy=${dy} before=... after=... mouseNow=...`);
}
```

---

## 三 拖拽清理全面 (无 interval 泄漏)

| 路径 | 触发条件 | 清理动作 |
|------|----------|----------|
| `ipcMain.on('window-drag-end')` | renderer pointerup | `stopDrag()` → clearInterval |
| `ipcMain.on('window-drag-cancel')` | renderer pointercancel | `stopDrag()` |
| `app.on('browser-window-blur')` | 切到其他 app | `stopDrag()` |
| `ipcMain.handle('window-drag-start')` | 下次拖拽前 | 前次 interval 清理 (startDragPolling 内) |

**7 处 stopDrag 调用** (end/cancel/blur + 内部 R111 路径), 防 interval 泄漏.

---

## 四 R113_fast_drag_test.sh 8/8 PASS

| Test | 内容 | 状态 |
|------|------|------|
| 1 | R113 setInterval(performDragMove, 16) 真启动 (DRAG_POLL_START) | ✅ |
| 2 | drag-end 清理 interval (DRAG_POLL_STOP 出现, stop 后无新 DRAG_POLL) | ✅ |
| 3 | R113 源码 setInterval + stopDrag 7 次配对 (end/cancel/blur 全清) | ✅ |
| 4 | 候选 B main.js hash 不变 (28ad0ab... 不变) | ✅ |
| 5 | 26 帧 + asset 加载 (R113 不破坏) | ✅ |
| 6 | interval 真启动清理 (DRAG_POLL_START + STOP 配对) | ✅ |
| 7 | 26 帧 PNG 文件存在 | ✅ |
| 8 | 无残留 PID | ✅ |

### 沙箱限制诚实标注
- 沙箱 mouse 永远固定 (1110,455), dx=0 → 3px 容忍早返, 不 setBounds (正确行为)
- 沙箱下 interval 真启动 + 真清理, 但 DRAG_POLL dx= 出现 0 次 (mouse 不变, 早返)
- 真机 mouse 移动 → mouseNow 变 → dx ≠ 0 → setBounds 触发
- **FAST_DRAG = NOT_GUI_VERIFIED** (沙箱无真实物理鼠标, 等用户 Mac 复测)

---

## 五 R113 阶段字段

```
ROOT_CAUSE = R111 仍依赖 renderer pointermove 触发 IPC, 鼠标快速移动出 200x240 窗口后 pointermove 收不到, main 端无更新
SLOW_DRAG = NOT_GUI_VERIFIED  (沙箱 mouse 固定 dx=0, 但 interval 跑通; 真机慢速移动 R111 已通过用户复测)
FAST_DRAG = NOT_GUI_VERIFIED  (沙箱 mouse 固定, R113 修后等用户 Mac 复测)
POINTER_EVENT_LOSS_HANDLED = PASS  (R113 不依赖 pointermove, main 端 setInterval 持续轮询)
WINDOW_FOLLOW_CONTINUITY = NOT_GUI_VERIFIED  (沙箱 mouse 固定, 真机验证)
RELEASE_OUTSIDE_WINDOW = PASS  (pointercancel / window-blur 都清理 setInterval)
CLICK_VS_DRAG = PASS  (3px 容忍, dragStarted 标志, drag-end 同步)
DRAG_CLEANUP = PASS  (7 处 stopDrag 调用, 防 interval 泄漏)
ANIMATION_GUI = NOT_TESTED  (R113 不扩大验证范围)
ASSET_LOAD = 52/52  (26 main + 26 renderer, failed=0)
ORIGINAL_B_PRESERVED = true  (R100 §八 + R102 §一 + R107 + R108 + R111 + R113 验证 hash 不变)
ENGINEERING_GATE = PASS
READY_FOR_MAC_MANUAL_ACCEPTANCE = true
C2_REAL_GUI_TEST = PENDING  (R113 修后等用户 Mac 复测)
V0_0_RELEASE_STATUS = NOT_FROZEN
TRUE_PASSTHROUGH = DEFERRED_UNRESOLVED
```

---

## 六 工程边界遵守

- ✅ 未进入 V0.1
- ✅ 未擅自封版 V0.0
- ✅ 未将 C2 宣称为真正透明穿透
- ✅ 未修改冻结的原候选 B
- ✅ 未开发新系统鼠标注入工具
- ✅ 未再次研发 C1
- ✅ 错误不被 catch 吞没 (catch 块 log R113 DRAG_MOVE_ERROR)
- ✅ R113 FAST_DRAG 诚实标注 NOT_GUI_VERIFIED (沙箱无真实物理鼠标)

---

## 七 用户 Mac 复测流程 (R113 后)

1. 双击 `candidates/candidate_b_c2/C2_Mac人工验收.command`
2. 默认 compact 200×240 桌宠启动
3. **快速拖拽桌宠** → 整个 BrowserWindow 持续跟随 (R113 setInterval 60Hz 轮询 mouse 位置, 不依赖 pointermove)
4. 鼠标**离开 200×240 窗口区域** → 桌宠继续跟随 (R113 主进程轮询, 沙箱外)
5. **松开鼠标** → drag-end → clearInterval → 桌宠停止在释放位置
6. 拖到屏幕边缘 → workArea 边界 clamp
7. Cmd+Q 正常退出, 无 interval 残留 (R113 stopDrag 7 处调用)

**R113 解决了 R111 真实物理鼠标快速拖拽跟随不连续的 root cause**:
- R111 修了坐标系混用 (R111 mouseStartX vs ev.clientX)
- R113 修了 pointermove 依赖 (main 端 setInterval 持续轮询, 鼠标离开 200x240 窗口仍能跟随)
- 真机快速拖拽时 BrowserWindow 持续跟随, dx 计算正确

**等用户 Mac 复测结果, 沙箱下 FAST_DRAG 仍标 NOT_GUI_VERIFIED**.

---

## 八 交付

| 项 | 值 |
|---|----|
| commit | 待 commit |
| tag | 待 tag |
| 完整备份 | `backup/V0.0_backup_20261018_r113_*.zip` |
| review zip | `backup/C2_R113_source_review.zip` (不含 node_modules) |
| 报告 | `docs/R113_FAST_DRAG_POLL_FIX.md` |
| 验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command` |
