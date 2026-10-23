# R182 QA 报告 — 桌面「AI桌宠」启动图标

> **对应交付**：`docs/R182_DELIVERY_INDEX.md`
> **基线**：R179 `8b52aef`
> **日期**：2026-10-23
> **结论**：`R182_DESKTOP_ICON = PASS` ／ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** ／ `V0_0_RELEASE_STATUS = NOT_FROZEN`

---

## 一、交付物路径（最终）

```
/Users/musk123/Desktop/AI桌宠.app        ← 桌面图标（符号链接 → 仓库内 bundle）
  └─▶ <repo>/_app_bundle/AI桌宠.app/
        Contents/Info.plist              CFBundleName/DisplayName=AI桌宠
                                        CFBundleExecutable=AIPet（ASCII，见 §四.3）
                                        CFBundleIconFile=AppIcon
                                        LSUIElement=true（不弹终端、不占 Dock）
        Contents/MacOS/AIPet             桌面启动器（绝对路径 + 两段式启动）
        Contents/Resources/AppIcon.icns  角色形象图标（16→1024 共 10 档）
```

---

## 二、启动验证（真实 Electron，逐条判据）

### 2.1 启动链路

| 判据 | 门槛 | 实测值 | 结论 |
|---|---|---|---|
| S1 启动器退出码 | `= 0` | `0` | ✅ |
| S2 本地状态加载 | 日志含 `R177 LOCAL_STATE` | `dir=~/Library/Application Support/AI桌宠 mood=calm settings={...}` | ✅ |
| S3 角色资源就绪 | `loaded = 23/23` | `loaded=23/23 actions=idle,walk_left,walk_right,sleep_enter,sleep_loop,wake_up` | ✅ |
| S4 行为引擎启动 | 日志含 `behavior engine started` | `state=IDLE` | ✅ |
| S5 屏上窗口数 | `= 1` | `1`（bounds `(600,300,200,240)`，`onscreen=True`，`alpha=0.999`） | ✅ |
| S6 验收开关泄漏 | 7 模式全部 `= 0` | `--acceptance 0`／`--preview 0`／`--demo-scene 0`／`--r177- 0`／`--quit-after 0`／`fallback 0`／`dev_mode=true 0` | ✅ |
| S7 调试文字 | `fallback` 命中 `= 0` | `0` | ✅ |
| S8 单实例 | 进程 `1→1`、窗口 `1→1` | 进程 `1→1`；窗口 `1→1`；日志 `R182 SECOND_INSTANCE 聚焦已有窗口` + `R182 SINGLE_INSTANCE …退出 (code 0)` | ✅ |
| S9 角色上屏 | 变化像素 > 区域 0.5% | **89.22%**（42827/48000，最大通道差 356） | ✅ |

### 2.2 S9 的取证方法（为什么不能直接看截图）

`macOS screencapture` **抓不到透明 Electron 叠层**（Pixi 画布走 GPU layer）。早期据此得出「桌宠没显示」的判断是**错的，已推翻**。

正确做法是 **A/B 对照**（`112_R182_screen_ab.py`）：

- **A** = 桌宠运行中，按 **WindowServer（Quartz `CGWindowListCopyWindowInfo`）报告的真实窗口坐标**截取该区域；
- **B** = 关掉桌宠后，截取**完全相同**的区域；
- A ≠ B ⇒ 角色确实叠加显示（差值即角色像素）。

门槛取 0.5%：低于此量级只能来自抗锯齿噪声，不可能是真实角色。

### 2.3 回归

| 套件 | 命令 | 结果 |
|---|---|---|
| node 单测 | `node tests/*.test.js`（15 个文件逐个） | **15/15 全过** |
| R147 e2e（真实 Electron） | `bash R147_e2e_test.sh` | **PASS=60 / FAIL=0 / NOT_VERIFIED=0** |
| R177 运行时验证（真实 Electron） | `python3 100_R177_runtime_verify.py` | **34/34 PASS**（A/C/D/E/F/G 七组） |

`src/main.js` 的两处增量（单实例锁 / manifest 回落）**未破坏任何既有判据**。

---

## 三、图标

| 项 | 说明 |
|---|---|
| 源素材 | `candidates/candidate_b_c2/assets/character_R138/idle/idle_00_base.png`（**只读**，SHA256 `09141caf…73aee`，逐字节未动） |
| 合成方式 | bust 裁切（源坐标 `(318,28)-(716,600)`，放大 1.55×）+ 冰蓝斜向渐变底 + 头部柔光晕 + 角色投影；**不重绘五官/发色/瞳色/服装** |
| 选型 | 三色底方案（A 浅 / B 中蓝 / C 深蓝）按 64px 小尺寸可读性对比取 **B**（白大褂与银发在小尺寸仍能压出轮廓） |
| 输出 | 1024 PNG（母版，`evidence_r182/AppIcon_1024.png`）→ `sips` 生成 10 档 iconset → `iconutil` 合成 `.icns` |
| 辨识度实测 | 256px 渲染：银白短发 ✅／冰蓝眼 ✅／白大褂+青色内衬+腕带 ✅／胸前「Q」徽标 ✅ |
| 圆角 | 交付**满幅方图**，由 macOS 自 Big Sur 起的圆角遮罩自动处理（自己画圆角会变成双层圆角） |

---

## 四、本轮真实踩坑（已固化进实现）

### 4.1 `screencapture` 抓不到透明 Electron 叠层 → 早期结论被推翻
见 §2.2。**教训**：判断「窗口有没有显示」不能只看一张截图。

### 4.2 启动器的就绪判据必须只看本轮新增日志
否则会命中上一轮残留的 `R177 LOCAL_STATE` 造成**假就绪**（进而误判启动失败、误触发兜底）。改用「启动前日志长度」做偏移后修正。

### 4.3 LaunchServices 打不开「可执行文件名含中文」的 bundle
实测 `CFBundleExecutable=AI桌宠` 时 `open` 直接报 `NSOSStatusErrorDomain Code=-600 "procNotFound: no eligible process with specified descriptor"`；改为 ASCII 的 `AIPet` 后正常。**桌面显示名仍是「AI桌宠」**（`CFBundleDisplayName` + 文件名），用户看到的不变。

### 4.4 Electron `--user-data-dir` 在 app 模式下可能被忽略
实测 `open` 启动时该开关未生效（Electron 落回由 `package.json` 名字派生的默认目录）。因此启动器**显式**传入该参数，且启动器路径自解析 + 硬编码兜底双保险。

---

## 五、未完成的验证（不伪造）

### 5.1 Finder 双击（LaunchServices）在本 Agent 会话无法端到端跑通

**现象**：本会话里**任何**经 LaunchServices / launchd 派生的 Electron 进程都停在 `app.whenReady()` 之前 —— Chromium 起来了、profile 建了，但永远不 ready、不出窗口。

**逐项排除**（均为实测，非推断）：

| 假设 | 实测 | 判定 |
|---|---|---|
| 单实例锁 | 回退 `requestSingleInstanceLock()` 后照样挂 | 排除 |
| `--user-data-dir` | 去掉后照样挂 | 排除 |
| 工作目录 | `cwd=/` 下直跑完全正常 | 排除 |
| 环境变量 | launchd 作业环境与本会话差异仅 `PATH` 与若干业务变量，**无任何 Electron 相关变量** | 排除 |
| bundle 签名 / 图标 | 改用 Electron 官方打包布局（真实 Frameworks 副本 + ad-hoc 签名 + Gatekeeper `accepted`）仍挂 | 排除 |
| Electron 本身 | **Electron 自带默认应用**（不含我方任何代码）经 `open -n` 也只建 profile、不出窗口 | 排除 |
| 本机 Electron 普遍坏 | 本机 **MiniMax Code.app 本身即 Electron**，由用户从 Dock 启动后一直正常 | ⇒ 本机由**用户会话**启动 Electron 是正常的 |

**实测规律**：Electron 需由「**已接入图形会话的进程**」派生才 ready —— 本会话 shell 直接派生 ✅、经 `osascript`（Cocoa 应用）派生 ✅；launchd 作业 / LaunchServices 后台派生 ❌。本 Agent 命令经由 Electron 应用（MiniMax Code）发出，落在「后者」一侧。

**对用户的意义**：用户从 Finder 双击时，responsible party 是 Finder（用户会话），**预期正常**；但本轮**无法在此环境复现用户双击**，故 `MAC_REAL_GUI_ACCEPTANCE` 保持 **PENDING**。

**已做的兜底**：启动器内置**两段式启动** —— 阶段 A 直连 Electron；20 秒内日志未出现就绪判据则自动切阶段 B（经 `osascript` 通道重启）。全程不弹终端窗口、不弹验收界面。

### 5.2 重启 Mac 后仍可启动 —— 代理验证，真机未做

不能重启用户机器。代理证据：桌面条目是**符号链接**（文件系统实体，跨重启存活）／启动器**全绝对路径**（bundle 位置反推 + 硬编码兜底）／`--user-data-dir` 落在 `~/Library/Application Support/AI桌宠`（非临时目录）⇒ 心情与设置重启后仍在。

### 5.3 办公场景最终观感 —— 沿用 R179 口径 `PENDING`

需用户肉眼确认，未登记为最终产品验收通过。

---

## 六、边界声明

- 本轮**唯一**改动既有源码处：`src/main.js`，且仅两处**增量**（Electron 原生单实例锁 / 无 `--manifest` 时回落默认 manifest）。R177、R179 全部功能与行为不变。
- 角色素材逐字节未动；零联网、零外部 API、零新功能；未进入 V0.1；未封版。
- 未移动、未删除任何原始项目文件；本轮只做新增与原地增量。
