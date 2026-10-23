# R179 质量报告 —— R177 独立审查问题修复（验收入口 / 精力计算 / 设置保存状态）

> AI 智能陪伴桌宠 V0.0 ｜ 候选实现 `candidates/candidate_b_c2/` ｜ 基线提交 `6bc4581`（R177 交付归档）
> 生成时间：2026-10-23 ｜ 主题：**R177 独立审查发现的三个实际问题**

---

## 〇、本轮结论（先给答案）

| # | 审查问题 | 结论 | 客观依据 |
|---|---|---|---|
| 1 | Mac 一键验收入口用相对路径 `src/main.js` 启动 Electron，Finder 双击起不来 | **已修复并实测** | 改用绝对路径 `$CAND/src/main.js` + 启动前存在性自检 + 启动判据；从 `one_click_test/` 目录实跑：**资源 23/23 就绪、行为引擎启动、自动进入办公场景、退出码 0**；验证脚本判据 `F1~F4` 全过 |
| 2 | 心情精力按**累计**清醒时长重复扣除 | **已修复并实测** | 改成按**时间增量**扣；独立复现脚本：已清醒 1 小时 + 每 30s 刷新 → 修复前第 **18** 次刷新归零，修复后 10 分钟仍是 **0.9417**（理论值 0.941667，完全吻合）；新增 `M17~M20` 回归测试 |
| 3 | `applySettingsPatch()` 落盘失败也可能返回 `ok:true`，界面误显示"已保存" | **已修复并实测** | 落盘失败 ⇒ `ok:false` + 明确错误原因 + **不应用**到运行时 + **不改**内存设置；面板显示"保存失败（设置未改动）：<原因>"并把控件恢复到真实状态；故障注入实测判据 `G1~G4` 全过 |

**顺带修掉的同类问题（同一根源）**：「开机自动启动」开关在系统拒绝时同样会"显示已开但没生效" —— macOS 上从源码直接跑（不是打包后的 `.app`）必然报 `Operation not permitted`。现在 `applyLaunchAtLogin()` 返回真实结果，经 `settings-get`/`settings-set` 传给面板，开关下方如实显示原因。

---

## 一、问题 1：Mac 一键验收入口起不来

### 1.1 根因

`one_click_test/run_r177_acceptance.sh` 开头 `cd "$(dirname "$0")"` ⇒ 工作目录是 `one_click_test/`，但启动 Electron 用的是**相对路径** `src/main.js`：

```
one_click_test/src/main.js   ← 不存在 (真实位置: candidates/candidate_b_c2/src/main.js)
```

所以 Finder 双击 `.command` → Electron 拿到一个不存在的入口 → 桌宠起不来。

### 1.2 修法

| 改动 | 说明 |
|---|---|
| `MAIN_JS="$CAND/src/main.js"` | 统一用绝对路径；`--manifest` 原本就是绝对路径，一致 |
| 启动前自检 | 主程序或 Electron 不存在 ⇒ 直接 `FATAL: ...` 并退出，**不再静默失败** |
| 启动判据 | 跑完 grep 真实运行日志里的 `R144 ASSETS_READY` ⇒ 明确告诉用户"桌宠确实启动了 / 没有启动" |
| `--smoke` 模式 | 桌宠只跑 8 秒，用于自动化验证"能否启动"（不进人工清单） |
| `--skip-auto` 模式 | 跳过自动化阶段，只做启动验证 |
| `PET_USER_DATA_DIR` | 自动化验证时可隔离本地数据目录（用户真跑时不设 ⇒ 用默认目录） |

### 1.3 实测（Finder 双击等价路径）

从 `one_click_test/` 目录实跑 `bash run_r177_acceptance.sh --skip-auto --smoke`：

```
[renderer] R144 assets-ready {"total":23,"loaded":23,"failed":0, ...}
[main] R144 ASSETS_READY loaded=23/23 actions=idle,walk_left,walk_right,sleep_enter,sleep_loop,wake_up
[main] R144 behavior engine started state=IDLE
[main] R141 STATE IDLE -> WORK (idle-decision) t=5492ms
[renderer] R147 set-action work applied=true
  ✅ 启动判据: 资源就绪 (R144 ASSETS_READY) —— 桌宠确实启动了
退出码: 0
```

**验证脚本判据**：`F1` 退出码 0 / `F2` 脚本自报"启动判据: 资源就绪" / `F3` 真实日志里 `R144 ASSETS_READY loaded=23/23` / `F4` 源码里不再有裸的 `src/main.js` 相对路径。

---

## 二、问题 2：心情精力被重复扣除

### 2.1 根因

`mood_engine.js` 的 `update()` 里：

```js
const awakeHours = (now - awakeSince) / 3600000;      // ← 累计清醒时长
st.energy = Math.max(0, Math.min(1, st.energy - awakeHours * 0.05));
```

`awakeHours` 是**从清醒起点到现在的累计值**，但这段代码在**每次** `update()` 都把它整个再扣一遍。
本应用每 30 秒刷新一次心情 ⇒ 每 30 秒就重复扣一次"至今为止累计清醒"的量。

### 2.2 独立复现（修复前）

```
已清醒 1 小时, 首次 update → energy = 0.9500
  第 1 次 30s 刷新 → 0.8996
  ...
  第17 次 30s 刷新 → 0.0363
  第18 次 30s 刷新 → 0.0000     ← 9 分钟就归零
```

### 2.3 修法：按**时间增量**结算

| 改动 | 说明 |
|---|---|
| 新增状态 `lastEnergyAt` | 上次结算精力的时刻；随 `toJSON`/`restore` 持久化 |
| `update()` 只扣增量 | `delta = now - lastEnergyAt`，`energy -= delta/小时 × 0.05` |
| 睡眠期间不扣 | `awakeSince === 0`（正在睡）⇒ 只推进结算基准，不扣精力 |
| `noteSleep` 重置基准 | 睡着的这段时间不算清醒消耗 |
| `noteAwake` 对齐基准 | 刚醒来时结算基准不早于醒来时刻 |
| 单次扣除上限 | `energy_max_delta_ms = 6 小时` —— 机器休眠 / 时钟回拨不会一次扣光 |
| 配置化 | `energy_decay_per_hour`（默认 0.05） |

### 2.4 修复后实测

```
已清醒 1 小时, 首次 update → energy = 0.9500        (期望 0.95)
再过 10 分钟 (20 次 30s 刷新) → energy = 0.9417      (理论值 1-(70/60)*0.05 = 0.941667)
归零? 未归零 ✓
重启恢复后 energy = 0.9417 (与保存值一致)
恢复后再过 30s → 0.94125 (期望 0.94167 - 0.00042 = 0.94125)
```

### 2.5 新增回归测试

| 断言 | 内容 |
|---|---|
| `M17` | 已清醒 1 小时 + 每 30s 刷新 10 分钟 ⇒ 精力 **0.9417**，不归零 |
| `M18` | **重启恢复**后精力等于保存值；恢复后再过 30s 只扣 30 秒的量；重启本身不额外扣 |
| `M19` | 睡着的时间**不**计入清醒消耗；醒来后从满值接着扣 |
| `M20` | 单次 100 小时跳变只扣 6 小时上限（不会一次归零） |

---

## 三、问题 3：设置保存失败却显示"已保存"

### 3.1 根因

```js
const res = settingsStore_.saveSettings(patch);   // res.ok 可能是 false
settings_ = res.settings;
applySettingsToRuntime();
return { ok: true, ... };                          // ← 无论 res.ok 是什么, 都返回 ok:true
```

面板只判断 `res.ok` ⇒ **落盘失败也显示"已保存"**；同时设置已经被应用到运行时 ⇒ 用户以为改好了，重启后全丢。

### 3.2 修法

| 层 | 改动 |
|---|---|
| `settings_store.js` | 新增 `commitSettings(store, patch, currentSettings)`：落盘成功 ⇒ `{ok:true, saved:true, settings:合并后}`；失败 ⇒ `{ok:false, saved:false, settings:原设置, error:原因}` |
| `main.js` | `applySettingsPatch()` 改用 `commitSettings`；**失败时不改内存设置、不应用到运行时**，并记 `R177 SETTINGS_SAVE_FAILED` |
| `main.js` | `settings-set` IPC 的 `ok` 严格等于"落盘成功" |
| `settings_panel.js` | 失败时显示 **「保存失败（设置未改动）：<原因>」**，并按主进程返回的权威值**把控件重画回真实状态**（不能停在用户拨动的位置上） |

### 3.3 故障注入实测（真实 Electron）

用 `--r177-fault-settings` 把存储目录指到一个**普通文件**上 ⇒ 写入必然 `ENOTDIR` 失败：

```
[main] R177 SETTINGS_SAVE_FAILED error=ENOTDIR: not a directory, open '.../r177_fault_dir/pet_settings.json.tmp'
[main] R177 APPLY_SETTINGS ok=false saved=false error=ENOTDIR: ...
[main] R177 DUMP {... "settings":{"pet_scale":1,"activity_rate":"normal",...} ...}
```

| 判据 | 结果 |
|---|---|
| `G1` 主进程明确报错 `SETTINGS_SAVE_FAILED` | ✅ 带完整错误原因 |
| `G2` 返回 `ok=false`（不是 `ok=true`） | ✅ `ok=false saved=false` |
| `G3` 设置**保持原值**（没被当成"改成功了"） | ✅ `pet_scale` 仍是 1 |
| `G4` 磁盘上确实**没有**写出设置文件 | ✅ `pet_settings.json` 不存在 |

---

## 四、顺带修掉的同类问题：「开机自动启动」也会谎报

真机日志里出现：

```
ERROR:platform_util_mac.mm(257)] Unable to set login item: 未能完成该操作。Operation not permitted
```

原因：**macOS 上从源码直接跑（不是打包后的 `.app`）时，`app.setLoginItemSettings` 必然被系统拒绝**。
这与问题 3 是同一类 —— 开关显示"已开"，实际没生效。

修法：
- `applyLaunchAtLogin()` 返回**真实结果** `{ok, reason}`，而不是只记日志；
- 结果经 `settings-get` / `settings-set` / `settings-changed` 传到面板；
- 面板在开关下方如实显示原因（例如「⚠️ 系统拒绝设置登录项（…）—— 通常是因为当前不是打包后的 .app」）；
- 用户勾选但没生效时，状态条显示「已保存，但开机自启未生效：<原因>」。

**已知限制（诚实登记）**：**开机自动启动只有在把桌宠打包成 `.app` 之后才真正生效**；从源码直接跑时 macOS 会拒绝。本轮不涉及打包，故该能力在开发态无法真机验证。

---

## 五、测试与回归（全部实跑）

### 5.1 单元测试

| 文件 | 断言数 | 本轮变化 |
|---|---|---|
| `tests/r177_mood_engine.test.js` | **20**（+4） | 新增 `M17~M20`：精力增量扣 / 重启恢复 / 睡眠不扣 / 单次上限 |
| `tests/r177_settings_store.test.js` | **18**（+4） | 新增 `S15~S18`：`commitSettings` 成功与失败路径 |
| `tests/r177_menu_settings.test.js` | 16 | 未变 |
| **node 全量** | **15 个文件全过** | — |

### 5.2 真实 Electron 运行时验证（`100_R177_runtime_verify.py`）：**34/34 PASS**

| 组 | 内容 | 结果 |
|---|---|---|
| A | 写入设置 + 菜单命令走正式行为系统 + 桌宠大小 + 频率 + 点击反馈 + 心情落盘 | 14/14 |
| C | 菜单命令"吃水果" ⇒ 场景道具挂载 | 3/3 |
| D | 菜单命令"睡觉" ⇒ 床/月亮/被子挂载 | 2/2 |
| E | 设置面板真实创建并读到磁盘上的设置 | 2/2 |
| **F** | **Mac 一键验收入口真的把桌宠拉起来**（Finder 双击等价路径） | **4/4** |
| **G** | **保存失败时如实报错、不谎报"已保存"、不改设置、不写文件** | **4/4** |
| B | **重启恢复**（设置逐字段 + 心情逐字段 + 大小 + 频率） | 5/5 |

### 5.3 回归

| 项 | 结果 |
|---|---|
| node 单元测试全量 | 15 文件**全过** |
| R147 e2e 真实 Electron | **PASS=60 FAIL=0 NOT_VERIFIED=0** |
| R167 段判据 | 15/15（R162 对照段失败为历史对照，预期） |
| R165 手臂判据 | 18/18 |
| R173 场景判据 | 26/26 |
| R170 场景判据 | 12/13（W3 为 R173 改帧后的历史预期失败） |

---

## 六、边界确认

- **零联网、零 AI 调用、零充值 i2i、零新角色素材**：本轮只改 5 个源文件 + 3 个测试/脚本，**未触碰任何角色素材**，未新增任何网络调用。
- **保留 R177 已完成的功能**：心情系统、控制菜单、设置面板、本地保存全部保留且行为不变；本轮只修 bug。
- **保留所有角色素材与原有行为系统**：`assets/character_R138/R153/R156/R158/R172/R173` 逐字节未动；行为引擎只改了精力/设置相关的纯逻辑。
- **未进入 V0.1 / 未擅自封版**：`V0_0_RELEASE_STATUS = NOT_FROZEN`。
- **办公场景仍待用户视觉确认**：本轮**未**把它登记为最终产品验收通过。

---

## 七、如实登记的已知限制

1. **开机自动启动在开发态（从源码跑）必然失败** —— macOS 要求是打包后的 `.app`；面板会如实提示，但真机验证需要打包版本。
2. **精力衰减是线性模型**（每小时 −0.05），没有"越累掉越快"的曲线；这是刻意保持简单。
3. **精力目前只作为可见状态展示**（设置面板里的进度条），尚未参与心情评分 —— 改了它会动到已有判定，故本轮不动。
4. 单次精力扣除有 6 小时上限 ⇒ 关机一整夜的消耗只算 6 小时。
5. `MAC_REAL_GUI_ACCEPTANCE = PENDING` —— 菜单、设置面板观感与真实鼠标手感仍需用户 Mac 真机确认。
6. **办公场景仍待用户视觉确认，未登记为最终产品验收通过。**
