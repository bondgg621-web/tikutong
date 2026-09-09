"""M3 canonical state graph construction and semantic validation."""
from __future__ import annotations
from copy import deepcopy
from qbcore.validation import validate_bundle
from .contracts import ContractError,validate_provenance

class StateGraphError(RuntimeError): pass

def initial_interchange(manifest:dict,candidate_document:dict)->dict:
    return {"manifest":deepcopy(manifest),"candidates":deepcopy(candidate_document),"review_queue":{"schema_version":"1.0","review_items":[]},"decisions":{"schema_version":"1.0","decisions":[]}}

def initial_provenance(*,snapshot_id:str,dataset_id:str)->dict:
    return {"schema_version":"1.0","snapshot_id":snapshot_id,"dataset_id":dataset_id,"decision_links":[],"review_links":[],"confirmation_audits":[],"reverify_audits":[],"stale_audits":[]}

def bundle(interchange):
    return {"manifest":interchange['manifest'],"candidates":interchange['candidates']['candidates'],"review_items":interchange['review_queue']['review_items'],"decisions":interchange['decisions']['decisions']}

def _byid(items,key):
    out={}
    for x in items:
        if x[key] in out:raise StateGraphError(f'duplicate {key}')
        out[x[key]]=x
    return out

def _candidate_immutable(c): return {k:deepcopy(v) for k,v in c.items() if k!='status'}
def _decision_immutable(d): return {k:deepcopy(v) for k,v in d.items() if k!='status'}
def _review_immutable(r): return {k:deepcopy(v) for k,v in r.items() if k!='status'}

def validate_interchange(interchange:dict):
    if type(interchange) is not dict or set(interchange)!={'manifest','candidates','review_queue','decisions'}:raise StateGraphError('interchange shape invalid')
    issues=validate_bundle(bundle(interchange))
    if issues:raise StateGraphError('M0/M3 interchange base contract failed')
    ids=[x['source_id'] for x in interchange['manifest']['sources']]
    if ids!=sorted(ids) or len(ids)!=len(set(ids)):raise StateGraphError('manifest source identity/order invalid')
    return True

def validate_parent_child(parent:dict|None,child:dict,parent_prov:dict|None,child_prov:dict,*,operation:str|None=None):
    validate_interchange(child);validate_provenance(child_prov)
    if child_prov['dataset_id']!=child['manifest']['dataset_id']:raise StateGraphError('provenance dataset mismatch')
    if parent is None:
        if parent_prov is not None:raise StateGraphError('first generation parent provenance invalid')
        validate_review_supersession_graph(child,child_prov)
        return True
    validate_interchange(parent);validate_provenance(parent_prov)
    # Source history cannot disappear or change kind/history prefix.
    ps={x['source_id']:x for x in parent['manifest']['sources']}; cs={x['source_id']:x for x in child['manifest']['sources']}
    for sid,p in ps.items():
        if sid not in cs:raise StateGraphError('parent source removed')
        c=cs[sid]
        if p['kind']!=c['kind'] or c['revision']<p['revision'] or c['path_history'][:len(p['path_history'])]!=p['path_history']:raise StateGraphError('source lineage changed')
    pc=_byid(parent['candidates']['candidates'],'candidate_id');cc=_byid(child['candidates']['candidates'],'candidate_id')
    if set(pc)!=set(cc):raise StateGraphError('candidate identity set changed')
    allowed_c={('candidate','candidate'),('candidate','validated'),('validated','validated'),('validated','candidate'),('unsupported','unsupported'),('ambiguous','ambiguous'),('archived','archived')}
    for cid,p in pc.items():
        c=cc[cid]
        if _candidate_immutable(p)!=_candidate_immutable(c):raise StateGraphError('candidate immutable fields changed')
        if (p['status'],c['status']) not in allowed_c:raise StateGraphError('candidate status transition invalid')
    pd=_byid(parent['decisions']['decisions'],'decision_id');cd=_byid(child['decisions']['decisions'],'decision_id')
    if not set(pd).issubset(cd):raise StateGraphError('historical decision removed')
    allowed_d={('valid','valid'),('valid','needs_revalidation'),('valid','archived'),('needs_revalidation','needs_revalidation'),('needs_revalidation','archived'),('archived','archived')}
    for did,p in pd.items():
        c=cd[did]
        if _decision_immutable(p)!=_decision_immutable(c):raise StateGraphError('decision immutable fields changed')
        if (p['status'],c['status']) not in allowed_d:raise StateGraphError('decision state regressed')
    pr=_byid(parent['review_queue']['review_items'],'review_id');cr=_byid(child['review_queue']['review_items'],'review_id')
    if not set(pr).issubset(cr):raise StateGraphError('historical review removed')
    allowed_r={('open','open'),('open','resolved'),('open','archived'),('resolved','resolved'),('resolved','archived'),('archived','archived')}
    for rid,p in pr.items():
        c=cr[rid]
        if _review_immutable(p)!=_review_immutable(c):raise StateGraphError('review immutable fields changed')
        if (p['status'],c['status']) not in allowed_r:raise StateGraphError('review state regressed')
    # Provenance is append-only, with one deliberate nested append point:
    # an existing Decision link may only gain reverify_audits.  Its identity,
    # original confirmation/proposal binding, source set and adjudication are
    # immutable.  Treating the entire link as byte-immutable would make every
    # legitimate reverify transaction impossible to publish.
    old_links=parent_prov['decision_links'];new_links=child_prov['decision_links']
    if len(new_links)<len(old_links):raise StateGraphError('historical decision provenance removed')
    for idx,old_link in enumerate(old_links):
        new_link=new_links[idx]
        old_fixed={k:deepcopy(v) for k,v in old_link.items() if k!='reverify_audits'}
        new_fixed={k:deepcopy(v) for k,v in new_link.items() if k!='reverify_audits'}
        if old_fixed!=new_fixed:raise StateGraphError('historical decision provenance changed')
        old_audits=old_link.get('reverify_audits',[]);new_audits=new_link.get('reverify_audits',[])
        if new_audits[:len(old_audits)]!=old_audits:raise StateGraphError('historical reverify audit changed')
        added=len(new_audits)-len(old_audits)
        if operation=='reverify':
            if added not in {0,1}:raise StateGraphError('reverify Decision audit cardinality invalid')
        elif added:
            raise StateGraphError('non-reverify operation appended Decision reverify audit')
    # All other provenance collections are ordinary append-only arrays.
    for field in ('review_links','confirmation_audits','reverify_audits','stale_audits'):
        old=parent_prov[field];new=child_prov[field]
        if new[:len(old)]!=old:raise StateGraphError('historical provenance changed')
    validate_review_supersession_graph(child,child_prov,parent_interchange=parent,parent_provenance=parent_prov)
    if operation: validate_provenance_delta(parent_prov,child_prov,operation=operation)
    return True

def validate_provenance_delta(parent:dict,child:dict,*,operation:str):
    delta={f:child[f][len(parent[f]):] for f in ('decision_links','review_links','confirmation_audits','reverify_audits','stale_audits')}
    internal_reverify_additions=0
    for old_link,new_link in zip(parent['decision_links'],child['decision_links']):
        internal_reverify_additions += len(new_link.get('reverify_audits',[]))-len(old_link.get('reverify_audits',[]))
    if operation=='prepare':
        if delta['decision_links'] or delta['confirmation_audits'] or delta['reverify_audits'] or internal_reverify_additions:raise StateGraphError('prepare appended unrelated provenance')
    elif operation=='confirm':
        if delta['review_links'] or delta['reverify_audits'] or delta['stale_audits'] or internal_reverify_additions:raise StateGraphError('confirm appended unrelated provenance')
        if len(delta['confirmation_audits'])!=1:raise StateGraphError('confirmation audit cardinality invalid')
    elif operation=='reverify':
        if delta['decision_links'] or delta['confirmation_audits']:raise StateGraphError('reverify appended unrelated provenance')
        if len(delta['reverify_audits'])!=1:raise StateGraphError('reverify audit cardinality invalid')
        if internal_reverify_additions<1:raise StateGraphError('reverify did not bind Decision audit')
    else:raise StateGraphError('unknown operation')


def validate_review_supersession_graph(interchange:dict,provenance:dict,*,parent_interchange:dict|None=None,parent_provenance:dict|None=None):
    """Validate stable-key recurrence/supersession as an append-only graph."""
    reviews=_byid(interchange['review_queue']['review_items'],'review_id')
    links=provenance['review_links']
    seen_ids=set()
    for idx,link in enumerate(links):
        required={'review_id','review_issue_key','question_source_id','proposal_path','proposal_hash','reverify_path','reverify_hash','supersedes_review_id'}
        if type(link) is not dict or set(link)!=required:raise StateGraphError('review provenance shape invalid')
        rid=link['review_id'];key=link['review_issue_key'];sup=link['supersedes_review_id']
        if rid in seen_ids:raise StateGraphError('duplicate review provenance link')
        seen_ids.add(rid)
        if rid not in reviews:raise StateGraphError('review provenance references missing ReviewItem')
        prior=[x for x in links[:idx] if x['review_issue_key']==key]
        expected=prior[-1]['review_id'] if prior else None
        if sup!=expected:raise StateGraphError('review supersession does not target nearest same-key predecessor')
        if sup is not None:
            if sup==rid:raise StateGraphError('review supersession self-cycle')
            target=reviews.get(sup)
            if target is None or target['status'] not in {'resolved','archived'}:raise StateGraphError('review supersession target is not closed')
    # A newly appended recurrence must point into the parent chain, not to another
    # ReviewItem created in the same child generation.  This makes "later" and
    # "nearest closed parent" mechanically checkable at the publication boundary.
    if parent_interchange is not None and parent_provenance is not None:
        parent_reviews=_byid(parent_interchange['review_queue']['review_items'],'review_id')
        base=len(parent_provenance['review_links'])
        if links[:base]!=parent_provenance['review_links']:raise StateGraphError('historical review provenance changed')
        for link in links[base:]:
            sup=link['supersedes_review_id']
            prior=[x for x in parent_provenance['review_links'] if x['review_issue_key']==link['review_issue_key']]
            expected=prior[-1]['review_id'] if prior else None
            if sup!=expected:raise StateGraphError('new review supersession is not nearest parent recurrence')
            if sup is not None and (sup not in parent_reviews or parent_reviews[sup]['status'] not in {'resolved','archived'}):raise StateGraphError('new review supersedes non-closed parent item')
    return True

def find_decision_link(prov,decision_id):
    xs=[x for x in prov['decision_links'] if x.get('decision_id')==decision_id]
    if len(xs)!=1:raise StateGraphError('decision provenance cardinality invalid')
    return xs[0]

def validated_gate(interchange:dict,provenance:dict,*,reverify_loader=None)->tuple[bool,str|None]:
    try:validate_interchange(interchange);validate_provenance(provenance)
    except Exception:return False,'contract'
    reviews=interchange['review_queue']['review_items'];decisions=interchange['decisions']['decisions'];sources={x['source_id']:x for x in interchange['manifest']['sources']}
    candidates={x['candidate_id']:x for x in interchange['candidates']['candidates']}
    for c in candidates.values():
        if c['status']!='validated':continue
        if c['question_type']!='single_choice':return False,'question_type'
        valid=[d for d in decisions if d['candidate_id']==c['candidate_id'] and d['candidate_revision']==c['candidate_revision'] and d['decision_type']=='answer_resolution' and d['status']=='valid']
        if len(valid)!=1:return False,'decision_cardinality'
        d=valid[0];opts={o['option_id'] for o in c['options']};resolved=d['value'].get('resolved_option_ids')
        if type(resolved) is not list or len(resolved)!=1 or resolved[0] not in opts:return False,'option_ownership'
        if any(r.get('candidate_id')==c['candidate_id'] and r['status']=='open' and r['blocking_level'] in {'blocking','review_required'} for r in reviews):return False,'open_review'
        try:link=find_decision_link(provenance,d['decision_id'])
        except StateGraphError:return False,'missing_provenance'
        if not link.get('confirmation_path') or not link.get('confirmation_hash'):return False,'missing_confirmation'
        for ev in d['evidence']:
            source=sources.get(ev['source_id'])
            if not source:return False,'source_missing'
            if source['revision']==ev['source_revision']:
                continue
            audits=link.get('reverify_audits',[])
            good=[a for a in audits if a.get('source_revisions',{}).get(ev['source_id'])==source['revision']]
            if not good:return False,'missing_reverify'
            if reverify_loader is not None:
                ok=False
                resolved_option=resolved[0]
                for a in good:
                    try: rv=reverify_loader(a['reverify_path'],a['reverify_hash'])
                    except Exception: continue
                    results=[r for r in rv.get('results',[]) if r.get('decision_id')==d['decision_id']]
                    if len(results)!=1 or results[0].get('result')!='valid':continue
                    result=results[0]
                    mappings=[m for m in result.get('mappings',[]) if m.get('historical_instance')==ev]
                    if len(mappings)!=1:continue
                    mapping=mappings[0];key=mapping.get('current_semantic_key');instances=mapping.get('current_instances',[])
                    if type(key) is not list or len(key)!=3 or key[0]!=ev['source_id'] or key[2]!=ev['evidence_fingerprint']:continue
                    if key not in result.get('current_semantic_keys',[]):continue
                    current=[x for x in instances if x.get('source_id')==ev['source_id'] and x.get('source_revision')==source['revision'] and x.get('question_number')==key[1] and x.get('evidence_fingerprint')==ev['evidence_fingerprint'] and x.get('resolved_option_id')==resolved_option]
                    if not current:continue
                    evidence_instances=result.get('current_evidence',[])
                    fields=('source_id','source_revision','locator','question_number','evidence_fingerprint','resolved_option_id')
                    if not any(all(full.get(k)==inst.get(k) for k in fields) for inst in current for full in evidence_instances):continue
                    ok=True;break
                if not ok:return False,'missing_reverify'
    return True,None
