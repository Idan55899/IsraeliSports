import pytest

from ilfootball.core.raw_store import RawStore


def test_save_then_load_roundtrip(tmp_path):
    store = RawStore(tmp_path)
    path = store.save("ifa", "match", "12345", "html", "<p>שלום</p>".encode())
    assert path == tmp_path / "ifa" / "match" / "12345.html.gz"
    assert store.exists("ifa", "match", "12345", "html")
    assert store.load("ifa", "match", "12345", "html").decode() == "<p>שלום</p>"


def test_keys_are_sanitised(tmp_path):
    store = RawStore(tmp_path)
    path = store.path_for("ifa", "match", "season=2025/26&id=7", "html")
    assert path.name == "season_2025_26_id_7.html.gz"


def test_empty_key_rejected(tmp_path):
    with pytest.raises(ValueError):
        RawStore(tmp_path).path_for("ifa", "match", "///", "html")
