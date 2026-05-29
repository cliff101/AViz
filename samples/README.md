# Sample audio (synthetic, royalty-free)

WAV files here are **generated test tones**, not commercial music. Safe for CI and local QA.

Regenerate:

```bash
python scripts/generate_sample_audio.py
```

| File | Purpose |
|------|---------|
| `tone_440hz.wav` | Pure A4 tone — spectrum peak test |
| `chord_major.wav` | C major chord — multiple frequency peaks |
| `sweep_log.wav` | Log frequency sweep — heatmap diagonal |
| `melody_arpeggio.wav` | Short arpeggio — playlist / playback |
| `stereo_pan.wav` | Stereo pan — channel decode |
| `mixed_bands.wav` | Bass + mid + treble — band energy |

Use in **Home → workspace → Add files** pointing at this folder.
