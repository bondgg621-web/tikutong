from __future__ import annotations
from m2_helpers import UUIDSequence
from m3_helpers import bootstrap
from qbanswer.answer_parser import parse_answer_text
from qbanswer.association import issue_evidence_group,raw_associate
from qbanswer.source_snapshot import resolve_question_view

def _views(tmp_path):
    c=bootstrap(tmp_path);*_,views,_=resolve_question_view(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,expected_candidate_hash=c.candidate_hash);return c,views

def test_unique_answers_become_confirmable_and_missing_is_exact(tmp_path):
    c,views=_views(tmp_path);ev=[x.as_dict() for x in parse_answer_text('1: A\n',source_id=c.answer_source_id,source_revision=1,uuid_factory=UUIDSequence(1))]
    entries,sl=raw_associate(views,ev);assert [e['conclusion'] for e in entries]==['confirmable','missing'];assert sl==[]

def test_unknown_answer_number_is_source_level_low_confidence(tmp_path):
    c,views=_views(tmp_path);ev=[x.as_dict() for x in parse_answer_text('99: A\n',source_id=c.answer_source_id,source_revision=1,uuid_factory=UUIDSequence(1))]
    _,sl=raw_associate(views,ev);assert len(sl)==1 and sl[0]['candidate_id'] is None and sl[0]['question_number']==99 and sl[0]['evidence']

def test_invalid_label_and_different_options_are_conflicts(tmp_path):
    c,views=_views(tmp_path)
    for text in ('1: Z\n','1: A\n1: B\n'):
        ev=[x.as_dict() for x in parse_answer_text(text,source_id=c.answer_source_id,source_revision=1,uuid_factory=UUIDSequence(1))]
        entries,_=raw_associate(views,ev);assert entries[0]['conclusion']=='conflict'

def test_issue_group_nullable_option_orders_null_first():
    rows=[{'source_id':'s','question_number':1,'evidence_fingerprint':'b','resolved_option_id':'z'},{'source_id':'s','question_number':1,'evidence_fingerprint':'a','resolved_option_id':None}]
    g=issue_evidence_group(rows);assert g[0]['resolved_option_id'] is None

def test_p1_unchanged_rejected_conflict_is_adjudicated_in_prepare_and_valid_in_reverify(tmp_path):
    from m3_helpers import current_hash,proposal_entry
    from qbanswer.prepare import prepare
    from qbanswer.confirmation import confirm
    from qbanswer.reverify import reverify
    c=bootstrap(tmp_path,answer='answers-conflict.txt')
    p=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(92000))
    e=proposal_entry(p,'conflict');chosen=e['alternatives'][0]['evidence_ids']
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p['proposal']['proposal_run_id'],proposal_hash=p['proposal_hash'],request={'action':'choose_evidence','proposal_ids':[e['proposal_id']],'selected_evidence_ids':chosen},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(93000))
    p2=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(94000))
    assert any(x['conclusion']=='adjudicated' for x in p2['proposal']['entries'])
    rv=reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:03:00Z',uuid_factory=UUIDSequence(95000))
    assert rv['reverify']['results'][0]['result']=='valid' and rv['reverify']['results'][0]['current_conclusion']=='adjudicated'

def test_association_order_is_independent_of_evidence_input_order(tmp_path):
    c,views=_views(tmp_path)
    ev=[x.as_dict() for x in parse_answer_text('1: A\n1: A\n2: B\n',source_id=c.answer_source_id,source_revision=1,uuid_factory=UUIDSequence(200))]
    a,_=raw_associate(views,ev);b,_=raw_associate(views,list(reversed(ev)))
    def semantic(entries):
        return [(x['candidate_id'],x['question_number'],x['conclusion'],x['proposed_option_id'],[(e['source_id'],e['locator'],e['evidence_fingerprint']) for e in x['evidence']]) for x in entries]
    assert semantic(a)==semantic(b)

def _chosen_conflict_case(root,start):
    from m3_helpers import current_hash,proposal_entry
    from qbanswer.prepare import prepare
    from qbanswer.confirmation import confirm
    c=bootstrap(root,answer='answers-conflict.txt')
    p=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(start))
    e=proposal_entry(p,'conflict');chosen=e['alternatives'][0]['evidence_ids']; chosen_set=set(chosen)
    selected_label=next(x['source_lexeme'] for x in e['evidence'] if x['evidence_id'] in chosen_set)
    rejected_label=next(x['source_lexeme'] for x in e['evidence'] if x['evidence_id'] not in chosen_set)
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p['proposal']['proposal_run_id'],proposal_hash=p['proposal_hash'],request={'action':'choose_evidence','proposal_ids':[e['proposal_id']],'selected_evidence_ids':chosen},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(start+1000))
    return c,selected_label,rejected_label


def test_p1_selected_key_disappears_is_stale_in_prepare_and_reverify(tmp_path):
    from m3_helpers import current_hash,rewrite_answer_and_inventory
    from qbanswer.prepare import prepare
    from qbanswer.reverify import reverify
    # Prepare entry point.
    c,_,rejected=_chosen_conflict_case(tmp_path/'prepare',96000)
    rewrite_answer_and_inventory(c,f'1: {rejected}\n2: B\n',uuid_start=97000)
    p=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(98000))
    q1=next(x for x in p['proposal']['entries'] if x.get('question_number')==1)
    assert q1['conclusion']=='stale'
    # Reverify entry point from the same pre-change logical state.
    d,_,rejected2=_chosen_conflict_case(tmp_path/'reverify',99000)
    rewrite_answer_and_inventory(d,f'1: {rejected2}\n2: B\n',uuid_start=100000)
    rv=reverify(input_root=d.input_root,workspace_root=d.workspace_root,scope={'kind':'question_source','question_source_id':d.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=d.candidate_hash,expected_pointer=current_hash(d),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(101000))
    r=next(x for x in rv['reverify']['results'] if x['issue_code']=='QB-DECISION-STALE')
    assert r['result']=='needs_revalidation' and r['current_conclusion']=='conflict'


def test_p1_new_outside_rejected_key_is_conflict_in_prepare_and_reverify(tmp_path):
    from m3_helpers import current_hash,rewrite_answer_and_inventory
    from qbanswer.prepare import prepare
    from qbanswer.reverify import reverify
    c,selected,_=_chosen_conflict_case(tmp_path/'prepare',102000)
    rewrite_answer_and_inventory(c,f'1: {selected}\n1: C\n2: B\n',uuid_start=103000)
    p=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(104000))
    q1=next(x for x in p['proposal']['entries'] if x.get('question_number')==1)
    assert q1['conclusion']=='conflict'
    d,selected2,_=_chosen_conflict_case(tmp_path/'reverify',105000)
    rewrite_answer_and_inventory(d,f'1: {selected2}\n1: C\n2: B\n',uuid_start=106000)
    rv=reverify(input_root=d.input_root,workspace_root=d.workspace_root,scope={'kind':'question_source','question_source_id':d.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=d.candidate_hash,expected_pointer=current_hash(d),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(107000))
    r=next(x for x in rv['reverify']['results'] if x['issue_code']=='QB-ANSWER-CONFLICT')
    assert r['result']=='needs_revalidation' and r['current_conclusion']=='conflict'
