from __future__ import annotations
import json
import pytest
from m2_helpers import UUIDSequence
from m3_helpers import bootstrap,current_hash,proposal_entry,rewrite_answer_and_inventory
from qbanswer.prepare import prepare
from qbanswer.confirmation import confirm

def _proposal(c,start=60000):return prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(start))

def test_confirm_all_unambiguous_promotes_only_with_proposal_evidence(tmp_path):
    c=bootstrap(tmp_path);p=_proposal(c);ids=[e['proposal_id'] for e in p['proposal']['entries'] if e['conclusion']=='confirmable'];r=confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p['proposal']['proposal_run_id'],proposal_hash=p['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(61000));assert r['run']['status']=='complete'

def test_confirmation_cannot_inject_option_or_free_text(tmp_path):
    c=bootstrap(tmp_path);p=_proposal(c);e=proposal_entry(p,'confirmable')
    with pytest.raises(Exception):confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p['proposal']['proposal_run_id'],proposal_hash=p['proposal_hash'],request={'action':'confirm','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[],'option_id':e['proposed_option_id']},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(62000))

def test_stale_proposal_replay_after_intervening_generation_fails(tmp_path):
    c=bootstrap(tmp_path);p=_proposal(c);e=proposal_entry(p,'confirmable')
    # another confirmation advances current
    confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p['proposal']['proposal_run_id'],proposal_hash=p['proposal_hash'],request={'action':'confirm','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(63000))
    with pytest.raises(Exception):confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p['proposal']['proposal_run_id'],proposal_hash=p['proposal_hash'],request={'action':'confirm','proposal_ids':[e['proposal_id']],'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:02:00Z',uuid_factory=UUIDSequence(64000))

def test_conflict_choose_evidence_uses_only_existing_evidence(tmp_path):
    c=bootstrap(tmp_path,answer='answers-conflict.txt');p=_proposal(c);e=proposal_entry(p,'conflict');chosen=e['alternatives'][0]['evidence_ids']
    r=confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p['proposal']['proposal_run_id'],proposal_hash=p['proposal_hash'],request={'action':'choose_evidence','proposal_ids':[e['proposal_id']],'selected_evidence_ids':chosen},expected_candidate_hash=c.candidate_hash,expected_pointer=current_hash(c),now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(65000));assert r['run']['status']=='complete'
