from __future__ import annotations
import json
import pytest
from m2_helpers import UUIDSequence
from m3_helpers import bootstrap
from qbcore.paths import validate_roots
from qbanswer.prepare import prepare
from qbanswer.run_audit import RunAuditError,new_run,write_run

def test_direct_prepare_success_is_run_only_and_never_creates_empty_transaction(tmp_path):
    c=bootstrap(tmp_path);r=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(40000))
    assert r['run']['status']=='needs_confirmation';assert not (c.workspace_root/'state/answer-association/transactions').exists()

def test_terminal_run_is_immutable(tmp_path):
    c=bootstrap(tmp_path);p=validate_roots(c.input_root,c.workspace_root);run=new_run(run_id='00000000-0000-4000-8000-000000000001',operation='prepare',now=lambda:'2026-08-30T00:00:00Z');run['status']='failed';run['phase']='complete';run['updated_at']='2026-08-30T00:00:01Z';run['result']=None;write_run(p,run)
    changed=dict(run);changed['updated_at']='2026-08-30T00:00:02Z'
    with pytest.raises(RunAuditError,match='terminal'):write_run(p,changed)

def test_run_is_not_part_of_current_canonical_hash_graph(tmp_path):
    c=bootstrap(tmp_path);r=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(41000));proposal=r['proposal'];run=json.loads((c.workspace_root/f"runs/answer-association/{proposal['proposal_run_id']}/run.json").read_text());assert 'run_hash' not in proposal and 'current' not in run

def _transaction_backed_prepare(case, *, uuid_start=42000):
    from m3_helpers import current_hash,rewrite_answer_and_inventory
    rewrite_answer_and_inventory(case,'',uuid_start=uuid_start)
    return prepare(
        input_root=case.input_root,
        workspace_root=case.workspace_root,
        question_source_id=case.question_source_id,
        answer_source_ids=[case.answer_source_id],
        expected_candidate_hash=case.candidate_hash,
        expected_pointer=current_hash(case),
        now=lambda:'2026-08-30T00:00:00Z',
        uuid_factory=UUIDSequence(uuid_start+1000),
    )

def test_existing_success_terminal_run_revalidates_complete_transaction_claim(tmp_path):
    from qbanswer.artifacts import workspace_json_bytes
    from qbanswer.run_audit import reconcile_transaction_run
    from qbanswer.transaction import recover_transaction
    from qbcore.paths import validate_roots
    c=bootstrap(tmp_path);result=_transaction_backed_prepare(c)
    run=result['run'];txid=run['result']['transaction_id']
    path=c.workspace_root/f"runs/answer-association/{run['run_id']}/run.json"
    tampered=json.loads(path.read_text(encoding='utf-8'))
    tampered['result']['current_hash']='0'*64
    path.write_bytes(workspace_json_bytes(tampered))
    policy=validate_roots(c.input_root,c.workspace_root)
    canonical_before=(c.workspace_root/'state/answer-association/current.json').read_bytes()
    with pytest.raises(RunAuditError,match='canonical claim'):
        reconcile_transaction_run(policy,recover_transaction(policy,txid),now=lambda:'2026-08-30T00:02:00Z')
    assert (c.workspace_root/'state/answer-association/current.json').read_bytes()==canonical_before
    # Audit corruption is not auto-overwritten by reconciliation.
    assert json.loads(path.read_text(encoding='utf-8'))['result']['current_hash']=='0'*64

def test_success_terminal_run_cannot_rebind_to_another_complete_transaction(tmp_path):
    from qbanswer.artifacts import workspace_json_bytes
    from qbanswer.confirmation import confirm
    from qbanswer.run_audit import reconcile_transaction_run
    from qbanswer.transaction import recover_transaction
    from qbcore.paths import validate_roots
    from m3_helpers import current_hash,proposal_entry
    c=bootstrap(tmp_path);first=_transaction_backed_prepare(c,uuid_start=44000)
    first_run=first['run'];first_tx=first_run['result']['transaction_id']
    entry=proposal_entry(first,'missing')
    second=confirm(
        input_root=c.input_root,workspace_root=c.workspace_root,
        proposal_run_id=first['proposal']['proposal_run_id'],proposal_hash=first['proposal_hash'],
        request={'action':'retain_unresolved','proposal_ids':[entry['proposal_id']],'selected_evidence_ids':[]},
        expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),
        now=lambda:'2026-08-30T00:03:00Z',uuid_factory=UUIDSequence(47000),
    )
    second_claim=second['run']['result']
    path=c.workspace_root/f"runs/answer-association/{first_run['run_id']}/run.json"
    tampered=json.loads(path.read_text(encoding='utf-8'))
    tampered['result']=dict(second_claim)
    path.write_bytes(workspace_json_bytes(tampered))
    policy=validate_roots(c.input_root,c.workspace_root)
    with pytest.raises(RunAuditError,match='canonical claim'):
        reconcile_transaction_run(policy,recover_transaction(policy,first_tx),now=lambda:'2026-08-30T00:04:00Z')
    assert json.loads(path.read_text(encoding='utf-8'))['result']['transaction_id']==second_claim['transaction_id']

def test_existing_direct_prepare_success_run_revalidates_pointer_claim(tmp_path):
    from qbanswer.artifacts import workspace_json_bytes
    from qbanswer.service import recover
    c=bootstrap(tmp_path)
    result=prepare(
        input_root=c.input_root,workspace_root=c.workspace_root,
        question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],
        expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',
        now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(48000),
    )
    run=result['run'];assert run['status']=='needs_confirmation'
    path=c.workspace_root/f"runs/answer-association/{run['run_id']}/run.json"
    tampered=json.loads(path.read_text(encoding='utf-8'));tampered['result']={'direct_pointer':'0'*64}
    path.write_bytes(workspace_json_bytes(tampered))
    with pytest.raises(RunAuditError,match='direct prepare canonical claim'):
        recover(input_root=c.input_root,workspace_root=c.workspace_root,now=lambda:'2026-08-30T00:01:00Z')
    assert not (c.workspace_root/'state/answer-association/current.json').exists()
    assert json.loads(path.read_text(encoding='utf-8'))['result']['direct_pointer']=='0'*64

def test_historical_direct_prepare_terminal_status_is_revalidated_after_confirmation(tmp_path):
    from qbanswer.artifacts import workspace_json_bytes
    from qbanswer.confirmation import confirm
    from qbanswer.service import recover
    from m3_helpers import proposal_entry,current_hash
    c=bootstrap(tmp_path)
    prepared=prepare(
        input_root=c.input_root,workspace_root=c.workspace_root,
        question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],
        expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',
        now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(49000),
    )
    entry=proposal_entry(prepared,'confirmable')
    confirm(
        input_root=c.input_root,workspace_root=c.workspace_root,
        proposal_run_id=prepared['proposal']['proposal_run_id'],proposal_hash=prepared['proposal_hash'],
        request={'action':'confirm','proposal_ids':[entry['proposal_id']],'selected_evidence_ids':[]},
        expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',
        now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(50000),
    )
    canonical_before=(c.workspace_root/'state/answer-association/current.json').read_bytes()
    run=prepared['run'];path=c.workspace_root/f"runs/answer-association/{run['run_id']}/run.json"
    tampered=json.loads(path.read_text(encoding='utf-8'));tampered['status']='complete'
    path.write_bytes(workspace_json_bytes(tampered))
    with pytest.raises(RunAuditError,match='terminal status claim'):
        recover(input_root=c.input_root,workspace_root=c.workspace_root,now=lambda:'2026-08-30T00:03:00Z')
    assert (c.workspace_root/'state/answer-association/current.json').read_bytes()==canonical_before

def test_nonterminal_run_phase_cannot_move_backwards(tmp_path):
    c=bootstrap(tmp_path);p=validate_roots(c.input_root,c.workspace_root)
    run=new_run(run_id='00000000-0000-4000-8000-000000000010',operation='prepare',now=lambda:'2026-08-30T00:00:00Z')
    run['phase']='publication';run['updated_at']='2026-08-30T00:00:01Z';write_run(p,run)
    backwards=dict(run);backwards['phase']='association';backwards['updated_at']='2026-08-30T00:00:02Z'
    with pytest.raises(RunAuditError,match='phase moved backwards'):write_run(p,backwards)

def test_direct_needs_review_run_reuses_frozen_low_confidence_issue_code(tmp_path):
    from qbanswer.service import recover
    from m3_helpers import current_hash
    c=bootstrap(tmp_path,answer='answers-unknown-number.txt')
    first=prepare(
        input_root=c.input_root,workspace_root=c.workspace_root,
        question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],
        expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',
        now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(51000),
    )
    assert first['run']['status']=='needs_review' and current_hash(c)!='ABSENT'
    second=prepare(
        input_root=c.input_root,workspace_root=c.workspace_root,
        question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],
        expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),
        now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(52000),
    )
    assert second['proposal']['confirmation_base']=={'kind':'direct'} and second['run']['status']=='needs_review'
    recovered=recover(input_root=c.input_root,workspace_root=c.workspace_root,now=lambda:'2026-08-30T00:02:00Z')
    assert any(r['run_id']==second['run']['run_id'] and r['status']=='needs_review' for r in recovered)
