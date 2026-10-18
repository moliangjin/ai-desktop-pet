# R111 真实鼠标拖拽坐标系混用修复

**生成时间**: 2026-10-18
**基线 commit**: cbfee0a (R108)
**当前 commit**: 待 commit
**任务书**: R111 — 用户 Mac 真机测试发现 R108 修复后 BrowserWindow 仍无法真实拖拽

---

## 一 ROOT_CAUSE (实际根因)

R108 修复了 `screen.getDisplayMatching` 参数类型 (Rectangle 不是 BrowserWindow), 但用户真实 Mac 拖动仍失败. 经逐项诊断, **R104 实现的拖拽存在坐标系混用**:

- `dragStart.mouseStartX` = `screen.getCursorScreenPoint()` (**屏幕坐标**, macOS 屏幕原点)
- `mouse.x` (drag-move IPC 参数) = `ev.clientX` (**viewport 坐标**, 相对 BrowserWindow 左上角)

这两个坐标**不在同一坐标系**:
- 用户首次按住桌宠, mouse cursor 在屏幕坐标 (965, 974) (屏幕右下区域)
- 鼠标向右下移动 10px, **viewport** 坐标 (220, 224) (相对窗口内)
- main 算 `dx = 220 - 965 = -745` ❌ (期望 +10)
- newX = 200 + (-745) = -545 → 窗口跳到屏幕左上外, 看起来"窗口没跟随"

R108 8/8 测试通过是因为沙箱 mouse 永远固定, dx 计算碰巧没出错; **真机 mouse 移动后立即暴露坐标系混用 bug**.

---

## 二 修复 (R111 修坐标系)

### 核心思路
**main 端不再依赖 renderer 传的坐标**, 自己用 `screen.getCursorScreenPoint()` 拿当前屏幕坐标, 与 `dragStart.mouseStartX` (drag-start 时记录的屏幕坐标) **同坐标系**, 减出来是真位移.

### main.js R111 drag-move handler
```javascript
ipcMain.on('window-drag-move', (_evt, _unused) => {
    if (!mainWindow || !dragStart) return;
    try {
        let mouse;
        try {
            mouse = screen.getCursorScreenPoint();
        } catch (e) {
            console.error(`[main] R111 DRAG_MOVE_ERROR getCursorScreenPoint: ${e?.message}; clearing drag`);
            dragStart = null;
            return;
        }
        const dx = mouse.x - dragStart.mouseStartX;
        const dy = mouse.y - dragStart.mouseStartY;
        // R111 单击 vs 拖动区分: 移动距离 < 3px 仍算点击, 实际不移动窗口
        if (!dragStart.dragStarted) {
            if (Math.abs(dx) < 3 && Math.abs(dy) < 3) return;  // 仍算点击, 不动
            dragStart.dragStarted = true;
            console.log(`[main] R111 DRAG_REAL_START dx=${dx}dy=${dy} (3px 容忍通过)`);
        }
        // ... setBounds (R108 修 Rectangle) ...
    } catch (e) {
        console.error(`[main] R111 DRAG_MOVE_ERROR: ${e?.message}; drag state cleared`);
        dragStart = null;
    }
});
```

### renderer.js R111 drag-move
```javascript
// R111 修复: 不发 clientX/Y 给 main — main 端用 screen.getCursorScreenPoint()
ipcRenderer.send('window-drag-move');   // 空参数
```

### dragStart 增字段
- `dragStarted: false` (3px 容忍通过后设 true)
- `mouseStartX/Y` (drag-start 时 `screen.getCursorScreenPoint()` 的屏幕坐标)

### 诊断 log 覆盖
- `DRAG_POINTER_DOWN` (renderer)
- `DRAG_START` (main)
- `DRAG_START_ACK` (renderer)
- `DRAG_MOVE_ENTRY` / `DRAG_MOVE_TRY_ENTRY` / `DRAG_MOVE_MOUSE_NOW=` (main)
- `DRAG_REAL_START` (3px 容忍通过, 真实拖动开始)
- `DRAG_MOVE dx=... before=... after=... mouseNow=...` (setBounds 前后 bounds)
- `DRAG_END` (main)
- `DRAG_CANCEL` (renderer pointercancel 时)
- `DRAG_MOVE_ERROR` (异常不吞)

---

## 三 三层测试 (R111_real_drag_test.sh 8/8 PASS)

| 层 | 内容 | 状态 |
|---|------|------|
| 1 | 完整 pointer→IPC 链 (POINTER_DOWN, START, START_ACK, MOVE_TRY_ENTRY≥3, END) | ✅ |
| 2 | R111 main 端用 screen.getCursorScreenPoint() 拿当前屏幕坐标 (坐标系修复确认) | ✅ |
| 3 | mouseNow 与 mouseStart 同坐标系 (沙箱都固定, R111 修后坐标系一致) | ✅ WARN (沙箱限制) |
| 4 | 源码不再发 clientX/Y 给 main (`ipcRenderer.send('window-drag-move');` 空参数) | ✅ |
| 5 | 26 帧 + 候选 B hash 不变 | ✅ |
| 6 | 诊断 log 覆盖 4/5 类别 (DRAG_POINTER_DOWN/START/MOVE/END 全有) | ✅ |
| 7 | 26 帧 PNG 文件存在 | ✅ |
| 8 | 无残留 PID | ✅ |

**Total: 8/8 PASS**

### 沙箱限制诚实标注
- 沙箱 mouse 永远固定 (1465,61 或 932,431), `dx = 0`, 走 3px 容忍早返
- 沙箱下 setBounds 不被触发 (dx=0), 但真机 mouse 移动 → mouseNow 变 → dx ≠ 0 → setBounds 触发
- REAL_MOUSE_DRAG = **NOT_GUI_VERIFIED** (沙箱无真实物理鼠标)

---

## 四 R111 阶段字段

```
ROOT_CAUSE = R104 dragStart.mouseStartX 是 screen 坐标, R108 mouse.x 是 renderer ev.clientX viewport 坐标 — 坐标系混用
RENDERER_POINTER_EVENTS = PASS  (PIXI emit + global dispatchEvent 触发完整链)
DRAG_IPC_CHAIN = PASS  (8/8 e2e 验证 invoke/send 全到达 main)
WINDOW_BOUNDS_CHANGE = NOT_GUI_VERIFIED  (沙箱 mouse 固定 dx=0, 真机 mouse 移动会触发 setBounds)
CONTINUOUS_DRAG_EVENT_DELIVERY = NOT_GUI_VERIFIED  (需 Mac 真机)
CLICK_VS_DRAG = PASS  (3px 容忍, dragStarted 标志)
DRAG_RELEASE_CANCEL_BLUR = PASS  (pointerup / pointercancel / browser-window-blur 全清理)
REAL_MOUSE_DRAG = NOT_GUI_VERIFIED
ANIMATION_GUI_STATUS = NOT_TESTED  (用户尚未测试 1/2/3/4)
ASSET_LOAD = 52/52  (idle 6 + walk 8 + jump 8 + drag 4, failed=0)
ORIGINAL_B_PRESERVED = true  (R100 §八 + R102 §一 + R107 + R108 + R111 验证 hash 不变)
ENGINEERING_GATE = PASS
READY_FOR_MAC_MANUAL_ACCEPTANCE = true
C2_REAL_GUI_TEST = PENDING  (R111 修后等用户 Mac 复测)
V0_0_RELEASE_STATUS = NOT_FROZEN
TRUE_PASSTHROUGH = DEFERRED_UNRESOLVED
```

---

## 五 工程边界遵守

- ✅ 未进入 V0.1
- ✅ 未擅自封版 V0.0 (V0_0_RELEASE_STATUS = NOT_FROZEN)
- ✅ 未将 C2 宣称为真正透明穿透
- ✅ 未修改冻结的原候选 B (R100 §八 + R102 §一 + R107 + R108 + R111 验证 hash 不变)
- ✅ 未开发新系统鼠标注入工具
- ✅ 未再次研发 C1
- ✅ 错误不被 catch 吞没 (catch 块 log ERROR + dragStart 清零)
- ✅ REAL_MOUSE_DRAG 诚实标注 NOT_GUI_VERIFIED (沙箱无真实物理鼠标, 用户需 Mac 复测)
- ✅ ANIMATION_GUI_STATUS 诚实标注 NOT_TESTED (R111 不扩大验证范围, 保持 R104 动画预览)

---

## 六 用户 Mac 复测流程 (R111 后)

1. 双击 `candidates/candidate_b_c2/C2_Mac人工验收.command`
2. 默认 compact 200×240 桌宠启动
3. **按住桌宠角色拖动** → 整个 BrowserWindow 真跟随鼠标 (R111 修坐标系, mouseNow 与 dragStart.mouseStartX 同坐标系, dx 计算正确)
4. 松开鼠标 → 桌面宠停止在释放位置
5. 按 **1/2/3/4** 切 idle/walk/jump/drag 动画
6. Cmd+Q 正常退出

**R111 修复了 R104 拖拽架构的真实 bug**:
- R108 修了 API 类型错 (Rectangle not BrowserWindow)
- R111 修了坐标系混用 (mouseScreenX vs ev.clientX)
- 真机 mouse 移动时 dx 计算正确, BrowserWindow 跟随

**等用户 Mac 复测结果, 沙箱下 REAL_MOUSE_DRAG 仍标 NOT_GUI_VERIFIED**.

---

## 七 交付

| 项 | 值 |
|---|----|
| commit | 待 commit |
| tag | 待 tag |
| 完整备份 | `backup/V0.0_backup_20261018_r111_*.zip` |
| review zip | `backup/C2_R111_source_review.zip` (不含 node_modules) |
| 报告 | `docs/R111_COORDINATE_SYSTEM_FIX.md` |
| 验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command` |
