# AViz — Audio Visualization

Premium audio visualization for Windows: live spectrum from your speakers, file heatmaps, playlists.

## Setup (once)

```powershell
cd Audio_Visualization
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Run

```powershell
python main.py
```

That opens the main window (Home, Live, Player tabs).

---

## Using the UI

### Live — speaker / headphone monitoring

1. **Live** tab → play music on your PC.
2. **Auto-detect** → picks the output that has audio.
3. **Start listening** → full spectrum (Hz vs dB).
4. **Visual FX** on the right for colormap, range, glow, etc.

### Home — library & playlists

1. **Create workspace** or **Open workspace**.
2. **Add files** (try the `samples` folder).
3. **Open in Player** when ready.

### Player

Workspace required. Heatmap, play/pause, seek, prev/next, Visual FX.

**Menu:** File · View · Help → Quick start guide.

---

## Sample audio

`samples/` contains synthetic test WAVs. Add them via **Home → Add files**.

---

## Android APK

See [docs/ANDROID.md](docs/ANDROID.md). Builds require **Linux or WSL** (or use the GitHub Actions workflow). Live monitoring uses the device **microphone** on Android (not Windows-style speaker loopback).

## Developers

```powershell
pytest
python scripts/generate_sample_audio.py
```

## License

[MIT License](LICENSE) — see [LICENSE](LICENSE) for details.
