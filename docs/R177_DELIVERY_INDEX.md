# R177 交付索引 — 纯离线体验增强（本地心情 / 控制菜单 / 设置面板 / 本地保存）

> **生成时间**：2026-10-23
> **对应任务书**：R177（承接 R173，基线 commit `080aaaf`）
> **作者**：MiniMax（Mavis）
> **上一交付**：R173 `080aaaf`（实现 `65d5d64` / 索引 `dfe1c6a` / 归档 `080aaaf`）
> **本轮实现提交**：`17f460f`
> **状态**：`R177_FEATURES = PASS` / **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮**只做任务书点名的纯离线体验增强**；**零联网、零 AI 调用、零充值 i2i、零新角色素材**；**未进入 V0.1**；**未改动任何角色素材**（`assets/character_R138/`、`character_R153/`、`character_R156/`、`character_R158/`、`character_R172/`、`character_R173/` 全部逐字节未动）；**未改动既有点击动作、吃水果、睡眠、办公场景与 R113 拖拽核心**；**办公场景仍待用户视觉确认，未登记为最终产品验收通过**。

---

## 〇、本轮结论（任务书逐项给结论）

| 字段 | 结论 | 一句话依据 |
|---|---|---|
| ① 本地性格与心情系统（开心/平静/困倦/无聊） | **PASS** | `mood_engine.js` 纯规则四分数判定，**可复算无随机**；单测 16 项全过（含 M7 同样事件序列必得同样心情） |
| ② 心情影响角色动作 / 互动反馈 / 自主活动频率 | **PASS** | 自主决策间隔系数 0.6~1.5、7 类活动权重系数、点击动作池权重（困倦 ⇒ 偏轻量动作，**但点击永远有反馈**）；单测 `M8/M9/M10/M11` + `C12/C15` 逐项断言 |
| ③ 不调用 AI、**不用预设聊天文字冒充 AI 人格** | **PASS** | 心情**不产生任何台词**；单测 `M16` 断言引擎原型与模块导出中**不存在** `say/chat/talk/reply/respond/dialog/speak/quote/message/text/script` 任一命名，且源码无网络调用 |
| ④ 右键菜单可手动触发 6 个动作 | **PASS** | `menu_template.js` 精确含 睡觉/醒来/坐沙发休息/电脑办公/吃水果/随机可爱动作 + 设置 + 退出；单测 `C1/C2/C4/C5` |
| ⑤ **所有功能使用现有正式行为系统**，不允许只播演示图片 | **PASS** | `BehaviorEngine.command()` 调用自主决策**同一批**内部方法；单测 `C6/C7`（状态真的切换 + 动作真的下发）、`C9`（接管排程）、`C10`（不受同类冷却）、`C11`（转移原因与自主决策一致 = `idle-decision`）；**真实 Electron**：`MENU command=work ok=true state=WORK` + `IDLE -> WORK` + `set-action work applied=true`，吃水果挂载 `prop_stool,prop_fruit_table`，睡觉挂载 `prop_bed,prop_moon,prop_quilt` |
| ⑥ 设置面板 5 项 | **PASS** | 独立窗口 340×486，不叠桌宠、无调试项；大小/活动频率/睡眠频率/点击反馈/开机自启逐项落到运行时（真实 Electron 判据 A9~A12） |
| ⑦ 开机自动启动「仅在系统权限与实现条件允许时提供」 | **PASS** | 仅 darwin/win32 提供（`canLaunchAtLogin()`），Linux 面板开关置灰并写明原因；失败只记录不崩 |
| ⑧ 设置简单、**不让调试界面污染桌宠外观** | **PASS** | 设置在独立窗口；右键菜单只有 8 个正式项 + 1 个只读心情项，单测 `C4` 断言可点击项集合无越界、label 无调试字样 |
| ⑨ 本地存储设置与基础心情状态 | **PASS** | `userData/pet_settings.json` + `pet_mood_state.json`；原子写；损坏回退默认值不抛异常（单测 `S6/S7/S10`） |
| ⑩ 重启程序后正确恢复 | **PASS（真实 Electron 实测）** | 重启后设置逐字段恢复、心情状态 = 启动时磁盘文件逐字段一致、大小与频率仍生效（判据 B1~B5） |
| ⑪ 不联网、不上传、不冒充 AI 长期记忆 | **PASS** | 单测 `S13` 扫描源码断言无网络调用；文件与文档语义明确为"设置"与"基础心情状态" |
| ⑫ 保留既有角色/点击/吃水果/睡眠/办公场景 + R113 拖拽核心 | **PASS** | 素材逐字节未动；node 全量 15 文件全过；R147 e2e **PASS=60 FAIL=0** |
| ⑬ 不再生成角色图片 / 不充值 i2i / 不进 V0.1 / V0.0 不擅自封版 | **PASS** | 本轮零生图调用、零 i2i、零版本号动作；`V0_0_RELEASE_STATUS = NOT_FROZEN` |
| ⑭ 办公场景仍待用户视觉确认 | **PASS（本轮未擅自结案）** | 报告与索引均保持 `MAC_REAL_GUI_ACCEPTANCE = PENDING`，办公场景**未**登记为最终产品验收通过 |
| 客观判据 | **26/26 PASS（真实 Electron）** | `100_R177_runtime_verify.py`：5 次真实启动，判据来自日志行 + 磁盘文件 + 实际视口尺寸 |
| 单元测试 | **3 文件 / 46 断言 全过** | 心情引擎 16 + 设置存储 14 + 菜单与设置集成 16 |
| 回归 | **全过** | node 全量 15 文件；R147 e2e 真实 Electron PASS=60 FAIL=0；R167 15/15；R165 18/18；R173 26/26 |

> **但**：沙箱内无法代替你在 Mac 上看最终观感与真实鼠标手感 ⇒ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`**，未伪造任何真机结论。

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 新增生产源码 | `candidates/candidate_b_c2/src/mood_engine.js`、`settings_store.js`、`menu_template.js`、`settings_panel.html`、`settings_panel.js` |
| 修改生产源码 | `candidates/candidate_b_c2/src/behavior_engine.js`、`main.js`、`renderer.js`、`action_library.js` |
| 新增单元测试 | `candidates/candidate_b_c2/tests/r177_mood_engine.test.js`、`r177_settings_store.test.js`、`r177_menu_settings.test.js` |
| 运行时验证脚本 | `candidates/candidate_b_c2/100_R177_runtime_verify.py` |
| 打包器 | `candidates/candidate_b_c2/101_R177_package.py` |
| 运行时验证证据 | `candidates/candidate_b_c2/evidence_r177_runtime/`（run_A~E.log + r177_runtime_verify.json + 落盘的 pet_settings.json / pet_mood_state.json） |
| **Mac 一键验收入口** | `one_click_test/R177_验收入口.command`（Finder 双击）/ `one_click_test/run_r177_acceptance.sh` |
| 质量报告 | `docs/R177_QA_REPORT.md` |
| 交付索引（本文件） | `docs/R177_DELIVERY_INDEX.md` |
| 轻量审查包 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R177_review.zip`（206 个文件 / 23,664,163 字节） |
| 审查包 SHA256 | `cc20a80a69fef79f9aabd5a658eb55dba0320d244664fb779398852b4eed59e4`（同时写在该 zip 旁的 `character_animation_R177_review.zip.sha256`） |
| 完整备份 | `backup/V0.0_backup_20261023_033946_r177.zip`（288 个文件 / 52,166,305 字节） |
| 备份 SHA256 | `cf0f25c1f8cea7f2c238845223c1f6395375705bd4fb15274e8ac154735466e5` |

---

## 二、本轮怎么用的（30 秒版）

1. **右键角色** → 弹出控制菜单（睡觉 / 醒来 / 坐沙发休息 / 电脑办公 / 吃水果 / 随机可爱动作 / 设置… / 退出桌宠），顶部只读显示当前心情。
2. **菜单里点「设置…」** → 独立设置面板：桌宠大小 / 自主活动频率 / 睡眠频率 / 点击反馈 / 开机自动启动。
3. **关掉程序再打开** → 大小、频率、点击反馈开关都还在，心情接着上次。

---

## 三、复审要点（按顺序）

```bash
cd candidates/candidate_b_c2

# ① 新增单元测试 (46 项)
node tests/r177_mood_engine.test.js
node tests/r177_settings_store.test.js
node tests/r177_menu_settings.test.js

# ② 真实 Electron 运行时验证 (26 项判据, 5 次真实启动, 约 80 秒)
python3 100_R177_runtime_verify.py

# ③ 真实 Electron 全量回归
bash R147_e2e_test.sh

# ④ Mac 一键验收入口 (Finder 双击)
one_click_test/R177_验收入口.command
```

---

## 四、提交链

| # | 提交 | 内容 |
|---|---|---|
| 1 | `17f460f` | 实现提交：心情引擎 / 设置存储 / 菜单模板 / 设置面板 UI / main 接线 / renderer 改造 / 三组单测 / 运行时验证脚本 / e2e 隔离修复 |
| 2 | `ad5f375` | 交付索引提交：本文件 + `docs/R177_QA_REPORT.md` |
| 3 | 本提交（归档） | 交付归档提交：审查包与 SHA256 指向最终值 |

---

## 五、如实登记的已知限制

见 `docs/R177_QA_REPORT.md` §八，要点：

1. 「开心」判定灵敏（一次点击即开心）；
2. 深夜困倦优先级高于开心，夜里点击可能表现得很困；
3. 心情只改点击反馈的**动作权重**，不改有没有反馈；若你希望困倦时干脆不响应，需显式打开 `sleepy_suppress_click`（默认关闭）；
4. 桌宠大小是位图放大（1.6× 边缘略柔化），不是更高分辨率重绘；
5. macOS 开机自启首次可能需在「系统设置 → 通用 → 登录项」确认一次；
6. 菜单/设置面板的观感与真实鼠标手感待真机确认；
7. `MAC_REAL_GUI_ACCEPTANCE = PENDING`；
8. **办公场景仍待用户视觉确认，未登记为最终产品验收通过**；
9. 本轮新增 4 个验收专用命令行入口（沿用仓库既有 `--demo-scene`/`--acceptance` 惯例），正式运行不触发。

---

## 六、本轮修掉的 3 个真 bug（测试逼出来的）

| # | Bug | 后果 | 抓它的测试 |
|---|---|---|---|
| 1 | `MOODS[st.mood]` 用小写值查大写键 | **恢复的心情永远是「平静」**，"重启后恢复心情"静默失效 | `M12` |
| 2 | `main.js` 读 `fx.sleep`，实际键名是 `fx.sleep_weight` | **「睡眠频率」设置完全不起作用** | `S11` |
| 3 | `--user-data-dir <path>`（两参数写法）被 Electron 静默忽略 | 设置写到默认用户目录；e2e/验证的隔离前提失效 | 真实判据 `A1` |

附带修掉的**产品级隐患**：`R147_e2e_test.sh` 原来用默认 userData 目录 ⇒ **用户自己的设置会让 e2e 判据崩溃**（`pet_scale≠1` → 采集帧尺寸对不上 → 判据脚本抛异常；`click_feedback=false` → 点击池随机性判据必然 FAIL）。本轮已把 e2e 的 4 处启动全部改为临时 user-data-dir。
