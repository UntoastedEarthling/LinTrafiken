# LinTrafiken

Insight into Linköping's public transit system, built on Östgötatrafiken's GTFS
and GTFS-RT data. MVP focuses on two static-GTFS map layers: a transit
frequency heatmap and street-network walking catchments around city bus stops.

See [docs/roadmap.md](docs/roadmap.md) for the full phased plan and the
decisions behind the architecture.

## Repo structure

- `frontend/` — React + TypeScript + MapLibre GL JS map app (scaffolded in Phase 4).
- `pipeline/` — Python batch jobs: GTFS ingestion, heatmap/catchment generation, PMTiles export.
- `infra/` — local dev Docker Compose, deployment configs, CI workflows.
- `docs/` — architecture and roadmap notes.

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+
- A [Trafiklab](https://www.trafiklab.se/) API key (GTFS Regional, Bronze tier is enough)

## Local dev quick start (Phase 0)

1. Copy `.env.example` to `.env` and fill in `TRAFIKLAB_API_KEY`.
2. Start local PostGIS: `docker compose -f infra/docker-compose.dev.yml up -d postgis`.

Pipeline and frontend setup instructions will be added as those phases land.
