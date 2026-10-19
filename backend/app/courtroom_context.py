"""Role-scoped model context and deterministic, validated Evidence assembly."""
from .courtroom_models import EvidenceSelection, EvidenceSubmission
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


def assemble_evidence(selection, evidence):
    """Exact lookup, not repair: unknown IDs are rejected before construction."""
    selection = EvidenceSelection.model_validate(selection)
    facts = {fact.fact_id: fact for fact in evidence.facts}
    unknown = set(selection.fact_ids) - facts.keys()
    if unknown:
        event_ids = {event.event_id for event in evidence.events}
        raise InvalidAgentOutput('unknown_fact_reference', field='selection.fact_ids',
            reference_kind='event_id' if unknown <= event_ids else 'unknown')
    if len(set(selection.fact_ids)) != len(selection.fact_ids):
        raise InvalidAgentOutput('duplicate_fact_reference', field='selection.fact_ids')
    selected = [facts[fact_id] for fact_id in selection.fact_ids]
    # First reference from each selected nonempty fact, then remaining support
    # in catalog order. This is an explicit bounded citation sample, not a new
    # fact or a claim that these are all supporting events.
    support = list(dict.fromkeys([*(fact.event_ids[0] for fact in selected if fact.event_ids),
                                  *(event_id for fact in selected for event_id in fact.event_ids)]))
    if not support:
        raise InvalidAgentOutput('missing_fact_support', field='selection.fact_ids')
    if not set(support) <= {event.event_id for event in evidence.events}:
        raise InvalidAgentOutput('unknown_event_reference')
    citations = support[:12]
    result = EvidenceSubmission(
        observations=[{'fact_id': fact.fact_id, 'value': fact.value} for fact in selected],
        event_ids=list(dict.fromkeys([*evidence.trigger_event_ids, *citations])),
        interpretation={'fact_ids': selection.fact_ids, 'event_ids': citations,
                        'interpretation': selection.explanation},
        uncertainty=selection.uncertainty)
    validate_submission('evidence', result, evidence)
    return result
