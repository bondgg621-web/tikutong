"""Stdlib-only M3 contract validation with frozen branch semantics."""
from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any

UUID_RE=re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
HASH_RE=re.compile(r'^[0-9a-f]{64}$')
TS_RE=re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$')

class ContractError(ValueError): pass

def schema_root()->Path: return Path(__file__).resolve().parents[2]/'schemas/m3'
def schema_path(name:str)->Path:
    path=schema_root()/name
    if path.parent!=schema_root(): raise ContractError('schema path escaped M3 schema root')
    return path

def load_schema(name:str)->dict:
    try:v=json.loads(schema_path(name).read_text(encoding='utf-8'))
    except Exception as exc: raise ContractError('M3 schema could not be loaded') from exc
    if type(v) is not dict: raise ContractError('M3 schema root must be object')
    return v

def _exact(v:dict,keys:set[str],ctx:str):
    if type(v) is not dict or set(v)!=keys: raise ContractError(f'{ctx} fields are not exact')
def _uuid(v,ctx):
    if type(v) is not str or not UUID_RE.fullmatch(v): raise ContractError(f'{ctx} must be UUID')
def _hash(v,ctx):
    if type(v) is not str or not HASH_RE.fullmatch(v): raise ContractError(f'{ctx} must be hash')
def _ptr(v,ctx):
    if v!='ABSENT': _hash(v,ctx)
def _rel(v,ctx):
    if type(v) is not str or not v or '\\' in v or v.startswith('/') or re.match(r'^[A-Za-z]:',v) or '..' in Path(v).parts: raise ContractError(f'{ctx} must be workspace relative')
def _ts(v,ctx):
    if type(v) is not str or not TS_RE.fullmatch(v): raise ContractError(f'{ctx} must be UTC Z')
def _list(v,ctx):
    if type(v) is not list: raise ContractError(f'{ctx} must be array')

def validate_evidence(e:dict,ctx='evidence'):
    keys={'evidence_id','source_id','source_revision','locator','question_number','source_lexeme','evidence_fingerprint','resolved_option_id'}; _exact(e,keys,ctx)
    _uuid(e['evidence_id'],ctx+'.evidence_id');_uuid(e['source_id'],ctx+'.source_id');_hash(e['evidence_fingerprint'],ctx+'.evidence_fingerprint')
    if type(e['source_revision']) is not int or e['source_revision']<1: raise ContractError(ctx+'.source_revision')
    if type(e['question_number']) is not int or e['question_number']<1: raise ContractError(ctx+'.question_number')
    if type(e['locator']) is not str or not re.fullmatch(r'line:[1-9][0-9]*',e['locator']): raise ContractError(ctx+'.locator')
    if type(e['source_lexeme']) is not str or not re.fullmatch(r'[A-Z]',e['source_lexeme']): raise ContractError(ctx+'.source_lexeme')
    if e['resolved_option_id'] is not None:_uuid(e['resolved_option_id'],ctx+'.resolved_option_id')

def validate_proposal(v:dict):
    keys={'schema_version','proposal_run_id','manifest_path','manifest_hash','candidate_artifact_path','candidate_artifact_hash','question_source_id','prepared_from_pointer','confirmation_base','entries'};_exact(v,keys,'proposal')
    if v['schema_version']!='1.0':raise ContractError('proposal schema_version')
    _uuid(v['proposal_run_id'],'proposal_run_id');_rel(v['manifest_path'],'manifest_path');_hash(v['manifest_hash'],'manifest_hash');_rel(v['candidate_artifact_path'],'candidate_artifact_path');_hash(v['candidate_artifact_hash'],'candidate_artifact_hash');_uuid(v['question_source_id'],'question_source_id');_ptr(v['prepared_from_pointer'],'prepared_from_pointer')
    b=v['confirmation_base']
    if type(b) is not dict or b.get('kind') not in {'direct','prepare_result'}:raise ContractError('confirmation_base')
    if b['kind']=='direct':_exact(b,{'kind'},'confirmation_base')
    else:_exact(b,{'kind','transaction_id','snapshot_id'},'confirmation_base');_uuid(b['transaction_id'],'confirmation_base.transaction_id');_uuid(b['snapshot_id'],'confirmation_base.snapshot_id')
    _list(v['entries'],'proposal.entries')
    seen=set()
    for i,e in enumerate(v['entries']):
        common={'proposal_id','candidate_id','candidate_revision','question_locator','question_number','conclusion','proposed_option_id','proposed_source_label','alternatives','evidence','review_item_id','decision_id','review_issue_key','adjudication'};_exact(e,common,f'entry[{i}]')
        _uuid(e['proposal_id'],'proposal_id')
        if e['proposal_id'] in seen:raise ContractError('duplicate proposal_id')
        seen.add(e['proposal_id']); c=e['conclusion']
        if c not in {'confirmable','conflict','missing','low_confidence','adjudicated','stale'}:raise ContractError('proposal conclusion')
        if e['candidate_id'] is None:
            if c!='low_confidence' or e['candidate_revision'] is not None or e['question_locator'] is not None:raise ContractError('source-level entry branch')
        else:
            _uuid(e['candidate_id'],'candidate_id')
            if type(e['candidate_revision']) is not int or e['candidate_revision']<1:raise ContractError('candidate_revision')
            if type(e['question_locator']) is not str or not e['question_locator']:raise ContractError('question_locator')
        if type(e['question_number']) is not int or e['question_number']<1:raise ContractError('question_number')
        if e['proposed_option_id'] is not None:_uuid(e['proposed_option_id'],'proposed_option_id')
        if e['proposed_source_label'] is not None and (type(e['proposed_source_label']) is not str or not re.fullmatch(r'[A-Z]',e['proposed_source_label'])):raise ContractError('proposed_source_label')
        _list(e['alternatives'],'alternatives');_list(e['evidence'],'evidence')
        for x in e['evidence']:validate_evidence(x)
        if e['review_item_id'] is not None:_uuid(e['review_item_id'],'review_item_id')
        if e['decision_id'] is not None:_uuid(e['decision_id'],'decision_id')
        if e['review_issue_key'] is not None:_hash(e['review_issue_key'],'review_issue_key')
        if c=='confirmable' and (e['proposed_option_id'] is None or not e['evidence'] or e['review_item_id'] is not None):raise ContractError('confirmable branch')
        if c=='missing' and (e['evidence'] or e['proposed_option_id'] is not None or e['review_item_id'] is None):raise ContractError('missing branch')
        if c=='conflict' and (not e['evidence'] or e['review_item_id'] is None):raise ContractError('conflict branch')
        if c=='low_confidence' and e['review_item_id'] is None:raise ContractError('low_confidence branch')
        if c=='adjudicated' and (e['decision_id'] is None or e['review_item_id'] is not None or type(e['adjudication']) is not dict):raise ContractError('adjudicated branch')
        if c=='stale':
            if e['decision_id'] is None or e['review_item_id'] is None or e['review_issue_key'] is None or e['evidence'] or e['alternatives'] or e['proposed_option_id'] is not None or e['proposed_source_label'] is not None:raise ContractError('stale branch')

def validate_confirmation(v:dict):
    keys={'schema_version','confirmation_id','proposal_run_id','proposal_path','proposal_hash','expected_candidate_hash','expected_current_pointer','request','considered_semantic_keys','selected_semantic_keys','rejected_semantic_keys','result_transaction_id','result_snapshot_id','recorded_at'};_exact(v,keys,'confirmation')
    for k in ('confirmation_id','proposal_run_id','result_transaction_id','result_snapshot_id'):_uuid(v[k],k)
    for k in ('proposal_hash','expected_candidate_hash'):_hash(v[k],k)
    _rel(v['proposal_path'],'proposal_path');_ptr(v['expected_current_pointer'],'expected_current_pointer');_ts(v['recorded_at'],'recorded_at')
    req=v['request'];_exact(req,{'action','proposal_ids','selected_evidence_ids'},'confirmation.request')
    if req['action'] not in {'confirm','confirm_all_unambiguous','choose_evidence','reject','reject_association','retain_unresolved','archive_stale'}:raise ContractError('confirmation action')
    if type(req['proposal_ids']) is not list or not req['proposal_ids']:raise ContractError('proposal_ids')
    for x in req['proposal_ids']:_uuid(x,'proposal_id')
    if type(req['selected_evidence_ids']) is not list:raise ContractError('selected_evidence_ids')
    for x in req['selected_evidence_ids']:_uuid(x,'evidence_id')
    action=req['action']
    if action!='confirm_all_unambiguous' and len(req['proposal_ids'])!=1:raise ContractError('confirmation action proposal cardinality')
    if action=='choose_evidence':
        if not req['selected_evidence_ids']:raise ContractError('choose_evidence requires selected evidence')
    elif req['selected_evidence_ids']:
        raise ContractError('confirmation action forbids selected evidence')
    for field in ('considered_semantic_keys','selected_semantic_keys','rejected_semantic_keys'):
        if type(v[field]) is not list:raise ContractError(field)
        for row in v[field]:
            if type(row) is not list or len(row)!=3:raise ContractError(field);_uuid(row[0],field);_hash(row[2],field)

def _semantic_key(row,ctx):
    if type(row) is not list or len(row)!=3:raise ContractError(ctx+' must be semantic key')
    _uuid(row[0],ctx+'.source_id')
    if type(row[1]) is not int or row[1]<1:raise ContractError(ctx+'.question_number')
    _hash(row[2],ctx+'.evidence_fingerprint')

def _uuid_list(v,ctx,*,nonempty=False):
    if type(v) is not list or (nonempty and not v):raise ContractError(ctx)
    for x in v:_uuid(x,ctx)

def _semantic_key_list(v,ctx):
    if type(v) is not list:raise ContractError(ctx)
    for i,row in enumerate(v):_semantic_key(row,f'{ctx}[{i}]')

def _nullable_rel_hash_pair(path_value,hash_value,ctx):
    if path_value is None or hash_value is None:
        if path_value is not None or hash_value is not None:raise ContractError(ctx+' path/hash pair')
        return False
    _rel(path_value,ctx+'.path');_hash(hash_value,ctx+'.hash');return True

def _validate_current_instance(v,ctx):
    keys={'source_id','source_revision','locator','question_number','evidence_fingerprint','resolved_option_id'};_exact(v,keys,ctx)
    _uuid(v['source_id'],ctx+'.source_id');_hash(v['evidence_fingerprint'],ctx+'.evidence_fingerprint')
    if type(v['source_revision']) is not int or v['source_revision']<1:raise ContractError(ctx+'.source_revision')
    if type(v['question_number']) is not int or v['question_number']<1:raise ContractError(ctx+'.question_number')
    if type(v['locator']) is not str or not re.fullmatch(r'line:[1-9][0-9]*',v['locator']):raise ContractError(ctx+'.locator')
    if v['resolved_option_id'] is not None:_uuid(v['resolved_option_id'],ctx+'.resolved_option_id')

def _validate_historical_instance(v,ctx):
    keys={'source_id','source_revision','locator','evidence_fingerprint'};_exact(v,keys,ctx)
    _uuid(v['source_id'],ctx+'.source_id');_hash(v['evidence_fingerprint'],ctx+'.evidence_fingerprint')
    if type(v['source_revision']) is not int or v['source_revision']<1:raise ContractError(ctx+'.source_revision')
    if type(v['locator']) is not str or not v['locator']:raise ContractError(ctx+'.locator')

def _validate_stale_evidence(v,ctx):
    keys={'source_id','question_number','evidence_fingerprint','resolved_option_id'};_exact(v,keys,ctx)
    _uuid(v['source_id'],ctx+'.source_id');_hash(v['evidence_fingerprint'],ctx+'.evidence_fingerprint')
    if type(v['question_number']) is not int or v['question_number']<1:raise ContractError(ctx+'.question_number')
    if v['resolved_option_id'] is not None:_uuid(v['resolved_option_id'],ctx+'.resolved_option_id')

def validate_reverify(v:dict):
    keys={'schema_version','reverify_id','scope','expected_before_pointer','question_source_id','manifest_path','manifest_hash','required_decision_ids','answer_source_ids','unavailable_source_ids','results','recorded_at','result_transaction_id','result_snapshot_id'};_exact(v,keys,'reverify')
    if v['schema_version']!='1.0':raise ContractError('reverify schema')
    for k in ('reverify_id','question_source_id','result_transaction_id','result_snapshot_id'):_uuid(v[k],k)
    _hash(v['expected_before_pointer'],'expected_before_pointer');_rel(v['manifest_path'],'manifest_path');_hash(v['manifest_hash'],'manifest_hash');_ts(v['recorded_at'],'recorded_at')
    sc=v['scope']
    if type(sc) is not dict or sc.get('kind') not in {'decision','question_source'}:raise ContractError('reverify scope')
    if sc['kind']=='decision':_exact(sc,{'kind','decision_id'},'scope');_uuid(sc['decision_id'],'decision_id')
    else:_exact(sc,{'kind','question_source_id'},'scope');_uuid(sc['question_source_id'],'question_source_id')
    _uuid_list(v['required_decision_ids'],'required_decision_ids',nonempty=True);_uuid_list(v['answer_source_ids'],'answer_source_ids',nonempty=True);_uuid_list(v['unavailable_source_ids'],'unavailable_source_ids')
    if len(set(v['required_decision_ids']))!=len(v['required_decision_ids']) or len(set(v['answer_source_ids']))!=len(v['answer_source_ids']) or len(set(v['unavailable_source_ids']))!=len(v['unavailable_source_ids']):raise ContractError('reverify sets contain duplicates')
    if type(v['results']) is not list or len(v['results'])!=len(v['required_decision_ids']):raise ContractError('reverify results cardinality')
    result_ids=[]
    for ri,r in enumerate(v['results']):
        ctx=f'reverify.results[{ri}]';rkeys={'decision_id','result','issue_code','review_item_id','current_conclusion','original_source_ids','current_source_ids','current_semantic_keys','current_evidence','mappings'};_exact(r,rkeys,ctx);_uuid(r['decision_id'],ctx+'.decision_id');result_ids.append(r['decision_id'])
        if r['result'] not in {'valid','needs_revalidation'}:raise ContractError(ctx+'.result')
        if r['issue_code'] not in {None,'QB-DECISION-STALE','QB-ANSWER-CONFLICT'}:raise ContractError(ctx+'.issue_code')
        if r['review_item_id'] is not None:_uuid(r['review_item_id'],ctx+'.review_item_id')
        if r['current_conclusion'] not in {'confirmable','conflict','missing','low_confidence','adjudicated'}:raise ContractError(ctx+'.current_conclusion')
        _uuid_list(r['original_source_ids'],ctx+'.original_source_ids',nonempty=True);_uuid_list(r['current_source_ids'],ctx+'.current_source_ids',nonempty=True)
        if len(set(r['original_source_ids']))!=len(r['original_source_ids']) or len(set(r['current_source_ids']))!=len(r['current_source_ids']):raise ContractError(ctx+' source set duplicate')
        _semantic_key_list(r['current_semantic_keys'],ctx+'.current_semantic_keys')
        if type(r['current_evidence']) is not list:raise ContractError(ctx+'.current_evidence')
        for ei,e in enumerate(r['current_evidence']):validate_evidence(e,f'{ctx}.current_evidence[{ei}]')
        if type(r['mappings']) is not list:raise ContractError(ctx+'.mappings')
        for mi,m in enumerate(r['mappings']):
            mctx=f'{ctx}.mappings[{mi}]';_exact(m,{'historical_instance','current_semantic_key','current_instances'},mctx);_validate_historical_instance(m['historical_instance'],mctx+'.historical_instance')
            if m['current_semantic_key'] is not None:_semantic_key(m['current_semantic_key'],mctx+'.current_semantic_key')
            if type(m['current_instances']) is not list:raise ContractError(mctx+'.current_instances')
            for ii,inst in enumerate(m['current_instances']):_validate_current_instance(inst,f'{mctx}.current_instances[{ii}]')
        if r['result']=='valid' and (r['issue_code'] is not None or r['review_item_id'] is not None):raise ContractError(ctx+' valid result carries issue')
        if r['result']=='needs_revalidation' and (r['issue_code'] is None or r['review_item_id'] is None):raise ContractError(ctx+' needs_revalidation lacks issue binding')
    if result_ids!=v['required_decision_ids']:raise ContractError('reverify results order/set mismatch')

def validate_provenance(v:dict):
    keys={'schema_version','snapshot_id','dataset_id','decision_links','review_links','confirmation_audits','reverify_audits','stale_audits'};_exact(v,keys,'provenance')
    if v['schema_version']!='1.0':raise ContractError('provenance schema')
    _uuid(v['snapshot_id'],'snapshot_id');_uuid(v['dataset_id'],'dataset_id')
    for field in ('decision_links','review_links','confirmation_audits','reverify_audits','stale_audits'):
        if type(v[field]) is not list:raise ContractError(field)
    for i,link in enumerate(v['decision_links']):
        ctx=f'decision_links[{i}]';ks={'decision_id','candidate_id','proposal_path','proposal_hash','confirmation_path','confirmation_hash','manifest_path','manifest_hash','question_source_id','answer_source_ids','selected_semantic_keys','rejected_semantic_keys','adjudication','reverify_audits'};_exact(link,ks,ctx)
        _uuid(link['decision_id'],ctx+'.decision_id');_uuid(link['candidate_id'],ctx+'.candidate_id');_rel(link['proposal_path'],ctx+'.proposal_path');_hash(link['proposal_hash'],ctx+'.proposal_hash');_rel(link['confirmation_path'],ctx+'.confirmation_path');_hash(link['confirmation_hash'],ctx+'.confirmation_hash');_rel(link['manifest_path'],ctx+'.manifest_path');_hash(link['manifest_hash'],ctx+'.manifest_hash');_uuid(link['question_source_id'],ctx+'.question_source_id')
        _uuid_list(link['answer_source_ids'],ctx+'.answer_source_ids',nonempty=True);_semantic_key_list(link['selected_semantic_keys'],ctx+'.selected_semantic_keys');_semantic_key_list(link['rejected_semantic_keys'],ctx+'.rejected_semantic_keys')
        if link['adjudication'] is not None:
            a=link['adjudication'];_exact(a,{'answer_source_ids','selected_semantic_keys','rejected_semantic_keys'},ctx+'.adjudication');_uuid_list(a['answer_source_ids'],ctx+'.adjudication.answer_source_ids',nonempty=True);_semantic_key_list(a['selected_semantic_keys'],ctx+'.adjudication.selected_semantic_keys');_semantic_key_list(a['rejected_semantic_keys'],ctx+'.adjudication.rejected_semantic_keys')
        if type(link['reverify_audits']) is not list:raise ContractError(ctx+'.reverify_audits')
        for ai,a in enumerate(link['reverify_audits']):
            actx=f'{ctx}.reverify_audits[{ai}]';_exact(a,{'reverify_path','reverify_hash','source_revisions'},actx);_rel(a['reverify_path'],actx+'.reverify_path');_hash(a['reverify_hash'],actx+'.reverify_hash')
            if type(a['source_revisions']) is not dict or not a['source_revisions']:raise ContractError(actx+'.source_revisions')
            for sid,rev in a['source_revisions'].items():_uuid(sid,actx+'.source_id');
            for rev in a['source_revisions'].values():
                if type(rev) is not int or rev<1:raise ContractError(actx+'.source_revision')
    for i,link in enumerate(v['review_links']):
        ctx=f'review_links[{i}]';ks={'review_id','review_issue_key','question_source_id','proposal_path','proposal_hash','reverify_path','reverify_hash','supersedes_review_id'};_exact(link,ks,ctx);_uuid(link['review_id'],ctx+'.review_id');_hash(link['review_issue_key'],ctx+'.review_issue_key');_uuid(link['question_source_id'],ctx+'.question_source_id')
        proposal_origin=_nullable_rel_hash_pair(link['proposal_path'],link['proposal_hash'],ctx+'.proposal')
        reverify_origin=_nullable_rel_hash_pair(link['reverify_path'],link['reverify_hash'],ctx+'.reverify')
        if proposal_origin==reverify_origin:raise ContractError(ctx+' must bind exactly one origin')
        if link['supersedes_review_id'] is not None:_uuid(link['supersedes_review_id'],ctx+'.supersedes_review_id')
    for i,a in enumerate(v['confirmation_audits']):
        ctx=f'confirmation_audits[{i}]';ks={'confirmation_id','confirmation_path','confirmation_hash','proposal_path','proposal_hash','transaction_id','snapshot_id'};_exact(a,ks,ctx);_uuid(a['confirmation_id'],ctx+'.confirmation_id');_rel(a['confirmation_path'],ctx+'.confirmation_path');_hash(a['confirmation_hash'],ctx+'.confirmation_hash');_rel(a['proposal_path'],ctx+'.proposal_path');_hash(a['proposal_hash'],ctx+'.proposal_hash');_uuid(a['transaction_id'],ctx+'.transaction_id');_uuid(a['snapshot_id'],ctx+'.snapshot_id')
    for i,a in enumerate(v['reverify_audits']):
        ctx=f'reverify_audits[{i}]';ks={'reverify_id','reverify_path','reverify_hash','decision_ids'};_exact(a,ks,ctx);_uuid(a['reverify_id'],ctx+'.reverify_id');_rel(a['reverify_path'],ctx+'.reverify_path');_hash(a['reverify_hash'],ctx+'.reverify_hash');_uuid_list(a['decision_ids'],ctx+'.decision_ids',nonempty=True)
    for i,a in enumerate(v['stale_audits']):
        ctx=f'stale_audits[{i}]';ks={'decision_id','review_id','review_issue_key','question_source_id','candidate_revision','answer_source_ids','evidence_group','manifest_path','manifest_hash'};_exact(a,ks,ctx);_uuid(a['decision_id'],ctx+'.decision_id');_uuid(a['review_id'],ctx+'.review_id');_hash(a['review_issue_key'],ctx+'.review_issue_key');_uuid(a['question_source_id'],ctx+'.question_source_id')
        if type(a['candidate_revision']) is not int or a['candidate_revision']<1:raise ContractError(ctx+'.candidate_revision')
        _uuid_list(a['answer_source_ids'],ctx+'.answer_source_ids',nonempty=True)
        if type(a['evidence_group']) is not list:raise ContractError(ctx+'.evidence_group')
        for ei,e in enumerate(a['evidence_group']):_validate_stale_evidence(e,f'{ctx}.evidence_group[{ei}]')
        _rel(a['manifest_path'],ctx+'.manifest_path');_hash(a['manifest_hash'],ctx+'.manifest_hash')

def validate_plan(v:dict):
    keys={'schema_version','transaction_id','snapshot_id','operation','before','after_snapshot_path','parent_pointer_hash','interchange_hash','provenance_hash','operation_artifacts'};_exact(v,keys,'plan')
    if v['schema_version']!='1.0':raise ContractError('plan schema')
    _uuid(v['transaction_id'],'transaction_id');_uuid(v['snapshot_id'],'snapshot_id');_ptr(v['before'],'before');_rel(v['after_snapshot_path'],'after_snapshot_path')
    for f in ('parent_pointer_hash','interchange_hash','provenance_hash'):_hash(v[f],f)
    if v['operation'] not in {'prepare','confirm','reverify'}:raise ContractError('operation')
    if type(v['operation_artifacts']) is not list:raise ContractError('operation_artifacts')
    kinds=[]
    for a in v['operation_artifacts']:
        _exact(a,{'kind','relative_path','content_hash'},'operation_artifact');kinds.append(a['kind']);_rel(a['relative_path'],'relative_path');_hash(a['content_hash'],'content_hash')
    expected={'prepare':['manifest','proposal'],'confirm':['confirmation'],'reverify':['reverify']}[v['operation']]
    if kinds!=expected:raise ContractError('operation artifact whitelist mismatch')

def validate_state(v:dict):
    _exact(v,{'schema_version','transaction_id','plan_hash','sequence','status'},'state');_uuid(v['transaction_id'],'transaction_id');_hash(v['plan_hash'],'plan_hash')
    pair=(v['sequence'],v['status'])
    if pair not in {(1,'staged'),(2,'publishing'),(3,'complete'),(3,'aborted')}:raise ContractError('transaction state pair invalid')

def validate_commit(v:dict):
    _exact(v,{'schema_version','transaction_id','snapshot_id','plan_hash','parent_pointer_hash','interchange_hash','provenance_hash'},'commit')
    _uuid(v['transaction_id'],'transaction_id');_uuid(v['snapshot_id'],'snapshot_id')
    for f in ('plan_hash','parent_pointer_hash','interchange_hash','provenance_hash'):_hash(v[f],f)

def validate_pointer(v:dict,*,allow_absent=True):
    if v=={'state':'ABSENT'}:
        if not allow_absent:raise ContractError('current cannot be ABSENT object')
        return
    keys={'schema_version','dataset_id','snapshot_id','snapshot_path','commit_path','commit_hash','parent_pointer_hash','generation'};_exact(v,keys,'pointer')
    _uuid(v['dataset_id'],'dataset_id');_uuid(v['snapshot_id'],'snapshot_id');_rel(v['snapshot_path'],'snapshot_path');_rel(v['commit_path'],'commit_path');_hash(v['commit_hash'],'commit_hash');_hash(v['parent_pointer_hash'],'parent_pointer_hash')
    if type(v['generation']) is not int or v['generation']<1:raise ContractError('generation')

def validate_run(v:dict):
    keys={'schema_version','run_id','operation','status','phase','started_at','updated_at','artifacts','run_findings','result'};_exact(v,keys,'run')
    if v['schema_version']!='1.0':raise ContractError('run schema')
    _uuid(v['run_id'],'run_id');_ts(v['started_at'],'started_at');_ts(v['updated_at'],'updated_at')
    operations={'prepare','confirm','reverify','recover'}
    phases={'source_resolution','snapshot_validation','answer_parse','association','review','confirmation','publication','read_back','complete'}
    statuses={'running','complete','needs_confirmation','needs_review','failed'}
    if v['operation'] not in operations or v['status'] not in statuses or v['phase'] not in phases:raise ContractError('run enum')
    if type(v['artifacts']) is not list or type(v['run_findings']) is not list:raise ContractError('run arrays')
    for a in v['artifacts']:_exact(a,{'relative_path','content_hash'},'run.artifact');_rel(a['relative_path'],'relative_path');_hash(a['content_hash'],'content_hash')
    for f in v['run_findings']:
        _exact(f,{'issue_code','blocking_level','source_id','candidate_id','option_id'},'run.finding')
        if f['blocking_level'] not in {'blocking','review_required','informational'}:raise ContractError('finding level')
        for k in ('source_id','candidate_id','option_id'):
            if f[k] is not None:_uuid(f[k],k)
    status=v['status'];result=v['result'];operation=v['operation']
    if status=='running':
        if v['phase']=='complete' or result is not None:raise ContractError('running run terminal claim invalid')
        return
    if v['phase']!='complete':raise ContractError('terminal run phase must be complete')
    if status=='failed':
        if result is not None:raise ContractError('failed run cannot claim success result')
        return
    if type(result) is not dict:raise ContractError('successful terminal run must claim result')
    if set(result)=={'direct_pointer'}:
        if operation!='prepare':raise ContractError('direct success is prepare-only')
        pointer=result['direct_pointer']
        if pointer!='ABSENT':_hash(pointer,'direct_pointer')
    else:
        _exact(result,{'transaction_id','transaction_state_hash','snapshot_id','current_hash','commit_hash'},'run.result')
        _uuid(result['transaction_id'],'transaction_id');_hash(result['transaction_state_hash'],'transaction_state_hash');_uuid(result['snapshot_id'],'snapshot_id');_hash(result['current_hash'],'current_hash');_hash(result['commit_hash'],'commit_hash')
        if operation in {'confirm','reverify'} and status!='complete':raise ContractError('confirm/reverify success must be complete')
        if operation=='recover':raise ContractError('recover has no successful run branch')
