"""Load and validate the airport, access rules and flight schedule from config/flights.yml."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DIRECTIONS = ("departure", "arrival")


@dataclass(frozen=True)
class Airport:
    iata: str
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Rules:
    walk_only_max_minutes: int
    home_access_max_minutes: int
    airport_access_max_minutes: int
    transfer_walk_max_minutes: int
    min_transfer_minutes: int
    arrive_before_departure_minutes: int
    leave_after_landing_minutes: int
    band_step_minutes: int
    max_band_minutes: int


@dataclass(frozen=True)
class Flight:
    id: str
    direction: str
    time: str  # "HH:MM" local time

    @property
    def seconds_of_day(self) -> int:
        hours, minutes = self.time.split(":")
        return int(hours) * 3600 + int(minutes) * 60


@dataclass(frozen=True)
class AirportConfig:
    airport: Airport
    rules: Rules
    flights: list[Flight]
    default_flight_id: str


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"flights.yml: rules.{name} must be a positive integer, got {value!r}")
    return value


def _parse_flight(raw: object, index: int) -> Flight:
    if not isinstance(raw, dict):
        raise ValueError(f"flights.yml: flights[{index}] must be a mapping")
    flight_id = str(raw.get("id") or "").strip()
    if not flight_id:
        raise ValueError(f"flights.yml: flights[{index}] is missing 'id'")
    direction = raw.get("direction")
    if direction not in DIRECTIONS:
        raise ValueError(
            f"flights.yml: flight {flight_id} direction must be one of {DIRECTIONS}, got {direction!r}"
        )
    time = raw.get("time")
    if not isinstance(time, str) or not _TIME_RE.match(time):
        raise ValueError(
            f"flights.yml: flight {flight_id} time must be a quoted 'HH:MM' string, got {time!r}"
        )
    return Flight(id=flight_id, direction=direction, time=time)


def load_airport_config(path: Path = config.FLIGHTS_CONFIG) -> AirportConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    airport_raw = raw.get("airport") or {}
    try:
        airport = Airport(
            iata=str(airport_raw["iata"]),
            name=str(airport_raw["name"]),
            lat=float(airport_raw["lat"]),
            lon=float(airport_raw["lon"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("flights.yml: 'airport' needs iata, name, lat and lon") from exc
    if not (-90 <= airport.lat <= 90 and -180 <= airport.lon <= 180):
        raise ValueError(f"flights.yml: airport coordinates out of range: {airport.lat}, {airport.lon}")

    rules_raw = raw.get("rules") or {}
    rules = Rules(**{name: _positive_int(rules_raw.get(name), name) for name in Rules.__dataclass_fields__})

    flights = [_parse_flight(f, i) for i, f in enumerate(raw.get("flights") or [])]
    if not flights:
        raise ValueError("flights.yml: 'flights' must list at least one flight")
    ids = [f.id for f in flights]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"flights.yml: duplicate flight ids: {duplicates}")

    default_flight_id = str(raw.get("default_flight") or ids[0])
    if default_flight_id not in ids:
        raise ValueError(f"flights.yml: default_flight {default_flight_id!r} is not in flights")

    return AirportConfig(airport=airport, rules=rules, flights=flights, default_flight_id=default_flight_id)
