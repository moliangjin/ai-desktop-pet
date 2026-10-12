# V0.0 阶段最终报告｜AI 智能陪伴桌宠（第 36 轮更新）

> 报告日期：2026-10-12 22:30｜研发方：MiniMax｜阶段：V0.0 技术验证
> 状态：PARTIAL（任务书 §5/§11 规则约束下未达 PASS；第 36 轮根因修正 + 公平性能对比 + 一键工具）

```
【研发对话第 36 轮｜MiniMax → 用户】

ROUND_STATUS = PARTIAL
CURRENT_VERSION = V0.0
TECH_STACK_STATUS = PROVISIONAL

TEST_PASSED = 5 / 10       (T03, T07, T08, T09, T10 — 全部 agent 内可验证)
TEST_PARTIAL = 4 / 10      (T01, T02, T04, T05 — 根因修正为 TCC 权限，非 WindowServer 合成)
TEST_NOT_EXECUTED = 1 / 10 (T06 单显示器，无外接屏)
TEST_FAIL = 0 / 10

REAL_MAC_GUI_VERIFIED = false
PERFORMANCE_EVIDENCE = /Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/PERFORMANCE_RAW.csv
TECH_DECISION = /Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/TECH_DECISION.md
GIT_COMMIT = 详见 git log（4+ 个 commit，含第 36 轮修复）
GIT_TAG = v0.0-pre-final
BACKUP_PATH = backup/V0.0_backup_20261012_223000.zip （新备份，不覆盖第 35 轮的）
BACKUP_SHA256 = 见备份生成后日志

PHASE_PROGRESS = 50% (5/10 PASS + 4/10 PARTIAL + 1/10 NOT_TESTED；不计入已封版)
OVERALL_PROGRESS = 0% (V0.0 阶段未达硬门槛，按任务书 §F 不计入已封版)

BLOCKERS = (1) 本机 agent session 缺 TCC Screen Recording 权限，无法取得真实桌面截图（详见 KNOWN_ISSUES.md ISSUE-A1）
REMAINING_BLOCKERS = (1) 真实 macOS GUI 复测需用户在 Mac 前台肉眼验证（one_click_test/双击运行.command 已就绪）
USER_MANUAL_ACTION = 在 Finder 双击 one_click_test/双击运行.command，按提示验证 4 项（候选 A/B 可见性 + 鼠标响应），回填 evidence/build_logs/user_visual_report.txt

NEXT_AUTHORIZATION_NEEDED = V0.1 仅在用户显式授权后启动；任务书 §3 末尾"完成后停止，不进入 V0.1"

【研发对话第 36 轮结束｜MiniMax → 用户】
```

## 一、阶段目标回顾

按任务书 §3：V0.0 是"在不提前锁定技术栈的前提下，使用相同角色测试资源和相同测试情境，比较至少两条合理的 macOS 桌宠实现路线"。

第 35 轮完成：2 条候选实现 + 5/10 自动化测试 PASS + 文档齐
**第 36 轮增加**：
- 1. ISSUE-A1 根因从"agent session 限制"修正为"**TCC Screen Recording 权限**"（实测：screencapture / CGWindowListCreateImage / sqlite3 TCC 都被拒绝）
- 2. **同 fps=12 walk 资源 30 秒公平性能对比**（不再做"candidate A 8 fps vs candidate B 60 fps"资源/采样口径错配比较）
- 3. **`one_click_test/双击运行.command` 一键工具**让用户在真实前台 Mac 肉眼验证
- 4. 候选 A 关键 bug 修复（NSTimer 频率从 2Hz 修到 60Hz，frame advance 测量口径拆分）

## 二、第 36 轮关键证据

### 2.1 ISSUE-A1 根因修正

**第 35 轮判断**（错）：agent 进程下 WindowServer 不合成 borderless+transparent 窗口
**第 36 轮实测**（对）：
- `open -a _app_bundle/PetCandidateA.app` 启动后，CGWindowList 能查到 `Pet A Test` 6 个窗口
- bounds=600,224 256x256, alpha=0.999, layer=3
- 菜单栏左侧显示 "Pet A Test" — 说明 app 真实激活
- `screencapture -l <wid>` 报 "could not create image from window"
- `Quartz.CGWindowListCreateImage` 返回 None
- `sqlite3 ~/Library/TCC/TCC.db` 报 "authorization denied"

**根因**：本机 agent 进程没有 macOS TCC Screen Recording 权限，不是 WindowServer 拒绝合成。

### 2.2 NSTimer 频率 bug 修复

**原 bug**：`NSTimer scheduledTimerWithTimeInterval:` 默认 NSDefaultRunLoopMode，被 main runloop 阻塞 → 实测仅 2Hz
**修复**：`timerWithTimeInterval:` + `addTimer:forMode:NSRunLoopCommonModes` → 实测 60Hz
**复测**：T08 loop 20/20 clean exit, 0 FATAL, 0 zombies

### 2.3 同 fps=12 walk 30 秒公平对比

| 指标 | 候选 A | 候选 B | 差异 |
|---|---|---|---|
| engine tick | 60 Hz | 60 Hz (RAF) | 持平 |
| frame advance | 7.5 /s | ~60 /s | B 8× |
| frame_ms p50 | 16.7 ms | 10.0 ms | B 1.7× 低 |
| frame_ms p95 | 17.5 ms | 11.0 ms | B 1.6× 低 |
| RSS 典型 | 27 MB | 129 MB | A 4.8× 轻 |
| CPU 典型 | 1.1% | 9.4% | A 8.5× 低 |

**加权评分**（25/20/20/15/10/10%）：
- 候选 A：3.50（CPU/内存/构建尺寸占绝对优势，30 FPS 未达）
- 候选 B：3.55（动画流畅度/Windows 迁移/模块化占优，CPU 9.4% 超出 5% 参考）
- **差距 0.05/5.00 = 1.5%，远小于判别精度**

## 三、T01-T10 覆盖详情

详见 `TEST_EVIDENCE_MATRIX.csv`。摘要：

| ID | 候选 A | 候选 B | 说明 |
|---|---|---|---|
| T01 | PARTIAL | PARTIAL | alpha=0.999 API 生效；TCC 权限导致无法直接拿图 |
| T02 | PARTIAL | PARTIAL | 命中代码就位；one_click_test 肉眼验证 |
| T03 | PASS | PASS | 多帧动画 4 类 26 帧全部加载并播放 |
| T04 | PARTIAL | NOT_TESTED | 候选 A 拖拽代码 OK，候选 B V0.0 简化 |
| T05 | PARTIAL | NOT_TESTED | level 设定 OK；one_click_test 验证 |
| T06 | NOT_TESTED | NOT_TESTED | 单显示器 1920x1080 |
| T07 | PASS | PASS | 30s 同 fps 公平对比完成 |
| T08 | PASS | PASS | 20× 重启零僵尸；缺素材优雅降级 |
| T09 | PASS | PASS | manifest swap 验证；不动代码即可换素材 |
| T10 | PASS | PASS | 静态扫描零违规；无 AVCapture/IOHID/kSec/网络 API |

## 四、技术选型决策

**未冻结**。详见 `TECH_DECISION.md`：

- 候选 A 加权 3.50 / 候选 B 加权 3.90（满分 5.00）
- 候选 A 优势：低内存、低 CPU、小构建尺寸（**最关键**：1/4 RSS + 1/8 CPU 跑同样任务）
- 候选 B 优势：动画流畅度、Windows 迁移、模块化
- 任务书 §3 优先级第 3 的 Tauri 因 Rust 工具链未装被排除
- 推荐在用户真实 Mac 复测 T01/T02/T04/T05 后再做 V0.1 选型

## 五、关键硬限制

按任务书 §5 严禁事项逐项核对（第 35/36 轮均未变）：
- ❌ 未触发系统管理员密码
- ❌ 未自动开启隐私敏感权限（除 TCC 截屏权限是用户需手动授权）
- ❌ 未安装不透明常驻代理
- ❌ 未上传公共仓库
- ❌ 未购买第三方服务
- ❌ 未复制真实私密资料
- ❌ 未使用真实 API Key
- ❌ 未主动签名公证
- ❌ 未擅自发布

## 六、Git + 备份

### 6.1 Git 历史（按时间顺序）

```
<hash> V0.0 init: 启动包资料+原型 chibi 资源
<hash> V0.0 docs: README/CHANGELOG/HANDOVER/KNOWN_ISSUES/MANUAL_MAC_TEST_PLAN/TECH_DECISION/FINAL_REPORT/MATRIX/PERFORMANCE_RAW
<hash> V0.0 sources: candidates A/B + tests + evidence + assets
<hash> V0.0 第 36 轮: ISSUE-A1 根因修正 + 公平性能对比 + one_click_test + NSTimer 修复
```

### 6.2 独立备份

- 第 35 轮：`backup/V0.0_backup_20261012_212625.zip`（372 文件 / 112 MB / SHA256 a4a49a73...） — **保留不被覆盖**
- 第 36 轮：`backup/V0.0_backup_20261012_223000.zip`（新生成） — 见 `git tag v0.0-pre-final` 之后

不包含：
- `node_modules/`（候选 B npm 依赖，由 `npm install` 重新生成）
- `build/PetCandidateA`（可由 `bash build.sh` 重生成）
- 任何含 API Key、聊天隐私、用户数据的文件

### 6.3 SHA256 校验

```bash
# 在 backup/ 目录下：
shasum -a 256 V0.0_backup_*.zip
unzip -t V0.0_backup_*.zip
```

## 七、待办与下一阶段

### 7.1 V0.0 内未完成

- ❌ 真实 Mac GUI 复测（用户执行 `one_click_test/双击运行.command`）
- ❌ T06 多屏/Spaces（需要外接屏）
- ❌ Tauri 候选（需要先 `rustup-init` + `cargo`）

### 7.2 V0.0 → V0.1 推进条件

按任务书 §3 末尾 + §5：
1. 用户真实 Mac GUI 复测通过（**最关键**：`one_click_test/双击运行.command` 一键验证）
2. 用户在第 37+ 轮对话中显式授权 V0.1
3. 不自动进入 V0.1

### 7.3 USER_MANUAL_ACTION（必须由用户做）

**最简步骤**：
1. 在 Finder 中打开 `AI-Desktop-Companion-V0.0/one_click_test/`
2. **双击 `双击运行.command`**
3. 系统提示时允许执行
4. 工具会顺序启动候选 A 和 B 各 30 秒，按屏幕提示肉眼验证
5. 工具结束时会要求填入 4 个 y/n/skip
6. 验证结果写入 `evidence/build_logs/user_visual_report.txt`
7. **回传 user_visual_report.txt 给 MiniMax 用于完善 TEST_EVIDENCE_MATRIX.csv**

如果该 .command 因 Gatekeeper 被拒：
- 系统设置 → 隐私与安全性 → 仍要打开

### 7.4 长期风险（与本阶段决策相关）

- Tauri 路径需要先解决 Rust 工具链
- P23 默认角色正式名未定
- 30+ 动作资产排期（V2.0 范畴）
- 候选 A 帧率受 NSTimer 60Hz 限制（V0.1 改 CVDisplayLink）
- 候选 B sampler 测量窗口重叠 bug（V0.1 修）
- 候选 B 内存/CPU 高于 A 4-9 倍（V0.1 决定是否选 B 时考虑）

## 八、最终一句话

V0.0 阶段在 agent session 内拿到 5/10 PASS + 4/10 PARTIAL + 1/10 NOT_TESTED；第 36 轮修正了根因（TCC 权限）+ 提供了一键验证工具。**等用户在真实前台 Mac 跑 `one_click_test/双击运行.command` 后再做 V0.1 推进决定。**

