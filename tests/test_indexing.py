"""Indexing: reading sidecar .txt files and building the database (taginDB.py)."""
import os
import sqlite3

import pytest

taginDB = pytest.importorskip("taginDB")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_read_sidecar_returns_tags_without_favorites_tag(tmp_path):
    sidecar = tmp_path / "a.txt"
    write(sidecar, "blue sky\nbeach\n\nuser:favorites\n")
    assert taginDB.read_sidecar_file(str(sidecar)) == ["blue_sky", "beach"]


def test_read_sidecar_without_favorites_tag(tmp_path):
    """Regression: this used to raise ValueError, so a fresh install indexed 0 images."""
    sidecar = tmp_path / "a.txt"
    write(sidecar, "cat\nindoor\n")
    assert taginDB.read_sidecar_file(str(sidecar)) == ["cat", "indoor"]


def test_read_sidecar_latin1_fallback(tmp_path):
    sidecar = tmp_path / "a.txt"
    sidecar.write_bytes("caf\xe9\n".encode("latin-1"))
    assert taginDB.read_sidecar_file(str(sidecar)) == ["caf\xe9"]


def test_read_sidecar_missing_file_returns_empty(tmp_path):
    assert taginDB.read_sidecar_file(str(tmp_path / "missing.txt")) == []


@pytest.fixture
def index_env(tmp_path, monkeypatch):
    images = tmp_path / "static" / "images" / "demo"
    write(images / "one.txt", "blue sky\nbeach\n")
    (images / "one.jpg").write_bytes(b"")
    write(images / "two.txt", "cat\nuser:favorites\n")
    (images / "two.png").write_bytes(b"")
    write(images / "orphan.txt", "no image\n")  # sidecar with no image
    (images / "notags.jpg").write_bytes(b"")  # image with no sidecar

    monkeypatch.setattr(taginDB, "script_dir", str(tmp_path))
    monkeypatch.setattr(taginDB, "directory_path", str(tmp_path / "static" / "images"))
    monkeypatch.setattr(taginDB, "db_path", str(tmp_path / "data.db"))
    taginDB.initialize_database()
    return tmp_path


def test_finds_image_sidecar_pairs(index_env):
    files, total_sidecars = taginDB.get_files_to_process(taginDB.directory_path, set())
    assert total_sidecars == 3
    assert sorted(p for p, _ in files) == [
        "static/images/demo/one.jpg",
        "static/images/demo/two.png",
    ]


def test_skips_already_indexed_files(index_env):
    files, _ = taginDB.get_files_to_process(
        taginDB.directory_path, {"static/images/demo/one.jpg"}
    )
    assert [p for p, _ in files] == ["static/images/demo/two.png"]


def test_full_index_writes_every_image(index_env):
    files, _ = taginDB.get_files_to_process(taginDB.directory_path, set())
    chunks = str(index_env / "chunks")
    taginDB.process_chunk(files, 0, chunks)
    taginDB.merge_chunk_databases(chunks, taginDB.db_path, 1)

    conn = sqlite3.connect(taginDB.db_path)
    rows = dict(conn.execute("SELECT image_path, tags FROM tags").fetchall())
    conn.close()
    assert rows == {
        "static/images/demo/one.jpg": "blue_sky, beach",
        "static/images/demo/two.png": "cat",
    }
    assert taginDB.get_existing_files() == set(rows)
    assert not os.path.exists(os.path.join(chunks, "chunk_0.db"))


def test_batch_size_is_sane():
    assert taginDB.calculate_batch_size(10) == 10
    assert taginDB.calculate_batch_size(30000) == 2000
    assert taginDB.calculate_batch_size(500000) == 10000
