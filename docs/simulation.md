# Synthetic football simulation, v2

This is a reproducible, simplified football model, not tracking data or a prediction of real clubs. `generate_match(seed)` retains the three fictional fixtures and returns the same event log for the same seed and code version. Changing generator versions changes those logs.

## Possession and space

`PossessionSimulation` owns the match clock, ball position, controlling team/player, active XI, bench, score, period and possession sequence. Each recorded action starts at the previous action's recorded endpoint. It chooses its next action from this state, rather than placing unrelated events around the pitch.

Role anchors are approximate tactical positions used to choose recipients and defenders. They shift with territorial progress, but are never presented as measured off-ball player positions. Goalkeepers stay near their own goal and distribute to defenders. Most passes prefer nearby recipients; occasional longer distribution/switches and forward through balls have explicit context. Carries advance the current carrier rather than changing players arbitrarily. Interceptions, tackles and saves transfer control at the ball's actual location.

Coordinates remain in fixed stadium space: x/y are each 0–100. Distances assume a fictional 105 × 68 metre pitch. Home attacks toward x=100 in period 1 and x=0 in period 2; away does the opposite. Role lanes also reverse at half time. Shots originate in the attacking quarter from plausible lateral positions. `target` records the intended goal-line point; `end` records the actual endpoint, including the keeper's save location. Off-target shots can cross the goal line outside the posts.

There are seven separate reserves per club. Substitution events remove the outgoing player and activate a previously unused reserve in a compatible role group, inheriting the vacated tactical slot. Sent-off players stop participating. Substitution timing is probabilistic at stoppages, with a maximum of five changes per team; this is not a full competition-rules implementation.

## Timing and calibration

Touch/control, ball flight and carrying have different durations. Fast and slow possession tempos vary the touch times. Fouls, out-of-play balls, corners, goals and restarts consume longer recorded dead-ball spans. A `movement: reset` event explicitly relocates the ball for a restart; the frontend does not fabricate a live trajectory during that relocation.

The match has two 45-minute periods, finishing at 5400 match seconds. The real-world half-time break and added time are excluded. Events are serialized, with instantaneous reactions sharing a completion timestamp. Positive-duration spans partition the match clock without overlapping.

Probabilities and distance weights are design assumptions, not fitted professional-player parameters. There are no pass, goal, shot or case quotas and no correction of results to hit a desired score. A diagnostic sample of seeds 0–29 produced roughly 470–610 total passes (crosses included), 15–31 shots, 0–5 goals, and 52–65 minutes in play. These are observed outputs of this version, not enforced limits or statistical guarantees.

Reference points used as broad checks:

- The [Premier League's January 2024 analysis](https://www.premierleague.com/en/news/3860720) reports 58:37 ball-in-play time and 3.09 goals per match for its partial 2023/24 sample. Our shorter regulation-only model is not a statistical reproduction of that season.
- Its [March 2025 tactical analysis](https://www.premierleague.com/en/news/4271974) reports a small minority of passes being longer passes. Our receiver weights similarly favor short/medium distribution, rather than constant cross-pitch passes.
- [StatsBomb's event specification](https://github.com/hudl/open-data/blob/master/doc/StatsBomb%20Open%20Data%20Specification%20v1.1.pdf) documents action durations and carry endpoints. Our own schema uses those concepts, but is not a StatsBomb adapter.

## Event contract

Existing IDs, types, `timestamp`, `minute`, `team_id`, `player_id`, x/y, metadata and synthetic flags remain. In v2, **timestamp is completion time**.

| Field | Meaning |
| --- | --- |
| `schema_version` | `2` for the new simulation |
| `start_timestamp`, `duration` | Recorded interval ending at `timestamp`; seconds |
| `period` | 1 or 2 |
| `possession_id` | Connected passage of play; resets on ownership/restarts |
| `possession_team_id`, `ball_player_id` | Controller during the action span; null during dead play |
| `metadata.start`, `metadata.end` | Actual recorded ball endpoints |
| `metadata.target`, `intended_end` | Intended shot/pass destinations, distinct from actual endpoints |
| `metadata.attack_direction` | +1 toward x=100, −1 toward x=0 for the acting team |
| `metadata.phase`, `pass_kind`, `pass_context` | Coarse tactical context |
| `metadata.ball_in_play`, `possession_seconds` | Whether/how long the span contributes to possession |
| `metadata.previous_team`, `new_team` | Explicit ownership transition |
| `metadata.related_event_id` | Links an interception/save/goal to its preceding action |
| `metadata.player_role`, `squad_number` | Actor identity/role context |
| `metadata.shot_quality` | Coarse good/speculative label; **not xG** |
| `metadata.movement`, `restart_type` | Dead-ball relocation and restart reason |

New event types are `ball_control`, `carry`, `dribble`, `interception`, `recovery`, `clearance`, `miscontrol`, `stoppage`, and `restart`. Previously declared crosses and saves are now generated as connected actions. Team/player metadata includes `is_starter` so reserves can be distinguished from the initial XI.

## Replay, statistics and cases

The shared reducer advances one continuous match clock from animation-frame elapsed time at the selected speed. The ball linearly interpolates only between a recorded action's endpoints over its recorded interval. It never joins unrelated locations or invents player tracking. The short trail is restricted to recent recorded possessions, with a brief failed-pass cue when control changes. Pause freezes the clock and geometry; seeking reconstructs it directly. Reduced motion holds at a recorded position until the next completion. Goal cues are clock-driven, not independent CSS animations.

Statistics, history, goal labels and timeline markers consume **completed** events only. An action in flight is exposed to the caption/pitch through a whitelist without its future outcome, recipient or result description. Only the already-traversed portion of its path is drawn. A shot finishing as a goal cannot update the score early.

`state.next_update_timestamp` marks the next completion or possible case-window boundary. Statistics and cases stay unchanged within that validity interval, so the frontend need not request them at animation-frame frequency. At the boundary it briefly holds until both API responses commit together. Stale requests are canceled/version-checked as before. Network latency can slightly slow playback at these boundaries. The SSE endpoint also uses recorded timestamp gaps divided by speed.

Passes include crosses; possession sums recorded in-play spans attributed to the controller (not the pressing opponent), excluding stoppages. Tackles, successful tackles, interceptions, recoveries, carries and clearances have separate counters. Pressure is no longer counted as an attacking entry, and the former pressure-duration double count is removed. No statistics are invented to smooth the display.

All three case types retain complete evidence-window eligibility. V2 substitution cases require the incoming player to participate and increased threat per unit time. Momentum cases need threat across multiple possessions and a shot, not just passing-volume spikes. Missed-opportunity cases require a good-position shot and progressive buildup. Cases spanning half time are rejected. Evidence includes its recorded threat indicators; confidence remains heuristic and counterevidence explicitly rejects causal certainty. Legacy event payloads retain the older count-based interpretation where richer geometry is unavailable.

## Remaining limitations

No off-ball tracking/22-player physical simulation, offside model, aerial height/spin, calibrated xG, fatigue, injuries, penalties, VAR, or added time. Defender proximity is tactical/heuristic, not a collision model. Save probabilities and tactical decisions are simplified, and deterministic rule-based cases are debate prompts rather than proven causal explanations. These limits are intentional; the new geometry is still explicitly synthetic.

## Validation

Backend invariants exercise multiple seeds for continuity, time ordering, active players, keeper roles, shot geometry, ownership, statistics and closed evidence windows. Frontend tests exercise continuous-clock barriers, interpolation, pause, seeking, reduced motion, hidden future results, and markers. Cross-stack tests run the real FastAPI app through TestClient and render its generated payloads in PitchStage; `npm test` therefore needs the backend dependencies available in the root `.venv` (or `python3`).
