# StockSense — AI-Powered Warehouse Intelligence Platform

A full-stack inventory management system with semantic search, natural language queries,
async PostgreSQL, Redis caching, and real-time performance monitoring.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│   Dashboard │ Inventory │ Semantic Search │ Ask Vikram │ Metrics │
│                     Vite + TypeScript + Tailwind                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP (proxied by Vite in dev)
┌──────────────────────────▼──────────────────────────────────────┐
│                      FastAPI (async)                             │
│                                                                  │
│  PerformanceMiddleware  ──►  api_metrics table                   │
│                                                                  │
│  /api/inventory/*    ──►  inventory router                       │
│  /api/metrics        ──►  metrics router                         │
│                                                                  │
│  EmbeddingService  (OpenAI text-embedding-3-small)               │
│  NLQService        (GPT-4o-mini + streaming)                     │
└───────────┬─────────────────────────┬───────────────────────────┘
            │                         │
┌───────────▼───────┐     ┌───────────▼───────────────────────────┐
│    Redis 7        │     │     PostgreSQL 16 + pgvector           │
│  TTL-based cache  │     │  skus (Vector 1536)                    │
│  60s – 300s TTL   │     │  inventory_records                     │
└───────────────────┘     │  api_metrics                           │
                          └────────────────────────────────────────┘
```

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncpg
- **Database**: PostgreSQL 16 + pgvector (cosine similarity search)
- **Cache**: Redis 7 (TTL-based, per-endpoint caching)
- **AI**: OpenAI `text-embedding-3-small` (1536d vectors), `gpt-4o-mini` (streaming NLQ)
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Recharts
- **Migrations**: Alembic
- **Infrastructure**: Docker Compose

---

## Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Desktop

### 1. Clone and install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://stocksense:stocksense123@localhost:5432/stocksense
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-...your-key-here...
```

### 3. Start services

```bash
docker-compose up -d
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Seed the database

```bash
python -m app.seed
```

### 6. Generate embeddings (requires OpenAI key)

```bash
python -m app.services.embedding_service
```

### 7. Start the API server

```bash
uvicorn app.main:app --reload --port 8000
```

### 8. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## API Endpoints

| Method | Endpoint | Description | Cached |
|--------|----------|-------------|--------|
| GET | `/api/inventory/skus` | Paginated SKU list | 300s |
| GET | `/api/inventory/skus/{id}` | Single SKU | 300s |
| GET | `/api/inventory/categories` | Category list | 300s |
| GET | `/api/inventory/stock` | Current stock levels | 60s |
| GET | `/api/inventory/alerts` | Expiring/expired/low stock | 30s |
| GET | `/api/inventory/search?q=...` | Semantic vector search | 120s |
| GET | `/api/inventory/ask?q=...` | Streaming NLQ (GPT) | No |
| GET | `/api/metrics` | Performance statistics | No |
| GET | `/health` | Liveness probe | No |

API docs: **http://localhost:8000/docs**

---

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard with expiry/stock alerts, auto-refreshes every 30s |
| `/inventory` | Searchable, filterable SKU table with pagination |
| `/search` | Semantic search — find by meaning, not keywords |
| `/ask` | Chat with Vikram, the AI warehouse assistant (streaming) |
| `/metrics` | P95 latency, cache hit rates, slowest requests chart |

---

## Screenshots

*Add screenshots here after running the app.*

---

## Key Design Decisions

**Why async?**
Every database query and Redis call is I/O-bound. Using `async/await` throughout lets
a single uvicorn worker handle hundreds of concurrent requests without blocking.

**Why pgvector?**
Storing embeddings in Postgres alongside inventory data avoids a separate vector DB.
For 500–50,000 SKUs, pgvector's cosine similarity performance is more than sufficient.

**Why Redis for caching?**
Inventory data is read far more often than it changes. Caching `alerts` for 30s and
`sku-lists` for 300s reduces Postgres queries by ~80% under typical load — visible in
the Metrics page cache hit rate column.

**Why stream the NLQ?**
GPT-4o-mini takes 2–5s to generate a full response. Streaming tokens as they arrive
gives instant visual feedback — the UI feels responsive even though the total time is
the same.
