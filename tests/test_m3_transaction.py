from __future__ import annotations
import json
import pytest
from m2_helpers import UUIDSequence
from m3_helpers import bootstrap,current_hash,proposal_entry
from qbcore.paths import validate_roots
from qbanswer.prepare import prepare
from qbanswer.confirmation import confirm
from qbanswer.transaction import TransactionError,read_current_verified,workspace_lock

def _validated(tmp_path,start=30000):
    c=bootstrap(tmp_path);pr=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(start));ids=[e['proposal_id'] for e in pr['proposal']['entries'] if e['conclusion']=='confirmable'];co=confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=pr['proposal']['proposal_run_id'],proposal_hash=pr['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(start+1000));return c,co

def test_current_pointer_verifies_commit_snapshot_and_transaction(tmp_path):
    c,_=_validated(tmp_path);digest,verified=read_current_verified(validate_roots(c.input_root,c.workspace_root));assert digest!='ABSENT' and verified['pointer']['generation']==1

def test_second_writer_lock_is_nonblocking(tmp_path):
    c=bootstrap(tmp_path);p=validate_roots(c.input_root,c.workspace_root)
    with workspace_lock(p):
        with pytest.raises(TransactionError,match='busy'): 
            with workspace_lock(p):pass
    with workspace_lock(p):pass

def test_unknown_external_pointer_fails_closed(tmp_path):
    c,_=_validated(tmp_path);ptr=c.workspace_root/'state/answer-association/current.json';v=json.loads(ptr.read_text());v['generation']+=100;ptr.write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
    with pytest.raises(Exception):read_current_verified(validate_roots(c.input_root,c.workspace_root))

def test_aborted_terminal_transaction_cannot_be_revived_when_staged_set_is_completable(tmp_path,monkeypatch):
    import importlib
    pm=importlib.import_module('qbanswer.prepare')
    from m3_helpers import rewrite_answer_and_inventory
    from qbanswer.artifacts import read_relative,write_atomic_json
    from qbanswer.transaction import recover_transaction
    c=bootstrap(tmp_path);rewrite_answer_and_inventory(c,'',uuid_start=70000)
    real=pm.publish_transaction
    def crashy(**kwargs):return real(**kwargs,crash_after='staged')
    monkeypatch.setattr(pm,'publish_transaction',crashy)
    with pytest.raises(Exception):
        prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(71000))
    txdirs=sorted((c.workspace_root/'transactions/answer-association').iterdir());assert len(txdirs)==1
    txid=txdirs[0].name;p=validate_roots(c.input_root,c.workspace_root)
    plan,_,plan_hash=read_relative(p,f'transactions/answer-association/{txid}/plan.json')
    write_atomic_json(p,f'transactions/answer-association/{txid}/state.json',{'schema_version':'1.0','transaction_id':txid,'plan_hash':plan_hash,'sequence':3,'status':'aborted'})
    with pytest.raises(TransactionError,match='completable staged snapshot'):
        recover_transaction(p,txid)
    assert current_hash(c)=='ABSENT'
    assert not (c.workspace_root/f"{plan['after_snapshot_path']}/commit.json").exists()

def test_complete_terminal_transaction_with_before_pointer_fails_closed_instead_of_republishing(tmp_path):
    from m3_helpers import rewrite_answer_and_inventory
    from qbanswer.transaction import recover_transaction
    c=bootstrap(tmp_path);rewrite_answer_and_inventory(c,'',uuid_start=72000)
    result=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(73000))
    txid=result['run']['result']['transaction_id'];current=c.workspace_root/'state/answer-association/current.json';assert current.exists();current.unlink()
    p=validate_roots(c.input_root,c.workspace_root)
    with pytest.raises(TransactionError,match='complete transaction current pointer contradiction'):
        recover_transaction(p,txid)
    assert current_hash(c)=='ABSENT' and not current.exists()
