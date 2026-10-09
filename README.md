# LinTrafiken

LinTrafiken is a hobby project of mine to better understand Linköping's local transit system.
It is completely vibe-coded, so don't expect great code quality.

Right now it consists of an interactive map with three views: a departure-frequency heatmap,
a walking-catchment view around city bus stops, and an airport view showing how long it takes
to get to or from Linköping City Airport (LPI) by bus and on foot for each flight. It is built
from Östgötatrafiken's static GTFS feed (via Trafiklab) and OpenStreetMap.

Precompute-first architecture — a Python batch pipeline turns GTFS + OSM data
into static [PMTiles](https://protomaps.com/docs/pmtiles) archives, which a
MapLibre GL JS frontend renders directly over HTTP. No tile server, no live
backend.

## Repo structure

- [`frontend/`](frontend) — React + TypeScript + MapLibre GL JS map app. See
  its own [README](frontend/README.md) for frontend-specific setup.
- [`pipeline/`](pipeline) — Python batch jobs: GTFS ingestion, transit-frequency
  heatmap generation, walking-catchment computation (via Valhalla), airport travel-time
  bands (bus scan + Valhalla walking), PMTiles export.
- [`infra/`](infra) — local dev Docker Compose (PostGIS, Valhalla) and deployment configs.
- [`.github/workflows/`](.github/workflows) — scheduled data refresh and frontend deploy (AWS S3 + CloudFront).

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
python -m lintrafiken_pipeline.airport      # -> data/processed/airport.pmtiles + airport-meta.json (needs Valhalla)
```

Walking catchments and the airport view additionally need a local Valhalla routing instance built
from a Linköping OSM extract. Clip one from a
[Geofabrik](https://download.geofabrik.de/) Sweden download, drop the
resulting `.osm.pbf` into `infra/valhalla/`, then:

```sh
docker compose -f infra/docker-compose.dev.yml --profile valhalla up -d valhalla
```

### Airport view configuration

The airport location, walking and transfer limits, and the flight schedule live in
[`pipeline/config/flights.yml`](pipeline/config/flights.yml). To change the schedule, edit that
file (times must be quoted, e.g. `"06:05"`), rerun `python -m lintrafiken_pipeline.airport`, then
`npm run sync-tiles` in `frontend/`. The frontend's flight dropdown and the assumptions shown in
the panel are generated from the resulting `airport-meta.json`, so nothing is hard-coded there.

Only the city bus routes listed in
[`pipeline/config/city_routes.yml`](pipeline/config/city_routes.yml) are used for routing.

### 3. Frontend

```sh
cd frontend
npm install
npm run sync-tiles   # copies pipeline output (PMTiles + airport-meta.json) into public/tiles/
npm run dev
```

See [frontend/README.md](frontend/README.md) for frontend-specific details.

## Deployment

Two GitHub Actions workflows deploy to AWS S3 + CloudFront:

- [`deploy-frontend.yml`](.github/workflows/deploy-frontend.yml) builds and uploads the app on
  every push to `main` that touches `frontend/`.
- [`data-refresh.yml`](.github/workflows/data-refresh.yml) runs weekly (and on demand): it runs the
  whole pipeline and uploads the PMTiles and `airport-meta.json` to `tiles/` in the bucket.

They need the secrets `AWS_ROLE_ARN` and `TRAFIKLAB_API_KEY` and the variables `AWS_REGION`,
`S3_BUCKET_NAME` and `CLOUDFRONT_DISTRIBUTION_ID`. The data refresh must have run once before the
map layers (including the Airport tab) show data in production.

