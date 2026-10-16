# Synthetic football simulation, v2 — Step 2.6

This is a reproducible, simplified football model, not tracking data or a prediction of real clubs. `generate_match(seed)` retains the three fictional fixtures and returns the same event log for the same seed and code version. Changing generator versions changes those logs.

## Possession and space

`PossessionSimulation` owns the match clock, ball position, controlling team/player, active XI, bench, score, period and possession sequence. Each recorded action starts at the previous action's recorded endpoint. It chooses its next action from this state, rather than placing unrelated events around the pitch.

Role anchors are approximate tactical positions used to choose recipients and defenders. They shift with territorial progress. Decisions now materialize explicit synthetic point-player snapshots, including all active opponents and the carrier at the ball; these are never presented as measured tracking. A pass records the snapshot at its first touch, before the recipient moves to the arrival point. Goalkeepers stay near their own goal and distribute to defenders. Most passes prefer nearby recipients; occasional longer distribution/switches and forward through balls have explicit context. Carries advance the current carrier rather than changing players arbitrarily. Interceptions, tackles and saves transfer control at the ball's actual location.

Coordinates remain in fixed stadium space: x/y are each 0–100. Distances assume a fictional 105 × 68 metre pitch. Home attacks toward x=100 in period 1 and x=0 in period 2; away does the opposite. Role lanes also reverse at half time. Shots originate in the attacking quarter from plausible lateral positions. `target` records the intended goal-line point; `end` records the actual endpoint, including the keeper's save location. Off-target shots can cross the goal line outside the posts.

There are seven separate reserves per club. Substitution events remove the outgoing player and activate a previously unused reserve in a compatible role group, inheriting the vacated tactical slot. Sent-off players stop participating. Substitution timing is probabilistic at stoppages, with a maximum of five changes per team; this is not a full competition-rules implementation.

## Timing and calibration

Touch/control, ball flight and carrying have different durations. Fast and slow possession tempos vary the touch times. Fouls, out-of-play balls, corners, goals and restarts consume longer recorded dead-ball spans. A `movement: reset` event explicitly relocates the ball for a restart; the frontend does not fabricate a live trajectory during that relocation.

The match normally has two 45-minute periods, finishing at 5400 elapsed match seconds. The real-world half-time break and general added time are excluded. The necessary time to complete an awarded penalty is an exception: that period extends, and the second period still lasts 2700 seconds. Consequently rare logs can exceed 5400 seconds. Period metadata and the actual half-time whistle, rather than a hardcoded 2700 cutoff, govern direction and case-window separation. Events are serialized, with instantaneous reactions sharing a completion timestamp. Positive-duration spans partition the match clock without overlapping.

Probabilities and distance weights are design assumptions, not fitted professional-player parameters. There are no pass, goal, shot or case quotas and no correction of results to hit a desired score. Changes to decisions and rules change the seeded logs. The older Step 2.5 sample is not a calibration target for this version. Outputs are not forced to contain every restart or case type; controlled scenarios exercise rare rules in tests.

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

New event types are `ball_control`, `carry`, `dribble`, `interception`, `recovery`, `clearance`, `miscontrol`, `stoppage`, `restart`, `restart_taken`, `boundary`, `offside`, and `deflection`. Previously declared crosses and saves are now generated as connected actions. Team/player metadata includes `is_starter` so reserves can be distinguished from the initial XI.

## Decisions and supported football rules

`football_decisions.py` contains pure geometry and a `DecisionTuning` dataclass. Shooting considers distance in metres, the angle between the posts, nearby pressure, blocked shooting lanes, role and possession phase. Central chances within 16 metres strongly favor a shot; close unpressured chances approach a 98% action probability. Impossible distance/angle combinations have zero shooting weight. A clearly better-placed teammate with a clear lane can reduce the shooting weight under pressure. Passing weights prefer nearby forward options, penalize blocked lanes, and strongly discourage receivers already offside. The selected action still uses the match's seeded RNG. Shot `decision_context` records the inputs; this is not xG or a learned player model.

The rules implement a deliberately bounded subset of the [IFAB Laws](https://www.theifab.com/laws/latest/):

| Mechanic | Supported decision and continuity |
| --- | --- |
| Ball out, [Law 9](https://www.theifab.com/laws/latest/the-ball-in-and-out-of-play/) | A raw `field_exit` proves the whole ball crossed, including an assumed 11 cm ball radius. Merely touching the line is not out. When a path can cross two boundaries, the first crossing determines the restart. Visible ball endpoints project to the field edge; no live relocation is fabricated. |
| [Throw-in](https://www.theifab.com/laws/latest/the-throw-in/) | Opponents of the last-touch team, at the touchline crossing; an eligible outfield taker, opponents at least 2 m away, then a pass into play to another player. Legal two-handed delivery/feet placement is assumed, not animated or adjudicated. No direct shot from a throw. |
| [Corner](https://www.theifab.com/laws/latest/the-corner-kick/) | Defender last touched before a non-goal goal-line exit; attacking side restarts at the corner on the exit side, opponents at least 9.15 m away, then a cross. Keeper parries have an explicit deflection path wide of the posts before a corner can be awarded. |
| [Goal kick](https://www.theifab.com/laws/latest/the-goal-kick/) | Attacker last touched before a non-goal goal-line exit; defending goalkeeper restarts inside the goal area, opponents outside the penalty area, then distribution. The low-dimensional exit helper can also distinguish a ground-level goal/own goal from a ball explicitly above the bar. |
| [Direct/indirect kicks](https://www.theifab.com/laws/latest/free-kicks/) | Trips, pushes, holding and contact tackles are direct offences; dangerous play and impeding **without contact** are indirect. Kicks use the offence spot, including the attacking IFK exception on the parallel goal-area line. Indirect kicks always pass to another player. |
| [Penalties](https://www.theifab.com/laws/latest/the-penalty-kick/) | Only an in-play direct-free-kick offence by the opposing defending team in its own penalty area, including its lines. An indirect offence in the box stays indirect. Setup relocates explicitly to the 11 m mark, keeper on the goal line, other players behind the mark/outside the box and arc. Recorded shot → goal/save/miss follows a setup pause. The period extends if required to complete the kick; no subsequent kickoff is forced after time expires. |
| [Cards](https://www.theifab.com/laws/latest/fouls-and-misconduct/) | Careless contact normally has no card; reckless contact is yellow; excessive force is direct red. A second yellow emits both the caution and dismissal. Dismissed players leave the active set immediately, cannot receive/act/restart/substitute back in, and do not return to the bench. Below seven players the match is abandoned. A conservative, recorded DOGSO subset uses controlled goalward movement, distance, central approach and covering opponents; penalty attempts to play/challenge for the ball are downgraded to yellow, while pushing/holding are not. Holding that demonstrably stops a progressing attack can be cautioned. |
| [Offside](https://www.theifab.com/laws/latest/offside/) | The intended receiver must be in the opponents' half and strictly beyond both the ball and **second-last actual opponent** in the release snapshot. Level is onside. Only a subsequent receiver touch triggers the offence; an intercepted ball does not. The IFK is at involvement, not the original offside position. Direct receipt of throw-ins, goal kicks and corners is exempt; subsequent ordinary passes are not. The evidence snapshot and offside line appear only after the call, explicitly labeled as simulated positions at pass release. |

Restarts record `restart`/`kickoff` as the **award and setup** (`restart_status: setup`, `movement: reset`, `setup_positions`), followed by a timed `stoppage`, then `restart_taken` and the first kick/throw. Setup immediately records the new team and eligible taker, so a pause displays the correct location and ownership. Substitutions occur before that setup snapshot. Possession time excludes the pause; only the ensuing in-play spans accrue time. The first action is a pass/cross or legal direct shot, preventing an immediate second touch by the taker. All generated restart deliveries are legal; encroachment, foul throws, delay countdowns and retakes are not sampled.

Additional metadata: `release_positions`, `offside_context`, `offence_location`, `foul_type`, `severity`, `dogso_context`, `stops_promising_attack`, `field_exit`, `whole_ball_crossed`, `last_touch_team`, `awarded_team`, and `boundary`. Existing schema version 2 and API routes remain compatible; there are no new dependencies or AI calls.

## Replay, statistics and cases

The shared reducer advances one continuous match clock from animation-frame elapsed time at the selected speed. The ball linearly interpolates only between a recorded action's endpoints over its recorded interval. It never joins unrelated locations or invents player tracking. The short trail is restricted to recent recorded possessions, with a brief failed-pass cue when control changes. Pause freezes the clock and geometry; seeking reconstructs it directly. Reduced motion holds at a recorded position until the next completion. Goal cues are clock-driven, not independent CSS animations.

Statistics, history, goal labels and timeline markers consume **completed** events only. An action in flight is exposed to the caption/pitch through a whitelist without its future outcome, recipient or result description. Only the already-traversed portion of its path is drawn. A shot finishing as a goal cannot update the score early.

`state.next_update_timestamp` marks the next completion or possible case-window boundary. Statistics and cases stay unchanged within that validity interval, so the frontend need not request them at animation-frame frequency. At the boundary it briefly holds until both API responses commit together. Stale requests are canceled/version-checked as before. Network latency can slightly slow playback at these boundaries. The SSE endpoint also uses recorded timestamp gaps divided by speed.

Passes include crosses; possession sums recorded in-play spans attributed to the controller (not the pressing opponent), excluding stoppages. Tackles, successful tackles, interceptions, recoveries, carries and clearances have separate counters. Pressure is no longer counted as an attacking entry, and the former pressure-duration double count is removed. No statistics are invented to smooth the display.

All three case types retain complete evidence-window eligibility. V2 substitution cases require the incoming player to participate and increased threat per unit time. Momentum cases need threat across multiple possessions and a shot, not just passing-volume spikes. Missed-opportunity cases require a good-position shot and progressive buildup. Cases spanning the recorded half-time whistle are rejected. Failed/offside passes do not count as progressive buildup. No new case types or unsupported review/VAR evidence are added. Evidence includes its recorded threat indicators; confidence remains heuristic and counterevidence explicitly rejects causal certainty. Legacy event payloads retain the older count-based interpretation where richer geometry is unavailable.

## Remaining limitations

No continuous off-ball tracking/22-player physical simulation, playable body-part extents, aerial height/spin simulation, calibrated xG, fatigue, injuries, handball/back-pass decisions, advantage, keeper handling-time sanctions, goalpost rebounds, retakes, or VAR. Player points are regenerated tactical approximations at decisions, not persistent athletic trajectories. Offside is limited to the intended receiver playing a direct pass; interference with opponents, rebounds, deliberate defender-play resets and off-field players are not adjudicated. DOGSO/SPA support is conservative and heuristic within the explicit point model, not a complete referee model. General added time and full competition substitution-window rules remain excluded. Save probabilities, defender proximity and tactical choices are tunable design assumptions. Courtroom cases remain debate prompts, not proven causal explanations.

## Validation

Backend invariants exercise multiple seeds for continuity, time ordering, active players, keeper roles, shot geometry, ownership, statistics and closed evidence windows. Frontend tests exercise continuous-clock barriers, interpolation, pause, seeking, reduced motion, hidden future results, and markers. Cross-stack tests run the real FastAPI app through TestClient and render its generated payloads in PitchStage; `npm test` therefore needs the backend dependencies available in the root `.venv` (or `python3`).
