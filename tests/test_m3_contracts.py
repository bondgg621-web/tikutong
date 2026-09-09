from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import pytest
from qbanswer.artifacts import ArtifactError,compact_json_bytes,workspace_json_bytes
from qbanswer.contracts import ContractError,load_schema,validate_confirmation,validate_proposal,validate_run

SCHEMAS=[
'answer-association-run.schema.json','answer-association-proposal.schema.json','answer-association-confirmation.schema.json','answer-association-reverify.schema.json','answer-association-provenance.schema.json','answer-association-transaction.schema.json','answer-association-pointer.schema.json','answer-association-commit.schema.json']

def test_all_eight_schemas_are_draft_2020_12_and_closed():
    import jsonschema
    for name in SCHEMAS:
        s=load_schema(name);jsonschema.Draft202012Validator.check_schema(s)
        assert s['$schema']=='https://json-schema.org/draft/2020-12/schema'
        branches=s.get('oneOf')
        assert s.get('additionalProperties') is False or (branches and all(b.get('additionalProperties') is False for b in branches))

def test_frozen_json_vectors_are_exact_and_independent():
    value={'a':'题','b':['A']}
    compact='{"a":"题","b":["A"]}'.encode('utf-8')
    workspace='''{\n  "a": "题",\n  "b": [\n    "A"\n  ]\n}\n'''.encode('utf-8')
    assert len(compact)==21 and sha256(compact).hexdigest()=='8fe664ef5335c949424a347dd901141cb1a68b0e8db91a318991e26ba8f5dc11'
    assert len(workspace)==39 and sha256(workspace).hexdigest()=='8c64fdc1fd7928af1840909f9afd41a55c9f9746375076129fdaeb8544d7bec9'
    assert compact_json_bytes(value)==compact
    assert workspace_json_bytes(value)==workspace

def test_exact_json_rejects_container_subclass_nonfinite_and_nonstring_key():
    class D(dict):pass
    for value in [D(a=1),{'a':float('nan')},{1:'x'}]:
        with pytest.raises(ArtifactError):workspace_json_bytes(value)

def test_proposal_schema_has_six_conclusion_branches_and_stale_binding_required():
    s=load_schema('answer-association-proposal.schema.json')
    branches=s['properties']['entries']['items']['oneOf'];assert len(branches)==6
    stale=next(b for b in branches if b['properties']['conclusion'].get('const')=='stale')
    for key in ('decision_id','review_item_id','review_issue_key'):assert key in stale['required']
    assert stale['properties']['decision_id']['type']=='string'
    assert stale['properties']['review_item_id']['type']=='string'

def test_confirmation_schema_and_runtime_have_seven_action_branches():
    s=load_schema('answer-association-confirmation.schema.json')
    branches=s['properties']['request']['oneOf'];assert len(branches)==7
    actions={b['properties']['action']['const'] for b in branches}
    assert actions=={'confirm','confirm_all_unambiguous','choose_evidence','reject','reject_association','retain_unresolved','archive_stale'}

def test_runtime_contract_rejects_direct_answer_fields_in_confirmation():
    bad={'schema_version':'1.0','confirmation_id':'00000000-0000-0000-0000-000000000001','proposal_run_id':'00000000-0000-0000-0000-000000000002','proposal_hash':'0'*64,'request':{'action':'confirm','proposal_ids':['00000000-0000-0000-0000-000000000003'],'selected_evidence_ids':[],'option_id':'00000000-0000-0000-0000-000000000004'},'expected_candidate_hash':'1'*64,'expected_current_pointer':'ABSENT','result_transaction_id':'00000000-0000-0000-0000-000000000005','result_snapshot_id':'00000000-0000-0000-0000-000000000006','recorded_at':'2026-08-30T00:00:00Z'}
    with pytest.raises(ContractError):validate_confirmation(bad)


def _run_sample(*,operation='prepare',status='running',phase='source_resolution',result=None):
    return {
        'schema_version':'1.0','run_id':'00000000-0000-4000-8000-000000000001',
        'operation':operation,'status':status,'phase':phase,
        'started_at':'2026-08-30T00:00:00Z','updated_at':'2026-08-30T00:00:01Z',
        'artifacts':[],'run_findings':[],'result':result,
    }

def _tx_claim():
    return {
        'transaction_id':'00000000-0000-4000-8000-000000000002',
        'transaction_state_hash':'1'*64,
        'snapshot_id':'00000000-0000-4000-8000-000000000003',
        'current_hash':'2'*64,'commit_hash':'3'*64,
    }

def _assert_run_contract_accepts(value):
    import jsonschema
    jsonschema.Draft202012Validator(load_schema('answer-association-run.schema.json')).validate(value)
    validate_run(value)

def _assert_run_contract_rejects(value):
    import jsonschema
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(load_schema('answer-association-run.schema.json')).validate(value)
    with pytest.raises(ContractError):validate_run(value)

def test_run_schema_runtime_freeze_nonterminal_failed_direct_and_transaction_success_branches():
    _assert_run_contract_accepts(_run_sample())
    _assert_run_contract_accepts(_run_sample(status='failed',phase='complete',result=None))
    _assert_run_contract_accepts(_run_sample(status='needs_confirmation',phase='complete',result={'direct_pointer':'ABSENT'}))
    _assert_run_contract_accepts(_run_sample(status='needs_review',phase='complete',result=_tx_claim()))
    _assert_run_contract_accepts(_run_sample(operation='confirm',status='complete',phase='complete',result=_tx_claim()))
    _assert_run_contract_accepts(_run_sample(operation='reverify',status='complete',phase='complete',result=_tx_claim()))

def test_run_schema_runtime_rejects_impossible_terminal_combinations():
    _assert_run_contract_rejects(_run_sample(operation='confirm',status='needs_confirmation',phase='complete',result=_tx_claim()))
    _assert_run_contract_rejects(_run_sample(operation='confirm',status='complete',phase='complete',result={'direct_pointer':'ABSENT'}))
    _assert_run_contract_rejects(_run_sample(status='complete',phase='publication',result={'direct_pointer':'ABSENT'}))
    _assert_run_contract_rejects(_run_sample(status='failed',phase='complete',result=_tx_claim()))
    _assert_run_contract_rejects(_run_sample(status='running',phase='complete',result=None))
    _assert_run_contract_rejects(_run_sample(operation='recover',status='complete',phase='complete',result=_tx_claim()))

def _plan_sample(operation='prepare',kinds=('manifest','proposal')):
    return {
        'schema_version':'1.0','transaction_id':'00000000-0000-4000-8000-000000000020',
        'snapshot_id':'00000000-0000-4000-8000-000000000021','operation':operation,'before':'ABSENT',
        'after_snapshot_path':'state/answer-association/snapshots/00000000-0000-4000-8000-000000000021',
        'parent_pointer_hash':'1'*64,'interchange_hash':'2'*64,'provenance_hash':'3'*64,
        'operation_artifacts':[{'kind':k,'relative_path':f'runs/answer-association/x/{k}.json','content_hash':str(i+4)*64} for i,k in enumerate(kinds)],
    }

def _state_sample(sequence,status):
    return {'schema_version':'1.0','transaction_id':'00000000-0000-4000-8000-000000000020','plan_hash':'9'*64,'sequence':sequence,'status':status}

def test_transaction_schema_runtime_pair_and_operation_artifact_whitelists_match():
    import jsonschema
    from qbanswer.contracts import validate_plan,validate_state
    validator=jsonschema.Draft202012Validator(load_schema('answer-association-transaction.schema.json'))
    valid=[_plan_sample(),_plan_sample('confirm',('confirmation',)),_plan_sample('reverify',('reverify',)),_state_sample(1,'staged'),_state_sample(2,'publishing'),_state_sample(3,'complete'),_state_sample(3,'aborted')]
    for value in valid:
        validator.validate(value)
        (validate_plan if 'operation' in value else validate_state)(value)
    invalid=[_plan_sample('confirm',('manifest','proposal')),_plan_sample('prepare',('proposal','manifest')),_state_sample(1,'complete'),_state_sample(2,'aborted'),_state_sample(3,'publishing')]
    for value in invalid:
        with pytest.raises(jsonschema.ValidationError):validator.validate(value)
        with pytest.raises(ContractError):(validate_plan if 'operation' in value else validate_state)(value)
