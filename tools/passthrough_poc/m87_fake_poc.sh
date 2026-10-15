#!/usr/bin/env bash
# tools/passthrough_poc/m87_fake_poc.sh
#
# R89 事件驱动 fake PoC — 严格按 click 信号 +1, 无信号计数永远不变.
#
# 协议:
#   - orchestrator → clickJson → fake_clicker 写 /tmp/m87_mock_click_signal
#   - fake_poc emit_loop 每 200ms 检查 signal, 按当前 tick 几何判定命中哪个 window
#   - 仅命中时 +1 (test_window/sprite → test+1; transparent → probe+1; c1 button → 切 C1)
#   - 无 signal → 计数不变
#   - mode-a-only / broken-json / no-c1-button / exit-early / no-tick 等 mode 控制行为
#
# 与 fake_clicker 配合: fake_clicker ok 模式每次 click 写 sentinel; click-ok-no-count-change
# 模式只写 sentinel 但 fake_poc 不消费 (测试 click OK 但 PoC 计数不变).

set -e
MODE="${FAKE_POC_MODE:-success}"
QUIT_AFTER="${QUIT_AFTER:-30}"
POC_PATH="${2:-/unused}"
SIGNAL_FILE="${MOCK_CLICK_SIGNAL:-/tmp/m87_mock_click_signal}"
SIGNAL_DIR="${MOCK_CLICK_SIGNAL_DIR:-/tmp/m87_click_signals}"
mkdir -p "$SIGNAL_DIR"
SCENARIO_FILE="${MOCK_POC_SCENARIO:-/tmp/m87_fake_poc_scenario}"
# R89 debug
[ -n "${MOCK_POC_DEBUG_LOG:-}" ] && printf '[start] MODE=%s QUIT_AFTER=%s PID=%s SIGNAL_DIR=%s argv_count=%s\n' "$MODE" "$QUIT_AFTER" "$$" "$SIGNAL_DIR" "$#" >> "$MOCK_POC_DEBUG_LOG"

# R89: 不在 startup rm signal — 让 emit_loop 自然消费 (standalone 测试需先写信号)
# R89: 强制 /bin/rm 绕开用户环境可能的 rm alias (mavis-trash 会输出 stdout 污染返回值)

# 默认几何 (与 fake_poc tick 输出对齐)
DEFAULT_GEOM_JSON='{"test_window":{"x":320,"y":200,"w":256,"h":256},"probe_window":{"x":360,"y":320,"w":360,"h":180},"control_window":{"x":80,"y":80,"w":360,"h":220},"sprite":{"cx":448,"cy":328,"r":50},"probe_button":{"x":372,"y":414,"w":284,"h":36},"control_buttons":{"c1":{"x":224,"y":130,"w":60,"h":30}}}'

# tick 输出 — R88 修复: tr -d 不能去换行; 末尾 printf '\n'.
emit_tick() {
    local mode="$1" clicks_test="$2" clicks_probe="$3" ignore="$4" no_c1="${5:-false}"
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

# 消费 click signals — glob 找所有信号文件, 每个独立判定 +1
# R89b: 每个 click 独立文件, 永不覆盖, 严格 click→+1 因果
consume_signals() {
    local sig_files=()
    # glob 信号文件
    for f in "$SIGNAL_DIR"/click_*; do
        [ -f "$f" ] || continue
        sig_files+=("$f")
    done
    if [ ${#sig_files[@]} -eq 0 ]; then return 1; fi
    # 处理每个 signal
    local hits=()
    for f in "${sig_files[@]}"; do
        local sig
        sig=$(cat "$f")
        /bin/rm -f "$f"
        HIT=$(MOCK_HIT_GEOM="$DEFAULT_GEOM_JSON" MOCK_HIT_SIGNAL="$sig" python3 -c "
import os, json, sys, math
sig = json.loads(os.environ['MOCK_HIT_SIGNAL'])
geom = json.loads(os.environ['MOCK_HIT_GEOM'])
x, y = float(sig['x']), float(sig['y'])
tw = geom['test_window']; pw = geom['probe_window']; cw = geom['control_window']
sp = geom['sprite']; c1 = geom.get('control_buttons', {}).get('c1', {})
def in_rect(px, py, r): return r['x'] <= px < r['x']+r['w'] and r['y'] <= py < r['y']+r['h']
in_tw = in_rect(x, y, tw)
in_pw = in_rect(x, y, pw)
in_cw = in_rect(x, y, cw)
in_sprite = math.hypot(x-sp['cx'], y-sp['cy']) < sp['r']
in_c1 = in_rect(x, y, c1) if c1 else False
if in_c1 and in_cw:
    print('c1:hit')
elif in_tw and in_sprite:
    print('test:+1')
elif in_tw:
    pb = geom.get('probe_button')
    if pb and in_rect(x, y, pb):
        print('probe:+1')
    else:
        print('test:+1')
elif in_pw:
    print('probe:+1')
else:
    print('none')
" 2>/dev/null) || HIT='none'
        hits+=("$HIT")
    done
    # R89b: 仅输出 hit (stdout) — DEBUG 走 stderr 避免污染返回值
    printf '%s\n' "${hits[@]}"
}

# 持续 emit_loop — 仅在有 signal 时才 +1
emit_loop() {
    local mode="$1" ignore="$2" no_c1="${3:-false}"
    local t=0 p=0
    local end_time=$((SECONDS + QUIT_AFTER))
    [ -n "${MOCK_POC_DEBUG_LOG:-}" ] && printf '[emit_loop] start mode=%s end_time=%s\n' "$mode" "$end_time" >> "$MOCK_POC_DEBUG_LOG"
    # R89c: 捕获 SIGTERM/SIGPIPE 让 fake_poc 知道何时被 orchestrator 杀
    cleanup() {
        [ -n "${MOCK_POC_DEBUG_LOG:-}" ] && printf '[emit_loop] killed SIG=%s SECONDS=%s\n' "$1" "$SECONDS" >> "$MOCK_POC_DEBUG_LOG"
        exit 0
    }
    trap 'cleanup TERM' SIGTERM
    trap 'cleanup PIPE' SIGPIPE
    while [ $SECONDS -lt $end_time ]; do
        # R89b: 一次循环处理多个独立 signal
        local HITS
        HITS=$(consume_signals 2>/dev/null || echo "none")
        local HIT
        while IFS= read -r HIT; do
            [ -z "$HIT" ] && continue
            case "$HIT" in
                test:*) t=$((t+1));;
                probe:*) p=$((p+1));;
                c1:hit)
                    if [ "${MOCK_POC_NO_MODE_SWITCH:-false}" = "true" ]; then
                        :
                    else
                        mode=C1
                        t=$((t+1))
                        p=$((p+1))
                    fi
                    ;;
                *) ;;
            esac
        done <<< "$HITS"
        # R89c: emit_tick 输出可能在 pipe 满时阻塞 → 忽略 SIGPIPE 仍写
        emit_tick "$mode" $t $p "$ignore" "$no_c1" || break
        [ -n "${MOCK_POC_DEBUG_LOG:-}" ] && printf 'mode=%s test=%d probe=%d SECONDS=%s\n' "$mode" "$t" "$p" "$SECONDS" >> "$MOCK_POC_DEBUG_LOG"
        sleep 0.2
    done
    [ -n "${MOCK_POC_DEBUG_LOG:-}" ] && printf '[emit_loop] end\n' >> "$MOCK_POC_DEBUG_LOG"
}

case "$MODE" in
    success)
        # R89: 先 A tick 让 orchestrator 拿到 firstTick.mode=A,
        # 然后 emit_loop 从 A 开始, 等待 click signal:
        #   - orchestrator 点 C1 按钮 (254,145) → c1:hit → 切 C1
        #   - 点 gold (448,328) → test:+1
        #   - 透明点 (372,414) → probe:+1 (穿透)
        emit_tick A 0 0 false
        emit_tick A 0 0 false
        emit_tick A 0 0 false
        sleep 1
        emit_loop A true false
        exit 0
        ;;
    mode-a-only)
        # 持续 A 不切 C1 — 即使收到 c1 signal 也不切
        MOCK_POC_NO_MODE_SWITCH=true emit_loop A false false
        exit 0
        ;;
    broken-json)
        end_time=$((SECONDS + QUIT_AFTER))
        while [ $SECONDS -lt $end_time ]; do
            printf '{not_json\n'
            sleep 0.2
        done
        exit 0
        ;;
    no-c1-button)
        emit_loop A false true
        exit 0
        ;;
    exit-early)
        emit_tick A 0 0 false
        emit_tick A 0 0 false
        sleep 1
        exit 0
        ;;
    no-tick)
        sleep $QUIT_AFTER
        exit 0
        ;;
    ignore-clicks)
        # R89: 收到 click signal 但不 +1 (测 click OK 但 PoC 计数不变)
        # 通过 MOCK_POC_NO_INCREMENT sentinel 触发
        while [ $SECONDS -lt $((SECONDS + QUIT_AFTER)) ]; do
            if [ -f "$SIGNAL_FILE" ]; then
                rm -f "$SIGNAL_FILE"   # 消费但不 +1
            fi
            emit_tick A 0 0 false false
            sleep 0.2
        done
        exit 0
        ;;
    wrong-target)
        # R89: 收到 click signal 但 +1 到错误计数 (test 变 probe, probe 变 test)
        local t=0 p=0
        local end_time=$((SECONDS + QUIT_AFTER))
        while [ $SECONDS -lt $end_time ]; do
            if [ -f "$SIGNAL_FILE" ]; then
                sig=$(cat "$SIGNAL_FILE"); rm -f "$SIGNAL_FILE"
                # 故意反转
                HIT=$(MOCK_HIT_GEOM="$DEFAULT_GEOM_JSON" MOCK_HIT_SIGNAL="$sig" python3 -c "
import os, json, math
sig = json.loads(os.environ['MOCK_HIT_SIGNAL'])
geom = json.loads(os.environ['MOCK_HIT_GEOM'])
x, y = float(sig['x']), float(sig['y'])
tw = geom['test_window']
sp = geom['sprite']
in_tw = tw['x'] <= x < tw['x']+tw['w'] and tw['y'] <= y < tw['y']+tw['h']
in_sprite = math.hypot(x-sp['cx'], y-sp['cy']) < sp['r']
# 故意: 在 test_window 但不在 sprite → 报 probe+1 (错)
# 在 sprite → 报 probe+1 (错)
print('probe:+1' if in_tw else 'none')
" 2>/dev/null || echo "none")
                case "$HIT" in
                    probe:*) p=$((p+1));;
                    *) ;;
                esac
            fi
            emit_tick A $t $p false false
            sleep 0.2
        done
        exit 0
        ;;
    *)
        sleep $QUIT_AFTER
        exit 0
        ;;
esac
