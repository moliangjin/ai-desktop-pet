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
# R88 修复: tr -d 不能去换行 — 否则连续多个 tick 黏成一行 JSON.parse 必败.
# 改为: JSON 内 tab 和多余空格用 tr -d 删, 但每个 tick 末尾必须有 \n 分隔.
emit_tick() {
    local mode="$1" clicks_test="$2" clicks_probe="$3" ignore="$4" no_c1="${5:-false}"
    # R88: no_c1=true 时省略 control_buttons.c1 (测试 no-c1-button 场景)
    if [ "$no_c1" = "true" ]; then
        cat <<TICK | tr -d "\n\t "
{"type":"poc-tick","run_id":"m87_fake_poc","mode":"$mode","ignore":$ignore,"test_window":{"x":320,"y":200,"w":256,"h":256},"probe_window":{"x":360,"y":320,"w":360,"h":180},"control_window":{"x":80,"y":80,"w":360,"h":220},"sprite":{"cx":448,"cy":328,"r":50},"probe_button":{"x":372,"y":414,"w":284,"h":36},"control_buttons":{"a":{"x":92,"y":130,"w":60,"h":30},"b":{"x":158,"y":130,"w":60,"h":30},"c2":{"x":290,"y":130,"w":60,"h":30}},"clicks":{"test":$clicks_test,"probe":$clicks_probe},"transitions":0}
TICK
    else
        cat <<TICK | tr -d "\n\t "
{"type":"poc-tick","run_id":"m87_fake_poc","mode":"$mode","ignore":$ignore,"test_window":{"x":320,"y":200,"w":256,"h":256},"probe_window":{"x":360,"y":320,"w":360,"h":180},"control_window":{"x":80,"y":80,"w":360,"h":220},"sprite":{"cx":448,"cy":328,"r":50},"probe_button":{"x":372,"y":414,"w":284,"h":36},"control_buttons":{"a":{"x":92,"y":130,"w":60,"h":30},"b":{"x":158,"y":130,"w":60,"h":30},"c1":{"x":224,"y":130,"w":60,"h":30},"c2":{"x":290,"y":130,"w":60,"h":30}},"clicks":{"test":$clicks_test,"probe":$clicks_probe},"transitions":0}
TICK
    fi
    printf '\n'
}

# 持续 emit_tick 循环 (mode, test, probe, ignore, no_c1?) — 保持 latestTick.__updated 新鲜
emit_loop() {
    local mode="$1" init_t="$2" init_p="$3" ignore="$4" no_c1="${5:-false}"
    local t=$init_t p=$init_p
    local end_time=$((SECONDS + QUIT_AFTER))
    while [ $SECONDS -lt $end_time ]; do
        t=$((t+1))
        p=$((p+1))
        emit_tick "$mode" $t $p $ignore $no_c1
        sleep 0.2
    done
}

case "$MODE" in
    success)
        # R88: 先发 A 阶段让 orchestrator 拿到 firstTick.mode=A,
        # sleep 1, 再切 C1, 然后 emit_loop 保持 latestTick 时效.
        emit_tick A 0 0 false
        emit_tick A 0 0 false
        emit_tick A 0 0 false
        sleep 1
        emit_tick C1 0 0 true
        emit_tick C1 1 0 true
        emit_tick C1 1 1 true
        emit_tick C1 2 1 true
        emit_loop C1 2 1 true false
        exit 0
        ;;
    mode-a-only)
        # 持续发 A 不切 C1 — orchestrator 收到 tick 但 mode-switch 失败 (exit 4)
        emit_loop A 0 0 false false
        exit 0
        ;;
    broken-json)
        # 持续输出非法 JSON — orchestrator 永远 parse 失败 → timeout (exit 6)
        end_time=$((SECONDS + QUIT_AFTER))
        while [ $SECONDS -lt $end_time ]; do
            printf '{not_json\n'
            sleep 0.2
        done
        exit 0
        ;;
    no-c1-button)
        # 持续发 tick 但省略 control_buttons.c1 — orchestrator 找不到 C1 (exit 8)
        emit_loop A 0 0 false true
        exit 0
        ;;
    exit-early)
        # 发几次 tick 然后立即退出 — 测试 orchestrator 处理 partial
        emit_tick A 0 0 false
        emit_tick A 0 0 false
        sleep 1
        exit 0
        ;;
    no-tick)
        # 一直不发 tick — orchestrator timeout
        sleep $QUIT_AFTER
        exit 0
        ;;
    signal-mode)
        sleep 0.5
        exit 0
        ;;
    *)
        sleep $QUIT_AFTER
        exit 0
        ;;
esac
