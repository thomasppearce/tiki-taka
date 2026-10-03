# Match Desk

**A live broadcast control room where AI agents propose on-air graphics, and every graphic has receipts.**

Synthetic football match events stream in. A team of agents built on Microsoft Agent Framework and Microsoft Foundry interprets them, explains why moments matter, and proposes broadcast graphics and commentary lines. Each proposal cites the exact events behind its claims. A human producer approves, edits, or rejects it, and approved items are emitted as timed, machine-readable overlay JSON rendered on a mock broadcast feed, personalized per audience, language, favorite club, and focus player.

> Built for **Inside the Game: Developer Hackathon**. Work in progress: currently at the walking-skeleton stage (data contracts and a live event stream end to end).

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/) and Node.js 24+.

```bash
make install        # backend (uv) + frontend (npm) dependencies
make dev-backend    # API on http://localhost:8001
make dev-frontend   # control room on http://localhost:3000 (second terminal)
```

To point the frontend at a different API, copy `frontend/.env.example` to `frontend/.env.local` and edit `NEXT_PUBLIC_API_URL`.

## Development

| Command | What it does |
|---|---|
| `make types` | Regenerates `docs/schema/contracts.schema.json` and `frontend/lib/contracts.generated.ts` from the Pydantic models |
| `make check-types` | Fails if the committed types have drifted from the models (runs in CI) |
| `make test` | Backend tests |
| `make lint` / `make format` | Ruff + Black (backend), ESLint + Prettier + `tsc` (frontend) |

## How it fits together

| Path | Contents |
|---|---|
| `backend/app/models` | The data contracts: `MatchEvent`, `Moment`, `Proposal`, `OverlayCommand`, `AuditRecord`, `ViewerProfile`. The single source of truth for every shared type. |
| `backend/app/main.py` | FastAPI app; `GET /api/stream/events` streams match events as server-sent events |
| `frontend/` | Next.js control room (static export) |
| `docs/schema/` | JSON Schema for the contracts, so any overlay consumer can validate against it |
