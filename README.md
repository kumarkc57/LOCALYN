# LOCALYN — Hyperlocal Multi-Agency Urban Public Intelligence Platform
## Spatio-Temporal Entity Resolution & Civic Evidence Fusion for Bengaluru

LOCALYN is an urban public intelligence platform designed to ingest, normalize, fuse, and communicate real-world municipal and traffic events across the Bengaluru Metropolitan Region with explainable evidence confidence.

The platform performs cross-source data fusion resolving **326,156 municipal complaints** (BBMP 2023–2024 across 198 wards) against **Bengaluru Traffic Police (BTP)** telemetry and live environmental sensor feeds.

---

## 1. System Architecture

```text
┌──────────────────────────────────────┐     ┌──────────────────────────────────────┐
│  BBMP Municipal Grievance Records    │     │  BTP Traffic Police Telemetry        │
│  - 326,156 complaints (2023–2024)    │     │  - GPS coordinates (lat, lon)        │
│  - 198 Bengaluru BBMP Wards          │     │  - Incident telemetry & causes       │
└──────────────────┬───────────────────┘     └──────────────────┬───────────────────┘
                   │                                            │
                   ▼                                            ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           1. Crosswalk Taxonomy Engine                            │
│  - 161 Category Mappings indexed (Direct, Probable, Ambiguous, Excluded)          │
│  - 13 Active Cross-Agency Event Families (Potholes, Waterlogging, Tree Fall, etc.)│
└──────────────────────────────────────────┬────────────────────────────────────────┘
                                           │
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                    2. Gated Candidate Generation & Spatial PIP                    │
│  - Gating 1: Temporal compatibility window (<= 48h)                               │
│  - Gating 2: Event family taxonomy compatibility                                  │
│  - Gating 3: Ray-casting Point-in-Polygon (BTP point strictly inside BBMP ward)   │
│  - Gating 4: Automatic exclusion of non-fusion municipal categories               │
└──────────────────────────────────────────┬────────────────────────────────────────┘
                                           │
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                      3. Decoupled 4-Feature Match Scoring                         │
│  Score = 0.25·f_temporal + 0.35·f_spatial + 0.25·f_semantic + 0.15·f_text         │
└──────────────────────────────────────────┬────────────────────────────────────────┘
                                           │
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│               4. Entity Resolution & Canonical Event Clustering                   │
│  - Connected-component graph clustering of matched observation pairs              │
│  - Synthesizes unified Canonical Event (Centroid coords, temporal bounds, title)  │
└──────────────────────────────────────────┬────────────────────────────────────────┘
                                           │
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                     5. Full CHEF Calculator with Source Diversity                 │
│  - Source Diversity (30%): Rewards cross-agency corroboration (BBMP + BTP)        │
│    vs penalizing single-agency ticket inflation                                   │
│  - Cross-Source Agreement (20%) + Geographic Consistency (15%)                    │
│  - Source Reliability (20%) + Temporal Freshness (15%)                            │
└──────────────────────────────────────────┬────────────────────────────────────────┘
                                           │
                                           ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│             FastAPI REST Endpoints  ──>  Interactive Citizen Dashboard            │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Empirical Benchmark & Comparative Evaluation

Evaluated against the Stratified Ground-Truth Gold Set of Bengaluru municipal and traffic incidents across strong positives, hard negatives, and cross-ward cases:

| Approach | TP | FP | FN | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline 1 (Date + Ward)** | 5 | 2 | 0 | 0.714 | 1.000 | **0.833** |
| **Baseline 2 (Date + Ward + Naive Category)** | 0 | 0 | 5 | 0.000 | 0.000 | **0.000** |
| **LOCALYN (Ours: Crosswalk + PIP + Multi-Feature Scorer)** | 5 | 0 | 0 | **1.000** | **1.000** | **1.000** |

### Methodological Analysis:
- **Baseline 1 Failure Mode:** Relies solely on co-occurrence in the same ward and date. Generates high False Positives by conflating unrelated grievances (e.g., streetlight failures or stray animal calls) with traffic bottlenecks.
- **Baseline 2 Failure Mode:** Naively checks string equality between administrative grievance names (`Road Maintenance(Engg) -> Potholes`) and police incident telemetry (`pot_holes`). Because separate civic agencies employ different administrative taxonomies, naive matching yields 0% recall.
- **LOCALYN Superiority:** Bridges the semantic gap through our 161-row administrative crosswalk, verifies physical spatial containment using point-in-polygon ray casting over BBMP ward boundaries, and scores multi-evidence dimensions to achieve optimal precision and recall.

---

## 3. Directory Structure

```text
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py          # FastAPI REST endpoints (telemetry, fusion & benchmarks)
│   │   │   └── __init__.py
│   │   ├── chef/
│   │   │   ├── calculator.py      # Explainable evidence confidence calculator (CHEF)
│   │   │   └── __init__.py
│   │   ├── classifier/
│   │   │   ├── classifier.py      # Deterministic 3-class keyword classifier
│   │   │   └── __init__.py
│   │   ├── database/
│   │   │   ├── db.py              # SQLite connection, schema, queries & deduplication
│   │   │   ├── models.py          # Pydantic schemas for reports, canonical events & benchmarks
│   │   │   ├── seed_hyperlocal.py # Bengaluru corridor seed data
│   │   │   └── __init__.py
│   │   ├── fusion/                # Multi-Agency Cross-Source Fusion Module
│   │   │   ├── crosswalk.py       # 161-row taxonomy engine with strength indexing
│   │   │   ├── matcher.py         # Candidate generator gating & 4-feature scorer
│   │   │   ├── cluster.py         # Connected-component entity resolution & Canonical Events
│   │   │   ├── gold_set.py        # Stratified ground-truth benchmark pairs
│   │   │   └── __init__.py
│   │   ├── geo/                   # Spatial & Ward Boundary Engine
│   │   │   ├── wards.py           # 198 BBMP ward polygons, ray-casting PIP & normalization
│   │   │   └── __init__.py
│   │   ├── evaluation/            # Academic Benchmark Suite
│   │   │   ├── benchmark.py       # Evaluates Baseline 1, Baseline 2, and LOCALYN (P, R, F1)
│   │   │   └── __init__.py
│   │   ├── ingestion/             # Heterogeneous ingestion engine (NewsData.io, OpenWeatherMap)
│   │   ├── nlp/                   # spaCy entity extractor (Localities, Temporal phrases)
│   │   ├── config.py              # Configuration & environment variables loader
│   │   └── main.py                # FastAPI application entry point with CORS & lifespan
│   ├── tests/
│   │   ├── test_telemetry.py      # Unit tests for real-time telemetry, dedup, and DB
│   │   ├── test_fusion.py         # Unit tests for crosswalk, PIP, fusion, cluster, bench
│   │   ├── test_api.py            # API endpoint integration tests
│   │   └── __init__.py
│   ├── requirements.txt           # Python dependencies
│   └── localyn.db                 # SQLite database
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Unified Dashboard with Multi-Agency Fusion & Benchmark
│   │   ├── App.css                # Component styles
│   │   ├── index.css              # Civic design system tokens & dark theme
│   │   ├── components/
│   │   │   └── BengaluruMap.jsx   # Interactive geospatial radar map
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── LOCALYN_BBMP_2023_2024_BTP_Crosswalk.csv  # 161-row verified taxonomy crosswalk
├── LOCALYN_Matching_Methodology.md           # Formal academic matching methodology specification
├── run_fusion_benchmark.py                  # Standalone CLI evaluation demo script
├── run_pipeline.py                          # Ingestion pipeline runner
└── README.md
```

---

## 4. Full CHEF Confidence Framework

CHEF (**Confidence Heuristic via Evidential Factors**) evaluates explainable confidence over synthesized **Canonical Events**:

$$\text{CHEF} = 0.30 \times S_{\text{diversity}} + 0.20 \times S_{\text{reliability}} + 0.20 \times S_{\text{agreement}} + 0.15 \times G_{\text{geo}} + 0.15 \times T_{\text{freshness}}$$

### Why Source Diversity Matters:
- Single-agency duplication (e.g., multiple duplicate tickets submitted by a citizen on the BBMP portal) is penalized ($0.50$), preventing artificial confidence inflation.
- Cross-agency corroboration (e.g., a citizen BBMP pothole ticket confirmed by BTP Traffic Police road telemetry) boosts score to **85%+**.
- Tri-corroboration (BBMP + BTP + Official Weather/News) reaches **98%** confidence.

---

## 5. API Endpoints

### Core Ingestion & Telemetry:
- `GET /health`: System health and service telemetry
- `GET /reports`: List ingested reports with filters (`category`, `search`, `limit`)
- `GET /reports/{id}`: Single report with factor breakdown
- `POST /ingest`: Trigger real external API ingestion

### Multi-Agency Fusion & Benchmarks:
- `GET /fusion/crosswalk/summary`: Statistical summary of 326k grievances across 161 taxonomy mappings
- `GET /fusion/crosswalk/mappings`: Filter crosswalk items by strength (`Direct`, `Probable`, `Ambiguous`, `Do not map`)
- `GET /fusion/canonical-events`: Retrieve synthesized multi-agency Canonical Events with CHEF scores
- `GET /fusion/benchmark`: Run the 3-baseline benchmark and return Precision, Recall, F1, and Markdown table
- `POST /fusion/match`: Run candidate generator and 4-feature scorer on arbitrary BBMP + BTP pairs

---

## 6. How to Run

### Backend:
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend:
```bash
cd frontend
npm install
npm run dev
```

### Standalone CLI Benchmark:
```bash
python run_fusion_benchmark.py
```

### Automated Unit Tests:
```bash
python -m unittest discover backend/tests
```
