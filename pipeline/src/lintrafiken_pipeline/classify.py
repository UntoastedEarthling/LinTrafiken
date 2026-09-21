"""Classify GTFS routes as city-transit vs regional via a curated allowlist."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from . import config


@dataclass
class CityRoutesAllowlist:
    route_ids: set[str]
    route_short_names: set[str]

    @property
    def is_empty(self) -> bool:
        return not self.route_ids and not self.route_short_names


def load_allowlist(path: Path = config.CITY_ROUTES_CONFIG) -> CityRoutesAllowlist:
    if not path.exists():
        return CityRoutesAllowlist(route_ids=set(), route_short_names=set())

    raw = yaml.safe_load(path.read_text()) or {}
    return CityRoutesAllowlist(
        route_ids=set(map(str, raw.get("route_ids") or [])),
        route_short_names=set(map(str, raw.get("route_short_names") or [])),
    )


def classify_city_routes(routes: pd.DataFrame, allowlist: CityRoutesAllowlist) -> pd.DataFrame:
    """Return the subset of `routes` matching the curated city-transit allowlist."""
    if allowlist.is_empty:
        raise ValueError(
            "City routes allowlist is empty. Populate pipeline/config/city_routes.yml "
            "(see pipeline/config/city_routes.example.yml) - run with --list-routes first "
            "to see the available routes."
        )

    mask = routes["route_id"].astype(str).isin(allowlist.route_ids)
    if "route_short_name" in routes.columns:
        mask |= routes["route_short_name"].astype(str).isin(allowlist.route_short_names)
    return routes[mask].copy()
