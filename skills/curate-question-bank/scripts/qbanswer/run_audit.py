"""Operational M3 run audit. Canonical truth never depends on this module."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path

from .artifacts import ABSENT,ArtifactError,current_pointer,read_json_bytes,read_relative,resolve_workspace,write_atomic_json
from .contracts import ContractError,validate_proposal,validate_run

class RunAuditError(RuntimeError):pass
TERMINAL={'complete','needs_confirmation','needs_review','failed'}
PHASE_ORDER=('source_resolution','snapshot_validation','answer_parse','association','review','confirmation','publication','read_back','complete')

def utc_now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def run_path(run_id):return f'runs/answer-association/{run_id}/run.json'
def new_run(*,run_id,operation,now=utc_now):
    t=now();return {'schema_version':'1.0','run_id':run_id,'operation':operation,'status':'running','phase':'source_resolution','started_at':t,'updated_at':t,'artifacts':[],'run_findings':[],'result':None}

def _immutable_prefix(v):return (v['schema_version'],v['run_id'],v['operation'],v['started_at'])
def write_run(policy,run:dict):
    path=resolve_workspace(policy,run_path(run['run_id']))
    if path.exists():
        old,_,_=read_json_bytes(path);validate_run(old)
        if _immutable_prefix(old)!=_immutable_prefix(run):raise RunAuditError('run immutable identity changed')
        if old['status'] in TERMINAL:
            if old!=run:raise RunAuditError('terminal run is immutable')
            return run
        # append-only artifact/finding and monotone phase progress
        if run['artifacts'][:len(old['artifacts'])]!=old['artifacts'] or run['run_findings'][:len(old['run_findings'])]!=old['run_findings']:raise RunAuditError('run audit history changed')
        if PHASE_ORDER.index(run['phase'])<PHASE_ORDER.index(old['phase']):raise RunAuditError('run phase moved backwards')
    validate_run(run);write_atomic_json(policy,run_path(run['run_id']),run);return run

def add_artifact(run,path,digest):
    ref={'relative_path':path,'content_hash':digest}
    if ref not in run['artifacts']:run['artifacts'].append(ref)

def finish_direct_prepare(policy,run,proposal,*,pointer_hash):
    if pointer_hash!=proposal['prepared_from_pointer']:raise RunAuditError('direct prepare pointer changed')
    open_review=any(e['conclusion'] in {'missing','conflict','low_confidence','stale'} for e in proposal['entries'])
    confirmable=any(e['conclusion']=='confirmable' for e in proposal['entries'])
    run['status']='needs_review' if open_review else ('needs_confirmation' if confirmable else 'complete');run['phase']='complete';run['updated_at']=utc_now();run['result']={'direct_pointer':pointer_hash};return write_run(policy,run)

def _infer_run_id(plan):
    paths=[x['relative_path'] for x in plan['operation_artifacts']]
    for p in paths:
        parts=Path(p).parts
        if len(parts)>=4 and parts[0]=='runs' and parts[1]=='answer-association':return parts[2]
    raise RunAuditError('transaction does not identify a run')
def _terminal_for_plan(policy,plan):
    if plan['operation'] in {'confirm','reverify'}:return 'complete'
    proposal_ref=next(x for x in plan['operation_artifacts'] if x['kind']=='proposal');proposal,_,_=read_relative(policy,proposal_ref['relative_path'])
    inter,_,_=read_relative(policy,f"{plan['after_snapshot_path']}/interchange.json")
    reviews={r['review_id']:r for r in inter['review_queue']['review_items']}
    open_review=any(e['review_item_id'] is not None and reviews.get(e['review_item_id'],{}).get('status')=='open' for e in proposal['entries'] if e['conclusion'] in {'missing','conflict','low_confidence','stale'})
    confirmable=any(e['conclusion']=='confirmable' for e in proposal['entries'])
    return 'needs_review' if open_review else ('needs_confirmation' if confirmable else 'complete')

def _expected_transaction_run_claim(policy,plan,state_hash):
    """Recompute the only permitted success claim from durable canonical facts.

    run.json is not canonical truth.  A successful terminal run may only mirror
    the already-verified complete transaction graph, so every reconciliation
    (including reconciliation of an existing terminal run) rebuilds this claim
    from immutable snapshot/transaction artifacts instead of trusting run.json.
    """
    current_obj_path=f"{plan['after_snapshot_path']}/commit.json"
    _,_,commit_hash=read_relative(policy,current_obj_path)
    from .transaction import _expected_pointer,verify_snapshot_pointer
    parent,_,parent_hash=read_relative(policy,f"{plan['after_snapshot_path']}/parent-pointer.json")
    inter,_,_=read_relative(policy,f"{plan['after_snapshot_path']}/interchange.json")
    expected=_expected_pointer(dataset_id=inter['manifest']['dataset_id'],plan=plan,commit_hash=commit_hash,parent_hash=parent_hash,parent_obj=parent)
    # This proves plan/state/commit/snapshot/operation semantics independently
    # of run.json.  The snapshot may be historical; verify_snapshot_pointer
    # validates its own complete graph and ancestry.
    verify_snapshot_pointer(policy,expected)
    from .artifacts import digest_bytes,workspace_json_bytes
    after_hash=digest_bytes(workspace_json_bytes(expected))
    return {
        'transaction_id':plan['transaction_id'],
        'transaction_state_hash':state_hash,
        'snapshot_id':plan['snapshot_id'],
        'current_hash':after_hash,
        'commit_hash':commit_hash,
    }

def _validate_terminal_transaction_run(policy,run,plan,state_hash):
    expected_status=_terminal_for_plan(policy,plan)
    expected_result=_expected_transaction_run_claim(policy,plan,state_hash)
    if run['operation']!=plan['operation']:
        raise RunAuditError('terminal run operation claim mismatch')
    if run['status']!=expected_status:
        raise RunAuditError('terminal run status claim mismatch')
    if run['result']!=expected_result:
        raise RunAuditError('terminal run canonical claim mismatch')
    required=[{'relative_path':r['relative_path'],'content_hash':r['content_hash']} for r in plan['operation_artifacts']]
    if any(ref not in run['artifacts'] for ref in required):
        raise RunAuditError('terminal run artifact claim mismatch')
    return run


def _historical_graph_for_pointer_hash(policy,pointer_hash):
    """Return the verified canonical graph at pointer_hash if it is on current ancestry."""
    if pointer_hash==ABSENT:
        return None
    current_hash,current_obj=current_pointer(policy)
    if current_obj is None:
        raise RunAuditError('direct prepare baseline is not canonical ancestry')
    from .transaction import verify_snapshot_pointer
    # Verify the current graph once before traversing historical parent pointers.
    verify_snapshot_pointer(policy,current_obj)
    cur_hash,cur_obj=current_hash,current_obj
    seen=set()
    while cur_obj and cur_obj!={'state':'ABSENT'}:
        sid=cur_obj.get('snapshot_id')
        if sid in seen:raise RunAuditError('direct prepare baseline ancestry cycle')
        seen.add(sid)
        if cur_hash==pointer_hash:
            return verify_snapshot_pointer(policy,cur_obj)
        parent,_,parent_hash=read_relative(policy,f"{cur_obj['snapshot_path']}/parent-pointer.json")
        if parent=={'state':'ABSENT'}:
            break
        cur_hash,cur_obj=parent_hash,parent
    raise RunAuditError('direct prepare baseline is not canonical ancestry')

def _validate_direct_review_bindings(proposal,manifest,graph):
    review_entries=[e for e in proposal['entries'] if e['conclusion'] in {'missing','conflict','low_confidence','stale'}]
    if not review_entries:return False
    if graph is None:raise RunAuditError('direct prepare cannot invent open review from ABSENT')
    inter=graph['interchange'];prov=graph['provenance']
    reviews={r['review_id']:r for r in inter['review_queue']['review_items']}
    links={x['review_id']:x for x in prov['review_links']}
    from .review import issue_for_conclusion,stable_issue_key
    answer_source_ids=[x['source_id'] for x in manifest['sources'] if x.get('kind')=='answer_document']
    for e in review_entries:
        rid=e.get('review_item_id');review=reviews.get(rid);link=links.get(rid)
        if rid is None or review is None or link is None:
            raise RunAuditError('direct prepare review binding is missing')
        if review.get('status')!='open' or review.get('issue_code')!=issue_for_conclusion(e['conclusion']):
            raise RunAuditError('direct prepare review binding is not open/current')
        expected_key=stable_issue_key(question_source_id=proposal['question_source_id'],candidate_id=e.get('candidate_id'),answer_source_ids=answer_source_ids,issue_code=review['issue_code'],evidence=e['evidence'])
        if review.get('candidate_id')!=e.get('candidate_id') or link.get('question_source_id')!=proposal['question_source_id'] or link.get('review_issue_key')!=expected_key:
            raise RunAuditError('direct prepare review binding mismatch')
        if e['conclusion']=='stale':
            if e.get('review_issue_key')!=expected_key:raise RunAuditError('direct stale review issue key mismatch')
            from .confirmation import _validate_archive_stale
            _validate_archive_stale(proposal=proposal,entry=e,parent=inter,parent_prov=prov)
    return True

def validate_direct_prepare_terminal_run(policy,run,proposal,*,proposal_path,proposal_hash):
    """Revalidate an existing direct-prepare success run without redoing business logic."""
    validate_run(run);validate_proposal(proposal)
    if run['status']=='failed' or run['status'] not in TERMINAL:
        raise RunAuditError('direct prepare run is not successful terminal')
    if run['operation']!='prepare' or proposal['proposal_run_id']!=run['run_id']:
        raise RunAuditError('direct prepare run identity mismatch')
    if proposal['confirmation_base']!={'kind':'direct'}:
        raise RunAuditError('direct prepare run has non-direct proposal')
    if run['result']!={'direct_pointer':proposal['prepared_from_pointer']}:
        raise RunAuditError('direct prepare canonical claim mismatch')
    # The immutable proposal and its manifest must still have exactly the hashes
    # recorded by the run/proposal.  run.json itself is never used as canonical truth.
    actual_proposal,_,actual_ph=read_relative(policy,proposal_path)
    if actual_ph!=proposal_hash or actual_proposal!=proposal:
        raise RunAuditError('direct prepare proposal artifact mismatch')
    manifest,_,actual_mh=read_relative(policy,proposal['manifest_path'])
    if actual_mh!=proposal['manifest_hash']:
        raise RunAuditError('direct prepare manifest artifact mismatch')
    required=[
        {'relative_path':proposal['manifest_path'],'content_hash':proposal['manifest_hash']},
        {'relative_path':proposal_path,'content_hash':proposal_hash},
    ]
    if any(ref not in run['artifacts'] for ref in required):
        raise RunAuditError('direct prepare artifact claim mismatch')
    graph=_historical_graph_for_pointer_hash(policy,proposal['prepared_from_pointer'])
    open_review=_validate_direct_review_bindings(proposal,manifest,graph)
    confirmable=any(e['conclusion']=='confirmable' for e in proposal['entries'])
    expected='needs_review' if open_review else ('needs_confirmation' if confirmable else 'complete')
    if run['status']!=expected:
        raise RunAuditError('direct prepare terminal status claim mismatch')
    return run

def reconcile_transaction_run(policy,transaction_result,*,now=utc_now):
    txid=transaction_result.transaction_id
    plan,_,_=read_relative(policy,f'transactions/answer-association/{txid}/plan.json')
    state,_,state_hash=read_relative(policy,f'transactions/answer-association/{txid}/state.json')
    if state['status']!='complete':raise RunAuditError('transaction is not complete')
    if plan['transaction_id']!=txid:
        raise RunAuditError('transaction plan identity mismatch')
    run_id=_infer_run_id(plan); path=resolve_workspace(policy,run_path(run_id))
    if path.exists():
        run,_,_=read_json_bytes(path);validate_run(run)
        if run['status'] in TERMINAL:
            if run['status']=='failed':raise RunAuditError('complete transaction conflicts with failed run')
            return _validate_terminal_transaction_run(policy,run,plan,state_hash)
    else:run=new_run(run_id=run_id,operation=plan['operation'],now=now)
    for ref in plan['operation_artifacts']:add_artifact(run,ref['relative_path'],ref['content_hash'])
    run['status']=_terminal_for_plan(policy,plan);run['phase']='complete';run['updated_at']=now();run['result']=_expected_transaction_run_claim(policy,plan,state_hash)
    return write_run(policy,run)
