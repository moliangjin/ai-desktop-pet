-- tools/passthrough_poc/r67_automated_test.scpt
--
-- V0.0 R68 自动化测试 AppleScript (.scpt) 包装
--
-- 这个 .scpt 在用户授权的 GUI 应用 (Terminal.app / Script Editor.app)
-- 中通过 osascript 间接运行, 继承宿主进程的 Accessibility 权限.
--
-- 运行方式 (任选其一):
--   1. 打开 Script Editor.app → File > Open... 选这个文件 → 按 ⌘R
--   2. Terminal.app: osascript /path/to/r67_automated_test.scpt
--   3. 直接双击 .scpt (系统会用 Script Editor 打开)
--
-- 前置条件 (重要!):
--   系统设置 → 隐私与安全 → 辅助功能 → 打开 Terminal.app (或 Script Editor.app)
--   否则会报 -25211 "osascript 不允许辅助访问".
--
-- 测试流程:
--   1. 用户先在 Terminal.app 跑 ./node_modules/.bin/electron .../main.js --mode=C1
--   2. 用户双击这个 .scpt 启动测试
--   3. 真实系统 mouse 注入, 验证 R67 3 窗口 PoC

on run
    set runLog to "/tmp/r68_scpt_automation.log"
    do shell script "date +%H:%M:%S > " & runLog
    do shell script "echo '=== R68 scpt 自动化测试 ===' >> " & runLog

    -- 1) 启动 R67 PoC (if not already)
    set pocCmd to "cd /Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0/candidates/candidate_b_electronpixir && POC_QUIT_AFTER=45 ./node_modules/.bin/electron ../../tools/passthrough_poc/main.js --mode=C1"
    do shell script pocCmd & " > /tmp/r68_poc_launch.log 2>&1"
    delay 5

    -- 2) Get R67 window positions from result file (PoC writes on close; for live we
    --    need to read from a temp file PoC writes continuously. The 3-window
    --    geometry is FIXED in main.js: control(80,80,360,110), test(320,200,256,256),
    --    probe(360,320,360,180).
    set controlBtnX to 300
    set controlBtnY to 165
    set goldX to 448
    set goldY to 328
    set transparentX to 340
    set transparentY to 220
    set probeBtnX to 540
    set probeBtnY to 380

    -- 3) Click C1 button in control panel
    my logClick("control panel C1", controlBtnX, controlBtnY)
    do shell script "echo 'before C1 click' >> " & runLog
    click at {controlBtnX, controlBtnY}
    delay 1
    do shell script "echo 'after C1 click' >> " & runLog

    -- 4) Click gold ball
    my logClick("test window gold ball", goldX, goldY)
    do shell script "echo 'before gold click' >> " & runLog
    click at {goldX, goldY}
    delay 1
    do shell script "echo 'after gold click' >> " & runLog

    -- 5) Click transparent corner
    my logClick("test window transparent", transparentX, transparentY)
    do shell script "echo 'before transparent click' >> " & runLog
    click at {transparentX, transparentY}
    delay 1
    do shell script "echo 'after transparent click' >> " & runLog

    -- 6) Return to gold ball
    my logClick("test window gold ball (return)", goldX, goldY)
    do shell script "echo 'before gold return' >> " & runLog
    click at {goldX, goldY}
    delay 1
    do shell script "echo 'after gold return' >> " & runLog

    -- 7) Cycle 2
    click at {transparentX, transparentY}
    delay 1
    click at {goldX, goldY}
    delay 1

    -- 8) Cycle 3
    click at {transparentX, transparentY}
    delay 1
    click at {goldX, goldY}
    delay 1

    -- 9) Click probe button directly (sanity check)
    my logClick("probe button direct", probeBtnX, probeBtnY)
    click at {probeBtnX, probeBtnY}
    delay 1

    -- 10) Wait for PoC to flush result file
    delay 2
    do shell script "pkill -TERM -f passthrough_poc/main.js 2>/dev/null; sleep 2; pkill -9 -f passthrough_poc/main.js 2>/dev/null"
    delay 2

    do shell script "ls -t /tmp/passthrough_poc_r67_*.json | head -1 >> " & runLog
    do shell script "cat $(ls -t /tmp/passthrough_poc_r67_*.json | head -1) >> " & runLog

    return runLog
end run

on logClick(label, x, y)
    set ts to do shell script "date +%H:%M:%S.%N"
    do shell script "echo '" & ts & " [scpt-click] " & label & " at (" & x & "," & y & ") >> /tmp/r68_scpt_automation.log"
end logClick
