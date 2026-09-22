# LinTrafiken

LinTrafiken is a hobby project of mine to better understand Linköping's local transit system.
It is completely vibe-coded, so don't expect great code quality.

Right now it consists of an interactive map with two views: a departure-frequency heatmap and
a walking-catchment view around city bus stops, built from Östgötatrafiken's
static GTFS feed (via Trafiklab) and OpenStreetMap.

Precompute-first architecture — a Python batch pipeline turns GTFS + OSM data
into static [PMTiles](https://protomaps.com/docs/pmtiles) archives, which a
MapLibre GL JS frontend renders directly over HTTP. No tile server, no live
backend.

## Repo structure

- [`frontend/`](frontend) — React + TypeScript + MapLibre GL JS map app. See
  its own [README](frontend/README.md) for frontend-specific setup.
- [`pipeline/`](pipeline) — Python batch jobs: GTFS ingestion, transit-frequency
  heatmap generation, walking-catchment computation (via Valhalla), PMTiles export.
- [`infra/`](infra) — local dev Docker Compose (PostGIS, Valhalla) and deployment configs.

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+
- A [Trafiklab](https://www.trafiklab.se/) API key (GTFS Regional, Bronze tier is enough)

## Local dev quick start

### 1. Environment

Copy `.env.example` to `.env` and fill in `TRAFIKLAB_API_KEY`.

### 2. Data pipeline

Start local PostGIS:

```sh
docker compose -f infra/docker-compose.dev.yml up -d postgis
```

Install and run the pipeline (from `pipeline/`):

```sh
pip install -r requirements.txt -e .
python -m lintrafiken_pipeline.ingest       # GTFS -> PostGIS
python -m lintrafiken_pipeline.heatmap      # -> data/processed/heatmap.pmtiles
python -m lintrafiken_pipeline.catchments   # -> data/processed/catchments.pmtiles (needs Valhalla, see below)
```

Walking catchments additionally need a local Valhalla routing instance built
from a Linköping OSM extract. Clip one from a
[Geofabrik](https://download.geofabrik.de/) Sweden download, drop the
resulting `.osm.pbf` into `infra/valhalla/`, then:

```sh
docker compose -f infra/docker-compose.dev.yml --profile valhalla up -d valhalla
```

### 3. Frontend

```sh
cd frontend
npm install
npm run sync-tiles   # copies pipeline output PMTiles into public/tiles/
npm run dev
```

See [frontend/README.md](frontend/README.md) for frontend-specific details.

