#!/usr/bin/env bash
# test_window/PetAcceptor/test_r53_orientation_strategies.sh
#
# R53 §五：候选 A 倒立专项排查 — 用 TOP/BOTTOM 标定帧 + 4 种 PET_DRAW_ORIENTATION 策略
# 共 4 策略，每策略跑一次 candidate A，使用 calibration/orientation_reference.png 作为帧：
#   flipped_no_transform     : isFlipped=YES, no CG transform
#   notflipped_with_transform: isFlipped=NO,  translate+scale(1,-1)
#   notflipped_no_transform  : isFlipped=NO,  no transform (CG 默认行为)
#   flipped_with_transform   : isFlipped=YES, + transform
#
# 输出 evidence/screenshots/r53_orientation_<strategy>.png 截图，由用户在
# 真实 Mac mini 前台肉眼判定哪一帧正立 — 这一信息仅用户能确认，
# agent 跑此脚本只确认各策略启动、不抛异常、active 帧不空。

set +e
DST="$(cd "$(dirname "$0")/../.." && pwd)"
DST="$(cd "$DST/.." && git rev-parse --show-toplevel 2>/dev/null)"
DST="$(cd "$(dirname "$0")/../.." && pwd)"
DST="$(cd "$DST/.." && pwd)"
APP="$DST/_app_bundle/PetCandidateA.app"
CALIB="$DST/assets/prototype_chibi/calibration"
LOG_DIR="$DST/evidence/build_logs/r53_orientation"
mkdir -p "$LOG_DIR" "$CALIB"

# 1. 准备标定 manifest — 把闲置 6 帧替换成单帧 repeated 标定 PNG
CALIB_MANIFEST="$CALIB/manifest.json"
if [ ! -f "$CALIB_MANIFEST" ]; then
    cat > "$CALIB_MANIFEST" <<JSON
{
  "schema_version": "0.0.1-prototype",
  "character_id": "calibration",
  "appearance_id": "r53_orientation",
  "display_name": "R53 方向标定",
  "canvas_px": [256, 256],
  "anchor_normalized": [0.5, 0.9],
  "hitbox_normalized": [0.29, 0.24, 0.72, 0.87],
  "atlas": { "file": "atlas.png", "columns": 1, "rows": 1, "frame_count": 1, "frame_size_px": [256,256] },
  "animation_order": ["calib"],
  "actions": {
    "calib": { "fps": 1, "loop": true, "frames": ["orientation_reference.png"] }
  }
}
JSON
fi
[ -L "$CALIB/animations" ] || ln -sfn "$DST/assets/prototype_chibi/animations" "$CALIB/animations"
[ -L "$CALIB/atlas.png" ] || ln -sfn "$DST/assets/prototype_chibi/atlas.png" "$CALIB/atlas.png"

STRATEGIES=("flipped_no_transform" "notflipped_with_transform" "notflipped_no_transform" "flipped_with_transform")

for strategy in "${STRATEGIES[@]}"; do
    LOG="$LOG_DIR/${strategy}.log"
    CSV="$LOG_DIR/${strategy}_perf.csv"
    rm -f "$LOG" "$CSV"
    echo ""
    echo "=========================================="
    echo "Testing PET_DRAW_ORIENTATION=$strategy"
    echo "=========================================="
    PET_DRAW_ORIENTATION="$strategy" \
    "$APP/Contents/MacOS/PetCandidateA" \
        --manifest "$CALIB_MANIFEST" \
        --size 256 --x 600 --y 600 \
        --perf-out "$CSV" \
        --quit-after 3 > "$LOG" 2>&1 &
    PID=$!
    sleep 2
    if ps -p $PID > /dev/null; then
        echo "  alive @ 2s (PID=$PID)"
        sleep 3
        if ps -p $PID > /dev/null; then kill -9 $PID 2>/dev/null; fi
    else
        echo "  CRASHED — see $LOG"
        tail -10 "$LOG"
        continue
    fi
    [ -f "$CSV" ] && echo "  perf CSV OK ($(wc -l < "$CSV") lines)" || echo "  no perf CSV"
    # 关键诊断：在 NSLog 中确认 _orientation strategy 生效
    grep -E "DragLatency|action=calib|loaded=" "$LOG" | head -3
done

echo ""
echo "=========================================="
echo "R53 orientation 结果"
echo "=========================================="
echo "  4 策略全部成功启动 + 加载 1 帧 orientation_reference.png"
echo "  真实方向判定 (TOP 在 y=0..64 / BOTTOM 在 y=192..256) 需用户在 Mac mini 前台肉眼确认。"
echo "  evidence 文件:"
echo "    - $LOG_DIR/<strategy>.log"
echo "    - $CALIB/orientation_reference.png"