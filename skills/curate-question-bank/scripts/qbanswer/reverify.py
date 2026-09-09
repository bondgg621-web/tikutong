"""Explicit revalidation and safe answer-evidence invalidation."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from uuid import uuid4

from qbcore.paths import validate_roots
from qbcore.parse_service import SourceResolutionError
from .answer_parser import AnswerParseError,parse_answer_text
from .artifacts import digest_value,read_relative,write_immutable_json
from .association import adjudication_still_applies,raw_associate
from .contracts import validate_reverify
from .review import find_or_create_review,stable_issue_key
from .run_audit import add_artifact,new_run,reconcile_transaction_run,write_run
from .source_snapshot import SnapshotError,build_manifest,resolve_answer_sources,resolve_question_view
from .state_graph import find_decision_link
from .transaction import publish_transaction,read_current_verified,recover_all_transactions,workspace_lock

class ReverifyError(RuntimeError):pass

def _now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def _uuid():return uuid4()
def _sem(e):return [e['source_id'],e['question_number'],e['evidence_fingerprint']]
def _instance(e):return {'source_id':e['source_id'],'source_revision':e['source_revision'],'locator':e['locator'],'question_number':e['question_number'],'evidence_fingerprint':e['evidence_fingerprint'],'resolved_option_id':e.get('resolved_option_id')}
def _hist(e):return {'source_id':e['source_id'],'source_revision':e['source_revision'],'locator':e['locator'],'evidence_fingerprint':e['evidence_fingerprint']}

def _classify_current_facts(*,candidate,decision,link,current_conclusion,current_evidence,unavailable_source_ids,answer_source_ids,adjudication_outcome=None):
    if decision['status']=='needs_revalidation':
        # Reverify can never restore automatically.
        existing_issue='QB-ANSWER-CONFLICT' if current_conclusion=='conflict' else 'QB-DECISION-STALE'
        return 'needs_revalidation',existing_issue
    if adjudication_outcome=='stale':return 'needs_revalidation','QB-DECISION-STALE'
    if adjudication_outcome=='applies':return 'valid',None
    original=set(link['answer_source_ids'])
    if original.intersection(unavailable_source_ids):return 'needs_revalidation','QB-DECISION-STALE'
    resolved=decision['value']['resolved_option_ids'][0]
    # P1 may classify a raw conflict as adjudicated.
    if current_conclusion=='adjudicated':return 'valid',None
    if current_conclusion=='confirmable' and current_evidence and all(e.get('resolved_option_id')==resolved for e in current_evidence):
        hist={(e['source_id'],e['evidence_fingerprint']) for e in decision['evidence']}
        cur={(e['source_id'],e['evidence_fingerprint']) for e in current_evidence if e.get('resolved_option_id')==resolved}
        if hist.issubset(cur):return 'valid',None
        return 'needs_revalidation','QB-DECISION-STALE'
    if current_conclusion=='conflict':return 'needs_revalidation','QB-ANSWER-CONFLICT'
    return 'needs_revalidation','QB-DECISION-STALE'

def _required(parent,scope):
    decisions=parent['decisions']['decisions'];cands={c['candidate_id']:c for c in parent['candidates']['candidates']}
    if scope['kind']=='decision':
        xs=[d for d in decisions if d['decision_id']==scope['decision_id'] and d['decision_type']=='answer_resolution' and d['status'] in {'valid','needs_revalidation'}]
        if len(xs)!=1:raise ReverifyError('required Decision is not current')
        cid=xs[0]['candidate_id'];others=[d for d in decisions if d['candidate_id']==cid and d['decision_type']=='answer_resolution' and d['status'] in {'valid','needs_revalidation'}]
        if len(others)!=1:raise ReverifyError('Decision uniqueness is corrupt')
        return xs
    qsid=scope['question_source_id'];cids={c['candidate_id'] for c in cands.values() if c['source_id']==qsid}
    xs=[d for d in decisions if d['candidate_id'] in cids and d['decision_type']=='answer_resolution' and d['status'] in {'valid','needs_revalidation'}]
    by={d['candidate_id']:d for d in xs}
    for c in cands.values():
        if c['source_id']==qsid and c['status']=='validated' and c['candidate_id'] not in by:raise ReverifyError('validated Candidate has no required Decision')
    return sorted(xs,key=lambda d:d['decision_id'])

def reverify_locked(*,input_root,workspace_root,scope,additional_answer_source_ids,expected_candidate_hash,expected_pointer,now=_now,uuid_factory=_uuid):
    policy=validate_roots(input_root,workspace_root);recover_all_transactions(policy);actual,verified=read_current_verified(policy)
    if verified is None or actual!=expected_pointer:raise ReverifyError('reverify current pointer mismatch')
    parent=verified['interchange'];parent_prov=verified['provenance'];required=_required(parent,scope)
    question_source_id=scope.get('question_source_id')
    if question_source_id is None:
        link=find_decision_link(parent_prov,required[0]['decision_id']);question_source_id=link['question_source_id']
    policy,qs,candidate_doc,views,candidate_hash=resolve_question_view(input_root=input_root,workspace_root=workspace_root,question_source_id=question_source_id,expected_candidate_hash=expected_candidate_hash)
    cmap={c['candidate_id']:c for c in views}
    # per-decision source set + union
    links={d['decision_id']:find_decision_link(parent_prov,d['decision_id']) for d in required}
    additions=sorted(set(additional_answer_source_ids or [])); union=set(additions)
    for d in required:union.update(links[d['decision_id']]['answer_source_ids'])
    records=[];snaps=[];unavailable=[]
    for sid in sorted(union):
        try:
            ss,rr=resolve_answer_sources(input_root=input_root,workspace_root=workspace_root,answer_source_ids=[sid],uuid_factory=uuid_factory,parse_func=parse_answer_text);snaps.extend(ss);records.extend([x.as_dict() for x in rr])
        except (SnapshotError,SourceResolutionError,AnswerParseError):unavailable.append(sid)
    # current manifest can only advance sources that were safely resolved; unavailable historical sources remain parent-known.
    merged=build_manifest(workspace_root=workspace_root,question_snapshot=qs,answer_snapshots=snaps,parent_manifest=parent['manifest'])
    child=deepcopy(parent);child['manifest']=merged;prov=deepcopy(parent_prov);reviews=child['review_queue']['review_items'];child_dec={d['decision_id']:d for d in child['decisions']['decisions']};child_cand={c['candidate_id']:c for c in child['candidates']['candidates']}
    txid=str(uuid_factory());sid=str(uuid_factory());rvid=str(uuid_factory());rpath=f'runs/answer-association/{rvid}/reverify.json'
    results=[];pending_reviews=[];pending_stale=[]
    for d in required:
        cand=cmap.get(d['candidate_id'])
        if not cand:raise ReverifyError('Decision Candidate identity is unavailable')
        link=links[d['decision_id']];current_sources=sorted(set(link['answer_source_ids'])|set(additions));subset=[e for e in records if e['source_id'] in current_sources]
        raw,_=raw_associate([cand],subset);entry=raw[0]
        current_conclusion=entry['conclusion']
        if current_conclusion=='confirmable' and entry.get('proposed_option_id')!=d['value']['resolved_option_ids'][0]:
            current_conclusion='conflict'
        p1_outcome=None
        if link.get('adjudication'):
            p1_outcome=adjudication_still_applies(candidate=cand,decision=d,original=link['adjudication'],current_evidence=entry['evidence'],current_conclusion=current_conclusion,answer_source_ids=current_sources,return_outcome=True)
            if p1_outcome=='invalid':raise ReverifyError('historical adjudication binding is no longer valid')
            if p1_outcome=='applies':current_conclusion='adjudicated'
            elif p1_outcome=='conflict':current_conclusion='conflict'
        current_evidence=deepcopy(entry['evidence'])
        result,issue=_classify_current_facts(candidate=cand,decision=d,link=link,current_conclusion=current_conclusion,current_evidence=current_evidence,unavailable_source_ids=unavailable,answer_source_ids=current_sources,adjudication_outcome=p1_outcome)
        # Historical -> current mapping.
        mappings=[]
        qnum=cand['_question_number']
        for old in d['evidence']:
            matches=[e for e in current_evidence if e['source_id']==old['source_id'] and e['evidence_fingerprint']==old['evidence_fingerprint']]
            mappings.append({'historical_instance':_hist(old),'current_semantic_key':[old['source_id'],qnum,old['evidence_fingerprint']] if matches else None,'current_instances':[_instance(e) for e in matches]})
        review_id=None
        if result=='needs_revalidation':
            issue=issue or 'QB-DECISION-STALE'; evidence=current_evidence if issue=='QB-ANSWER-CONFLICT' else [{'source_id':e['source_id'],'question_number':qnum,'evidence_fingerprint':e['evidence_fingerprint'],'resolved_option_id':d['value']['resolved_option_ids'][0]} for e in d['evidence']]
            key=stable_issue_key(question_source_id=question_source_id,candidate_id=cand['candidate_id'],answer_source_ids=current_sources,issue_code=issue,evidence=evidence)
            item,sup,new=find_or_create_review(reviews=reviews,provenance=prov,issue_key=key,candidate_id=cand['candidate_id'],issue_code=issue,uuid_factory=uuid_factory);review_id=item['review_id']
            if new:pending_reviews.append((item,key,sup))
            child_dec[d['decision_id']]['status']='needs_revalidation';child_cand[cand['candidate_id']]['status']='candidate'
            if issue=='QB-DECISION-STALE':pending_stale.append((d,item,key,evidence,current_sources,cand['candidate_revision']))
        # valid stays valid; needs_revalidation never auto-recovers
        results.append({'decision_id':d['decision_id'],'result':result,'issue_code':issue if result=='needs_revalidation' else None,'review_item_id':review_id,'current_conclusion':current_conclusion,'original_source_ids':sorted(link['answer_source_ids']),'current_source_ids':current_sources,'current_semantic_keys':sorted({_sem(e)[0]+'|'+str(_sem(e)[1])+'|'+_sem(e)[2] for e in current_evidence}), 'current_evidence':current_evidence,'mappings':mappings})
    # convert semantic key string staging to proper arrays deterministically
    for r in results:r['current_semantic_keys']=[[x.split('|',2)[0],int(x.split('|',2)[1]),x.split('|',2)[2]] for x in r['current_semantic_keys']]
    manifest_run={'schema_version':'1.0','dataset_id':merged['dataset_id'],'sources':[x for x in merged['sources'] if x['source_id'] in {question_source_id,*union}]}
    mpath=f'runs/answer-association/{rvid}/manifest.json';mpath,mhash=write_immutable_json(policy,mpath,manifest_run)
    rv={'schema_version':'1.0','reverify_id':rvid,'scope':deepcopy(scope),'expected_before_pointer':actual,'question_source_id':question_source_id,'manifest_path':mpath,'manifest_hash':mhash,'required_decision_ids':[d['decision_id'] for d in required],'answer_source_ids':sorted(union),'unavailable_source_ids':sorted(unavailable),'results':results,'recorded_at':now(),'result_transaction_id':txid,'result_snapshot_id':sid}
    validate_reverify(rv);rv_hash=digest_value(rv)
    # provenance now binds exact reverify artifact.
    for item,key,sup in pending_reviews:prov['review_links'].append({'review_id':item['review_id'],'review_issue_key':key,'question_source_id':question_source_id,'proposal_path':None,'proposal_hash':None,'reverify_path':rpath,'reverify_hash':rv_hash,'supersedes_review_id':sup})
    for d,item,key,evidence,srcs,rev in pending_stale:prov['stale_audits'].append({'decision_id':d['decision_id'],'review_id':item['review_id'],'review_issue_key':key,'question_source_id':question_source_id,'candidate_revision':rev,'answer_source_ids':sorted(srcs),'evidence_group':evidence,'manifest_path':mpath,'manifest_hash':mhash})
    source_revisions={x['source_id']:x['revision'] for x in merged['sources'] if x['source_id'] in union}
    for d in required:
        link=next(x for x in prov['decision_links'] if x['decision_id']==d['decision_id']);link.setdefault('reverify_audits',[]).append({'reverify_path':rpath,'reverify_hash':rv_hash,'source_revisions':{k:v for k,v in source_revisions.items() if k in next(r for r in results if r['decision_id']==d['decision_id'])['current_source_ids']}})
    prov['reverify_audits'].append({'reverify_id':rvid,'reverify_path':rpath,'reverify_hash':rv_hash,'decision_ids':[d['decision_id'] for d in required]})
    rpath,actual_hash=write_immutable_json(policy,rpath,rv)
    if actual_hash!=rv_hash:raise ReverifyError('reverify hash prediction mismatch')
    run=new_run(run_id=rvid,operation='reverify',now=now);add_artifact(run,rpath,rv_hash);run['phase']='publication';run['updated_at']=now();write_run(policy,run)
    try:tr=publish_transaction(policy=policy,operation='reverify',before=actual,child_interchange=child,child_provenance=prov,operation_artifacts=[{'kind':'reverify','relative_path':rpath,'content_hash':rv_hash}],transaction_id=txid,snapshot_id=sid)
    except Exception as exc:
        run['status']='failed';run['phase']='complete';run['updated_at']=now();run['result']=None;write_run(policy,run);raise ReverifyError('reverify publication failed') from exc
    return {'run':reconcile_transaction_run(policy,tr,now=now),'reverify':rv}

def reverify(**kwargs):
    policy=validate_roots(kwargs['input_root'],kwargs['workspace_root'])
    with workspace_lock(policy):return reverify_locked(**kwargs)

def _derive_raw_current_conclusion(result,decision):
    ev=result['current_evidence']
    if not ev:return 'missing'
    opts={e.get('resolved_option_id') for e in ev}
    if None in opts or len(opts)>1:return 'conflict'
    only=next(iter(opts))
    if only!=decision['value']['resolved_option_ids'][0]:return 'conflict'
    return 'confirmable'

def validate_reverify_semantics(*,policy,plan,parent,child,parent_provenance,child_provenance,reverify_artifact):
    validate_reverify(reverify_artifact)
    if reverify_artifact['expected_before_pointer']!=plan['before'] or reverify_artifact['result_transaction_id']!=plan['transaction_id'] or reverify_artifact['result_snapshot_id']!=plan['snapshot_id']:raise ReverifyError('reverify transaction binding mismatch')
    required=_required(parent,reverify_artifact['scope'])
    if [d['decision_id'] for d in required]!=reverify_artifact['required_decision_ids']:raise ReverifyError('reverify required set changed')
    if {r['decision_id'] for r in reverify_artifact['results']}!=set(reverify_artifact['required_decision_ids']):raise ReverifyError('reverify result set mismatch')
    pc={c['candidate_id']:c for c in parent['candidates']['candidates']};cd={d['decision_id']:d for d in child['decisions']['decisions']}
    for d in required:
        link=find_decision_link(parent_provenance,d['decision_id']);r=next(x for x in reverify_artifact['results'] if x['decision_id']==d['decision_id'])
        if sorted(r['original_source_ids'])!=sorted(link['answer_source_ids']) or not set(link['answer_source_ids']).issubset(r['current_source_ids']) or not set(r['current_source_ids']).issubset(reverify_artifact['answer_source_ids']):raise ReverifyError('reverify source set changed')
        # Current semantic keys and mappings must be exactly derivable from facts.
        expected_sem=sorted({_sem(e)[0]+'|'+str(_sem(e)[1])+'|'+_sem(e)[2] for e in r['current_evidence']});actual_sem=sorted(x[0]+'|'+str(x[1])+'|'+x[2] for x in r['current_semantic_keys'])
        if expected_sem!=actual_sem:raise ReverifyError('reverify semantic keys are forged')
        for m in r['mappings']:
            h=m['historical_instance'];matches=[e for e in r['current_evidence'] if e['source_id']==h['source_id'] and e['evidence_fingerprint']==h['evidence_fingerprint']]
            expected=[_instance(e) for e in matches]
            if expected!=m['current_instances'] or (m['current_semantic_key'] is None)!=(not matches):raise ReverifyError('reverify evidence mapping is forged')
        conc=_derive_raw_current_conclusion(r,d);p1_outcome=None
        if link.get('adjudication'):
            p1_outcome=adjudication_still_applies(candidate=pc[d['candidate_id']],decision=d,original=link['adjudication'],current_evidence=r['current_evidence'],current_conclusion=conc,answer_source_ids=r['current_source_ids'],return_outcome=True)
            if p1_outcome=='invalid':raise ReverifyError('reverify historical adjudication binding is invalid')
            if p1_outcome=='applies':conc='adjudicated'
            elif p1_outcome=='conflict':conc='conflict'
        if conc!=r['current_conclusion']:raise ReverifyError('reverify current conclusion inconsistent')
        expected_result,expected_issue=_classify_current_facts(candidate=pc[d['candidate_id']],decision=d,link=link,current_conclusion=conc,current_evidence=r['current_evidence'],unavailable_source_ids=reverify_artifact['unavailable_source_ids'],answer_source_ids=r['current_source_ids'],adjudication_outcome=p1_outcome)
        if (expected_result,expected_issue)!=(r['result'],r['issue_code']):raise ReverifyError('reverify result cannot be recomputed')
        if cd[d['decision_id']]['status']!=r['result']:raise ReverifyError('reverify child Decision does not match result')
