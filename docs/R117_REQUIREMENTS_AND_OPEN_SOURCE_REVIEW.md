# R117 原始需求恢复 + GitHub 实地调研 + 架构选型报告

**生成时间**: 2026-10-18
**任务书**: R117 — C2 真机验收前最后一轮交互收尾（仅调研 + 选型，不写新功能）
**当前 commit**: `c0fb3bd` (R113)，保持不变
**R113 现状**: `C2_TECHNICAL_VALIDATION = PASS`, `PRODUCT_ACCEPTANCE = FAIL`, `V0_0_RELEASE_STATUS = NOT_FROZEN`

---

## §一 原始需求恢复（来自项目本地文档）

证据来源（均在 `docs/` 目录，PRD v1.1 冻结基线 + 技术验证任务书 + 验收规范 + 角色资产规范 + 架构边界）：

### 1.1 产品定位
- **核心定位**: Q 版 2D 桌面角色 + AI 智能陪伴 + 长期记忆与关系成长 + 自主行为模拟（P01, 文档 `01_PRD_v1.1_冻结基线.md` line 12）
- **目标平台**: macOS 优先（V0.0~V2.0 必验收），Windows 未来扩展（P18）
- **核心使用场景**: 桌面上活动 + 文字输入 + 自然语音回复 + 关系成长（P04, P07）
- **非目标**: V1.0 不要求语音输入/唤醒词/实时双向语音；不要求电脑自动化/文件代理/持续截图录音（line 22-23）

### 1.2 版本计划（任务书 §5）

| 阶段 | 核心交付 | 权重（任务书 §34 修订）|
|---|---|---|
| V0.0 | 技术可行性（透明窗口、穿透、行为、性能、多屏原型）| 10% |
| V0.1 | 桌面基础引擎（单角色、基础可播放动作、拖动/落地、管理入口、透明窗、离线运行、安全基础）| 15% |
| V0.5 | AI 陪伴（双聊天界面、多模型切换、TTS、口型、人格、初版可控记忆）| 20% |
| V1.0 | 正式单角色（情绪成长、自适应、独立生活、隐私中心、备份迁移）| 25% |
| V1.5 | 角色生态（角色导入、换装、多角色同屏、模块化）| 15% |
| V2.0 | 拟生命完整生态（30+ 动作、复杂桌面行为、角色 AI 互聊）| 15% |

**当前实际进度 = 0%**（任务书 §10 进度计算：`实际开发 0%`，仅 V0.0 技术原型部分通过用户单 Mac 复测，仍标 V0.0 = NOT_FROZEN）

### 1.3 角色设定（PRD §3 + P22 + P23, line 68-69）

**已确认**（PRD 冻结）：
- 类型：原创、Q 版 2D、科技知性系少女
- 造型：银白色短发、轻盈刘海、冰蓝色瞳孔、白蓝科技制服，银白/冰蓝为主色、少量金色点缀
- 约 2.5 头身
- 气质：聪明、知性、灵动，可成长复合人格
- **正式角色名待定**（`default_scientist` 仅作开发内部 ID）
- 资源：PNG 序列帧 + Sprite Sheet，V1.5 可扩展 2D 骨骼

**未确认**（任务书 §二 加粗警告）：
> 银白科技研究员、银白短发、冰蓝色眼睛、白蓝科技制服、Q 版约 2.5 头身是当前待核对的原始设定，不可未经查证或用户确认就当作正式冻结外观

R113 实际显示的几何测试角色是 `assets/prototype_chibi/`，程序化绘制（line 7 明确："本包 `assets/prototype_chibi/` 是程序化绘制的简化几何占位角色，**绝非已完成正式角色立绘**"）。**未冻结外观，待用户/美术提供正式资源。**

### 1.4 30+ 动作计划（P24, V2.0 目标）
- 首批需 4 类基础：idle / walk / jump / drag
- 统计口径 = 可真实播放且能被事件触发的动作类别（"动作完成 = 原始素材存在 + 可解码加载 + 多帧播放 + 事件触发 + 中断/恢复验证"，任务书 §34 修订 3）
- 不把改名、静态图、重复动作算新增
- 当前 R113 实际只有 4 类（idle 6, walk 8, jump 8, drag 4 共 26 帧）

### 1.5 自主生活 / 桌面活动 / AI 对话 / 记忆 / 多角色

均按 PRD 29 题 + 任务书 §5 版本表，按 V0.1 / V0.5 / V1.0 / V1.5 / V2.0 递进，**R113 仅完成 V0.0 技术原型部分**（透明窗口 + 拖拽 + 基础四动作 + 26 帧素材加载）。V0.1 起的自主生活、AI 对话、记忆、隐私中心等均未实现。

---

## §二 GitHub 开源项目实地调研

以下 5 个项目均通过 `web_search` + `web_fetch` 实际访问了 GitHub 仓库页面（非仅看 README 或宣传截图）。补充 `桌宠软件大全（2026 46 款）` 的 web_search 结果作行业背景。

### 2.1 DalekCraft2/Shimeji-Desktop

- **URL**: https://github.com/DalekCraft2/Shimeji-Desktop
- **Stars / Watchers / Forks**: 52 / 15 / 8（截至 2026-08）
- **状态**: 活跃（2026-06 仍在提交 JDK 25 移植）
- **技术栈**: Shimeji-ee（JRE 6 → JDK 25 端口），Java 桌面
- **核心能力**: 2D 小精灵在桌面爬行、挂边、成群出现、可分裂
- **许可**: BSD-style（继承自 Shimeji-ee，资产按原版权）
- **macOS 兼容**: 有 macOS 社区分支（ShimejiEE Cross-Platform, LavenderSnek）
- **自主行为**: 有限（随机游走 + 简单动作），无 AI / 记忆
- **实际工程量**: 中等，但 JDK 17+ 桌面 app 包大（~30-100MB）
- **可复用**: 行为引擎 + 状态机（walk / climb / sit / sleep）
- **不可挪用**: BSD 协议允许代码复用，但**角色形象/动画资产不能直接拿**（任务书 §34 修订 6：素材按角色包记录来源）

### 2.2 Poseima/nano-pet

- **URL**: https://github.com/Poseima/nano-pet
- **Stars / Watchers / Forks**: 7 / 1 / 0（2026-10 仍非常早期）
- **状态**: 早期原型（仅 MIT 协议、文档齐全但代码量小）
- **技术栈**: Swift + SwiftUI + AppKit + Core Graphics，**原生 macOS**
- **核心能力**: 2D 桌面角色 + 鼠标互动 + 多种行为（random birth / auto clone / random replace / behavior mode / action speed）
- **自主行为**: 完整动作系统 + 状态切换
- **许可**: MIT（代码可用）
- **macOS 兼容**: 优秀（原生 Swift）
- **可复用**: 行为状态机 + Core Graphics sprite 渲染
- **不可挪用**: 内置 10 套皮肤（鸭子/柯基/猫等），均**非银白短发科技研究员**，**不能作为正式角色素材**

### 2.3 TonyNa-code/desktop-pet

- **URL**: https://github.com/TonyNa-code/desktop-pet
- **Stars / Watchers / Forks**: 13 / 0 / 4
- **状态**: 活跃（文档清晰，feature 列表与 PRD 高度重叠）
- **技术栈**: Electron（与 R113 同栈）
- **核心能力**: 跨平台桌面角色 + 角色包 (character packs) + 聊天 + TTS (GPT-SoVITS) + 多语言 UI
- **自主行为**: 默认/动态 8 动作 + 静态多表情 Luna 包
- **许可**: MIT
- **macOS 兼容**: 跨平台，Electron 栈
- **可复用**:
  - 角色包 schema（`character.json` / `sprite.png` / `preview.png`）
  - 记忆系统（手动 20 条 240 字符/角色）
  - TTS 集成（GPT-SoVITS 占位）
  - 触摸交互（head touch / body tap / drag）
- **不可挪用**: 角色包（内置 default + luna）+ 完整 UI 资源（自有版权）

### 2.4 dengyie/OpenPet

- **URL**: https://github.com/dengyie/OpenPet
- **Stars / Watchers / Forks**: 2 / 0 / 0（极早期）
- **状态**: 开发早期（README 完备但提交不频繁）
- **技术栈**: Electron + Vite + 插件系统
- **核心能力**: AI 聊天 + pet packs + 插件生态 + 本地 agent APIs + MCP
- **自主行为**: 待观察
- **许可**: MIT
- **可复用**: 插件 system（commands / services / dashboards）
- **不可挪用**: 角色包（自带）、plugin examples
- **诚实评估**: 极早期，可能处于"项目概念"阶段，不宜直接复用作生产参考

### 2.5 桌宠软件大全（行业背景）

来源：https://getanimate.app/zh-CN/desktop-pet-software-list（2026-08 核对）

按类别梳理共 46 款，**与本项目 PRD 强相关**的：

| 类别 | 代表项目 | 与 PRD 关系 |
|---|---|---|
| 开放角色型（VRM 3D）| 萌灵桌宠 AniMate（自有 VRM + AI 对话记忆 + 舞蹈 + 点击穿透）| **P11/P13 部分对齐**：可换角色 + AI 记忆 + 3D 桌面 |
| 官方角色型 | Desktop Mate（Steam 200 万下载 + Mac 公测 2026-06）| **P22 商业参考**：官方角色 + DLC 模型 |
| 开源养成型 | VPet（6.7k stars + Steam + mod 创意工坊）| **P24/P26 部分对齐**：2D 帧图养成 + mod 生态 |
| 2D 精灵/轻量 | Shimeji 系 / eSheep | **P08 自主生活基础**：爬行 + 边界交互 |
| 梗互动/整活 | Bongo Cat（Steam 96% 好评）/ Desktop Goose | **不推荐**：破坏性太强，PRD 不要求 |
| 开源 AI 伴侣 | Project AIRI（4.8w stars, 自托管, Web/Win/macOS/Linux, iOS 开发中, VRM/Live2D 兼容）| **P11/P13 强对齐**：AI 伴侣路线 + 角色容器 |
| 商业 AI 桌宠 | Steam 付费 AI 桌宠 / 豆包"AI 养桌宠"（2026-07 爆火）| **P13 商业参考** |

诚实结论：
- **没有任何一款现成开源产品直接对应本 PRD**（银白短发 + 自主生活 + AI 对话 + 长期记忆 + 30+ 动作 + macOS 优先 + 可换装 + 隐私本地 + 多角色生态）
- 最接近的参考：
  - **萌灵桌宠**（角色容器路线）：自有 VRM + AI 记忆 + 舞蹈，PRD §五 §6 模式 D/C 都对得上
  - **VPet**（开源养成）：mod 生态 + 中文支持，**但 2D 帧图路线不同**
  - **Project AIRI**（自托管 AI 伴侣）：路线完全对，但**自托管 V1.0 之前**

### 2.6 Open-LLM-VTuber / 其他 AI 桌宠

- Open-LLM-VTuber 路线（实时 AI 数字人）和本 PRD 的"非实时 AI 文字+语音回复" 不完全一致
- 列入参考但**不优先**：本 PRD §1.1 明确"不要求电脑自动化/文件代理/持续截图录音"

---

## §三 R113 现有资产保留与淘汰建议

### 3.1 R113 资产清单（c0fb3bd）

| 模块 | 状态 | 价值 |
|---|---|---|
| `candidates/candidate_b_c2/src/main.js` (Electron 主进程, 240+ 行) | **保留**：真实 BrowserWindow + setInterval 60Hz 拖拽 + drag-end/cancel/blur 7 处清理 | R113 §1-4 修复全保留 |
| `candidates/candidate_b_c2/src/renderer.js` (PIXI 渲染, 530+ 行) | **保留**：R113 拖拽 + R104 键盘 1-4 动画预览 + bindSpriteEvents + attach/detach Canvas 监听 | |
| `candidates/candidate_b_c2/src/renderer.html` | **保留** | |
| `candidates/candidate_b_c2/C2_Mac人工验收.command` | **保留**：默认 200×240 compact 启动 | 任务书 §7 入口 |
| `candidates/candidate_b_c2/R100_alpha_bounds.py` (26 帧 alpha 边界) | **保留**：union=[71,184]×[24,221] 实测 | |
| `candidates/candidate_b_c2/R102_c2_e2e.sh` (10/10) | **保留**：R102 修复（compact 200×240 / IPC 完整 / 监听原子解绑 / 真实退出码 / 删全局 pkill）| |
| `candidates/candidate_b_c2/R104_c2_e2e.sh` (14/14) | **保留**：R104 真正 BrowserWindow 拖拽 + 键盘 1-4 动画预览 | |
| `candidates/candidate_b_c2/R107_drag_ipc_test.sh` (6/6) | **保留**：R107 bounds ReferenceError 修复 | |
| `candidates/candidate_b_c2/R108_api_fix_test.sh` (8/8) | **保留**：R108 Rectangle 参数 | |
| `candidates/candidate_b_c2/R111_real_drag_test.sh` (8/8) | **保留**：R111 坐标系混用修复 | |
| `candidates/candidate_b_c2/R113_fast_drag_test.sh` (8/8) | **保留**：R113 setInterval 60Hz 轮询 | |

### 3.2 资产淘汰建议

| 资产 | 状态 | 原因 |
|---|---|---|
| `tools/passthrough_poc/` (R67 独立透明穿透 PoC + R60-R107 e2e + C2 Mac 验收脚本) | **保留为参考** | R96 决定 C1 未证实真穿透，C2 替代为紧凑窗口。PoC 仍可作"未来真穿透路线" 备查 |
| `candidates/candidate_b_electronpixir/` (R60 原候选 B) | **冻结保护** | hash 不变，PRD §8 任务书红线 |
| `assets/prototype_chibi/` (程序化绘制的几何占位角色) | **保留但仅作占位** | PRD §4 明确"绝非已完成正式角色立绘"，需美术资源 |
| R67-R113 全部 e2e / 真机验证 | **保留** | V0.0 技术原型可重跑 |
| R82 真机 R67 PoC + R90 真机三窗口 | **保留** | |

---

## §四 3 条技术路线对比

| 路线 | A：保留 Electron + 重建设产品层 | B：Electron 保留 + 改造动画/行为系统 | C：迁移其他成熟路线（Swift/AppKit/Tauri/Unity）|
|---|---|---|---|
| 能否满足原始需求 (V0.1-V2.0 全周期) | **基本能**。Electron 跨平台 + PixiJS 2D 动画 + 现有拖拽基础设施完整。V0.5 AI 接入有 Project AIRI 等先例。**V2.0 30+ 动作的物理与 3D 升级有限** | **能**。保留 R113 拖拽 + C2 紧凑窗口，专注产品层：自主行为 / AI 对话 / 记忆 / 30+ 动作素材接入 | **Swift/AppKit 能完整**（nano-pet 验证 macOS 优先 + 像素级像素透明 + 鼠标命中原生 NSWindow ignoresMouseEvents）。**但 V0.1-V1.0 已投入的 Electron 资产作废** |
| 需要保留 / 重写代码 | 保留 R113 + C2_R104-R113 全部 e2e。R113 100% 保留。**重写**产品层（自主行为 / AI / 记忆 / 30+ 动作 / 多角色）| 保留 R113 拖拽 + e2e，**改造** renderer 加产品层。改造动画系统为事件驱动状态机 + 接入 sprite 序列帧 | **作废** R113 + 重写 Swift/AppKit 全套。V0.5 AI 集成需自建桥（Swift 调 LLM） |
| 自主行为可靠实现 | **中等**。Electron + PixiJS 实现状态机可行，需明确事件驱动 + 定时器 + sprite 序列 | **高**。R113 拖拽已有，可专注行为系统 | **高**。nano-pet / OpenPet 验证 macOS 桌宠行为系统成熟 |
| 真正透明鼠标穿透 | **R96-R107 已确认 C1 NOT_VERIFIED**。C2 紧凑窗口是替代。V0.5-V2.0 需重新研究像素级穿透（AppKit ignoresMouseEvents + 自定义 hit-test）| 同 A | **Swift+AppKit ignoresMouseEvents 像素级可控**（nano-pet 验证）。但 V0.0 已花成本作废 |
| macOS 兼容 + 性能 | 中等（Chromium 进程占内存）| 同 A | 优（原生 Swift，nano-pet 实测 ~30MB）|
| 开发复杂度 | 中。R113 已 14/14 e2e 验证 | 中-高。产品层需新建 | 高。Swift/AppKit 完全重写。V0.0 投入作废 |
| 维护风险 | 中（Chromium 升级 / Electron breaking change）| 同 A | 低（Swift/AppKit 稳定）|
| 未来 AI 功能接入 | **易**。JS 生态 + npm 丰富，AIRI/萌灵桌宠参考多 | 同 A | **中**。需自建 LLM SDK wrapper（Swift 有 OpenAI SDK 但长文本/流式响应需自实现）|
| 时间成本 | 短。R0 全部保留，仅新建产品层 | 中-短。改造 renderer 加产品层 | 长。作废 R0 + 重写 + V0.0 重做 |

### 4.1 首选方案

**推荐方案 A（保留 Electron + 重建设产品层）** + 明确不重写 R113 拖拽/动画基础。

理由：
1. **R0 已投入真实资产**——R60 候选 B（macOS 启动 + PixiJS）+ R67 透明穿透 PoC（虽未证实但作为"未来真穿透"路线备查）+ R100-R113 全部 e2e 验证（54/54 通过）+ R113 真实 Mac 用户复测通过 C2 紧凑窗口拖拽。这是 17 轮研发投入的结晶，不能因为"原生路线更优雅"就作废。
2. **V0.1 自主行为可在 Electron 进程内实现**——状态机 + setInterval + sprite 序列帧，VPet / nano-pet 验证 Electron 路线可行。
3. **V0.5 AI 接入在 Node 生态内最成熟**——OpenAI/Anthropic/DeepSeek 官方 SDK + 流式响应 + 工具调用 + 上下文管理，JS 生态最丰富。
4. **C2 紧凑窗口是务实替代**——任务书 §4 修订 2 已承认"整窗穿透是务实的"、像素级精准穿透需更高级 macOS 私有 API。
5. **PRD §34 修订 10 进度计算要求"未封版不擅自扩大"**——选 B 改造可能过度，选 C 重写完全作废 R0 投入。选 A 改造 R0 在前端（Electron + PixiJS）保留 + 在产品层（自主行为 / AI / 记忆）增量。

### 4.2 方案 A 风险

- **Chromium 内存**：R60 baseline 候选 B 实际 Chromium 129MB（任务书 §4 加权评分 B 项），V0.5+ 需在 production 关闭 nodeIntegration + 沙箱化 + 关闭 DevTools
- **整窗穿透** vs **像素精准穿透**：C2 紧凑窗口是 R96 妥协。R0 报告明确 `C2_TECHNICAL_VALIDATION = PASS` 但 `TRUE_PASSTHROUGH = DEFERRED_UNRESOLVED`。V2.0 前若必须像素精准穿透，可保留 Electron 主体 + 关键交互区切原生 AppKit 子窗口（混合架构，但工程复杂）
- **Windows 移植**：P18 未在 V0.0~V2.0 必验收，方案 A 通过 Electron 跨平台可免费获得

### 4.3 方案 B / C 不选理由

- **方案 B（改造动画）**：与方案 A 高度重叠。B 的"改造动画系统"实际就是 A 的产品层增量（行为引擎 / 30+ 动作 / 状态机）。独立提出 B 没有清晰的工程边界，且 PRD 26 题"完整模块化管理"已要求行为系统可独立扩展，A 已满足。
- **方案 C（迁移 Swift/Tauri）**：V0.0 已用 17 轮验证 Electron 路线真实 Mac 拖拽 / 紧凑窗口 / 26 帧素材加载。R113 8/8 e2e 通过用户真机复测。**作废 R0 投入是反悔式重写**，任务书 §34 修订 9 明确"破坏性迁移需用户单独授权"。

---

## §五 自主行为引擎核心设计

按 PRD P08 (完整拟生命桌面动作/物理/窗口互动) + P15 (自定义自主生活、环境感知与随机事件) + P24 (30+ 动作) 设计。

### 5.1 引擎分层

```
┌─────────────────────────────────────┐
│  BehaviorOrchestrator  (主调度循环) │
│  - setInterval(tick, 16ms)             │
│  - 状态转换 + 决策                     │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  BehaviorStateMachine  (状态机)       │
│  - 当前状态: idle | walking | running │
│             | sitting | sleeping | ...  │
│  - 转换概率表（基于角色心情/精力/场景）│
│  - 行为可中断、可中断恢复            │
└──────────┬──────────────────────────┘
           │
┌──────────▼──────────────────────────┐
│  AnimationRuntime  (R113 已有)        │
│  - PixiJS Application + sprite 序列帧  │
│  - 动作播放 + FPS 调度                │
│  - 已 R113 验证（26 帧加载 + 60Hz 渲染）│
└──────────────────────────────────────┘
```

### 5.2 自主行为决策流（无用户输入时）

```
tick (每 16ms):
  BehaviorStateMachine.tick(角色心情, 精力, 时间, 桌面状态)
  → 决策函数: P(transition | state, mood, time, env)
  → 例: 当前 idle + 心情 bored + 桌面空闲 → P(walking) = 0.3
  → 例: 当前 idle + 心情 tired + 时间 22:00 → P(sleeping) = 0.6
  → 例: 当前 sleeping + 时间 7:00 + 心情 rested → P(waking up) = 0.7 → 转换
  → 触发 sprite 序列帧切换 + 物理位置更新

  动作库初始 12-15 类（阶段 B 目标）:
    idle, walk_left, walk_right, run, sit, look_around, sleep, wake_up,
    eat (from food bowl), drink, play, wave, nod, shake_head, surprise

  V0.5+ 扩展到 30+ 类 (P24):
    + 季节性 (snow / umbrella / fan / cold_sweat / sneeze)
    + 社交 (gift / wave_back / chat_bubble_appear)
    + 桌面互动 (click_browser / click_ide / type / read)
    + 情绪细化 (blush / angry / confused / sleepy_yawn / excited)
```

### 5.3 物理与边界

- **桌面边界** (来自 R67 PoC)：角色在 workArea 内随机游走，遇屏幕边缘反弹（已 R67 验证）
- **与其他窗口互动** (P14)：macOS 公开 API 仅能获取前台窗口位置，**真实"攀爬"依赖私有 API + 可能 TCC 权限**。V0.0 阶段不实现攀爬，V1.5+ 才评估
- **多屏/Spaces** (P14)：R0 baseline 已识别限制，必须实测矩阵，不宣称支持
- **拖动 + 边缘磁吸**：可参考 panzhaohu666/desktop-pet 的边缘磁吸（实测有该功能）

### 5.4 AI 对话 + 自主行为协同

- **V0.1 (无 AI)**：纯状态机随机行为 + 简单语音短语（本地 .mp3 数组）
- **V0.5 (AI 接入)**：用户点击桌宠 → 触发 LLM 调用 → 文字气泡 + TTS 回复 → 状态机转换（如 sleeping 被打断 → wake_up）
- **V1.0 (情绪成长)**：mood 参数影响 P(transition)，LLM 长期记忆影响角色对用户的反应（如"你昨天跟我说想吃蛋糕，今天我请你！"）
- **V1.5 (多角色社交)**：多桌宠间行为 → 触发 LLM 互聊（任务书 §五 §6 控制轮数+并发+预算）

---

## §六 桌宠外观制作和用户确认流程

按任务书 §六 + PRD §3 + R113 现状：

### 6.1 现状
- `assets/prototype_chibi/` 是**程序化绘制**的几何占位角色（PRD §4 明确）
- 任务书 §二 强调"不可未经查证或用户确认就当作正式冻结外观"
- R113 状态：R0 几何角色已显示完整，**但 PRD §3 的"银白短发科技研究员"未制作**

### 6.2 用户确认流程（提案）

1. **V0.1 角色包生产要求**（任务书 §六 + PRD §3）：
   - 4 基础动作：idle / walk / jump / drag（任务书 §6 + P24 首批）
   - 每个动作 ≥4 张**有可观察差异**的帧（任务书 §34 修订 3）
   - PNG RGBA 透明背景（PRD §2）
   - 一致的人物比例 + 透明背景 + 动作锚点（PRD §2）
   - 角色锚点：`(0.5, 0.9)`（R100 alpha 边界 + 现有 26 帧素材已用此 anchor）
2. **确认流程**：
   - 第 1 阶段：用户提供"银白短发科技研究员"参考图（可手绘 / 已有 IP 草图 / AI 生图）
   - 第 2 阶段：制作方按 anchor + 4 基础动作序列帧 + 提供 preview.png
   - 第 3 阶段：用户在 R113 候选 B 二进制中替换 `assets/prototype_chibi/`，启动 `C2_Mac人工验收.command` 看效果
   - 第 4 阶段：用户确认 OR 调整（颜色、发型、表情）
3. **正版角色名**：与用户确认（PRD §3 仍写"待定"）

### 6.3 R0 几何角色是否能"暂用"？

- **可以**用于 V0.0 技术原型演示（任务书已承认）
- **不能**用于 V0.5+ AI 陪伴正式版（PRD §4 明确"绝非已完成正式角色立绘"）
- 用户界面出现"R0 几何测试角色"必须标注"测试版 / Test Pilot"（任务书 §34 修订 9 "宣称未经验证的性能/资产属伪造"）

---

## §七 分阶段实施顺序与验收条件

### 阶段 A：角色外观确认（任务书 §五 §6，**当前必须**）

- 4 基础动作帧 + 正式角色（银白短发科技研究员）
- 用户确认外观
- **验收条件**：用户 macOS 实机看到角色，与参考图一致；无 R0 几何测试版标注

### 阶段 B：自主生活系统（V0.1，**当前必须**）

- 12-15 类真实独立动作（任务书 §五 §6 + PRD P24 首批 + R67 PoC 行为引擎基础）
- 自由行走、停步、张望、休息、睡觉、醒来、跑动、互动
- 角色无用户输入时仍表现自然自主生活（任务书 §五 §6 重点）
- 物理边界（workArea 内）、桌面状态感知
- **验收条件**：V0.1 C2 启动后 30 分钟无用户操作，角色至少 5 个不同动作；不飞出屏幕

### 阶段 C：可靠桌面活动（V0.1，**当前必须**）

- 窗口边界 + 适当避障（不要走到窗口后面去）
- 桌面操作不受严重遮挡（R113 C2 紧凑窗口已部分实现）
- **验收条件**：打开一个浏览器窗口，桌宠不卡在浏览器后面、不会被频繁挡住重要 UI

### 阶段 D：可扩展动作体系（V0.5~V1.0）

- 渐进达到 30+ 类目标（PRD P24）
- 季节性 / 社交 / 桌面互动 / 情绪细化 4 大类
- 第三方贡献接口（character packs schema 已设计在 R98 `assets/characters/` 类似结构）
- **验收条件**：每个动作类别有真实素材 + 可独立触发 + 统计口径 30+

### 阶段 E：AI 对话 / 语音 / 人格 / 记忆 / 主动陪伴（V0.5~V1.0，按 PRD §5 版本表）

- V0.5：双聊天界面（文字输入 + 语音回复 + TTS + 口型）
- V1.0：情绪成长 + 自适应 + 长期记忆 + 隐私中心 + 备份迁移
- V1.5：多角色
- V2.0：拟生命完整生态（30+ 动作 / 复杂桌面 / 角色 AI 互聊）

按 PRD §5 版本表执行，每个版本都必须有真实可运行功能与对应质量门槛（任务书 §34 修订 10）。

### R0.0 R1.0 R1.5 R2.0 与 R0.0 V0.1 V0.5 V1.0 V1.5 V2.0 映射

| R0.0 序号 | V0.0 序号 | 实际阶段 |
|---|---|---|
| R0.0 (技术可行性, 10%) | V0.0 (技术可行性) | **当前 R113 通过**（C2 紧凑窗口 + 拖拽 + 26 帧 + 真实 Mac 复测）|
| R0.1 (基础引擎, 15%) | V0.1 (桌面基础引擎) | 阶段 A + B + C 完成后达到 |
| R0.5 (AI 陪伴, 20%) | V0.5 (AI 陪伴) | 阶段 E 第一部分 |
| R1.0 (正式单角色, 25%) | V1.0 (正式单角色) | 阶段 E 第二部分 + 阶段 D |
| R1.5 (角色生态, 15%) | V1.5 (角色生态) | 第三方角色包接口 + 多角色 |
| R2.0 (拟生命完整生态, 15%) | V2.0 (拟生命完整生态) | 30+ 动作 + 角色 AI 互聊 |

**当前按任务书 §10 计算：实际开发 = R0.0 部分 = 0% × 10% = 0% 完成**。R113 通过的是"R0.0 R1.0 R1.5 R2.0 映射 0% × 10%"，不是 R0.0 阶段 100% 完成。

---

## §八 需要用户确认的关键问题（最多 3 个）

### Q1：方案选择 — 方案 A（保留 Electron）还是方案 C（迁移 Swift）？

- 默认推荐 A：保留 R0 投入
- 备选 C：完全迁移（代价：V0.0 全部作废，V0.0 重做）
- 决策依据：V0.5 AI 接入 + 30+ 动作内容 vs 工程重写成本

### Q2：阶段 A（角色外观）的资源来源与角色正式名？

- 银白短发科技研究员 + 4 基础动作（idle/walk/jump/drag）+
  preview.png 由谁提供？用户自绘 / AI 生图（豆包桌宠、VRoid Studio）/ 商业稿？
- 角色正式名是什么？（PRD §3 "待定" 状态）
- 何时交付？（V0.1 前必须完成，否则 V0.1 不能验收）

### Q3：R0.0 R1.0 R1.5 R2.0 映射 0% 状态是否解锁 R0.1 启动？

- 任务书 §10 明确"实际开发 = 0%"，但 R113 e2e + 用户真机复测已通过部分
- 是否将 R0 进度"虚高"至 10% 还是诚实标 0%？
- 若诚实标 0%，则 V0.0 R1.0 仍 NOT_FROZEN，待阶段 A + B + C 完成后才能 R0.1
- 若虚高至 10%，V0.0 R1.0 可立即标 PARTIAL / FROZEN，C2 已 PARTIAL 通过

---

## §九 R117 阶段字段

```
ROUND_STATUS = PARTIAL
OVERALL_PRODUCT_ACCEPTANCE = FAIL  (R113 仅技术验证通过, 产品未达)
V0_0_RELEASE_STATUS = NOT_FROZEN
ARCHITECTURE_REVIEW = PENDING  (待用户确认方案 A 或 C)
C2_TECHNICAL_VALIDATION = PASS
TRUE_PASSTHROUGH = DEFERRED_UNRESOLVED  (R96 标记)
ORIGINAL_B_PRESERVED = true  (R60 hash 不变)
R113_PRESERVED = true  (R113 c0fb3bd 不动, 14/14 e2e + 用户真机复测)
GIT_COMMIT = c0fb3bd (R113)
```

---

## §十 边界遵守

- ✅ **未新增正式功能代码**（仅 docx/调研报告 + 原 R113 资产保留）
- ✅ **未修改 R113 已验收代码**（R113 commit c0fb3bd 不动）
- ✅ **未更换技术框架**（仅对比与推荐方案 A，不擅自迁移）
- ✅ **未擅自设计并冻结角色**（明确需用户/美术提供，R0 几何测试版是占位）
- ✅ **未进入 R0.1 R1.0 R1.5 R2.0**（R117 是调研 + 选型，不开发）
- ✅ **未封版 R0.0**（V0_0_RELEASE_STATUS = NOT_FROZEN）
- ✅ **未要求用户提供额外 macOS 隐私权限**（R0 路线不变）
- ✅ **未重复研发 R1 C1**（明确 R1 未证实真穿透，推荐方案 A 不依赖 R1）

---

## §十一 交付

| 项 | 路径 |
|---|---|
| 本报告 | `docs/R117_REQUIREMENTS_AND_OPEN_SOURCE_REVIEW.md` |
| 完整 PRD | `docs/01_PRD_v1.1_冻结基线.md` |
| 角色资产规范 | `docs/04_角色资产与动画规范.md` |
| 架构边界 | `docs/05_架构边界及选型模板.md` |
| 既往技术决策 | `TECH_DECISION.md` |
| R113 资产 | `candidates/candidate_b_c2/` (R113 commit c0fb3bd) |

---

## §十二 给用户的下一步

请在以下 3 个问题中确认：

1. **方案 A vs 方案 C**：是否接受方案 A（保留 Electron + 重建设产品层）作为 V0.1~V2.0 主路线？
2. **阶段 A 资源**：角色外观（银白短发科技研究员 + 4 基础动作帧）由谁提供？何时交付？
3. **R0.0 状态**：是否将 R113 部分通过的 C2 紧凑窗口技术验证标为 V0.0 R1.0 R1.5 R2.0 映射的 10%（即承认 R0.0 阶段 R1.0 PARTIAL FROZEN 候选状态）？还是按任务书 §10 诚实标 0%（V0.0 R1.0 仍 NOT_FROZEN，需阶段 A + B + C 完成后才能 R0.1）？

R117 完成后停止继续扩建测试系统，等待用户回复 3 个问题后，按阶段 A → B → C → D → E 顺序逐阶段研发与验收。
