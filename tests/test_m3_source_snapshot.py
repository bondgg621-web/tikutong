from __future__ import annotations
import json
import pytest
from m2_helpers import UUIDSequence
from m3_helpers import bootstrap
from qbanswer.answer_parser import parse_answer_text
from qbanswer.source_snapshot import SnapshotError,build_manifest,resolve_answer_sources,resolve_question_view

def test_question_identity_replay_and_candidate_hash_gate(tmp_path):
    c=bootstrap(tmp_path)
    _,snap,doc,views,actual=resolve_question_view(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,expected_candidate_hash=c.candidate_hash)
    assert actual==c.candidate_hash and len(views)==len(doc['candidates'])==2
    assert [v['_question_number'] for v in views]==[1,2]
    with pytest.raises(SnapshotError) as e:resolve_question_view(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,expected_candidate_hash='0'*64)
    assert e.value.issue_code=='QB-IDENTITY-AMBIGUOUS'

def test_answer_source_selection_rejects_empty_or_duplicates(tmp_path):
    c=bootstrap(tmp_path)
    for ids in ([],[c.answer_source_id,c.answer_source_id]):
        with pytest.raises(SnapshotError):resolve_answer_sources(input_root=c.input_root,workspace_root=c.workspace_root,answer_source_ids=ids,uuid_factory=UUIDSequence(1),parse_func=parse_answer_text)

def test_manifest_roles_are_explicit_and_registry_is_not_modified(tmp_path):
    c=bootstrap(tmp_path);before=(c.workspace_root/'registry/sources.json').read_bytes()
    _,q,_,_,_=resolve_question_view(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,expected_candidate_hash=c.candidate_hash)
    ans,_=resolve_answer_sources(input_root=c.input_root,workspace_root=c.workspace_root,answer_source_ids=[c.answer_source_id],uuid_factory=UUIDSequence(1),parse_func=parse_answer_text)
    m=build_manifest(workspace_root=c.workspace_root,question_snapshot=q,answer_snapshots=ans)
    kinds={x['source_id']:x['kind'] for x in m['sources']};assert kinds[c.question_source_id]=='question_document' and kinds[c.answer_source_id]=='answer_document'
    assert (c.workspace_root/'registry/sources.json').read_bytes()==before

def test_candidate_and_option_identity_replay_mismatch_have_distinct_issue_codes(tmp_path,monkeypatch):
    from copy import deepcopy
    import qbanswer.source_snapshot as ss
    c=bootstrap(tmp_path);doc=json.loads((c.workspace_root/'candidates/sources'/f'{c.question_source_id}.json').read_text())
    candidate_drift=deepcopy(doc);candidate_drift['candidates'][0]['stem']+=' drift'
    monkeypatch.setattr(ss,'materialize_candidates',lambda *a,**k:candidate_drift)
    with pytest.raises(SnapshotError) as e:ss.resolve_question_view(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,expected_candidate_hash=c.candidate_hash)
    assert e.value.issue_code=='QB-IDENTITY-AMBIGUOUS'
    option_drift=deepcopy(doc);option_drift['candidates'][0]['options'][0]['normalized_text_fingerprint']='f'*64
    monkeypatch.setattr(ss,'materialize_candidates',lambda *a,**k:option_drift)
    with pytest.raises(SnapshotError) as e:ss.resolve_question_view(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,expected_candidate_hash=c.candidate_hash)
    assert e.value.issue_code=='QB-OPTION-IDENTITY-AMBIGUOUS'

def test_manifest_absorbs_full_registry_path_history_suffix(tmp_path):
    from qbcore.cli import run_inventory
    from m2_helpers import fixed_now
    c=bootstrap(tmp_path);(c.input_root/'answers.txt').rename(c.input_root/'renamed.txt')
    run_inventory(input_root=c.input_root,workspace_root=c.workspace_root,now=fixed_now,uuid_factory=UUIDSequence(90000))
    _,q,_,_,_=resolve_question_view(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,expected_candidate_hash=c.candidate_hash)
    ans,_=resolve_answer_sources(input_root=c.input_root,workspace_root=c.workspace_root,answer_source_ids=[c.answer_source_id],uuid_factory=UUIDSequence(91000),parse_func=parse_answer_text)
    m=build_manifest(workspace_root=c.workspace_root,question_snapshot=q,answer_snapshots=ans)
    a=next(x for x in m['sources'] if x['source_id']==c.answer_source_id)
    assert a['current_relative_path']=='renamed.txt' and a['path_history']==['answers.txt','renamed.txt']
