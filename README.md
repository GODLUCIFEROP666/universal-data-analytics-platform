# Universal Data Analytics Platform

A production-ready, 100% free, open-source, offline-capable Universal Data Analytics Platform for instant Excel and CSV data profiling, automated chart generation, rule-based insights, and multi-format exports.

## Features

- **Messy File Support**: Upload CSV, XLS, and XLSX files up to 50 MB.
- **Smart Cleaning**: Automatic detection of header rows, merged title banners, and trailing TOTAL/SUBTOTAL summary rows.
- **Strict Data Type Detection**: Automatically classifies columns into Numeric (80%+ rule), Date (80%+ rule), Boolean (80%+ rule), Category, ID/Key, Email, Phone, and URLs.
- **Automated Visualization Engine**: Recommends up to 10 chart types including Bar, Horizontal Bar, Line, Area, Pie, Donut, Histogram, Boxplot, Scatter, and Correlation Heatmaps with Top-N + Others aggregation.
- **Manual Chart Selection & Live Preview**: Interactively select any X/Y column pair and chart type to preview and add custom charts to the dashboard on demand.
- **Executive Dashboard**: KPI summary cards, automated rule-based insight cards, dataset health metrics, interactive data table with search, category/range filters, sorting, server pagination, and column visibility control.
- **Comprehensive Multi-Format Export**:
  - Full-dashboard **PNG** high-res capture
  - Multi-page **PDF** export with automated page-break alignment (no chart clipping)
  - Processed **Excel (.xlsx)** export with Executive Summary, Column Details, Correlation Matrix, Insights, and Clean Data sheets
  - Processed **CSV** export
  - Individual per-chart **PNG** downloads
- **Admin System & Counters**:
  - SQLite persistent counters for Total Visitors, Files Uploaded, Analyses Completed, and Active Users.
  - Bcrypt password hashing and JWT authentication for administrator access.
- **Strict Free & Open-Source Policy**: 0 paid APIs, 0 cloud AI services, 0 proprietary SDKs, 0 external runtime CDNs.

## Project Architecture

```
data/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point & lifespan
│   │   ├── database.py          # SQLite database layer (admin & counters)
│   │   ├── auth_utils.py        # bcrypt & PyJWT token utilities
│   │   ├── analyzer/            # Pure Python data profiling & chart engine
│   │   └── routes/              # Analytics, Auth, and Counters endpoints
│   ├── requirements.txt
│   └── data.db                  # Auto-created SQLite database
└── frontend/
    ├── src/
    │   ├── App.tsx              # Dashboard container & export engine
    │   ├── components/          # StartScreen, Admin, and ChartSelector
    │   └── lib/api.ts           # Fetch API client
    ├── package.json
    └── vercel.json              # Vercel SPA deployment rules
```

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+

### Backend Setup

```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Initial Admin Login

- The administrator account is created automatically during the first database initialization.
- The initial password is read from the `ADMIN_INITIAL_PASSWORD` environment variable.
- If the environment variable is not configured, a temporary development password (`ChangeMeOnFirstLogin#123`) is used for local setup.
- Immediately after the first successful login, change the administrator password from the Admin Dashboard.
- **Never use the temporary development password in production.**

### Default Credentials (First-run)

- **Username**: `jignesh`
- **Initial Password**: Configured via `ADMIN_INITIAL_PASSWORD` (or temporary fallback `ChangeMeOnFirstLogin#123` for local dev)

*Note: Password management is handled securely via bcrypt hashes in SQLite and can be updated through the Admin Dashboard.*

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `HOST` | `127.0.0.1` | Host IP address |
| `PORT` | `8001` | Listening port |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated for production) |
| `JWT_SECRET` | *(required)* | Secret key for signing JWT tokens (backend refuses to start if missing) |
| `DATABASE_PATH` | `./data.db` | Absolute or relative path to SQLite database |
| `ADMIN_INITIAL_PASSWORD` | `ChangeMeOnFirstLogin#123` | Initial password used only during first database seeding |

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8001` | Backend API base URL |

## Deployment Readiness

### Frontend (Vercel)
The `frontend/vercel.json` file is pre-configured for SPA rewrites. Deploy the `frontend/` directory directly to Vercel.

### Backend (Render / Railway / Docker)
The `render.yaml` file provides a service definition for Render deployment using Uvicorn.

## License

This project is licensed under the [MIT License](LICENSE).
