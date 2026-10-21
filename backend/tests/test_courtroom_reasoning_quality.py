"""Offline prompt contracts and full-chain acceptance, not live model evaluations."""
import asyncio

import httpx
import pytest

from app import courtroom
from app.courtroom_evidence import build_evidence, validate_submission
from app.courtroom_workflow import CASE_CRITERIA, ROLE_INSTRUCTIONS
from app.synthetic_match import get_match
from test_courtroom import MockWire, enabled, isolated, assert_azure_evidence_schema, user_payload


CASES = [
    ('missed_opportunity', 'synthetic-303-missed_opportunity-home-1082', 1172),
    ('momentum_shift', 'synthetic-303-momentum_shift-home-583', 763),
    ('substitution_impact', 'synthetic-303-substitution_impact-away-4187', 4397),
]

WRITING = {
    'missed_opportunity': (
        'The buildup gives context to the good-quality shot that went wide.',
        'The home attack created a good chance and failed to finish it; that supports a significant missed opportunity.',
        'The shot quality supports significance, but the record cannot settle how difficult the finish was.',
        'The record does not show the defender distance.',
    ),
    'momentum_shift': (
        'The attacking threat comparison frames whether the home side took control.',
        'The home attacking threat and forward moves support a meaningful change in control.',
        'A longer observation window can inflate volume without showing a sustained swing in control.',
        'The short window limits how long this pattern can be expected to last.',
    ),
    'substitution_impact': (
        'The attacking activity around the substitution frames the change in rhythm.',
        'The attacking pattern following the substitution supports a change in rhythm.',
        'The switch may coincide with the change; its timing does not settle who drove the improvement.',
        'The record cannot isolate the incoming player from the wider team pattern.',
    ),
}


@pytest.mark.parametrize('case_type,case_id,cutoff', CASES)
@pytest.mark.parametrize('verdict', ['prosecution_supported', 'defense_supported', 'inconclusive'])
def test_case_specific_criteria_reach_every_agent_without_forcing_a_ruling(
        enabled, tmp_path, case_type, case_id, cutoff, verdict):
    match = get_match('synthetic-303')
    evidence = build_evidence(match, case_id, cutoff)
    original = evidence.model_dump_json()
    wire = MockWire(evidence)
    explanation, prosecution, defense, gap = WRITING[case_type]
    selected = [next(f for f in evidence.facts if f.fact_id.startswith('trigger:')),
                next(f for f in evidence.facts if f.fact_id == 'window:0:home:threats'),
                next(f for f in evidence.facts if f.fact_id == 'window:1:home:threats')]
    wire.outputs['evidence'].update(fact_ids=[f.fact_id for f in selected],
        explanation=explanation, uncertainty=gap)
    wire.outputs['prosecution']['points'][0].update(interpretation=prosecution,
        fact_ids=[f.fact_id for f in selected])
    wire.outputs['prosecution']['uncertainty'] = 'The selected pattern leaves some detail of the incident unresolved.'
    wire.outputs['defense']['points'][0].update(interpretation=defense,
        fact_ids=[f.fact_id for f in selected])
    wire.outputs['defense']['uncertainty'] = 'The prosecution still identifies a relevant pattern in this window.'
    judge = wire.outputs['judge']
    judge.update(result=verdict, uncertainty=gap,
        prosecution_assessment='The prosecution connects the allegation to the selected attacking record.',
        defense_assessment='The defense identifies a specific limit in the strength of that inference.')
    # Outputs are controlled examples. These tests prove all verdicts remain
    # possible without a causal/counterfactual claim, not which a model chooses.
    judge['findings'][0].update(interpretation={
        'prosecution_supported': 'The attacking record makes the allegation the better-supported reading.',
        'defense_supported': 'The rebuttal exposes a gap that undermines the allegation as framed.',
        'inconclusive': 'The supporting pattern and its limits leave the competing readings balanced.',
    }[verdict], fact_ids=[f.fact_id for f in selected])
    service = courtroom.TrialService(courtroom.TrialCache(tmp_path / 'cache'),
        courtroom.DailyRequestBudget(tmp_path / 'usage'), httpx.MockTransport(wire.handle))
    result = asyncio.run(service.analyze(match, case_id, cutoff, allow_live=True))
    assert result.source == 'live_ai' and result.api_attempts == 4
    assert result.judge.result == verdict and result.judge.causation_established is False
    assert result.judge.counterfactual_outcome == 'unknown'
    assert len(result.evidence_agent.observations) == 3
    for index, (role, body) in enumerate(wire.calls):
        instructions = body['instructions']
        assert f'CASE CRITERIA ({case_type}):\n{CASE_CRITERIA[case_type]}' in instructions
        assert ROLE_INSTRUCTIONS[role] in instructions
        assert 'Alternative explanations remain plausible' not in instructions
        assert body['max_output_tokens'] == courtroom.DEFAULT_AGENT_OUTPUT_TOKENS[role]
        assert_azure_evidence_schema(body['text']['format']['schema'])
        assert list(user_payload(body)['prior_submissions']) == list(courtroom.ROLES[:index])
        validate_submission(role, getattr(result, 'evidence_agent' if role == 'evidence' else role), evidence)
    assert [t.handoff_to for t in result.trace] == ['prosecution', 'defense', 'judge', None]
    assert evidence.model_dump_json() == original
    ledger = service.budget.path.read_bytes()
    cached = asyncio.run(service.prepare(match, case_id, cutoff))
    assert cached.source == 'cached_ai' and cached.api_attempts == 0
    assert len(wire.calls) == 4 and service.budget.path.read_bytes() == ledger


def test_judging_criteria_separate_observation_from_causation_and_missing_data():
    missed = CASE_CRITERIA['missed_opportunity']
    assert 'not whether taking it would have changed the match result' in missed
    assert 'lack of later pressure alone' in ROLE_INSTRUCTIONS['defense']
    assert 'unknown, not unopposed' in missed
    assert 'different window durations' in CASE_CRITERIA['momentum_shift']
    assert 'passing volume is not measured possession time' in CASE_CRITERIA['momentum_shift']
    assert 'unequal window' in CASE_CRITERIA['substitution_impact']
    assert 'Timing alone is not impact' in CASE_CRITERIA['substitution_impact']
    assert 'No result is preferred in advance' in ROLE_INSTRUCTIONS['judge']
    assert 'genuinely insufficient or balanced' in ROLE_INSTRUCTIONS['judge']
