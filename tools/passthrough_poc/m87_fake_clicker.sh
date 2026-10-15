#!/usr/bin/env bash
# tools/passthrough_poc/m87_fake_clicker.sh
#
# R89 事件驱动 MOCK clicker — 每次 click 写 sentinel /tmp/m87_mock_click_signal,
# 让 fake_poc 按几何判定 +1. 没 click = 没 sentinel = fake_poc 计数不变.
# 通过 FAKE_CLICKER_MODE 控制行为. 不发送任何真实 mouse event.

set -e
MODE="${FAKE_CLICKER_MODE:-ok}"
# R88: 坐标默认 0/0 (避免 --ax-check 等选项参数被当作 X/Y 拼到 JSON 损坏解析)
X=0
Y=0
# 仅当参数看起来像数字时才覆盖坐标
if [[ "$1" =~ ^-?[0-9]+$ ]]; then X="$1"; fi
if [[ "$2" =~ ^-?[0-9]+$ ]]; then Y="$2"; fi

# R88: FAKE_CLICKER_MODE 优先于命令行参数 — 否则测试 ax-blocked 时被 --ax-check
# 强制覆盖成 ax-check-ok, 测不出失败路径.
if [ -z "$FAKE_CLICKER_MODE" ]; then
    case "$1" in
        --ax-check) MODE=ax-check-ok; shift;;
        --self-test) MODE=self-test-ok; shift;;
    esac
fi

# R89: 写 click signal sentinel — fake_poc 用它判定 +1
# 仅当 click 实际"发生"时写. AX-check / self-test 不写 signal (因为没真 click).
# R89b: 每个 click 写独立文件 (避免连续 click 覆盖), fake_poc glob 消费所有
SIGNAL_DIR="${MOCK_CLICK_SIGNAL_DIR:-/tmp/m87_click_signals}"
mkdir -p "$SIGNAL_DIR"
write_signal() {
    # 用 PID + ns + x + y 命名, 永不冲突
    local fn="${SIGNAL_DIR}/click_${$}_$(date +%s)}_${X}_${Y}"
    printf '{"x":%d,"y":%d,"ts":%d}\n' "$X" "$Y" "$(date +%s)" > "$fn"
}

case "$MODE" in
    ok)
        # R89: 真 click → 写 sentinel
        write_signal
        echo '{"result":"OK","event":"MOCK_CLICK_POSTED","x":'$X',"y":'$Y'}'
        exit 0
        ;;
    ax-blocked)
        echo '{"result":"BLOCKED","reason":"fake AX blocked"}'
        exit 11
        ;;
    invalid-json)
        echo 'this is not json'
        exit 0
        ;;
    self-test-ok)
        echo '{"result":"SELFTEST_OK","accessibility_granted":true,"event_post_fn":"linked","no_event_dispatched":true}'
        exit 0
        ;;
    self-test-fail)
        echo '{"result":"FAIL","reason":"forced"}'
        exit 10
        ;;
    ax-ok-self-test-fail)
        STATE_FILE="/tmp/m87_fake_clicker_state"
        PREV=$(cat "$STATE_FILE" 2>/dev/null || echo "")
        if [ -z "$PREV" ]; then
            echo '{"result":"OK","accessibility_granted":true}' > "$STATE_FILE"
            echo '{"result":"OK","accessibility_granted":true}'
            exit 0
        else
            /bin/rm -f "$STATE_FILE"
            echo '{"result":"FAIL","reason":"self-test forced"}'
            exit 10
        fi
        ;;
    ax-check-ok)
        echo '{"result":"OK","accessibility_granted":true}'
        exit 0
        ;;
    ax-check-blocked)
        echo '{"result":"BLOCKED","reason":"fake AX blocked"}'
        exit 11
        ;;
    param-nan)
        echo '{"result":"FAIL","reason":"coord not finite"}'
        exit 10
        ;;
    click-ok-no-count-change)
        # R89: 故意不写 sentinel — click OK 但 fake_poc 不响应 (测 orchestrator mode-switch FAIL)
        echo '{"result":"OK","event":"MOCK_CLICK_POSTED_NO_CHANGE","x":'$X',"y":'$Y'}'
        exit 0
        ;;
    click-signal-no-count)
        # R89b: 写 sentinel 让 fake_poc 切 C1 (响应), 但 fake_poc 模式 ignore-clicks 不 +1 → gold-count FAIL
        write_signal
        echo '{"result":"OK","event":"MOCK_CLICK_SIGNAL_NO_COUNT","x":'$X',"y":'$Y'}'
        exit 0
        ;;
    wrong-target)
        # R89b: 写独立信号文件但 x/y 故意偏移到错误目标 (999,999)
        WT_FN="${SIGNAL_DIR}/click_${$}_$(date +%s)_999_999"
        printf '{"x":999,"y":999,"ts":%d}\n' "$(date +%s)" > "$WT_FN"
        echo '{"result":"OK","event":"MOCK_CLICK_WRONG_TARGET","x":'$X',"y":'$Y'}'
        exit 0
        ;;
    click-fail)
        # R89: --ax-check / --self-test 走 OK, 普通 click 返 FAIL
        if [ "$1" = "--ax-check" ]; then
            echo '{"result":"OK","accessibility_granted":true}'
            exit 0
        elif [ "$1" = "--self-test" ]; then
            echo '{"result":"SELFTEST_OK","accessibility_granted":true}'
            exit 0
        fi
        echo '{"result":"FAIL","reason":"forced click fail"}'
        exit 10
        ;;
    crash)
        exit 99
        ;;
    *)
        echo '{"result":"FAIL","reason":"unknown mode"}'
        exit 10
        ;;
esac
