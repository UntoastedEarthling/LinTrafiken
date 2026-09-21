"""Load classified GTFS tables into transient local PostGIS for the batch run."""
from __future__ import annotations

import logging

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from . import config

logger = logging.getLogger(__name__)


def get_engine() -> Engine:
    return create_engine(config.database_url())


def ensure_postgis(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))


def load_tables(engine: Engine, feed, route_ids: set[str]) -> None:
    """Write GTFS tables filtered down to `route_ids`, replacing any existing tables."""
    ensure_postgis(engine)

    routes = feed.routes[feed.routes["route_id"].astype(str).isin(route_ids)].copy()
    trips = feed.trips[feed.trips["route_id"].astype(str).isin(route_ids)].copy()
    trip_ids = set(trips["trip_id"].astype(str))

    stop_times = feed.stop_times[feed.stop_times["trip_id"].astype(str).isin(trip_ids)].copy()
    stop_ids = set(stop_times["stop_id"].astype(str))

    stops = feed.stops[feed.stops["stop_id"].astype(str).isin(stop_ids)].copy()
    stops_gdf = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
        crs="EPSG:4326",
    )

    service_ids = set(trips["service_id"].astype(str))
    calendar = (
        feed.calendar[feed.calendar["service_id"].astype(str).isin(service_ids)].copy()
        if feed.calendar is not None
        else pd.DataFrame()
    )
    calendar_dates = (
        feed.calendar_dates[feed.calendar_dates["service_id"].astype(str).isin(service_ids)].copy()
        if feed.calendar_dates is not None
        else pd.DataFrame()
    )

    routes.to_sql("routes", engine, if_exists="replace", index=False)
    trips.to_sql("trips", engine, if_exists="replace", index=False)
    stop_times.to_sql("stop_times", engine, if_exists="replace", index=False)
    if not calendar.empty:
        calendar.to_sql("calendar", engine, if_exists="replace", index=False)
    if not calendar_dates.empty:
        calendar_dates.to_sql("calendar_dates", engine, if_exists="replace", index=False)
    stops_gdf.to_postgis("stops", engine, if_exists="replace", index=False)

    logger.info(
        "Loaded %d routes, %d trips, %d stop_times, %d stops into PostGIS",
        len(routes), len(trips), len(stop_times), len(stops_gdf),
    )
