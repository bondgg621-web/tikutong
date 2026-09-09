from __future__ import annotations
from copy import deepcopy
import pytest
from m3_helpers import bootstrap
from qbanswer.state_graph import StateGraphError,initial_interchange,initial_provenance,validate_parent_child,validated_gate

def test_initial_snapshot_keeps_m2_candidate_semantics(tmp_path):
    c=bootstrap(tmp_path);import json
    doc=json.loads((c.workspace_root/'candidates/sources'/f'{c.question_source_id}.json').read_text());manifest={'schema_version':'1.0','dataset_id':json.loads((c.workspace_root/'project.json').read_text())['dataset_id'],'sources':[]}
    inter=initial_interchange(manifest,doc);assert inter['candidates']['candidates']==doc['candidates'] and inter['decisions']['decisions']==[]

def test_parent_candidate_semantics_are_immutable_except_status(tmp_path):
    c=bootstrap(tmp_path);import json
    doc=json.loads((c.workspace_root/'candidates/sources'/f'{c.question_source_id}.json').read_text());m={'schema_version':'1.0','dataset_id':json.loads((c.workspace_root/'project.json').read_text())['dataset_id'],'sources':[]}
    p=initial_interchange(m,doc);ch=deepcopy(p);ch['candidates']['candidates'][0]['stem']='tampered';pp=initial_provenance(snapshot_id='00000000-0000-0000-0000-000000000001',dataset_id=m['dataset_id']);cp=deepcopy(pp);cp['snapshot_id']='00000000-0000-0000-0000-000000000002'
    with pytest.raises(StateGraphError):validate_parent_child(p,ch,pp,cp,operation='prepare')

def test_validated_gate_fails_without_exact_valid_decision(tmp_path):
    c=bootstrap(tmp_path);import json
    doc=json.loads((c.workspace_root/'candidates/sources'/f'{c.question_source_id}.json').read_text());m={'schema_version':'1.0','dataset_id':json.loads((c.workspace_root/'project.json').read_text())['dataset_id'],'sources':[]}
    inter=initial_interchange(m,doc);inter['candidates']['candidates'][0]['status']='validated';prov=initial_provenance(snapshot_id='00000000-0000-0000-0000-000000000001',dataset_id=m['dataset_id'])
    ok,reason=validated_gate(inter,prov);assert not ok and reason

def _validated_graph(tmp_path,start=100000):
    from m2_helpers import UUIDSequence
    from m3_helpers import bootstrap,current_hash
    from qbanswer.prepare import prepare
    from qbanswer.confirmation import confirm
    from qbcore.paths import validate_roots
    from qbanswer.transaction import read_current_verified
    c=bootstrap(tmp_path);p=prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(start));ids=[e['proposal_id'] for e in p['proposal']['entries'] if e['conclusion']=='confirmable'];confirm(input_root=c.input_root,workspace_root=c.workspace_root,proposal_run_id=p['proposal']['proposal_run_id'],proposal_hash=p['proposal_hash'],request={'action':'confirm_all_unambiguous','proposal_ids':ids,'selected_evidence_ids':[]},expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:01:00Z',uuid_factory=UUIDSequence(start+1000));_,v=read_current_verified(validate_roots(c.input_root,c.workspace_root));return c,v['interchange'],v['provenance']

def test_validated_gate_negative_matrix(tmp_path):
    from copy import deepcopy
    from qbanswer.review import make_review
    c,base,prov=_validated_graph(tmp_path)
    validated=next(x for x in base['candidates']['candidates'] if x['status']=='validated');decision=next(x for x in base['decisions']['decisions'] if x['candidate_id']==validated['candidate_id'] and x['status']=='valid')
    mutations=[]
    def m1(i,p):i['candidates']['candidates'][0]['question_type']='unsupported'
    mutations.append(m1)
    def m2(i,p):i['decisions']['decisions']=[d for d in i['decisions']['decisions'] if d['decision_id']!=decision['decision_id']]
    mutations.append(m2)
    def m3(i,p):next(d for d in i['decisions']['decisions'] if d['decision_id']==decision['decision_id'])['value']['resolved_option_ids']=['00000000-0000-4000-8000-ffffffffffff']
    mutations.append(m3)
    def m4(i,p):i['review_queue']['review_items'].append(make_review(review_id='00000000-0000-4000-8000-fffffffffff1',candidate_id=validated['candidate_id'],issue_code='QB-ANSWER-MISSING'))
    mutations.append(m4)
    def m5(i,p):next(x for x in p['decision_links'] if x['decision_id']==decision['decision_id'])['confirmation_path']=None
    mutations.append(m5)
    def m6(i,p):i['manifest']['sources']=[x for x in i['manifest']['sources'] if x['source_id']!=decision['evidence'][0]['source_id']]
    mutations.append(m6)
    def m7(i,p):next(x for x in i['manifest']['sources'] if x['source_id']==decision['evidence'][0]['source_id'])['revision']+=1
    mutations.append(m7)
    for mutate in mutations:
        i=deepcopy(base);p=deepcopy(prov);mutate(i,p);ok,reason=validated_gate(i,p);assert not ok and reason
