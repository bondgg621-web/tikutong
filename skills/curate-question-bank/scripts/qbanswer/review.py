"""Review issue identity, recurrence and frozen action mappings."""
from __future__ import annotations
from .artifacts import compact_json_bytes,digest_bytes
from .association import issue_evidence_group

_RULES={
 'QB-ANSWER-MISSING':('blocking',['provide evidence','retain']),
 'QB-ANSWER-CONFLICT':('blocking',['choose evidence','retain']),
 'QB-ASSOCIATION-LOW-CONFIDENCE':('review_required',['reject','retain']),
 'QB-DECISION-STALE':('blocking',['revalidate','archive']),
}

def stable_issue_key(*,question_source_id,candidate_id,answer_source_ids,issue_code,evidence):
    obj={"answer_source_ids":sorted(set(answer_source_ids)),"candidate_id":candidate_id,"evidence_group":issue_evidence_group(evidence),"issue_code":issue_code,"question_source_id":question_source_id}
    return digest_bytes(compact_json_bytes(obj))

def issue_for_conclusion(conclusion):
    return {'missing':'QB-ANSWER-MISSING','conflict':'QB-ANSWER-CONFLICT','low_confidence':'QB-ASSOCIATION-LOW-CONFIDENCE','stale':'QB-DECISION-STALE'}.get(conclusion)

def make_review(*,review_id,candidate_id,issue_code):
    level,actions=_RULES[issue_code]
    value={"review_id":review_id,"issue_code":issue_code,"blocking_level":level,"status":"open","allowed_user_actions":actions}
    if candidate_id is not None:value['candidate_id']=candidate_id
    return value

def find_or_create_review(*,reviews,provenance,issue_key,candidate_id,issue_code,uuid_factory):
    links=[x for x in provenance.get('review_links',[]) if x.get('review_issue_key')==issue_key]
    byid={r['review_id']:r for r in reviews}
    opens=[byid[x['review_id']] for x in links if x.get('review_id') in byid and byid[x['review_id']]['status']=='open']
    if len(opens)>1: raise ValueError('multiple open reviews share one stable issue key')
    if opens:return opens[0],None,False
    closed=[byid[x['review_id']] for x in links if x.get('review_id') in byid and byid[x['review_id']]['status'] in {'resolved','archived'}]
    supersedes=closed[-1]['review_id'] if closed else None
    item=make_review(review_id=str(uuid_factory()),candidate_id=candidate_id,issue_code=issue_code)
    reviews.append(item)
    return item,supersedes,True
