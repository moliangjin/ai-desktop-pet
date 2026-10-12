#!/bin/bash
# Build script for candidate A: Objective-C + AppKit.
# Uses CommandLineTools SDK + clang; no Swift involved (Swift toolchain has
# CommandLineTools modulemap redefinition bug on this machine — see
# docs/03_验收与审计规范.md §B). Objective-C reaches the same NSWindow API
# surface, so this is the equivalent native path.
set -euo pipefail

cd "$(dirname "$0")"
HERE="$(pwd)"

SDK="$(xcrun --sdk macosx --show-sdk-path)"
OUT=build/PetCandidateA
mkdir -p build

CLANG="$(xcrun --find clang)"

echo "[build.sh] SDK=$SDK"
echo "[build.sh] clang=$($CLANG --version | head -1)"

# Compile each .m into .o, then link.
SRCS=(src/Manifest.m src/FrameStore.m src/PerfSampler.m src/InputSynth.m
      src/PetView.m src/PetWindow.m src/AppDelegate.m src/main.m)

OBJS=()
for s in "${SRCS[@]}"; do
    o="build/$(basename "$s" .m).o"
    echo "[build.sh] compile $s -> $o"
    $CLANG -fobjc-arc -O0 -g \
        -isysroot "$SDK" \
        -mmacosx-version-min=14.0 \
        -Wall -Wno-deprecated-declarations \
        -c "$s" -o "$o"
    OBJS+=("$o")
done

echo "[build.sh] link"
$CLANG -fobjc-arc \
    -isysroot "$SDK" \
    -mmacosx-version-min=14.0 \
    -framework Cocoa -framework CoreGraphics -framework QuartzCore \
    -o "$OUT" "${OBJS[@]}"

echo "[build.sh] built: $OUT"
ls -la "$OUT"
file "$OUT"

# V0.0 R41: 解决 macOS Taskgated SIGKILL "Code Signature Invalid"。
# 根因：R38/R39 cp 二进制到 _app_bundle/PetCandidateA.app/Contents/MacOS/ 后，
# 原 adhoc 签名里的资源哈希链已与新二进制不再一致，launchd 在启动 .app 时
# Taskgated 拒绝加载并 SIGKILL。
# 崩溃报告关键字段：
#   signal: "SIGKILL (Code Signature Invalid)"
#   termination.namespace: "CODESIGNING"
#   termination.indicator: "Taskgated Invalid Signature"
# 修复：
#   1. 本 build.sh 自动把新二进制 cp 到 ../../_app_bundle/PetCandidateA.app/Contents/MacOS/
#   2. 立刻 codesign --force --deep --sign - 重新签整个 .app
#   3. codesign --verify --deep --strict --verbose=2 自验
#   4. 修复 Info.plist 中 CFBundleIdentifier 中的 BundleIdentifier 必须与代码一致
PROJECT_BUNDLE="$(cd "$HERE/../.." && pwd)/_app_bundle/PetCandidateA.app"
echo "[R41] 目标 .app: $PROJECT_BUNDLE"
if [ -d "$PROJECT_BUNDLE" ]; then
    echo "[R41] copy $OUT -> $PROJECT_BUNDLE/Contents/MacOS/PetCandidateA"
    cp "$OUT" "$PROJECT_BUNDLE/Contents/MacOS/PetCandidateA"
    chmod +x "$PROJECT_BUNDLE/Contents/MacOS/PetCandidateA"

    echo "[R41] codesign --force --deep --sign - $PROJECT_BUNDLE"
    codesign --force --deep --sign - "$PROJECT_BUNDLE" 2>&1
    echo "[R41] codesign --verify"
    codesign --verify --deep --strict --verbose=2 "$PROJECT_BUNDLE" 2>&1
    echo "[R41] codesign -dvv"
    codesign -dvv "$PROJECT_BUNDLE" 2>&1 | head -12
else
    echo "[R41] WARN: $PROJECT_BUNDLE 不存在，跳过签名"
fi
