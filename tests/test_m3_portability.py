from __future__ import annotations
import os,shutil,sys,json
from pathlib import Path
from m2_helpers import run_subprocess
from m3_helpers import bootstrap

ROOT=Path(__file__).resolve().parents[1];SKILL=ROOT/'skills/curate-question-bank'

def test_copied_skill_cli_runs_from_new_location_and_only_writes_explicit_workspace(tmp_path):
    c=bootstrap(tmp_path/'case');copy=tmp_path/'copied-skill';shutil.copytree(SKILL,copy,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    before={p.relative_to(copy).as_posix():p.read_bytes() for p in copy.rglob('*') if p.is_file()}
    pp=str(copy/'scripts');existing=os.environ.get('PYTHONPATH');
    if existing:pp=os.pathsep.join((pp,existing))
    cp=run_subprocess((sys.executable,str(copy/'scripts/qbanswer_cli.py'),'prepare','--input-root',c.input_root,'--workspace-root',c.workspace_root,'--question-source-id',c.question_source_id,'--answer-source-id',c.answer_source_id,'--expected-candidate-hash',c.candidate_hash,'--expected-pointer','ABSENT'),cwd=copy,env={'PYTHONPATH':pp})
    assert cp.returncode==3 and json.loads(cp.stdout)['status']=='needs_confirmation'
    after={p.relative_to(copy).as_posix():p.read_bytes() for p in copy.rglob('*') if p.is_file()};assert after==before
    assert not list(copy.rglob('__pycache__')) and not list(copy.rglob('*.pyc'))
