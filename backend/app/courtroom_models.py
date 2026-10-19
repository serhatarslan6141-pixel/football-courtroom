"""Backend trial contract: recorded facts and AI interpretations stay separate."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class TrialPreparationRequest(StrictModel):
    through_timestamp: int = Field(ge=0, le=20000)


class TrialRequest(TrialPreparationRequest):
    allow_live: bool = False


class ObservedEvent(StrictModel):
    event_id: str
    timestamp: int
    clock: str
    event_type: str
    team_id: Optional[str]
    team_name: Optional[str]
    player_id: Optional[str]
    player_name: Optional[str]
    outcome: Optional[str]
    shot_quality: Optional[str]
    on_target: Optional[bool]
    player_in: Optional[str]
    player_out: Optional[str]


class RecordedFact(StrictModel):
    fact_id: str
    label: str
    value: str
    event_ids: list[str]


class VerifiedEvidence(StrictModel):
    source: Literal['verified_synthetic_match'] = 'verified_synthetic_match'
    match_id: str
    case_id: str
    seed: int
    allegation: str
    case_type: str
    incident_timestamp: int
    evidence_start: int
    evidence_cutoff: int
    trigger_event_ids: list[str]
    events: list[ObservedEvent]
    facts: list[RecordedFact]
    limitations: list[str]
    evidence_version: str


class FactAssertion(StrictModel):
    """Value must match a server-computed fact byte for byte."""
    fact_id: str
    value: str


class GroundedPoint(StrictModel):
    interpretation: str = Field(min_length=8, max_length=600)
    fact_ids: list[str] = Field(min_length=1, max_length=8)
    event_ids: list[str] = Field(min_length=1, max_length=12)


class EvidenceSubmission(StrictModel):
    observations: list[FactAssertion] = Field(min_length=1, max_length=8)
    event_ids: list[str] = Field(min_length=1, max_length=20)
    interpretation: GroundedPoint
    uncertainty: str = Field(min_length=12, max_length=500)


class EvidenceSelection(StrictModel):
    """Private model task: prioritize existing facts, never reconstruct records."""
    fact_ids: list[str] = Field(min_length=1, max_length=3)
    explanation: str = Field(min_length=8, max_length=240)
    uncertainty: str = Field(min_length=12, max_length=180)


class Argument(StrictModel):
    stance: Literal['support', 'challenge']
    points: list[GroundedPoint] = Field(min_length=1, max_length=3)
    uncertainty: str = Field(min_length=12, max_length=500)


class Ruling(StrictModel):
    result: Literal['prosecution_supported', 'defense_supported', 'inconclusive']
    findings: list[GroundedPoint] = Field(min_length=1, max_length=3)
    prosecution_assessment: str = Field(min_length=12, max_length=500)
    defense_assessment: str = Field(min_length=12, max_length=500)
    confidence: Literal['low', 'medium']
    uncertainty: str = Field(min_length=12, max_length=500)
    causation_established: Literal[False]
    counterfactual_outcome: Literal['unknown']


class AgentTrace(StrictModel):
    agent: Literal['evidence', 'prosecution', 'defense', 'judge']
    status: Literal['completed', 'failed']
    handoff_to: Optional[str]
    input_digest: str
    output_digest: Optional[str]
    error_category: Optional[str]


class TrialResult(StrictModel):
    source: Literal['live_ai', 'cached_ai', 'deterministic_fallback']
    disclosure: str
    evidence: VerifiedEvidence
    evidence_agent: Optional[EvidenceSubmission]
    prosecution: Argument
    defense: Argument
    judge: Ruling
    trace: list[AgentTrace]
    api_attempts: int
    original_api_attempts: int
    error_category: Optional[str]
    http_status: Optional[int]
    cache_key: Optional[str]
    configuration_version: str


class TrialPreparation(StrictModel):
    status: Literal['ready', 'confirmation_required']
    result: Optional[TrialResult] = None
