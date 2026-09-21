"""Load the static GTFS feed into pandas dataframes via gtfs-kit."""
from __future__ import annotations

from pathlib import Path

import gtfs_kit as gk


def load_feed(gtfs_zip_path: Path) -> gk.Feed:
    return gk.read_feed(gtfs_zip_path, dist_units="km")
