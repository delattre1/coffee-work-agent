#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
output_path="${1:-$HOME/Library/Application Support/Hermes/PrepareMyMac/bin/hermes-native-meeting}"
temporary_path="${output_path}.tmp.$$"

mkdir -p "${output_path:h}"
trap 'rm -f "$temporary_path"' EXIT

/usr/bin/xcrun --find swiftc >/dev/null
/usr/bin/xcrun swiftc -O -swift-version 5 \
  "$script_dir/native_meeting.swift" \
  -framework AVFoundation \
  -framework CoreMedia \
  -framework ScreenCaptureKit \
  -framework Speech \
  -Xlinker -sectcreate \
  -Xlinker __TEXT \
  -Xlinker __info_plist \
  -Xlinker "$script_dir/NativeInfo.plist" \
  -o "$temporary_path"

/bin/chmod 700 "$temporary_path"
/bin/mv "$temporary_path" "$output_path"
print -r -- "$output_path"
