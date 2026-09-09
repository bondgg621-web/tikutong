"""Human confirmation of immutable M3 proposals."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from uuid import uuid4

from qbcore.paths import validate_roots
from .artifacts import digest_value,read_relative,write_immutable_json
from .contracts import validate_confirmation,validate_proposal
from .review import stable_issue_key
from .run_audit import add_artifact,new_run,reconcile_transaction_run,write_run
from .source_snapshot import resolve_question_view
from .state_graph import StateGraphError,find_decision_link,validated_gate,initial_interchange,initial_provenance
from .transaction import publish_transaction,read_current_verified,recover_all_transactions,validate_confirmation_base,validate_prepare_result_proposal_origin,workspace_lock

class ConfirmationError(RuntimeError):pass

def _now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def _uuid():return uuid4()
def _sem(e):return [e['source_id'],e['question_number'],e['evidence_fingerprint']]
def _option(candidate,option_id):return next((o for o in candidate['options'] if o['option_id']==option_id),None)
def _entry_by_id(proposal,pid):
    xs=[e for e in proposal['entries'] if e['proposal_id']==pid]
    if len(xs)!=1:raise ConfirmationError('proposal entry is not unique')
    return xs[0]
def _answer_source_ids(policy,proposal):
    manifest,_,mh=read_relative(policy,proposal['manifest_path'])
    if mh!=proposal['manifest_hash']:raise ConfirmationError('proposal manifest hash mismatch')
    return sorted(x['source_id'] for x in manifest['sources'] if x['kind']=='answer_document')

def _validate_archive_stale(*,proposal,entry,parent,parent_prov):
    if entry['conclusion']!='stale':raise ConfirmationError('archive_stale requires stale proposal')
    cand=next((c for c in parent['candidates']['candidates'] if c['candidate_id']==entry['candidate_id']),None)
    if not cand or cand['candidate_revision']!=entry['candidate_revision'] or cand['status']!='candidate':raise ConfirmationError('stale Candidate binding invalid')
    dec=next((d for d in parent['decisions']['decisions'] if d['decision_id']==entry['decision_id']),None)
    if not dec or dec['candidate_id']!=cand['candidate_id'] or dec['candidate_revision']!=cand['candidate_revision'] or dec['decision_type']!='answer_resolution' or dec['status']!='needs_revalidation':raise ConfirmationError('stale Decision binding invalid')
    review=next((r for r in parent['review_queue']['review_items'] if r['review_id']==entry['review_item_id']),None)
    if not review or review.get('candidate_id')!=cand['candidate_id'] or review['issue_code']!='QB-DECISION-STALE' or review['status']!='open' or review['blocking_level']!='blocking' or review['allowed_user_actions']!=['revalidate','archive']:raise ConfirmationError('stale ReviewItem binding invalid')
    audits=[a for a in parent_prov['stale_audits'] if a.get('decision_id')==dec['decision_id'] and a.get('review_id')==review['review_id'] and a.get('review_issue_key')==entry['review_issue_key']]
    if len(audits)!=1:raise ConfirmationError('stale provenance binding invalid')
    a=audits[0]
    if a.get('question_source_id')!=proposal['question_source_id'] or a.get('candidate_revision')!=cand['candidate_revision']:raise ConfirmationError('stale namespace binding invalid')
    key=stable_issue_key(question_source_id=proposal['question_source_id'],candidate_id=cand['candidate_id'],answer_source_ids=a.get('answer_source_ids',[]),issue_code='QB-DECISION-STALE',evidence=a.get('evidence_group',[]))
    if key!=entry['review_issue_key']:raise ConfirmationError('stale issue key cannot be recomputed')
    return cand,dec,review

def _validate_action(proposal,request,parent,parent_prov):
    action=request['action'];ids=request['proposal_ids'];selected=set(request['selected_evidence_ids'])
    entries=[_entry_by_id(proposal,x) for x in ids]
    if action!='confirm_all_unambiguous' and len(entries)!=1:raise ConfirmationError('action requires exactly one proposal entry')
    if action=='confirm_all_unambiguous':
        wanted=[e for e in proposal['entries'] if e['conclusion']=='confirmable']
        if not wanted or {e['proposal_id'] for e in wanted}!=set(ids) or selected:raise ConfirmationError('confirm_all must bind all confirmable entries exactly')
    elif action=='confirm':
        if entries[0]['conclusion']!='confirmable' or selected:raise ConfirmationError('confirm action payload invalid')
    elif action=='choose_evidence':
        e=entries[0]
        if e['conclusion']!='conflict' or not selected:raise ConfirmationError('choose_evidence payload invalid')
        byid={x['evidence_id']:x for x in e['evidence']}
        if not selected.issubset(byid):raise ConfirmationError('selected evidence is outside proposal')
        opts={byid[x]['resolved_option_id'] for x in selected}
        if None in opts or len(opts)!=1:raise ConfirmationError('selected evidence does not resolve one Option')
    elif action=='reject':
        if entries[0]['conclusion']!='confirmable' or selected:raise ConfirmationError('reject action payload invalid')
    elif action=='reject_association':
        if entries[0]['conclusion']!='low_confidence' or selected:raise ConfirmationError('reject_association action payload invalid')
    elif action=='retain_unresolved':
        if entries[0]['conclusion'] not in {'missing','conflict','low_confidence'} or selected:raise ConfirmationError('retain_unresolved action payload invalid')
    elif action=='archive_stale':
        if selected:raise ConfirmationError('archive_stale cannot carry evidence')
        _validate_archive_stale(proposal=proposal,entry=entries[0],parent=parent,parent_prov=parent_prov)
    else:raise ConfirmationError('unknown confirmation action')
    if any(e['conclusion'] in {'stale','adjudicated'} for e in entries) and action!='archive_stale':raise ConfirmationError('proposal conclusion is not compatible with action')
    return entries

def _resolvable_reviews_for_answer(*,policy,proposal,entry,parent,parent_prov):
    """Return exact open ReviewItems whose frozen trigger is disproved/replaced.

    Confirmable entries intentionally carry review_item_id=null, so historical
    missing/conflict/stale issues must be recovered from immutable provenance
    rather than smuggled into the new proposal payload.
    """
    current_sources=set(_answer_source_ids(policy,proposal));reviews={r['review_id']:r for r in parent['review_queue']['review_items']}
    resolved=set()
    if entry.get('review_item_id') is not None: resolved.add(entry['review_item_id'])
    # A newly confirmed answer replaces any current needs_revalidation Decision;
    # resolve only the stale ReviewItem uniquely bound to that exact Decision.
    live=[d for d in parent['decisions']['decisions'] if d['candidate_id']==entry['candidate_id'] and d['candidate_revision']==entry['candidate_revision'] and d['decision_type']=='answer_resolution' and d['status']=='needs_revalidation']
    for d in live:
        audits=[a for a in parent_prov['stale_audits'] if a.get('decision_id')==d['decision_id'] and set(a.get('answer_source_ids',[])).issubset(current_sources)]
        for a in audits:
            r=reviews.get(a.get('review_id'))
            if r and r.get('candidate_id')==entry['candidate_id'] and r['issue_code']=='QB-DECISION-STALE' and r['status']=='open':resolved.add(r['review_id'])
    # Historical missing/conflict ReviewItems are recovered through the exact
    # immutable proposal that created them.  They may close only after all of
    # that proposal's answer sources are present in this confirmation run.
    for link in parent_prov['review_links']:
        rid=link['review_id'];r=reviews.get(rid)
        if not r or r['status']!='open' or r.get('candidate_id')!=entry['candidate_id'] or r['issue_code'] not in {'QB-ANSWER-MISSING','QB-ANSWER-CONFLICT'}:continue
        path=link.get('proposal_path');expected=link.get('proposal_hash')
        if not path or not expected:continue
        old,_,actual=read_relative(policy,path);validate_proposal(old)
        if actual!=expected:raise ConfirmationError('historical ReviewItem proposal hash mismatch')
        old_sources=set(_answer_source_ids(policy,old))
        if not old_sources.issubset(current_sources):continue
        old_entries=[x for x in old['entries'] if x.get('review_item_id')==rid]
        if len(old_entries)!=1:raise ConfirmationError('historical ReviewItem proposal binding invalid')
        if r['issue_code']=='QB-ANSWER-MISSING' and entry['conclusion'] in {'confirmable','conflict'}:resolved.add(rid)
        elif r['issue_code']=='QB-ANSWER-CONFLICT':
            if entry['conclusion']=='confirmable' or (entry['conclusion']=='conflict' and entry.get('review_item_id')!=rid):resolved.add(rid)
    return resolved

def _resolve_review(child,review_id):
    if review_id is None:return
    r=next((x for x in child['review_queue']['review_items'] if x['review_id']==review_id),None)
    if r and r['status']=='open':r['status']='resolved'

def _decision_evidence(entry,selected_ids=None):
    evs=entry['evidence'] if selected_ids is None else [e for e in entry['evidence'] if e['evidence_id'] in selected_ids]
    return [{"source_id":e['source_id'],"source_revision":e['source_revision'],"locator":e['locator'],"evidence_fingerprint":e['evidence_fingerprint']} for e in evs]

def _same_evidence(a,b):return sorted(a,key=lambda x:(x['source_id'],x['source_revision'],x['locator'],x['evidence_fingerprint']))==sorted(b,key=lambda x:(x['source_id'],x['source_revision'],x['locator'],x['evidence_fingerprint']))

def confirm_locked(*,input_root,workspace_root,proposal_run_id,proposal_hash,request,expected_candidate_hash,expected_pointer,now=_now,uuid_factory=_uuid):
    policy=validate_roots(input_root,workspace_root);recover_all_transactions(policy);actual,verified=read_current_verified(policy)
    if actual!=expected_pointer:raise ConfirmationError('confirmation current pointer mismatch')
    ppath=f'runs/answer-association/{proposal_run_id}/proposal.json';proposal,_,ph=read_relative(policy,ppath);validate_proposal(proposal)
    if ph!=proposal_hash or proposal['proposal_run_id']!=proposal_run_id:raise ConfirmationError('proposal hash/run mismatch')
    proposal_manifest,_,proposal_mh=read_relative(policy,proposal['manifest_path'])
    if proposal_mh!=proposal['manifest_hash']:raise ConfirmationError('proposal manifest hash mismatch')
    validate_confirmation_base(policy,proposal,actual,None if verified is None else verified['pointer'],proposal_path=ppath,proposal_hash=ph)
    _,_,candidate_doc,views,candidate_hash=resolve_question_view(input_root=input_root,workspace_root=workspace_root,question_source_id=proposal['question_source_id'],expected_candidate_hash=expected_candidate_hash)
    if candidate_hash!=proposal['candidate_artifact_hash']:raise ConfirmationError('Candidate baseline differs from proposal')
    if verified is None:
        parent=initial_interchange(proposal_manifest,candidate_doc);parent_prov=initial_provenance(snapshot_id='00000000-0000-4000-8000-000000000001',dataset_id=proposal_manifest['dataset_id'])
    else:
        parent=verified['interchange'];parent_prov=verified['provenance']
    entries=_validate_action(proposal,request,parent,parent_prov)
    txid=str(uuid_factory());sid=str(uuid_factory());cid=str(uuid_factory()); recorded=now()
    considered=[];selected=[];rejected=[]
    if request['action']=='choose_evidence':
        e=entries[0];considered=[_sem(x) for x in e['evidence']];selected=[_sem(x) for x in e['evidence'] if x['evidence_id'] in set(request['selected_evidence_ids'])];rejected=[x for x in considered if x not in selected]
    elif request['action'] in {'confirm','confirm_all_unambiguous'}:
        considered=[_sem(x) for e in entries for x in e['evidence']];selected=deepcopy(considered)
    confirmation={'schema_version':'1.0','confirmation_id':cid,'proposal_run_id':proposal_run_id,'proposal_path':ppath,'proposal_hash':ph,'expected_candidate_hash':candidate_hash,'expected_current_pointer':actual,'request':deepcopy(request),'considered_semantic_keys':sorted(considered),'selected_semantic_keys':sorted(selected),'rejected_semantic_keys':sorted(rejected),'result_transaction_id':txid,'result_snapshot_id':sid,'recorded_at':recorded}
    validate_confirmation(confirmation);cpath=f'runs/answer-association/{cid}/confirmation.json';chash=digest_value(confirmation)
    child=deepcopy(parent)
    # A direct proposal may freeze a newer source manifest without creating a
    # canonical prepare snapshot.  Confirmation is the first publishing
    # transaction in that case, so its child must adopt the exact immutable
    # proposal manifest before binding evidence revisions.
    child['manifest']=deepcopy(proposal_manifest)
    prov=deepcopy(parent_prov);cmap={c['candidate_id']:c for c in child['candidates']['candidates']}
    dlist=child['decisions']['decisions']
    action=request['action']
    if action in {'confirm','confirm_all_unambiguous','choose_evidence'}:
        for e in entries:
            candidate=cmap[e['candidate_id']]
            option_id=e['proposed_option_id'] if action!='choose_evidence' else next(x['resolved_option_id'] for x in e['evidence'] if x['evidence_id'] in set(request['selected_evidence_ids']))
            selected_ids=None if action!='choose_evidence' else set(request['selected_evidence_ids'])
            evidence=_decision_evidence(e,selected_ids)
            resolutions=_resolvable_reviews_for_answer(policy=policy,proposal=proposal,entry=e,parent=parent,parent_prov=parent_prov)
            current=[d for d in dlist if d['candidate_id']==candidate['candidate_id'] and d['decision_type']=='answer_resolution' and d['status']=='valid']
            if len(current)>1:raise ConfirmationError('multiple valid decisions')
            keep=None
            if current and current[0]['value'].get('resolved_option_ids')==[option_id] and _same_evidence(current[0]['evidence'],evidence):keep=current[0]
            if keep is None:
                for d in [d for d in dlist if d['candidate_id']==candidate['candidate_id'] and d['decision_type']=='answer_resolution' and d['status'] in {'valid','needs_revalidation'}]:d['status']='archived'
                did=str(uuid_factory());decision={'decision_id':did,'candidate_id':candidate['candidate_id'],'candidate_revision':candidate['candidate_revision'],'decision_type':'answer_resolution','value':{'resolved_option_ids':[option_id]},'evidence':evidence,'status':'valid'};dlist.append(decision)
                ans_ids=_answer_source_ids(policy,proposal)
                adjudication={'answer_source_ids':ans_ids,'selected_semantic_keys':selected if len(entries)==1 else [_sem(x) for x in e['evidence']],'rejected_semantic_keys':rejected if len(entries)==1 else []} if action=='choose_evidence' else None
                prov['decision_links'].append({'decision_id':did,'candidate_id':candidate['candidate_id'],'proposal_path':ppath,'proposal_hash':ph,'confirmation_path':cpath,'confirmation_hash':chash,'manifest_path':proposal['manifest_path'],'manifest_hash':proposal['manifest_hash'],'question_source_id':proposal['question_source_id'],'answer_source_ids':ans_ids,'selected_semantic_keys':[_sem(x) for x in (e['evidence'] if selected_ids is None else [x for x in e['evidence'] if x['evidence_id'] in selected_ids])],'rejected_semantic_keys':[_sem(x) for x in ([] if selected_ids is None else [x for x in e['evidence'] if x['evidence_id'] not in selected_ids])],'adjudication':adjudication,'reverify_audits':[]})
            for review_id in resolutions:_resolve_review(child,review_id)
        # Promotion is evaluated after provenance links exist.
        for e in entries:
            cand=cmap[e['candidate_id']];cand['status']='validated'
    elif action=='reject_association':_resolve_review(child,entries[0]['review_item_id'])
    elif action=='archive_stale':
        cand,dec,review=_validate_archive_stale(proposal=proposal,entry=entries[0],parent=parent,parent_prov=parent_prov);next(d for d in dlist if d['decision_id']==dec['decision_id'])['status']='archived';_resolve_review(child,review['review_id']);cmap[cand['candidate_id']]['status']='candidate'
    # reject and retain are audit-only child snapshots.
    prov['confirmation_audits'].append({'confirmation_id':cid,'confirmation_path':cpath,'confirmation_hash':chash,'proposal_path':ppath,'proposal_hash':ph,'transaction_id':txid,'snapshot_id':sid})
    # Check validated gate using current manifest/reverify provenance. New confirmations have no revision gap.
    ok,reason=validated_gate(child,prov)
    if not ok:
        # Only candidates being promoted are demoted; other pre-existing validated candidates must remain valid.
        promoted={e['candidate_id'] for e in entries if e['candidate_id'] is not None and action in {'confirm','confirm_all_unambiguous','choose_evidence'}}
        for c in child['candidates']['candidates']:
            if c['candidate_id'] in promoted:c['status']='candidate'
        if promoted:raise ConfirmationError(f'validated gate failed: {reason}')
    cpath,actual_chash=write_immutable_json(policy,cpath,confirmation)
    if actual_chash!=chash:raise ConfirmationError('confirmation hash prediction mismatch')
    run_id=cid;run=new_run(run_id=run_id,operation='confirm',now=now);add_artifact(run,cpath,chash);run['phase']='publication';run['updated_at']=now();write_run(policy,run)
    refs=[{'kind':'confirmation','relative_path':cpath,'content_hash':chash}]
    try:result=publish_transaction(policy=policy,operation='confirm',before=actual,child_interchange=child,child_provenance=prov,operation_artifacts=refs,transaction_id=txid,snapshot_id=sid)
    except Exception as exc:
        run['status']='failed';run['phase']='complete';run['updated_at']=now();run['result']=None;write_run(policy,run);raise ConfirmationError('confirmation publication failed') from exc
    return {'run':reconcile_transaction_run(policy,result,now=now),'confirmation':confirmation}

def confirm(**kwargs):
    policy=validate_roots(kwargs['input_root'],kwargs['workspace_root'])
    with workspace_lock(policy):return confirm_locked(**kwargs)

def validate_confirmation_semantics(*,policy,plan,parent,child,parent_provenance,child_provenance,confirmation):
    """Recompute a confirmation transaction from immutable proposal facts.

    Hash consistency is necessary but not sufficient: this validator deliberately
    reconnects the child Decision/Review/Candidate graph to the proposal and the
    human action so a tamperer cannot rewrite business objects and merely repair
    the direct hash graph.
    """
    validate_confirmation(confirmation)
    if confirmation['expected_current_pointer']!=plan['before'] or confirmation['result_transaction_id']!=plan['transaction_id'] or confirmation['result_snapshot_id']!=plan['snapshot_id']:
        raise ConfirmationError('confirmation transaction binding mismatch')
    proposal,_,ph=read_relative(policy,confirmation['proposal_path']);validate_proposal(proposal)
    if ph!=confirmation['proposal_hash']:raise ConfirmationError('confirmation proposal hash mismatch')
    proposal_manifest,_,mh=read_relative(policy,proposal['manifest_path'])
    if mh!=proposal['manifest_hash']:raise ConfirmationError('proposal manifest hash mismatch')
    validate_prepare_result_proposal_origin(policy,proposal,confirmation['proposal_path'],ph)
    if parent is None:
        candidate,_,ch=read_relative(policy,proposal['candidate_artifact_path'])
        if ch!=proposal['candidate_artifact_hash']:raise ConfirmationError('proposal Candidate hash mismatch')
        parent=initial_interchange(proposal_manifest,candidate);parent_provenance=initial_provenance(snapshot_id='00000000-0000-4000-8000-000000000001',dataset_id=proposal_manifest['dataset_id'])
    if child.get('manifest')!=proposal_manifest:raise ConfirmationError('confirmation child manifest differs from proposal manifest')
    entries=_validate_action(proposal,confirmation['request'],parent,parent_provenance)
    action=confirmation['request']['action'];selected_ids=set(confirmation['request']['selected_evidence_ids'])

    # The audit semantic partition is itself derived data, never an authority.
    if action=='choose_evidence':
        e=entries[0]
        considered=sorted(_sem(x) for x in e['evidence'])
        selected=sorted(_sem(x) for x in e['evidence'] if x['evidence_id'] in selected_ids)
        rejected=sorted(x for x in considered if x not in selected)
    elif action in {'confirm','confirm_all_unambiguous'}:
        considered=sorted(_sem(x) for e in entries for x in e['evidence']);selected=list(considered);rejected=[]
    else:
        considered=[];selected=[];rejected=[]
    if confirmation['considered_semantic_keys']!=considered or confirmation['selected_semantic_keys']!=selected or confirmation['rejected_semantic_keys']!=rejected:
        raise ConfirmationError('confirmation evidence partition cannot be recomputed')

    pc={c['candidate_id']:c for c in parent['candidates']['candidates']};cc={c['candidate_id']:c for c in child['candidates']['candidates']}
    pd={d['decision_id']:d for d in parent['decisions']['decisions']};cd={d['decision_id']:d for d in child['decisions']['decisions']}
    pr={r['review_id']:r for r in parent['review_queue']['review_items']};cr={r['review_id']:r for r in child['review_queue']['review_items']}

    # Standalone confirmation audit must bind this exact immutable confirmation.
    cpath=plan['operation_artifacts'][0]['relative_path'];chash=plan['operation_artifacts'][0]['content_hash']
    expected_audit={'confirmation_id':confirmation['confirmation_id'],'confirmation_path':cpath,'confirmation_hash':chash,'proposal_path':confirmation['proposal_path'],'proposal_hash':confirmation['proposal_hash'],'transaction_id':plan['transaction_id'],'snapshot_id':plan['snapshot_id']}
    delta_audits=child_provenance['confirmation_audits'][len(parent_provenance['confirmation_audits']):]
    if delta_audits!=[expected_audit]:raise ConfirmationError('standalone confirmation audit binding invalid')

    involved={e['candidate_id'] for e in entries if e.get('candidate_id') is not None}
    expected_review_resolutions=set()
    expected_new_decisions=set()
    expected_archives=set()

    if action in {'confirm','confirm_all_unambiguous','choose_evidence'}:
        for e in entries:
            candidate=pc.get(e['candidate_id']);child_candidate=cc.get(e['candidate_id'])
            if not candidate or not child_candidate or child_candidate['status']!='validated':raise ConfirmationError('confirmed Candidate is not validated')
            option_id=e['proposed_option_id'] if action!='choose_evidence' else next(x['resolved_option_id'] for x in e['evidence'] if x['evidence_id'] in selected_ids)
            evidence=_decision_evidence(e,None if action!='choose_evidence' else selected_ids)
            expected_review_resolutions.update(_resolvable_reviews_for_answer(policy=policy,proposal=proposal,entry=e,parent=parent,parent_prov=parent_provenance))
            matches=[d for d in cd.values() if d['candidate_id']==candidate['candidate_id'] and d['candidate_revision']==candidate['candidate_revision'] and d['decision_type']=='answer_resolution' and d['status']=='valid' and d['value'].get('resolved_option_ids')==[option_id] and _same_evidence(d['evidence'],evidence)]
            if len(matches)!=1:raise ConfirmationError('confirmed Decision cannot be derived from proposal')
            chosen=matches[0]
            parent_live=[d for d in pd.values() if d['candidate_id']==candidate['candidate_id'] and d['candidate_revision']==candidate['candidate_revision'] and d['decision_type']=='answer_resolution' and d['status'] in {'valid','needs_revalidation'}]
            identical=[d for d in parent_live if d['status']=='valid' and d['value'].get('resolved_option_ids')==[option_id] and _same_evidence(d['evidence'],evidence)]
            if identical:
                if len(identical)!=1 or chosen['decision_id']!=identical[0]['decision_id']:raise ConfirmationError('same Decision confirmation changed identity')
            else:
                if chosen['decision_id'] in pd:raise ConfirmationError('replacement Decision reused historical identity')
                expected_new_decisions.add(chosen['decision_id'])
                expected_archives.update(d['decision_id'] for d in parent_live)
                links=[x for x in child_provenance['decision_links'] if x.get('decision_id')==chosen['decision_id']]
                if len(links)!=1:raise ConfirmationError('new Decision provenance cardinality invalid')
                link=links[0];ans_ids=_answer_source_ids(policy,proposal)
                expected_selected=sorted(_sem(x) for x in (e['evidence'] if action!='choose_evidence' else [x for x in e['evidence'] if x['evidence_id'] in selected_ids]))
                expected_rejected=[] if action!='choose_evidence' else sorted(_sem(x) for x in e['evidence'] if x['evidence_id'] not in selected_ids)
                if link.get('candidate_id')!=candidate['candidate_id'] or link.get('proposal_path')!=confirmation['proposal_path'] or link.get('proposal_hash')!=confirmation['proposal_hash'] or link.get('confirmation_path')!=cpath or link.get('confirmation_hash')!=chash or link.get('manifest_path')!=proposal['manifest_path'] or link.get('manifest_hash')!=proposal['manifest_hash'] or link.get('question_source_id')!=proposal['question_source_id'] or sorted(link.get('answer_source_ids',[]))!=ans_ids:
                    raise ConfirmationError('new Decision provenance binding invalid')
                if sorted(link.get('selected_semantic_keys',[]))!=expected_selected or sorted(link.get('rejected_semantic_keys',[]))!=expected_rejected:
                    raise ConfirmationError('new Decision evidence provenance invalid')
                if action=='choose_evidence':
                    adj=link.get('adjudication')
                    if type(adj) is not dict or sorted(adj.get('answer_source_ids',[]))!=ans_ids or sorted(adj.get('selected_semantic_keys',[]))!=expected_selected or sorted(adj.get('rejected_semantic_keys',[]))!=expected_rejected:
                        raise ConfirmationError('conflict adjudication provenance invalid')
                elif link.get('adjudication') is not None:raise ConfirmationError('unexpected conflict adjudication')
            if e['review_item_id'] is not None:expected_review_resolutions.add(e['review_item_id'])
    elif action=='reject_association':
        expected_review_resolutions.add(entries[0]['review_item_id'])
    elif action=='archive_stale':
        e=entries[0];_validate_archive_stale(proposal=proposal,entry=e,parent=parent,parent_prov=parent_provenance)
        expected_archives.add(e['decision_id']);expected_review_resolutions.add(e['review_item_id'])
        if cc[e['candidate_id']]['status']!='candidate':raise ConfirmationError('archive_stale Candidate transition invalid')
        if len(cd)!=len(pd):raise ConfirmationError('archive_stale created Decision')
    # reject/retain_unresolved intentionally change no canonical object.

    # No unrelated Candidate state change is permitted.
    for cid,p in pc.items():
        c=cc[cid]
        if cid not in involved and c!=p:raise ConfirmationError('confirmation changed unrelated Candidate')
        if cid in involved and action not in {'confirm','confirm_all_unambiguous','choose_evidence','archive_stale'} and c!=p:raise ConfirmationError('audit-only action changed Candidate')

    # Decision changes must be exactly replacement archives/new Decisions or archive_stale.
    for did,p in pd.items():
        c=cd[did]
        if did in expected_archives:
            if c['status']!='archived':raise ConfirmationError('expected historical Decision was not archived')
        elif c!=p:raise ConfirmationError('confirmation changed unrelated Decision')
    if set(cd)-set(pd)!=expected_new_decisions:raise ConfirmationError('unexpected Decision creation')

    # Review resolution is also an exact delta.
    for rid,p in pr.items():
        c=cr[rid]
        if rid in expected_review_resolutions:
            if p['status']!='open' or c['status']!='resolved':raise ConfirmationError('expected ReviewItem resolution invalid')
        elif c!=p:raise ConfirmationError('confirmation changed unrelated ReviewItem')
    if set(cr)!=set(pr):raise ConfirmationError('confirmation created ReviewItem')

