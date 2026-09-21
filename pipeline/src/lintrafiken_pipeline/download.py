"""Download and cache the Trafiklab static GTFS feed for Östgötatrafiken."""
from __future__ import annotations

import logging
from pathlib import Path

import requests

from . import config

logger = logging.getLogger(__name__)

ZIP_PATH = config.RAW_DIR / f"{config.GTFS_OPERATOR}.zip"
ETAG_PATH = config.RAW_DIR / f"{config.GTFS_OPERATOR}.etag"


def download_gtfs(force: bool = False) -> Path:
    """Download otraf.zip, reusing the cached copy if the feed hasn't changed (best-effort ETag check)."""
    if not config.TRAFIKLAB_API_KEY:
        raise RuntimeError(
            "TRAFIKLAB_API_KEY is not set. Copy .env.example to .env and fill in your key."
        )

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)

    headers = {}
    cached_etag = ETAG_PATH.read_text().strip() if ETAG_PATH.exists() else None
    if cached_etag and ZIP_PATH.exists() and not force:
        headers["If-None-Match"] = cached_etag

    response = requests.get(
        config.GTFS_URL,
        params={"key": config.TRAFIKLAB_API_KEY},
        headers=headers,
        timeout=60,
    )

    if response.status_code == 304:
        logger.info("GTFS feed unchanged, using cached copy at %s", ZIP_PATH)
        return ZIP_PATH

    response.raise_for_status()
    ZIP_PATH.write_bytes(response.content)

    etag = response.headers.get("ETag")
    if etag:
        ETAG_PATH.write_text(etag)

    logger.info("Downloaded fresh GTFS feed to %s", ZIP_PATH)
    return ZIP_PATH
