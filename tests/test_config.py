from pathlib import Path

from ilfootball.config import Settings, load_settings


def test_load_settings_reads_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ILF_DATA_DIR", str(tmp_path))
    s = load_settings()
    assert s.data_dir == tmp_path
    assert s.raw_dir == tmp_path / "raw"
    assert s.db_path == tmp_path / "ilfootball.duckdb"


def test_interval_for_known_and_unknown_host():
    s = Settings(data_dir=Path("data"))
    assert s.interval_for("www.transfermarkt.com") == 6.0
    assert s.interval_for("example.org") == 5.0
