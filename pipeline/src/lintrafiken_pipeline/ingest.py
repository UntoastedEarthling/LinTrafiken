"""Phase 1 entrypoint: download, parse, classify, and load GTFS into PostGIS."""
from __future__ import annotations

import argparse
import logging

from . import classify, db, download, gtfs_data

logger = logging.getLogger(__name__)


def list_routes(feed) -> None:
    columns = [
        c for c in ("route_id", "route_short_name", "route_long_name", "route_type")
        if c in feed.routes.columns
    ]
    routes = feed.routes[columns].sort_values(by=columns[0])
    print(routes.to_string(index=False))
    print(
        f"\n{len(routes)} routes total. Populate pipeline/config/city_routes.yml with the "
        "city-transit subset (see pipeline/config/city_routes.example.yml)."
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="LinTrafiken GTFS ingestion pipeline (Phase 1)")
    parser.add_argument(
        "--list-routes", action="store_true",
        help="Print all routes and exit, without loading anything into Postgres.",
    )
    parser.add_argument(
        "--force-download", action="store_true",
        help="Re-download the GTFS feed even if a cached copy exists.",
    )
    args = parser.parse_args()

    zip_path = download.download_gtfs(force=args.force_download)
    feed = gtfs_data.load_feed(zip_path)

    if args.list_routes:
        list_routes(feed)
        return

    allowlist = classify.load_allowlist()
    city_routes = classify.classify_city_routes(feed.routes, allowlist)
    route_ids = set(city_routes["route_id"].astype(str))

    engine = db.get_engine()
    db.load_tables(engine, feed, route_ids)
    logger.info("Ingestion complete: %d city-transit routes loaded", len(route_ids))


if __name__ == "__main__":
    main()
