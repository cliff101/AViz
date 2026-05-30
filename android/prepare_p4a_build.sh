#!/usr/bin/env bash
# Reset cached p4a / gradle dist so buildozer picks up patched buildozer.spec (api 35, etc.).
set -euo pipefail

P4A_ROOT=".buildozer/android/platform/python-for-android"
if [ -d "${P4A_ROOT}" ]; then
  echo "Removing cached python-for-android at ${P4A_ROOT}"
  rm -rf "${P4A_ROOT}"
fi

for DIST in .buildozer/android/platform/build-*/dists/aviz; do
  if [ -d "${DIST}" ]; then
    echo "Removing cached gradle dist at ${DIST}"
    rm -rf "${DIST}"
  fi
done
