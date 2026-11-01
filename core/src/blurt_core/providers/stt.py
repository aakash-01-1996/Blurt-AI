import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class Segment:
    __slots__ = ("start", "end", "text")

    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text

    def to_dict(self) -> dict[str, float | str]:
        return {"start": self.start, "end": self.end, "text": self.text}


@dataclass
class TranscriptionResult:
    """Output of an STT provider.

    `language` is the detected *source* language (ISO code, e.g. "en", "hi",
    "mr") when the provider reports it, else None. When the provider ran in
    translate mode, `text`/`segments` are English regardless of `language`.
    """

    text: str
    segments: list[Segment] = field(default_factory=list)
    language: str | None = None


@runtime_checkable
class SttProvider(Protocol):
    model_name: str

    def transcribe(self, audio_bytes: bytes) -> TranscriptionResult: ...


class MlxWhisperStt:
    """On-device transcription via mlx-whisper (Apple Silicon only)."""

    def __init__(self, model: str = "mlx-community/whisper-small", translate: bool = False) -> None:
        self.model_name = model
        self._translate = translate

    def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        import os
        import tempfile

        import mlx_whisper

        # mlx_whisper requires a file path
        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            result = mlx_whisper.transcribe(
                tmp_path,
                path_or_hf_repo=self.model_name,
                # `translate` emits English for any source language; `transcribe`
                # keeps the source language.
                task="translate" if self._translate else "transcribe",
            )
        finally:
            os.unlink(tmp_path)

        text: str = result.get("text", "").strip()
        segments = [
            Segment(
                start=float(s["start"]),
                end=float(s["end"]),
                text=s["text"].strip(),
            )
            for s in result.get("segments", [])
        ]
        language = result.get("language")
        return TranscriptionResult(text=text, segments=segments, language=language)


class GroqStt:
    """Cloud transcription via Groq Whisper API."""

    def __init__(
        self,
        api_key: str,
        model: str = "whisper-large-v3-turbo",
        translate: bool = False,
    ) -> None:
        self.model_name = model
        self._api_key = api_key
        self._translate = translate

    def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        import io

        from groq import Groq

        client = Groq(api_key=self._api_key)
        audio_file = ("audio.flac", io.BytesIO(audio_bytes), "audio/flac")

        response: Any
        if self._translate:
            # The translations endpoint always outputs English and only
            # supports whisper-large-v3 (not the turbo model).
            response = client.audio.translations.create(
                file=audio_file,
                model=self.model_name,
                response_format="verbose_json",
            )
        else:
            response = client.audio.transcriptions.create(
                file=audio_file,
                model=self.model_name,
                response_format="verbose_json",
            )

        text: str = (response.text or "").strip()
        raw_segments = getattr(response, "segments", None) or []
        segments = [
            Segment(
                start=float(s["start"]),
                end=float(s["end"]),
                text=(s["text"] or "").strip(),
            )
            for s in raw_segments
        ]
        language = getattr(response, "language", None)
        return TranscriptionResult(text=text, segments=segments, language=language)


def build_stt_provider(settings: object) -> MlxWhisperStt | GroqStt:
    from blurt_core.config import Settings

    assert isinstance(settings, Settings)
    translate = settings.stt_translate
    if settings.stt_provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required when STT_PROVIDER=groq")
        model = settings.stt_model or "whisper-large-v3-turbo"
        if translate and "turbo" in model:
            # Groq's translations endpoint rejects the turbo model; fall back to
            # the full large-v3 which it does support.
            logger.info(
                "overriding STT model for translate mode",
                extra={"from": model, "to": "whisper-large-v3"},
            )
            model = "whisper-large-v3"
        return GroqStt(api_key=settings.groq_api_key, model=model, translate=translate)
    return MlxWhisperStt(model=settings.stt_model, translate=translate)
