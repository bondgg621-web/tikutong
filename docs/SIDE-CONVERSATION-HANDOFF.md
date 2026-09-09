# Question Bank Curator Canonical Handoff

Updated: 2026-08-29

## Objective

Complete Milestone 3 design and specification review only. Scope is local existing-answer evidence association, explicit human confirmation, conflict handling, re-verification, and gated `validated` promotion. Do not implement, generate or infer answers, use network access, build quiz UI, or add formal scoring.

## Verified paths

- Project: `D:\question-bank-curator`
- Frozen specification: `docs/MILESTONE-2-SINGLE-CHOICE-PARSER-SPEC.md`
- Specification SHA-256: `A4E6CFCEE04A497243DA9282931B1BAA99BA1589702420AF3C5034D88A6A809C`
- Frozen plan: `docs/MILESTONE-2-SINGLE-CHOICE-PARSER-PLAN.md`
- Plan SHA-256: `07ED596F2842D513C5CE0224777698A5E38724216DF7FD58A5BFEF4FA8DC262A`
- Implemented M2 modules under `skills/curate-question-bank/scripts/qbcore/`: `parse_contracts.py`, `single_choice_parser.py`, `text_normalization.py`, `candidate_materializer.py`, `parse_service.py`, with bounded updates to `workspace.py` and `cli.py`.
- M2 schemas: `single-choice-parse-report.schema.json`, `single-choice-parse-issues.schema.json`, `single-choice-parse-run.schema.json`
- M2 tests: `tests/m2_helpers.py`, all `tests/test_m2_*.py`, five persistent synthetic files under `tests/fixtures/m2-parser/`, and the exact UTF-8-BOM/CRLF fixture generated at test runtime.

## Current result

- Milestone 3 implementation has not started and is not authorized.
- Current M3 design candidate: `docs/MILESTONE-3-LOCAL-ANSWER-EVIDENCE-SPEC.md`, 680 lines, 82,953 bytes, SHA-256 `84C4FBE8A02346DF4B05761CA8345199C88FFB033C4FD9E7D9A42E7B643A4374`.
- The previously authorized prepare/reverify adjudication predicate and `run.json` crash-recovery blockers were revised and structurally rechecked. A fresh independent local review accepted those closures but still returned FAIL on one separate stale-action lineage blocker. Milestone 3 is 尚未验收.
- Remaining blocker: `archive_stale` is a confirmation action that must bind a proposal entry, but the frozen proposal conclusion branches contain no legal stale payload. Implementation would have to guess an unauthorized binding.
- No runtime code, implementation plan, schema, test, fixture, metadata, Git, network, dependency, worktree, or commit change has been made for M3.

- Completed, independently spec/quality reviewed, and root-verified: Tasks 1–12. Milestone 2 is accepted.
- Task 10 is accepted. It now provides one-source CLI parsing, safe first materialization, exact incomplete-publication recovery, fail-closed existing-candidate handling, and sanitized CLI errors.
- Task 11 is accepted. Skill/agent descriptions advertise only implemented inventory and one-source parsing behavior; copied-package parsing and audit-hook safeguards prove portability, workspace-only writes, read-only input, workspace pruning, Unicode/case paths, traversal rejection, and output privacy.
- Task 12 specification and quality reviews passed. Final authoritative run 1: exit `0`, `661 passed, 3 skipped in 35.75s`; run 2: exit `0`, `661 passed, 3 skipped in 36.60s`.
- Last full command: `$env:PYTHONDONTWRITEBYTECODE='1'; D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q`
- Last accepted full-suite result after Task 9: exit `0`; `618 passed, 2 skipped in 25.20s`.
- Latest root full-suite result after Task 10: exit `0`; `649 passed, 2 skipped in 80.45s`.
- Latest root full-suite result after Task 11: exit `0`; `661 passed, 3 skipped in 81.82s`.
- Task 12 structured read-back passed for 46 Python, 21 JSON, and 25 Markdown/YAML files. Frozen hash/scope checks passed `7/7`.
- Final synthetic CLI passed from clean roots: 7 candidates with option counts `4,4,4,4,4,3,3`; repeat parse preserved bytes/IDs and exited `2`; needs-review exited `3`; stale registry exited `2`; 25 workspace JSON files read back.
- Reproducible evidence manifest: `C:\Users\lenovo\AppData\Local\Temp\qbc-m2-final-acceptance-l4pmrtyz\acceptance-evidence.json`; it contains seven command results, stdout/stderr, before/after candidate hashes and IDs, input-tree hashes, and all JSON artifact hashes.
- M0 frozen schemas/references and `qbcore/validation.py` remain protected by hash guards.
- No Git repository was initialized; no commit/worktree/network/dependency installation occurred.
- Model/reasoning intensity has not changed. Remind the user before any later change.
- Latest documentation-only regression run: exit `0`; `661 passed, 3 skipped in 39.28s`. This verifies M0/M1/M2 only and is not an M3 feature test.

## Changed files

- Skill package metadata: `skills/curate-question-bank/SKILL.md`, `skills/curate-question-bank/agents/openai.yaml`.
- New schemas: the three `single-choice-parse-*.schema.json` files.
- Runtime: new `parse_contracts.py`, `single_choice_parser.py`, `text_normalization.py`, `candidate_materializer.py`, `parse_service.py`; bounded updates to `workspace.py` and `cli.py`.
- Tests/fixtures: `tests/m2_helpers.py`, all `tests/test_m2_*.py`, and `tests/fixtures/m2-parser/*`.
- Task 12 docs: `START-HERE.md`, `NEW-THREAD-PROMPT.md`, and this handoff.
- M3 specification-review docs: `docs/MILESTONE-3-LOCAL-ANSWER-EVIDENCE-SPEC.md`, prior records under `docs/m3-review/`, and the current bounded records under `docs/m3-two-blocker-review/`.
- Necessary plan-map deviation: `tests/test_m1_skill_package.py` stopped pinning obsolete exact agent wording while retaining the supported-field whitelist and M1 copied-inventory test. This was required by Task 11's explicit metadata-update step and did not change runtime scope.

## Next atomic action

Human authorization has now been received to revise only the remaining `archive_stale` proposal-binding blocker. Baseline re-verification passed exactly at 680 lines, 82,953 bytes, SHA-256 `84C4FBE8A02346DF4B05761CA8345199C88FFB033C4FD9E7D9A42E7B643A4374`, UTF-8 without BOM, LF only, one LF at EOF. The handoff package is `D:\下载\question-bank-curator-m3-archive-stale-local-codex-handoff.zip`. The next task must read that package, add the minimal Candidate-bound `stale` proposal conclusion and exact `archive_stale` lineage/state transition, freeze a new hash, verify vectors plus all prior closures, run the existing full test suite once, perform a fresh independent read-only specification review, generate one sanitized ZIP, and stop. Do not create an implementation plan or code.

## Open risks

- M3 design is not approved. No M3 behavior is available to users yet.
- `archive_stale` does not yet have a legal proposal payload and lineage binding.
- Three direct symlink tests remain skipped because this Windows host denies symlink creation; junction and hardlink defenses passed. Concurrent path replacement between reparse validation and opening has not been stress-tested.
- Task 9 publication rollback cleanup is best effort. A stale non-authoritative rollback file can remain after cleanup failure, and directory fsync is not available through the frozen Windows/Python path.
- Static mutation guards use reviewed function-level allowlists and dynamic audit hooks cover executed paths; future unexecuted branches still require review.
- Existing project `.pytest_cache`, `__pycache__`, and `.pyc` artifacts were listed but not deleted. No staging or rollback artifact was found.
- Current-task cleanup candidates retained for audit: `C:\Users\lenovo\AppData\Local\Temp\qbc-m2-final-acceptance-zy9cn93d` (superseded) and `C:\Users\lenovo\AppData\Local\Temp\qbc-m2-final-acceptance-l4pmrtyz` (authoritative evidence). The reminder policy explicitly stays in project docs and is not written to global memories.
- No known high-risk defect is intentionally undisclosed; unimplemented areas above are not claimed complete.
