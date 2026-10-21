"""Role-scoped context and deterministic citations for validated submissions."""
from .courtroom_models import (Argument, ArgumentSelection, EvidenceSelection,
                              EvidenceSubmission, Ruling, RulingSelection)
from .courtroom_evidence import InvalidAgentOutput, validate_submission


def evidence_selection_context(evidence):
    """Complete verified fact catalog; backing event references stay in Python.

    Selection/explanation needs every fact's identity, meaning and value, plus
    the complete trigger record and cutoff. It does not need to regenerate or
    audit a replay catalog. The immutable canonical file remains authoritative.
    """
    context = evidence.model_dump(exclude={'events', 'facts'})
    context['facts'] = [fact.model_dump(exclude={'event_ids'}) for fact in evidence.facts]
    context['trigger_events'] = [event.model_dump(exclude_none=True) for event in evidence.events
                                 if event.event_id in evidence.trigger_event_ids]
    context['context_scope'] = 'Complete verified fact catalog and incident records; supporting references are assembled by the backend.'
    return context


def compact_evidence_context(evidence):
    """Lossless downstream view: share support lists; omit only null fields."""
    context = evidence.model_dump(exclude={'events', 'facts'})
    groups, indexes, facts = {}, {}, []
    for fact in evidence.facts:
        support = tuple(fact.event_ids)
        if support not in indexes:
            name = f'support_{len(indexes)}'
            indexes[support] = name
            groups[name] = list(support)
        facts.append({**fact.model_dump(exclude={'event_ids'}), 'support_group': indexes[support]})
    context.update(facts=facts, support_groups=groups,
                   events=[event.model_dump(exclude_none=True) for event in evidence.events])
    return context


def agent_payload(role, evidence, prior_submissions):
    return {'evidence': evidence_selection_context(evidence) if role == 'evidence'
            else compact_evidence_context(evidence), 'prior_submissions': prior_submissions}


def _selected_facts(fact_ids, evidence, field):
    """Exact lookup only; never repair or substitute a model reference."""
    facts = {fact.fact_id: fact for fact in evidence.facts}
    unknown = set(fact_ids) - facts.keys()
    if unknown:
        event_ids = {event.event_id for event in evidence.events}
        raise InvalidAgentOutput('unknown_fact_reference', field=field,
            reference_kind='event_id' if unknown <= event_ids else 'unknown')
    if len(set(fact_ids)) != len(fact_ids):
        raise InvalidAgentOutput('duplicate_fact_reference', field=field)
    return [facts[fact_id] for fact_id in fact_ids]


def _support_citations(selected, evidence, field):
    # First reference from each selected nonempty fact, then remaining support
    # in catalog order. This is an explicit bounded citation sample, not a new
    # fact or a claim that these are all supporting events.
    support = list(dict.fromkeys([*(fact.event_ids[0] for fact in selected if fact.event_ids),
                                  *(event_id for fact in selected for event_id in fact.event_ids)]))
    if not support:
        raise InvalidAgentOutput('missing_fact_support', field=field)
    if not set(support) <= {event.event_id for event in evidence.events}:
        raise InvalidAgentOutput('unknown_event_reference')
    return support[:12]


def assemble_evidence(selection, evidence):
    """Construct public records only after validating the private selection."""
    selection = EvidenceSelection.model_validate(selection)
    selected = _selected_facts(selection.fact_ids, evidence, 'selection.fact_ids')
    citations = _support_citations(selected, evidence, 'selection.fact_ids')
    result = EvidenceSubmission(
        observations=[{'fact_id': fact.fact_id, 'value': fact.value} for fact in selected],
        event_ids=list(dict.fromkeys([*evidence.trigger_event_ids, *citations])),
        interpretation={'fact_ids': selection.fact_ids, 'event_ids': citations,
                        'interpretation': selection.explanation},
        uncertainty=selection.uncertainty)
    validate_submission('evidence', result, evidence)
    return result


def assemble_reasoning(role, selection, evidence):
    """Keep model reasoning; construct fact-supported citations deterministically.

    The private schema forbids event_ids. Supplying an unsupported event is a
    schema error, never an instruction to silently replace it with a valid one.
    """
    if role not in ('prosecution', 'defense', 'judge'):
        raise InvalidAgentOutput('wrong_submission_type')
    private = RulingSelection if role == 'judge' else ArgumentSelection
    selection = private.model_validate(selection)
    key = 'findings' if role == 'judge' else 'points'
    points = []
    for point in getattr(selection, key):
        field = f'{key}[].fact_ids'
        selected = _selected_facts(point.fact_ids, evidence, field)
        points.append({**point.model_dump(), 'event_ids': _support_citations(selected, evidence, field)})
    public = Ruling if role == 'judge' else Argument
    result = public.model_validate({**selection.model_dump(), key: points})
    validate_submission(role, result, evidence)
    return result
