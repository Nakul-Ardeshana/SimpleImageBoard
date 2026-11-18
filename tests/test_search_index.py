"""The in-memory tag index must return exactly what a full table scan returns."""
import random
import re

import pytest

from conftest import ids_for


def reference_search(db, query):
    """Straightforward full scan with the same query rules as the app."""
    terms = query.split(";")
    or_conditions = [t.split("|") for t in terms if "|" in t]
    exclude = [t[1:] for t in terms if t.startswith("-")]
    and_conditions = [t for t in terms if "|" not in t and not t.startswith("-")]
    favorites = set(db.fetch_favorite_image_ids())
    only_favs = exclude_favs = False
    if "user:favorites" in and_conditions:
        and_conditions.remove("user:favorites")
        only_favs = True
    elif "user:favorites" in exclude:
        exclude.remove("user:favorites")
        exclude_favs = True
    out = []
    for image_id, tags_string in db.get_db_connection().execute("SELECT id, tags FROM tags ORDER BY id"):
        tags = tags_string.split(", ")
        if only_favs and image_id not in favorites:
            continue
        if exclude_favs and image_id in favorites:
            continue
        ok = True
        for c in and_conditions:
            if "*" in c:
                rx = re.compile(".*".join(map(re.escape, c.split("*"))) + r"\Z")
                ok = any(rx.match(t) for t in tags)
            else:
                ok = c in tags
            if not ok:
                break
        if not ok:
            continue
        if or_conditions and not any(
            (t == "user:favorites" and image_id in favorites) or t in tags
            for group in or_conditions for t in group
        ):
            continue
        if any(t in tags for t in exclude):
            continue
        out.append(image_id)
    return out


@pytest.fixture
def random_library(db):
    rng = random.Random(42)
    vocab = [f"t{i}" for i in range(30)] + ["blue_sky", "outdoor", "doorway", "char_(x)", "a.b"]
    conn = db.get_db_connection()
    conn.executemany(
        "INSERT INTO tags (image_path, tags) VALUES (?, ?)",
        [(f"static/images/r/{i}.jpg", ", ".join(rng.sample(vocab, rng.randint(1, 6)))) for i in range(300)],
    )
    conn.executemany(
        "INSERT INTO favorites (image_id) VALUES (?)",
        [(i,) for i in rng.sample(range(1, 301), 25)],
    )
    conn.commit()
    return db


QUERIES = [
    "t1", "t1;t2", "t1|t2", "t1;-t2", "t1;t2|t3;-t4", "t1|t2;t3|t4",
    "t1*", "t*;-t5", "*door", "char_(x)", "char_(*", "a.b*", "*",
    "user:favorites", "user:favorites;t3", "t3;-user:favorites",
    "user:favorites|t7", "-t1", "nothing", "",
]


@pytest.mark.parametrize("query", QUERIES)
def test_index_matches_full_scan(random_library, query):
    assert random_library.search_images_with_conditions(query, onlyids=True) == \
        reference_search(random_library, query)


def test_index_stays_correct_after_edits_and_deletes(random_library):
    db = random_library
    db.search_images_with_conditions("t1")  # build the index
    db.upsert_tags("static/images/r/0.jpg", ["t1", "brand_new"])
    db.upsert_tags("static/images/r/1.jpg", ["t9"])
    db.upsert_tags("static/images/new.jpg", ["t1", "t2"])
    db.delete_image("static/images/r/2.jpg")
    for query in QUERIES + ["brand_new"]:
        assert db.search_images_with_conditions(query, onlyids=True) == reference_search(db, query), query
    # A rebuilt index agrees with the incrementally updated one
    before = {q: db.search_images_with_conditions(q, onlyids=True) for q in QUERIES}
    db.build_tag_index()
    db.invalidate_stored_queries()
    assert before == {q: db.search_images_with_conditions(q, onlyids=True) for q in QUERIES}


def test_wildcard_must_match_whole_tag(library):
    library.upsert_tags("static/images/demo/6.jpg", ["doorway"])
    paths = [r["image_path"] for r in library.search_images_with_conditions("*door")]
    assert "static/images/demo/6.jpg" not in paths
    assert "static/images/demo/4.jpg" in paths  # outdoor


def test_wildcard_treats_special_characters_literally(library):
    library.upsert_tags("static/images/demo/6.jpg", ["smile_(cat)"])
    library.upsert_tags("static/images/demo/7.jpg", ["axb"])
    (six,) = ids_for(library, "static/images/demo/6.jpg")
    assert library.search_images_with_conditions("smile_(*", onlyids=True) == [six]
    assert library.search_images_with_conditions("smile_(cat)*", onlyids=True) == [six]
    assert library.search_images_with_conditions("a.b*", onlyids=True) == []
