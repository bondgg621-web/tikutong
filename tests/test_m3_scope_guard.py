from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from m3_helpers import (
    APPROVED_M3_PLAN_SHA256,APPROVED_M3_SPEC_SHA256,AUTHORITY_SHA256,
    M3_FIXTURE_WHITELIST,M3_RUNTIME_WHITELIST,M3_SCHEMA_WHITELIST,M3_TEST_WHITELIST,
)

ROOT=Path(__file__).resolve().parents[1]

# IP-03 added runtime-only document normalization while retaining the frozen
# M2 parser contract.  IP-05B adds a test-only M3 rich-evidence baseline.
# Keep the M3 guard's approved set explicit without expanding its authority
# count or its runtime/schema scope.
AUTHORITY_SHA256={
    **AUTHORITY_SHA256,
    'skills/curate-question-bank/scripts/qbcore/text_normalization.py':'bb1822a4a46028c2c747344ac002ec33bdbe60233ef2640e439f7447ec080152',
    'tests/test_m2_scope_guard.py':'92ab658bfe2ed57f94143574919b26b8e2916b631fb7f5a0415865651ff03d72',
}
M3_TEST_WHITELIST=[
    *M3_TEST_WHITELIST,
    'tests/test_m3_rich_answer_evidence.py',
]

def _hash(path:Path)->str:return sha256(path.read_bytes()).hexdigest()

def _repo_files():
    ignored_parts={'__pycache__','.pytest_cache','.git'}
    return {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not any(x in ignored_parts for x in p.parts) and p.suffix!='.pyc'}

def test_approved_spec_plan_and_97_authorities_are_exact():
    assert _hash(ROOT/'docs/MILESTONE-3-LOCAL-ANSWER-EVIDENCE-SPEC.md')==APPROVED_M3_SPEC_SHA256
    assert _hash(ROOT/'docs/MILESTONE-3-LOCAL-ANSWER-EVIDENCE-PLAN.md')==APPROVED_M3_PLAN_SHA256
    assert len(AUTHORITY_SHA256)==97
    for rel,expected in AUTHORITY_SHA256.items():
        path=ROOT/rel;assert path.is_file(),rel;assert _hash(path)==expected,rel

def test_repository_noncache_files_are_inside_frozen_physical_scope():
    # The web handoff cannot enumerate local-only pre-existing review/evidence
    # files.  Freeze known M0-M2 authorities here, and make every M3 namespace
    # closed; the external task applicator freezes *all* real local baseline
    # files before Task 0 and proves those unknown pre-existing files never
    # change.
    files=_repo_files()
    runtime=set(M3_RUNTIME_WHITELIST);schemas=set(M3_SCHEMA_WHITELIST);tests=set(M3_TEST_WHITELIST);fixtures=set(M3_FIXTURE_WHITELIST)
    for rel in files:
        if rel.startswith('skills/curate-question-bank/scripts/qbanswer/') or rel=='skills/curate-question-bank/scripts/qbanswer_cli.py':
            assert rel in runtime,rel
        if rel.startswith('skills/curate-question-bank/schemas/m3/'):
            assert rel in schemas,rel
        if rel=='tests/m3_helpers.py' or (rel.startswith('tests/test_m3_') and rel.endswith('.py')):
            assert rel in tests,rel
        if rel.startswith('tests/fixtures/m3-answer-association/'):
            assert rel in fixtures,rel

def test_existing_m3_files_use_only_frozen_runtime_schema_test_fixture_paths():
    actual_runtime={p.relative_to(ROOT).as_posix() for p in (ROOT/'skills/curate-question-bank/scripts/qbanswer').glob('*.py')}
    if (ROOT/'skills/curate-question-bank/scripts/qbanswer_cli.py').exists():actual_runtime.add('skills/curate-question-bank/scripts/qbanswer_cli.py')
    actual_schemas={p.relative_to(ROOT).as_posix() for p in (ROOT/'skills/curate-question-bank/schemas/m3').glob('*.schema.json')}
    actual_tests={p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_m3_*.py')}
    if (ROOT/'tests/m3_helpers.py').exists():actual_tests.add('tests/m3_helpers.py')
    actual_fixtures={p.relative_to(ROOT).as_posix() for p in (ROOT/'tests/fixtures/m3-answer-association').glob('*') if p.is_file()}

    # Task 0 must be GREEN before any M3 runtime exists.  During Tasks 0-9,
    # only a prefix/subset of the frozen physical whitelist may exist; no
    # out-of-scope path is ever permitted.  Schema creation is atomic at Task 1.
    assert actual_runtime <= set(M3_RUNTIME_WHITELIST)
    assert actual_tests <= set(M3_TEST_WHITELIST)
    assert actual_fixtures <= set(M3_FIXTURE_WHITELIST)
    assert actual_schemas <= set(M3_SCHEMA_WHITELIST)
    if actual_schemas:
        assert actual_schemas == set(M3_SCHEMA_WHITELIST)

    # Task 10 creates the final end-to-end test.  From that point onward the
    # approved physical implementation/test/fixture set must be exact.
    if 'tests/test_m3_end_to_end.py' in actual_tests:
        assert actual_runtime == set(M3_RUNTIME_WHITELIST)
        assert actual_schemas == set(M3_SCHEMA_WHITELIST)
        assert actual_tests == set(M3_TEST_WHITELIST)
        assert actual_fixtures == set(M3_FIXTURE_WHITELIST)

def test_two_full_gate_policy_is_frozen_in_approved_plan():
    text=(ROOT/'docs/MILESTONE-3-LOCAL-ANSWER-EVIDENCE-PLAN.md').read_text(encoding='utf-8')
    assert '连续两次运行' in text
    assert "python -m pytest -p no:cacheprovider tests -q" in text

def test_frozen_m2_skill_boundary_and_agent_metadata_survive_m3_implementation():
    skill=(ROOT/'skills/curate-question-bank/SKILL.md').read_text(encoding='utf-8')
    assert 'This milestone does not associate answers' in skill
    assert _hash(ROOT/'skills/curate-question-bank/agents/openai.yaml')==AUTHORITY_SHA256['skills/curate-question-bank/agents/openai.yaml']
