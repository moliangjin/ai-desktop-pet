# 真实 Mac GUI 复测计划｜AI 智能陪伴桌宠 V0.0

> 版本：V0.0 Plan v1.0｜2026-10-12｜研发方：MiniMax
> 适用：用户在真实前台 Mac mini M2 / Sonoma 14.7.4 复测时按此逐项执行

## 0. 准备

- 设备：Mac mini M2 16GB（与本 V0.0 实测同机；其它机型结果可能因 GPU/显示缩放有差异）
- 系统：macOS 14.7.4 (23H420)
- 确认窗口服务器可合成桌面应用：Dock 与 Finder 正常
- 解压 `AI-Desktop-Companion-V0.0` 仓库到任意本地路径
- 终端在真实前台 Terminal.app（不要 ssh 进 agent 之类的 session）

## 1. 候选 A：Objective-C + AppKit

### 构建
```bash
cd AI-Desktop-Companion-V0.0/candidates/candidate_a_appkit
bash build.sh
```

### T01 真实透明窗口
1. 打开 `Terminal.app`（前台）
2. 运行：`bash run.sh 15`
3. **预期**：桌面出现 256×256 的 Q 版角色，背景透明（角色外完全能看到壁纸与其它应用）
4. **关掉**：菜单栏右侧"🐾"图标 → Quit，或 Cmd+Q

### T02 像素级命中/穿透
1. 候选 A 启动后保持前台
2. 鼠标移到角色身体上 → 角色应变为"drag"动作（点击测试）
3. 鼠标移到角色**周围的透明区域** → 正常点击应落到下层应用（如 Finder 桌面图标）
4. **重复 20 次** → 统计角色命中数 vs 透明穿透数

### T03 多帧动画
1. 菜单栏"🐾" → "Action: walk" → 角色循环播放 walk
2. 切到 "jump" → 单次跳跃动画
3. 切到 "drag" → 拖动姿势循环
4. 切到 "idle" → 待机循环
5. 关闭并重新启动 → 仍从 idle 开始

### T04 拖拽 + 边界
1. 鼠标按住角色 → 角色变 drag 姿势
2. 拖到屏幕左边缘、右边缘、顶/底部 → 角色停在屏幕内不超出
3. **重复 20 次**
4. 松手 → 角色应回到 idle

### T05 焦点
1. 打开 TextEdit，新建文档
2. 在文本中持续输入
3. 桌宠应不抢键盘焦点（输入正常落到 TextEdit）
4. 点击角色 → 角色响应一次但不打断下一次 TextEdit 输入

### T06 多屏 / Spaces
- 接外接屏：把桌宠拖到外接屏
- 三指上滑切到其他 Space：桌宠是否仍可见
- **无外接屏 / 无 Spaces 时**：在 `TEST_EVIDENCE_MATRIX.csv` 中此项保持 NOT_TESTED

### T07 性能
- 任务书 §3 规定：10 分钟互动、30 分钟活动、10 分钟空闲
- 实测：候选 A 启动后查看菜单 "🐾" → "Dump Perf" 看 fps / RSS / CPU
- 长跑：候选 A `--quit-after 600` 跑 10 分钟；或手动启动 30 分钟后菜单 Quit

### T08 错误恢复
1. 故意把 `assets/prototype_chibi/manifest.json` 改成 `animations/missing/000.png` 等不存在的路径
2. 启动：`--quit-after 3`
3. **预期**：log 中出现 `load fail` 但程序仍正常退出，无残留进程
4. **20× relaunch 验证**：`bash tests/test_loop.sh` 应输出 pass=20 fail=0 zombies=0

### T09 资源接口
1. 跑 `bash tests/test_manifest.sh`
2. **预期**：`[T09] PASS — engine loaded swapped frame lists without code change.`
3. 引擎代码（`src/Manifest.m`/`FrameStore.m`/`PetView.m`）未改

### T10 安全
- 候选 A 不应触发任何系统权限请求
- 跑 `bash tests/test_security.sh` 应输出 `[T10] PASS`

## 2. 候选 B：Electron + PixiJS

### 构建
```bash
cd AI-Desktop-Companion-V0.0/candidates/candidate_b_electronpixir
npm install  # 仅首次
```

### T01 真实透明窗口
1. 前台 Terminal 跑：`bash run.sh 15`
2. **预期**：桌面出现 256×256 角色，背景透明

### T02-T05 同上（候选 A 步骤 2-5）

候选 B 的菜单交互通过 `ipcMain` 触发；V0.0 暂未实装菜单栏，但可通过修改 main.js 接受 `--action walk` 之类参数来切换。

### T07 性能
- 候选 B 的 RSS 约 126-128MB（Electron 基线 + 1 个 WebView）
- CPU 11-22% idle
- FPS 60（PIXI RAF 限制）

### T08 错误恢复
1. `node tests/test_manifest.js` 验证 manifest 缺资源时引擎优雅降级
2. `node tests/test_loop.js` 验证 20× 干净退出

### T09 资源接口
1. 跑 `node tests/test_manifest.js`
2. **预期**：`[T09] PASS`

### T10 安全
- `node tests/test_security.js`

## 3. 复测证据提交

将以下文件交给 MiniMax：
- 每个 T01-T10 的桌面截图（PNG，**不要录屏上传**——任务书 §0 禁止）
- 性能 CSV（候选 A/B 的 `candidate_a_perf_v5.csv` 与 `candidate_b_perf_5.csv` 之类）
- 任何异常 log

## 4. 复测发现的问题

如果发现以下任一情况，请把 T01/T02/T04 标 FAIL 并反馈：
- 桌宠窗口完全不显示（候选 A alpha=1.0 / 候选 B 不渲染）
- 透明区域仍拦截点击
- 拖动时窗口飞出屏幕
- 占用持续 > 250MB RSS 或 > 5% CPU 单核

## 5. 不能做的

按任务书 §5：
- 不要让候选 A/B 访问任何系统级权限（屏幕录制/辅助功能/麦克风/摄像头/键盘监听）
- 不要输入真实 API Key
- 不要用 sudo 启动候选程序
- 不要在多用户共享的 Mac 上运行（可能写入候选目录，影响其它用户）

