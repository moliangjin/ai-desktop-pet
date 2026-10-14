#!/usr/bin/env bash
# tools/passthrough_poc/m87_fake_clicker.sh
#
# R87 E2E 模拟点击器 (MOCK_CLICKER) — 模拟不同失败/成功场景.
# 通过 FAKE_CLICKER_MODE 环境变量控制行为.
# 不发送任何真实 mouse event.

set -e
MODE="${FAKE_CLICKER_MODE:-ok}"
X="${1:-100}"
Y="${2:-200}"

case "$1" in
    --ax-check) MODE=ax-check-ok; shift;;
    --self-test) MODE=self-test-ok; shift;;
esac
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
