# R182 QA 报告 — 桌面「AI桌宠」启动图标

> **对应交付**：`docs/R182_DELIVERY_INDEX.md`
> **基线**：R179 `8b52aef`
> **日期**：2026-10-23（含同日「桌面上没找到」返工修订）
> **结论**：`R182_DESKTOP_ICON = PASS` ／ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** ／ `V0_0_RELEASE_STATUS = NOT_FROZEN`

---

## 一、交付物路径（最终）

```
/Users/musk123/Desktop/AI桌宠.app            ← 桌面图标（真 app bundle 拷贝）
  ├─ Contents/Info.plist                     CFBundleName/DisplayName=AI桌宠
  │                                          CFBundleExecutable=AIPet（ASCII，见 §四.4）
  │                                          CFBundleIconFile=AppIcon
  │                                          LSUIElement=true（不弹终端、不占 Dock）
  ├─ Contents/MacOS/AIPet                    302 字节委托脚本 → exec 下面那份
  └─ Contents/Resources/AppIcon.icns         角色形象图标（16→1024 共 10 档）
        │  (exec)
        ▼
<repo>/_app_bundle/AI桌宠.app/                ← 仓库内真身（启动逻辑唯一来源）
  ├─ Contents/Info.plist
  ├─ Contents/MacOS/AIPet                     桌面启动器（绝对路径 + 两段式启动）
  └─ Contents/Resources/AppIcon.icns
```

**桌面屏幕坐标**：`(1165, 46)`，bounds `(1133,14)-(1197,78)`（屏幕 1920×1080 逻辑像素）⇒ 落在**菜单栏正下方、偏右**，在所有已打开窗口之外。

> 桌面项为什么是**拷贝**而不是符号链接：符号链接在 macOS 桌面上拿不到网格槽位（Finder 报坐标 `{-1,-1}` = 不画它）。拷贝里只有 `Info.plist` + 图标是静态的，**启动逻辑靠委托脚本指向仓库那一份** ⇒ 不会出现两份逻辑跑偏。

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
| **S10 桌面项会被画出来** | Finder 坐标 ≠ `{-1,-1}` | `position=(1165,46)`、`bounds=(1133,14)-(1197,78)`（对照组：`面试.xlsx` 正常显示为 `65,158`） | ✅ |
| **S11 坐标已落盘、重启不丢** | `.DS_Store` 含 `AI桌宠.app` 的 `Iloc` 记录 **且** Finder 完全重启后坐标不变 | 命中 `AI桌宠.app`(UTF-16BE)；`killall Finder` 后复读仍 `(1165,46)` | ✅ |
| **S12 `open` 桌面图标能启动** | 日志出现就绪判据 + 主进程数 `=1` | `open "/Users/musk123/Desktop/AI桌宠.app"` → **阶段 A 1 秒成功 (pid=33128)**，`R144 ASSETS_READY loaded=23/23`，主进程 `1` | ✅ |
| **S13 图标资源与画出来的一致** | AppKit 同源渲染肉眼可辨角色特征 | `NSWorkspace.iconForFile_` 渲染出银白短发/冰蓝眼/白大褂+青色内衬/「Q」徽标 | ✅ |
| **S14 位置无遮挡** | 落点不被任何已打开窗口覆盖 | 占用窗口：Finder `(8,46,920×492)`、`(27,54,920×492)`、终端 `(1313,184,570×371)`、Finder `(1035,311,404×98)` ⇒ 落点 `(1133,14)-(1197,78)` 与之**均无交集** | ✅ |

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
| 桌面同源渲染 | `NSWorkspace.iconForFile_("~/Desktop/AI桌宠.app")` 渲染（**与 Finder 画的是同一份图标资源**）：银白短发 ✅／冰蓝眼 ✅／白大褂 + 青色内衬 ✅／胸前「Q」徽标 ✅ ⇒ 产物 `evidence_r182/桌面图标_渲染_128.png` / `_64.png` |
| 圆角 | 交付**满幅方图**，由 macOS 自 Big Sur 起的圆角遮罩自动处理（自己画圆角会变成双层圆角） |

---

## 四、本轮真实踩坑（已固化进实现）

### 4.1 `screencapture` 抓不到透明 Electron 叠层 → 早期结论被推翻
见 §2.2。**教训**：判断「窗口有没有显示」不能只看一张截图。

### 4.2 启动器的就绪判据必须只看本轮新增日志
否则会命中上一轮残留的 `R177 LOCAL_STATE` 造成**假就绪**（进而误判启动失败、误触发兜底）。改用「启动前日志长度」做偏移后修正。**且日志文件首启时不存在**，`tail -c "+1"` 读不到内容 ⇒ 偏移为 0 时改用 `cat`。

### 4.3 符号链接做桌面 `.app` 入口 ⇒ 桌面**根本不画它**
Finder 报符号链接的坐标是 `{-1,-1}`（= 没有位置）⇒ 用户看到的桌面就是"没有这个图标"。桌面这一份必须是**真 app bundle**。

### 4.4 桌面网格溢出屏幕 + 已打开的窗口盖住整个图标区
该机桌面网格**只占 x=65~395 四列**（7 个外置磁盘图标由 macOS 固定画在右上角，报 `{-1,-1}` 属正常），且 **x=8~928 / y=46~538 被两个已打开的 Finder 窗口整个盖住** ⇒ 图标画了也看不见。`F_SETADDTIME`（改「添加日期」）在现代 macOS/APFS **已失效**（EINVAL），只能改用 Finder API 显式定位到空闲且无遮挡的 `(1165,46)`。

### 4.5 ⭐ 坐标是**延迟落盘**的 ⇒ Finder 重启太快会让图标重新消失
桌面图标坐标写在 **`~/Desktop/.DS_Store` 的 `Iloc` 记录**里（文件名 **UTF-16BE**），实测落盘延迟 **≈6 秒**。装好 → `set position` → 6 秒后 `killall Finder` ⇒ 坐标从未写进 `.DS_Store` ⇒ 重启后回到 `{-1,-1}`、bounds 退化成 `(-33,-33)-(31,31)` ⇒ **图标又不会被画出来**。

**已固化的判据**（`113_R182_install_desktop_icon.sh`）：设完位置后**轮询 `.DS_Store`** 直到命中记录（≤60 秒），再 `killall Finder` + 复读坐标，**两次都过**才算持久化。

### 4.6 LaunchServices 打不开「可执行文件名含中文」的 bundle
实测 `CFBundleExecutable=AI桌宠` 时 `open` 直接报 `NSOSStatusErrorDomain Code=-600 "procNotFound: no eligible process with specified descriptor"`；改为 ASCII 的 `AIPet` 后正常。**桌面显示名仍是「AI桌宠」**（`CFBundleDisplayName` + 文件名），用户看到的不变。

### 4.7 Electron `--user-data-dir` 在 app 模式下可能被忽略
实测 `open` 启动时该开关未生效（Electron 落回由 `package.json` 名字派生的默认目录）。因此启动器**显式**传入该参数，且启动器路径自解析 + 硬编码兜底双保险。

### 4.8 阶段 B 的 `osascript do shell script` 是**同步**的
里面若 `exec`/前台等桌宠，`osascript` 会一直等桌宠退出 ⇒ 整条启动链永久阻塞。必须**后台起 + 立即返回**。

---

## 五、未完成的验证（不伪造）

### 5.1 Finder 双击（LaunchServices）—— 已用 `open` 走同一通路验证通过，但非亲手点击

**早期结论（已修正）**：本会话里**任何**经 LaunchServices / launchd 派生的 Electron 进程都停在 `app.whenReady()` 之前 —— Chromium 起来了、profile 建了，但永远不 ready、不出窗口。逐项排除（均为实测）：单实例锁 ❌排除、`--user-data-dir` ❌排除、工作目录 ❌排除、环境变量 ❌排除、bundle 签名/图标 ❌排除、**Electron 自带默认应用同样如此 ⇒ 非 Electron 普遍故障**。

**实测规律**：Electron 需由「**已接入图形会话的进程**」派生才 ready —— 本会话 shell 直接派生 ✅、经 `osascript` 派生 ✅；launchd 作业 / LaunchServices **后台**派生 ❌。

**本轮关键澄清**：桌面项的 `CFBundleExecutable` 是**一份 shell 脚本**（委托到仓库启动器），Electron 因此是 LaunchServices 派生进程的**孙进程**，落在「已接入图形会话」一侧 ⇒ **实测 `open` 端到端通过**（S12：阶段 A 1 秒就绪、23/23 资源就绪、主进程 1 个）。

**仍未做的**：用户**亲手**在 Finder 里双击。`open` 与双击同走 LaunchServices → bundle 可执行文件，差异仅在「谁来点」。故 `MAC_REAL_GUI_ACCEPTANCE` 保持 **PENDING**，不伪造结论。

**兜底保留**：启动器内置**两段式启动** —— 阶段 A 直连 Electron；20 秒内日志未出现就绪判据则自动切阶段 B（经 `osascript` 通道重启）。全程不弹终端窗口、不弹验收界面。

### 5.2 重启 Mac 后仍可启动 —— 代理验证，真机未做

不能重启用户机器。代理证据：坐标已落盘进 `~/Desktop/.DS_Store` 的 `Iloc` 记录且 **Finder 完全重启后不变**（S11）／桌面条目是文件系统实体跨重启存活／启动器**全绝对路径**（bundle 位置反推 + 硬编码兜底）／`--user-data-dir` 落在 `~/Library/Application Support/AI桌宠`（非临时目录）⇒ 心情与设置重启后仍在。

### 5.3 桌面图标的**屏幕像素**截图 —— 本机拿不到

`screencapture` 抓不到 Finder 的桌面图标层（桌面窗口 layer = `-2147483603`）：实测全屏截图里原有 36 个桌面图标**全部不可见**。故改用双证据：**Finder 坐标**（S10/S11）+ **AppKit 同源渲染**（S13）+ **位置示意**（S14）。不等于"用户肉眼确认"，不伪装。

### 5.4 办公场景最终观感 —— 沿用 R179 口径 `PENDING`

需用户肉眼确认，未登记为最终产品验收通过。

---

## 六、边界声明

- 本轮**唯一**改动既有源码处：`src/main.js`，且仅两处**增量**（Electron 原生单实例锁 / 无 `--manifest` 时回落默认 manifest）。R177、R179 全部功能与行为不变。
- 角色素材逐字节未动；零联网、零外部 API、零新功能；未进入 V0.1；未封版。
- 未移动、未删除任何原始项目文件；本轮只做新增与原地增量。
- 桌面项是**仓库 bundle 的拷贝** ⇒ 仓库 bundle 之后若改动，桌面副本会滞后（启动逻辑已用委托脚本规避；图标与 `Info.plist` 仍是拷贝）。重跑 `candidates/candidate_b_c2/113_R182_install_desktop_icon.sh` 即可同步。
- `_app_bundle/PetCandidateA.app/Contents/MacOS/PetCandidateA` 与 `Contents/_CodeSignature/` 的改动是 **10 月 13–15 日早前轮次的遗留**（mtime 分别为 10-15 19:40 / 10-13），**不属本轮**，未纳入本轮提交，也未动它。
- 清理旧桌面项一律走 `mavis-trash`（可恢复回收站），不用 `rm -rf`。
