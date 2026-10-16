# R104 C2 真正窗口拖拽 + 动画预览 + 交互回归

**生成时间**: 2026-10-16
**基线 commit**: 8e42073 (R102)
**当前 commit**: 待 commit
**任务书**: R104 — C2 真机验收前最后一轮交互收尾

---

## §一 P0-1 真正 BrowserWindow 拖拽

**问题**: R60/R100/R102 的拖拽只修改 `sprite_.x / sprite_.y` (sprite 在 canvas 内移动), 整个 Electron BrowserWindow 不动 — 不是用户期望的"拖动桌宠窗口"。

**修复方案** (R104):
- renderer.js 拖拽时发 IPC 给 main, main 调 `BrowserWindow.setBounds({x, y, ...})` 移动整个窗口
- sprite 固定在 canvas 中心, 不再被 drag 修改 (整个 BrowserWindow 移动, sprite 相对窗口位置不变)
- 使用 Electron 原生 `BrowserWindow.setBounds` (不需要 AX/Screen Recording, 不调用 CGEventPost)

**main.js**:
```javascript
let dragStart = null;
ipcMain.handle('window-drag-start', () => {
    const bounds = mainWindow.getBounds();
    const mouse = screen.getCursorScreenPoint();
    dragStart = { winX: bounds.x, winY: bounds.y, mouseScreenX: mouse.x, mouseScreenY: mouse.y, ... };
    return { ok: true, start: dragStart };
});
ipcMain.on('window-drag-move', (_e, mouse) => {
    const dx = mouse.x - dragStart.mouseScreenX;
    const dy = mouse.y - dragStart.mouseScreenY;
    // 限定在当前 display 工作区, 避免拖出屏幕
    const display = screen.getDisplayMatching(bounds);
    const wa = display.workArea;
    const clampedX = Math.max(wa.x, Math.min(dragStart.winX + dx, wa.x + wa.width - dragStart.width));
    const clampedY = Math.max(wa.y, Math.min(dragStart.winY + dy, wa.y + wa.height - dragStart.height));
    mainWindow.setBounds({ x: clampedX, y: clampedY, width: dragStart.width, height: dragStart.height });
});
ipcMain.on('window-drag-end', () => { dragStart = null; });
app.on('browser-window-blur', () => { if (dragStart) dragStart = null; });
```

**renderer.js** (bindSpriteEvents + attachCanvasListeners):
- `pointerdown`: 记录 `dragStartClientX/Y`, 设 `dragging=true`, 切 drag action
- `pointermove` (3px 容忍): 第一次进入真拖动调 `invoke('window-drag-start')`, 之后 `send('window-drag-move', {x: clientX, y: clientY})`
- `pointerup`/`pointerupoutside`/`blur`: 调 `send('window-drag-end')` + `endDrag()`
- sprite 位置不变 (真正拖动 BrowserWindow, sprite 相对窗口位置稳定)

**click vs drag 区分** (3px 容忍):
```javascript
if (dragMoved_ < 3) {
    const dx = Math.abs((ev.clientX || 0) - dragStartClientX_);
    const dy = Math.abs((ev.clientY || 0) - dragStartClientY_);
    if (dx * dx + dy * dy < 9) { dragMoved_++; return; }  // 仍在 click 容忍
}
dragIsWindowDrag_ = true;  // 真拖动开始
```

---

## §二 P0-2 动画预览 (键盘 1-4)

**问题**: R102 之前用户必须打开 DevTools 才能切换动作, 实际 Mac 桌宠用 DevTools 验证不友好。

**修复** (renderer.js `setupAnimationPreviewKeys`):
```javascript
window.addEventListener('keydown', (ev) => {
    const actionMap = { '1': 'idle', '2': 'walk', '3': 'jump', '4': 'drag' };
    if (actionMap[ev.key]) {
        const action = actionMap[ev.key];
        if (spritesByAction[action]?.frames.length > 0) {
            currentAction = action;
            frameIdx = 0;
            lastAdvanceAt = performance.now();
            fallback.textContent = `[R104 preview] ${action} (press 1=idle 2=walk 3=jump 4=drag)`;
        }
        ev.preventDefault();
    }
});
```

- 用户 Mac 真机: 第一次点击桌宠 (focus), 然后按 1/2/3/4 切换 idle/walk/jump/drag
- 帧非空时切换成功, 帧缺失时显示 "NOT loaded" (asset failure)
- 启动时 fallback 显示提示 "press 1/2/3/4 to switch idle/walk/jump/drag"

---

## §三 P0-3 资源/退出验证 (保留 R102 修复)

- Test 1/2: 启动后 asset-report loaded=26+ (idle 6 + walk 8 + jump 8 + drag 4, failed=0)
- Test 6: 候选 B hash 不变 (28ad0ab.../e37185cc...)
- C2_Mac人工验收.command: 不再设 PET_R100_SELFTEST (用户模式不污染), ELECTRON_RC 直接拿真实退出码
- R104 e2e 用 TEST_PIDS 数组 + trap 针对性 PID 清理 (不全局 pkill)

---

## §四 P0-4 交互回归证据 (R104 c2 e2e 14/14 PASS)

| Test | 内容 | 状态 |
|------|------|------|
| 1 | compact 200x240 + asset 26 帧 | ✅ |
| 2 | standard 256x256 + asset 26 帧 | ✅ |
| 3 | 真实 IPC 模式切换 (compact→standard→compact) | ✅ |
| 4 | 26 帧 alpha 边界 union=[71,184]x[24,221] | ✅ |
| 5 | 26 帧 PNG 文件存在 | ✅ |
| 6 | 候选 B hash 不变 | ✅ |
| 7/8 | renderer/main 语法 | ✅ |
| 9 | canvas 监听解绑 (attach/detach 配对) | ✅ |
| 10 | 无残留 PID | ✅ |
| **11** | **R104 真正 BrowserWindow 拖拽 IPC handlers 注册** (源码验证 + 启动无错; 真实鼠标行为 Mac 真机) | ✅ NOT_GUI_VERIFIED |
| **12** | **R104 动画预览 keydown handler (1/2/3/4 切动作)** | ✅ |
| **13** | **sprite 拖动期间位置稳定 (源码不再修改 sprite.x/y)** | ✅ |
| **14** | **3px 容忍 + dx²+dy²<9 区分点击 vs 拖动** | ✅ |

**Total: 14/14 PASS**

---

## §五 R104 阶段字段

```
CURRENT_VERSION                = V0.0
ROUND_STATUS                   = PARTIAL  (工程门槛 PASS, 等 Mac 真机验收)
WINDOW_DRAG_IMPLEMENTED        = true  (R104 P0-1 真正 BrowserWindow 拖拽)
WINDOW_POSITION_CHANGES_ON_DRAG = NOT_GUI_VERIFIED  (需 Mac 真机鼠标)
SPRITE_RELATIVE_POSITION_STABLE = PASS  (源码验证 sprite.x/y 不被 drag 修改)
DRAG_RELEASE_CANCEL_BLUR       = PASS  (pointerup/pointerupoutside/blur 都发 window-drag-end)
CLICK_VS_DRAG                  = PASS  (3px 容忍 + dx²+dy²<9 区分)
ANIMATION_PREVIEW_AVAILABLE    = true  (1/2/3/4 键切动作)
ASSET_LOAD                     = 26/26
NORMAL_EXIT_TEST               = PASS  (R102 P0-4 真实退出码保留)
ORIGINAL_B_PRESERVED           = true  (R100 §八 + R102 §一 验证 hash 不变)
ENGINEERING_GATE               = PASS
READY_FOR_MAC_MANUAL_ACCEPTANCE = true
C2_REAL_GUI_TEST               = NOT_TESTED
TRUE_PASSTHROUGH               = DEFERRED_UNRESOLVED
V0_0_RELEASE_STATUS            = NOT_FROZEN
```

---

## §六 工程边界遵守

- ✅ 未进入 V0.1
- ✅ 未擅自封版 V0.0
- ✅ 未将 C2 宣称为真正透明穿透
- ✅ 未修改冻结的原候选 B (R100 §八 + R102 §一 验证 hash 不变)
- ✅ 未开发新系统鼠标注入工具 (用 Electron 原生 BrowserWindow.setBounds)
- ✅ 未再次研发 C1
- ✅ 未开始 AI 对话/语音/记忆等其他功能
- ✅ 关键鼠标行为 (WINDOW_POSITION_CHANGES_ON_DRAG) 标注 NOT_GUI_VERIFIED, 不假装沙箱能真实测

---

## §七 交付

| 项 | 值 |
|---|----|
| commit | 待 commit |
| tag | 待 tag |
| 完整备份 | `backup/V0.0_backup_20261016_r104_*.zip` |
| review zip | `backup/C2_R104_source_review.zip` (不含 node_modules) |
| 报告 | `docs/R104_C2_WINDOW_DRAG_AND_PREVIEW.md` |
| 验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command` (R102 修复) |

---

## §八 用户 Mac 验收流程 (R104 后)

1. 双击 `candidates/candidate_b_c2/C2_Mac人工验收.command`
2. 默认启动 compact 200x240 桌宠
3. **点击桌宠角色**: 验证触发 drag 动作
4. **按住桌宠角色拖动**: 验证整个 BrowserWindow 跟随移动, sprite 位置稳定
5. **按数字键 1/2/3/4**: 验证 idle/walk/jump/drag 四种动画正常循环, 无明显裁切
6. **释放鼠标到桌宠外**: 验证拖动结束, 窗口停在释放位置
7. **Cmd+Q**: 验证正常退出, 无残留窗口
