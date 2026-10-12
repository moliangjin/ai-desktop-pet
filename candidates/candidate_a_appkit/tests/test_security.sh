#!/bin/bash
# T10: Security boundaries — verify no permission requests, no real API keys.
set -euo pipefail
ROOT="/Users/musk123/Downloads/minimax工作文件夹/软件开发/AI桌宠_v0.0_workspace/AI-Desktop-Companion-V0.0"
EXT="$ROOT/candidates/candidate_a_appkit"

echo "[T10] static checks"

# 1. Source must not import privacy-sensitive frameworks
FORBIDDEN=("AVCaptureDevice" "AVAudioSession" "CGEventTapCreate" "IOHIDManager" "ScreenCapture" "CoreGraphicsDisplayCapture" "TCC" "CGRequestScreen" "IOSurface" "kSec" "Security")
for sym in "${FORBIDDEN[@]}"; do
    if grep -RIn --include='*.m' --include='*.h' "$sym" "$EXT/src" 2>/dev/null | head -1; then
        echo "  [FAIL] forbidden symbol $sym referenced"
        exit 1
    fi
done
echo "  ok — no privacy-sensitive framework symbols."

# 2. No hard-coded API keys (looking for common cloud provider key shapes)
if grep -RIn -E '(sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z\-_]{30,}|xoxb-[0-9-]+)' "$EXT" 2>/dev/null | head -1; then
    echo "  [FAIL] hard-coded API key pattern"
    exit 1
fi
echo "  ok — no hard-coded API key patterns."

# 3. No file-write to home/user directories
if grep -RIn --include='*.m' '/Users/' "$EXT/src" 2>/dev/null | grep -v "// " | grep -v "NSHomeDirectory" | head -1; then
    echo "  [WARN] source references /Users/ path — verify it is a documentation comment only"
fi

# 4. No network code (URLSession / NSURLConnection / fetch / XMLHttpRequest)
if grep -RIn --include='*.m' --include='*.h' -E '(NSURLSession|NSURLConnection|CFHTTPMessage)' "$EXT/src" 2>/dev/null | head -1; then
    echo "  [FAIL] network API used"
    exit 1
fi
echo "  ok — no network calls."

echo "[T10] PASS — security boundary checks clean."
