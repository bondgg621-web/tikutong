"""Single-writer canonical transaction publication and deterministic recovery."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
import json, os
from pathlib import Path
from typing import Iterable

from qbcore.paths import RootPolicy
from .artifacts import ABSENT,ArtifactError,current_pointer,digest_bytes,read_json_bytes,read_relative,resolve_workspace,workspace_json_bytes,write_atomic_json,write_immutable_json
from .contracts import ContractError,validate_commit,validate_plan,validate_pointer,validate_provenance,validate_reverify,validate_state
from .state_graph import StateGraphError,validate_parent_child,validated_gate

class TransactionError(RuntimeError): pass

@dataclass(frozen=True)
class TransactionResult:
    transaction_id:str; snapshot_id:str; state_hash:str; current_hash:str; commit_hash:str

@contextmanager
def workspace_lock(policy:RootPolicy):
    path=policy.assert_write_target(policy.workspace_root/'locks/answer-association.lock');path.parent.mkdir(parents=True,exist_ok=True)
    stream=path.open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            stream.seek(0); stream.write(b'0'); stream.flush(); stream.seek(0)
            try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as exc:raise TransactionError('answer-association workspace is busy') from exc
        else:
            import fcntl
            try:fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc:raise TransactionError('answer-association workspace is busy') from exc
        yield
    finally:
        try:
            if os.name=='nt':
                import msvcrt;stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl;fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
        except OSError:pass
        stream.close()

def _parent_obj(policy):
    digest,obj=current_pointer(policy)
    return digest, ({'state':'ABSENT'} if obj is None else obj)

def _generation(parent): return 1 if parent=={'state':'ABSENT'} else parent['generation']+1

def _expected_commit(plan,plan_hash):
    return {'schema_version':'1.0','transaction_id':plan['transaction_id'],'snapshot_id':plan['snapshot_id'],'plan_hash':plan_hash,'parent_pointer_hash':plan['parent_pointer_hash'],'interchange_hash':plan['interchange_hash'],'provenance_hash':plan['provenance_hash']}

def _expected_pointer(*,dataset_id,plan,commit_hash,parent_hash,parent_obj):
    snap=plan['after_snapshot_path']
    return {'schema_version':'1.0','dataset_id':dataset_id,'snapshot_id':plan['snapshot_id'],'snapshot_path':snap,'commit_path':f"{snap}/commit.json",'commit_hash':commit_hash,'parent_pointer_hash':parent_hash,'generation':_generation(parent_obj)}

def _load_parent_graph(policy,parent_obj):
    if parent_obj=={'state':'ABSENT'}:return None,None
    validate_pointer(parent_obj,allow_absent=False)
    inter,_,_=read_relative(policy,f"{parent_obj['snapshot_path']}/interchange.json")
    prov,_,_=read_relative(policy,f"{parent_obj['snapshot_path']}/provenance.json")
    return inter,prov

def _verify_artifact_ref(policy,ref):
    _,_,actual=read_relative(policy,ref['relative_path'])
    if actual!=ref['content_hash']:raise TransactionError('operation artifact hash mismatch')

def _validate_operation_semantics(policy,plan,parent_obj,child,child_prov):
    parent,parent_prov=_load_parent_graph(policy,parent_obj)
    validate_parent_child(parent,child,parent_prov,child_prov,operation=plan['operation'])
    refs=plan['operation_artifacts']
    if plan['operation']=='prepare':
        manifest,_,_=read_relative(policy,refs[0]['relative_path']);proposal,_,_=read_relative(policy,refs[1]['relative_path'])
        from .prepare import validate_prepare_semantics
        validate_prepare_semantics(plan=plan,parent=parent,child=child,parent_provenance=parent_prov,child_provenance=child_prov,manifest=manifest,proposal=proposal)
    elif plan['operation']=='confirm':
        confirmation,_,_=read_relative(policy,refs[0]['relative_path'])
        from .confirmation import validate_confirmation_semantics
        validate_confirmation_semantics(policy=policy,plan=plan,parent=parent,child=child,parent_provenance=parent_prov,child_provenance=child_prov,confirmation=confirmation)
    elif plan['operation']=='reverify':
        rv,_,_=read_relative(policy,refs[0]['relative_path'])
        from .reverify import validate_reverify_semantics
        validate_reverify_semantics(policy=policy,plan=plan,parent=parent,child=child,parent_provenance=parent_prov,child_provenance=child_prov,reverify_artifact=rv)

def verify_snapshot_pointer(policy:RootPolicy,pointer:dict,*,visited=None):
    validate_pointer(pointer,allow_absent=False)
    visited=set() if visited is None else visited
    if pointer['snapshot_id'] in visited:raise TransactionError('snapshot ancestry cycle')
    visited.add(pointer['snapshot_id'])
    commit,_,ch=read_relative(policy,pointer['commit_path']);validate_commit(commit)
    if ch!=pointer['commit_hash'] or commit['snapshot_id']!=pointer['snapshot_id']:raise TransactionError('current commit mismatch')
    txroot=f"transactions/answer-association/{commit['transaction_id']}"
    plan,_,ph=read_relative(policy,f'{txroot}/plan.json');state,_,sh=read_relative(policy,f'{txroot}/state.json');validate_plan(plan);validate_state(state)
    if ph!=commit['plan_hash'] or state['plan_hash']!=ph or state['status']!='complete':raise TransactionError('snapshot transaction is not complete')
    snap=pointer['snapshot_path']
    parent,_,pah=read_relative(policy,f'{snap}/parent-pointer.json');inter,_,ih=read_relative(policy,f'{snap}/interchange.json');prov,_,prh=read_relative(policy,f'{snap}/provenance.json')
    validate_pointer(parent,allow_absent=True);validate_provenance(prov)
    if (pah,ih,prh)!=(commit['parent_pointer_hash'],commit['interchange_hash'],commit['provenance_hash']):raise TransactionError('snapshot content hash mismatch')
    if pah!=pointer['parent_pointer_hash'] or plan['parent_pointer_hash']!=pah or plan['interchange_hash']!=ih or plan['provenance_hash']!=prh:raise TransactionError('snapshot plan hash mismatch')
    for ref in plan['operation_artifacts']:_verify_artifact_ref(policy,ref)
    _validate_operation_semantics(policy,plan,parent,inter,prov)
    def _load_reverify(relative_path,expected_hash):
        rv,_,actual_hash=read_relative(policy,relative_path)
        if actual_hash!=expected_hash:raise TransactionError('reverify audit hash mismatch')
        validate_reverify(rv)
        return rv
    gate_ok,gate_reason=validated_gate(inter,prov,reverify_loader=_load_reverify)
    if not gate_ok:raise TransactionError(f'validated gate failed: {gate_reason}')
    if parent=={'state':'ABSENT'}:
        if pointer['generation']!=1:raise TransactionError('first generation invalid')
    else:
        if pointer['generation']!=parent['generation']+1:raise TransactionError('generation chain invalid')
        verify_snapshot_pointer(policy,parent,visited=visited)
    return {'pointer':pointer,'commit':commit,'plan':plan,'state':state,'state_hash':sh,'interchange':inter,'provenance':prov,'parent':parent}

def read_current_verified(policy):
    digest,obj=current_pointer(policy)
    if obj is None:return ABSENT,None
    return digest,verify_snapshot_pointer(policy,obj)

def _is_descendant_of(policy,current_obj,target_obj):
    cur=current_obj;seen=set()
    while cur and cur!={'state':'ABSENT'}:
        if cur==target_obj:return True
        sid=cur.get('snapshot_id')
        if sid in seen:return False
        seen.add(sid)
        try:cur,_,_=read_relative(policy,f"{cur['snapshot_path']}/parent-pointer.json")
        except Exception:return False
    return False

def validate_prepare_result_proposal_origin(policy,proposal:dict,proposal_path:str,proposal_hash:str):
    base=proposal['confirmation_base']
    if base['kind']!='prepare_result':return
    txid=base['transaction_id'];plan,_,_=read_relative(policy,f'transactions/answer-association/{txid}/plan.json');validate_plan(plan)
    state,_,_=read_relative(policy,f'transactions/answer-association/{txid}/state.json');validate_state(state)
    if plan['operation']!='prepare' or plan['transaction_id']!=txid or plan['snapshot_id']!=base['snapshot_id'] or state['status']!='complete':raise TransactionError('proposal prepare transaction binding invalid')
    refs=plan['operation_artifacts']
    if len(refs)!=2 or [x['kind'] for x in refs]!=['manifest','proposal']:raise TransactionError('proposal prepare artifact whitelist invalid')
    pref=refs[1]
    if pref['relative_path']!=proposal_path or pref['content_hash']!=proposal_hash:raise TransactionError('proposal is not the artifact frozen by prepare transaction')

def validate_confirmation_base(policy,proposal:dict,actual_hash:str,actual_obj:dict|None,*,proposal_path:str,proposal_hash:str):
    base=proposal['confirmation_base']; prepared=proposal['prepared_from_pointer']
    if base['kind']=='direct':
        if actual_hash!=prepared:raise TransactionError('proposal direct base is stale')
        return
    validate_prepare_result_proposal_origin(policy,proposal,proposal_path,proposal_hash)
    if actual_obj is None or actual_obj.get('snapshot_id')!=base['snapshot_id']:raise TransactionError('proposal prepare-result base is stale')
    commit,_,_=read_relative(policy,actual_obj['commit_path'])
    if commit['transaction_id']!=base['transaction_id']:raise TransactionError('proposal prepare transaction mismatch')
    parent,_,parent_hash=read_relative(policy,f"{actual_obj['snapshot_path']}/parent-pointer.json")
    if prepared=='ABSENT':
        if parent!={'state':'ABSENT'}:raise TransactionError('proposal parent mismatch')
    elif parent_hash!=prepared:raise TransactionError('proposal parent mismatch')

def publish_transaction(*,policy:RootPolicy,operation:str,before:str,child_interchange:dict,child_provenance:dict,operation_artifacts:list[dict],transaction_id:str,snapshot_id:str,crash_after:str|None=None)->TransactionResult:
    actual,parent_obj=_parent_obj(policy)
    if actual!=before:raise TransactionError('current pointer changed before publication')
    snap=f'state/answer-association/snapshots/{snapshot_id}'
    child_provenance=dict(child_provenance);child_provenance['snapshot_id']=snapshot_id
    _,parent_hash=write_immutable_json(policy,f'{snap}/parent-pointer.json',parent_obj)
    _,inter_hash=write_immutable_json(policy,f'{snap}/interchange.json',child_interchange)
    _,prov_hash=write_immutable_json(policy,f'{snap}/provenance.json',child_provenance)
    refs=[]
    for r in operation_artifacts:
        _verify_artifact_ref(policy,r);refs.append(dict(r))
    plan={'schema_version':'1.0','transaction_id':transaction_id,'snapshot_id':snapshot_id,'operation':operation,'before':before,'after_snapshot_path':snap,'parent_pointer_hash':parent_hash,'interchange_hash':inter_hash,'provenance_hash':prov_hash,'operation_artifacts':refs}
    validate_plan(plan)
    plan_path=f'transactions/answer-association/{transaction_id}/plan.json';_,plan_hash=write_immutable_json(policy,plan_path,plan)
    if crash_after=='plan':raise TransactionError('injected crash B')
    state={'schema_version':'1.0','transaction_id':transaction_id,'plan_hash':plan_hash,'sequence':1,'status':'staged'};write_atomic_json(policy,f'transactions/answer-association/{transaction_id}/state.json',state)
    if crash_after=='staged':raise TransactionError('injected crash B')
    commit=_expected_commit(plan,plan_hash);validate_commit(commit);_,commit_hash=write_immutable_json(policy,f'{snap}/commit.json',commit)
    if crash_after=='commit':raise TransactionError('injected crash C')
    state={**state,'sequence':2,'status':'publishing'};write_atomic_json(policy,f'transactions/answer-association/{transaction_id}/state.json',state)
    # Validate committed child before pointer switch. Terminal state is intentionally not required yet.
    _validate_operation_semantics(policy,plan,parent_obj,child_interchange,child_provenance)
    if crash_after=='publishing':raise TransactionError('injected crash C')
    current=_expected_pointer(dataset_id=child_interchange['manifest']['dataset_id'],plan=plan,commit_hash=commit_hash,parent_hash=parent_hash,parent_obj=parent_obj)
    actual2,_=current_pointer(policy)
    if actual2==before:write_atomic_json(policy,'state/answer-association/current.json',current)
    else:
        cur_obj=current_pointer(policy)[1]
        if cur_obj!=current:raise TransactionError('current pointer changed during publication')
    current_hash=digest_bytes(workspace_json_bytes(current))
    if crash_after=='pointer':raise TransactionError('injected crash D')
    # Validate complete canonical graph except terminal state, then publish complete state.
    # Use local semantic validation; after terminal write full recursive reader is allowed.
    state={**state,'sequence':3,'status':'complete'};_,state_hash=write_atomic_json(policy,f'transactions/answer-association/{transaction_id}/state.json',state)
    if crash_after=='complete':raise TransactionError('injected crash E')
    verify_snapshot_pointer(policy,current)
    return TransactionResult(transaction_id,snapshot_id,state_hash,current_hash,commit_hash)

def _read_plan(policy,txid):
    plan,_,ph=read_relative(policy,f'transactions/answer-association/{txid}/plan.json');validate_plan(plan);return plan,ph

def recover_transaction(policy:RootPolicy,txid:str)->TransactionResult|None:
    plan,ph=_read_plan(policy,txid); txstate=f'transactions/answer-association/{txid}/state.json'
    state=None;state_hash=None
    try:state,_,state_hash=read_relative(policy,txstate);validate_state(state)
    except Exception:state=None;state_hash=None
    if state and state['plan_hash']!=ph:raise TransactionError('transaction state plan mismatch')
    snap=plan['after_snapshot_path']; commit_path=f'{snap}/commit.json'; commit=None;commit_hash=None
    cp=resolve_workspace(policy,commit_path)
    if cp.exists():
        try:commit,_,commit_hash=read_relative(policy,commit_path);validate_commit(commit)
        except Exception as exc:raise TransactionError('existing commit is invalid') from exc
        if commit!=_expected_commit(plan,ph):raise TransactionError('existing commit is not deterministic')
    current_hash,current_obj=current_pointer(policy)

    # Operation artifacts are immutable inputs published before plan.json.  Their
    # corruption is never an "aborted staged snapshot" condition.
    try:
        for ref in plan['operation_artifacts']:_verify_artifact_ref(policy,ref)
    except Exception as exc:
        raise TransactionError('operation artifact is invalid') from exc

    def _load_staged():
        parent,_,parent_hash=read_relative(policy,f'{snap}/parent-pointer.json')
        if plan['before']=='ABSENT':
            if parent!={'state':'ABSENT'}:raise TransactionError('transaction parent does not match before')
        elif parent_hash!=plan['before']:raise TransactionError('transaction parent does not match before')
        inter,_,ih=read_relative(policy,f'{snap}/interchange.json');prov,_,prh=read_relative(policy,f'{snap}/provenance.json')
        if ih!=plan['interchange_hash'] or prh!=plan['provenance_hash'] or parent_hash!=plan['parent_pointer_hash']:raise TransactionError('staged snapshot hash mismatch')
        _validate_operation_semantics(policy,plan,parent,inter,prov)
        return parent,parent_hash,inter,prov

    # Terminal states are irreversible.  An aborted transaction may only remain
    # aborted when current is still before, no commit exists, and the staged set
    # genuinely cannot be completed.  A fully valid staged set contradicts an
    # already-published aborted terminal state and must fail closed.
    if state and state['status']=='aborted':
        if current_hash!=plan['before']:raise TransactionError('aborted transaction current pointer contradiction')
        if commit is not None:raise TransactionError('aborted transaction has commit')
        try:_load_staged()
        except Exception:return None
        raise TransactionError('aborted transaction has completable staged snapshot')

    try:
        parent,parent_hash,inter,prov=_load_staged()
    except Exception as exc:
        if state and state.get('status')=='complete':
            raise TransactionError('complete transaction staged snapshot is invalid') from exc
        if current_hash==plan['before'] and commit is None:
            aborted={'schema_version':'1.0','transaction_id':txid,'plan_hash':ph,'sequence':3,'status':'aborted'};write_atomic_json(policy,txstate,aborted);return None
        raise TransactionError('staged snapshot is invalid') from exc

    if state and state['status']=='complete':
        if commit is None:raise TransactionError('complete transaction has no commit')
        expected=_expected_pointer(dataset_id=inter['manifest']['dataset_id'],plan=plan,commit_hash=commit_hash,parent_hash=parent_hash,parent_obj=parent)
        expected_hash=digest_bytes(workspace_json_bytes(expected))
        if current_hash==expected_hash and current_obj==expected:
            verify_snapshot_pointer(policy,expected);return TransactionResult(txid,plan['snapshot_id'],state_hash,expected_hash,commit_hash)
        if current_obj and _is_descendant_of(policy,current_obj,expected):
            verify_snapshot_pointer(policy,expected);return TransactionResult(txid,plan['snapshot_id'],state_hash,expected_hash,commit_hash)
        raise TransactionError('complete transaction current pointer contradiction')

    if commit is None:
        if state and state.get('status')=='publishing':raise TransactionError('publishing transaction has no commit')
        commit=_expected_commit(plan,ph);_,commit_hash=write_immutable_json(policy,commit_path,commit)
    expected=_expected_pointer(dataset_id=inter['manifest']['dataset_id'],plan=plan,commit_hash=commit_hash,parent_hash=parent_hash,parent_obj=parent)
    expected_hash=digest_bytes(workspace_json_bytes(expected))
    if current_hash==plan['before']:
        write_atomic_json(policy,txstate,{'schema_version':'1.0','transaction_id':txid,'plan_hash':ph,'sequence':2,'status':'publishing'})
        write_atomic_json(policy,'state/answer-association/current.json',expected);current_hash,current_obj=current_pointer(policy)
    if current_hash==expected_hash and current_obj==expected:
        _,sh=write_atomic_json(policy,txstate,{'schema_version':'1.0','transaction_id':txid,'plan_hash':ph,'sequence':3,'status':'complete'});verify_snapshot_pointer(policy,expected);return TransactionResult(txid,plan['snapshot_id'],sh,expected_hash,commit_hash)
    raise TransactionError('transaction current pointer is unknown')

def recover_all_transactions(policy:RootPolicy):
    root=policy.workspace_root/'transactions/answer-association'
    if not root.exists():return []
    out=[]
    for d in sorted(root.iterdir(),key=lambda x:x.name):
        if d.is_dir() and (d/'plan.json').exists():out.append((d.name,recover_transaction(policy,d.name)))
    return out
