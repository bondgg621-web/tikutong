from __future__ import annotations
import json
from m2_helpers import UUIDSequence
from m3_helpers import bootstrap,current_hash,rewrite_answer_and_inventory
from qbanswer.prepare import prepare

def test_clean_prepare_publishes_proposal_but_no_canonical_snapshot(tmp_path):
    c=bootstrap(tmp_path);r=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(50000));assert r['run']['status']=='needs_confirmation';assert current_hash(c)=='ABSENT';assert r['proposal']['confirmation_base']=={'kind':'direct'}

def test_missing_prepare_creates_review_snapshot_and_needs_review(tmp_path):
    c=bootstrap(tmp_path);rewrite_answer_and_inventory(c,'',uuid_start=51000);r=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(52000));assert r['run']['status']=='needs_review';assert current_hash(c)!='ABSENT';assert r['proposal']['confirmation_base']['kind']=='prepare_result';assert all(e['conclusion']=='missing' for e in r['proposal']['entries'])

def test_prepare_expected_pointer_mismatch_fails_without_canonical_change(tmp_path):
    c=bootstrap(tmp_path);before=current_hash(c)
    try:prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='0'*64,now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(53000))
    except Exception:pass
    assert current_hash(c)==before

def test_identity_failures_leave_canonical_unchanged_and_emit_exact_structured_findings(tmp_path,monkeypatch):
    from copy import deepcopy
    import json
    import qbanswer.source_snapshot as ss
    c=bootstrap(tmp_path);before=current_hash(c)
    # Candidate hash mismatch.
    try:prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash='0'*64,expected_pointer=before,now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(54000))
    except Exception:pass
    assert current_hash(c)==before
    runs=sorted((c.workspace_root/'runs/answer-association').glob('*/run.json'));r=json.loads(runs[-1].read_text())
    assert r['status']=='failed' and r['run_findings'][0]['issue_code']=='QB-IDENTITY-AMBIGUOUS'
    assert set(r['run_findings'][0])=={'issue_code','blocking_level','source_id','candidate_id','option_id'}
    # Option-only replay drift must use the distinct frozen issue code and also leave current untouched.
    doc=json.loads((c.workspace_root/'candidates/sources'/f'{c.question_source_id}.json').read_text());drift=deepcopy(doc);drift['candidates'][0]['options'][0]['normalized_text_fingerprint']='f'*64
    monkeypatch.setattr(ss,'materialize_candidates',lambda *a,**k:drift)
    try:prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=before,now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(55000))
    except Exception:pass
    assert current_hash(c)==before
    runs=sorted((c.workspace_root/'runs/answer-association').glob('*/run.json'));r=json.loads(runs[-1].read_text())
    assert r['status']=='failed' and r['run_findings'][0]['issue_code']=='QB-OPTION-IDENTITY-AMBIGUOUS'
