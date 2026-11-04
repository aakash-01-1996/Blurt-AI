import re
import subprocess
import tempfile
from pathlib import Path

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


class AudioError(Exception):
    pass


def _decode_duration(path: str) -> float | None:
    """Duration by fully decoding the stream (slow but works when the container
    header has no duration, e.g. MediaRecorder WebM). Returns None if unknown."""
    result = subprocess.run(
        ["ffmpeg", "-i", path, "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    matches = _TIME_RE.findall(result.stderr)
    if not matches:
        return None
    hours, minutes, seconds = matches[-1]
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def probe_duration(data: bytes) -> float:
    """Return duration in seconds. Uses the ffprobe header first; if that's
    missing (N/A) — common for browser MediaRecorder streams — falls back to
    decoding the stream. Raises AudioError if the audio is unreadable."""
    with tempfile.NamedTemporaryFile(suffix=".audio") as f:
        f.write(data)
        f.flush()
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                f.name,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            try:
                return float(result.stdout.strip())
            except ValueError:
                pass  # header has no duration (e.g. "N/A") → decode below

        decoded = _decode_duration(f.name)

    if decoded is not None:
        return decoded
    if result.returncode != 0:
        raise AudioError(f"ffprobe failed: {result.stderr.strip()}")
    raise AudioError(f"could not parse duration: {result.stdout!r}")


def normalize(data: bytes) -> bytes:
    """Convert audio to 16 kHz mono FLAC. Raises AudioError on failure."""
    # Keep the input file open/alive for the whole ffmpeg run — it must still
    # exist on disk when ffmpeg reads it.
    with tempfile.NamedTemporaryFile(suffix=".input") as src:
        src.write(data)
        src.flush()

        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as dst:
            dst_path = Path(dst.name)

        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    src.name,
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(dst_path),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise AudioError(f"ffmpeg failed: {result.stderr.strip()}")
            return dst_path.read_bytes()
        finally:
            dst_path.unlink(missing_ok=True)
