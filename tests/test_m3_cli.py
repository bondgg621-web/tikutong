from __future__ import annotations
import json,os,sys
from pathlib import Path
from m2_helpers import run_subprocess
from m3_helpers import bootstrap,current_hash

ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'skills/curate-question-bank/scripts'

def _run(*args):
    pp=str(SCRIPTS);existing=os.environ.get('PYTHONPATH');
    if existing:pp=os.pathsep.join((pp,existing))
    return run_subprocess((sys.executable,str(SCRIPTS/'qbanswer_cli.py'),*map(str,args)),env={'PYTHONPATH':pp})

def test_cli_prepare_returns_stable_json_summary_and_exit_3(tmp_path):
    c=bootstrap(tmp_path);p=_run('prepare','--input-root',c.input_root,'--workspace-root',c.workspace_root,'--question-source-id',c.question_source_id,'--answer-source-id',c.answer_source_id,'--expected-candidate-hash',c.candidate_hash,'--expected-pointer','ABSENT')
    assert p.returncode==3 and p.stderr=='';v=json.loads(p.stdout);assert set(v)=={'operation','run_id','status'} and v['operation']=='prepare' and v['status']=='needs_confirmation'

def test_cli_failure_is_redacted_json_without_traceback_or_paths(tmp_path):
    c=bootstrap(tmp_path);p=_run('prepare','--input-root',c.input_root,'--workspace-root',c.workspace_root,'--question-source-id',c.question_source_id,'--answer-source-id',c.answer_source_id,'--expected-candidate-hash','0'*64,'--expected-pointer','ABSENT')
    assert p.returncode==2 and json.loads(p.stdout)=={'status':'failed'} and p.stderr=='';assert str(c.input_root) not in p.stdout and 'Traceback' not in p.stdout

def test_cli_recover_is_service_route_and_complete(tmp_path):
    c=bootstrap(tmp_path);p=_run('recover','--input-root',c.input_root,'--workspace-root',c.workspace_root);assert p.returncode==0;assert json.loads(p.stdout)=={'recovered_run_count':0,'status':'complete'}
