# Plan: LinTrafiken MVP — Transit Frequency Heatmap + Walking Catchments

## TL;DR
Precompute-first architecture to fit a hard 100 SEK/month hosting budget. A Python
batch pipeline (run in GitHub Actions / locally, NOT persistently in production)
ingests Östgötatrafiken's static GTFS from Trafiklab, computes (1) an H3 hex-grid
transit-frequency heatmap and (2) Valhalla-derived 5/10/15-min walking catchments
around city-transit stops, and exports both as PMTiles (self-contained vector tile
archives, servable via plain HTTP range requests — no tile server process needed).
Frontend: React + TypeScript + MapLibre GL JS + deck.gl + Tailwind/shadcn for a
polished, chrome-light full-screen map. Production = AWS S3 (static frontend build
+ PMTiles files) + CloudFront (Free flat-rate plan: CDN, custom DNS, TLS cert,
WAF/DDoS included) — no persistent compute, near-$0/month at MVP traffic levels.
Postgres/PostGIS + FastAPI + Valhalla are fully designed and used in local/CI batch
jobs so Phase 2 (GTFS-RT realtime, KoDa historical data) is an additive upgrade
(deploy those services to an AWS Lightsail instance behind the same CloudFront
distribution) — not a rewrite.

## Decisions from discussion
- Backend/pipeline language: Python (FastAPI later for dynamic endpoints).
- Map rendering: MapLibre GL JS (open-source, no vendor lock-in) + deck.gl for
  heatmap layer, styled with a light, warm-coloured basemap (custom-recoloured
  from a light open style) + warm sequential data palettes — per user request
  for a light/warm design, not a stock gray basemap.
- City transit classification: explicit curated allowlist of route
  IDs/short_names in `routes.txt` (config file), not a heuristic — per user
  request, simpler and unambiguous; still needs the actual route list
  populated once real GTFS data is inspected.
- Walking isochrones: Valhalla (`/isochrone` endpoint), run ephemerally in
  CI/local only — never as a persistent prod service in MVP.
- Hosting: AWS S3 + CloudFront (Free flat-rate plan) for MVP static hosting —
  near-$0/month, chosen over GleSYS (~50 SEK/mo, Swedish) after cost comparison;
  user explicitly chose AWS despite it not being Swedish-hosted. Rejected
  Cleura/Elastx (too expensive) and AWS managed compute (RDS/Fargate/ALB — each
  adds $15-40+/mo, breaking the 100 SEK budget) for the MVP phase.
- Phase 2 compute (when realtime/live queries are added): deploy FastAPI +
  Postgres/PostGIS + Valhalla to a single AWS Lightsail instance (~$7-12/mo,
  bundled compute+storage+transfer, closest AWS equivalent to a plain VPS)
  behind the same CloudFront distribution — cheapest AWS path to persistent
  compute; avoid RDS/ECS+ALB (adds $35-60+/mo) unless traffic later justifies it.
- Overlay layers (homes, destinations, sidewalks, bike infra) = fast-follow,
  NOT in MVP scope.
- User already has a Trafiklab API key (Bronze tier is sufficient for MVP).
- Key cost trick: nothing geospatial runs persistently in prod for MVP — only
  the static frontend build + PMTiles files are served. This is what makes the
  100 SEK/month budget achievable while still designing for later growth.

## Steps / Phases

### Phase 0: Repo & environment setup
1. GitHub monorepo: `/frontend`, `/pipeline` (Python batch jobs), `/infra`
   (docker-compose, AWS deploy/IaC configs, GitHub Actions workflows), `/docs`.
2. `infra/docker-compose.dev.yml`: Postgres+PostGIS (+ Valhalla profile) for
   local dev of the pipeline only.
3. `.env` handling for Trafiklab API key; never committed.

### Phase 1: GTFS ingestion pipeline (Python) — depends on Phase 0
4. Download `otraf.zip` from Trafiklab GTFS Regional
   (`https://opendata.samtrafiken.se/gtfs/otraf/otraf.zip?key={apikey}`), cache
   locally, detect daily updates (data refreshes 03:00-07:00 daily per Trafiklab).
5. Parse GTFS (gtfs-kit / pandas) into stops, stop_times, trips, calendar,
   calendar_dates, routes dataframes.
6. Classify "city transit" (Linköping stadsbuss) vs regional stops/routes via
   an explicit, manually curated allowlist: a config file (e.g.
   `pipeline/config/city_routes.yml`) listing the `route_id`/`route_short_name`
   values from `routes.txt` that count as city transit; filter stops/trips to
   only those routes. Simpler and more accurate than a heuristic — just needs
   the actual list of Östgötatrafiken city bus route names/IDs populated once
   real `routes.txt` is inspected, and is trivial to update if routes change.
7. Load into transient local PostGIS (spun up for the batch run only) for
   spatial queries.

### Phase 2: Transit frequency heatmap — depends on Phase 1
8. Generate H3 hex grid (res ≈9, ~175m edge) covering Linköping city bbox.
9. For weekday-type (Mon–Fri / Sat / Sun), pick representative service date via
   calendar/calendar_dates; per hex centroid, count departures within 500m
   (PostGIS ST_DWithin on stops→stop_times→trips) per hour 0–23.
10. Store as GeoJSON/FlatGeobuf with per-cell properties
    `weekday_h0..h23`, `saturday_h0..h23`, `sunday_h0..h23`; convert to PMTiles
    (tippecanoe / `pmtiles convert`).
11. Frontend: deck.gl H3HexagonLayer / MapLibre fill layer; slider changes only
    swap the style expression's property key — no refetch needed.

### Phase 3: Walking catchments — depends on Phase 1, parallel with Phase 2
12. Clip Geofabrik Östergötland OSM extract to Linköping bbox (osmium) for
    Valhalla tile build (build in CI/local, never on the prod VPS).
13. Run Valhalla batch job: walk isochrones (5/10/15 min) per classified
    city-transit stop from step 6.
14. `ST_Union` same-time-band polygons across all stops into 3 combined
    catchment layers (5/10/15 min, drawn 15→10→5 for a concentric look).
15. Export as PMTiles alongside heatmap tiles.

### Phase 4: Frontend — parallel with Phases 2-3 once GTFS shapes are known
16. Scaffold Vite + React + TypeScript; Tailwind + shadcn/ui for layer panel,
    sliders, toggles.
17. MapLibre GL JS + a light, warm-toned basemap: start from a light open style
    (e.g. Protomaps/OpenFreeMap "Light" or CARTO Positron as a base) and
    override its color ramp — cream/warm-white background, warm beige/tan land,
    soft terracotta building fills, muted warm-gray roads — instead of the
    default cool-gray look, for a distinct, polished, non-homemade feel.
    Heatmap/catchment layers use a complementary warm sequential palette (e.g.
    amber → orange → deep red for frequency; warm ochre/terracotta bands for
    the 5/10/15-min catchments) so data layers pop against the light basemap.
    Use the `pmtiles` npm package to register a MapLibre protocol handler for
    the local heatmap/catchment tile layers via HTTP range requests.
18. Layer-control UI: toggle "Frequency Heatmap" vs "Walking Catchments", each
    with own slider(s) (hour + weekday for heatmap; 5/10/15 segmented control
    for catchments).
19. Full-screen layout, minimal chrome, subtle glassmorphism control panel.

### Phase 5: Build & deploy — depends on Phases 2-4
20. GitHub Actions (scheduled daily + manual dispatch): spins up ephemeral
    Postgres+Valhalla, runs ingestion+heatmap+catchment pipeline, produces
    PMTiles artifacts.
21. Second workflow: Vite build referencing PMTiles URLs; `aws s3 sync` build
    output + PMTiles to an S3 bucket (via OIDC-federated deploy role, no long-
    lived AWS keys in GitHub), then invalidate the CloudFront distribution's
    cache for changed paths.
22. Provision AWS: S3 bucket (private, CloudFront-only access via Origin Access
    Control), CloudFront distribution on the Free flat-rate plan (custom domain
    + ACM TLS cert + WAF/DDoS included), Route 53 hosted zone (or point an
    external registrar's DNS at CloudFront) for the domain.
23. Configure S3/CloudFront response headers for correct MIME types + HTTP
    Range support for PMTiles, and cache-control for the frontend build vs.
    the (daily-refreshed) PMTiles files.

## Relevant references
- Trafiklab GTFS Regional docs: static data daily-updated, CC0 license, Bronze
  key tier (10 req/min, 50/day static) is sufficient; historical data via KoDa
  API (RISE/Vinnova) for later Phase 2.
- AWS static hosting for MVP: S3 (storage ~$0.023/GB Stockholm region) +
  CloudFront Free flat-rate plan (1M requests/mo, 100GB transfer/mo, 5GB S3
  storage credits, custom DNS + ACM TLS + WAF/DDoS included, $0/month) +
  Route 53 hosted zone (~$0.50/mo + $0.40/million queries) — realistic MVP
  cost ~$0-3/month, well under the 100 SEK budget. First 100GB/month data
  transfer out is free account-wide (not just first 12 months).
- Phase 2 compute options costed: AWS Lightsail instance (~$7-12/mo, cheapest,
  runs the existing Docker Compose stack unchanged) vs. RDS PostgreSQL managed
  (+$15-20+/mo alone) vs. ECS Fargate + Application Load Balancer (+$20-40+/mo,
  ALB has a flat ~$16-20/mo cost regardless of traffic) — Lightsail recommended
  when Phase 2 compute is needed, to stay budget-conscious.
- GleSYS KVM VPS "Essential" tier (€4.42/mo, ~50 SEK) was the original Swedish-
  hosting candidate; superseded by the AWS S3+CloudFront choice above per user
  decision (cost took priority over Swedish-only hosting for MVP).

## Verification
1. Local: `docker compose -f infra/docker-compose.dev.yml up`; run pipeline
   scripts; validate PMTiles via `pmtiles show`/local MapLibre debug page.
2. Data QA: known high-frequency corridor (Central Station) shows high rush-hour
   counts vs low at night; a known city bus stop's 5/10/15 catchment roughly
   matches ~400/800/1200m walk distance at ~5km/h.
3. Frontend manual QA: toggle layers, move sliders, confirm DevTools Network
   tab shows no new tile fetch on slider move (only initial PMTiles load).
4. Deployment: hit public HTTPS URL, confirm map loads; confirm AWS bill
   (S3 + CloudFront + Route 53) stays at ~$0-3/month (well under 100 SEK).

## Further considerations
1. City-vs-regional classification method is settled (curated route allowlist,
   see Phase 1 step 6) — the only remaining task is populating the actual list
   of Östgötatrafiken city bus route IDs/names once real GTFS data is fetched.
2. If GitHub Actions free-tier minutes become insufficient for the ephemeral
   Postgres+Valhalla batch build, move precompute to a scheduled job instead
   (e.g. a Lightsail instance or a one-off EC2/Fargate task spun up per run).
3. Data-sovereignty tradeoff: AWS hosting (US-headquartered, though data can be
   pinned to Stockholm region eu-north-1) was explicitly chosen over Swedish
   providers (GleSYS/Cleura/Elastx) for cost reasons — worth revisiting if data
   residency/sovereignty becomes a hard requirement later (e.g. GDPR posture,
   public-sector procurement rules), since GTFS data itself is CC0/public so
   this is a soft preference, not a legal blocker for this project.
