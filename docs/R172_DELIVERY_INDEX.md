# R172 交付索引 — 办公场景构图重做（恢复完整坐姿 + 3/4 透视电脑 + 可见屏幕内容）

> **生成时间**：2026-10-22
> **对应任务书**：R172（承接 R170，基线 commit `c9ea732`）
> **作者**：MiniMax（Mavis）
> **上一交付**：R170 `c9ea732`（实现 `d1b700e` / 索引 `9c3892f` / 归档 `c9ea732`）
> **本轮实现提交**：`b34e7c9`
> **状态**：`WORK_SCENE = PASS` / **`MAC_REAL_GUI_ACCEPTANCE = PENDING`** / `V0_0_RELEASE_STATUS = NOT_FROZEN`
> **范围声明**：本轮**只做任务书点名的办公场景构图重做**，未扩展功能；**未进入 V0.1**；**未改动人物身份与服装**（R138 原始 23 帧 SHA256 逐字节未变）；**未改动任何点击动作素材**（`assets/character_R158/` 18 张帧与 `c9ea732` 逐字节一致）；**未重新开发整个桌宠**；**未充值 i2i**（全程零 AI 生图调用）；R148 行走方向 / R153 自主行为 / R162 点击互动 / R165 手臂修复 / **R170 吃水果场景全部成果** / R113 拖拽核心均未改动。

---

## 〇、本轮结论（任务书逐项给结论）

| 字段 | 结论 | 一句话依据 |
|---|---|---|
| 恢复完整坐姿（双腿/鞋子/坐在椅子上/双脚落点） | **PASS** | 角色帧桌沿以下的腿脚像素 **0 → 70,580 px**（修复前下半身被 `WORK_CUT_Y=592` 整段剪掉）；200×240 桌下青色长袜 **775 px**、靴子 **1,032 px**、靴底最低行 **234**（地面线 236 ⇒ 双脚落地）；256×256 分别 **1,266 / 1,684 / 249**（地面线 252）。**桌面只遮住大腿，桌下腿脚完整可见** |
| 重新设计电脑透视（3/4 视角 + 可见屏幕内容） | **PASS** | 屏幕由「笔记本背板」换成 **3/4 透视显示器正面**：屏幕投影区亮内容像素 **198 → 728 px**、高频细节能量 **5.53 → 23.56**（背板是平涂石墨灰，界面有标题栏/侧栏/代码行 ⇒ 细节能量拉开 4 倍）；屏内界面在 200×240 下 ≈ 36×30 屏幕 px，代码行仍可分辨 |
| 优先调整整体构图（重排桌椅电脑，不剪身体） | **PASS** | 底图 `sleep_enter_01_sit`（跪坐）→ `wake_up_01_sit_up`（双腿下垂、靴子踩地）；桌面/键盘/双手**画进角色帧内部**（PNG 内 z 序可控）⇒ 不再需要剪身体；场景 back=办公转椅 / front=3/4 显示器 |
| 200×240 与 256×256 同屏可见（人物/腿脚/双手/屏幕） | **PASS** | 两档同时达标：200×240 腿 775 / 鞋 1,032 / 手 31 / 屏 728 / 手在键盘 0.516；256×256 腿 1,266 / 鞋 1,684 / 手 54 / 屏 1,210 / 手在键盘 0.685 |
| 保留双手放在键盘上打字 | **PASS** | 纹理空间：双手皮肤 **1,148 px**（单只 494 / 376）、**66.4%** 落在键盘投影区、肤色连通块 **恰好 2**；两帧手部质心位移 **6.96 纹理 px**（打字动作真实存在） |
| `--demo-scene work` 可直接观看 | **PASS** | 冒烟实测：`PROPS action=work scene=yes mounted=prop_office_chair,prop_office_monitor`；`set-action work applied=true loop=true frames=2` |
| 客观判据 | **13/13 PASS** | `92_R172_scene_verify.py`（纹理空间 + 合成空间 + 修复前后绝对差三层） |

> **但**：沙箱内无法代替你在 Mac 上看最终观感 ⇒ **`MAC_REAL_GUI_ACCEPTANCE = PENDING`**，未伪造任何真机结论。

---

## 一、交付路径

| 项 | 路径 |
|---|---|
| 主工作区 | `/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/` |
| 候选实现 | `candidates/candidate_b_c2/` |
| QA 报告 | `docs/R172_QA_REPORT.md` |
| 交付索引 | `docs/R172_DELIVERY_INDEX.md`（本文件） |
| 审查包 ZIP | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R172_review.zip`（163 文件 / 20,361,727 字节） |
| ZIP SHA256 旁文件 | `/Users/musk123/Downloads/minimax工作文件夹/character_animation_R172_review.zip.sha256`（`ef7c670584b4cceb1bedc5489de421559a6ed56a629692683d845cb5f1eba299`） |
| 备份 | `backup/V0.0_backup_20261022_221445_r172.zip`（263 文件 / 51,113,067 字节）+ 同名 `.sha256`（`226e6cf8a9da055cc9764a0a7c8790f4516cc0e5dc700a16e962637baf85271d`） |
| e2e 机器报告 | `candidates/candidate_b_c2/evidence_r147_e2e.json`（**60 PASS / 0 FAIL / 0 NOT_VERIFIED**） |
| **R172 客观判据** | `candidates/candidate_b_c2/evidence_r172_scene_verify.json`（**13/13 PASS**） |
| 真实采集帧 | `candidates/candidate_b_c2/evidence_r172_preview/`（709 帧 + `preview_meta.json` + `run.log`；**原始 PNG 不入库**） |
| 可观看运行预览 | `candidates/candidate_b_c2/evidence_r172_gifs/`（办公 GIF + 总览图） |
| 前后对比图 | `candidates/candidate_b_c2/evidence_r172_compare/`（7 张，含**完整坐姿截图**与**真机帧 vs 脚本预览**对照） |
| 可视化产物副本 | `/Users/musk123/Downloads/minimax工作文件夹/图文工作/R172_办公场景/` + 图文工作根目录 4 份直取文件 |
| Mac 真机验收入口 | `candidates/candidate_b_c2/C2_Mac人工验收.command`（双击即用，支持 `work` / `eat_fruit` 参数） |

**ZIP SHA256 不写在本索引内**（避免「改索引就改 ZIP 哈希」的循环自引用），写在 ZIP 旁边的独立 `.sha256` 文件；本索引里的占位符在**归档提交**里替换为最终值。

---

## 二、代码结构（R172 变更）

| 文件 | 变更 |
|---|---|
| `assets/character_R141_manifest.json` | ① `action_library.actions.work.frames` → `character_R172/work_1.png` / `work_2.png`（`ground_tex_y=1001`）；② `props.scenes.work` → `back:[prop_office_chair]` / `front:[prop_office_monitor]` / `floor_tex_y:1001`；③ `props.library` 新增 `prop_office_chair` / `prop_office_monitor`（含 desc）；④ `layout.frame_bboxes.work` 重测；⑤ 新增 `r172_office_scene` 段（根因 / 改动 / **honest_limits**） |
| `assets/character_R172/work_1.png` `work_2.png` | **新增**：完整坐姿办公帧（桌面/键盘/双手内嵌，PNG 内 z 序：身体→桌面→键盘→手→桌沿桌腿） |
| `assets/character_R172/prop_office_chair.png` | **新增**：办公转椅（back 层），刻意不画中柱与五星脚 |
| `assets/character_R172/prop_office_monitor.png` | **新增**：3/4 透视显示器（front 层），屏内蓝白科技界面 |
| `90_R172_office_bake.py` | **新增**：办公素材烘焙器（换底图 / 抠手转腕 / 桌面 / 键盘 / 显示器 / 转椅） |
| `91_R172_manifest_update.py` | **新增**：manifest 更新器（**幂等**，重跑逐字节一致） |
| `92_R172_scene_verify.py` | **新增**：13 项客观判据（纹理空间 + 200×240/256×256 合成空间 + 修复前后绝对差） |
| `93_R172_evidence.py` | **新增**：前后对比图 / 完整坐姿截图 / 办公 GIF（取自真实 Electron 采集帧） |
| `94_R172_package.py` | **新增**：审查包 + 备份 + SHA256 打包器 |
| `45_R165_scene_preview.py` | **修正垂直落点 bug**：旧实现把"地面行"当"纹理底行 1024" ⇒ 整幅图比运行时**上移 15.58px**（200×240）/ 20.10px（256×256）。已用真实 Electron 采集帧逐像素比对确认（平均绝对差 3.03）并修正为与 `sprite_layout.js` 一致 |
| `83_R170_scene_verify.py` | 同一份数学的副本同步修正 |
| `tests/r156_click_props_work.test.js` | C1 道具数 12→**14** 并要求新增 2 个道具在库；C3 改为断言办公场景含**转椅 + 显示器**，并**新增**"显示器 PNG 必须有亮色界面内容 ≥ 2000px、深色边框 ≥ 500px"；F2 允许道具放在 `character_R172/` |
| `tests/r170_eat_fruit_work.test.js` | F2 改为断言：work 场景指向 R172 新构图 **且** R167 旧办公道具**文件仍在磁盘**（历史成果不删） **且** 吃水果/睡眠场景一字未改 |
| `R147_e2e_test.sh` | TI4 期望道具数 12→14；TI5 work 挂载列表 → `prop_office_chair,prop_office_monitor` |

---

## 三、本轮最关键的一件事：办公场景为什么会"腿消失 + 只剩背板"

**不是素材不够，是 R167 的一条图层归属设计前提错了。**

R167 的注释原文（`29_R156_pose_bake.py`）：

> 渲染顺序是 back 道具 → 角色 → front 道具。台面在 back 层，而角色的**大腿正好压在台面带上**
> ⇒ 台面被她的腿整片挡住，键盘根本没法出现在她手下
> ⇒ 把 `CUT_Y=592` 以下的身体剪掉。

于是 R170 的办公场景里，用户看到的两个现象是**同一根因的两个后果**：
下半身被剪 + 电脑只能画成"背朝观众的笔记本盖板"（`LID_QUAD`）。

**R172 的改法是换图层归属，不是在身体上继续做文章**：桌面/键盘/双手与角色同处一张 PNG，
PNG 内部 z 序可控 ⇒ 桌面可以正确地遮住大腿，而小腿与靴子完整留在桌下；
电脑则从"背板"换成"正面 3/4 的显示器"。

---

## 四、验收入口（与正式自主行为严格分离）

```bash
cd candidates/candidate_b_c2
../candidate_b_electronpixir/node_modules/.bin/electron . \
  --manifest assets/character_R141_manifest.json --size 200 --demo-scene work
```

或双击 `C2_Mac人工验收.command` 并带上 `work` 参数。

**实现保证**：进入验收模式时 `behaviorEngine.setAutonomousPaused(true)` ⇒ **自主决策暂停，不会随机跑掉**；场景仍走**正式渲染路径** ⇒ 道具按正式规则挂载/卸载。

实测输出：
```
[main] R170 DEMO_SCENE action=work (自主决策已暂停, 场景锁定供验收)
[renderer] R156 PROPS action=work scene=yes mounted=prop_office_chair,prop_office_monitor
[renderer] R147 set-action work applied=true loop=true frame_ms=2600,2600 frames=2 skew=0
```

---

## 五、已知限制（如实登记，完整 7 条见 `docs/R172_QA_REPORT.md`）

### L1 双手没有真正收到键盘中央

坐姿底图两腕间距实测 **280 纹理 px**，肩→腕臂长仅 **227 px**，手腕无法挪到角色中线附近；
强行平移会让手与袖口脱节。键盘因此按实际手位画成宽键盘（x 344~692），双手落在键区**两端**，
指尖已旋转成"向前"方向（判据 A5 实测落在键盘投影区 **66.4%**）。

### L2 袖口被桌面远沿遮住

袖口在 y 614~646、桌面远沿 y=620 ⇒ 袖口大半被盖住，前臂与桌沿的衔接在 200×240 下只剩 2~3 屏幕 px，
读作"手臂伸到桌面上"。

### L3 显示器是"正面 3/4 的屏幕"，不是物理正确的背面同侧视角

2D 插画里"正面坐姿 + 正对观众的显示器"只能这样表达"看得到屏幕内容"。

### L4 打字动作是"手部整体位移 9 纹理 px + 抬头/低头"，不是逐键动画

桌面/键盘/双手画在角色帧里可以逐帧动，但键盘本身是场景道具（运行时按 action 整组挂载，不支持逐帧换道具）。

### L5 历史轮次的"预览图"证据此前比运行时高 15.58px

`45_R165_scene_preview.py` 的落点 bug 本轮才修（见第二节）。**真实 Electron 采集帧一直是对的**，
受影响的只是用 45_ 渲染的历史对比图。

### L6 真机观感未确认

以上所有视觉结论都来自**真实 Electron 运行像素 + 逐帧目视复核**，但**沙箱无法代替你在 Mac 上看最终观感**
⇒ `MAC_REAL_GUI_ACCEPTANCE = PENDING`。

### L7 R170 判据脚本的 W3 断言在本轮预期失败

`83_R170_scene_verify.py` 的 W3「R167 的 work 帧路径不得改动」与 R172 任务书直接冲突（本轮就是要改 work 帧），
已改写为"R172 新构图 + 旧素材仍在磁盘 + 吃水果/睡眠未改"。该脚本其余 12 项全部 PASS。

---

## 六、复算方法

见 `docs/R172_QA_REPORT.md` 第七节。
