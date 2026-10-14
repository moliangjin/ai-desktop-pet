#!/usr/bin/env bash
# tools/passthrough_poc/m87_fake_poc.sh
#
# R87 E2E 模拟 PoC (MOCK_POC) — argv[0] 是此脚本, 后续 argv 是 PoC 路径.
# 通过 FAKE_POC_MODE 控制行为.

set -e
MODE="${FAKE_POC_MODE:-success}"
QUIT_AFTER="${QUIT_AFTER:-30}"
# 第二个参数是 PoC 路径 (我们忽略, 不真跑 electron)
POC_PATH="${2:-/unused}"

# 模拟几个 tick 输出, 包含 mode A 状态, C1 按钮位置, 金球位置
emit_tick() {
    local mode="$1" clicks_test="$2" clicks_probe="$3" ignore="$4"
    cat <<TICK | tr -d "\n\t "
{"type":"poc-tick","run_id":"m87_fake_poc","mode":"$mode","ignore":$ignore,
 "test_window":{"x":320,"y":200,"w":256,"h":256},
 "probe_window":{"x":360,"y":320,"w":360,"h":180},
 "control_window":{"x":80,"y":80,"w":360,"h":220},
 "sprite":{"cx":448,"cy":328,"r":50},
 "probe_button":{"x":372,"y":414,"w":284,"h":36},
 "control_buttons":{"a":{"x":92,"y":130,"w":60,"h":30},
                  "b":{"x":158,"y":130,"w":60,"h":30},
                  "c1":{"x":224,"y":130,"w":60,"h":30},
                  "c2":{"x":290,"y":130,"w":60,"h":30}},
 "clicks":{"test":$clicks_test,"probe":$clicks_probe},
 "transitions":0}
TICK
}

case "$MODE" in
    success)
        # 3 tick: mode=A, then after click mode=C1
        # 立即发全套 tick (A → C1, 测试/探针计数 1, 1, cycles)
        emit_tick A 0 0 false
        emit_tick A 0 0 false
        emit_tick A 0 0 false
        emit_tick C1 0 0 true
        emit_tick C1 1 0 true
        emit_tick C1 1 1 true
        emit_tick C1 2 1 true
        for i in 1 2 3; do
            emit_tick C1 $((3+i)) $((1+i)) true
        done
        # 等 QUIT_AFTER 秒 (默认 8) 后退出
        sleep $QUIT_AFTER
        exit 0
        ;;
    mode-a-only)
        # 只发 A, 不切 C1 → orchestrator 应判 control_click FAIL
        emit_tick A 0 0 false
        sleep $QUIT_AFTER
        exit 0
        ;;
    broken-json)
        echo '{not_json'
        sleep $QUIT_AFTER
        exit 0
        ;;
    no-c1-button)
        emit_tick A 0 0 false
        sleep $QUIT_AFTER
        exit 0
        ;;
    exit-early)
        emit_tick A 0 0 false
        sleep 1
        exit 0  # 提早退出
        ;;
    no-tick)
        # 一直不发 tick, 让 orchestrator timeout
        sleep $QUIT_AFTER
        exit 0
        ;;
    signal-mode)
        # 发 SIGTERM 到 orchestrator (要求 orchestrator handle)
        # 实际上 fake poc 退出 0 后 orchestrator 看到 exit → 触发 cleanup
        sleep 0.5
        exit 0
        ;;
    *)
        sleep $QUIT_AFTER
        exit 0
        ;;
esac
