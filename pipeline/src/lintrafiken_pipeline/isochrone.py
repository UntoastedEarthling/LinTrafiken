"""Compute 5/10/15-min walking catchments around classified city-transit stops via Valhalla.

Valhalla's /isochrone contours are cumulative (the 15-min polygon already contains the
10-min and 5-min areas), so unioning same-time-band polygons across all stops and drawing
them 15 -> 10 -> 5 (largest first) gives the concentric-catchment look from the roadmap
without needing any exclusive-ring differencing.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape
from shapely.ops import unary_union
from sqlalchemy import text
from sqlalchemy.engine import Engine

from . import config

logger = logging.getLogger(__name__)

CONTOUR_MINUTES = [5, 10, 15]
MAX_WORKERS = 8
REQUEST_TIMEOUT_SECONDS = 30


def _fetch_stops(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        stops = pd.DataFrame(
            conn.execute(text("SELECT stop_id, stop_lon, stop_lat FROM stops")).fetchall(),
            columns=["stop_id", "stop_lon", "stop_lat"],
        )
    return stops


def _query_isochrone(stop_lon: float, stop_lat: float) -> dict[int, list]:
    """Return {minutes: [shapely geometry, ...]} for one stop, or {} if unreachable."""
    body = {
        "locations": [{"lat": stop_lat, "lon": stop_lon}],
        "costing": "pedestrian",
        "contours": [{"time": m} for m in CONTOUR_MINUTES],
        "polygons": True,
        "denoise": 0.1,
        "generalize": 20,
    }
    resp = requests.post(
        f"{config.VALHALLA_URL}/isochrone", json=body, timeout=REQUEST_TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    features = resp.json()["features"]

    by_minutes: dict[int, list] = {}
    for feature in features:
        minutes = int(feature["properties"]["contour"])
        geom = shape(feature["geometry"])
        if not geom.is_empty:
            by_minutes.setdefault(minutes, []).append(geom)
    return by_minutes


def compute_catchments(engine: Engine) -> gpd.GeoDataFrame:
    """Return a 3-row GeoDataFrame (`minutes`, `geometry`) with unioned 5/10/15-min catchments."""
    stops = _fetch_stops(engine)
    logger.info("Querying Valhalla isochrones for %d stops", len(stops))

    geoms_by_minutes: dict[int, list] = {m: [] for m in CONTOUR_MINUTES}
    n_failed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_query_isochrone, row.stop_lon, row.stop_lat): row.stop_id
            for row in stops.itertuples()
        }
        for future in as_completed(futures):
            stop_id = futures[future]
            try:
                by_minutes = future.result()
            except requests.RequestException:
                logger.warning("Isochrone request failed for stop %s", stop_id, exc_info=True)
                n_failed += 1
                continue
            for minutes, geoms in by_minutes.items():
                geoms_by_minutes[minutes].extend(geoms)

    if n_failed:
        logger.warning("%d/%d stops failed isochrone lookup", n_failed, len(stops))

    rows = []
    for minutes in CONTOUR_MINUTES:
        geoms = geoms_by_minutes[minutes]
        if not geoms:
            raise ValueError(f"No isochrone geometry collected for {minutes}-min contour")
        rows.append({"minutes": minutes, "geometry": unary_union(geoms)})

    return gpd.GeoDataFrame(rows, crs="EPSG:4326")
