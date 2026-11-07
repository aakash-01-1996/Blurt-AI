import tempfile

from blurt_core.providers.storage import FakeStorage, LocalDiskStorage


def test_fake_storage_put_get_delete() -> None:
    s = FakeStorage()
    s.put("key/file.flac", b"audio", "audio/flac")
    assert s.get("key/file.flac") == b"audio"
    s.delete("key/file.flac")
    try:
        s.get("key/file.flac")
        assert False, "should have raised"
    except KeyError:
        pass


def test_local_disk_storage_round_trip() -> None:
    with tempfile.TemporaryDirectory() as d:
        s = LocalDiskStorage(d)
        s.put("recordings/user/abc.flac", b"data", "audio/flac")
        assert s.get("recordings/user/abc.flac") == b"data"
        url = s.playback_url("recordings/user/abc.flac")
        assert url.startswith("/api/v1/audio/")
        s.delete("recordings/user/abc.flac")


def test_fake_storage_playback_url() -> None:
    s = FakeStorage()
    s.put("x.flac", b"d", "audio/flac")
    assert "x.flac" in s.playback_url("x.flac")


def test_local_disk_storage_rejects_out_of_base_keys() -> None:
    import pytest

    with tempfile.TemporaryDirectory() as d:
        s = LocalDiskStorage(d)
        for bad in ("../escape.flac", "a/../../escape.flac", "/etc/passwd"):
            with pytest.raises(ValueError, match="invalid storage key"):
                s.put(bad, b"data", "audio/flac")
            with pytest.raises(ValueError, match="invalid storage key"):
                s.get(bad)


def test_local_disk_storage_allows_nested_keys() -> None:
    with tempfile.TemporaryDirectory() as d:
        s = LocalDiskStorage(d)
        s.put("recordings/user-123/abc.flac", b"data", "audio/flac")
        assert s.get("recordings/user-123/abc.flac") == b"data"
