from __future__ import annotations
import json
from pathlib import Path
from m2_helpers import UUIDSequence,fixed_now
from m3_helpers import bootstrap,current_hash,proposal_entry,rewrite_answer_and_inventory
from qbanswer.prepare import prepare
from qbanswer.confirmation import confirm
from qbanswer.reverify import reverify


def test_clean_prepare_confirm_validated(tmp_path):
    c=bootstrap(tmp_path)
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(5000))
    assert pr['run']['status']=='needs_confirmation'
    assert current_hash(c)=='ABSENT'
    ids=[e['proposal_id'] for e in pr['proposal']['entries'] if e['conclusion']=='confirmable']
    co=confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(6000))
    assert co['run']['status']=='complete'
    ptr=json.loads((c.workspace_root/'state/answer-association/current.json').read_text())
    inter=json.loads((c.workspace_root/ptr['snapshot_path']/'interchange.json').read_text())
    assert [x['status'] for x in inter['candidates']['candidates']]==['validated','validated']
    assert len([d for d in inter['decisions']['decisions'] if d['status']=='valid'])==2


def test_reverify_stale_then_prepare_archive_stale(tmp_path):
    c=bootstrap(tmp_path)
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(5000))
    ids=[e['proposal_id'] for e in pr['proposal']['entries'] if e['conclusion']=='confirmable']
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(6000))
    before=current_hash(c)
    rewrite_answer_and_inventory(c,'2: B\n')
    rv=reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(7000))
    assert rv['run']['status']=='complete'
    assert any(x['result']=='needs_revalidation' for x in rv['reverify']['results'])
    p2=current_hash(c)
    pr2=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=p2,now=lambda:'2026-08-30T00:03:00Z',uuid_factory=UUIDSequence(8000))
    assert pr2['proposal']['confirmation_base']['kind']=='prepare_result'
    # A second prepare has no new canonical delta and therefore freezes the
    # already-stale binding directly against the current pointer.
    p3=current_hash(c)
    pr3=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=p3,now=lambda:'2026-08-30T00:03:30Z',uuid_factory=UUIDSequence(8500))
    assert pr3['proposal']['confirmation_base']=={'kind':'direct'}
    stale=[e for e in pr3['proposal']['entries'] if e['conclusion']=='stale'];assert stale
    e=stale[0]
    co=confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr3['proposal']['proposal_run_id'],proposal_hash=pr3['proposal_hash'],request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=p3,now=lambda:'2026-08-30T00:04:00Z',uuid_factory=UUIDSequence(9000))
    assert co['run']['status']=='complete'


def _rewrite_workspace_json(path,obj):
    from hashlib import sha256
    from qbanswer.artifacts import workspace_json_bytes
    raw=workspace_json_bytes(obj);path.write_bytes(raw);return sha256(raw).hexdigest()


def test_confirmation_semantic_tamper_rehashed_graph_is_rejected(tmp_path):
    """Direct hashes are not an authority for confirmation business semantics."""
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c=bootstrap(tmp_path)
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(15000))
    ids=[e['proposal_id'] for e in pr['proposal']['entries'] if e['conclusion']=='confirmable']
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(16000))
    ws=c.workspace_root;ptr_path=ws/'state/answer-association/current.json';ptr=json.loads(ptr_path.read_text())
    snap=ws/ptr['snapshot_path'];inter_path=snap/'interchange.json';inter=json.loads(inter_path.read_text())
    d=next(x for x in inter['decisions']['decisions'] if x['status']=='valid')
    cand=next(x for x in inter['candidates']['candidates'] if x['candidate_id']==d['candidate_id'])
    d['value']['resolved_option_ids']=[next(o['option_id'] for o in cand['options'] if o['option_id']!=d['value']['resolved_option_ids'][0])]
    inter_hash=_rewrite_workspace_json(inter_path,inter)
    commit_path=ws/ptr['commit_path'];commit=json.loads(commit_path.read_text());txid=commit['transaction_id']
    plan_path=ws/f'transactions/answer-association/{txid}/plan.json';plan=json.loads(plan_path.read_text());plan['interchange_hash']=inter_hash
    plan_hash=_rewrite_workspace_json(plan_path,plan)
    state_path=ws/f'transactions/answer-association/{txid}/state.json';state=json.loads(state_path.read_text());state['plan_hash']=plan_hash;_rewrite_workspace_json(state_path,state)
    commit['plan_hash']=plan_hash;commit['interchange_hash']=inter_hash;commit_hash=_rewrite_workspace_json(commit_path,commit)
    ptr['commit_hash']=commit_hash;_rewrite_workspace_json(ptr_path,ptr)
    import pytest
    with pytest.raises(Exception,match='confirmed Decision cannot be derived from proposal'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def _rehash_current_transaction_after_operation_change(case,*,operation_kind,operation_obj,mutate_provenance=None):
    """Attacker helper: rewrite artifact + every directly dependent canonical hash."""
    ws=case.workspace_root;ptr_path=ws/'state/answer-association/current.json';ptr=json.loads(ptr_path.read_text())
    commit_path=ws/ptr['commit_path'];commit=json.loads(commit_path.read_text());txid=commit['transaction_id']
    plan_path=ws/f'transactions/answer-association/{txid}/plan.json';plan=json.loads(plan_path.read_text())
    ref=next(x for x in plan['operation_artifacts'] if x['kind']==operation_kind);op_path=ws/ref['relative_path']
    op_hash=_rewrite_workspace_json(op_path,operation_obj);ref['content_hash']=op_hash
    prov_path=ws/ptr['snapshot_path']/'provenance.json';prov=json.loads(prov_path.read_text())
    if mutate_provenance is not None:mutate_provenance(prov,ref['relative_path'],op_hash)
    prov_hash=_rewrite_workspace_json(prov_path,prov);plan['provenance_hash']=prov_hash
    plan_hash=_rewrite_workspace_json(plan_path,plan)
    state_path=ws/f'transactions/answer-association/{txid}/state.json';state=json.loads(state_path.read_text());state['plan_hash']=plan_hash;_rewrite_workspace_json(state_path,state)
    commit['plan_hash']=plan_hash;commit['provenance_hash']=prov_hash;commit_hash=_rewrite_workspace_json(commit_path,commit)
    ptr['commit_hash']=commit_hash;_rewrite_workspace_json(ptr_path,ptr)
    return ref['relative_path'],op_hash


def _confirmed_case(case,*,start=20000):
    pr=prepare(input_root=case.input_root,workspace_root=case.workspace_root,question_source_id=case.question_source_id,answer_source_ids=[case.answer_source_id],expected_candidate_hash=case.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(start))
    ids=[e['proposal_id'] for e in pr['proposal']['entries'] if e['conclusion']=='confirmable']
    confirm(input_root=case.input_root,workspace_root=case.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=case.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(start+1000))


def test_reverify_required_set_tamper_rehashed_graph_is_rejected(tmp_path):
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c=bootstrap(tmp_path);_confirmed_case(c,start=22000)
    before=current_hash(c)
    reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(24000))
    ws=c.workspace_root;ptr=json.loads((ws/'state/answer-association/current.json').read_text());commit=json.loads((ws/ptr['commit_path']).read_text());plan=json.loads((ws/f"transactions/answer-association/{commit['transaction_id']}/plan.json").read_text())
    rv_ref=next(x for x in plan['operation_artifacts'] if x['kind']=='reverify');rv=json.loads((ws/rv_ref['relative_path']).read_text())
    removed=rv['required_decision_ids'].pop();rv['results']=[x for x in rv['results'] if x['decision_id']!=removed]
    def mutate(prov,path,new_hash):
        for link in prov['decision_links']:
            if link['decision_id']==removed:
                link['reverify_audits']=[a for a in link.get('reverify_audits',[]) if a.get('reverify_path')!=path]
            else:
                for a in link.get('reverify_audits',[]):
                    if a.get('reverify_path')==path:a['reverify_hash']=new_hash
        for a in prov['reverify_audits']:
            if a.get('reverify_path')==path:
                a['reverify_hash']=new_hash;a['decision_ids']=[x for x in a['decision_ids'] if x!=removed]
    _rehash_current_transaction_after_operation_change(c,operation_kind='reverify',operation_obj=rv,mutate_provenance=mutate)
    import pytest
    with pytest.raises(Exception,match='reverify required set changed'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_reverify_mapping_tamper_rehashed_graph_is_rejected(tmp_path):
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c=bootstrap(tmp_path);_confirmed_case(c,start=26000)
    # Advance the source revision while preserving the semantic answers.
    rewrite_answer_and_inventory(c,'1 : A\n2 : B\n',uuid_start=28000)
    before=current_hash(c)
    reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(29000))
    ws=c.workspace_root;ptr=json.loads((ws/'state/answer-association/current.json').read_text());commit=json.loads((ws/ptr['commit_path']).read_text());plan=json.loads((ws/f"transactions/answer-association/{commit['transaction_id']}/plan.json").read_text())
    rv_ref=next(x for x in plan['operation_artifacts'] if x['kind']=='reverify');rv=json.loads((ws/rv_ref['relative_path']).read_text())
    mapping=next(m for r in rv['results'] for m in r['mappings'] if m['current_instances'])
    mapping['current_instances'][0]['locator'] = 'line:101'
    def mutate(prov,path,new_hash):
        for link in prov['decision_links']:
            for a in link.get('reverify_audits',[]):
                if a.get('reverify_path')==path:a['reverify_hash']=new_hash
        for a in prov['reverify_audits']:
            if a.get('reverify_path')==path:a['reverify_hash']=new_hash
    _rehash_current_transaction_after_operation_change(c,operation_kind='reverify',operation_obj=rv,mutate_provenance=mutate)
    import pytest
    with pytest.raises(Exception,match='reverify evidence mapping is forged'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_reverify_source_set_shrink_rehashed_graph_is_rejected(tmp_path):
    from qbcore.cli import run_inventory
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c=bootstrap(tmp_path)
    # Add a second explicit answer source before M3 prepare.
    (c.input_root/'answers2.txt').write_text('1: A\n2: B\n',encoding='utf-8',newline='\n')
    run_inventory(input_root=c.input_root,workspace_root=c.workspace_root,now=fixed_now,uuid_factory=UUIDSequence(31000))
    reg=json.loads((c.workspace_root/'registry/sources.json').read_text())
    a2=next(x['source_id'] for x in reg['sources'] if x['current_relative_path']=='answers2.txt')
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id,a2],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(32000))
    ids=[e['proposal_id'] for e in pr['proposal']['entries'] if e['conclusion']=='confirmable']
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(33000))
    before=current_hash(c)
    reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(34000))
    ws=c.workspace_root;ptr=json.loads((ws/'state/answer-association/current.json').read_text());commit=json.loads((ws/ptr['commit_path']).read_text());plan=json.loads((ws/f"transactions/answer-association/{commit['transaction_id']}/plan.json").read_text())
    rv_ref=next(x for x in plan['operation_artifacts'] if x['kind']=='reverify');rv=json.loads((ws/rv_ref['relative_path']).read_text())
    removed=a2;rv['answer_source_ids']=[x for x in rv['answer_source_ids'] if x!=removed]
    for r in rv['results']:
        r['current_source_ids']=[x for x in r['current_source_ids'] if x!=removed]
        r['current_evidence']=[x for x in r['current_evidence'] if x['source_id']!=removed]
        r['current_semantic_keys']=[x for x in r['current_semantic_keys'] if x[0]!=removed]
        # Keep historical mappings for the removed source explicitly unavailable-looking.
        for m in r['mappings']:
            if m['historical_instance']['source_id']==removed:
                m['current_semantic_key']=None;m['current_instances']=[]
    def mutate(prov,path,new_hash):
        for link in prov['decision_links']:
            for a in link.get('reverify_audits',[]):
                if a.get('reverify_path')==path:
                    a['reverify_hash']=new_hash;a['source_revisions'].pop(removed,None)
        for a in prov['reverify_audits']:
            if a.get('reverify_path')==path:a['reverify_hash']=new_hash
    _rehash_current_transaction_after_operation_change(c,operation_kind='reverify',operation_obj=rv,mutate_provenance=mutate)
    import pytest
    with pytest.raises(Exception,match='reverify source set changed'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_archive_stale_new_stale_prepare_result_succeeds(tmp_path):
    c=bootstrap(tmp_path);_confirmed_case(c,start=70000)
    # Same answers, different bytes => registry revision advances.  Prepare has
    # no reverify audit, so both historical Decisions lose current proof.
    rewrite_answer_and_inventory(c,'1 : A\n2 : B\n',uuid_start=72000)
    before=current_hash(c)
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T01:00:00Z',uuid_factory=UUIDSequence(73000))
    assert pr['proposal']['confirmation_base']['kind']=='prepare_result'
    stale=[e for e in pr['proposal']['entries'] if e['conclusion']=='stale'];assert len(stale)==2
    after_prepare=current_hash(c);e=stale[0]
    out=confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=after_prepare,now=lambda:'2026-08-30T01:01:00Z',uuid_factory=UUIDSequence(74000))
    assert out['run']['status']=='complete'
    ptr=json.loads((c.workspace_root/'state/answer-association/current.json').read_text());inter=json.loads((c.workspace_root/ptr['snapshot_path']/'interchange.json').read_text())
    d=next(x for x in inter['decisions']['decisions'] if x['decision_id']==e['decision_id']);r=next(x for x in inter['review_queue']['review_items'] if x['review_id']==e['review_item_id']);cand=next(x for x in inter['candidates']['candidates'] if x['candidate_id']==e['candidate_id'])
    assert (d['status'],r['status'],cand['status'])==('archived','resolved','candidate')
    # The other stale issue is intentionally untouched.
    other=next(x for x in stale if x['proposal_id']!=e['proposal_id'])
    assert next(x for x in inter['review_queue']['review_items'] if x['review_id']==other['review_item_id'])['status']=='open'


def _direct_stale_setup(tmp_path,*,start=80000):
    c=bootstrap(tmp_path);_confirmed_case(c,start=start)
    rewrite_answer_and_inventory(c,'2: B\n',uuid_start=start+2000)
    before=current_hash(c)
    reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T02:00:00Z',uuid_factory=UUIDSequence(start+3000))
    p=current_hash(c)
    prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=p,now=lambda:'2026-08-30T02:01:00Z',uuid_factory=UUIDSequence(start+4000))
    p=current_hash(c)
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=p,now=lambda:'2026-08-30T02:02:00Z',uuid_factory=UUIDSequence(start+5000))
    assert pr['proposal']['confirmation_base']=={'kind':'direct'}
    stale=next(e for e in pr['proposal']['entries'] if e['conclusion']=='stale')
    return c,pr,stale,p


def _rewrite_direct_proposal(case,proposal):
    path=case.workspace_root/f"runs/answer-association/{proposal['proposal_run_id']}/proposal.json"
    return _rewrite_workspace_json(path,proposal)


def test_archive_stale_wrong_decision_id_fails_even_with_matching_proposal_hash(tmp_path):
    import copy,pytest
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=80000)
    ptr=json.loads((c.workspace_root/'state/answer-association/current.json').read_text());inter=json.loads((c.workspace_root/ptr['snapshot_path']/'interchange.json').read_text())
    other=next(d for d in inter['decisions']['decisions'] if d['decision_id']!=e['decision_id'])
    proposal=copy.deepcopy(pr['proposal']);next(x for x in proposal['entries'] if x['proposal_id']==e['proposal_id'])['decision_id']=other['decision_id'];ph=_rewrite_direct_proposal(c,proposal)
    with pytest.raises(Exception,match='stale Decision binding invalid'):
        confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=proposal['proposal_run_id'],proposal_hash=ph,request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=pointer,now=lambda:'2026-08-30T02:03:00Z',uuid_factory=UUIDSequence(86000))


def test_archive_stale_other_candidate_or_revision_fails(tmp_path):
    import copy,pytest
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=87000)
    ptr=json.loads((c.workspace_root/'state/answer-association/current.json').read_text());inter=json.loads((c.workspace_root/ptr['snapshot_path']/'interchange.json').read_text());other=next(x for x in inter['candidates']['candidates'] if x['candidate_id']!=e['candidate_id'])
    for mode in ('candidate','revision'):
        proposal=copy.deepcopy(pr['proposal']);x=next(x for x in proposal['entries'] if x['proposal_id']==e['proposal_id'])
        if mode=='candidate':x['candidate_id']=other['candidate_id'];x['candidate_revision']=other['candidate_revision']
        else:x['candidate_revision']+=1
        ph=_rewrite_direct_proposal(c,proposal)
        with pytest.raises(Exception,match='stale Candidate binding invalid'):
            confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=proposal['proposal_run_id'],proposal_hash=ph,request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=pointer,now=lambda:'2026-08-30T02:03:00Z',uuid_factory=UUIDSequence(93000 if mode=='candidate' else 94000))
        # Restore original proposal bytes before the next subcase.
        _rewrite_direct_proposal(c,pr['proposal'])


def test_archive_stale_non_stale_review_item_fails(tmp_path):
    import copy,pytest
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=95000)
    missing=next(x for x in pr['proposal']['entries'] if x['conclusion']=='missing')
    proposal=copy.deepcopy(pr['proposal']);next(x for x in proposal['entries'] if x['proposal_id']==e['proposal_id'])['review_item_id']=missing['review_item_id'];ph=_rewrite_direct_proposal(c,proposal)
    with pytest.raises(Exception,match='stale ReviewItem binding invalid'):
        confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=proposal['proposal_run_id'],proposal_hash=ph,request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=pointer,now=lambda:'2026-08-30T02:03:00Z',uuid_factory=UUIDSequence(101000))


def test_archive_stale_wrong_issue_key_fails(tmp_path):
    import copy,pytest
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=102000)
    proposal=copy.deepcopy(pr['proposal']);next(x for x in proposal['entries'] if x['proposal_id']==e['proposal_id'])['review_issue_key']='0'*64;ph=_rewrite_direct_proposal(c,proposal)
    with pytest.raises(Exception,match='stale provenance binding invalid|stale issue key cannot be recomputed'):
        confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=proposal['proposal_run_id'],proposal_hash=ph,request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=pointer,now=lambda:'2026-08-30T02:03:00Z',uuid_factory=UUIDSequence(108000))


def _direct_stale_objects(case, proposal, entry):
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    policy=validate_roots(case.input_root,case.workspace_root)
    _,verified=read_current_verified(policy)
    return verified['interchange'],verified['provenance']


def test_archive_stale_closed_review_item_is_rejected_by_binding_validator(tmp_path):
    """Resolved/archived stale ReviewItems are never valid archive_stale targets."""
    import copy,pytest
    from qbanswer.confirmation import _validate_archive_stale,ConfirmationError
    c,pr,e,_=_direct_stale_setup(tmp_path,start=109000)
    parent,prov=_direct_stale_objects(c,pr['proposal'],e)
    for status in ('resolved','archived'):
        bad=copy.deepcopy(parent)
        next(r for r in bad['review_queue']['review_items'] if r['review_id']==e['review_item_id'])['status']=status
        with pytest.raises(ConfirmationError,match='stale ReviewItem binding invalid'):
            _validate_archive_stale(proposal=pr['proposal'],entry=e,parent=bad,parent_prov=prov)


def test_archive_stale_archived_decision_is_rejected_by_binding_validator(tmp_path):
    import copy,pytest
    from qbanswer.confirmation import _validate_archive_stale,ConfirmationError
    c,pr,e,_=_direct_stale_setup(tmp_path,start=116000)
    parent,prov=_direct_stale_objects(c,pr['proposal'],e)
    bad=copy.deepcopy(parent)
    next(d for d in bad['decisions']['decisions'] if d['decision_id']==e['decision_id'])['status']='archived'
    with pytest.raises(ConfirmationError,match='stale Decision binding invalid'):
        _validate_archive_stale(proposal=pr['proposal'],entry=e,parent=bad,parent_prov=prov)


def test_archive_stale_intervening_snapshot_replay_fails(tmp_path):
    """A direct stale proposal cannot be replayed after any intervening child snapshot."""
    import pytest
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=123000)
    missing=next(x for x in pr['proposal']['entries'] if x['conclusion']=='missing')
    # retain_unresolved is intentionally audit-only but still publishes a child snapshot.
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'retain_unresolved','proposal_ids':[missing['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=pointer,now=lambda:'2026-08-30T03:00:00Z',uuid_factory=UUIDSequence(129000))
    new_pointer=current_hash(c);assert new_pointer!=pointer
    with pytest.raises(Exception,match='proposal direct base is stale'):
        confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=new_pointer,now=lambda:'2026-08-30T03:01:00Z',uuid_factory=UUIDSequence(130000))


def test_archive_stale_cannot_reference_other_conclusion(tmp_path):
    import pytest
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=131000)
    other=next(x for x in pr['proposal']['entries'] if x['conclusion']!='stale')
    with pytest.raises(Exception,match='archive_stale requires stale proposal'):
        confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'archive_stale','proposal_ids':[other['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=pointer,now=lambda:'2026-08-30T03:10:00Z',uuid_factory=UUIDSequence(137000))


def test_other_confirmation_actions_cannot_reference_stale(tmp_path):
    import pytest
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=138000)
    cases=[
        ('confirm',[]),
        ('confirm_all_unambiguous',[]),
        ('choose_evidence',['00000000-0000-4000-8000-000000000001']),
        ('reject',[]),
        ('reject_association',[]),
        ('retain_unresolved',[]),
    ]
    for idx,(action,selected) in enumerate(cases):
        with pytest.raises(Exception):
            confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':action,'proposal_ids':[e['proposal_id']],'selected_evidence_ids':selected},expected_candidate_hash=c.candidate_hash,expected_pointer=pointer,now=lambda:'2026-08-30T03:20:00Z',uuid_factory=UUIDSequence(145000+idx*100))


def test_archive_stale_child_extra_delta_rehashed_graph_is_rejected(tmp_path):
    """Even a fully rehashed child may not sneak an unrelated business change into archive_stale."""
    import pytest
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=146000)
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=pointer,now=lambda:'2026-08-30T03:30:00Z',uuid_factory=UUIDSequence(152000))
    ws=c.workspace_root;ptr_path=ws/'state/answer-association/current.json';ptr=json.loads(ptr_path.read_text())
    snap=ws/ptr['snapshot_path'];inter_path=snap/'interchange.json';inter=json.loads(inter_path.read_text())
    # Change an unrelated Candidate state and repair every direct hash dependency.
    unrelated=next(x for x in inter['candidates']['candidates'] if x['candidate_id']!=e['candidate_id'])
    unrelated['status']='candidate' if unrelated['status']=='validated' else 'validated'
    inter_hash=_rewrite_workspace_json(inter_path,inter)
    commit_path=ws/ptr['commit_path'];commit=json.loads(commit_path.read_text());txid=commit['transaction_id']
    plan_path=ws/f'transactions/answer-association/{txid}/plan.json';plan=json.loads(plan_path.read_text());plan['interchange_hash']=inter_hash
    plan_hash=_rewrite_workspace_json(plan_path,plan)
    state_path=ws/f'transactions/answer-association/{txid}/state.json';state=json.loads(state_path.read_text());state['plan_hash']=plan_hash;_rewrite_workspace_json(state_path,state)
    commit['plan_hash']=plan_hash;commit['interchange_hash']=inter_hash;commit_hash=_rewrite_workspace_json(commit_path,commit)
    ptr['commit_hash']=commit_hash;_rewrite_workspace_json(ptr_path,ptr)
    with pytest.raises(Exception,match='confirmation changed unrelated Candidate|validated gate failed|candidate status transition'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_archive_stale_schema_runtime_action_parity(tmp_path):
    """Stale entry shape and confirmation action shape agree across Schema/runtime."""
    import copy
    import jsonschema
    from pathlib import Path
    from qbanswer.contracts import validate_confirmation,validate_proposal,ContractError
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=160000)
    stale_schema=json.loads((Path('skills/curate-question-bank/schemas/m3/answer-association-proposal.schema.json')).read_text())
    confirmation_schema=json.loads((Path('skills/curate-question-bank/schemas/m3/answer-association-confirmation.schema.json')).read_text())
    jsonschema.Draft202012Validator.check_schema(stale_schema);jsonschema.Draft202012Validator.check_schema(confirmation_schema)
    jsonschema.validate(pr['proposal'],stale_schema);validate_proposal(pr['proposal'])
    # Stale answer-carrying fields are forbidden identically by Schema and runtime.
    for field,bad_value in [('decision_id',None),('review_item_id',None),('review_issue_key',None),('proposed_option_id','00000000-0000-4000-8000-000000000001'),('evidence',[{'x':1}])]:
        bad=copy.deepcopy(pr['proposal']);target=next(x for x in bad['entries'] if x['proposal_id']==e['proposal_id']);target[field]=bad_value
        schema_bad=False;runtime_bad=False
        try:jsonschema.validate(bad,stale_schema)
        except jsonschema.ValidationError:schema_bad=True
        try:validate_proposal(bad)
        except ContractError:runtime_bad=True
        assert schema_bad and runtime_bad,field
    base_confirmation={
        'schema_version':'1.0','confirmation_id':'00000000-0000-4000-8000-000000000101','proposal_run_id':pr['proposal']['proposal_run_id'],
        'proposal_path':f"runs/answer-association/{pr['proposal']['proposal_run_id']}/proposal.json",'proposal_hash':pr['proposal_hash'],
        'expected_candidate_hash':c.candidate_hash,'expected_current_pointer':pointer,
        'request':{'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},
        'considered_semantic_keys':[],'selected_semantic_keys':[],'rejected_semantic_keys':[],
        'result_transaction_id':'00000000-0000-4000-8000-000000000102','result_snapshot_id':'00000000-0000-4000-8000-000000000103','recorded_at':'2026-08-30T04:00:00Z'}
    jsonschema.validate(base_confirmation,confirmation_schema);validate_confirmation(base_confirmation)
    # Every non-choose action rejects selected evidence at the contract layer.
    bad=copy.deepcopy(base_confirmation);bad['request']['selected_evidence_ids']=['00000000-0000-4000-8000-000000000104']
    for validator in ('schema','runtime'):
        failed=False
        try:
            jsonschema.validate(bad,confirmation_schema) if validator=='schema' else validate_confirmation(bad)
        except (jsonschema.ValidationError,ContractError):failed=True
        assert failed,validator
    # choose_evidence requires one proposal and non-empty selected evidence in both layers.
    choose=copy.deepcopy(base_confirmation);choose['request']={'action':'choose_evidence','proposal_ids':[e['proposal_id']],'selected_evidence_ids':['00000000-0000-4000-8000-000000000104']}
    jsonschema.validate(choose,confirmation_schema);validate_confirmation(choose)
    choose['request']['selected_evidence_ids']=[]
    for validator in ('schema','runtime'):
        failed=False
        try:jsonschema.validate(choose,confirmation_schema) if validator=='schema' else validate_confirmation(choose)
        except (jsonschema.ValidationError,ContractError):failed=True
        assert failed,validator


def _rehash_current_provenance_only(case,mutator):
    ws=case.workspace_root;ptr_path=ws/'state/answer-association/current.json';ptr=json.loads(ptr_path.read_text())
    snap=ws/ptr['snapshot_path'];prov_path=snap/'provenance.json';prov=json.loads(prov_path.read_text());mutator(prov)
    prov_hash=_rewrite_workspace_json(prov_path,prov)
    commit_path=ws/ptr['commit_path'];commit=json.loads(commit_path.read_text());txid=commit['transaction_id']
    plan_path=ws/f'transactions/answer-association/{txid}/plan.json';plan=json.loads(plan_path.read_text());plan['provenance_hash']=prov_hash
    plan_hash=_rewrite_workspace_json(plan_path,plan)
    state_path=ws/f'transactions/answer-association/{txid}/state.json';state=json.loads(state_path.read_text());state['plan_hash']=plan_hash;_rewrite_workspace_json(state_path,state)
    commit['plan_hash']=plan_hash;commit['provenance_hash']=prov_hash;commit_hash=_rewrite_workspace_json(commit_path,commit)
    ptr['commit_hash']=commit_hash;_rewrite_workspace_json(ptr_path,ptr)


def _copy_detached(case,relative_path,new_name):
    from hashlib import sha256
    src=case.workspace_root/relative_path
    dst=case.workspace_root/'runs/answer-association/detached'/new_name
    dst.parent.mkdir(parents=True,exist_ok=True);raw=src.read_bytes();dst.write_bytes(raw)
    return dst.relative_to(case.workspace_root).as_posix(),sha256(raw).hexdigest()


def test_prepare_rehashed_graph_rejects_detached_valid_confirmation_audit(tmp_path):
    import copy,pytest
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c=bootstrap(tmp_path);_confirmed_case(c,start=170000)
    rewrite_answer_and_inventory(c,'1 : A\n2 : B\n',uuid_start=172000)
    before=current_hash(c)
    prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T05:00:00Z',uuid_factory=UUIDSequence(173000))
    ptr=json.loads((c.workspace_root/'state/answer-association/current.json').read_text());prov=json.loads((c.workspace_root/ptr['snapshot_path']/'provenance.json').read_text())
    original=prov['confirmation_audits'][0];new_path,new_hash=_copy_detached(c,original['confirmation_path'],'copied-confirmation.json')
    def mutate(p):
        extra=copy.deepcopy(original);extra['confirmation_path']=new_path;extra['confirmation_hash']=new_hash;p['confirmation_audits'].append(extra)
    _rehash_current_provenance_only(c,mutate)
    with pytest.raises(Exception,match='prepare appended unrelated provenance'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_reverify_rehashed_graph_rejects_detached_valid_confirmation_audit(tmp_path):
    import copy,pytest
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c=bootstrap(tmp_path);_confirmed_case(c,start=176000)
    rewrite_answer_and_inventory(c,'1 : A\n2 : B\n',uuid_start=178000)
    before=current_hash(c)
    reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T05:10:00Z',uuid_factory=UUIDSequence(179000))
    ptr=json.loads((c.workspace_root/'state/answer-association/current.json').read_text());prov=json.loads((c.workspace_root/ptr['snapshot_path']/'provenance.json').read_text())
    original=prov['confirmation_audits'][0];new_path,new_hash=_copy_detached(c,original['confirmation_path'],'copied-confirmation-2.json')
    def mutate(p):
        extra=copy.deepcopy(original);extra['confirmation_path']=new_path;extra['confirmation_hash']=new_hash;p['confirmation_audits'].append(extra)
    _rehash_current_provenance_only(c,mutate)
    with pytest.raises(Exception,match='reverify appended unrelated provenance'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_confirm_rehashed_graph_rejects_detached_valid_reverify_audit(tmp_path):
    import copy,pytest
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c,pr,e,pointer=_direct_stale_setup(tmp_path,start=182000)
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=pointer,now=lambda:'2026-08-30T05:20:00Z',uuid_factory=UUIDSequence(188000))
    ptr=json.loads((c.workspace_root/'state/answer-association/current.json').read_text());prov=json.loads((c.workspace_root/ptr['snapshot_path']/'provenance.json').read_text())
    original=prov['reverify_audits'][0];new_path,new_hash=_copy_detached(c,original['reverify_path'],'copied-reverify.json')
    def mutate(p):
        extra=copy.deepcopy(original);extra['reverify_path']=new_path;extra['reverify_hash']=new_hash;p['reverify_audits'].append(extra)
    _rehash_current_provenance_only(c,mutate)
    with pytest.raises(Exception,match='confirm appended unrelated provenance'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_reverify_forged_new_conflict_claimed_valid_rehashed_graph_is_rejected(tmp_path):
    """A reverify artifact cannot inject conflict facts while continuing to claim valid."""
    import copy,pytest
    from hashlib import sha256
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c=bootstrap(tmp_path);_confirmed_case(c,start=190000)
    rewrite_answer_and_inventory(c,'1 : A\n2 : B\n',uuid_start=192000)
    before=current_hash(c)
    reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T06:00:00Z',uuid_factory=UUIDSequence(193000))
    ws=c.workspace_root;ptr=json.loads((ws/'state/answer-association/current.json').read_text());commit=json.loads((ws/ptr['commit_path']).read_text());plan=json.loads((ws/f"transactions/answer-association/{commit['transaction_id']}/plan.json").read_text())
    rv_ref=next(x for x in plan['operation_artifacts'] if x['kind']=='reverify');rv=json.loads((ws/rv_ref['relative_path']).read_text())
    r=next(x for x in rv['results'] if x['result']=='valid');inter=json.loads((ws/ptr['snapshot_path']/'interchange.json').read_text());d=next(x for x in inter['decisions']['decisions'] if x['decision_id']==r['decision_id']);cand=next(x for x in inter['candidates']['candidates'] if x['candidate_id']==d['candidate_id'])
    current=d['value']['resolved_option_ids'][0];other=next(o['option_id'] for o in cand['options'] if o['option_id']!=current)
    number=r['current_evidence'][0]['question_number'];fake_fp=sha256(f"m3-answer-evidence-v1\0{number}\0Z".encode()).hexdigest()
    fake={'evidence_id':'00000000-0000-4000-8000-000000000777','source_id':r['current_source_ids'][0],'source_revision':next(x['revision'] for x in inter['manifest']['sources'] if x['source_id']==r['current_source_ids'][0]),'locator':'line:999','question_number':number,'source_lexeme':'Z','evidence_fingerprint':fake_fp,'resolved_option_id':other}
    r['current_evidence'].append(fake);r['current_semantic_keys'].append([fake['source_id'],number,fake_fp]);r['current_semantic_keys'].sort();r['current_conclusion']='conflict'
    # Keep the malicious claim itself at valid/no issue.
    assert r['result']=='valid' and r['issue_code'] is None
    def mutate(prov,path,new_hash):
        for link in prov['decision_links']:
            for a in link.get('reverify_audits',[]):
                if a.get('reverify_path')==path:a['reverify_hash']=new_hash
        for a in prov['reverify_audits']:
            if a.get('reverify_path')==path:a['reverify_hash']=new_hash
    _rehash_current_transaction_after_operation_change(c,operation_kind='reverify',operation_obj=rv,mutate_provenance=mutate)
    with pytest.raises(Exception,match='reverify result cannot be recomputed'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def _two_missing_prepare_setup(tmp_path,*,start):
    c=bootstrap(tmp_path);rewrite_answer_and_inventory(c,'',uuid_start=start)
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T07:00:00Z',uuid_factory=UUIDSequence(start+1000))
    assert [e['conclusion'] for e in pr['proposal']['entries']]==['missing','missing']
    return c,pr


def test_review_supersession_self_or_forward_rehashed_graph_is_rejected(tmp_path):
    import pytest
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c,_=_two_missing_prepare_setup(tmp_path,start=220000)
    def mutate(prov):
        first,second=prov['review_links'][:2];first['supersedes_review_id']=second['review_id']
    _rehash_current_provenance_only(c,mutate)
    with pytest.raises(Exception,match='review supersession does not target nearest same-key predecessor'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_review_supersession_different_key_rehashed_graph_is_rejected(tmp_path):
    import pytest
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c,_=_two_missing_prepare_setup(tmp_path,start=223000)
    def mutate(prov):
        first,second=prov['review_links'][:2];second['supersedes_review_id']=first['review_id']
    _rehash_current_provenance_only(c,mutate)
    with pytest.raises(Exception,match='review supersession does not target nearest same-key predecessor'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_review_supersession_open_same_key_predecessor_rehashed_graph_is_rejected(tmp_path):
    import pytest
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c,_=_two_missing_prepare_setup(tmp_path,start=226000)
    def mutate(prov):
        first,second=prov['review_links'][:2]
        second['review_issue_key']=first['review_issue_key'];second['supersedes_review_id']=first['review_id']
    _rehash_current_provenance_only(c,mutate)
    with pytest.raises(Exception,match='review supersession target is not closed'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))


def test_missing_resolution_then_true_recurrence_supersedes_nearest_closed_item(tmp_path):
    """A missing issue closes on confirmed evidence and later true recurrence gets a new ReviewItem."""
    c=bootstrap(tmp_path);rewrite_answer_and_inventory(c,'',uuid_start=240000)
    p0=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T08:00:00Z',uuid_factory=UUIDSequence(241000))
    old_missing={e['question_number']:e['review_item_id'] for e in p0['proposal']['entries'] if e['conclusion']=='missing'}
    assert len(old_missing)==2
    # Evidence appears; confirmable payloads remain review_item_id=null, but
    # confirmation recovers and resolves the historical missing links.
    rewrite_answer_and_inventory(c,'1: A\n2: B\n',uuid_start=242000)
    p1=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T08:01:00Z',uuid_factory=UUIDSequence(243000))
    assert all(e['review_item_id'] is None for e in p1['proposal']['entries'] if e['conclusion']=='confirmable')
    ids=[e['proposal_id'] for e in p1['proposal']['entries'] if e['conclusion']=='confirmable']
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p1['proposal']['proposal_run_id'],proposal_hash=p1['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T08:02:00Z',uuid_factory=UUIDSequence(244000))
    ptr=json.loads((c.workspace_root/'state/answer-association/current.json').read_text());inter=json.loads((c.workspace_root/ptr['snapshot_path']/'interchange.json').read_text())
    assert all(next(r for r in inter['review_queue']['review_items'] if r['review_id']==rid)['status']=='resolved' for rid in old_missing.values())
    # Evidence disappears.  Archive each stale Decision through a fresh proposal
    # because every archive publishes an intervening generation by design.
    rewrite_answer_and_inventory(c,'',uuid_start=245000)
    ps=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T08:03:00Z',uuid_factory=UUIDSequence(246000))
    while True:
        stale=[e for e in ps['proposal']['entries'] if e['conclusion']=='stale']
        if not stale:break
        e=stale[0];confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=ps['proposal']['proposal_run_id'],proposal_hash=ps['proposal_hash'],request={'action':'archive_stale','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T08:04:00Z',uuid_factory=UUIDSequence(247000+len(stale)*100))
        ps=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T08:05:00Z',uuid_factory=UUIDSequence(248000+len(stale)*100))
        if not any(x['conclusion']=='stale' for x in ps['proposal']['entries']):break
    # With no current Decision and the same answer-source identity, missing is a
    # true recurrence.  Each new link must supersede the original closed item.
    recur=ps if any(x['conclusion']=='missing' for x in ps['proposal']['entries']) else prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T08:06:00Z',uuid_factory=UUIDSequence(249000))
    missing=[e for e in recur['proposal']['entries'] if e['conclusion']=='missing'];assert len(missing)==2
    ptr=json.loads((c.workspace_root/'state/answer-association/current.json').read_text());prov=json.loads((c.workspace_root/ptr['snapshot_path']/'provenance.json').read_text())
    for e in missing:
        assert e['review_item_id']!=old_missing[e['question_number']]
        link=next(x for x in prov['review_links'] if x['review_id']==e['review_item_id'])
        assert link['supersedes_review_id']==old_missing[e['question_number']]


def test_all_published_m3_artifacts_match_jsonschema_and_stdlib_contracts(tmp_path):
    """Published artifacts must satisfy both frozen JSON Schema and runtime contracts."""
    import copy
    import jsonschema
    from qbanswer.contracts import (
        ContractError,validate_commit,validate_confirmation,validate_plan,validate_pointer,
        validate_proposal,validate_provenance,validate_reverify,validate_run,validate_state,
    )
    c=bootstrap(tmp_path)
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T11:00:00Z',uuid_factory=UUIDSequence(250000))
    ids=[e['proposal_id'] for e in pr['proposal']['entries'] if e['conclusion']=='confirmable']
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T11:01:00Z',uuid_factory=UUIDSequence(251000))
    rewrite_answer_and_inventory(c,'2: B\n',uuid_start=252000)
    reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T11:02:00Z',uuid_factory=UUIDSequence(253000))

    schema_root=Path(__file__).resolve().parents[1]/'skills/curate-question-bank/schemas/m3'
    schemas={p.name:json.loads(p.read_text(encoding='utf-8')) for p in schema_root.glob('*.schema.json')}
    for schema in schemas.values():jsonschema.Draft202012Validator.check_schema(schema)

    samples=[]
    def check(path,schema_name,validator):
        value=json.loads(path.read_text(encoding='utf-8'))
        jsonschema.validate(value,schemas[schema_name]);validator(value);samples.append((value,schema_name,validator))
    for p in sorted((c.workspace_root/'runs/answer-association').glob('*/proposal.json')):check(p,'answer-association-proposal.schema.json',validate_proposal)
    for p in sorted((c.workspace_root/'runs/answer-association').glob('*/confirmation.json')):check(p,'answer-association-confirmation.schema.json',validate_confirmation)
    for p in sorted((c.workspace_root/'runs/answer-association').glob('*/reverify.json')):check(p,'answer-association-reverify.schema.json',validate_reverify)
    for p in sorted((c.workspace_root/'runs/answer-association').glob('*/run.json')):check(p,'answer-association-run.schema.json',validate_run)
    for p in sorted((c.workspace_root/'state/answer-association/snapshots').glob('*/provenance.json')):check(p,'answer-association-provenance.schema.json',validate_provenance)
    for p in sorted((c.workspace_root/'state/answer-association/snapshots').glob('*/parent-pointer.json')):check(p,'answer-association-pointer.schema.json',validate_pointer)
    check(c.workspace_root/'state/answer-association/current.json','answer-association-pointer.schema.json',validate_pointer)
    for p in sorted((c.workspace_root/'state/answer-association/transactions').glob('*/plan.json')):check(p,'answer-association-transaction.schema.json',validate_plan)
    for p in sorted((c.workspace_root/'state/answer-association/transactions').glob('*/state.json')):check(p,'answer-association-transaction.schema.json',validate_state)
    for p in sorted((c.workspace_root/'state/answer-association/transactions').glob('*/commit.json')):check(p,'answer-association-commit.schema.json',validate_commit)
    assert samples
    # Exact-shape parity: an unknown top-level field must fail both layers for
    # every artifact family represented by the real workflow.
    seen=set()
    for value,schema_name,validator in samples:
        key=(schema_name,validator.__name__)
        if key in seen:continue
        seen.add(key);bad=copy.deepcopy(value);bad['_unexpected']=True
        try:jsonschema.validate(bad,schemas[schema_name])
        except jsonschema.ValidationError:pass
        else:raise AssertionError(f'JSON Schema accepted extra field for {key}')
        try:validator(bad)
        except ContractError:pass
        else:raise AssertionError(f'runtime contract accepted extra field for {key}')


def _crash_prepare_case(tmp_path,monkeypatch,point,*,start):
    import importlib
    import pytest
    from qbanswer.transaction import TransactionError
    from qbanswer.service import recover as recover_service
    pm=importlib.import_module('qbanswer.prepare')
    c=bootstrap(tmp_path);rewrite_answer_and_inventory(c,'',uuid_start=start)
    real=pm.publish_transaction
    if point=='A':
        def crashy(**kwargs):raise KeyboardInterrupt('crash A before plan')
    else:
        inject={'B':'staged','C':'publishing','D':'pointer','E':'complete'}[point]
        def crashy(**kwargs):
            try:return real(**kwargs,crash_after=inject)
            except TransactionError as exc:raise KeyboardInterrupt(f'crash {point}') from exc
    monkeypatch.setattr(pm,'publish_transaction',crashy)
    with pytest.raises(KeyboardInterrupt):
        prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T12:00:00Z',uuid_factory=UUIDSequence(start+1000))
    monkeypatch.setattr(pm,'publish_transaction',real)
    before=current_hash(c)
    recovered=recover_service(input_root=c.input_root,workspace_root=c.workspace_root,now=lambda:'2026-08-30T12:01:00Z')
    runs=list((c.workspace_root/'runs/answer-association').glob('*/run.json'));assert len(runs)==1
    run=json.loads(runs[0].read_text(encoding='utf-8'))
    return c,before,recovered,run


def test_crash_points_a_to_e_recover_to_unique_frozen_outcome(tmp_path,monkeypatch):
    import pytest
    for offset,point in enumerate('ABCDE'):
        root=tmp_path/point;root.mkdir()
        c,before,recovered,run=_crash_prepare_case(root,monkeypatch,point,start=260000+offset*10000)
        snapshots=list((c.workspace_root/'state/answer-association/snapshots').glob('*')) if (c.workspace_root/'state/answer-association/snapshots').exists() else []
        plans=list((c.workspace_root/'transactions/answer-association').glob('*/plan.json')) if (c.workspace_root/'transactions/answer-association').exists() else []
        if point=='A':
            assert before=='ABSENT' and current_hash(c)=='ABSENT'
            assert plans==[] and snapshots==[]
            assert run['status']=='failed' and run['result'] is None
        else:
            assert current_hash(c)!='ABSENT'
            assert len(plans)==1 and len(snapshots)==1
            state=json.loads(next((c.workspace_root/'transactions/answer-association').glob('*/state.json')).read_text(encoding='utf-8'))
            assert state['status']=='complete'
            assert run['status']=='needs_review' and run['result'] is not None
            assert len(recovered)>=1


def test_crash_e_with_missing_run_rebuilds_audit_only(tmp_path,monkeypatch):
    import importlib,pytest
    from qbanswer.transaction import TransactionError
    from qbanswer.service import recover as recover_service
    pm=importlib.import_module('qbanswer.prepare');c=bootstrap(tmp_path);rewrite_answer_and_inventory(c,'',uuid_start=320000);real=pm.publish_transaction
    def crashy(**kwargs):
        try:return real(**kwargs,crash_after='complete')
        except TransactionError as exc:raise KeyboardInterrupt('crash E') from exc
    monkeypatch.setattr(pm,'publish_transaction',crashy)
    with pytest.raises(KeyboardInterrupt):prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T12:10:00Z',uuid_factory=UUIDSequence(321000))
    monkeypatch.setattr(pm,'publish_transaction',real)
    pointer_before=current_hash(c);snapshots_before=sorted(p.name for p in (c.workspace_root/'state/answer-association/snapshots').iterdir())
    run_path=next((c.workspace_root/'runs/answer-association').glob('*/run.json'));run_path.unlink()
    recovered=recover_service(input_root=c.input_root,workspace_root=c.workspace_root,now=lambda:'2026-08-30T12:11:00Z')
    assert current_hash(c)==pointer_before
    assert sorted(p.name for p in (c.workspace_root/'state/answer-association/snapshots').iterdir())==snapshots_before
    rebuilt=json.loads(run_path.read_text(encoding='utf-8'));assert rebuilt['status']=='needs_review' and rebuilt['result'] is not None
    assert recovered


def _current_interchange(case):
    ptr=json.loads((case.workspace_root/'state/answer-association/current.json').read_text(encoding='utf-8'))
    return json.loads((case.workspace_root/ptr['snapshot_path']/'interchange.json').read_text(encoding='utf-8'))


def test_decision_matrix_same_option_same_evidence_reuses_decision(tmp_path):
    c=bootstrap(tmp_path);_confirmed_case(c,start=340000)
    before=_current_interchange(c);old={d['candidate_id']:d['decision_id'] for d in before['decisions']['decisions'] if d['status']=='valid'}
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T13:00:00Z',uuid_factory=UUIDSequence(342000))
    ids=[e['proposal_id'] for e in pr['proposal']['entries'] if e['conclusion']=='confirmable']
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T13:01:00Z',uuid_factory=UUIDSequence(343000))
    after=_current_interchange(c);live={d['candidate_id']:d['decision_id'] for d in after['decisions']['decisions'] if d['status']=='valid'}
    assert live==old
    assert len(after['decisions']['decisions'])==len(before['decisions']['decisions'])


def test_decision_matrix_same_option_new_evidence_archives_and_replaces(tmp_path):
    from qbcore.cli import run_inventory
    c=bootstrap(tmp_path);_confirmed_case(c,start=350000)
    before=_current_interchange(c);old={d['candidate_id']:d['decision_id'] for d in before['decisions']['decisions'] if d['status']=='valid'}
    (c.input_root/'answers2.txt').write_text('1: A\n2: B\n',encoding='utf-8',newline='\n')
    run_inventory(input_root=c.input_root,workspace_root=c.workspace_root,now=fixed_now,uuid_factory=UUIDSequence(352000))
    reg=json.loads((c.workspace_root/'registry/sources.json').read_text(encoding='utf-8'));a2=next(x['source_id'] for x in reg['sources'] if x['current_relative_path']=='answers2.txt')
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id,a2],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T13:10:00Z',uuid_factory=UUIDSequence(353000))
    ids=[e['proposal_id'] for e in pr['proposal']['entries'] if e['conclusion']=='confirmable'];assert len(ids)==2
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T13:11:00Z',uuid_factory=UUIDSequence(354000))
    after=_current_interchange(c);live={d['candidate_id']:d for d in after['decisions']['decisions'] if d['status']=='valid'}
    assert all(live[cid]['decision_id']!=did for cid,did in old.items())
    assert all(next(d for d in after['decisions']['decisions'] if d['decision_id']==did)['status']=='archived' for did in old.values())
    assert all(len(d['evidence'])==2 for d in live.values())


def test_decision_matrix_different_option_requires_conflict_choose_then_replace(tmp_path):
    c=bootstrap(tmp_path);_confirmed_case(c,start=360000);before=_current_interchange(c)
    q1=before['candidates']['candidates'][0]['candidate_id'];old=next(d for d in before['decisions']['decisions'] if d['candidate_id']==q1 and d['status']=='valid')['decision_id']
    rewrite_answer_and_inventory(c,'1: B\n2: B\n',uuid_start=362000)
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T13:20:00Z',uuid_factory=UUIDSequence(363000))
    conflict=next(e for e in pr['proposal']['entries'] if e['candidate_id']==q1 and e['conclusion']=='conflict');selected=[x['evidence_id'] for x in conflict['evidence']]
    mid=_current_interchange(c);assert next(d for d in mid['decisions']['decisions'] if d['decision_id']==old)['status']=='needs_revalidation'
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'choose_evidence','proposal_ids':[conflict['proposal_id']],'selected_evidence_ids':selected},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T13:21:00Z',uuid_factory=UUIDSequence(364000))
    after=_current_interchange(c);assert next(d for d in after['decisions']['decisions'] if d['decision_id']==old)['status']=='archived'
    live=[d for d in after['decisions']['decisions'] if d['candidate_id']==q1 and d['status']=='valid'];assert len(live)==1 and live[0]['decision_id']!=old


def test_decision_matrix_needs_revalidation_reconfirm_archives_old(tmp_path):
    c=bootstrap(tmp_path);_confirmed_case(c,start=370000);before=_current_interchange(c);q1=before['candidates']['candidates'][0]['candidate_id'];old=next(d for d in before['decisions']['decisions'] if d['candidate_id']==q1 and d['status']=='valid')['decision_id']
    rewrite_answer_and_inventory(c,'2: B\n',uuid_start=372000)
    prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T13:30:00Z',uuid_factory=UUIDSequence(373000))
    assert next(d for d in _current_interchange(c)['decisions']['decisions'] if d['decision_id']==old)['status']=='needs_revalidation'
    rewrite_answer_and_inventory(c,'1: A\n2: B\n',uuid_start=374000)
    pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T13:31:00Z',uuid_factory=UUIDSequence(375000))
    e=next(x for x in pr['proposal']['entries'] if x['candidate_id']==q1 and x['conclusion']=='confirmable')
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T13:32:00Z',uuid_factory=UUIDSequence(376000))
    after=_current_interchange(c);assert next(d for d in after['decisions']['decisions'] if d['decision_id']==old)['status']=='archived'
    live=[d for d in after['decisions']['decisions'] if d['candidate_id']==q1 and d['status']=='valid'];assert len(live)==1 and live[0]['decision_id']!=old

# Frozen Task-10 acceptance traceability.  Each ID maps to executable pytest
# nodes; case 29 intentionally maps to the 12 frozen archive_stale scenario nodes.
SPEC_ACCEPTANCE_NODES = {
  1:("tests/test_m3_source_snapshot.py::test_manifest_roles_are_explicit_and_registry_is_not_modified",),
  2:("tests/test_m3_source_snapshot.py::test_answer_source_selection_rejects_empty_or_duplicates","tests/test_m2_source_resolution.py::test_project_and_registry_dataset_ids_must_match","tests/test_m2_source_resolution.py::test_stale_content_hash_requires_inventory_without_registry_update","tests/test_m2_source_resolution.py::test_tampered_unsafe_registry_paths_are_rejected","tests/test_m2_source_resolution.py::test_symlink_escape_is_rejected_where_supported","tests/test_m3_source_snapshot.py::test_question_identity_replay_and_candidate_hash_gate"),
  3:("tests/test_m3_answer_parser.py::test_strict_number_label_and_blank_lines","tests/test_m3_answer_parser.py::test_crlf_cr_lf_have_same_semantics_and_fingerprint","tests/test_m3_answer_parser.py::test_any_nonempty_invalid_line_fails_whole_source"),
  4:("tests/test_m3_answer_parser.py::test_fingerprint_ignores_locator_and_whitespace_but_not_number_or_label",),
  5:("tests/test_m3_source_snapshot.py::test_candidate_and_option_identity_replay_mismatch_have_distinct_issue_codes","tests/test_m3_prepare.py::test_identity_failures_leave_canonical_unchanged_and_emit_exact_structured_findings"),
  6:("tests/test_m3_prepare.py::test_clean_prepare_publishes_proposal_but_no_canonical_snapshot",),
  7:("tests/test_m3_association.py::test_unique_answers_become_confirmable_and_missing_is_exact","tests/test_m3_association.py::test_unknown_answer_number_is_source_level_low_confidence","tests/test_m3_association.py::test_invalid_label_and_different_options_are_conflicts","tests/test_m3_review.py::test_open_same_key_deduplicates_and_closed_recurrence_supersedes","tests/test_m3_end_to_end.py::test_missing_resolution_then_true_recurrence_supersedes_nearest_closed_item"),
  8:("tests/test_m3_association.py::test_association_order_is_independent_of_evidence_input_order",),
  9:("tests/test_m3_confirmation.py::test_confirm_all_unambiguous_promotes_only_with_proposal_evidence","tests/test_m3_confirmation.py::test_conflict_choose_evidence_uses_only_existing_evidence","tests/test_m3_end_to_end.py::test_archive_stale_new_stale_prepare_result_succeeds","tests/test_m3_end_to_end.py::test_reverify_stale_then_prepare_archive_stale"),
 10:("tests/test_m3_confirmation.py::test_confirmation_cannot_inject_option_or_free_text",),
 11:("tests/test_m3_confirmation.py::test_stale_proposal_replay_after_intervening_generation_fails","tests/test_m3_end_to_end.py::test_confirmation_semantic_tamper_rehashed_graph_is_rejected"),
 12:("tests/test_m3_end_to_end.py::test_decision_matrix_same_option_same_evidence_reuses_decision","tests/test_m3_end_to_end.py::test_decision_matrix_same_option_new_evidence_archives_and_replaces","tests/test_m3_end_to_end.py::test_decision_matrix_different_option_requires_conflict_choose_then_replace","tests/test_m3_end_to_end.py::test_decision_matrix_needs_revalidation_reconfirm_archives_old"),
 13:("tests/test_m3_state_graph.py::test_validated_gate_negative_matrix",),
 14:("tests/test_m3_state_graph.py::test_parent_candidate_semantics_are_immutable_except_status","tests/test_m3_end_to_end.py::test_clean_prepare_confirm_validated"),
 15:("tests/test_m3_reverify.py::test_question_source_reverify_covers_all_current_decisions","tests/test_m3_source_snapshot.py::test_manifest_absorbs_full_registry_path_history_suffix","tests/test_m3_end_to_end.py::test_reverify_source_set_shrink_rehashed_graph_is_rejected"),
 16:("tests/test_m3_association.py::test_p1_unchanged_rejected_conflict_is_adjudicated_in_prepare_and_valid_in_reverify","tests/test_m3_association.py::test_p1_selected_key_disappears_is_stale_in_prepare_and_reverify","tests/test_m3_association.py::test_p1_new_outside_rejected_key_is_conflict_in_prepare_and_reverify","tests/test_m3_end_to_end.py::test_reverify_forged_new_conflict_claimed_valid_rehashed_graph_is_rejected","tests/test_m3_end_to_end.py::test_reverify_cannot_self_assert_adjudicated_when_parent_has_no_adjudication"),
 17:("tests/test_m3_reverify.py::test_selected_evidence_disappears_causes_safe_downgrade_not_auto_recovery","tests/test_m3_end_to_end.py::test_reverify_stale_then_prepare_archive_stale"),
 18:("tests/test_m3_transaction.py::test_second_writer_lock_is_nonblocking","tests/test_m3_transaction.py::test_unknown_external_pointer_fails_closed"),
 19:("tests/test_m3_end_to_end.py::test_crash_points_a_to_e_recover_to_unique_frozen_outcome",),
 20:("tests/test_m3_end_to_end.py::test_crash_e_with_missing_run_rebuilds_audit_only","tests/test_m3_transaction.py::test_unknown_external_pointer_fails_closed","tests/test_m3_transaction.py::test_aborted_terminal_transaction_cannot_be_revived_when_staged_set_is_completable","tests/test_m3_transaction.py::test_complete_terminal_transaction_with_before_pointer_fails_closed_instead_of_republishing","tests/test_m3_run_audit.py::test_existing_success_terminal_run_revalidates_complete_transaction_claim","tests/test_m3_run_audit.py::test_existing_direct_prepare_success_run_revalidates_pointer_claim"),
 21:("tests/test_m3_contracts.py::test_all_eight_schemas_are_draft_2020_12_and_closed","tests/test_m3_contracts.py::test_frozen_json_vectors_are_exact_and_independent","tests/test_m3_contracts.py::test_run_schema_runtime_freeze_nonterminal_failed_direct_and_transaction_success_branches","tests/test_m3_contracts.py::test_run_schema_runtime_rejects_impossible_terminal_combinations","tests/test_m3_contracts.py::test_transaction_schema_runtime_pair_and_operation_artifact_whitelists_match","tests/test_m3_end_to_end.py::test_all_published_m3_artifacts_match_jsonschema_and_stdlib_contracts"),
 22:("tests/test_m3_end_to_end.py::test_confirmation_semantic_tamper_rehashed_graph_is_rejected","tests/test_m3_end_to_end.py::test_reverify_required_set_tamper_rehashed_graph_is_rejected","tests/test_m3_end_to_end.py::test_reverify_mapping_tamper_rehashed_graph_is_rejected","tests/test_m3_end_to_end.py::test_review_supersession_self_or_forward_rehashed_graph_is_rejected"),
 23:("tests/test_m3_privacy.py::test_prepare_never_modifies_explicit_input_tree","tests/test_m3_privacy.py::test_published_m3_artifacts_do_not_expose_paths_env_or_full_answer_lines"),
 24:("tests/test_m3_safeguards.py::test_m3_runtime_has_no_network_process_dynamic_exec_or_install_capability",),
 25:("tests/test_m3_scope_guard.py::test_approved_spec_plan_and_97_authorities_are_exact","tests/test_m3_scope_guard.py::test_repository_noncache_files_are_inside_frozen_physical_scope"),
 26:("tests/test_m3_portability.py::test_copied_skill_cli_runs_from_new_location_and_only_writes_explicit_workspace",),
 27:("tests/test_m3_safeguards.py::test_runtime_exposes_no_ui_scoring_generation_or_non_single_choice_adapter",),
 28:("tests/test_m3_scope_guard.py::test_two_full_gate_policy_is_frozen_in_approved_plan",),
 29:(
      "tests/test_m3_end_to_end.py::test_archive_stale_new_stale_prepare_result_succeeds",
      "tests/test_m3_end_to_end.py::test_reverify_stale_then_prepare_archive_stale",
      "tests/test_m3_end_to_end.py::test_archive_stale_wrong_decision_id_fails_even_with_matching_proposal_hash",
      "tests/test_m3_end_to_end.py::test_archive_stale_other_candidate_or_revision_fails",
      "tests/test_m3_end_to_end.py::test_archive_stale_non_stale_review_item_fails",
      "tests/test_m3_end_to_end.py::test_archive_stale_closed_review_item_is_rejected_by_binding_validator",
      "tests/test_m3_end_to_end.py::test_archive_stale_archived_decision_is_rejected_by_binding_validator",
      "tests/test_m3_end_to_end.py::test_archive_stale_intervening_snapshot_replay_fails",
      "tests/test_m3_end_to_end.py::test_archive_stale_cannot_reference_other_conclusion",
      "tests/test_m3_end_to_end.py::test_other_confirmation_actions_cannot_reference_stale",
      "tests/test_m3_end_to_end.py::test_archive_stale_child_extra_delta_rehashed_graph_is_rejected",
      "tests/test_m3_end_to_end.py::test_archive_stale_schema_runtime_action_parity",
  ),
}

def test_spec_acceptance_mapping_covers_exactly_1_to_29_and_all_nodes_exist():
    import ast
    assert set(SPEC_ACCEPTANCE_NODES)==set(range(1,30))
    assert len(SPEC_ACCEPTANCE_NODES[29])==12
    for case_id,nodes in SPEC_ACCEPTANCE_NODES.items():
        assert nodes,case_id
        for node in nodes:
            rel,func=node.split('::',1);path=Path(__file__).resolve().parents[1]/rel
            assert path.is_file(),node
            tree=ast.parse(path.read_text(encoding='utf-8'))
            names={x.name for x in tree.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
            assert func in names,node


def test_reverify_cannot_self_assert_adjudicated_when_parent_has_no_adjudication(tmp_path):
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c=bootstrap(tmp_path);_confirmed_case(c,start=130000)
    before=current_hash(c)
    reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(131000))
    ws=c.workspace_root;ptr=json.loads((ws/'state/answer-association/current.json').read_text());commit=json.loads((ws/ptr['commit_path']).read_text());plan=json.loads((ws/f"transactions/answer-association/{commit['transaction_id']}/plan.json").read_text())
    rv_ref=next(x for x in plan['operation_artifacts'] if x['kind']=='reverify');rv=json.loads((ws/rv_ref['relative_path']).read_text())
    assert all(r['current_conclusion']=='confirmable' for r in rv['results'])
    rv['results'][0]['current_conclusion']='adjudicated'
    def mutate(prov,path,new_hash):
        for link in prov['decision_links']:
            for a in link.get('reverify_audits',[]):
                if a.get('reverify_path')==path:a['reverify_hash']=new_hash
        for a in prov['reverify_audits']:
            if a.get('reverify_path')==path:a['reverify_hash']=new_hash
    _rehash_current_transaction_after_operation_change(c,operation_kind='reverify',operation_obj=rv,mutate_provenance=mutate)
    import pytest
    with pytest.raises(Exception,match='reverify current conclusion inconsistent'):
        read_current_verified(validate_roots(c.input_root,c.workspace_root))
