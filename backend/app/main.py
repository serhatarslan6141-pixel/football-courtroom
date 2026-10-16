import asyncio
import json

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .case_detection import detect_cases
from .synthetic_match import calculate_match_state, create_generated_match, get_match, list_available_matches

app = FastAPI(title="Football Courtroom API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "football-courtroom-backend",
        "version": "0.1.0",
    }


@app.get("/api/matches")
async def fetch_matches() -> dict[str, object]:
    matches = list_available_matches()
    return {"matches": matches, "count": len(matches), "synthetic": True}


def require_match(match_id: str):
    try:
        return get_match(match_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Match not found. Generated matches last for this server session.")


@app.post("/api/matches", status_code=201)
def create_match() -> dict[str, object]:
    # A synchronous route runs CPU generation in FastAPI's worker thread pool.
    # Return setup metadata only: results and cases still require replay cutoffs.
    return create_generated_match().as_metadata()


@app.get("/api/matches/{match_id}")
async def fetch_match(match_id: str) -> dict[str, object]:
    match = require_match(match_id)
    teams = [
        {
            "team_id": team.team_id,
            "name": team.name,
            "short_name": team.short_name,
            "formation": team.formation,
            "primary_color": team.primary_color,
            "secondary_color": team.secondary_color,
            "players": [
                {
                    "player_id": player.player_id,
                    "name": player.name,
                    "position": player.position,
                    "squad_number": player.squad_number,
                    "is_starter": player.is_starter,
                }
                for player in team.players
            ],
        }
        for team in (match.home_team, match.away_team)
    ]
    players = [
        {
            "player_id": player.player_id,
            "name": player.name,
            "position": player.position,
            "squad_number": player.squad_number,
            "is_starter": player.is_starter,
            "team_id": team.team_id,
        }
        for team in (match.home_team, match.away_team)
        for player in team.players
    ]
    return {
        "match_id": match.match_id,
        "seed": match.seed,
        "generation_mode": match.generation_mode,
        "style": match.style,
        "synthetic": True,
        "created_at": match.created_at,
        "home_team": match.home_team.name,
        "away_team": match.away_team.name,
        "teams": teams,
        "players": players,
    }


@app.get("/api/matches/{match_id}/events")
async def fetch_match_events(match_id: str) -> dict[str, object]:
    match = require_match(match_id)
    return {"match_id": match.match_id, "count": len(match.events), "events": match.events, "synthetic": True}


@app.get("/api/matches/{match_id}/state")
async def fetch_match_state(
    match_id: str,
    through_event: Optional[int] = Query(default=None, ge=0, description="Number of chronologically sorted events to include"),
    through_timestamp: Optional[int] = Query(default=None, ge=0, description="Inclusive replay cutoff in match seconds"),
) -> dict[str, object]:
    match = require_match(match_id)
    state = calculate_match_state(
        match.events,
        through_event=through_event,
        through_timestamp=through_timestamp,
    )
    return {"match_id": match_id, "through_event": state["through_event"], "state": state, "synthetic": True}


@app.get("/api/matches/{match_id}/cases")
async def fetch_match_cases(
    match_id: str,
    through_event: Optional[int] = Query(default=None, ge=0, description="Number of chronologically sorted events to include"),
    through_timestamp: Optional[int] = Query(default=None, ge=0, description="Inclusive replay cutoff in match seconds"),
) -> dict[str, object]:
    match = require_match(match_id)
    cases = detect_cases(
        match.events,
        through_event=through_event,
        through_timestamp=through_timestamp,
        match_id=match_id,
    )
    return {"match_id": match_id, "count": len(cases), "cases": cases, "synthetic": True}


@app.get("/api/matches/{match_id}/stream")
async def stream_match_events(
    match_id: str,
    speed: float = Query(default=1.0, ge=0.25, le=4.0),
    start: int = Query(default=0, ge=0),
):
    match = require_match(match_id)
    if start >= len(match.events):
        raise HTTPException(status_code=400, detail="start must be before the end of the event list")

    async def event_generator():
        try:
            for idx in range(start, len(match.events)):
                payload = {
                    "match_id": match_id,
                    "index": idx,
                    "event": match.events[idx],
                    "synthetic": True,
                }
                if idx > start:
                    gap = match.events[idx]["timestamp"] - match.events[idx - 1]["timestamp"]
                    await asyncio.sleep(max(0, gap) / speed)
                yield f"data: {json.dumps(payload)}\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
