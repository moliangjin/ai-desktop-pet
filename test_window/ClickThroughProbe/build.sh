#!/usr/bin/env bash
# test_window/ClickThroughProbe/build.sh
#
# Build the passthrough probe app — a 360x180 NSWindow with a clickable
# button. Used to verify that the pet candidates' transparent pixels let
# mouse clicks fall through to whatever is underneath.
#
# Output: build/ClickThroughProbe.app — launch with `open` or directly:
#   ./build/ClickThroughProbe.app/Contents/MacOS/ClickThroughProbe
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/build/ClickThroughProbe.app"
rm -rf "$OUT"
mkdir -p "$OUT/Contents/MacOS" "$OUT/Contents/Resources"

cat > "$OUT/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>ClickThroughProbe</string>
  <key>CFBundleDisplayName</key><string>ClickThroughProbe</string>
  <key>CFBundleIdentifier</key><string>com.v0.clickthroughprobe</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleExecutable</key><string>ClickThroughProbe</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

clang -fobjc-arc \
    -framework AppKit \
    -O2 \
    -o "$OUT/Contents/MacOS/ClickThroughProbe" \
    "$HERE/main.m"

echo "[build] built $OUT"
ls -la "$OUT/Contents/MacOS/ClickThroughProbe"
