"""Environment and path configuration for the pipeline, loaded from the repo-root .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")

DATA_DIR = REPO_ROOT / "pipeline" / "data"
RAW_DIR = DATA_DIR / "raw"
CONFIG_DIR = REPO_ROOT / "pipeline" / "config"
CITY_ROUTES_CONFIG = CONFIG_DIR / "city_routes.yml"

GTFS_OPERATOR = "otraf"  # Östgötatrafiken, per Trafiklab GTFS Regional
GTFS_URL = f"https://opendata.samtrafiken.se/gtfs/{GTFS_OPERATOR}/{GTFS_OPERATOR}.zip"
TRAFIKLAB_API_KEY = os.environ.get("TRAFIKLAB_API_KEY", "")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "lintrafiken")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "lintrafiken")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "lintrafiken")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")


def database_url() -> str:
    return (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
