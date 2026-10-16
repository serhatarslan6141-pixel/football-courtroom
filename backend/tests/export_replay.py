"""Real API payloads consumed by cross-stack frontend integration tests."""

import json
import sys
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
match_id = "synthetic-202"
json.dump(
    {
        "match": client.get(f"/api/matches/{match_id}").json(),
        "events": client.get(f"/api/matches/{match_id}/events").json()["events"],
        "cases": client.get(
            f"/api/matches/{match_id}/cases?through_timestamp=5400"
        ).json()["cases"],
        "snapshots": {
            str(t): {
                "timestamp": t,
                "state": client.get(
                    f"/api/matches/{match_id}/state?through_timestamp={t}"
                ).json()["state"],
                "cases": client.get(
                    f"/api/matches/{match_id}/cases?through_timestamp={t}"
                ).json()["cases"],
            }
            for t in range(31)
        },
    },
    sys.stdout,
)
