"""Pure deterministic answer association and historical-adjudication logic."""
from __future__ import annotations
from collections import defaultdict


def _nullable_option_key(v): return (0,"") if v is None else (1,v)

def evidence_sort_key(e): return (e['source_id'],e['locator'],e['evidence_fingerprint'])

def issue_evidence_group(records):
    unique={(e['source_id'],e['question_number'],e['evidence_fingerprint'],e.get('resolved_option_id')) for e in records}
    return [{"source_id":s,"question_number":q,"evidence_fingerprint":f,"resolved_option_id":o} for s,q,f,o in sorted(unique,key=lambda x:(x[0],x[1],x[2],_nullable_option_key(x[3])))]


def raw_associate(candidates:list[dict], evidences:list[dict])->tuple[list[dict],list[dict]]:
    by_num=defaultdict(list)
    for c in candidates:
        try: number=int(c['stem'].split('.',1)[0].strip())
        except Exception:
            # M2 parser does not persist a dedicated question-number field; locator/source replay supplies it normally.
            number=c.get('_question_number')
        if number is not None: by_num[number].append(c)
    ev_by_num=defaultdict(list)
    for e in evidences: ev_by_num[e['question_number']].append(dict(e))
    entries=[]; source_level=[]
    ordered=[]
    for c in candidates:
        number=c.get('_question_number')
        if number is None:
            try:number=int(c['stem'].split('.',1)[0].strip())
            except Exception:number=None
        ordered.append((c,number))
    known={n for _,n in ordered if n is not None}
    for c,number in ordered:
        if number is None or len(by_num.get(number,[]))!=1:
            evs=ev_by_num.get(number,[]) if number is not None else []
            entries.append(_base(c,number,'low_confidence',evs,None,[]))
            continue
        evs=ev_by_num.get(number,[])
        if not evs:
            entries.append(_base(c,number,'missing',[],None,[])); continue
        label_to_option={o['source_label']:o['option_id'] for o in c['options']}
        normalized=[]; groups=defaultdict(list); unresolved=False
        for e in evs:
            x=dict(e); x['resolved_option_id']=label_to_option.get(e['source_lexeme']); normalized.append(x)
            if x['resolved_option_id'] is None: unresolved=True
            groups[x['resolved_option_id']].append(x)
        resolved={k for k in groups if k is not None}
        if unresolved or len(resolved)!=1:
            alternatives=[{"resolved_option_id":k,"evidence_ids":[e['evidence_id'] for e in sorted(v,key=evidence_sort_key)]} for k,v in sorted(groups.items(),key=lambda kv:_nullable_option_key(kv[0]))]
            entries.append(_base(c,number,'conflict',normalized,None,alternatives))
        else:
            opt=next(iter(resolved)); label=next(o['source_label'] for o in c['options'] if o['option_id']==opt)
            entries.append(_base(c,number,'confirmable',normalized,opt,[],label))
    for number,evs in ev_by_num.items():
        if number not in known:
            source_level.append({"candidate_id":None,"candidate_revision":None,"question_locator":None,"question_number":number,"conclusion":"low_confidence","proposed_option_id":None,"proposed_source_label":None,"alternatives":[],"evidence":sorted([dict(e, resolved_option_id=None) for e in evs],key=evidence_sort_key),"review_item_id":None})
    return entries,source_level


def _base(c,n,conclusion,evs,opt,alts,label=None):
    return {"candidate_id":c['candidate_id'],"candidate_revision":c['candidate_revision'],"question_locator":c['locator'],"question_number":n,"conclusion":conclusion,"proposed_option_id":opt,"proposed_source_label":label,"alternatives":alts,"evidence":sorted(evs,key=evidence_sort_key),"review_item_id":None}


def _adjudication_outcome(*,candidate:dict,decision:dict,original:dict|None,current_evidence:list[dict],current_conclusion:str,answer_source_ids:list[str])->str:
    """Classify whether a historical choose-evidence adjudication still governs.

    The return value is one of ``applies``, ``stale``, ``conflict`` or
    ``invalid``.  This is the single fact classifier used by prepare, reverify
    and transaction read-back; an artifact is never allowed to self-assert an
    ``adjudicated`` conclusion.
    """
    if type(original) is not dict:
        return 'invalid'
    if decision.get('status')!='valid' or decision.get('candidate_id')!=candidate.get('candidate_id') or decision.get('candidate_revision')!=candidate.get('candidate_revision'):
        return 'invalid'
    original_sources=set(original.get('answer_source_ids',[])); current_sources=set(answer_source_ids)
    # The original source identity set is a floor.  Explicit additions are
    # allowed, but removing an adjudicated source invalidates the old binding.
    if not original_sources or not original_sources.issubset(current_sources):
        return 'invalid'
    resolved=decision.get('value',{}).get('resolved_option_ids',[None])
    if type(resolved) is not list or len(resolved)!=1:
        return 'invalid'
    resolved_option=resolved[0]
    selected={tuple(x) for x in original.get('selected_semantic_keys',[])}
    rejected={tuple(x) for x in original.get('rejected_semantic_keys',[])}
    if not selected or selected.intersection(rejected):
        return 'invalid'
    current=[(e['source_id'],e['question_number'],e['evidence_fingerprint'],e.get('resolved_option_id')) for e in current_evidence]
    selected_now={(a,b,c) for a,b,c,o in current if o==resolved_option}
    # Missing/changed selected facts are stale even when a formerly rejected
    # Option is now the only remaining answer.  This ordering is frozen by P1.
    if not selected.issubset(selected_now):
        return 'stale'
    other_now={(a,b,c) for a,b,c,o in current if o!=resolved_option}
    if not other_now.issubset(rejected):
        return 'conflict'
    # A duplicate/association gate that is not representable by the frozen
    # selected/rejected partition cannot be revived by historical adjudication.
    if current_conclusion not in {'confirmable','conflict'}:
        return 'invalid'
    return 'applies'


def adjudication_still_applies(*,candidate:dict,decision:dict,original:dict,current_evidence:list[dict],current_conclusion:str,answer_source_ids:list[str],return_outcome:bool=False):
    outcome=_adjudication_outcome(candidate=candidate,decision=decision,original=original,current_evidence=current_evidence,current_conclusion=current_conclusion,answer_source_ids=answer_source_ids)
    return outcome if return_outcome else outcome=='applies'
