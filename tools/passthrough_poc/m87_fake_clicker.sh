#!/usr/bin/env bash
# tools/passthrough_poc/m87_fake_clicker.sh
#
# R87 E2E 模拟点击器 (MOCK_CLICKER) — 模拟不同失败/成功场景.
# 通过 FAKE_CLICKER_MODE 环境变量控制行为.
# 不发送任何真实 mouse event.

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
case "$MODE" in
    ok)
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
        # R88: 第一次调用 --ax-check → OK; 后续 --self-test → FAIL
        # 用固定 state file (不用 $$ 因为每次 spawn 新 process PID 不同)
        STATE_FILE="/tmp/m87_fake_clicker_state"
        PREV=$(cat "$STATE_FILE" 2>/dev/null || echo "")
        if [ -z "$PREV" ]; then
            echo '{"result":"OK","accessibility_granted":true}' > "$STATE_FILE"
            echo '{"result":"OK","accessibility_granted":true}'
            exit 0
        else
            rm -f "$STATE_FILE"
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
        # 返回 OK 但 click count 不会变 (test 可验证 orchestrator 是否判 FAIL)
        echo '{"result":"OK","event":"MOCK_CLICK_POSTED_NO_CHANGE","x":'$X',"y":'$Y'}'
        exit 0
        ;;
    crash)
        exit 99
        ;;
    *)
        echo '{"result":"FAIL","reason":"unknown mode"}'
        exit 10
        ;;
esac
