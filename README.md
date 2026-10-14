# Football Courtroom

Football Courtroom is a mock, AI-storytelling football experience where match moments are reframed as courtroom cases. Phase 1 established the project foundation, and Phase 2 adds a deterministic synthetic match engine and live replay system that drives future courtroom case generation.

## Stack

- Frontend: React with Vite
- Backend: Python with FastAPI
- Local development: Node.js + Python virtual environment
- Synthetic data: Seeded, deterministic event generation using Python standard library

## Project structure

- [backend/app/main.py](backend/app/main.py): FastAPI routes and CORS configuration
- [backend/app/synthetic_match.py](backend/app/synthetic_match.py): synthetic generator, event sequencing, and match-state calculations
- [frontend/src/App.jsx](frontend/src/App.jsx): landing page, courtroom placeholder, and live match replay interface
- [scripts/start-dev.sh](scripts/start-dev.sh): starts backend and frontend together
- [scripts/stop-dev.sh](scripts/stop-dev.sh): stops the local services

## Local setup

1. Open a terminal in the project root.
2. Create and activate the Python environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r backend/requirements.txt
   ```
3. Install the frontend dependencies:
   ```bash
   cd frontend
   npm install
   cd ..
   ```
4. Start the app locally:
   ```bash
   ./scripts/start-dev.sh
   ```
5. Open the frontend in the browser at http://localhost:5173.
6. Check the backend health endpoint at http://localhost:8000/health.

## Match engine usage

The backend includes a deterministic synthetic match generator that can be reused and extended with different seeds:

```python
from app.synthetic_match import generate_match

match = generate_match(seed=101)
print(match.match_id)
print(len(match.events))
print(match.events[0])
```

This preserves realistic event ordering, score updates, substitutions, and synthetic metadata while remaining fully fictional.

## API overview

- GET /health
- GET /api/matches
- GET /api/matches/{match_id}
- GET /api/matches/{match_id}/events
- GET /api/matches/{match_id}/state?through_event=N
- GET /api/matches/{match_id}/stream?speed=1.0

The SSE endpoint streams events in order with a configurable replay speed and gracefully stops when the client disconnects.

## Start and stop commands

- Start both services:
  ```bash
  ./scripts/start-dev.sh
  ```
- Stop both services:
  ```bash
  ./scripts/stop-dev.sh
  ```

## Testing

Run backend tests from the project root:

```bash
source .venv/bin/activate
cd backend
pytest
```

Run the frontend validation commands:

```bash
cd frontend
npm run lint
npm run build
```

## Notes

- All match data is synthetic and intentionally fictional.
- The generator produces consistent events from a seed, making it easy to reproduce scenarios and debug replay logic.
- The architecture remains modular so future phases can add agent logic, richer event interpretation, and courtroom verdict generation without a rewrite.
