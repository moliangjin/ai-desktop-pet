# R182 交付索引 — 在用户 Mac 桌面创建「AI桌宠」启动快捷图标

> **生成时间**：2026-10-23（含同日「桌面上没找到」返工修订）
> **对应任务书**：R182（承接 R179，基线 commit `8b52aef`）
> **作者**：MiniMax（Mavis）
> **上一交付**：R179 `8b52aef`（实现 `4756fd0` / 索引 `ed8ebad` / 归档 `8b52aef`）
> **本轮实现提交**：`68b55d3` → 返工补充提交见「三、提交链」
> **状态**：`R182_DESKTOP_ICON = PASS` / **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮**只做一件事** —— 在桌面放一个能启动桌宠的图标；**零联网、零外部 API、零新功能、零新角色素材**；**所有角色素材逐字节未动**；**未移动/未删除任何原始项目文件**；**未进入 V0.1**；**未擅自封版**；办公场景仍待用户视觉确认，未登记为最终产品验收通过。

---

## 〇、本轮结论（任务书逐项给结论）

| 字段 | 结论 | 一句话依据 |
|---|---|---|
| ① 桌面显示「AI桌宠」图标，优先用原生 `.app` 启动器 | **PASS** | 桌面条目 `/Users/musk123/Desktop/AI桌宠.app` 是**真 macOS app bundle**（`Contents/Info.plist` + `Contents/MacOS/AIPet` 委托脚本 + `Contents/Resources/AppIcon.icns`），Finder 桌面项坐标 `(1165,46)`、bounds `(1133,14)-(1197,78)` ⇒ **Finder 确实给它排了网格槽位、确实会画出来**（对比：符号链接时期坐标是 `{-1,-1}` = 不画） |
| ② 双击图标直接启动当前验收通过的桌宠 | **PASS（`open` 端到端实测通过）** | `open "/Users/musk123/Desktop/AI桌宠.app"` 实跑：阶段 A **1 秒**就绪 → `R177 LOCAL_STATE` → `R144 ASSETS_READY loaded=23/23` → `behavior engine started state=IDLE` → 屏上窗口 `(600,300,200,240)` onscreen=True |
| ③ 不弹测试界面 / 不执行验收脚本 / 不重复启动多进程 | **PASS** | 7 项验收开关泄漏检查**全部命中 0 次**；二次双击实测日志 `R182 SECOND_INSTANCE 聚焦已有窗口` + `R182 SINGLE_INSTANCE 退出 (code 0)`，**进程数 1→1、窗口数 1→1** |
| ④ 用现有角色形象制作图标，保持辨识度 | **PASS** | 源图 `assets/character_R138/idle/idle_00_base.png` **只读**；bust 裁切 + 冰蓝渐变底合成，**不重绘五官/发色/瞳色/服装**；AppKit 按 Finder 同源图标资源渲染实测：银白短发 + 冰蓝眼 + 白大褂青色内衬 + 胸前「Q」徽标均可辨 |
| ⑤ 不移动、不删除原始项目文件 | **PASS** | 本轮只**新增** `_app_bundle/AI桌宠.app/`、`110/112/113/114_R182_*.{py,sh}`、`evidence_r182/`；`src/main.js` 为**原地增量修改**；角色素材 SHA256 未变 |
| ⑥ 重启 Mac 后桌面图标仍可正常启动 | **代理验证 PASS，真机重启未做** | 坐标已落盘进 `~/Desktop/.DS_Store` 的 `Iloc` 记录（**实测 Finder 完全重启后坐标不变**）；桌面条目是文件系统实体跨重启存活；启动器**全用绝对路径**；`--user-data-dir` 落在 `~/Library/Application Support/AI桌宠`（非临时目录）⇒ 心情/设置重启后仍在。**未实际重启机器，不伪造该结论** |
| ⑦ 自主完成创建、路径检查及启动验证，不要求用户操作终端 | **PASS** | 全程脚本化完成（`113_R182_install_desktop_icon.sh` 一条命令即可复现）；用户只需双击图标 |
| 客观判据 | **见下表** | 启动链路 12 项判据 + 桌面可见性 3 项判据 + 回归 3 套全绿 |
| 单元测试 | **15/15 文件全过** | `tests/*.test.js` 逐文件执行，0 失败 |
| 回归 | **全过** | R147 e2e 真实 Electron **PASS=60 / FAIL=0**；R177 运行时验证 **34/34 PASS** |

---

## 一、本轮改了什么

| 文件 | 性质 | 改动 |
|---|---|---|
| `_app_bundle/AI桌宠.app/Contents/Info.plist` | 新增 | `CFBundleName/DisplayName=AI桌宠`、`CFBundleExecutable=AIPet`、`CFBundleIconFile=AppIcon`、**`LSUIElement=true`**（不弹终端、不占 Dock 位） |
| `_app_bundle/AI桌宠.app/Contents/MacOS/AIPet` | 新增 | 桌面启动器：绝对路径解析 + 启动前自检 + 两段式启动 + 就绪判据 + 日志（返工修了 3 个 bug，见「三.3」） |
| `_app_bundle/AI桌宠.app/Contents/Resources/AppIcon.icns` | 新增 | 角色形象图标（10 档尺寸，16→1024） |
| `candidates/candidate_b_c2/110_R182_desktop_icon.py` | 新增 | 图标生成脚本（可复现；只读原素材；三色底方案对比） |
| `candidates/candidate_b_c2/112_R182_screen_ab.py` | 新增 | 屏幕取证脚本（**A/B 对照法**，见「二.2」） |
| `candidates/candidate_b_c2/113_R182_install_desktop_icon.sh` | 新增（返工） | 桌面项**一键安装 + 定位 + 落盘校验 + Finder 重启持久化校验 + 冒烟**的可复现脚本 |
| `candidates/candidate_b_c2/114_R182_desktop_icon_proof.py` | 新增（返工） | 桌面图标"落地证据"渲染器：AppKit 按系统图标资源渲染 + 生成桌面位置示意图 |
| `candidates/candidate_b_c2/src/main.js` | **修改** | ① Electron 原生单实例锁（`requestSingleInstanceLock` + `second-instance` 聚焦）② 无 `--manifest` 时回落到项目内默认 manifest（纯增量，`--manifest` 优先级不变） |
| `candidates/candidate_b_c2/evidence_r182/` | 新增 | 图标母版 1024 PNG + 三色底小尺寸对比图 + **桌面图标渲染 128/64px** + **桌面位置示意图** |

> **桌面项形态说明**：桌面上的 `AI桌宠.app` 是**仓库 bundle 的拷贝**（`Info.plist` + `AppIcon.icns` 原样拷贝，`MacOS/AIPet` 是一份 302 字节的**委托脚本**，`exec` 到仓库内那一份正式启动器）。这样做的原因见「三.2」；启动逻辑只有仓库内一份真身，不会两边跑偏。

---

## 二、启动验证结果（客观判据）

### 2.1 启动链路（真实 Electron，逐条取证）

| # | 判据 | 门槛 | 实测 | 结论 |
|---|---|---|---|---|
| S1 | 启动器退出码 | `0` | `0` | ✅ |
| S2 | 本地状态已加载（证明 Electron 真的 ready、窗口已建） | 日志含 `R177 LOCAL_STATE` | `dir=~/Library/Application Support/AI桌宠 mood=calm` | ✅ |
| S3 | 角色资源全部就绪 | `loaded=23/23` | `loaded=23/23 actions=idle,walk_left,walk_right,sleep_enter,sleep_loop,wake_up` | ✅ |
| S4 | 自主行为引擎已启动 | 日志含 `behavior engine started` | `state=IDLE`，随后 `IDLE → WORK → IDLE` 自主运转 | ✅ |
| S5 | 屏上恰好 1 个桌宠窗口 | `= 1` | `1`，bounds `(600,300,200,240)`，`onscreen=True, alpha=0.999` | ✅ |
| S6 | 无验收/预览/故障注入开关泄漏 | 7 项模式**全部 = 0** | `--acceptance 0 / --preview 0 / --demo-scene 0 / --r177- 0 / --quit-after 0 / fallback 0 / dev_mode=true 0` | ✅ |
| S7 | 无调试文字 | `fallback` 文本命中 `0` | `0`（`DEV_MODE` 正式运行默认关闭，见 `src/renderer.js:53-61`） | ✅ |
| S8 | 第二次启动不新增进程 | 进程数 `1 → 1`、窗口数 `1 → 1` | 进程 `1→1`，窗口 `1→1`；日志 `R182 SECOND_INSTANCE 聚焦已有窗口` + `R182 SINGLE_INSTANCE …退出 (code 0)` | ✅ |
| **S9** | **`open` 桌面图标能启动（Finder 双击同一条 LaunchServices 通路）** | 日志出现就绪判据 + 进程数 `=1` | `open "/Users/musk123/Desktop/AI桌宠.app"` → **阶段 A 1 秒成功 (pid=33128)**，`R144 ASSETS_READY loaded=23/23`，主进程数 `1` | ✅ |
| **S10** | **桌面项是"会被画出来"的真 bundle** | Finder 坐标 ≠ `{-1,-1}` | `position=(1165,46)`、`bounds=(1133,14)-(1197,78)`（符号链接时期是 `{-1,-1}` = 桌面不画） | ✅ |
| **S11** | **坐标已落盘，重启后不丢** | `~/Desktop/.DS_Store` 含 `AI桌宠.app` 的 `Iloc` 记录 **且** Finder 完全重启后坐标不变 | `.DS_Store` 命中 `AI桌宠.app`(UTF-16BE)；`killall Finder` 后复读仍为 `(1165,46)` | ✅ |

### 2.2 「角色真的显示在屏幕上」的取证方法（重要）

macOS 的 `screencapture` **抓不到透明 Electron 叠层**（Pixi 画布走 GPU layer），所以「截图里没有桌宠」**不能**证明桌宠没显示 —— 早期据此得出的判断是错的，已推翻。

改用 **A/B 对照法**（`112_R182_screen_ab.py`）：

1. **A** —— 桌宠运行中，按 WindowServer（Quartz）报告的**真实窗口坐标**截取该区域；
2. **B** —— 关掉桌宠，截取**完全相同**的区域；
3. 若 A ≠ B ⇒ 角色确实叠加显示在屏幕上（差值即角色像素）。

| # | 判据 | 门槛（门槛出处） | 实测 | 结论 |
|---|---|---|---|---|
| S12 | 角色上屏 | 变化像素 > 区域 0.5%（0.5% 足以区分抗锯齿噪声与真实角色） | **89.22%**（42827/48000，最大通道差 356） | ✅ |

### 2.3 「桌面图标真的画出来了」的取证方法（返工新增）

`screencapture` 在本机会话里**也抓不到 Finder 的桌面图标层**（桌面窗口 layer = `-2147483603`）—— 实测全屏截图里原有 36 个桌面图标**全部不可见**，所以截图**不能**作为桌面图标显示的证据。改用两条独立证据：

| # | 判据 | 方法 | 实测 |
|---|---|---|---|
| S10 | Finder 给它排了网格槽位 | `tell application "Finder" to get {name, position, bounds} of item "AI桌宠.app" of desktop` | `(1165,46)` / `(1133,14)-(1197,78)`；对照组：同法查已正常显示的 `面试.xlsx` 得到 `65,158` |
| S13 | 图标资源与画出来的一致 | `NSWorkspace.sharedWorkspace().iconForFile_("~/Desktop/AI桌宠.app")` —— 走系统图标缓存，与 Finder 画的是同一份资源 | 渲染出银白短发 / 冰蓝眼 / 白大褂 + 青色内衬 / 胸前「Q」徽标，**与角色形象一致**；产物 `evidence_r182/桌面图标_渲染_128.png` |
| S14 | 位置示意 | 按 Finder 上报的坐标合成到 1920×1080 底图 | `evidence_r182/桌面位置示意.png`：图标落在**菜单栏正下方、偏右**，在所有已打开窗口之外 |

### 2.4 回归

| 套件 | 结果 |
|---|---|
| node 单测（`tests/*.test.js`） | **15/15 文件全过**，0 失败 |
| R147 e2e（真实 Electron） | **PASS=60 / FAIL=0 / NOT_VERIFIED=0** |
| R177 运行时验证（真实 Electron，7 组） | **34/34 PASS**（含 F 组验收入口、G 组故障注入） |

> 新增的单实例锁与 manifest 回落**未破坏任何既有契约** —— R147 e2e 与 R177 运行时验证的判据全部仍为 PASS。

---

## 三、本轮踩到并已固化的坑

### 3.1 符号链接做桌面 `.app` 入口 ⇒ 桌面**根本不画它**

**现象**：桌面放符号链接时，Finder 报它的坐标是 `{-1,-1}`（=「没有位置」）⇒ **桌面上看不见**。这就是用户反馈「桌面上没找到啊」的第一层根因。

**判定**：桌面这一份必须是**真 app bundle**（Finder 才会正常排位 + 画图标）。已改为在桌面放真 bundle（`Info.plist` + `MacOS/AIPet` 委托脚本 + `AppIcon.icns`），启动逻辑仍委托仓库内那一份（单一真身）。

### 3.2 桌面网格**溢出屏幕** + 已打开的窗口**整个盖住**图标区

**现象**：该机桌面是 `arrangeBy = dateAdded` 排序，网格**溢出屏幕**（有条目落在 `y=1054`，屏幕只有 1080 高）⇒ 新增条目会被排到屏幕外。

**叠加问题**：实测桌面网格**只占 x=65~395 四列**（42 个桌面项里有 7 个外置磁盘图标由 macOS 固定画在右上角，报 `{-1,-1}` 属正常），而 **x=8~928 / y=46~538 这片区域被两个已打开的 Finder 窗口整个盖住** ⇒ 图标就算画了也看不见。

**修法**：`F_SETADDTIME`（改「添加日期」）在现代 macOS/APFS 上**已失效**（多种布局均 EINVAL），所以改用 Finder API 显式定位到**空闲列 + 无遮挡**的槽位 **`(1165,46)`**（屏幕 1920×1080 逻辑像素）。

**顺带实测**：设在空列的第 2 行（如 `1165,158`）时，Finder 重启会把图标归位到该列首行 ⇒ 空列只认首行，脚本直接写首行坐标。

### 3.3 ⭐ 坐标是**延迟落盘**的，Finder 重启太快 ⇒ 坐标退回 `{-1,-1}`，图标又消失

**这是最隐蔽的一个**：桌面图标坐标写在 **`~/Desktop/.DS_Store` 的 `Iloc` 记录**里（文件名以 **UTF-16BE** 存储）。实测落盘延迟 **≈6 秒**。

**失败链**：装好桌面项 → `set position` → **6 秒后 `killall Finder`** → 坐标从未写进 `.DS_Store` ⇒ 重启后回到 `{-1,-1}`、bounds 退化成 `(-33,-33)-(31,31)` ⇒ **图标又不会被画出来**。

**验证方法（已固化进脚本）**：
1. 设完位置后**轮询** `~/Desktop/.DS_Store`，直到命中 `AI桌宠.app` 的 UTF-16BE 记录（最多 60 秒）；
2. 再 `killall Finder` + 复读坐标，**两次都通过**才算位置真的持久化。

### 3.4 `CFBundleExecutable` 不能含中文

实测 `CFBundleExecutable=AI桌宠` 时 `open` 直接报 `NSOSStatusErrorDomain Code=-600 "procNotFound"`；改为 ASCII 的 `AIPet` 后正常启动。**桌面显示名仍是「AI桌宠」**（`CFBundleDisplayName` + 文件名），用户看到的不变。

### 3.5 启动器就绪判据必须只看本轮新增日志

否则会命中上一轮残留的 `R177 LOCAL_STATE` 造成假就绪；改用「启动前日志长度」做偏移。**且日志文件首启时不存在**，`tail -c "+1"` 读不到内容 ⇒ 偏移为 0 时改用 `cat`。

### 3.6 阶段 B 的 `osascript do shell script` 是**同步**的

里面若 `exec`/前台等桌宠，`osascript` 会一直等桌宠退出 ⇒ 整条启动链永久阻塞。必须**后台起 + 立即返回**。

---

## 四、诚实登记（不能掩盖的部分）

### 4.1 未做的验证（明确登记）

| 项 | 状态 | 原因 |
|---|---|---|
| 重启 Mac 后桌面图标仍可启动 | **代理验证 PASS，真机未做** | 不能重启用户机器。代理证据：坐标已落盘进 `~/Desktop/.DS_Store` 的 `Iloc` 记录且 **Finder 完全重启后不变**／桌面条目是文件系统实体跨重启存活／启动器全绝对路径／user-data-dir 落在 `~/Library/Application Support` |
| 用户在 Finder 里**亲手双击** | **已用 `open` 走同一条 LaunchServices 通路验证通过**，但非亲手点击 | `open` 与 Finder 双击同走 LaunchServices → bundle 可执行文件 → 本机实测 1 秒就绪；差异仅在「谁来点」 |
| 办公场景最终观感 | **PENDING（沿用 R179 口径）** | 需用户肉眼确认 |
| 桌面图标的**屏幕像素**截图 | **无法提供** | `screencapture` 抓不到 Finder 桌面图标层（原有 36 个图标同样不可见）。改用 AppKit 同源渲染 + Finder 坐标双证据（S10/S13/S14） |

### 4.2 会话级限制（已定位，与本启动器无关）

早期排查发现：本 Agent 会话里，**任何经 launchd 作业派生**的 Electron 进程都会停在 `app.whenReady()` 之前（Electron 自带默认应用同样如此 ⇒ 非 Electron 普遍故障，而是「是否已接入图形会话」的问题）。

**关键澄清**：本轮桌面项的 `CFBundleExecutable` 是**一份 shell 脚本**（委托到仓库启动器），Electron 是 LaunchServices 派生进程的**孙进程** ⇒ 落在「已接入图形会话」一侧 ⇒ **实测正常**（S9）。两段式启动（阶段 A 直连 / 阶段 B 走 `osascript` 通道）作为兜底保留。

### 4.3 边界

- 本轮**唯一**改动既有源码的地方是 `src/main.js`，且仅两处**增量**（单实例锁 + manifest 回落），R177/R179 全部功能与行为不变。
- 角色素材 `assets/character_R138/idle/idle_00_base.png` **逐字节未动**（SHA256 `09141caf2b5b091ebd6f9a61c85a881976f87c4ce62cbb63017e57c88dd73aee`）。
- 桌面项是**仓库 bundle 的拷贝** ⇒ 若仓库 bundle 之后改动，桌面副本会滞后（启动逻辑已用委托脚本规避，图标与 `Info.plist` 仍是拷贝）。重跑 `113_R182_install_desktop_icon.sh` 即可同步。
- `_app_bundle/PetCandidateA.app/Contents/MacOS/PetCandidateA` 与 `Contents/_CodeSignature/` 的改动是 **10 月 13–15 日早前轮次的遗留**（mtime 分别为 10-15 19:40 / 10-13），**不属本轮**，未纳入本轮提交，也未动它。
- 零联网、零外部 API、零新功能、未进入 V0.1、未封版。

---

## 五、交付物清单

| 交付物 | 路径 |
|---|---|
| **桌面图标（本轮主交付）** | `/Users/musk123/Desktop/AI桌宠.app` |
| 桌面图标屏幕坐标 | `(1165, 46)`，bounds `(1133,14)-(1197,78)`（屏幕 1920×1080） |
| 图标 bundle（仓库内真身） | `_app_bundle/AI桌宠.app/` |
| 启动器（仓库内真身） | `_app_bundle/AI桌宠.app/Contents/MacOS/AIPet` |
| 桌面项委托脚本 | `/Users/musk123/Desktop/AI桌宠.app/Contents/MacOS/AIPet`（302 字节，exec 到上面那份） |
| 图标源 | `_app_bundle/AI桌宠.app/Contents/Resources/AppIcon.icns` |
| 图标生成脚本 | `candidates/candidate_b_c2/110_R182_desktop_icon.py` |
| 屏幕 A/B 取证脚本 | `candidates/candidate_b_c2/112_R182_screen_ab.py` |
| **桌面项安装/校验脚本** | `candidates/candidate_b_c2/113_R182_install_desktop_icon.sh` |
| **桌面图标证据渲染脚本** | `candidates/candidate_b_c2/114_R182_desktop_icon_proof.py` |
| 桌面图标渲染证据 | `candidates/candidate_b_c2/evidence_r182/桌面图标_渲染_128.png` / `_64.png` |
| 桌面位置示意 | `candidates/candidate_b_c2/evidence_r182/桌面位置示意.png` |
| 运行时日志 | `~/Library/Logs/AI桌宠/launcher.log` |
| 本地状态目录 | `~/Library/Application Support/AI桌宠/` |
| 桌面坐标落盘处 | `~/Desktop/.DS_Store`（`Iloc` 记录，UTF-16BE 文件名） |

### SHA256（最终值）

```
<仓库 AppIcon.icns>        = 08b6159801237a35b83b3c9f2cb5934633fdfbd7b840bddd8227aa8692879af3
<仓库 AIPet>               = 5756ca734b56c755c93fee1a31a551eec0ca77f1b0543cea0b91ddf5fc0adc25
<仓库 Info.plist>          = d2dce45ddbc8917f5dbecface0c33afa7a41d9094c932411c0acdc10e0483f8c
<桌面 AppIcon.icns>        = 08b6159801237a35b83b3c9f2cb5934633fdfbd7b840bddd8227aa8692879af3
<桌面 AIPet（委托脚本）>    = 472e5cdd953f2a281b50ed9bc8fc9d66e438473c76799976d11de8917161f552
<桌面 Info.plist>          = d2dce45ddbc8917f5dbecface0c33afa7a41d9094c932411c0acdc10e0483f8c
<AppIcon_1024.png>         = 8826a6d6a563552806ef035baff5a26090573c897ad5de2bc7a476b96738dbff
<桌面图标_渲染_128.png>     = 64ab701a55c0f683ce2f9b6bc7bc6ac21bac289df4b5f1e409b17561886e27c2
<桌面图标_渲染_64.png>      = fbb2272df25cde62b70437b18c67474162da34c7ee041ab4a4f0548847952b0d
<桌面位置示意.png>          = 2c75d0f946106a0295393e27a1c33a729ea162ae08187476ab3024ea8dd3b6da
<110_R182_desktop_icon.py> = 405b463ea00a2831e602299b84d8e159ad0c62866e88653b0df768ddf6d7a2ed
<112_R182_screen_ab.py>    = 347ad04215c7b5147f0fd8da86cdfb8f6495146e52e17a7d73d78afc4ba9a7f0
<113_R182_install...sh>    = 6300e4ddc9ce1976525dbb668111d06a37e810ddf7746fca63474e331d9bd787
<114_R182_desktop_icon_proof.py> = 65f26216ce7db3a30290071777d2f996592944221de590c734cf8961d0caa231
<桌面 AI桌宠.app 目录清单>  = 72b8560bae972a8b479d8aed28199c203e03363996769ba6eb800ae5e71d2531
```

### 三、提交链

| # | 类型 | 内容 |
|---|---|---|
| 1 | 实现 | `68b55d3` — 桌面图标 + 启动器 + 图标脚本 + A/B 取证脚本 + bundle + evidence + `main.js` 单实例锁 |
| 2 | 交付索引 | `025f470` — `docs/R182_DELIVERY_INDEX.md` + `docs/R182_QA_REPORT.md` |
| 3 | 交付归档 | `aca2c2e` — SHA256 回填 |
| 4 | **实现（返工）** | 本次 — 启动器 3 个 bug 修复 + `113/114` 脚本 + 桌面项改真 bundle + 坐标定位 + 文档修订 |
