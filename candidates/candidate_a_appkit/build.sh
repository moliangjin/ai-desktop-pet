#!/bin/bash
# Build script for candidate A: Objective-C + AppKit.
# Uses CommandLineTools SDK + clang; no Swift involved (Swift toolchain has
# CommandLineTools modulemap redefinition bug on this machine — see
# docs/03_验收与审计规范.md §B). Objective-C reaches the same NSWindow API
# surface, so this is the equivalent native path.
set -euo pipefail

cd "$(dirname "$0")"

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
