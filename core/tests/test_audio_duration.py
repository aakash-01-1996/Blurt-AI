"""probe_duration: header path, decode fallback, and the N/A case."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from blurt_core import audio

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")


def _make_wav(seconds: float) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = Path(f.name)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:duration={seconds}",
                str(path),
            ],
            capture_output=True,
            check=True,
        )
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


@needs_ffmpeg
def test_probe_duration_reads_normal_file() -> None:
    assert abs(audio.probe_duration(_make_wav(1.0)) - 1.0) < 0.3


@needs_ffmpeg
def test_decode_duration_direct() -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        f.write(_make_wav(2.0))
        f.flush()
        dur = audio._decode_duration(f.name)
    assert dur is not None and abs(dur - 2.0) < 0.3


class _FakeProc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_na_header_falls_back_to_decode(monkeypatch: pytest.MonkeyPatch) -> None:
    """ffprobe returns 'N/A' (as with MediaRecorder WebM) → decode fallback is used."""

    def fake_run(cmd: list[str], *args: object, **kwargs: object) -> _FakeProc:
        if cmd[0] == "ffprobe":
            return _FakeProc(returncode=0, stdout="N/A\n")
        # ffmpeg decode prints progress with time= on stderr
        return _FakeProc(returncode=0, stderr="size=N/A time=00:00:03.50 bitrate=N/A")

    monkeypatch.setattr(audio.subprocess, "run", fake_run)
    assert audio.probe_duration(b"fake-webm-bytes") == pytest.approx(3.5)


def test_unreadable_audio_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], *args: object, **kwargs: object) -> _FakeProc:
        if cmd[0] == "ffprobe":
            return _FakeProc(returncode=1, stderr="Invalid data found")
        return _FakeProc(returncode=1, stderr="Invalid data found")  # no time= → None

    monkeypatch.setattr(audio.subprocess, "run", fake_run)
    with pytest.raises(audio.AudioError):
        audio.probe_duration(b"garbage")
