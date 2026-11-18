"""Shared fixtures for the SimpleImageBoard test suite.

db_utils and Images_searcher open ./database/data.db and ./templates/... relative
to the current directory when they are imported, so every test gets a fresh
temporary working directory and fresh imports. Your real database is never touched.
"""
import builtins
import importlib
import json
import os
import sys
import time

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Small tag-type table used by colorcode() (the real one is ~14 MB).
TAG_TYPES = {
    "blue_sky": {"type": "0"},
    "beach": {"type": "0"},
    "cat": {"type": "4"},
}

# A small library: path -> tags
LIBRARY = {
    "static/images/demo/1.jpg": ["beach", "blue_sky", "sunset"],
    "static/images/demo/2.jpg": ["beach", "dog"],
    "static/images/demo/3.png": ["cat", "indoor"],
    "static/images/demo/4.jpg": ["cat", "blue_sky", "outdoor"],
    "static/images/demo/5.mp4": ["dog", "outdoor", "video_clip"],
}


def _fresh_import(name):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Empty working directory with the files the app expects at import time."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "list of tags.json").write_text(json.dumps(TAG_TYPES))
    return tmp_path


@pytest.fixture
def db(workdir):
    """A fresh db_utils module backed by a temporary database."""
    db_utils = _fresh_import("db_utils")
    db_utils.initialize_database()
    yield db_utils
    db_utils.get_db_connection().close()
    sys.modules.pop("db_utils", None)


@pytest.fixture
def library(db, workdir):
    """db_utils with LIBRARY loaded (files exist on disk), plus image 4 favorited."""
    for path, tags in LIBRARY.items():
        full = workdir / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(b"")
        db.upsert_tags(path, tags)
    conn = db.get_db_connection()
    conn.execute("INSERT OR IGNORE INTO tag_counts (tag, count) VALUES ('user:favorites', 0)")
    conn.commit()
    db.add_to_favorites(4)
    return db


@pytest.fixture
def app(library, monkeypatch):
    """The Flask app (Images_searcher) wired to the temporary library."""
    monkeypatch.setattr(builtins, "input", lambda *a, **k: "1")
    monkeypatch.setattr(time, "sleep", lambda *a, **k: None)
    module = _fresh_import("Images_searcher")
    module.app.config["TESTING"] = True
    yield module
    sys.modules.pop("Images_searcher", None)


@pytest.fixture
def client(app):
    return app.app.test_client()


def ids_for(db, *paths):
    return [db.fetch_tags_with_id(p)["id"] for p in paths]
