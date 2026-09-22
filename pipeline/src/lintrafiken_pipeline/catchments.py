"""Phase 3 entrypoint: compute the 5/10/15-min walking catchments and export as PMTiles.

Requires the Valhalla service running locally (`docker compose --profile valhalla up -d valhalla`)
with tiles already built from the clipped Linköping OSM extract.
"""
from __future__ import annotations

import logging

from . import config, db
from .export import export_geojson
from .isochrone import compute_catchments
from .tile import tile_to_pmtiles

logger = logging.getLogger(__name__)

OUTPUT_PATH = config.DATA_DIR / "processed" / "catchments.geojson"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    engine = db.get_engine()
    gdf = compute_catchments(engine)
    export_geojson(gdf, OUTPUT_PATH)
    logger.info("Exported %d catchment bands to %s", len(gdf), OUTPUT_PATH)

    tile_to_pmtiles(OUTPUT_PATH, layer_name="catchments")


if __name__ == "__main__":
    main()
