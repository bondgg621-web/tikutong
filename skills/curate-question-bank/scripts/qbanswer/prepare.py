"""Prepare explicit local answer evidence into immutable proposals."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

from qbcore.paths import validate_roots
from .answer_parser import parse_answer_text
from .artifacts import ABSENT,digest_bytes,read_relative,workspace_json_bytes,write_immutable_json
from .association import adjudication_still_applies,raw_associate
from .contracts import validate_proposal
from .review import find_or_create_review,issue_for_conclusion,stable_issue_key
from .run_audit import add_artifact,finish_direct_prepare,new_run,reconcile_transaction_run,write_run
from .source_snapshot import SnapshotError,build_manifest,resolve_answer_sources,resolve_question_view
from .state_graph import initial_interchange,initial_provenance,find_decision_link
from .transaction import TransactionError,publish_transaction,read_current_verified,recover_all_transactions,workspace_lock

class PrepareError(RuntimeError):pass

def _now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def _uuid():return uuid4()

def _finding(code,*,source_id=None,candidate_id=None,option_id=None):
    level={'QB-IDENTITY-AMBIGUOUS':'blocking','QB-OPTION-IDENTITY-AMBIGUOUS':'review_required'}.get(code,'blocking')
    return {'issue_code':code,'blocking_level':level,'source_id':source_id,'candidate_id':candidate_id,'option_id':option_id}

def _parent_state(verified,manifest,candidate_doc,snapshot_id):
    if verified is None:return initial_interchange(manifest,candidate_doc),initial_provenance(snapshot_id=snapshot_id,dataset_id=manifest['dataset_id'])
    return deepcopy(verified['interchange']),deepcopy(verified['provenance'])

def _candidate_map(inter):return {c['candidate_id']:c for c in inter['candidates']['candidates']}
def _decision_map(inter):return {d['decision_id']:d for d in inter['decisions']['decisions']}

def _current_valid(inter,cid):return [d for d in inter['decisions']['decisions'] if d['candidate_id']==cid and d['decision_type']=='answer_resolution' and d['status']=='valid']

def _historical_stale_entry(*,candidate,decision,inter,prov,uuid_factory):
    if decision['status']!='needs_revalidation':return None
    audits=[a for a in prov['stale_audits'] if a.get('decision_id')==decision['decision_id'] and a.get('candidate_revision')==candidate['candidate_revision']]
    if not audits:return None
    audit=audits[-1]; review=next((r for r in inter['review_queue']['review_items'] if r['review_id']==audit.get('review_id')),None)
    if not review or review['status']!='open' or review['issue_code']!='QB-DECISION-STALE':return None
    return {'proposal_id':str(uuid_factory()),'candidate_id':candidate['candidate_id'],'candidate_revision':candidate['candidate_revision'],'question_locator':candidate['locator'],'question_number':candidate['_question_number'],'conclusion':'stale','proposed_option_id':None,'proposed_source_label':None,'alternatives':[],'evidence':[],'review_item_id':review['review_id'],'decision_id':decision['decision_id'],'review_issue_key':audit['review_issue_key'],'adjudication':None}

def _selected_source_manifest(manifest,selected):
    s=set(selected);return {'schema_version':'1.0','dataset_id':manifest['dataset_id'],'sources':[x for x in manifest['sources'] if x['source_id'] in s]}

def prepare_locked(*,input_root,workspace_root,question_source_id,answer_source_ids,expected_candidate_hash,expected_pointer,now=_now,uuid_factory=_uuid):
    policy=validate_roots(input_root,workspace_root)
    recover_all_transactions(policy)
    actual,verified=read_current_verified(policy)
    if actual!=expected_pointer:raise PrepareError('expected current pointer mismatch')
    run_id=str(uuid_factory());run=new_run(run_id=run_id,operation='prepare',now=now);write_run(policy,run)
    try:
        policy,qs,candidate_doc,views,candidate_hash=resolve_question_view(input_root=input_root,workspace_root=workspace_root,question_source_id=question_source_id,expected_candidate_hash=expected_candidate_hash)
        if question_source_id in answer_source_ids:raise PrepareError('source roles overlap')
        answer_snaps,records=resolve_answer_sources(input_root=input_root,workspace_root=workspace_root,answer_source_ids=answer_source_ids,uuid_factory=uuid_factory,parse_func=parse_answer_text)
        parent_manifest=verified['interchange']['manifest'] if verified else None
        merged_manifest=build_manifest(workspace_root=workspace_root,question_snapshot=qs,answer_snapshots=answer_snaps,parent_manifest=parent_manifest)
        run_manifest=_selected_source_manifest(merged_manifest,[question_source_id,*answer_source_ids])
    except SnapshotError as exc:
        run['run_findings']=[_finding(exc.issue_code or 'QB-IDENTITY-AMBIGUOUS',source_id=question_source_id)];run['status']='failed';run['phase']='complete';run['updated_at']=now();run['result']=None;write_run(policy,run);raise PrepareError('prepare identity/source gate failed') from exc
    except Exception as exc:
        run['status']='failed';run['phase']='complete';run['updated_at']=now();run['result']=None;write_run(policy,run);raise PrepareError('prepare source/parse gate failed') from exc
    # Base canonical graph. First state uses M2 candidates; later state must match immutable M2 shell.
    pre_snapshot_id=str(uuid_factory())
    inter,prov=_parent_state(verified,merged_manifest,candidate_doc,pre_snapshot_id)
    inter['manifest']=deepcopy(merged_manifest)
    cmap=_candidate_map(inter)
    for v in views:
        c=cmap.get(v['candidate_id'])
        if not c or {k:x for k,x in c.items() if k!='status'}!={k:x for k,x in v.items() if k not in {'status','_question_number'}}:
            raise PrepareError('canonical Candidate differs from M2 baseline')
    raw,source_entries=raw_associate(views,[r.as_dict() for r in records])
    by_cid={e['candidate_id']:e for e in raw}
    review_link_base=len(prov['review_links']);stale_audit_base=len(prov['stale_audits'])
    changed=False
    entries=[]
    reviews=inter['review_queue']['review_items']
    for v in views:
        cid=v['candidate_id'];entry=deepcopy(by_cid[cid]);canonical=cmap[cid]
        valid=_current_valid(inter,cid)
        if len(valid)>1:raise PrepareError('canonical contains multiple valid decisions')
        # Historical needs_revalidation may expose exact stale archive entry.
        nd=[d for d in inter['decisions']['decisions'] if d['candidate_id']==cid and d['decision_type']=='answer_resolution' and d['status']=='needs_revalidation']
        if not valid and nd:
            stale=_historical_stale_entry(candidate=dict(v),decision=nd[-1],inter=inter,prov=prov,uuid_factory=uuid_factory)
            if stale is not None: entries.append(stale)
        if valid:
            d=valid[0]
            link=find_decision_link(prov,d['decision_id'])
            original=link.get('adjudication')
            p1_outcome=None
            if original:
                p1_outcome=adjudication_still_applies(candidate=v,decision=d,original=original,current_evidence=entry['evidence'],current_conclusion=entry['conclusion'],answer_source_ids=answer_source_ids,return_outcome=True)
                if p1_outcome=='invalid':
                    raise PrepareError('historical adjudication binding is no longer valid')
                if p1_outcome=='applies':
                    entry['conclusion']='adjudicated';entry['decision_id']=d['decision_id'];entry['proposed_option_id']=d['value']['resolved_option_ids'][0];entry['proposed_source_label']=None;entry['alternatives']=[];entry['review_item_id']=None;entry['review_issue_key']=None;entry['adjudication']=deepcopy(original);entries.append(_assign(entry,uuid_factory));continue
            resolved=d['value']['resolved_option_ids'][0]
            if p1_outcome=='stale':
                d['status']='needs_revalidation';canonical['status']='candidate';changed=True
                evidence=[{'source_id':ev['source_id'],'question_number':v['_question_number'],'evidence_fingerprint':ev['evidence_fingerprint'],'resolved_option_id':resolved} for ev in d['evidence']]
                key=stable_issue_key(question_source_id=question_source_id,candidate_id=cid,answer_source_ids=answer_source_ids,issue_code='QB-DECISION-STALE',evidence=evidence)
                item,sup,new=find_or_create_review(reviews=reviews,provenance=prov,issue_key=key,candidate_id=cid,issue_code='QB-DECISION-STALE',uuid_factory=uuid_factory)
                if new:prov['review_links'].append({'review_id':item['review_id'],'review_issue_key':key,'question_source_id':question_source_id,'proposal_path':None,'proposal_hash':None,'reverify_path':None,'reverify_hash':None,'supersedes_review_id':sup})
                prov['stale_audits'].append({'decision_id':d['decision_id'],'review_id':item['review_id'],'review_issue_key':key,'question_source_id':question_source_id,'candidate_revision':v['candidate_revision'],'answer_source_ids':sorted(answer_source_ids),'evidence_group':evidence,'manifest_path':f'runs/answer-association/{run_id}/manifest.json','manifest_hash':None})
                entries.append({'proposal_id':str(uuid_factory()),'candidate_id':cid,'candidate_revision':v['candidate_revision'],'question_locator':v['locator'],'question_number':v['_question_number'],'conclusion':'stale','proposed_option_id':None,'proposed_source_label':None,'alternatives':[],'evidence':[],'review_item_id':item['review_id'],'decision_id':d['decision_id'],'review_issue_key':key,'adjudication':None})
                continue
            # A single, otherwise unambiguous current answer that resolves to a
            # different Option is a Decision conflict, not a generic stale proof.
            # Preserve the current evidence but express it through the frozen
            # conflict proposal shape so only choose_evidence may replace the old
            # Decision after human confirmation.
            if entry['conclusion']=='confirmable' and entry['proposed_option_id']!=resolved:
                alt=entry['proposed_option_id']
                entry['conclusion']='conflict';entry['alternatives']=[{'resolved_option_id':alt,'evidence_ids':[x['evidence_id'] for x in entry['evidence']]}]
                entry['proposed_option_id']=None;entry['proposed_source_label']=None
            semantic_support=entry['conclusion']=='confirmable' and entry['proposed_option_id']==resolved
            # A semantic match alone is not current proof.  The historical Decision
            # remains directly proven only when all recorded evidence instances are
            # still exact, or when the already-verified parent snapshot covered the
            # same source revision/content facts (e.g. after a successful reverify).
            exact_instances=all(any(
                cur['source_id']==old['source_id'] and
                cur['source_revision']==old['source_revision'] and
                cur['locator']==old['locator'] and
                cur['evidence_fingerprint']==old['evidence_fingerprint']
                for cur in entry['evidence']) for old in d['evidence'])
            carried_parent_proof=False
            if verified is not None:
                old_sources={x['source_id']:x for x in verified['interchange']['manifest']['sources']}
                new_sources={x['source_id']:x for x in merged_manifest['sources']}
                carried_parent_proof=all(
                    ev['source_id'] in old_sources and ev['source_id'] in new_sources and
                    old_sources[ev['source_id']]['revision']==new_sources[ev['source_id']]['revision'] and
                    old_sources[ev['source_id']]['current_content_hash']==new_sources[ev['source_id']]['current_content_hash']
                    for ev in d['evidence'])
            current_support=semantic_support and (exact_instances or carried_parent_proof)
            if not current_support:
                # Conflict with new evidence stays conflict; disappeared selected evidence becomes stale.
                if entry['conclusion']=='conflict':
                    d['status']='needs_revalidation';canonical['status']='candidate';changed=True
                else:
                    d['status']='needs_revalidation';canonical['status']='candidate';changed=True
                    evidence=[]
                    for ev in d['evidence']:
                        evidence.append({'source_id':ev['source_id'],'question_number':v['_question_number'],'evidence_fingerprint':ev['evidence_fingerprint'],'resolved_option_id':resolved})
                    key=stable_issue_key(question_source_id=question_source_id,candidate_id=cid,answer_source_ids=answer_source_ids,issue_code='QB-DECISION-STALE',evidence=evidence)
                    item,sup,new=find_or_create_review(reviews=reviews,provenance=prov,issue_key=key,candidate_id=cid,issue_code='QB-DECISION-STALE',uuid_factory=uuid_factory)
                    if new:prov['review_links'].append({'review_id':item['review_id'],'review_issue_key':key,'question_source_id':question_source_id,'proposal_path':None,'proposal_hash':None,'reverify_path':None,'reverify_hash':None,'supersedes_review_id':sup})
                    prov['stale_audits'].append({'decision_id':d['decision_id'],'review_id':item['review_id'],'review_issue_key':key,'question_source_id':question_source_id,'candidate_revision':v['candidate_revision'],'answer_source_ids':sorted(answer_source_ids),'evidence_group':evidence,'manifest_path':f'runs/answer-association/{run_id}/manifest.json','manifest_hash':None})
                    entries.append({'proposal_id':str(uuid_factory()),'candidate_id':cid,'candidate_revision':v['candidate_revision'],'question_locator':v['locator'],'question_number':v['_question_number'],'conclusion':'stale','proposed_option_id':None,'proposed_source_label':None,'alternatives':[],'evidence':[],'review_item_id':item['review_id'],'decision_id':d['decision_id'],'review_issue_key':key,'adjudication':None})
                    continue
        if entry['conclusion'] in {'missing','conflict','low_confidence'}:
            issue=issue_for_conclusion(entry['conclusion']); key=stable_issue_key(question_source_id=question_source_id,candidate_id=cid,answer_source_ids=answer_source_ids,issue_code=issue,evidence=entry['evidence'])
            item,sup,new=find_or_create_review(reviews=reviews,provenance=prov,issue_key=key,candidate_id=cid,issue_code=issue,uuid_factory=uuid_factory)
            entry['review_item_id']=item['review_id'];changed|=new
            if new:prov['review_links'].append({'review_id':item['review_id'],'review_issue_key':key,'question_source_id':question_source_id,'proposal_path':None,'proposal_hash':None,'reverify_path':None,'reverify_hash':None,'supersedes_review_id':sup})
        entries.append(_assign(entry,uuid_factory))
    for entry in source_entries:
        issue='QB-ASSOCIATION-LOW-CONFIDENCE';key=stable_issue_key(question_source_id=question_source_id,candidate_id=None,answer_source_ids=answer_source_ids,issue_code=issue,evidence=entry['evidence'])
        item,sup,new=find_or_create_review(reviews=reviews,provenance=prov,issue_key=key,candidate_id=None,issue_code=issue,uuid_factory=uuid_factory);entry['review_item_id']=item['review_id'];changed|=new
        if new:prov['review_links'].append({'review_id':item['review_id'],'review_issue_key':key,'question_source_id':question_source_id,'proposal_path':None,'proposal_hash':None,'reverify_path':None,'reverify_hash':None,'supersedes_review_id':sup})
        entries.append(_assign(entry,uuid_factory))
    txid=str(uuid_factory()) if changed else None;snapshot_id=pre_snapshot_id if changed else None
    base={'kind':'prepare_result','transaction_id':txid,'snapshot_id':snapshot_id} if changed else {'kind':'direct'}
    proposal={'schema_version':'1.0','proposal_run_id':run_id,'manifest_path':f'runs/answer-association/{run_id}/manifest.json','manifest_hash':'0'*64,'candidate_artifact_path':f'candidates/sources/{question_source_id}.json','candidate_artifact_hash':candidate_hash,'question_source_id':question_source_id,'prepared_from_pointer':actual,'confirmation_base':base,'entries':entries}
    # Publish manifest, then insert actual manifest hash and publish proposal.
    mpath,mhash=write_immutable_json(policy,proposal['manifest_path'],run_manifest);proposal['manifest_hash']=mhash;validate_proposal(proposal)
    ppath,phash=write_immutable_json(policy,f'runs/answer-association/{run_id}/proposal.json',proposal)
    # Complete provenance references that were preallocated before immutable proposal existed.
    for link in prov['review_links'][review_link_base:]:
        if link.get('proposal_path') is None:link['proposal_path']=ppath;link['proposal_hash']=phash
    for audit in prov['stale_audits'][stale_audit_base:]:
        if audit.get('manifest_hash') is None:audit['manifest_hash']=mhash
    add_artifact(run,mpath,mhash);add_artifact(run,ppath,phash);run['phase']='publication';run['updated_at']=now();write_run(policy,run)
    if not changed:
        return {'run':finish_direct_prepare(policy,run,proposal,pointer_hash=actual),'proposal':proposal,'proposal_hash':phash}
    refs=[{'kind':'manifest','relative_path':mpath,'content_hash':mhash},{'kind':'proposal','relative_path':ppath,'content_hash':phash}]
    try:result=publish_transaction(policy=policy,operation='prepare',before=actual,child_interchange=inter,child_provenance=prov,operation_artifacts=refs,transaction_id=txid,snapshot_id=snapshot_id)
    except Exception as exc:
        run['status']='failed';run['phase']='complete';run['updated_at']=now();run['result']=None;write_run(policy,run);raise PrepareError('prepare publication failed') from exc
    return {'run':reconcile_transaction_run(policy,result,now=now),'proposal':proposal,'proposal_hash':phash}

def _assign(entry,uuid_factory):
    entry=deepcopy(entry);entry['proposal_id']=str(uuid_factory());entry.setdefault('decision_id',None);entry.setdefault('review_issue_key',None);entry.setdefault('adjudication',None);return entry

def prepare(**kwargs):
    policy=validate_roots(kwargs['input_root'],kwargs['workspace_root'])
    with workspace_lock(policy):return prepare_locked(**kwargs)

def validate_prepare_semantics(*,plan,parent,child,parent_provenance,child_provenance,manifest,proposal):
    validate_proposal(proposal)
    if proposal['prepared_from_pointer']!=plan['before']:raise PrepareError('prepare plan before mismatch')
    selected={x['source_id']:x for x in manifest['sources']};child_sources={x['source_id']:x for x in child['manifest']['sources']}
    if any(child_sources.get(k)!=v for k,v in selected.items()):raise PrepareError('prepare manifest not reflected in child')
    reviews={r['review_id']:r for r in child['review_queue']['review_items']};decisions={d['decision_id']:d for d in child['decisions']['decisions']}
    for e in proposal['entries']:
        if e['review_item_id'] is not None:
            r=reviews.get(e['review_item_id'])
            if not r:raise PrepareError('proposal review missing from child')
        if e['conclusion']=='stale':
            d=decisions.get(e['decision_id']);r=reviews.get(e['review_item_id'])
            if not d or d['status']!='needs_revalidation' or not r or r['status']!='open' or r['issue_code']!='QB-DECISION-STALE':raise PrepareError('stale proposal child graph invalid')
