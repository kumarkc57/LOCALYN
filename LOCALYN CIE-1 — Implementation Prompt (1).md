# LOCALYN CIE-1 — Implementation Prompt

You are working on an existing LOCALYN repository. Your task is to implement **CIE-1 only**: a small, real, end-to-end working slice of the LOCALYN hyperlocal public intelligence platform.

## 1. FIRST: INSPECT THE EXISTING REPOSITORY

Before changing anything:

1. Inspect the complete existing repository structure.
2. Identify the existing backend/frontend framework and dependencies.
3. Reuse the existing structure and code wherever possible.
4. Do **NOT** reinitialize the project.
5. Do **NOT** create duplicate backend/frontend folders.
6. Identify:
   - what already works
   - what is missing for CIE-1
   - required dependencies
   - required API keys/environment variables
7. Report the findings briefly.
8. Then implement CIE-1 in the existing architecture.

Expected existing structure is approximately:

```text
backend/
└── app/
    ├── nlp/
    ├── fusion/
    ├── chef/
    ├── geo/
    ├── ingestion/
    └── api/

frontend/
```

Adapt to the actual repository if it differs.

---

# 2. CIE-1 OBJECTIVE

Build this working pipeline:

```text
NewsData.io ───────┐
                   ├──> Ingestion → SQLite → NLP → Classification → Partial CHEF → FastAPI → Frontend
OpenWeatherMap ────┘
```

The system must use **real external data**.

Do not use hardcoded demo data as the primary data source.

---

# 3. TECHNOLOGY

Use the existing stack where possible.

Preferred stack:

### Backend
- Python
- FastAPI
- SQLite
- SQLAlchemy or the existing database layer
- spaCy
- Pydantic

### Frontend
- Existing React/Vite setup if present
- CSS
- Use the existing frontend structure and visual language

### External APIs
- NewsData.io
- OpenWeatherMap

API keys must be loaded from environment variables.

Never hardcode API keys.

Provide/update:

```text
.env.example
```

with placeholders.

---

# 4. DATABASE

Implement a SQLite database for CIE-1.

Minimum report fields:

```text
id
source
raw_text
category
location
event_time
confidence
ingested_at
```

Also include where useful:

```text
title
url
source_type
latitude
longitude
```

Use proper timestamps.

The database must persist ingested reports.

---

# 5. NEWS INGESTION

Implement:

```text
fetch_news()
```

using NewsData.io.

Fetch relevant Bengaluru/local news.

Normalize the incoming records into the internal report format.

Implement only simple deterministic deduplication:

- normalize title using lowercase, whitespace normalization, and punctuation normalization
- skip insertion when:
  - same source
  - near-identical normalized title
  - within the previous 24 hours

Do NOT implement sophisticated semantic deduplication.

Store the original article URL.

---

# 6. WEATHER INGESTION

Implement:

```text
fetch_weather()
```

using OpenWeatherMap.

Retrieve current Bengaluru weather information.

Normalize it into the same internal report/event-report structure.

Store it in SQLite.

---

# 7. NLP

Use spaCy for basic information extraction.

Extract:

- `LOCATION`
- `TIME`

where available.

Do not build an advanced NLP pipeline.

If a field cannot be extracted, safely store it as null/unknown.

---

# 8. CLASSIFICATION

Implement a simple deterministic classifier with exactly these categories:

```text
TRAFFIC
WEATHER
OTHER
```

Use keyword/rule-based classification.

Examples:

Traffic keywords may include:

```text
traffic
congestion
jam
accident
road
vehicle
commute
collision
```

Weather keywords may include:

```text
rain
rainfall
flood
flooding
storm
weather
temperature
wind
thunder
```

The classifier must be deterministic and easy to inspect.

---

# 9. PARTIAL CHEF

Implement the CIE-1 version of CHEF.

CHEF is an **evidence-confidence score**, not a truth detector.

Use these provisional, frozen CIE-1 weights:

```text
Source Reliability       = 0.30
Temporal Consistency     = 0.25
Corroboration             = 0.25
Source Agreement          = 0.10
Geographic Consistency    = 0.10
```

Total:

```text
1.00
```

Formula:

```text
CHEF =
    0.30 * source_reliability
  + 0.25 * temporal_consistency
  + 0.25 * corroboration
  + 0.10 * source_agreement
  + 0.10 * geographic_consistency
```

Clamp the final value to:

```text
0.0 – 1.0
```

For CIE-1:

```text
source_agreement = 1.0
geographic_consistency = 1.0
```

because full cross-source event fusion and geographic consistency are not implemented yet.

Implement reasonable deterministic functions for:

- source reliability
- temporal consistency
- corroboration

Keep them simple, explainable, and easy to modify later.

Do NOT claim that the resulting score proves an event is true.

---

# 10. CONFIDENCE EXPLANATION

The API must expose the individual CHEF factors, not only the final score.

Example structure:

```json
{
  "confidence": 0.78,
  "chef": {
    "source_reliability": 0.9,
    "temporal_consistency": 0.8,
    "corroboration": 0.6,
    "source_agreement": 1.0,
    "geographic_consistency": 1.0
  }
}
```

The frontend must make these factors understandable to a user.

---

# 11. FASTAPI

Implement:

```text
GET /health
GET /reports
GET /reports/{id}
```

`/health` should confirm that the backend is running.

`/reports` should return persisted reports from SQLite.

`/reports/{id}` should return a single report with its confidence information.

Add CORS so the frontend can communicate with the backend.

The frontend must **never directly access SQLite**.

---

# 12. FRONTEND

Build one polished citizen-facing dashboard.

Do NOT build an admin CRUD interface.

The screen should communicate:

```text
LOCALYN
Bengaluru Urban Intelligence
```

Each report should visibly show:

- title/summary
- category
- location
- source
- timestamp
- confidence
- confidence tier
- source link where available

Use a clean, modern civic-information interface.

The confidence explanation should be accessible from the report/card/detail view.

The frontend must consume data from the FastAPI API.

Do not hardcode the displayed reports.

---

# 13. CIE-1 SCOPE — STRICTLY OUT OF SCOPE

Do NOT implement these in CIE-1:

- DBSCAN
- event clustering
- event fusion
- canonical event generation
- source independence analysis
- contradiction detection
- evidence graph
- event lifecycle/state machine
- route matching
- PostGIS
- Redis
- citizen submission forms
- authentication
- mobile application
- microservices
- sophisticated maps
- full LLM pipeline
- LLM-vs-NLP experiments
- confidence calibration experiments
- research benchmarking
- advanced geographic relevance
- advanced semantic deduplication

These are future CIE-2/research-stage capabilities.

Do NOT add them just to make the implementation look larger.

---

# 14. NO LLM IN CIE-1 CORE PIPELINE

Do not introduce an LLM into the CIE-1 core pipeline.

CIE-1 should demonstrate:

```text
real data
→ normalization
→ NLP extraction
→ classification
→ partial evidence confidence
→ API
→ frontend
```

LLM-assisted extraction/event briefs can be added later in CIE-2.

---

# 15. DEVELOPMENT ORDER

Follow this order:

1. Inspect repository
2. Verify existing setup
3. Implement/verify SQLite schema
4. Implement NewsData.io ingestion
5. Implement OpenWeatherMap ingestion
6. Implement spaCy extraction
7. Implement classification
8. Implement partial CHEF
9. Implement FastAPI endpoints
10. Implement frontend dashboard
11. Integrate frontend with backend
12. Test complete pipeline
13. Update README
14. Verify the final demo from a clean run

Do not jump ahead into future features.

---

# 16. TESTING

Add basic tests or validation for:

- database insertion
- news deduplication
- NLP extraction
- classification
- CHEF calculation
- API responses

At minimum verify:

```text
ingestion → database → processing → API → frontend
```

works end-to-end.

Handle API failures gracefully.

The application should not crash simply because one external API fails.

---

# 17. README

Update the README with:

- project overview
- CIE-1 architecture
- setup instructions
- environment variables
- API keys required
- database setup
- how to run backend
- how to run frontend
- available endpoints
- what CIE-1 implements
- what is intentionally stubbed
- CIE-2 roadmap

Clearly state that CHEF in CIE-1 is a **partial evidence-confidence implementation**.

---

# 18. FINAL DEMO ACCEPTANCE TEST

The final implementation must allow this sequence:

```text
1. Start backend
2. Run ingestion
3. Real NewsData.io/OpenWeatherMap data enters SQLite
4. NLP extracts available location/time information
5. Reports receive TRAFFIC/WEATHER/OTHER classification
6. Partial CHEF confidence is calculated
7. FastAPI exposes the reports
8. Frontend loads reports from the API
9. User can see confidence and its component factors
10. User can open the original news source where applicable
```

There must be no dependency on hardcoded demo records for the main demonstration.

---

# 19. ACADEMIC POSITIONING

CIE-1 is the initial working slice of LOCALYN.

It establishes:

```text
heterogeneous public-data ingestion
+
structured NLP extraction
+
domain classification
+
explainable partial confidence
+
API-based delivery
+
citizen-facing presentation
```

Do not describe CIE-1 as the complete LOCALYN research system.

The later research contribution will focus on:

```text
heterogeneous report fusion
→ canonical urban events
→ source independence
→ full CHEF
→ geographic relevance
→ LLM-assisted structured interpretation
→ ground-truth evaluation
```

---

# 20. IMPORTANT IMPLEMENTATION RULE

Prioritize **working software over feature count**.

Do not create unnecessary abstractions.

Do not over-engineer.

Do not add future features unless required for the CIE-1 pipeline.

Reuse existing code.

Keep the architecture clean enough that CIE-2 can extend:

```text
ingestion
    ↓
normalization
    ↓
NLP
    ↓
classification
    ↓
fusion
    ↓
CHEF
    ↓
geo
    ↓
API
    ↓
frontend
```

CIE-1 may leave `fusion` and `geo` as placeholders/stubs where appropriate.

---

## START NOW

First inspect the repository and report:

1. Existing structure
2. Existing working functionality
3. Missing CIE-1 components
4. Dependencies/API keys required
5. Exact implementation order

Then begin implementing CIE-1.