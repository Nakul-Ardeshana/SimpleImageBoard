"""Tag search: AND / OR / NOT / wildcard / user:favorites (db_utils.py)."""
from conftest import ids_for


def search_paths(db, query):
    return sorted(r["image_path"] for r in db.search_images_with_conditions(query))


def test_single_tag(library):
    assert search_paths(library, "beach") == [
        "static/images/demo/1.jpg",
        "static/images/demo/2.jpg",
    ]


def test_and(library):
    assert search_paths(library, "cat;blue_sky") == ["static/images/demo/4.jpg"]


def test_or(library):
    assert search_paths(library, "sunset|indoor") == [
        "static/images/demo/1.jpg",
        "static/images/demo/3.png",
    ]


def test_not(library):
    assert search_paths(library, "cat;-outdoor") == ["static/images/demo/3.png"]


def test_wildcard(library):
    assert search_paths(library, "blue*") == [
        "static/images/demo/1.jpg",
        "static/images/demo/4.jpg",
    ]


def test_no_match(library):
    assert library.search_images_with_conditions("nonexistent") == []


def test_favorites(library):
    assert search_paths(library, "user:favorites") == ["static/images/demo/4.jpg"]


def test_exclude_favorites(library):
    assert search_paths(library, "cat;-user:favorites") == ["static/images/demo/3.png"]


def test_favorites_in_or_group(library):
    assert search_paths(library, "user:favorites|dog") == [
        "static/images/demo/2.jpg",
        "static/images/demo/4.jpg",
        "static/images/demo/5.mp4",
    ]


def test_onlyids_returns_ids_in_db_order(library):
    expected = ids_for(library, "static/images/demo/2.jpg", "static/images/demo/5.mp4")
    assert library.search_images_with_conditions("dog", onlyids=True) == expected


def test_results_include_tags(library):
    (result,) = library.search_images_with_conditions("sunset")
    assert result["tags"] == ["beach", "blue_sky", "sunset"]


def test_tag_counts_track_edits(library):
    assert library.fetch_tag_count("beach") == 2
    library.upsert_tags("static/images/demo/2.jpg", ["dog"])
    assert library.fetch_tag_count("beach") == 1
    assert library.fetch_tag_count("user:favorites") == 1
