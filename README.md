<div align="center">

<img src="candidates/candidate_b_c2/evidence_r182/AppIcon_1024.png" width="120" alt="AI 桌宠图标" />

# AI 桌宠 · AI Desktop Companion

**macOS 桌面陪伴角色 —— 透明无边框窗口常驻桌面，自己决定该干什么**

Electron 33 · PixiJS v7 · 纯离线 · 零外部 API · 角色与美术 100% 自产

[English](README_EN.md) · [MIT License](LICENSE) · [文档索引](#-文档索引)

</div>

---

## 📸 长这样

<table>
<tr>
<td><img src="candidates/candidate_b_c2/evidence_r170_gifs/R170_scenes_overview.png" alt="办公与吃水果场景" /></td>
</tr>
<tr>
<td align="center"><sub>办公（打字） · 吃水果 —— 真实 Electron 运行时采集，200×240 紧凑窗口</sub></td>
</tr>
</table>

## 🐾 它是什么

一个住在你 macOS 桌面上的小角色。

它不是循环播放预录动画 —— 它有一个**行为引擎**，会根据当前状态、心情、精力和场景，**自己决定**接下来做什么：站起来走两步、站着发呆、在电脑前办公、吃个水果、犯困趴下睡一会儿。你不碰它，它也自己在过日子。

你碰它，它也有反应：可以拖到桌面任意位置、点击触发反馈、打开设置面板调它的脾气。

## ✨ 特性

| | 能力 | 说明 |
|---|---|---|
| 🎭 | **自主行为引擎** | 12 个状态：`IDLE` / `WALK_LEFT` / `WALK_RIGHT` / `SLEEP_ENTER` / `SLEEP_LOOP` / `WAKE_UP` / `DRAGGING` / `GESTURE` / `SIT` / `DOZE` / `WORK` / `EAT_FRUIT`，带转换概率表与动作打断/恢复 |
| 💙 | **心情系统** | 4 种心情（开心 / 平静 / 困倦 / 无聊）由互动频次与静默时长驱动，心情反过来影响行为概率 |
| 🪑 | **生活化场景道具** | 办公桌 / 座椅 / 沙发 / 床 / 被子 / 水果桌 / 键盘 / 屏幕辉光 / 吊灯 / 心形 —— 共 13 件程序化生成的道具 |
| 🎬 | **23 个可播放动作** | 6 个核心动作（idle / walk_left / walk_right / sleep_enter / sleep_loop / wake_up）+ 17 个动作库（张望 / 歪头 / 点头 / 伸展 / 开心 / 招手 / 鼓掌 / 吃水果 …） |
| 🖱 | **透明交互** | 透明无边框置顶窗口 + 像素级命中区域，角色本体之外的区域不拦截鼠标 |
| 🖱 | **拖拽** | 60Hz 轮询跟随，落地后交还行为引擎，边界内 clamp |
| ⚙️ | **设置面板** | 缩放 / 活动频率 / 睡眠频率 / 点击反馈 / 开机自启，持久化到 `~/Library/Application Support` |
| 🚀 | **桌面启动图标** | 一键生成 macOS `.app` bundle 装到桌面，双击即启动（`candidates/candidate_b_c2/113_R182_install_desktop_icon.sh`） |
| 🔒 | **单实例** | Electron 原生单实例锁，重复启动只会聚焦已有窗口，不会开出第二只 |
| 🌍 | **完全离线** | 不连任何服务器、不调任何外部 API，所有状态都留在本机 |

## 🚀 快速开始

需要 **macOS 11+** 和 **Node.js 18+**。

```bash
# 1. 装依赖（会下载 Electron 运行时，约 200MB）
cd candidates/candidate_b_c2
npm install

# 2. 启动桌宠
npm start
```

启动后你会看到一个小小的角色出现在桌面左上角（200×240 紧凑窗口）。

### 装成桌面图标（推荐）

```bash
# 在仓库根目录执行
bash candidates/candidate_b_c2/113_R182_install_desktop_icon.sh
```

脚本会：生成角色图标 → 打包成真 `.app` bundle → 放到桌面 → 用 Finder API 定位到**空闲且不被窗口遮挡**的网格槽位 → 校验坐标已落盘 → 冒烟启动一次。

> 桌面上那个 `AI桌宠.app` 是**仓库 bundle 的拷贝**，其中 `Contents/MacOS/AIPet` 是一份委托脚本，转发到仓库内那一份正式启动器 —— 启动逻辑只有一份真身，不会两边跑偏。

## 📁 项目结构

```
.
├── candidates/
│   ├── candidate_b_c2/            ← ★ 主实现：Electron + PixiJS
│   │   ├── src/                   ← 运行时源码（见下表）
│   │   ├── assets/                ← 角色帧 + 场景道具 + manifest
│   │   ├── tests/                 ← node 单元测试
│   │   ├── 1xx_R182_*.py|sh       ← 图标生成 / 桌面安装 / 取证脚本
│   │   └── evidence_r*/           ← 各轮次的可复现证据产物
│   ├── candidate_a_appkit/        ← 备选实现：Objective-C + AppKit（保留做选型对比）
│   └── candidate_b_electronpixir/ ← 原候选 B（冻结保护，不在主线上）
├── assets/prototype_chibi/        ← 程序化绘制的几何占位角色（早期）
├── _app_bundle/                   ← 打包好的 .app bundle
├── docs/                          ← 每轮的交付索引 / QA 报告 / 调研
├── evidence/                      ← 构建日志 / 性能采样 / 截图
├── one_click_test/                ← 一键复测脚本
└── test_window/                   ← 点击穿透探针等小工具
```

核心源码：

| 文件 | 职责 |
|---|---|
| `src/main.js` | Electron 主进程：窗口、拖拽 IPC、单实例锁、状态持久化 |
| `src/renderer.js` | PixiJS 渲染层：sprite 播放、场景道具挂载、点击/拖拽 |
| `src/behavior_engine.js` | 行为状态机与调度（最大的一块） |
| `src/mood_engine.js` | 心情评分与状态衰减 |
| `src/action_library.js` | 动作目录、过渡混合、手势池、点击池 |
| `src/idle_director.js` | 站立时的眨眼/呼吸等微动作编排 |
| `src/sprite_layout.js` | 角色锚点与布局计算 |
| `src/settings_store.js` / `settings_panel.*` | 设置持久化与设置面板 |

## 🧭 技术选型（做过对比，结论留在仓库里）

项目对 **Objective-C + AppKit** 和 **Electron + PixiJS** 两条路线做过同帧率公平对比，加权评分 **A 3.50 / B 3.55**（差距 0.05/5.00）：

- AppKit 更轻（RSS ~27MB vs Chromium ~129MB），但受限于本机 Swift 工具链问题，且放弃已投入的 Electron 资产属于"破坏性迁移"；
- Electron 跨平台、npm 生态对后续接 AI 最友好，PixiJS 的 2D 序列帧播放正是本项目要的能力。

完整推理、实测数据与被排除的第三条路线（Tauri）见 [`docs/R117_REQUIREMENTS_AND_OPEN_SOURCE_REVIEW.md`](docs/R117_REQUIREMENTS_AND_OPEN_SOURCE_REVIEW.md) 与 [`TECH_DECISION.md`](TECH_DECISION.md)。

## 🎨 角色与美术

**角色美术 100% 自产，仓库里没有任何第三方美术资源。**

- 角色设定：银白短发、冰蓝瞳孔、白色实验服 + 青色内衬与腕带，Q 版约 2.5 头身
- 帧序列、场景道具、图标全部由 Python + Pillow 的烘焙脚本程序化生成，脚本和参数全部在仓库里，可复现
- `assets/prototype_chibi/LICENSE.txt` 明确写明："Original deterministic test sprite graphics generated locally by Python/Pillow. No third-party artwork."

> 角色正式定名与外观冻结仍在进行中，当前 `default_scientist` 只是开发内部 ID。

## ✅ 测试

```bash
# node 单元测试（15 个文件）
cd candidates/candidate_b_c2 && node tests/*.test.js

# R147 端到端（真实 Electron，60 项）
bash candidates/candidate_b_c2/R147_e2e_test.sh

# R177 运行时验证（真实 Electron，34 项）
python3 candidates/candidate_b_c2/100_R177_runtime_verify.py
```

当前状态：**单元测试 15/15 通过 · e2e 60/60 通过 · 运行时验证 34/34 通过**。

## 📚 文档索引

| 文档 | 内容 |
|---|---|
| [`docs/01_PRD_v1.1_冻结基线.md`](docs/01_PRD_v1.1_冻结基线.md) | 产品需求基线 |
| [`docs/02_V0.0_技术验证任务书.md`](docs/02_V0.0_技术验证任务书.md) | 技术验证任务书 |
| [`docs/03_验收与审计规范.md`](docs/03_验收与审计规范.md) | 验收规范 |
| [`docs/04_角色资产与动画规范.md`](docs/04_角色资产与动画规范.md) | 角色资产规范 |
| [`TECH_DECISION.md`](TECH_DECISION.md) | 技术选型决策记录（含实测性能数据） |
| [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) | 已知问题（含 TCC 权限限制对真机验收的影响） |
| [`CHANGELOG.md`](CHANGELOG.md) | 变更日志 |
| [`docs/R182_DELIVERY_INDEX.md`](docs/R182_DELIVERY_INDEX.md) | 最近一轮（桌面启动图标）的完整交付索引 |
| [`docs/` 下各轮交付索引](docs/) | 每一轮都有对应的 DELIVERY_INDEX + QA_REPORT，可追溯 |

## 🚧 路线图与已知限制

诚实说明当前边界：

- **V0.0 技术原型阶段，非成品**。基础引擎、资产管线、桌面集成已跑通；UI 打磨还在前面。
- **窗口级透明，非像素级穿透**。当前用 200×240 紧凑窗口 + 命中区域规避，实测"整窗穿透"方案未通过验证。
- **真实 Mac 视觉验收受 TCC 限制**。自动化进程默认没有 Screen Recording 权限，`screencapture` 抓不到含桌宠像素的图 —— 因此改用 WindowServer 窗口坐标 + A/B 像素对照取证，但最终观感仍需人眼确认。
- **开机自启在源码构建下不生效**（macOS 对未签名 app 的 login item 限制），设置面板会如实显示未开启，不谎报。
- **AI 对话、长期记忆、语音**在路线图上，尚未实现 —— 当前版本完全离线。

## 📄 许可

代码与本仓库内全部美术资源采用 [MIT License](LICENSE)。

如果你 fork 了它，角色美术同样可以随便用 —— 因为它本来就是这个仓库自己生成的。

## 👤 作者

**墨良**（[@moliangjin](https://github.com/moliangjin)）

---

<div align="center">
<sub>用 Electron + PixiJS 造一个住在桌面上的小伙伴 · 纯离线 · 无追踪</sub>
</div>
