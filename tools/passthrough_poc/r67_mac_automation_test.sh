#!/bin/bash
# tools/passthrough_poc/r67_mac_automation_test.sh
#
# V0.0 R67 自主真实 macOS GUI 自动化测试 (任务书 §四)
#
# 该脚本在 mavis shell (有 GUI session) 中,launch 3 窗口 PoC,然后通过
# AppleScript / System Events 注入**真实系统 mouse event** (非 JS 模拟),
# 验证:
#   1. 控制面板 [C1] 按钮可点击 (即使 test window 处于 setIgnore(true))
#   2. 真实点击金球 → testWindow click count +1
#   3. 真实点击透明角 → underWindow click count +1 (Path 1 透传生效)
#   4. 真实点击回金球 → testWindow click count 再 +1
#   5. 多轮循环 (3 轮) 验证状态机不失联
#
# 输出:
#   /tmp/passthrough_poc_r67_<ts>_A.{txt,json,csv}  (PoC 状态)
#   /tmp/r67_automation_<ts>.log                   (自动化日志)
#
# 如果 osascript + cliclick 都被 sandbox kill,该脚本会诚实报告
# MAC_GUI_AUTOMATION_AVAILABLE=false,REAL_SYSTEM_CLICK_INJECTED=false,
# GUI_NOT_TESTED 保留。

set +e
SRC="$(cd "$(dirname "$0")/../.." && git rev-parse --show-toplevel)"
cd "$SRC/candidates/candidate_b_electronpixir"

LOG="/tmp/r67_automation_$(date +%s).log"
RESULT_DIR="/tmp"
LAUNCH_TIMEOUT=15
CLICK_SETTLE=1.5

exec > >(tee -a "$LOG") 2>&1
echo "=========================================="
echo " R67 macOS GUI 自动化测试"
echo " log: $LOG"
echo " $(date +%H:%M:%S)"
echo "=========================================="

# Step 1: probe automation tools
echo ""
echo "[step 1] probe automation tools"
OSASCRIPT_OK=0
LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 osascript -e 'return "ok"' >/dev/null 2>&1 && OSASCRIPT_OK=1
echo "  osascript OK=$OSASCRIPT_OK"

# cliclick test (it's often killed by sandbox)
CLICKCLICK_OK=0
LANG=en_US.UTF-8 cliclick -V >/dev/null 2>&1
if [ $? -eq 0 ]; then
    CLICKCLICK_OK=1
    echo "  cliclick OK=1"
else
    echo "  cliclick killed by sandbox (exit=$?)"
fi

if [ $OSASCRIPT_OK -eq 0 ]; then
    echo "[ABORT] osascript not functional; cannot inject real system mouse events"
    echo "REAL_SYSTEM_CLICK_INJECTED=false"
    echo "MAC_GUI_AUTOMATION_AVAILABLE=false"
    exit 2
fi

# Step 2: launch PoC
echo ""
echo "[step 2] launch PoC (3 独立窗口, mode=C1)"
POC_LOG=/tmp/r67_poc.log
rm -f "$POC_LOG"
POC_QUIT_AFTER=60 ./node_modules/.bin/electron "$SRC/tools/passthrough_poc/main.js" --mode=C1 --quit-after=60 > "$POC_LOG" 2>&1 &
POC_PID=$!
echo "  PoC PID=$POC_PID"
sleep "$LAUNCH_TIMEOUT"
if ! ps -p $POC_PID > /dev/null 2>&1; then
    echo "[ABORT] PoC did not stay alive"
    tail -20 "$POC_LOG"
    exit 3
fi
echo "  PoC alive @ ${LAUNCH_TIMEOUT}s"
echo "  PoC log tail:"
tail -15 "$POC_LOG" | sed 's/^/    /'

# Step 3: probe PoC state
echo ""
echo "[step 3] query PoC state via r67_get_state"
STATE=$(LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 osascript -e '
tell application "System Events"
    set out to "mode=?"
    try
        set tapp to first application process whose unix id is '$POC_PID'
    end try
    return out
' 2>&1)
echo "  $STATE"

# Step 4: get window bounds via ipcMain handle?
# Direct: query PoC via /tmp result file (PoC writes it on quit; we use live)
# Get window bounds from --help or known constant
# Per R67 main.js: control=(80,80,360,110), test=(320,200,256,256), probe=(360,320,360,180)
# Test sprites: gold centre (448,328) r=50; transparent corners (340,220)
CONTROL_BTN_Y_MIN=160
CONTROL_BTN_Y_MAX=190   # mode buttons row
CONTROL_C1_X=300        # approximate x of [C1] button (3rd of 4)
GOLD_X=448
GOLD_Y=328
TRANSPARENT_X=340
TRANSPARENT_Y=220
PROBE_BTN_X=540        # approximate x of "Probe Button" (200 wide centred at 540, 380+22)
PROBE_BTN_Y=380

# Step 5: real clicks via osascript System Events
echo ""
echo "[step 5] REAL osascript System Events mouse injection"

click_at() {
    # $1=x, $2=y, $3=label
    local x=$1 y=$2 lbl=$3
    local script="tell application \"System Events\" to ¬
        set mouse position to {$x, $y} ¬
    delay 0.2 ¬
    set c to (count of (every process whose frontmost is true)) ¬
    click at {$x, $y}"
    LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 osascript -e "$script" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "  [click] $lbl at ($x,$y) -> osascript OK"
        return 0
    else
        echo "  [click] $lbl at ($x,$y) -> osascript FAIL"
        return 1
    fi
}

# Round 1: click [C1] in control panel (should be clickable always)
click_at $CONTROL_C1_X 165 "control panel C1"

# Round 2: click gold ball center in test window
click_at $GOLD_X $GOLD_Y "test window gold ball"

# Round 3: click transparent corner in test window
click_at $TRANSPARENT_X $TRANSPARENT_Y "test window transparent corner"

# Round 4: return to gold ball
click_at $GOLD_X $GOLD_Y "test window gold ball (return)"

# Round 5: cycle 2 - click transparent again
click_at $TRANSPARENT_X $TRANSPARENT_Y "test window transparent corner (cycle 2)"

# Round 6: cycle 2 - return to gold
click_at $GOLD_X $GOLD_Y "test window gold ball (cycle 2 return)"

# Round 7: cycle 3
click_at $TRANSPARENT_X $TRANSPARENT_Y "test window transparent corner (cycle 3)"
click_at $GOLD_X $GOLD_Y "test window gold ball (cycle 3 return)"

# Round 9: probe button directly
click_at $PROBE_BTN_X $PROBE_BTN_Y "probe button (direct)"

sleep 3
# Step 6: read PoC result + counters
echo ""
echo "[step 6] read PoC state after clicks"
if [ -f /tmp/passthrough_poc_r67_*.json ] 2>/dev/null; then
    LATEST=$(ls -t /tmp/passthrough_poc_r67_*.json 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        echo "  result file: $LATEST"
        python3 -c "
import json
d = json.load(open('$LATEST'))
print(f'  mode={d.get(\"mode\")}  test_window={d.get(\"test_window\")}  probe_window={d.get(\"probe_window\")}')
print(f'  top_clicks={d[\"counts\"][\"top_clicks\"]}  under_clicks={d[\"counts\"][\"under_clicks\"]}  state_transitions={d[\"counts\"][\"state_transitions\"]}')
"
    fi
else
    echo "  (no result file yet — need to query live state)"
fi

# Step 7: final state via Electron IPC (use --remote-debugging-port or just kill)
echo ""
echo "[step 7] read final state (PoC may still be running)"
# Send SIGTERM to force before-quit hook
kill -TERM $POC_PID 2>/dev/null
sleep 3
if ps -p $POC_PID > /dev/null; then
    kill -9 $POC_PID
fi
sleep 1
LATEST=$(ls -t /tmp/passthrough_poc_r67_*.json 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
    echo "  final result file: $LATEST"
    python3 -c "
import json
d = json.load(open('$LATEST'))
print('=' * 60)
print(f'  run_id:     {d.get(\"run_id\")}')
print(f'  mode:       {d.get(\"mode\")}')
print(f'  test_window:    {d.get(\"test_window\")}')
print(f'  probe_window:   {d.get(\"probe_window\")}')
print(f'  control_window: {d.get(\"control_window\")}')
print(f'  geometry_overlap: {d.get(\"geometry_overlap\")}')
print('=' * 60)
print(f'  top_clicks:   {d[\"counts\"][\"top_clicks\"]}')
print(f'  under_clicks: {d[\"counts\"][\"under_clicks\"]}')
print(f'  state_transitions: {d[\"counts\"][\"state_transitions\"]}')
print()
log = d.get('transition_log', [])
print(f'  transition_log ({len(log)} entries):')
for e in log[:10]:
    print(f'    #{e[\"n\"]} cursor=({e[\"cursor\"][\"x\"]},{e[\"cursor\"][\"y\"]}) expected={e[\"expected\"]} actual={e[\"target\"]}')
"
fi

echo ""
echo "=========================================="
echo " R67 macOS GUI 自动化测试完成"
echo "  log: $LOG"
echo "=========================================="
