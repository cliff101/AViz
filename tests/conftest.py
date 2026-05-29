"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.sample_audio import generate_all_samples, list_sample_paths

ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = ROOT / "samples"


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    """Ensure synthetic sample WAVs exist under samples/."""
    if not SAMPLES_DIR.exists() or not any(SAMPLES_DIR.glob("*.wav")):
        generate_all_samples(SAMPLES_DIR)
    return SAMPLES_DIR


@pytest.fixture(scope="session")
def sample_paths(samples_dir: Path) -> dict[str, Path]:
    paths = list_sample_paths(samples_dir)
    assert len(paths) >= 4, "Expected sample WAV fixtures in samples/"
    return paths


@pytest.fixture
def tone_wav(sample_paths: dict[str, Path]) -> Path:
    return sample_paths["tone_440hz.wav"]


@pytest.fixture
def melody_wav(sample_paths: dict[str, Path]) -> Path:
    return sample_paths["melody_arpeggio.wav"]


@pytest.fixture
def sweep_wav(sample_paths: dict[str, Path]) -> Path:
    return sample_paths["sweep_log.wav"]


@pytest.fixture
def tmp_workspace(tmp_path: Path):
    """Empty parent dir for workspace create/open tests."""
    return tmp_path / "ws_test"
