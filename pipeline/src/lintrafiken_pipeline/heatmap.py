"""Phase 2 entrypoint: compute the H3 transit-frequency heatmap and export it as GeoJSON."""
from __future__ import annotations

import logging

from . import config, db
from .export import export_geojson, to_geodataframe
from .frequency import compute_hex_frequencies
from .tile import tile_to_pmtiles

logger = logging.getLogger(__name__)

OUTPUT_PATH = config.DATA_DIR / "processed" / "heatmap.geojson"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    engine = db.get_engine()
    hexes = compute_hex_frequencies(engine)
    gdf = to_geodataframe(hexes)
    export_geojson(gdf, OUTPUT_PATH)
    logger.info("Exported %d hex cells to %s", len(gdf), OUTPUT_PATH)

    tile_to_pmtiles(OUTPUT_PATH, layer_name="heatmap")


if __name__ == "__main__":
    main()
