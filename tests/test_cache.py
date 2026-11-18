"""Query cache and batched metadata lookups (db_utils.py)."""
from conftest import ids_for


def test_search_is_cached(library):
    ids = library.search_images_with_conditions("beach", onlyids=True)
    assert library.cached_queries["beach"] == ids


def test_empty_results_are_cached(library):
    assert library.search_images_with_conditions("nonexistent", onlyids=True) == []
    assert library.cached_queries["nonexistent"] == []


def test_favorite_changes_invalidate_cache(library):
    assert len(library.search_images_with_conditions("user:favorites")) == 1
    (image_id,) = ids_for(library, "static/images/demo/1.jpg")
    library.add_to_favorites(image_id)
    assert len(library.search_images_with_conditions("user:favorites")) == 2
    library.remove_from_favorites(image_id)
    assert len(library.search_images_with_conditions("user:favorites")) == 1


def test_cache_size_is_capped(library, monkeypatch):
    monkeypatch.setattr(library, "MAX_CACHED_QUERIES", 3)
    for q in ["beach", "cat", "dog", "outdoor"]:
        library.search_images_with_conditions(q)
    assert list(library.cached_queries) == ["cat", "dog", "outdoor"]


def test_cached_search_skips_the_scan(library):
    first = library.search_images_with_conditions("beach")
    # Change the DB behind the cache's back: a cached query must not rescan.
    library.get_db_connection().execute(
        "UPDATE tags SET tags = 'beach' WHERE image_path = 'static/images/demo/3.png'"
    )
    assert library.search_images_with_conditions("beach") == first


def test_cached_search_returns_same_results_as_uncached(library):
    uncached = library.search_images_with_conditions("blue_sky|dog")
    cached = library.search_images_with_conditions("blue_sky|dog")
    assert cached == uncached


def test_edit_invalidates_cache(library):
    library.search_images_with_conditions("beach")
    library.upsert_tags("static/images/demo/3.png", ["cat", "beach"])
    assert library.cached_queries == {}
    assert len(library.search_images_with_conditions("beach")) == 3


def test_delete_invalidates_cache(library):
    library.search_images_with_conditions("beach")
    (image_id,) = ids_for(library, "static/images/demo/2.jpg")
    assert library.delete_image_by_id(image_id)
    assert library.cached_queries == {}
    assert len(library.search_images_with_conditions("beach")) == 1


def test_batched_metadata_keeps_order_and_skips_missing(library):
    ids = ids_for(library, "static/images/demo/4.jpg", "static/images/demo/1.jpg")
    results = library.fetch_metadata_by_ids([ids[0], 9999, ids[1]])
    assert [r["id"] for r in results] == [ids[0], ids[1]]
    assert results[0] == library.fetch_metadata_by_id(ids[0])


def test_batched_metadata_across_chunks(library):
    ids = library.search_images_with_conditions("*", onlyids=True)
    results = library.fetch_metadata_by_ids(ids, chunk_size=2)
    assert [r["id"] for r in results] == ids


def test_batched_metadata_empty(library):
    assert library.fetch_metadata_by_ids([]) == []
