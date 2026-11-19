from ilfootball.db.connect import init_db

EXPECTED = {"competition", "season", "club", "player", "match", "lineup", "event", "standing", "id_map"}


def tables(con):
    return {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}


def test_init_db_creates_all_tables(tmp_path):
    con = init_db(tmp_path / "sub" / "t.duckdb")
    assert EXPECTED <= tables(con)


def test_init_db_is_idempotent(tmp_path):
    path = tmp_path / "t.duckdb"
    init_db(path).close()
    con = init_db(path)
    assert EXPECTED <= tables(con)
