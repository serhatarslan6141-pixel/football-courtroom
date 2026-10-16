# Match variety and server-session storage

## What existed before this change

The startup catalog was constructed from seeds **101, 202 and 303** at module import. `random.Random(seed)` controls the complete generation, including bench names and subsequent simulation decisions. The same code and seed therefore produce identical clubs, players, events, scores and deterministic courtroom cases after every restart. Events were generated, not read from static JSON; the inputs were simply fixed.

`generate_match` already accepted arbitrary seeds, but chose only one of three fixed pairings using `seed % 3`. The old `get_match` silently created unknown IDs using `len(MATCH_LIBRARY) + 1`, making that ID's contents depend on request order and server uptime. There was no explicit creation endpoint or creation UI.

## Current behavior

The three original demo IDs and seeds remain. Their RNG call order, full event logs, player squads and case payloads were checked against the pre-change baseline. Their recorded outcomes are unchanged. The new setup path is opt-in and feeds the **same** `simulate_match` engine; football rules, decisions, statistics and case detection are untouched.

The fixture picker has one **Create a new match** button. Creation selects the new fixture once its full simulation has completed; Enter replay uses the normal match loading and synchronized snapshot flow. Users can keep creating and revisiting matches without restarting the server. Tiles distinguish demos from new matches and show three fixtures per page, preserving the broadcast layout for a larger catalog. Club colors are embedded in the catalog, so 100 fixtures do not trigger 100 detail requests.

### API

- `POST /api/matches`: no configuration/body required. Generates a fresh match and returns setup metadata with HTTP 201: `match_id`, `seed`, `generation_mode`, `style`, `created_at`, fixture names and club colors. It does **not** include final scores or future cases.
- `GET /api/matches`: all current demo and generated fixture metadata, including colors.
- Existing detail, events, state, cases and stream routes work with generated IDs unchanged.
- Unknown/expired IDs return **404** without changing the catalog. In particular, a generated ID after a server restart is never silently replaced with a different seed's match.

Creation runs in a synchronous FastAPI route, which uses its worker thread pool. A short lock reserves the seed and publishes the completed match atomically. It is not held while running the simulation. Failed generation publishes no partial match and releases its reservation. Concurrent creations cannot reuse a reserved seed.

### Randomness and variety

The creation service obtains a fresh nonzero 53-bit seed from `secrets`, checking both stored and in-flight seeds. This fits exactly in a JavaScript number. The seed becomes the stable ID `generated-<seed>` and is retained in metadata. All football randomness thereafter comes from the match-local `random.Random(seed)`.

For `generation_mode: varied-v1`, seeded setup:

1. Selects two distinct clubs from the existing six, including home/away ordering: 30 possible ordered matchups.
2. Chooses balanced or pressing play, the two distinct pressure behaviors already supported by the engine. This remains a shared match style, not a new per-club tactical simulation.
3. Rotates zero to three outfield reserves per team into **matching actual roles**. Demoted starters remain eligible substitutes. The first eleven and `is_starter` flags are updated together; IDs, shirt numbers, roles, goalkeeper and formation balance remain consistent.
4. Runs the existing possession simulation. Goals, player actions, cards, restarts and cases emerge from that log, without quotas, injected events or score corrections.

Distinct seeds produce different action sequences and performances. Scorelines, pairings and starters may naturally repeat; cases are possible rather than guaranteed. Generation is never rerolled to manufacture a different score or a courtroom case.

### Reproduction

With the same source version, use the saved seed and setup mode:

```python
from app.synthetic_match import generate_match

match = generate_match(saved_seed, variety=True)
# Or explicitly retain an exported identifier:
match = generate_match(saved_seed, match_id=saved_id, variety=True)
```

This reproduces squads, events, outcomes and case evidence. The creation service stamps the actual creation time; the pure generator retains a deterministic placeholder time, so that timestamp is not part of replay equivalence. Default `generate_match(seed)` retains the original demo-style setup behavior.

## Lifetime and replay safety

The full completed match is stored once in the existing in-memory library for the current **Python server process**. Replays, repeat GETs, browser refreshes and other clients of that process reuse it. A browser session is not the storage boundary. A server restart or development reload restores just the three demos; there is no database, disk persistence or shared multi-worker catalog.

Creation does not mutate an existing match. The frontend gives each creation a request version, disables duplicate clicks while pending, invalidates old catalog results and retains existing match/replay response guards. If the user selects or enters another fixture while generation runs, completion adds the new match to the catalog without stealing selection, resetting the current cursor or opening another scene. A creation failure is separate from existing replay errors and leaves the old fixture playable. Switching fixtures still starts that fixture's replay at zero, as before; returning from court preserves its exact paused return position.

A disconnected client may miss a successful POST response while the server still stores the match. Refreshing the catalog discovers it. The client does not automatically retry POST requests. Stored votes remain keyed by match and case, and generated cases retain their generated match ID and full observation-window eligibility.

## Validation and scaling limits

Focused tests cover unchanged demo log fingerprints/outcomes, varied-seed reproduction, real action/score differences, legal squad rotation, concurrency/collision handling, failed generation, repeated clients, server restart, case ownership/eligibility, creation UI, fixture switching, creation races and catalog pagination. Existing spatial, temporal, active-player, goalkeeper and statistics invariants also run against varied matches.

A manual 100-match audit retained 103 matches including the demos and observed:

- 100 distinct football action sequences, all 30 ordered matchups and 35 scorelines.
- 54 balanced and 46 pressing matches; all three existing case types occurred.
- Every match in that sample had valid cases. This is an observation, not an enforced guarantee.
- About 22 seconds for generation plus statistics/case checks, and roughly 1 GB peak memory in that local audit process.

Keeping complete logs, including explicit player snapshots, makes memory grow with the catalog. The UI is paginated, but server storage is unbounded and process-local. Durable storage, server-side pagination, retention policies and queued generation belong to a larger production-scale change. No courtroom or Foundry changes are included here.
