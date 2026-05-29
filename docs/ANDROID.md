# AViz on Android

AViz can be packaged as an Android APK using **PySide6** and `pyside6-android-deploy`. The same UI (Home, Live, Player, spectrograms, Visual FX) runs on device with platform-specific audio backends.

## Important limitations

| Feature | Windows desktop | Android |
|--------|------------------|---------|
| Live — system / speaker loopback | WASAPI loopback (PyAudioWPatch) | **Microphone** input (Android does not expose full system loopback to apps) |
| Player — file formats | All formats via soundfile + ffmpeg for video | soundfile when bundled; WAV fallback via stdlib; **no ffmpeg** in APK unless you add it |
| Spectrum / spectrogram charts | pyqtgraph | **Disabled** in APK (pyqtgraph crashes natively); UI placeholders only |
| Build host | Windows OK | **Linux only** (WSL, VM, or GitHub Actions) |

“Full function” here means all tabs, charts, workspaces, playlists, and file analysis — not identical Windows loopback behavior.

## Build the APK (Linux or WSL)

1. Install Ubuntu (WSL2 or native) and Python 3.11.
2. Clone this repo and install host tools:

```bash
sudo apt-get update
sudo apt-get install -y git zip unzip openjdk-17-jdk autoconf libtool pkg-config \
  zlib1g-dev libncurses5-dev libncursesw5-dev cmake libffi-dev libssl-dev
python3 -m venv .venv && source .venv/bin/activate
pip install "PySide6==6.10.2" buildozer==1.5.0 "cython==0.29.33"
pip install -r "$(python -c "import PySide6, os; print(os.path.join(os.path.dirname(PySide6.__file__), 'scripts', 'requirements-android.txt'))")"
```

3. Download Android wheels (match your PySide6 version):

```bash
mkdir wheels
curl -fL -o wheels/PySide6.whl \
  https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.2-6.10.2-cp311-cp311-android_aarch64.whl
curl -fL -o wheels/shiboken6.whl \
  https://download.qt.io/official_releases/QtForPython/shiboken6/shiboken6-6.10.2-6.10.2-cp311-cp311-android_aarch64.whl
```

4. Download NDK/SDK (once):

```bash
git clone --depth 1 --branch 6.10.2 https://code.qt.io/pyside/pyside-setup.git /tmp/pyside-setup
pip install -r /tmp/pyside-setup/tools/cross_compile_android/requirements.txt
python /tmp/pyside-setup/tools/cross_compile_android/main.py --download-only --skip-update --auto-accept-license
```

5. Deploy (from repo root; `main.py` must stay the entry point):

```bash
NDK=~/.pyside6_android_deploy/android-ndk/android-ndk-r27c
SDK=~/.pyside6_android_deploy/android-sdk
pyside6-android-deploy --config-file pysidedeploy.spec --name aviz \
  --wheel-pyside wheels/PySide6.whl \
  --wheel-shiboken wheels/shiboken6.whl \
  --ndk-path "$NDK" --sdk-path "$SDK" \
  --force --keep-deployment-files -v
python android/patch_buildozer.py buildozer.spec
buildozer android debug
```

The APK appears under `.buildozer/.../bin/`.

## Build without local Linux (GitHub Actions)

Push to GitHub and run **Actions → Android APK → Run workflow**, or push to `main`/`master`. Download **aviz-android-apk** from the run artifacts.

## Install on device

Enable “Install unknown apps” for your file manager, copy `AViz-debug.apk` to the phone, and install. Grant **microphone** and **storage/media** permissions when prompted.

## App closes immediately on launch

The most common cause was a **missing `soundfile` module** at import time: `PlayerTab` loads `aviz.audio.decoder`, which used to `import soundfile` at module level even though the APK does not bundle it. Rebuild from a commit that lazy-imports `soundfile` (WAV analysis still works via the stdlib).

On launch you should see a short **toast**: “AViz: Python started”. If the app still closes instantly with **no toast**, Python is not starting (native/Qt packaging issue — not fixable from Python alone).

If Python runs but something fails, a **Qt error dialog** appears, or **open the app again** for “previous crash”.

## Windows-only note

`pyside6-android-deploy` does **not** run on Windows. Use WSL2 Ubuntu, a Linux VM, or the GitHub workflow above.
