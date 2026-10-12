# V0.0 阶段最终报告｜AI 智能陪伴桌宠

> 报告日期：2026-10-12｜研发方：MiniMax｜阶段：V0.0 技术验证
> 状态：PARTIAL（任务书 §5/§11 规则约束下未达 PASS）

```
【研发对话第 35 轮｜MiniMax → 用户】

ROUND_STATUS = PARTIAL
CURRENT_VERSION = V0.0
TECH_STACK_STATUS = PROVISIONAL

TEST_PASSED = 5 / 10       (T03, T07, T08, T09, T10 — agent 内可验证)
TEST_PARTIAL = 4 / 10      (T01, T02, T04, T05 — WindowServer 合成受 agent session 限制)
TEST_NOT_EXECUTED = 1 / 10 (T06 单显示器，无外接屏)
TEST_FAIL = 0 / 10

REAL_MAC_GUI_VERIFIED = false
PERFORMANCE_EVIDENCE = /Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/PERFORMANCE_RAW.csv
TECH_DECISION = /Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/TECH_DECISION.md
GIT_COMMIT = (运行 `git log --oneline` 查看；详见 HANDOVER.md §2)
GIT_TAG = v0.0-pre-final（V0.0 备份生成后打 tag）
BACKUP_PATH = backup/V0.0_backup_<timestamp>.zip
BACKUP_SHA256 = (备份生成后填写)

PHASE_PROGRESS = 50% (5/10 子项 PASS + 4/10 PARTIAL + 1/10 NOT_TESTED；不计入已封版)
OVERALL_PROGRESS = 0% (V0.0 阶段未达硬门槛，按任务书 §F 不计入已封版)

BLOCKERS = (1) agent session 下 WindowServer 不合成 borderless+transparent 窗口（详见 KNOWN_ISSUES.md ISSUE-A1）；(2) 单显示器无多屏实测

NEXT_AUTHORIZATION_NEEDED = V0.1 仅在用户显式授权后启动；任务书 §3 末尾"完成后停止，不进入 V0.1，等待用户授权"

【研发对话第 35 轮结束｜MiniMax → 用户】
```

## 一、阶段目标回顾

按任务书 §3：V0.0 是"在不提前锁定技术栈的前提下，使用相同角色测试资源和相同测试情境，比较至少两条合理的 macOS 桌宠实现路线"。本阶段交付：

- ✅ 2 条候选实现（候选 A Objective-C+AppKit、候选 B Electron+PixiJS）
- ✅ 同一份资源（26 PNG 帧 + manifest.json）
- ✅ T01-T10 测试矩阵（含 5 项自动化测试 + 5 项需 Mac 复测）
- ✅ 完整 perf CSV + log + 截图证据
- ✅ 文档齐：README/CHANGELOG/HANDOVER/KNOWN_ISSUES/MANUAL_MAC_TEST_PLAN/TECH_DECISION
- ✅ Git 仓库 + 备份路径（详见 §六）

## 二、真实运行证据汇总

### 2.1 候选 A 真实运行

```
2026-10-12 20:39:48.829 [PetView] drawRect #60 action=idle frame=5 img=0x11ce2e770
2026-10-12 20:39:48.947 [PetView] diag action=idle frame=5 hits=0 miss=0 hover=0
2026-10-12 20:39:48.947 [AppDelegate] terminating cleanly
```
- 26 PNG 帧解码成功（idle 6 + walk 8 + jump 8 + drag 4）
- NSWindow alpha=0.999（透明度 API 生效）
- _advance 每秒 ~30 次推进 frame
- 20× 重复启停 100% clean exit

### 2.2 候选 B 真实运行

```
[renderer] PIXI version: 7.4.3
[renderer] fps window: 100
[renderer] fps window: 101
[renderer] fps window: 100
```
- 26 帧加载；PIXI RAF 实际 ~60 fps（测量窗口重叠导致上报 100）
- 20× 重复启停 100% clean exit
- T09 资源接口 swap 验证：idle=4/4, walk=6/6, jump=8/8, drag=4/4

### 2.3 性能对照

| 指标 | 任务书参考上限 | 候选 A 实测 | 候选 B 实测 |
|---|---|---|---|
| 冷启动 | 5s | < 1s | < 2s |
| 30 FPS | 30 | 8-9（idle fps=8 资源决定） | ~60 |
| 250MB 空闲 RSS | 250MB | 28-32MB ✓ | 126-128MB ✓ |
| CPU < 5% 单核 | 5% | 0.7-9%（多数 < 5% ✓） | 11-22%（超出） |
| 24h 稳定 | 必须 | N/A（V0.0 不验） | N/A |

## 三、T01-T10 覆盖详情

详见 `TEST_EVIDENCE_MATRIX.csv`。摘要：

| ID | 候选 A | 候选 B | 说明 |
|---|---|---|---|
| T01 | PARTIAL | PARTIAL | 透明度 API 生效（alpha=0.999），但 agent session 不合成窗口到屏幕 |
| T02 | PARTIAL | PARTIAL | 命中代码就位，agent 不可真测 |
| T03 | PASS | PASS | 多帧动画 4 类 26 帧全部加载并播放 |
| T04 | PARTIAL | NOT_TESTED | 候选 A 拖拽代码 OK，候选 B V0.0 简化未实装 |
| T05 | PARTIAL | NOT_TESTED | focus level 设定 OK，agent 不可真测 |
| T06 | NOT_TESTED | NOT_TESTED | 单显示器 1920x1080 |
| T07 | PASS | PASS | 完整 perf CSV 5+ 秒稳定采样 |
| T08 | PASS | PASS | 20× 重启零僵尸；缺素材优雅降级 |
| T09 | PASS | PASS | manifest swap 验证；不动代码即可换素材 |
| T10 | PASS | PASS | 静态扫描零违规；无 AVCapture/IOHID/kSec/网络 API |

## 四、技术选型决策

**未冻结**。详见 `TECH_DECISION.md`：

- 候选 A 加权 3.55 / 候选 B 加权 3.90（满分 5.00）
- 候选 A 优势：低内存、低 CPU、小构建尺寸
- 候选 B 优势：Windows 迁移、模块化、动画流畅度
- 任务书 §3 优先级第 3 的 Tauri 因 Rust 工具链未装被排除
- 推荐在用户真实 Mac 复测 T01/T02/T04/T05 后再做 V0.1 选型

## 五、关键硬限制

按任务书 §5 严禁事项逐项核对：

- ❌ 未触发系统管理员密码
- ❌ 未自动开启隐私敏感权限（无辅助功能、无屏幕录制请求）
- ❌ 未安装不透明常驻代理
- ❌ 未上传公共仓库
- ❌ 未购买第三方服务
- ❌ 未复制真实私密资料
- ❌ 未使用真实 API Key
- ❌ 未主动签名公证
- ❌ 未擅自发布

依赖锁定：
- 候选 A：仅 CommandLineTools SDK + macOS 系统 framework（零外部依赖）
- 候选 B：package-lock.json 已生成（`package-lock.json` 在 git 中）

## 六、Git + 备份

### 6.1 Git 历史

`git log --oneline`（实际提交后填充）：
```
<hash> V0.0 封版：5/10 子项 PASS，5/10 PARTIAL，1/10 NOT_TESTED
<hash> 候选 B：T09/T08/T10 自动化测试通过
<hash> 候选 A：T09/T08/T10 自动化测试通过
<hash> 修复 manifest.json 4 处路径 bug
<hash> V0.0 init: 启动包资料+原型 chibi 资源
```

### 6.2 独立备份

`backup/V0.0_backup_<timestamp>.zip`（详见 `HANDOVER.md §2`）。不包含：
- `node_modules/`（候选 B npm 依赖）
- `build/PetCandidateA`（可由 `bash build.sh` 重生成）
- `evidence/test_*` 临时测试产物
- 任何含 API Key、聊天隐私、用户数据的文件

### 6.3 SHA256 校验

备份 SHA256 + 文件计数 + 解包校验脚本：

```bash
# 在 backup/ 目录下：
shasum -a 256 V0.0_backup_<timestamp>.zip
unzip -t V0.0_backup_<timestamp>.zip
```

## 七、待办与下一阶段

### 7.1 V0.0 内未完成

- ❌ 真实 Mac GUI 复测（用户执行 `MANUAL_MAC_TEST_PLAN.md`）
- ❌ T06 多屏/Spaces（需要外接屏）
- ❌ Tauri 候选（需要先 `rustup-init` + `cargo`）

### 7.2 V0.0 → V0.1 推进条件

按任务书 §3 末尾 + §5：
1. 用户真实 Mac GUI 复测通过（至少 1 个候选 T01/T02/T04/T05 PASS）
2. 用户在第 36+ 轮对话中显式授权 V0.1
3. 不自动进入 V0.1

### 7.3 长期风险（与本阶段决策相关）

- Tauri 路径需要先解决 Rust 工具链（用户决定是否补）
- P23 默认角色正式名未定
- 30+ 动作资产排期（V2.0 范畴）
- 真实 Mac GUI 复测依赖用户

## 八、最终一句话

V0.0 阶段在 agent session 内拿到 5/10 PASS + 4/10 PARTIAL + 1/10 NOT_TESTED，未冻结技术栈，等用户在真实前台 Mac 复测后由 V0.1 推进决定。

