"""The Figshare helpers, with the API and the file transfer stood in for so nothing touches the network."""

import json

import pytest

from neuroconv.tools import figshare

ARTICLES = {
    11: dict(
        description="First article.",
        files=[dict(name="a.dat", size=3, download_url="https://example.invalid/a.dat")],
    ),
    12: dict(
        description="Second article.",
        files=[
            dict(name="b.dat", size=5, download_url="https://example.invalid/b.dat"),
            dict(name="c.dat", size=1, download_url="https://example.invalid/c.dat"),
        ],
    ),
}
COLLECTION = [dict(id=11, title="Article One"), dict(id=12, title="Article Two")]
CONTENT = {
    "https://example.invalid/a.dat": b"aaa",
    "https://example.invalid/b.dat": b"bbbbb",
    "https://example.invalid/c.dat": b"c",
}


@pytest.fixture
def offline_figshare(monkeypatch):
    """Answer the two API endpoints from the tables above and record every file transfer asked for."""
    transfers = []

    def get_json(url):
        if url.endswith("/articles?page=1&page_size=1000"):
            return COLLECTION
        article_id = int(url.rsplit("/", 1)[-1])
        return ARTICLES[article_id]

    def urlretrieve(url, filepath, reporthook=None):
        transfers.append(url)
        with open(filepath, "wb") as file:
            file.write(CONTENT[url])
        if reporthook is not None:
            reporthook(1, len(CONTENT[url]), len(CONTENT[url]))

    monkeypatch.setattr(figshare, "_get_json", get_json)
    monkeypatch.setattr(figshare, "urlretrieve", urlretrieve)
    return transfers


def test_download_collection_writes_every_article(tmp_path, offline_figshare):
    destination = tmp_path / "missing_parent" / "collection"

    figshare.download_collection(collection_id=5043830, destination=str(destination))

    assert (destination / "Article One" / "a.dat").read_bytes() == b"aaa"
    assert (destination / "Article Two" / "b.dat").read_bytes() == b"bbbbb"
    assert (destination / "Article Two" / "c.dat").read_bytes() == b"c"
    metadata = json.loads((destination / "Article One" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata == dict(NWBFile=dict(experiment_description="First article."))
    assert len(offline_figshare) == 3


def test_download_article_skips_a_complete_file(tmp_path, offline_figshare):
    destination = tmp_path / "article"
    destination.mkdir()
    (destination / "b.dat").write_bytes(b"bbbbb")  # already there, and the right size

    figshare.download_article(article_record=dict(id=12, title="Article Two"), destination=str(destination))

    assert offline_figshare == ["https://example.invalid/c.dat"]
