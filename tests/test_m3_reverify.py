from __future__ import annotations
import json
import pytest
from m2_helpers import UUIDSequence
from m3_helpers import bootstrap,current_hash,rewrite_answer_and_inventory
from qbanswer.prepare import prepare
from qbanswer.confirmation import confirm
from qbanswer.reverify import reverify

def _validated(c,start=70000):
    p=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(start));ids=[e['proposal_id'] for e in p['proposal']['entries'] if e['conclusion']=='confirmable'];confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p['proposal']['proposal_run_id'],proposal_hash=p['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(start+1000))

def test_question_source_reverify_covers_all_current_decisions(tmp_path):
    c=bootstrap(tmp_path);_validated(c);r=reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(72000));assert len(r['reverify']['required_decision_ids'])==2 and all(x['result']=='valid' for x in r['reverify']['results'])

def test_revision_change_with_same_semantics_records_mapping_and_stays_valid(tmp_path):
    c=bootstrap(tmp_path);_validated(c);rewrite_answer_and_inventory(c,'\n1: A\n\n2: B\n',uuid_start=73000);r=reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(74000));assert all(x['result']=='valid' and x['mappings'] for x in r['reverify']['results'])

def test_selected_evidence_disappears_causes_safe_downgrade_not_auto_recovery(tmp_path):
    c=bootstrap(tmp_path);_validated(c);rewrite_answer_and_inventory(c,'2: B\n',uuid_start=75000);r=reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(76000));assert any(x['result']=='needs_revalidation' for x in r['reverify']['results'])
    # restore bytes; reverify cannot auto-create a new valid Decision
    rewrite_answer_and_inventory(c,'1: A\n2: B\n',uuid_start=77000);r2=reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:03:00Z',uuid_factory=UUIDSequence(78000));assert any(x['result']=='needs_revalidation' for x in r2['reverify']['results'])

def test_reverify_does_not_swallow_unexpected_source_resolution_bug(tmp_path,monkeypatch):
    import pytest
    import importlib
    module=importlib.import_module('qbanswer.reverify')
    from m3_helpers import current_hash
    c=bootstrap(tmp_path);_validated(c)
    def boom(**kwargs):raise RuntimeError('synthetic programmer bug')
    monkeypatch.setattr(module,'resolve_answer_sources',boom)
    with pytest.raises(RuntimeError,match='synthetic programmer bug'):
        module.reverify(input_root=c.input_root,workspace_root=c.workspace_root,scope={'kind':'question_source','question_source_id':c.question_source_id},additional_answer_source_ids=[],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(132000))
