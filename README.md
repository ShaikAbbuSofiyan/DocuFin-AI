# DocuFin AI — Enterprise Financial Document Intelligence Platform

DocuFin AI is an enterprise-grade financial intelligence platform architected for deep document comprehension, SEC filings (10-K, 10-Q, 8-K) auditing, balance sheet reconciliation, and automated compliance verification.

Phase 1 establishes the production architecture, modular monolith backend, responsive financial SaaS application shell, health monitoring subsystems, and container orchestration.

---

## Architecture Blueprint (Phase 1 Modular Monolith)

DocuFin AI avoids premature microservice decomposition in favor of a clean, bounded **Modular Monolith**:

```
DocuFin-AI/
├── backend/
│   ├── app/
│   │   ├── api/                 # API route definitions
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   └── health.py # /health/live and /health/ready probes
│   │   │       └── router.py    # V1 route aggregator
│   │   ├── core/                # Core platform utilities
│   │   │   ├── config.py        # Pydantic Settings & typed environment loading
│   │   │   ├── logging.py       # Structured logging formatters
│   │   │   └── exceptions.py    # Centralized exception handlers & domain errors
│   │   ├── db/                  # Database connectivity & session management
│   │   │   ├── base.py          # SQLAlchemy 2.x DeclarativeBase & TimestampMixin
│   │   │   └── session.py       # Async engine & async_sessionmaker
│   │   ├── models/              # SQLAlchemy domain models
│   │   │   ├── document.py      # Financial document entity
│   │   │   └── audit.py         # Regulatory audit trail log
│   │   ├── schemas/             # Pydantic v2 validation models
│   │   │   └── health.py        # Health, readiness, and latency schemas
│   │   ├── repositories/        # Data access abstraction
│   │   │   └── base.py          # Generic AsyncRepository
│   │   ├── services/            # Domain business logic
│   │   │   └── health_service.py# PostgreSQL & Redis connection diagnostics
│   │   ├── ai/                  # AI integrations namespace (Phase 2+)
│   │   │   └── README.md        # RAG, LLM orchestrators, and prompt specs
│   │   ├── workers/             # Background workers namespace (Phase 2+)
│   │   │   └── README.md        # Async document ingestion & Celery tasks
│   │   └── main.py              # Application factory, lifespan, CORS, and routing
│   ├── alembic/                 # Database migrations
│   │   ├── versions/            # Versioned migration scripts
│   │   └── env.py               # Async Alembic configuration
│   ├── tests/                   # Pytest suite
│   │   ├── conftest.py          # Async test fixtures & in-memory SQLite DB
│   │   ├── test_config.py       # Configuration and validation tests
│   │   ├── test_exceptions.py   # Error handling tests
│   │   └── test_health.py       # Liveness & readiness probe tests
│   ├── alembic.ini              # Alembic migration configuration
│   ├── requirements.txt         # Pinned production backend dependencies
│   ├── pyproject.toml           # Backend packaging & test options
│   └── Dockerfile               # Multi-stage Python 3.12 production image
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/          # Application shell layout
│   │   │   │   ├── AppShell.tsx # Root shell coordinating Sidebar & TopNav
│   │   │   │   ├── Sidebar.tsx  # Responsive navigation & tenant card
│   │   │   │   └── TopNavbar.tsx# Search, health indicator & analyst profile
│   │   │   └── common/
│   │   │       ├── StatusBadge.tsx     # Color-coded dependency health pills
│   │   │       └── PlaceholderView.tsx # Structured enterprise coming-soon view
│   │   ├── pages/               # Application route views
│   │   │   ├── DashboardPage.tsx       # Platform overview & roadmap
│   │   │   ├── DocumentsPage.tsx       # Ingestion & Vault placeholder
│   │   │   ├── AiAssistantPage.tsx     # Conversational RAG placeholder
│   │   │   ├── ReviewQueuePage.tsx     # Human-in-the-loop audit placeholder
│   │   │   ├── AnalyticsPage.tsx       # Financial analytics placeholder
│   │   │   ├── SettingsPage.tsx        # Tenant administration placeholder
│   │   │   └── SystemHealthPage.tsx    # Live health dashboard with auto-polling
│   │   ├── services/            # API communication
│   │   │   ├── api.ts           # Fetch client with base URL & error parsing
│   │   │   └── health.ts        # TanStack Query health hooks
│   │   ├── types/               # TypeScript interfaces
│   │   │   └── health.ts
│   │   ├── router.tsx           # React Router v6 setup
│   │   ├── App.tsx              # QueryClientProvider & router mount
│   │   ├── main.tsx             # Application DOM entrypoint
│   │   └── index.css            # Tailwind directives & typography
│   ├── tests/                   # Vitest unit & component test suite
│   │   ├── setup.ts             # DOM matcher imports
│   │   ├── StatusBadge.test.tsx # Status badge unit tests
│   │   └── AppShell.test.tsx    # App shell and navigation tests
│   ├── package.json             # React 18, Vite, Tailwind, TanStack Query
│   ├── vite.config.ts           # Vite bundler, proxy & Vitest config
│   ├── tailwind.config.js       # Financial SaaS palette tokens
│   ├── nginx.conf               # SPA web server & reverse proxy
│   └── Dockerfile               # Multi-stage Node build & Nginx runtime
│
├── docker-compose.yml           # PostgreSQL, Redis, Backend, and Frontend
├── .env.example                 # Documented configuration variables
├── .gitignore                   # Excludes secrets, venvs, and build outputs
└── README.md                    # Project documentation
```

---

## Technology Stack & Mutual Compatibility

| Tier | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | FastAPI | `^0.114.0` | Asynchronous high-performance REST API |
| **Web Server** | Uvicorn | `^0.31.0` | Production ASGI web server |
| **Data Validation** | Pydantic / Pydantic Settings | `^2.6.4` / `^2.2.1` | Type validation and environment management |
| **ORM** | SQLAlchemy | `^2.0.28` | Async relational database abstraction |
| **Migrations** | Alembic | `^1.13.1` | Schema version control |
| **Database Driver** | asyncpg / psycopg2-binary | `^0.29.0` / `^2.9.9` | High-throughput async PostgreSQL driver |
| **Cache & Queue** | Redis (asyncio) | `^5.0.3` | Session cache & future worker broker |
| **Frontend Framework** | React + TypeScript | `^18.3.1` / `^5.4.5` | Strict-typed user interface |
| **Build Tool** | Vite | `^5.2.11` | Instant HMR and optimized bundler |
| **Styling** | Tailwind CSS | `^3.4.3` | Financial SaaS component design |
| **State Management** | TanStack Query | `^5.37.1` | Asynchronous server state and polling |
| **Routing** | React Router | `^6.23.1` | Client-side routing |
| **Icons** | Lucide React | `^0.378.0` | Clean enterprise iconography |
| **Backend Testing** | Pytest + pytest-asyncio | `^8.1.1` / `^0.23.6` | Async integration & unit testing |
| **Frontend Testing** | Vitest + Testing Library | `^1.6.0` / `^15.0.7` | Component and client tests |
| **Containerization** | Docker & Docker Compose | Compose v3.8 | Multi-service orchestration |

---

## Prerequisites

1. **Python**: `3.11` or `3.12` installed
2. **Node.js**: `v18+` or `v20+` (v24 supported) with `npm`
3. **Docker & Docker Compose**: (Optional for local testing; required for full container stack)

---

## Quickstart: Docker Compose

To launch the full enterprise stack with PostgreSQL 16, Redis 7, the FastAPI backend, and the Nginx React frontend:

```bash
# 1. Clone repository and navigate to root
cd DocuFin-AI

# 2. Configure environment file
cp .env.example .env

# 3. Build and launch all containers in detached mode
docker compose up --build -d

# 4. View container logs
docker compose logs -f

# 5. Execute database migrations inside the backend container
docker compose exec backend alembic upgrade head
```

### Container Endpoints
- **Frontend SPA**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **API Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Liveness Probe**: [http://localhost:8000/health/live](http://localhost:8000/health/live)
- **Readiness Probe**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`

---

## Local Development Without Docker

If Docker Desktop is not currently running on your host, you can run the backend and frontend locally with native runtimes.

### 1. Backend Setup

```bash
# From workspace root:
cd backend

# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux / macOS:
# source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Start FastAPI development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend server is now listening at [http://localhost:8000](http://localhost:8000).

### 2. Frontend Setup

```bash
# From workspace root in a separate terminal:
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

The frontend application will start at [http://localhost:5173](http://localhost:5173) with automated proxy routing to `http://localhost:8000`.

---

## Health & Readiness Endpoints

DocuFin AI exposes cloud-native health checks designed for Kubernetes / Docker container probes:

### 1. Liveness Probe (`GET /health/live`)
- **Status Code**: `200 OK`
- **Purpose**: Verifies that the FastAPI process is responsive.
- **Payload**:
```json
{
  "status": "ok",
  "app_name": "DocuFin AI",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-10-19T14:00:00Z"
}
```

### 2. Readiness Probe (`GET /health/ready`)
- **Status Code**: `200 OK` (when dependencies are healthy) or `503 Service Unavailable` (if any dependency fails)
- **Purpose**: Validates active connectivity to PostgreSQL (`SELECT 1`) and Redis (`PING`), reporting latency in milliseconds.
- **Payload**:
```json
{
  "status": "ready",
  "app_name": "DocuFin AI",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-10-19T14:00:00Z",
  "components": {
    "database": {
      "status": "connected",
      "latency_ms": 1.42,
      "details": null
    },
    "redis": {
      "status": "connected",
      "latency_ms": 0.85,
      "details": null
    }
  }
}
```

---

## Database Migrations (Alembic)

Migrations use SQLAlchemy 2.0 async connections:

```bash
cd backend

# Run pending migrations to the latest revision
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Generate a new migration revision based on models
alembic revision --autogenerate -m "add_table_name"
```

---

## Automated Testing

### Running Backend Tests (Pytest)

The test suite utilizes in-memory SQLite with an asynchronous driver and mocked Redis fixtures so tests can execute without external infrastructure dependencies:

```bash
cd backend
pytest -v
```

### Running Frontend Tests (Vitest)

```bash
cd frontend
npm run test
```

---

## Roadmap

- **Phase 1: Architecture & Project Foundation** *(Current)*: Modular monolith, FastAPI, SQLAlchemy 2.0, Alembic, Redis, React Vite App Shell, Health Dashboard, Docker Compose.
- **Phase 2: Document Ingestion & AI Parsing**: SEC filing parsing (10-K, 10-Q), OCR extraction, PDF table parsing, bounding box alignment, financial embeddings.
- **Phase 3: Financial RAG & Human-in-the-Loop Review**: Hybrid vector search, financial ratio cross-checking, confidence-based review queue, SEC compliance audit logging.
- **Phase 4: Financial Analytics & Insights**: Interactive time-series visualizers, cross-portfolio aggregation, executive report export, enterprise RBAC.
