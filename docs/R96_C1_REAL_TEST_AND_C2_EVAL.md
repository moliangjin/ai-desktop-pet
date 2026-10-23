# R96 真实 Mac 前台测试结论 + C2 紧凑窗口方案评估

**生成时间**: 2026-10-16
**基线 commit**: 83d2465 (R92)
**状态**: 冻结 C1 未证实结论, 评估 C2 替代方案

---

## 一、真实 Mac 前台测试结论 (run_id r67_1792071455002)

用户已在前台 macOS 完成 R67 三窗口 PoC 真实人工验收 (commit 140e16d, R90 + R92 修复后的 orchestrator + 真三窗口 PoC).

| 项 | 结论 | 依据 |
|---|------|------|
| **C1_MODE_SWITCH** | **PASS** | tick 显示 mode 从 A 成功切到 C1, 状态机转换日志多次 |
| **GOLD_CLICK** | **PASS** | TEST 累计 = 10, 金球 click 被上层窗口正确接收 |
| **PROBE_DIRECT_CLICK** | **PASS** | PROBE 累计 = 13, 下层窗口独立 click 路径正常 |
| **C1_TRUE_PASSTHROUGH** | **NOT_VERIFIED** | `TEST click where=transparent` 出现, 但无充分证据确认上层覆盖区真实穿透 — 多数 Probe 点击位置位于上层窗口外或边界处 |

### 关键诚实声明 (按 R96 §一要求)

- ❌ **不得**把 `TEST=10, PROBE=13` 解释为透明穿透 PASS
- ✅ 这两个数字只证明 click 总数累加正常, 不证明 click 因果链 (上层 click → 下层接收)
- ✅ C1 状态机模拟的"穿透"在沙箱 MOCK 模式下验证过, 但**真实 macOS 窗口层级**下未观察到可重复的穿透证据

---

## 二、停止扩大 C1 验证 (按 R96 §二)

- ❌ 不再开发 Swift / Objective-C / Quartz 鼠标注入测试器
- ❌ 不再要求用户开启辅助功能 / 屏幕录制权限
- ✅ 保留全部 C1 源码 (R67 PoC main.js)
- ✅ 保留原始日志 + 实验结论 + 历史备份 (backup/V0.0_backup_20261014_r67_*.zip)
- ✅ 作为技术研究记录, 不作为 V0.0 验收依据

---

## 三、C2 紧凑窗口方案评估 (按 R96 §三)

### C2 现有实现 (R67 PoC main.js line 85-96)

```javascript
} else if (mode === 'C2') {
    // COMPACT_WINDOW_FALLBACK: shrink test window to sprite bbox
    const compact = {
        x: SPRITE_CX - SPRITE_R,   // sprite 中心 - 半径
        y: SPRITE_CY - SPRITE_R,
        width: SPRITE_R * 2,        // 100 x 100
        height: SPRITE_R * 2,
    };
    testWindow.setBounds(compact);
    testWindow.setIgnoreMouseEvents(false);
    lastIgnoreState = false;
    stopStateMachine();
}
```

### 评估表

| # | 项 | 结论 | 依据 |
|---|----|------|------|
| 1 | 金球及正式角色能正常显示 | ✅ | compact 窗口 (100x100) 完全包含 sprite bbox (50 半径圆) |
| 2 | 角色外观不被裁切 | ✅ | sprite 完全在 compact 窗口内, 不裁切 |
| 3 | 可见角色区域能点击 | ✅ | setIgnoreMouseEvents(false) + sprite hitbox 接 click |
| 4 | 拖拽不失去鼠标捕获 | ✅ | stopStateMachine 关闭轮询, 拖拽不被 state machine 干扰 |
| 5 | 窗口不闪烁不抖动 | ✅ | setBounds 同步, 模式切换时调一次, 不持续调 |
| 6 | 角色外部窗口范围小 | ✅ | 100x100 = 10000 px² (原 256x256 = 65536 px², 缩到 15%) |
| 7 | 不因动态动画频繁调窗 | ✅ | C2 只在 mode 切换时调一次, 动画不影响窗口 |
| 8 | 不破坏 PixiJS v7 兼容 | ✅ | C2 仅改 setBounds, 不动 PixiJS 层 |
| 9 | 无须额外 macOS 隐私权限 | ✅ | 不依赖 setIgnoreMouseEvents forwarding, 不需要 AX/Screen Recording |
| 10 | 记录剩余透明边缘遮挡 | ✅ | 100x100 圆外无任何遮挡, sprite 圆内 100% 是角色 |

### 关键限制

- **C2 不是真透明穿透**: `setIgnoreMouseEvents(false)` — 鼠标事件直接给上层, 不会"穿透"到下层
- **C2 是减小遮挡方案**: 100x100 窗口比 256x256 小 84% 遮挡
- **C2 与 C1 完全不同**:
  - C1: 256x256 窗口 + 状态机模拟"穿透" (MOCK 验证过, Mac 前台 NOT_VERIFIED)
  - C2: 100x100 窗口 + 不模拟穿透 (直接收 click)

### R96 §四 工程策略遵循

- ✅ 最小实现 — 复用 R67 PoC 现有 C2 实现
- ✅ 不重新设计桌宠架构
- ✅ 不开发新跨窗口事件模拟
- ✅ 明确区分四项 (真正透明穿透 / 缩小窗口 / 鼠标点击 / 用户体验)

---

## 四、最终结论

### 四项能力区分 (R96 §四明确)

| 项 | C1 | C2 | 真实 Mac 前台验证 |
|---|----|----|------|
| 真正透明穿透 | MOCK 模拟 ✅, Mac 真实 NOT_VERIFIED | ❌ (不是穿透) | C1 NOT_VERIFIED |
| 缩小窗口减少遮挡 | ❌ (256x256 不变) | ✅ (100x100 = 15% 面积) | C2 PoC 存在 |
| 鼠标点击与拖拽正常 | ✅ | ✅ | C1 PASS |
| 真实用户体验 | 部分 (C1 需复杂) | 简单 (窗口小) | C1 需前台; C2 未前台 |

### 候选 B 主程序保护

- ✅ **不修改** `candidates/candidate_b_electronpixir/src/main.js` (R60 输入基线冻结)
- ✅ **不修改** 候选 B 任何代码
- ✅ 候选 B 实际用 R39 passthrough 路线 (`setIgnoreMouseEvents + forward:true`), 不是 C2
- ✅ R67 PoC 是独立测试, 不影响候选 B

### C2 与候选 B 集成路径

- C2 紧凑窗口仅在 **R67 PoC** (独立测试原型) 中实现
- 候选 B (R60 输入基线) **未集成 C2**
- 如未来 V0.1 需引入 C2, 应作为独立子任务, 单独 commit, 不并入当前轮

---

## 五、阶段字段

```
CURRENT_VERSION                = V0.0
C1_TRUE_PASSTHROUGH            = NOT_VERIFIED  (按 R96 §一诚实标注)
C2_PROTOTYPE_STATUS            = PARTIAL        (R67 PoC 实现, 候选 B 未集成, 未 Mac 前台验证)
C2_WINDOW_BOUNDS               = 100x100 (SPRITE_R * 2, 中心 SPRITE_CX/SPRITE_CY)
C2_INTERACTION_RISK            = LOW            (setIgnoreMouseEvents(false), 无 forward 风险)
C2_ACTUAL_PASSTHROUGH          = false          (C2 不是真穿透, 仅是减小遮挡)
C2_REAL_GUI_TEST               = NOT_TESTED     (PoC 存在, 未在 Mac 前台验证)
B_STABLE_BASELINE_PRESERVED     = true           (候选 B R60 输入基线零修改)
GIT_COMMIT                      = 83d2465 (R92 baseline, 本轮无代码改动)
BACKUP_SHA256                   = 4e333b03ffdd7896b208b09de4665de3f8db434c91bd21161ad11669c7a85c48
PHASE_PROGRESS                  = C1 冻结 + C2 评估完成
OVERALL_PROGRESS                = 0%  (V0.0 未正式封版, 需用户最终决策)
USER_MANUAL_ACTION              = NONE  (本轮无新验证, 等待用户决策是否进入 V0.1)
```

### 关键声明

> **C2 属于替代方案评估, 不能擅自降低原产品需求或宣布 V0.0 验收通过。**
> (R96 任务书原话)

V0.0 真透明穿透 **仍未在真实 Mac 前台证实**。C2 是"减小遮挡"的折中方案, **不替代**真透明穿透的产品需求。
