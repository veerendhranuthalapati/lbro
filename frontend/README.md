# LBRO Frontend

**Law-aware Breach Response Orchestrator** — Enterprise SOC dashboard built with React + Vite + TypeScript.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| Build | Vite 5 |
| Styling | TailwindCSS + custom dark SOC theme |
| Routing | React Router DOM v6 |
| State | Zustand (auth) |
| Data fetching | TanStack Query v5 + Axios |
| Charts | Recharts |
| Animation | Framer Motion |
| Icons | Lucide React |
| Dataset | **CICIDS2017** (Canadian Institute for Cybersecurity IDS 2017) |

---

## CICIDS2017 Dataset Integration

Incident data, attack signatures, and network flows are modelled after the [CICIDS2017 dataset](https://www.unb.ca/cic/datasets/ids-2017.html):

- **Attack types**: DoS Hulk, DDoS, SSH/FTP-Patator, SQL Injection, XSS, Infiltration, GoldenEye, Heartbleed, PortScan, Bot
- **Network flows**: Realistic src/dst IP pairs, packet counts, byte rates, and flow durations from the dataset
- **Severity mapping**: Each CICIDS2017 attack type is mapped to LBRO severity (CRITICAL/HIGH/MEDIUM/LOW)
- **Flow signatures**: Fwd/bwd packet asymmetry, bytes/sec, and flow duration match published dataset statistics

See `src/data/cicids2017.ts` for all sample data and commentary.

---

## Quick Start

```bash
# 1. Copy env
cp .env.example .env

# 2. Install
npm install --legacy-peer-deps

# 3. Dev server (http://localhost:5173)
npm run dev

# 4. Login with any key starting with: lbro-
#    e.g. lbro-demo-key-001
```

---

## Production Build

```bash
npm run build
# Output: dist/
```

---

## Docker

```bash
# Build image
docker build -t lbro-frontend .

# Run standalone
docker run -p 5173:5173 lbro-frontend

# Or add to existing docker-compose.yml (see docker-compose.frontend.yml)
```

---

## Pages

| Route | Page |
|---|---|
| `/login` | API key authentication |
| `/dashboard` | Live SOC dashboard with CICIDS2017 charts |
| `/incidents` | Filterable incident list |
| `/incidents/:id` | Detail: CICIDS2017 flow, timeline, evidence, notifications |
| `/compliance` | GDPR / HIPAA / DPDPA deadline tracker |
| `/evidence` | S3 evidence vault with chain-of-custody |
| `/infrastructure` | ECS / SQS / RDS / S3 live status |
| `/settings` | API key, notifications, team, IAM |

---

## Project Structure

```
src/
├── api/          # Axios client + API functions
├── components/
│   ├── layout/   # Sidebar, Navbar
│   └── ui/       # GlassCard, StatCard, Badges, Skeleton, Toast
├── data/         # cicids2017.ts — all sample data
├── hooks/        # useApi.ts — React Query hooks
├── layouts/      # AppLayout.tsx
├── pages/        # One file per route
├── routes/       # AppRouter, ProtectedRoute
├── store/        # authStore.ts (Zustand)
├── styles/       # globals.css (TailwindCSS + custom vars)
├── types/        # index.ts — all TypeScript types
└── utils/        # cn(), formatters, severity/status configs
```

---

## Environment Variables

```env
VITE_API_URL=http://localhost:8000   # Backend FastAPI URL
VITE_APP_NAME=LBRO
VITE_APP_VERSION=1.0.0
```

---

## Backend Integration

When the FastAPI backend is running, the Axios client (`src/api/client.ts`) will call real endpoints. The `X-API-Key` header is injected on every request from the Zustand auth store. React Query polls incident endpoints every 15 seconds for live updates.

Demo mode (no backend) works fully with the CICIDS2017 sample data in `src/data/cicids2017.ts`.
