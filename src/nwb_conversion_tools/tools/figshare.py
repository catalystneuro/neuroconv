import json
import os
from urllib.request import urlretrieve

import requests
from tqdm.notebook import tqdm

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


def download_article(article_record: dict, destination: str) -> None:
    """
    Download all files in an article. Files that already exist in the destination will be skipped if they  have the
    same size as the source. Also add a metadata.yaml json file.

    Parameters
    ----------
    article_record: dict
    destination: str

    """
    # if article directory does not exist, create it
    if not os.path.exists(destination):
        os.mkdir(destination)

    # get all metadata for that article
    article_metadata = json.loads(requests.get(BASE_URL + f'/articles/{article_record["id"]}').content)

    # write metadata file
    metadata_filepath = os.path.join(destination, "metadata.json")
    if not os.path.exists(metadata_filepath):
        with open(metadata_filepath, "w") as metadata_file:
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
    """Download all articles in a collection.

    Parameters
    ----------
    collection_id: int
    destination: str

    Example
    -------
    >>> download_collection(5043830, "/Users/bendichter/Downloads/Schiavo2020")
    """

    if not os.path.exists(destination):
        os.mkdir(destination)

    # get all articles for collection
    article_records = json.loads(
        requests.get(BASE_URL + f"/collections/{collection_id}/articles?page=1&page_size=1000").content
    )

    # iterate over articles
    for article_record in tqdm(article_records, desc="articles in collection", leave=False):
        download_article(
            article_record=article_record,
            destination=os.path.join(destination, article_record["title"]),
        )
