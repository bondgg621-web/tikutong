"""Public M3 service boundary."""
from __future__ import annotations
from pathlib import Path
from qbcore.paths import validate_roots
from .artifacts import current_pointer,read_json_bytes
from .contracts import validate_confirmation,validate_proposal,validate_reverify
from .confirmation import confirm as _confirm
from .prepare import prepare as _prepare
from .reverify import reverify as _reverify
from .run_audit import add_artifact,finish_direct_prepare,new_run,reconcile_transaction_run,run_path,utc_now,validate_direct_prepare_terminal_run,write_run
from .transaction import recover_all_transactions,workspace_lock


def prepare(**kwargs):return _prepare(**kwargs)
def confirm(**kwargs):return _confirm(**kwargs)
def reverify(**kwargs):return _reverify(**kwargs)

def recover(*,input_root,workspace_root,now=None):
    policy=validate_roots(input_root,workspace_root)
    with workspace_lock(policy):
        recovered=[]
        for txid,result in recover_all_transactions(policy):
            if result is not None:
                recovered.append(reconcile_transaction_run(policy,result,**({} if now is None else {'now':now})))
        # Runs whose operation artifact exists but whose plan was never published
        # are crash-point-A orphans.  They have no canonical transaction and must
        # deterministically terminate failed; direct prepare is the only no-plan
        # success branch.
        runs_root=policy.workspace_root/'runs/answer-association'
        if runs_root.exists():
            for d in sorted(runs_root.iterdir(),key=lambda x:x.name):
                if not d.is_dir():continue
                rp=d/'run.json';existing=None
                if rp.exists():
                    existing,_,_=read_json_bytes(rp)
                proposal_path=d/'proposal.json';confirmation_path=d/'confirmation.json';reverify_path=d/'reverify.json'
                if existing is not None and existing.get('status') in {'complete','needs_confirmation','needs_review','failed'}:
                    # Transaction-backed success runs were already revalidated in
                    # the transaction loop above.  Direct prepare has no plan, so
                    # it must be revalidated explicitly instead of being skipped.
                    if existing.get('status')!='failed' and existing.get('operation')=='prepare' and proposal_path.exists():
                        proposal,_,ph=read_json_bytes(proposal_path);validate_proposal(proposal)
                        if proposal.get('confirmation_base')=={'kind':'direct'}:
                            recovered.append(validate_direct_prepare_terminal_run(policy,existing,proposal,proposal_path=f'runs/answer-association/{d.name}/proposal.json',proposal_hash=ph))
                    continue
                operation=None;declared_txid=None;refs=[];direct_proposal=None
                if proposal_path.exists():
                    proposal,_,ph=read_json_bytes(proposal_path);validate_proposal(proposal);operation='prepare';refs.append((f'runs/answer-association/{d.name}/proposal.json',ph))
                    manifest_path=d/'manifest.json';_,_,mh=read_json_bytes(manifest_path);refs.insert(0,(f'runs/answer-association/{d.name}/manifest.json',mh))
                    base=proposal['confirmation_base']
                    if base['kind']=='direct':direct_proposal=proposal
                    else:declared_txid=base['transaction_id']
                elif confirmation_path.exists():
                    confirmation,_,ch=read_json_bytes(confirmation_path);validate_confirmation(confirmation);operation='confirm';declared_txid=confirmation['result_transaction_id'];refs.append((f'runs/answer-association/{d.name}/confirmation.json',ch))
                elif reverify_path.exists():
                    rv,_,rh=read_json_bytes(reverify_path);validate_reverify(rv);operation='reverify';declared_txid=rv['result_transaction_id'];refs.append((f'runs/answer-association/{d.name}/reverify.json',rh))
                else:
                    continue
                run=existing or new_run(run_id=d.name,operation=operation,**({} if now is None else {'now':now}))
                for rel,digest in refs:add_artifact(run,rel,digest)
                if direct_proposal is not None:
                    pointer,_=current_pointer(policy);recovered.append(finish_direct_prepare(policy,run,direct_proposal,pointer_hash=pointer));continue
                plan_path=policy.workspace_root/f'transactions/answer-association/{declared_txid}/plan.json'
                if not plan_path.exists():
                    run['status']='failed';run['phase']='complete';run['updated_at']=(now() if now is not None else utc_now());run['result']=None
                    recovered.append(write_run(policy,run))
        return recovered
