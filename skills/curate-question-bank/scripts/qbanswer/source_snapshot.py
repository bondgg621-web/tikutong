"""Read-only M1/M2 source and Candidate identity gates for M3."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

from qbcore.candidate_materializer import materialize_candidates
from qbcore.parse_service import _existing_candidate_matches_complete_run, _resolve_single_choice_source_snapshot
from qbcore.paths import validate_roots
from qbcore.single_choice_parser import parse_single_choice
from qbcore.workspace import Workspace
from qbcore.validation import validate_document

class SnapshotError(RuntimeError):
    def __init__(self,message,*,issue_code=None):
        super().__init__(message); self.issue_code=issue_code

class _ExistingUUIDs:
    def __init__(self,values): self._it=iter(values)
    def __call__(self): return UUID(next(self._it))


def _load(path:Path)->dict:
    try: value=json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: raise SnapshotError('workspace metadata is invalid') from exc
    if type(value) is not dict: raise SnapshotError('workspace metadata is invalid')
    return value


def resolve_question_view(*,input_root,workspace_root,question_source_id,expected_candidate_hash):
    policy=validate_roots(input_root,workspace_root)
    snap=_resolve_single_choice_source_snapshot(input_root=input_root,workspace_root=workspace_root,source_id=question_source_id)
    ws=Workspace(policy)
    if not _existing_candidate_matches_complete_run(workspace=ws,resolved=snap):
        raise SnapshotError('question source M2 baseline is not complete',issue_code='QB-IDENTITY-AMBIGUOUS')
    path=policy.workspace_root/'candidates/sources'/f'{question_source_id}.json'
    try: raw=path.read_bytes(); doc=json.loads(raw.decode('utf-8'))
    except Exception as exc: raise SnapshotError('candidate artifact is unreadable',issue_code='QB-IDENTITY-AMBIGUOUS') from exc
    actual=sha256(raw).hexdigest()
    if actual!=expected_candidate_hash:
        raise SnapshotError('candidate artifact hash mismatch',issue_code='QB-IDENTITY-AMBIGUOUS')
    if validate_document('candidate',doc): raise SnapshotError('candidate artifact invalid',issue_code='QB-IDENTITY-AMBIGUOUS')
    parsed=parse_single_choice(snap.text)
    if not parsed.publishable: raise SnapshotError('question source no longer replays cleanly',issue_code='QB-IDENTITY-AMBIGUOUS')
    ids=[]
    for c in doc['candidates']:
        ids.append(c['candidate_id']); ids.extend(o['option_id'] for o in c['options'])
    try: replay=materialize_candidates(parsed.questions,source_id=question_source_id,uuid_factory=_ExistingUUIDs(ids))
    except Exception as exc: raise SnapshotError('candidate identity replay failed',issue_code='QB-IDENTITY-AMBIGUOUS') from exc
    if replay!=doc:
        # distinguish option-only drift if candidate structural shell still matches
        code='QB-IDENTITY-AMBIGUOUS'
        if len(replay.get('candidates',[]))==len(doc.get('candidates',[])):
            for a,b in zip(replay['candidates'],doc['candidates']):
                aa={k:v for k,v in a.items() if k!='options'}; bb={k:v for k,v in b.items() if k!='options'}
                if aa==bb and a.get('options')!=b.get('options'): code='QB-OPTION-IDENTITY-AMBIGUOUS'; break
        raise SnapshotError('candidate identity replay mismatch',issue_code=code)
    views=[]
    for parsed_q,c in zip(parsed.questions,deepcopy(doc['candidates']),strict=True):
        c['_question_number']=int(parsed_q.display_number); views.append(c)
    return policy,snap,doc,views,actual


def resolve_answer_sources(*,input_root,workspace_root,answer_source_ids,uuid_factory,parse_func):
    if not answer_source_ids or len(set(answer_source_ids))!=len(answer_source_ids): raise SnapshotError('answer source selection is invalid')
    records=[]; snaps=[]
    for sid in answer_source_ids:
        snap=_resolve_single_choice_source_snapshot(input_root=input_root,workspace_root=workspace_root,source_id=sid)
        snaps.append(snap)
        records.extend(parse_func(snap.text,source_id=sid,source_revision=snap.source_revision,uuid_factory=uuid_factory))
    return snaps,records


def build_manifest(*,workspace_root,question_snapshot,answer_snapshots,parent_manifest=None):
    root=Path(workspace_root)
    project=_load(root/'project.json'); registry=_load(root/'registry/sources.json')
    if project.get('dataset_id')!=registry.get('dataset_id'): raise SnapshotError('dataset identity mismatch')
    byid={x['source_id']:x for x in registry['sources']}
    explicit={question_snapshot.source_id:('question_document',question_snapshot)}
    explicit.update({s.source_id:('answer_document',s) for s in answer_snapshots})
    merged={}
    if parent_manifest:
        for x in parent_manifest['sources']: merged[x['source_id']]=deepcopy(x)
    for sid,(kind,snap) in explicit.items():
        r=byid.get(sid)
        if not r or r.get('presence')!='present': raise SnapshotError('selected source is unavailable')
        if r['revision']!=snap.source_revision or r['current_content_hash']!=snap.content_hash or r['current_relative_path']!=snap.relative_path: raise SnapshotError('selected source snapshot is stale')
        history=list(r['path_history'])
        if not history or history[-1]!=r['current_relative_path']: raise SnapshotError('registry path history is invalid')
        old=merged.get(sid)
        if old:
            if old['kind']!=kind: raise SnapshotError('source role conflicts with parent',issue_code='QB-ROLE-AMBIGUOUS')
            if r['revision']<old['revision'] or history[:len(old['path_history'])]!=old['path_history']: raise SnapshotError('source path history regressed')
        merged[sid]={"source_id":sid,"kind":kind,"current_relative_path":r['current_relative_path'],"path_history":history,"current_content_hash":r['current_content_hash'],"revision":r['revision']}
    value={"schema_version":"1.0","dataset_id":project['dataset_id'],"sources":[merged[k] for k in sorted(merged)]}
    if validate_document('manifest',value): raise SnapshotError('manifest contract failed')
    return value
