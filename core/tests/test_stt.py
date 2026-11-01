"""STT provider dispatch + translate-mode tests (hermetic: groq/mlx mocked)."""

import sys
import types
from unittest.mock import MagicMock

import pytest
from blurt_core.config import Settings
from blurt_core.providers.stt import (
    GroqStt,
    MlxWhisperStt,
    build_stt_provider,
)

# ── build_stt_provider ────────────────────────────────────────────────────────


def test_build_groq_translate_overrides_turbo_model() -> None:
    s = Settings(
        stt_provider="groq",
        groq_api_key="k",
        stt_model="whisper-large-v3-turbo",
        stt_translate=True,
    )
    provider = build_stt_provider(s)
    assert isinstance(provider, GroqStt)
    # translations endpoint doesn't support turbo → must fall back to large-v3
    assert provider.model_name == "whisper-large-v3"
    assert provider._translate is True


def test_build_groq_no_translate_keeps_turbo() -> None:
    s = Settings(
        stt_provider="groq",
        groq_api_key="k",
        stt_model="whisper-large-v3-turbo",
        stt_translate=False,
    )
    provider = build_stt_provider(s)
    assert isinstance(provider, GroqStt)
    assert provider.model_name == "whisper-large-v3-turbo"
    assert provider._translate is False


def test_build_mlx_carries_translate_flag() -> None:
    s = Settings(
        stt_provider="mlx",
        stt_model="mlx-community/whisper-small",
        stt_translate=True,
    )
    provider = build_stt_provider(s)
    assert isinstance(provider, MlxWhisperStt)
    assert provider._translate is True


# ── GroqStt endpoint dispatch ─────────────────────────────────────────────────


def _install_fake_groq(monkeypatch: pytest.MonkeyPatch, response: MagicMock) -> MagicMock:
    client = MagicMock()
    client.audio.translations.create.return_value = response
    client.audio.transcriptions.create.return_value = response
    fake_mod = types.ModuleType("groq")
    fake_mod.Groq = MagicMock(return_value=client)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "groq", fake_mod)
    return client


def _groq_response(language: str) -> MagicMock:
    response = MagicMock()
    response.text = "hello world"
    response.segments = [{"start": 0.0, "end": 1.0, "text": "hello world"}]
    response.language = language
    return response


def test_groq_translate_uses_translations_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _install_fake_groq(monkeypatch, _groq_response("hi"))

    provider = GroqStt(api_key="k", model="whisper-large-v3", translate=True)
    result = provider.transcribe(b"audio")

    client.audio.translations.create.assert_called_once()
    client.audio.transcriptions.create.assert_not_called()
    assert result.text == "hello world"
    assert result.language == "hi"
    assert len(result.segments) == 1
    assert result.segments[0].start == 0.0


def test_groq_no_translate_uses_transcriptions_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _install_fake_groq(monkeypatch, _groq_response("en"))

    provider = GroqStt(api_key="k", model="whisper-large-v3-turbo", translate=False)
    result = provider.transcribe(b"audio")

    client.audio.transcriptions.create.assert_called_once()
    client.audio.translations.create.assert_not_called()
    assert result.language == "en"


# ── MlxWhisperStt task dispatch ───────────────────────────────────────────────


def test_mlx_translate_passes_translate_task(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_transcribe(path: str, *, path_or_hf_repo: str, task: str) -> dict:
        captured["task"] = task
        return {
            "text": "hello",
            "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
            "language": "mr",
        }

    fake_mod = types.ModuleType("mlx_whisper")
    fake_mod.transcribe = fake_transcribe  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake_mod)

    provider = MlxWhisperStt(model="m", translate=True)
    result = provider.transcribe(b"audio")

    assert captured["task"] == "translate"
    assert result.text == "hello"
    assert result.language == "mr"


def test_mlx_no_translate_uses_transcribe_task(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_transcribe(path: str, *, path_or_hf_repo: str, task: str) -> dict:
        captured["task"] = task
        return {"text": "hi", "segments": [], "language": "en"}

    fake_mod = types.ModuleType("mlx_whisper")
    fake_mod.transcribe = fake_transcribe  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake_mod)

    provider = MlxWhisperStt(model="m", translate=False)
    provider.transcribe(b"audio")

    assert captured["task"] == "transcribe"
