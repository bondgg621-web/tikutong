"""Stable local CLI for M3 answer-evidence operations."""
from __future__ import annotations
import argparse,json,sys
from qbanswer.service import confirm,prepare,recover,reverify


def _emit(value):sys.stdout.write(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
def _summary(result):
    run=result.get('run') if isinstance(result,dict) else None
    if run:return {'run_id':run['run_id'],'operation':run['operation'],'status':run['status']}
    return {'status':'complete','recovered_run_count':len(result) if isinstance(result,list) else 0}
def _exit(summary):return 0 if summary['status']=='complete' else (3 if summary['status'] in {'needs_confirmation','needs_review'} else 2)

def parser():
    p=argparse.ArgumentParser(prog='qbanswer');sub=p.add_subparsers(dest='command',required=True)
    common=argparse.ArgumentParser(add_help=False);common.add_argument('--input-root',required=True);common.add_argument('--workspace-root',required=True)
    pr=sub.add_parser('prepare',parents=[common]);pr.add_argument('--question-source-id',required=True);pr.add_argument('--answer-source-id',action='append',required=True);pr.add_argument('--expected-candidate-hash',required=True);pr.add_argument('--expected-pointer',required=True)
    co=sub.add_parser('confirm',parents=[common]);co.add_argument('--proposal-run-id',required=True);co.add_argument('--proposal-hash',required=True);co.add_argument('--action',required=True,choices=['confirm','confirm_all_unambiguous','choose_evidence','reject','reject_association','retain_unresolved','archive_stale']);co.add_argument('--proposal-id',action='append',required=True);co.add_argument('--selected-evidence-id',action='append',default=[]);co.add_argument('--expected-candidate-hash',required=True);co.add_argument('--expected-pointer',required=True)
    rv=sub.add_parser('reverify',parents=[common]);g=rv.add_mutually_exclusive_group(required=True);g.add_argument('--decision-id');g.add_argument('--question-source-id');rv.add_argument('--additional-answer-source-id',action='append',default=[]);rv.add_argument('--expected-candidate-hash',required=True);rv.add_argument('--expected-pointer',required=True)
    sub.add_parser('recover',parents=[common]);return p

def main(argv=None):
    a=parser().parse_args(argv)
    try:
        if a.command=='prepare':r=prepare(input_root=a.input_root,workspace_root=a.workspace_root,question_source_id=a.question_source_id,answer_source_ids=a.answer_source_id,expected_candidate_hash=a.expected_candidate_hash,expected_pointer=a.expected_pointer)
        elif a.command=='confirm':r=confirm(input_root=a.input_root,workspace_root=a.workspace_root,proposal_run_id=a.proposal_run_id,proposal_hash=a.proposal_hash,request={'action':a.action,'proposal_ids':a.proposal_id,'selected_evidence_ids':a.selected_evidence_id},expected_candidate_hash=a.expected_candidate_hash,expected_pointer=a.expected_pointer)
        elif a.command=='reverify':
            scope={'kind':'decision','decision_id':a.decision_id} if a.decision_id else {'kind':'question_source','question_source_id':a.question_source_id}
            r=reverify(input_root=a.input_root,workspace_root=a.workspace_root,scope=scope,additional_answer_source_ids=a.additional_answer_source_id,expected_candidate_hash=a.expected_candidate_hash,expected_pointer=a.expected_pointer)
        else:r=recover(input_root=a.input_root,workspace_root=a.workspace_root)
        s=_summary(r);_emit(s);return _exit(s)
    except Exception:
        _emit({'status':'failed'});return 2
if __name__=='__main__':raise SystemExit(main())
