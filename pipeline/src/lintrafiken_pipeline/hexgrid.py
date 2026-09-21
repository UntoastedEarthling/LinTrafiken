"""Generate an H3 hex grid (resolution 9, ~175m edge) covering a buffered stops bounding box."""
from __future__ import annotations

import h3
import numpy as np
import pandas as pd
from pyproj import Transformer

H3_RESOLUTION = 9
METRIC_CRS = "EPSG:3006"  # SWEREF99 TM, meters
GEOGRAPHIC_CRS = "EPSG:4326"

_to_metric = Transformer.from_crs(GEOGRAPHIC_CRS, METRIC_CRS, always_xy=True)
_to_geographic = Transformer.from_crs(METRIC_CRS, GEOGRAPHIC_CRS, always_xy=True)


def build_hex_grid(stop_lons: np.ndarray, stop_lats: np.ndarray, buffer_meters: float) -> pd.DataFrame:
    """Return H3 cells (hex_id, lon, lat centroid) covering the stops' extent, padded by `buffer_meters`."""
    x, y = _to_metric.transform(stop_lons, stop_lats)
    min_x, max_x = x.min() - buffer_meters, x.max() + buffer_meters
    min_y, max_y = y.min() - buffer_meters, y.max() + buffer_meters

    corners_x = [min_x, max_x, max_x, min_x]
    corners_y = [min_y, min_y, max_y, max_y]
    lon, lat = _to_geographic.transform(corners_x, corners_y)

    boundary = h3.LatLngPoly(list(zip(lat, lon)))
    hex_ids = list(h3.polygon_to_cells(boundary, H3_RESOLUTION))

    centroids = [h3.cell_to_latlng(cell) for cell in hex_ids]
    return pd.DataFrame(
        {
            "hex_id": hex_ids,
            "lat": [c[0] for c in centroids],
            "lon": [c[1] for c in centroids],
        }
    )
