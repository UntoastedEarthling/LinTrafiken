"""Export computed hex data to GeoJSON for downstream tiling (tippecanoe -> PMTiles)."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon


def to_geodataframe(hexes: pd.DataFrame) -> gpd.GeoDataFrame:
    """Attach hex boundary polygons to a hex frequency DataFrame (must have a `hex_id` column)."""

    def boundary_polygon(hex_id: str) -> Polygon:
        latlngs = h3.cell_to_boundary(hex_id)
        return Polygon([(lng, lat) for lat, lng in latlngs])

    geometry = hexes["hex_id"].map(boundary_polygon)
    return gpd.GeoDataFrame(hexes, geometry=geometry, crs="EPSG:4326")


def export_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, driver="GeoJSON")
