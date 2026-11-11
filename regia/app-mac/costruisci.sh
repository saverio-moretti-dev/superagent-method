#!/bin/zsh
# Costruisce Regia.app in regia/app-mac/build/ e (con --installa) la copia in ~/Applications.
set -euo pipefail
cd "${0:A:h}"
B=build/Regia.app
rm -rf build; mkdir -p "$B/Contents/MacOS" "$B/Contents/Resources" build/tmp
swiftc -O -o "$B/Contents/MacOS/Regia" main.swift
cp Info.plist "$B/Contents/Info.plist"
# Icona: svg → png 1024 (qlmanage), contenuto 824 px con margine trasparente (griglia icone macOS).
qlmanage -t -s 1024 -o build/tmp ../web/icone/regia.svg >/dev/null 2>&1
P=build/tmp/regia.svg.png
sips -z 824 824 "$P" --out build/tmp/c.png >/dev/null
sips -p 1024 1024 build/tmp/c.png --out build/tmp/base.png >/dev/null
I=build/tmp/Regia.iconset; mkdir -p "$I"
for s in 16 32 128 256 512; do
  sips -z $s $s build/tmp/base.png --out "$I/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) build/tmp/base.png --out "$I/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$I" -o "$B/Contents/Resources/Regia.icns"
rm -rf build/tmp
codesign --force --deep -s - "$B"
echo "costruita: $PWD/$B"
if [[ "${1:-}" == "--installa" ]]; then
  mkdir -p ~/Applications
  pkill -x Regia 2>/dev/null || true
  rm -rf ~/Applications/Regia.app
  cp -R "$B" ~/Applications/Regia.app
  echo "installata: ~/Applications/Regia.app"
fi
