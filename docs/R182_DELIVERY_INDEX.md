# R182 交付索引 — 在用户 Mac 桌面创建「AI桌宠」启动快捷图标

> **生成时间**：2026-10-23
> **对应任务书**：R182（承接 R179，基线 commit `8b52aef`）
> **作者**：MiniMax（Mavis）
> **上一交付**：R179 `8b52aef`（实现 `4756fd0` / 索引 `ed8ebad` / 归档 `8b52aef`）
> **本轮实现提交**：`68b55d3`
> **状态**：`R182_DESKTOP_ICON = PASS` / **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮**只做一件事** —— 在桌面放一个能启动桌宠的图标；**零联网、零外部 API、零新功能、零新角色素材**；**所有角色素材逐字节未动**；**未移动/未删除任何原始项目文件**；**未进入 V0.1**；**未擅自封版**；办公场景仍待用户视觉确认，未登记为最终产品验收通过。

---

## 〇、本轮结论（任务书逐项给结论）

| 字段 | 结论 | 一句话依据 |
|---|---|---|
| ① 桌面显示「AI桌宠」图标，优先用原生 `.app` 启动器 | **PASS** | 桌面条目 `/Users/musk123/Desktop/AI桌宠.app` 是真 macOS app bundle（`Contents/Info.plist` + `Contents/MacOS/AIPet` + `Contents/Resources/AppIcon.icns`），指向仓库内 `_app_bundle/AI桌宠.app`（软链，零权限、跨重启存活、不会误删目标） |
| ② 双击图标直接启动当前验收通过的桌宠 | **PASS（启动器本体已实测）** | 启动器参数与验收脚本完全一致（`--manifest assets/character_R141_manifest.json --mode compact --x 600 --y 300`）；实跑：`R144 ASSETS_READY loaded=23/23` + `behavior engine started state=IDLE` + 屏上窗口 `(600,300,200,240)` |
| ③ 不弹测试界面 / 不执行验收脚本 / 不重复启动多进程 | **PASS** | 启动器与运行时日志中 `--acceptance / --preview / --demo-scene / --r177-* / --quit-after / fallback / dev_mode=true` **7 项全部命中 0 次**；单实例锁实测：第二次启动后 **进程 1→1、窗口 1→1**，日志 `R182 SECOND_INSTANCE`（聚焦已有窗口）+ `R182 SINGLE_INSTANCE`（第二实例退出码 0） |
| ④ 用现有角色形象制作图标，保持辨识度 | **PASS** | 源图 `assets/character_R138/idle/idle_00_base.png` **只读**；bust 裁切 + 冰蓝渐变底合成，**不重绘五官/发色/瞳色/服装**；256px 渲染实测：银白短发 + 冰蓝眼 + 白大褂青色内衬 + 胸前「Q」徽标均可辨 |
| ⑤ 不移动、不删除原始项目文件 | **PASS** | 本轮只**新增** `_app_bundle/AI桌宠.app/`、`110_R182_desktop_icon.py`、`112_R182_screen_ab.py`、`evidence_r182/`；`src/main.js` 为**原地增量修改**；角色素材 SHA256 未变 |
| ⑥ 重启 Mac 后桌面图标仍可正常启动 | **代理验证 PASS，真机重启未做** | 桌面条目是**文件系统实体**（符号链接）跨重启存活；启动器**全用绝对路径**（bundle 位置反推 + 硬编码兜底）；`--user-data-dir` 落在 `~/Library/Application Support/AI桌宠`（非临时目录）⇒ 心情/设置重启后仍在。**未实际重启机器，不伪造该结论** |
| ⑦ 自主完成创建、路径检查及启动验证，不要求用户操作终端 | **PASS** | 全程脚本化完成，桌面条目已落地；用户只需双击图标 |
| 客观判据 | **见下表** | 启动链路 8 项判据 + 回归 3 套全绿 |
| 单元测试 | **15/15 文件全过** | `tests/*.test.js` 逐文件执行，0 失败 |
| 回归 | **全过** | R147 e2e 真实 Electron **PASS=60 / FAIL=0**；R177 运行时验证 **34/34 PASS** |

> **但**：**Finder 双击（LaunchServices）这条路径本轮未能端到端跑通** —— 原因与本启动器无关，详见「三、诚实登记」。

---

## 一、本轮改了什么

| 文件 | 性质 | 改动 |
|---|---|---|
| `_app_bundle/AI桌宠.app/Contents/Info.plist` | 新增 | `CFBundleName/DisplayName=AI桌宠`、`CFBundleExecutable=AIPet`、`CFBundleIconFile=AppIcon`、**`LSUIElement=true`**（不弹终端、不占 Dock 位） |
| `_app_bundle/AI桌宠.app/Contents/MacOS/AIPet` | 新增 | 桌面启动器：绝对路径解析 + 启动前自检 + 两段式启动 + 就绪判据 + 日志 |
| `_app_bundle/AI桌宠.app/Contents/Resources/AppIcon.icns` | 新增 | 角色形象图标（10 档尺寸，16→1024） |
| `candidates/candidate_b_c2/110_R182_desktop_icon.py` | 新增 | 图标生成脚本（可复现；只读原素材；三色底方案对比） |
| `candidates/candidate_b_c2/112_R182_screen_ab.py` | 新增 | 屏幕取证脚本（**A/B 对照法**，见「二」） |
| `candidates/candidate_b_c2/src/main.js` | **修改** | ① Electron 原生单实例锁（`requestSingleInstanceLock` + `second-instance` 聚焦）② 无 `--manifest` 时回落到项目内默认 manifest（纯增量，`--manifest` 优先级不变） |
| `candidates/candidate_b_c2/evidence_r182/` | 新增 | 图标母版 1024 PNG + 三色底小尺寸对比图 |

---

## 二、启动验证结果（客观判据）

### 2.1 启动链路（真实 Electron，逐条取证）

| # | 判据 | 门槛 | 实测 | 结论 |
|---|---|---|---|---|
| S1 | 启动器退出码 | `0` | `0` | ✅ |
| S2 | 本地状态已加载（证明 Electron 真的 ready、窗口已建） | 日志含 `R177 LOCAL_STATE` | `dir=~/Library/Application Support/AI桌宠 mood=calm` | ✅ |
| S3 | 角色资源全部就绪 | `loaded=23/23` | `loaded=23/23 actions=idle,walk_left,walk_right,sleep_enter,sleep_loop,wake_up` | ✅ |
| S4 | 自主行为引擎已启动 | 日志含 `behavior engine started` | `state=IDLE` | ✅ |
| S5 | 屏上恰好 1 个桌宠窗口 | `= 1` | `1`，bounds `(600,300,200,240)`，`onscreen=True, alpha=0.999` | ✅ |
| S6 | 无验收/预览/故障注入开关泄漏 | 7 项模式**全部 = 0** | `--acceptance 0 / --preview 0 / --demo-scene 0 / --r177- 0 / --quit-after 0 / fallback 0 / dev_mode=true 0` | ✅ |
| S7 | 无调试文字 | `fallback` 文本命中 `0` | `0`（`DEV_MODE` 正式运行默认关闭，见 `src/renderer.js:53-61`） | ✅ |
| S8 | 第二次启动不新增进程 | 进程数 `1 → 1`、窗口数 `1 → 1` | 进程 `1→1`，窗口 `1→1`；日志 `R182 SECOND_INSTANCE 聚焦已有窗口` + `R182 SINGLE_INSTANCE …退出 (code 0)` | ✅ |

### 2.2 「角色真的显示在屏幕上」的取证方法（重要）

macOS 的 `screencapture` **抓不到透明 Electron 叠层**（Pixi 画布走 GPU layer），所以「截图里没有桌宠」**不能**证明桌宠没显示 —— 早期据此得出的判断是错的，已推翻。

改用 **A/B 对照法**（`112_R182_screen_ab.py`）：

1. **A** —— 桌宠运行中，按 WindowServer（Quartz）报告的**真实窗口坐标**截取该区域；
2. **B** —— 关掉桌宠，截取**完全相同**的区域；
3. 若 A ≠ B ⇒ 角色确实叠加显示在屏幕上（差值即角色像素）。

| # | 判据 | 门槛（门槛出处） | 实测 | 结论 |
|---|---|---|---|---|
| S9 | 角色上屏 | 变化像素 > 区域 0.5%（0.5% 足以区分抗锯齿噪声与真实角色） | **89.22%**（42827/48000，最大通道差 356） | ✅ |

### 2.3 回归

| 套件 | 结果 |
|---|---|
| node 单测（`tests/*.test.js`） | **15/15 文件全过**，0 失败 |
| R147 e2e（真实 Electron） | **PASS=60 / FAIL=0 / NOT_VERIFIED=0** |
| R177 运行时验证（真实 Electron，7 组） | **34/34 PASS**（含 F 组验收入口、G 组故障注入） |

> 新增的单实例锁与 manifest 回落**未破坏任何既有契约** —— R147 e2e 与 R177 运行时验证的判据全部仍为 PASS。

---

## 三、诚实登记（不能掩盖的部分）

### 3.1 Finder 双击（LaunchServices）路径本轮未端到端跑通 —— 且**原因不在本启动器**

**现象**：在本 Agent 会话里，**任何**经 macOS LaunchServices / launchd 派生的 Electron 进程都会停在 `app.whenReady()` 之前（Chromium 起来、建了 profile，但永远不 ready、不出窗口）。

**已排除的可能**（逐个实测，不是猜测）：

| 假设 | 实测 | 判定 |
|---|---|---|
| 是单实例锁导致 | 回退掉 `requestSingleInstanceLock()` 后 `open` 照样挂 | ❌ 排除 |
| 是 `--user-data-dir` 导致 | 去掉后 `open` 照样挂 | ❌ 排除 |
| 是工作目录导致 | `cwd=/` 下直跑完全正常 | ❌ 排除 |
| 是 `cwd`/环境变量导致 | launchd 作业环境与本会话差异仅 `PATH`/若干业务变量，无 Electron 相关变量 | ❌ 排除 |
| 是 bundle 签名/图标导致 | 改用 Electron 官方打包布局（真实 Frameworks 副本 + ad-hoc 签名 + Gatekeeper `accepted`）仍挂 | ❌ 排除 |
| 是 Electron 本身的问题 | **Electron 自带的默认应用**（不含我方任何代码）经 `open -n` 也只建 profile、不出窗口 | ❌ **排除**（⇒ 是会话级环境特性，非 Electron 普遍故障） |
| 是不是本机 Electron 普遍坏 | 本机 **MiniMax Code.app 本身就是 Electron**，由用户从 Dock 启动后一直正常运行 | ⇒ **Electron 在本机由用户会话启动是正常的** |

**实测规律**：Electron 必须由「**已接入图形会话的进程**」派生才 ready —— 从本会话的 shell 直接派生 ✅、经 `osascript`（Cocoa 应用）派生 ✅；而 launchd 作业 / LaunchServices 后台派生 ❌。本 Agent 的命令经由 Electron 应用（MiniMax Code）发出，落在「后者」一侧。

**因此**：
- **对用户**：用户在 Finder 里双击，进程的 responsible party 是 Finder（用户会话），**预期正常** —— 但本轮**无法在此环境真机复现用户双击**，故 `MAC_REAL_GUI_ACCEPTANCE` 保持 **PENDING**，不伪造结论。
- **已做的兜底**：启动器内置**两段式启动** —— 阶段 A 直连 Electron；20 秒内日志未出现就绪判据则自动切阶段 B（经 `osascript` 通道重启），全程不弹终端窗口。若阶段 A 在用户机器上也不就绪，阶段 B 会接手。

### 3.2 未做的验证（明确登记）

| 项 | 状态 | 原因 |
|---|---|---|
| 重启 Mac 后桌面图标仍可启动 | **代理验证 PASS，真机未做** | 不能重启用户机器。代理证据：桌面条目是符号链接（文件系统实体，跨重启存活）／启动器全绝对路径／user-data-dir 落在 `~/Library/Application Support` |
| Finder 双击的真实点击 | **未完成** | 见 3.1（会话级限制） |
| 办公场景最终观感 | **PENDING（沿用 R179 口径）** | 需用户肉眼确认 |

### 3.3 本轮踩到的两个真实坑（已固化进实现）

1. **LaunchServices 打不开「可执行文件名含中文」的 bundle** —— 实测 `CFBundleExecutable=AI桌宠` 时 `open` 直接报 `-600 procNotFound`；改为 ASCII 的 `AIPet` 后正常启动。**桌面显示名仍是「AI桌宠」**（`CFBundleDisplayName` + 文件名），用户看到的不变。
2. **启动器的就绪判据必须只看本轮新增日志** —— 否则会命中上一轮残留的 `R177 LOCAL_STATE` 造成假就绪；改用「启动前日志长度」做偏移。

---

## 四、交付物清单

| 交付物 | 路径 |
|---|---|
| **桌面图标（本轮主交付）** | `/Users/musk123/Desktop/AI桌宠.app` |
| 图标 bundle（仓库内真身） | `_app_bundle/AI桌宠.app/` |
| 启动器 | `_app_bundle/AI桌宠.app/Contents/MacOS/AIPet` |
| 图标源 | `_app_bundle/AI桌宠.app/Contents/Resources/AppIcon.icns` |
| 图标生成脚本 | `candidates/candidate_b_c2/110_R182_desktop_icon.py` |
| 屏幕 A/B 取证脚本 | `candidates/candidate_b_c2/112_R182_screen_ab.py` |
| 运行时日志 | `~/Library/Logs/AI桌宠/launcher.log` |
| 本地状态目录 | `~/Library/Application Support/AI桌宠/` |

### SHA256（最终值）

```
<AppIcon.icns>          = 08b6159801237a35b83b3c9f2cb5934633fdfbd7b840bddd8227aa8692879af3
<AIPet>                 = 06b916a76d36591cb59e06c436ecb14c456a03f8e191ef03637b8193a1c2153d
<Info.plist>            = d2dce45ddbc8917f5dbecface0c33afa7a41d9094c932411c0acdc10e0483f8c
<AppIcon_1024.png>      = 8826a6d6a563552806ef035baff5a26090573c897ad5de2bc7a476b96738dbff
<AI桌宠.app 目录清单>   = 3cf4800201a3065ecced09fa42ce227a8dbb4b9b5888b03ca6f49508e851de20
```

---

## 五、边界声明

- 本轮**唯一**改动既有源码的地方是 `src/main.js`，且仅两处**增量**（单实例锁 + manifest 回落），R177/R179 全部功能与行为不变。
- 角色素材 `assets/character_R138/idle/idle_00_base.png` **逐字节未动**（SHA256 `09141caf2b5b091ebd6f9a61c85a881976f87c4ce62cbb63017e57c88dd73aee`）。
- 零联网、零外部 API、零新功能、未进入 V0.1、未封版。
