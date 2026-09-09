from __future__ import annotations
import json
from pathlib import Path
from m2_helpers import UUIDSequence
from m3_helpers import bootstrap
from qbanswer.prepare import prepare

FORBIDDEN_KEYS={'password','token','api_key','username','environment','traceback','raw_answer_line','option_text'}

def _walk(v,path=()):
    if isinstance(v,dict):
        for k,x in v.items():yield path+(k,),x;yield from _walk(x,path+(k,))
    elif isinstance(v,list):
        for i,x in enumerate(v):yield from _walk(x,path+(str(i),))

def test_run_findings_are_exact_structured_shape():
    # Contract-level privacy shape: no free-text field is even representable.
    import inspect
    from qbanswer.prepare import _finding
    v=_finding('QB-IDENTITY-AMBIGUOUS',source_id=None,candidate_id=None,option_id=None)
    assert set(v)=={'issue_code','blocking_level','source_id','candidate_id','option_id'}

def test_published_m3_artifacts_do_not_expose_paths_env_or_full_answer_lines(tmp_path):
    c=bootstrap(tmp_path);prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(80000))
    bad=[];root=c.workspace_root
    for p in root.rglob('*.json'):
        rel=p.relative_to(root).as_posix()
        # Existing M0-M2 artifacts are out of M3 privacy scope for this test.
        if not (rel.startswith('runs/answer-association/') or rel.startswith('state/answer-association/')):continue
        v=json.loads(p.read_text(encoding='utf-8'))
        for path,x in _walk(v):
            if path and path[-1] in FORBIDDEN_KEYS:bad.append((rel,path[-1]))
            if isinstance(x,str) and (str(c.input_root) in x or str(c.workspace_root) in x or '\\' in x):bad.append((rel,'absolute-path'))
            # Candidate stem in interchange is explicitly allowed by the frozen spec;
            # answer artifacts must never contain a complete raw line such as "1: A".
            if isinstance(x,str) and x.strip() in {'1: A','2: B'}:bad.append((rel,'raw-answer-line'))
    assert bad==[]

def test_prepare_never_modifies_explicit_input_tree(tmp_path):
    from m2_helpers import tree_snapshot
    c=bootstrap(tmp_path);before=tree_snapshot(c.input_root)
    prepare(input_root=c.input_root,workspace_root=c.workspace_root,question_source_id=c.question_source_id,answer_source_ids=[c.answer_source_id],expected_candidate_hash=c.candidate_hash,expected_pointer='ABSENT',now=lambda:'2026-08-30T00:00:00Z',uuid_factory=UUIDSequence(81000))
    assert tree_snapshot(c.input_root)==before
