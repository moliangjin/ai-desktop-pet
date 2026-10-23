# R179 交付索引 — R177 独立审查问题修复（验收入口 / 精力计算 / 设置保存状态）

> **生成时间**：2026-10-23
> **对应任务书**：R179（承接 R177，基线 commit `655e446`）
> **作者**：MiniMax（Mavis）
> **上一交付**：R177 `655e446`（实现 `4e976bd` / 索引 `68d24d6` / 归档 `655e446`）
> **本轮实现提交**：`4756fd0`
> **状态**：`R179_FIXES = PASS` / **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮**只修 R177 独立审查点名的三个问题**（外加一个同类问题的顺带修复）；**零联网、零 AI 调用、零充值 i2i、零新角色素材**；**R177 已完成的全部功能保留且行为不变**；**所有角色素材逐字节未动**；**未进入 V0.1**；**未擅自封版**；**办公场景仍待用户视觉确认，未登记为最终产品验收通过**。

---

## 〇、本轮结论（任务书逐项给结论）

| 字段 | 结论 | 一句话依据 |
|---|---|---|
| ① 修复 Mac 一键验收入口（相对路径 `src/main.js` 导致 Finder 双击起不来） | **PASS** | 改用绝对路径 `$CAND/src/main.js` + 启动前自检 + **启动判据**；从 `one_click_test/` 实跑：**资源 23/23 就绪、行为引擎启动、自动进入办公场景、退出码 0**；判据 `F1~F4` 全过 |
| ② 验证 Finder 双击后确实可以启动桌宠 | **PASS** | 新增 `--smoke`/`--skip-auto` 自动化模式：脚本自报「✅ 启动判据: 资源就绪 (R144 ASSETS_READY)」，真实运行日志 `loaded=23/23` |
| ③ 修复心情精力计算（按累计清醒时长重复扣除） | **PASS** | 改成按**时间增量**扣；独立复现：已清醒 1 小时 + 每 30s 刷新 → 修复前**第 18 次归零**，修复后 10 分钟仍是 **0.9417**（理论 0.941667）；新增 `M17~M20` |
| ④ 连续运行的回归测试 | **PASS** | `M17`：1 小时清醒 + 20 次 30s 刷新 ⇒ 0.9417 不归零；`M20`：单次 100 小时跳变只扣 6 小时上限 |
| ⑤ 重启恢复的回归测试 | **PASS** | `M18`：恢复后精力 = 保存值；恢复后再过 30s 只扣 30 秒的量；重启本身不额外扣 |
| ⑥ 修复设置保存失败仍返回 `ok:true` | **PASS** | 落盘失败 ⇒ `ok:false` + 错误原因 + **不应用**到运行时 + **不改**内存设置；面板显示「保存失败（设置未改动）」并把控件重画回真实状态 |
| ⑦ 保证失败时不误导用户 | **PASS（故障注入实测）** | 判据 `G1~G4`：`SETTINGS_SAVE_FAILED` / `ok=false` / 设置保持原值 / 磁盘无文件 |
| 保留 R177 功能、素材与原有行为系统 | **PASS** | 心情/菜单/设置面板/本地保存全部保留；素材逐字节未动；行为引擎只改精力与设置相关纯逻辑 |
| 不接入外部 API / 不重新生成角色 / 不开发无关功能 / 不进 V0.1 | **PASS** | 只改 5 个源文件 + 3 个测试/脚本；零网络调用；零生图；零版本号动作 |
| 客观判据 | **34/34 PASS（真实 Electron）** | `100_R177_runtime_verify.py`：A/C/D/E/**F**/**G**/B 共 7 组，其中 F、G 为本轮新增 |
| 单元测试 | **3 文件 / 54 断言 全过** | 心情 20（+4）+ 设置存储 18（+4）+ 菜单与设置 16 |
| 回归 | **全过** | node 全量 15 文件；R147 e2e 真实 Electron PASS=60 FAIL=0；R167 15/15；R165 18/18；R173 26/26 |

> **但**：沙箱内无法代替你在 Mac 上看最终观感 ⇒ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`**，未伪造任何真机结论。

---

## 一、本轮改了什么（5 个源文件）

| 文件 | 改动 |
|---|---|
| `one_click_test/run_r177_acceptance.sh` | 绝对路径启动主程序 + 存在性自检 + 启动判据 + `--smoke`/`--skip-auto` + `PET_USER_DATA_DIR` 隔离 |
| `src/mood_engine.js` | 精力改按**时间增量**结算（新增 `lastEnergyAt`）；睡眠期间不扣；睡醒对齐基准；单次扣除上限 6 小时；`lastEnergyAt` 随状态持久化 |
| `src/settings_store.js` | 新增 `commitSettings()`：落盘成功/失败两条明确出口 |
| `src/main.js` | `applySettingsPatch()` 用 `commitSettings`，失败不应用不改内存；`settings-set` 的 `ok` 严格等于落盘成功；`applyLaunchAtLogin()` 返回真实结果并回传；新增 `--r177-fault-settings` 故障注入开关 |
| `src/settings_panel.js` | 保存失败显示「保存失败（设置未改动）：<原因>」并把控件重画回真实状态；开机自启未生效时如实说明 |

**未改动**：任何角色素材、`behavior_engine.js` 的状态机分支、`action_library.js`、`renderer.js` 的动画与交互路径。

---

## 二、交付路径

| 项 | 路径 |
|---|---|
| 质量报告 | `docs/R179_QA_REPORT.md` |
| 交付索引（本文件） | `docs/R179_DELIVERY_INDEX.md` |
| **Mac 一键验收入口** | `one_click_test/R177_验收入口.command`（Finder 双击）/ `one_click_test/run_r177_acceptance.sh` |
| 运行时验证脚本 | `candidates/candidate_b_c2/100_R177_runtime_verify.py`（本轮扩到 34 项） |
| 运行时验证证据 | `candidates/candidate_b_c2/evidence_r177_runtime/`（A~G 共 7 份真实日志 + 判据 JSON） |
| 打包器 | `candidates/candidate_b_c2/102_R179_package.py` |
| 轻量审查包 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R179_review.zip` |
| 审查包 SHA256 | `__REVIEW_SHA256__`（同时写在该 zip 旁的 `.sha256` 文件） |
| 完整备份 | `backup/V0.0_backup_20261023_xxxxxx_r179.zip` |
| 备份 SHA256 | `__BACKUP_SHA256__` |

---

## 三、复审要点（按顺序）

```bash
cd candidates/candidate_b_c2

# ① 单元测试 (54 断言)
node tests/r177_mood_engine.test.js       # 20 (含 M17~M20 精力回归)
node tests/r177_settings_store.test.js    # 18 (含 S15~S18 保存失败回归)
node tests/r177_menu_settings.test.js     # 16

# ② 真实 Electron 运行时验证 (34 项, 含 F 验收入口启动 + G 保存失败故障注入)
python3 100_R177_runtime_verify.py

# ③ 真实 Electron 全量回归
bash R147_e2e_test.sh

# ④ 单独验证"验收入口能启动桌宠"(等价于 Finder 双击)
bash ../one_click_test/run_r177_acceptance.sh --skip-auto --smoke
```

---

## 四、提交链

| # | 提交 | 内容 |
|---|---|---|
| 1 | `4756fd0` | 实现提交：验收入口绝对路径 + 启动判据 / 精力增量结算 / `commitSettings` + 保存失败如实反馈 / 开机自启真实结果回传 / 新增 `M17~M20`、`S15~S18` 与 F、G 两组运行时判据 |
| 2 | `__INDEX_COMMIT__` | 交付索引提交：本文件 + `docs/R179_QA_REPORT.md` |
| 3 | 本提交（归档） | 交付归档提交：审查包与 SHA256 指向最终值 |

---

## 五、如实登记的已知限制

1. **开机自动启动在开发态（从源码跑）必然失败** —— macOS 要求打包后的 `.app`；面板会如实提示，但真机验证需打包版本。
2. **精力衰减是线性模型**（每小时 −0.05），无"越累掉越快"的曲线；刻意保持简单。
3. **精力目前只作可见状态展示**（设置面板进度条），尚未参与心情评分 —— 改了会动到已有判定，本轮不动。
4. **单次精力扣除上限 6 小时** ⇒ 关机一整夜的消耗只算 6 小时。
5. `MAC_REAL_GUI_ACCEPTANCE = PENDING`。
6. **办公场景仍待用户视觉确认，未登记为最终产品验收通过。**
7. 本轮新增 1 个验收专用开关 `--r177-fault-settings`（故障注入用，沿用仓库既有 `--demo-scene`/`--acceptance` 惯例），正式运行不触发。
