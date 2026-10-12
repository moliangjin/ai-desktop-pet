#!/usr/bin/env bash
# test_window/PetAcceptor/build.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/build/PetAcceptor.app"
rm -rf "$OUT"
mkdir -p "$OUT/Contents/MacOS" "$OUT/Contents/Resources"

cat > "$OUT/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>PetAcceptor</string>
  <key>CFBundleDisplayName</key><string>PetAcceptor</string>
  <key>CFBundleIdentifier</key><string>com.v0.petacceptor</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleExecutable</key><string>PetAcceptor</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

clang -fobjc-arc \
    -framework AppKit -framework Foundation \
    -O2 \
    -o "$OUT/Contents/MacOS/PetAcceptor" \
    "$HERE/main.m"

echo "[build] $OUT/Contents/MacOS/PetAcceptor"
ls -la "$OUT/Contents/MacOS/PetAcceptor"

# 自动 adhoc 签名（R45 经验 — 与候选 A 同样原因）
codesign --force --deep --sign - "$OUT" 2>&1
codesign --verify --deep --strict "$OUT" 2>&1
