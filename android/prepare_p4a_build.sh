#!/usr/bin/env bash
# Reset python-for-android checkout so the next buildozer run uses a fresh p4a tree.
set -euo pipefail

P4A_ROOT=".buildozer/android/platform/python-for-android"
if [ -d "${P4A_ROOT}" ]; then
  echo "Removing cached python-for-android at ${P4A_ROOT}"
  rm -rf "${P4A_ROOT}"
fi
