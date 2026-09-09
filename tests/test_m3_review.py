from __future__ import annotations
from m2_helpers import UUIDSequence
from qbanswer.review import find_or_create_review,stable_issue_key

def test_stable_issue_key_is_namespaced_by_question_source():
    kw=dict(candidate_id=None,answer_source_ids=['00000000-0000-0000-0000-000000000001'],issue_code='QB-ANSWER-MISSING',evidence=[])
    a=stable_issue_key(question_source_id='00000000-0000-0000-0000-000000000002',**kw);b=stable_issue_key(question_source_id='00000000-0000-0000-0000-000000000003',**kw);assert a!=b

def test_open_same_key_deduplicates_and_closed_recurrence_supersedes():
    reviews=[];prov={'review_links':[]};u=UUIDSequence(1);key='a'*64
    r,s,new=find_or_create_review(reviews=reviews,provenance=prov,issue_key=key,candidate_id=None,issue_code='QB-ASSOCIATION-LOW-CONFIDENCE',uuid_factory=u);assert new and s is None
    prov['review_links'].append({'review_id':r['review_id'],'review_issue_key':key});same,s,new=find_or_create_review(reviews=reviews,provenance=prov,issue_key=key,candidate_id=None,issue_code='QB-ASSOCIATION-LOW-CONFIDENCE',uuid_factory=u);assert same['review_id']==r['review_id'] and not new
    r['status']='resolved';newr,s,new=find_or_create_review(reviews=reviews,provenance=prov,issue_key=key,candidate_id=None,issue_code='QB-ASSOCIATION-LOW-CONFIDENCE',uuid_factory=u);assert new and s==r['review_id'] and newr['review_id']!=r['review_id']
