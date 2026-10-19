# Football Courtroom

Football Courtroom is a mock, AI-storytelling football experience where match moments are reframed as courtroom cases. Phase 1 established the project foundation, and Phase 2 adds a deterministic synthetic match engine and live replay system that drives future courtroom case generation.

## Stack

- Frontend: React with Vite
- Backend: Python with FastAPI
- Local development: Node.js + Python virtual environment
- Synthetic data: Seeded, deterministic event generation using Python standard library

## Project structure

- [backend/app/main.py](backend/app/main.py): FastAPI routes and CORS configuration
- [backend/app/synthetic_match.py](backend/app/synthetic_match.py): fixture models and event-derived statistics
- [backend/app/simulation.py](backend/app/simulation.py): coherent possession, role, ball and timing simulation
- [backend/app/football_rules.py](backend/app/football_rules.py): supported boundary, foul, discipline and offside rules
- [backend/app/football_decisions.py](backend/app/football_decisions.py): tunable shooting geometry and passing-lane decisions
- [docs/simulation.md](docs/simulation.md): v2 event contract, supported rules and explicit model limitations
- [frontend/src/App.jsx](frontend/src/App.jsx): scene navigation and session provider
- [frontend/src/scenes](frontend/src/scenes): welcome, match replay, and courtroom presentation
- [frontend/src/session](frontend/src/session): shared context, reducer, replay loading, trial progression and session votes
- [docs/courtroom.md](docs/courtroom.md): interactive trial, evidence boundaries and future response interface
- [frontend/src/services/apiClient.js](frontend/src/services/apiClient.js): reusable backend client
- [scripts/start-dev.sh](scripts/start-dev.sh): starts backend and frontend together
- [scripts/stop-dev.sh](scripts/stop-dev.sh): stops the local services

## Local setup

1. Open a terminal in the project root.
2. Install Python 3.12+ and create the framework-capable backend environment:
   ```bash
   python3.12 -m venv .venv/phase4b
   source .venv/phase4b/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r backend/requirements-agents.txt
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

For backend-only development, run `./scripts/start-backend.sh` from the project
root. Both launchers prefer `.venv/phase4b`, verify Python 3.12+ and the pinned
framework dependencies, and refuse to silently use a legacy Python 3.9 runtime.
Use `./scripts/start-dev.sh --check` to verify runtime selection without starting
either service. Neither launcher loads `.env` or enables inference.

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
- POST /api/matches (create a new server-session match)
- GET /api/matches/{match_id}
- GET /api/matches/{match_id}/events
- GET /api/matches/{match_id}/state?through_event=N
- GET /api/matches/{match_id}/cases?through_timestamp=SECONDS
- GET /api/matches/{match_id}/stream?speed=1.0
- POST /api/matches/{match_id}/cases/{case_id}/courtroom (Phase 4B; deterministic fallback by default)

The SSE endpoint streams events in order with a configurable replay speed and gracefully stops when the client disconnects.

### Match variety

The original three fixtures remain reproducible demos with seeds 101, 202 and 303. Use **Create a new match** in the fixture picker for a fresh seeded match using the same football engine, varied club pairings, compatible lineup rotations and supported playing styles. New matches remain available through replays and browser refreshes for the current backend process; restarting the backend clears them. Saved seeds and `generation_mode` support debugging reproduction. See [match generation](docs/match-generation.md) for the API, storage lifetime, validation and scaling limits.

### Replay synchronization

The frontend uses one inclusive `through_timestamp` cutoff for statistics, cases, and visible events. Events sharing a timestamp appear together. Statistics and cases are fetched in parallel and committed together; the display holds its last complete snapshot while the next one loads. Playback advances a continuous shared clock, interpolating recorded ball movement at the selected speed. Completed events and case-eligibility boundaries trigger atomic statistics/case refreshes; the clock briefly waits for those responses. SSE remains available but is not used by the frontend.

Both `/state` and `/cases` interpret `through_event=N` as the first N chronologically sorted events, including zero for an empty replay. This corrects the previous case-endpoint behavior that filtered original generation indexes. When both filters are supplied, both apply.

Cases become eligible only when their entire observation window has elapsed: 210 seconds after a substitution, 180 after a momentum trigger, or 90 after a missed shot. `detection_timestamp` identifies the trigger; the new `available_timestamp` identifies eligibility. Case IDs derive from match, type, team, and trigger time, so they do not change when other cases qualify. These IDs differ from the previous order-based format.

Entering the courtroom pauses playback at the committed match timestamp and cancels any pending advance. Returning keeps that timestamp and remains paused until Play is pressed. The session has a separate evidence-review timestamp for future evidence controls; changing it cannot move the main replay. Navigating to welcome also pauses playback.

### API configuration

By default the frontend requests `/api` on its own origin. Vite's development proxy forwards these requests to `http://localhost:8000`, so the usual start script still works. For a separate backend origin, set `VITE_API_BASE_URL` before starting Vite or building, for example:

```bash
VITE_API_BASE_URL=https://api.example.com npm run build
```

Production hosting must either forward `/api` to FastAPI or supply that environment variable at build time. A separate backend origin also needs the frontend origin allowed in FastAPI CORS.

### Match broadcast

The Match scene starts with a fixture picker. Club colors and abbreviations come from each fixture's backend metadata. Choose a tile and enter its replay; Change fixture returns to the picker and pauses playback.

The SVG pitch projects recorded 0–100 ball coordinates in fixed stadium space, reversing attacking directions at half time. Passes, carries, shots and clearances interpolate over recorded durations, with recent possession trails and distinct turnover/pressure cues. Restart setup stays at the awarded location during its pause, with compact throw-in/corner/free-kick/goal-kick/penalty labels. Recorded card and offside context appears only after the decision. In-flight results stay hidden until completion. Missing positions are never filled with invented player tracking. See [the simulation notes](docs/simulation.md) for timing, statistics, eligibility and model assumptions.

The timeline supports mouse/touch dragging and native range-keyboard navigation. It can seek anywhere between kickoff and full time, pausing playback. Next/previous skip to distinct event timestamps. All displayed statistics, pitch events, and cases continue to use the last committed snapshot while a seek loads. Old requests are canceled and version-checked. Goals, substitutions, cards, and courtroom markers appear only once observed; case markers use eligibility time rather than trigger time. Rewinding removes future markers and cases.

The secondary rail has Stats, Events, and Cases tabs. History is paginated in groups of 20 with bounded internal scrolling. Case alerts open the existing Courtroom scene, preserving the replay return position. Reduced-motion preferences disable goal and alert animations.

### Interactive courtroom

Opening an eligible case enters one five-stage trial in the existing purple/gold courtroom. **Begin trial** starts the recorded case. The optional **Generate AI Trial** action beneath it and within later stages explicitly requests the four-agent backend; nothing generates automatically. AI results update the same evidence, opposing podium submissions and judge's ruling without resetting the stage or the independent user vote. The ruling stays sealed until voting. Live, cached and recorded-fallback sources are labeled, and actual handoffs are available in a small collapsible trace inside the courtroom. Click citations to inspect the bounded evidence replay without moving the match cursor. With AI disabled, the recorded trial remains available. See [Phase 4C](docs/phase4c.md) for the flow, safe testing and remaining limitations.

Votes remain in the current session, scoped to the fixture and case. Evidence playback is separate from the match cursor, and returning restores the exact paused match position. See [the courtroom notes](docs/courtroom.md) for component structure, evidence safeguards and the future Microsoft Foundry response interface.

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
PYTHONPATH=backend .venv/phase4b/bin/python -m pytest -q backend/tests
```

Run the frontend validation commands:

```bash
cd frontend
npm test
npm run lint
npm run build
```

## Notes

- All match data is synthetic and intentionally fictional.
- The generator produces consistent events from a seed, making it easy to reproduce scenarios and debug replay logic.
- The architecture remains modular so future phases can add agent logic, richer event interpretation, and courtroom verdict generation without a rewrite.

## Microsoft Foundry — Phase 4A

Optional backend connectivity is available through a controlled CLI probe;
normal startup and the courtroom remain deterministic and need no credentials.
See [Foundry setup and one-request test](docs/foundry.md) and [.env.example](.env.example)
for backend-only credentials, disabled-by-default live calls, local daily attempt
limits and the future Microsoft Agent Framework boundary. No orchestration is
implemented in this phase.

## Microsoft Agent Framework — Phase 4B backend

The optional backend now implements four real agents in a sequential framework
workflow: Evidence → Prosecution → Defense → Judge. It validates citations and
observations against a fixed synthetic evidence window, retains deterministic
fallback, and protects each model request with the existing daily budget.
Successful trials are cached; concurrent or failed trials are not automatically
regenerated. The frontend still uses recorded-evidence assessments.

See [Phase 4B architecture, API, offline tests and controlled opt-in](docs/phase4b.md).
The agent dependencies require Python 3.10+; the full implementation was tested
in a separate Python 3.12 environment. Base simulation and fallback remain
compatible with the original environment. Live trials require both backend
enable switches and an explicit `allow_live: true` request; all default to off.
