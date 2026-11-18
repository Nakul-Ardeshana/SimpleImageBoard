"""Flask routes: autocomplete, search pages, result navigation (Images_searcher.py)."""
import re

from conftest import ids_for


def suggestions(client, q):
    return client.get("/autocomplete", query_string={"q": q}).get_json()


def test_autocomplete_prefix(client):
    tags = {s["tag"]: s["count"] for s in suggestions(client, "b")}
    assert tags == {"beach": 2, "blue_sky": 2}


def test_autocomplete_includes_type(client):
    (cat,) = suggestions(client, "cat")
    assert cat == {"tag": "cat", "count": 2, "type": 4}


def test_autocomplete_exclude(client):
    assert [s["tag"] for s in suggestions(client, "-sun")] == ["-sunset"]


def test_autocomplete_uses_last_or_term(client):
    assert [s["tag"] for s in suggestions(client, "beach|ind")] == ["indoor"]


def test_autocomplete_wildcard(client):
    assert {s["tag"] for s in suggestions(client, "*door")} == {"indoor", "outdoor"}


def test_autocomplete_favorites_first(client):
    assert suggestions(client, "u")[0]["tag"] == "user:favorites"


def test_autocomplete_empty_and_limit(client, library):
    assert suggestions(client, "") == []
    for i in range(15):
        library.upsert_tags(f"static/images/demo/x{i}.jpg", [f"zz_{i}"])
    assert len(suggestions(client, "zz")) == 10


def image_ids_on_page(html):
    return [int(i) for i in re.findall(r"/result/(\d+)", html)]


def test_search_page(client, app):
    resp = client.get("/search/beach")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "/static/images/demo/1.jpg" in html
    assert "/static/images/demo/2.jpg" in html
    assert "/static/images/demo/3.png" not in html


def test_search_page_pagination(client, app, library):
    for i in range(35):
        path = f"static/images/demo/p{i:02d}.jpg"
        open(path, "wb").close()
        library.upsert_tags(path, ["paged"])
    page1 = client.get("/search/paged/1").get_data(as_text=True)
    page2 = client.get("/search/paged/2").get_data(as_text=True)
    assert page1.count("static/images/demo/p") >= 30
    assert "p00.jpg" in page1 and "p29.jpg" in page1 and "p30.jpg" not in page1
    assert "p30.jpg" in page2 and "p34.jpg" in page2 and "p00.jpg" not in page2


def test_repeated_search_page_is_identical(client):
    first = client.get("/search/blue_sky").get_data(as_text=True)
    second = client.get("/search/blue_sky").get_data(as_text=True)
    assert first == second


def test_search_page_drops_missing_files(client, library, workdir):
    (workdir / "static/images/demo/2.jpg").unlink()
    client.get("/search/beach")
    assert library.search_images_with_conditions("beach", onlyids=True) == ids_for(
        library, "static/images/demo/1.jpg"
    )


def test_result_navigation_uses_search_order(client, library):
    client.get("/search/beach")
    first, second = ids_for(library, "static/images/demo/1.jpg", "static/images/demo/2.jpg")
    html = client.get(f"/result/{first}?context=search&query=beach").get_data(as_text=True)
    assert f"/result/{second}?context=search&amp;query=beach" in html or \
        f"/result/{second}?context=search&query=beach" in html


def test_result_not_found(client):
    assert client.get("/result/9999").status_code == 404
    assert client.get("/result/abc").status_code == 400
