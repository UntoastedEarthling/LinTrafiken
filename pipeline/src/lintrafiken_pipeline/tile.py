"""Tile a GeoJSON file into PMTiles: tippecanoe (via Docker) -> pmtiles conversion.

Zoom range (9-14) is a reasonable default for a city-scale hex heatmap; revisit once the
frontend map view (Phase 4) is wired up. With only ~3k hex features, dropping/simplification
is disabled so every hex renders at every zoom level.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from pmtiles.convert import mbtiles_to_pmtiles

logger = logging.getLogger(__name__)

TIPPECANOE_IMAGE = "klokantech/tippecanoe:latest"
MIN_ZOOM = 9
MAX_ZOOM = 14


def tile_to_pmtiles(geojson_path: Path, layer_name: str) -> Path:
    """Tile `geojson_path` into a same-named .pmtiles file via tippecanoe (Docker) + pmtiles conversion."""
    mbtiles_path = geojson_path.with_suffix(".mbtiles")
    pmtiles_path = geojson_path.with_suffix(".pmtiles")

    subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", f"{geojson_path.parent.resolve()}:/data",
            TIPPECANOE_IMAGE,
            "tippecanoe",
            "-o", f"/data/{mbtiles_path.name}",
            f"-z{MAX_ZOOM}", f"-Z{MIN_ZOOM}",
            "--no-tile-size-limit", "--no-feature-limit",
            "--force",
            "-l", layer_name,
            f"/data/{geojson_path.name}",
        ],
        check=True,
    )

    mbtiles_to_pmtiles(str(mbtiles_path), str(pmtiles_path), maxzoom=MAX_ZOOM)
    logger.info("Wrote %s", pmtiles_path)
    return pmtiles_path
