"""Download the files of a Figshare article or collection."""

import json
import os
from urllib.request import urlretrieve

from tqdm import tqdm

from .importing import get_package

BASE_URL = "https://api.figshare.com/v2"


def tqdm_hook(t):
    """Wraps tqdm instance.
    Don't forget to close() or __exit__()
    the tqdm instance once you're done with it (easiest using `with` syntax).
    Example
    -------
    >>> with tqdm(...) as t:
    ...     reporthook = tqdm_hook(t)
    ...     urllib.urlretrieve(..., reporthook=reporthook)
    """
    last_b = [0]

    def update_to(b=1, bsize=1, tsize=None):
        """
        b  : int, optional
            Number of blocks transferred so far [default: 1].
        bsize  : int, optional
            Size of each block (in tqdm units) [default: 1].
        tsize  : int, optional
            Total size (in tqdm units). If [default: None] remains unchanged.
        """
        if tsize is not None:
            t.total = tsize
        t.update((b - last_b[0]) * bsize)
        last_b[0] = b

    return update_to


def _get_json(url: str) -> dict | list:
    """Fetch a Figshare API endpoint and decode its JSON body."""
    # Imported here rather than at the top: ``requests`` is not a dependency of neuroconv, so a
    # user reaches for it only when they call one of these helpers.
    requests = get_package(package_name="requests", installation_instructions="pip install requests")
    response = requests.get(url)
    response.raise_for_status()
    return json.loads(response.content)


def download_article(article_record: dict, destination: str) -> None:
    """
    Download all files in an article. Files that already exist in the destination will be skipped if they have the
    same size as the source. Also writes a ``metadata.json`` file holding the article description in the shape
    ``metadata["NWBFile"]["experiment_description"]`` expects.

    Parameters
    ----------
    article_record: dict
        A Figshare article record, as returned by the collection listing; ``"id"`` and ``"title"`` are used.
    destination: str
        Folder to download the files into. Created, along with any missing parents, if it does not exist.

    """
    os.makedirs(destination, exist_ok=True)

    # get all metadata for that article
    article_metadata = _get_json(BASE_URL + f'/articles/{article_record["id"]}')

    # write metadata file
    metadata_filepath = os.path.join(destination, "metadata.json")
    if not os.path.exists(metadata_filepath):
        with open(metadata_filepath, "w", encoding="utf-8") as metadata_file:
            json.dump(
                dict(NWBFile=dict(experiment_description=article_metadata["description"])),
                metadata_file,
            )

    # download data files
    file_records = article_metadata["files"]
    for file_record in tqdm(file_records, desc=f"files in article {article_record['title']}", leave=False):
        filepath = os.path.join(destination, file_record["name"])
        if os.path.exists(filepath) and os.path.getsize(filepath) == file_record["size"]:
            continue
        with tqdm(desc=file_record["name"], miniters=1, leave=False) as t:
            urlretrieve(file_record["download_url"], filepath, reporthook=tqdm_hook(t))


def download_collection(collection_id: int, destination: str) -> None:
    """Download all articles in a collection, each into a sub-folder named after the article's title.

    Parameters
    ----------
    collection_id: int
    destination: str
        Folder to download the articles into. Created, along with any missing parents, if it does not exist.

    Example
    -------
    >>> download_collection(5043830, "/Users/bendichter/Downloads/Schiavo2020")
    """

    os.makedirs(destination, exist_ok=True)

    # get all articles for collection
    article_records = _get_json(BASE_URL + f"/collections/{collection_id}/articles?page=1&page_size=1000")

    # iterate over articles
    for article_record in tqdm(article_records, desc="articles in collection", leave=False):
        download_article(
            article_record=article_record,
            destination=os.path.join(destination, article_record["title"]),
        )
