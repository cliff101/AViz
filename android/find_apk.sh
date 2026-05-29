#!/usr/bin/env bash
# Print path to the newest debug APK from buildozer / p4a / gradle output.
set -euo pipefail
find . -type f -name "*debug*.apk" ! -path "*/intermediates/*" 2>/dev/null \
  | sort \
  | tail -1
