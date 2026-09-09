# Milestone 2 Single-Choice Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILLS during implementation: use `superpowers:executing-plans` to execute this frozen plan and `superpowers:test-driven-development` for every behavior change. The specification is accepted; do not start implementation until the user separately authorizes M2 code changes.

**Status:** Frozen implementation plan; implementation has not started.

**Goal:** Parse one explicitly selected, registry-backed UTF-8 Markdown/TXT source containing strict `[single_choice]` blocks and safely perform its first persistent Candidate/Option materialization without answer association or identity migration.

**Architecture:** A pure line-state parser produces an identity-free intermediate representation and findings. A pure normalization/materialization layer computes frozen fingerprints and allocates injected UUIDs. A service resolves the source through the M1 registry, verifies the byte hash, enforces first-materialization-only semantics, and publishes validated M2 run artifacts plus one M0 candidate document through the existing workspace write boundary.

**Tech stack:** Python 3.12+, standard library runtime (`argparse`, `dataclasses`, `hashlib`, `json`, `os`, `pathlib`, `re`, `unicodedata`, `uuid`), pytest and jsonschema as development-only dependencies.

---

## 0. Authority, baseline, and execution discipline

Repository root:

```text
D:\question-bank-curator
```

Authoritative frozen design:

```text
docs/MILESTONE-2-SINGLE-CHOICE-PARSER-SPEC.md
SHA-256 A4E6CFCEE04A497243DA9282931B1BAA99BA1589702420AF3C5034D88A6A809C
```

The hash above records the frozen specification approved on 2026-08-14. Task 1 must recompute it. Any later design change requires renewed user approval, a new specification hash, an updated authority line, and another plan consistency check before implementation.

Latest observed pre-plan baseline:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Observed result: `90 passed`. Task 1 must run it again; the historical result is not implementation evidence.

This repository is not initialized as Git. Do not run `git init`, commit, branch, worktree, remote, push, pull, reset, or clean. Do not install or upgrade dependencies. Each task ends with file read-back, targeted tests, and the full regression command.

At each task:

1. Record existence and SHA-256 of every target file before editing.
2. Modify only the listed files.
3. Run the named RED test and confirm the failure is caused by the missing requested behavior.
4. Implement only the task's behavior.
5. Run targeted GREEN tests, then the entire suite.
6. If blocked, stop at the exact Task/Step and use the handoff template in section 4.

Reasoning-intensity rule: before any model or reasoning/thinking-intensity change, remind the user and state why the change is useful. Do not switch silently. This is a project execution rule; the global memory update remains pending the protected-path backup gate.

Milestone 2 implementation must not contain answer association, Decision creation, `validated` promotion, rescans, candidate/option migration, heuristic unmarked-question recognition, remote/model calls, dependency installation, databases, or non-text adapters.

## 1. Target file map

All paths are relative to `D:\question-bank-curator`.

```text
skills/curate-question-bank/
├─ SKILL.md                                      # update capability and limits
├─ agents/openai.yaml                            # update short capability metadata only
├─ schemas/
│  ├─ candidate.schema.json                      # unchanged M0 authority
│  ├─ single-choice-parse-report.schema.json     # create
│  ├─ single-choice-parse-issues.schema.json     # create
│  └─ single-choice-parse-run.schema.json        # create
└─ scripts/
   └─ qbcore/
      ├─ validation.py                           # unchanged M0 authority
      ├─ single_choice_parser.py                 # create
      ├─ text_normalization.py                   # create
      ├─ candidate_materializer.py                # create
      ├─ parse_contracts.py                      # create
      ├─ parse_service.py                        # create
      ├─ workspace.py                            # add bounded M2 writes
      └─ cli.py                                  # add parse-single-choice route

tests/
├─ fixtures/m2-parser/
│  ├─ strict-seven.md                            # create from synthetic golden source
│  ├─ strict-two.txt                             # create
│  ├─ malformed.md                               # create
│  ├─ unsupported-type.md                        # create
│  ├─ fenced.md                                  # create
│  └─ utf8-bom-crlf.txt                          # generated as exact bytes by helper
├─ m2_helpers.py                                 # create
├─ test_m2_scope_guard.py                        # create
├─ test_m2_parse_contracts.py                    # create
├─ test_m2_single_choice_parser.py               # create
├─ test_m2_text_normalization.py                 # create
├─ test_m2_candidate_materializer.py             # create
├─ test_m2_source_resolution.py                  # create
├─ test_m2_workspace_publication.py              # create
├─ test_m2_parse_service.py                      # create
├─ test_m2_cli.py                                # create
├─ test_m2_safeguards.py                         # create
└─ test_m2_portability.py                        # create

docs/
├─ MILESTONE-2-SINGLE-CHOICE-PARSER-SPEC.md      # frozen authority; no implementation edit
├─ MILESTONE-2-SINGLE-CHOICE-PARSER-PLAN.md      # this plan
└─ SIDE-CONVERSATION-HANDOFF.md                   # update only at Task 12

START-HERE.md                                    # update only at Task 12
NEW-THREAD-PROMPT.md                             # update only at Task 12
```

`candidate.schema.json`, the other five M0 schemas, `references/identity-contract.md`, and `qbcore/validation.py` are read-only authorities for this milestone.

---

### Task 1: Freeze authority, baseline, helpers, and scope guard

**Files:** create `tests/m2_helpers.py`, `tests/test_m2_scope_guard.py`; inspect but do not modify the M2 spec, M0 schemas/references, and M1 implementation.

- [ ] **Step 1: Recompute authority hashes and test baseline**

Run `Get-FileHash -Algorithm SHA256 docs\MILESTONE-2-SINGLE-CHOICE-PARSER-SPEC.md` and the full pytest command. Expected before edits: the frozen spec hash equals the plan authority line and pytest reports `90 passed`. If the status is not frozen or the hash differs, stop for design reconciliation.

- [ ] **Step 2: Record immutable-contract hashes**

Record SHA-256 for all six M0 schemas, `references/question-types.md`, `references/identity-contract.md`, `references/state-contract.md`, and `qbcore/validation.py`. Store expected values as test constants so later tasks prove these authorities did not change.

- [ ] **Step 3: Write a RED scope-guard test**

Assert the future M2 modules/files exist, the M0 authority hashes remain fixed, only approved issue-code tokens appear in M2 schemas, and forbidden capability tokens are absent from executable M2 code. Run only `tests/test_m2_scope_guard.py`; expected RED is missing M2 files, not a changed M0 hash.

- [ ] **Step 4: Add deterministic M2 helpers**

Create injected clock/UUID sequence, canonical fixture-copy helpers, file/tree byte-hash snapshots, workspace bootstrap through the real M1 inventory path, and subprocess helpers that set `PYTHONDONTWRITEBYTECODE=1`. Helpers must never derive expected fingerprints by importing implementation functions.

- [ ] **Step 5: Add synthetic parser fixtures**

Create the exact fixture map from section 1. Copy the existing synthetic chapter-1 question text into `strict-seven.md`; keep fixtures free of real user data. Generate BOM/CRLF bytes through a test fixture function rather than relying on editor newline behavior.

- [ ] **Step 6: Establish the first GREEN checkpoint**

Narrow the scope guard to already created helpers/fixtures and immutable authorities, run it GREEN, then run the full suite. Record command, exit code, test count, changed files, and the next action: Task 2 Step 1.

### Task 2: Add independent M2 artifact contracts

**Files:** create the three `single-choice-parse-*.schema.json` files, `qbcore/parse_contracts.py`, and `tests/test_m2_parse_contracts.py`.

- [ ] **Step 1: Write RED schema-shape tests**

Test valid minimal `parse-report`, `parse-issues`, and `parse-run` documents plus missing fields, additional properties, invalid UUID/hash/time/locator, unsupported issue codes, bad phases/statuses, and candidate artifact path/hash null-pair consistency. Confirm RED is missing contract support.

- [ ] **Step 2: Create closed JSON Schemas**

Use Draft 2020-12, `additionalProperties: false`, schema version `1.0`, lowercase UUID/hash patterns, explicit enums, and no source正文 fields. `parse-issues` must only allow the six codes listed in the spec and freeze their blocking level and allowed action combinations.

- [ ] **Step 3: Implement the bounded schema validator**

Create `parse_contracts.py` with an explicit document-kind registry and the minimum recursive validation features required by these schemas. Do not broaden M1 `workspace_contracts.py` or add a runtime jsonschema dependency.

- [ ] **Step 4: Add semantic cross-field checks**

Enforce report candidate path/hash null pairing, `complete` requiring a non-null candidate artifact and positive accepted count, `needs_review` requiring no candidate artifact, run artifact hashes for every declared artifact, and matching run/source IDs across documents.

- [ ] **Step 5: Verify schema/read-back parity**

Load each schema as UTF-8 JSON, validate the same fixtures with development-only jsonschema and the runtime validator, and assert both reject every negative vector. Run targeted tests GREEN.

- [ ] **Step 6: Run full regression and record checkpoint**

Run all tests with no pytest cache or bytecode. Confirm the M0 authority hash guard and all M1 tests remain GREEN before Task 3.

### Task 3: Implement the pure supported-grammar state machine

**Files:** create `qbcore/single_choice_parser.py`, `tests/test_m2_single_choice_parser.py`; extend parser fixtures only.

- [ ] **Step 1: Write RED tests for the internal representation**

Assert the dataclass fields, 1-based lines, display numbers, exact preserved stem/option text, stable finding order, and absence of UUID/workspace access. Include `.`, `)`, three bullet markers, blanks between elements, and EOF closure.

- [ ] **Step 2: Implement frozen header and option recognizers**

Compile the exact regex semantics from spec sections 7.1–7.2. Keep recognizers private and marker case-sensitive; do not accept alternative labels or unmarked questions.

- [ ] **Step 3: Implement the line-state transition core**

Parse an already decoded string into `ParsedSingleChoice[]` and `ParseFinding[]`. A supported header opens a block, any question-like header or EOF closes it, and valid options attach only to the open block.

- [ ] **Step 4: Enforce option cardinality and label sequence**

Reject a whole block when it has fewer than 2 or more than 26 options, a duplicate label, a first label other than A, or a non-contiguous label. Never emit a partial Candidate for the rejected block.

- [ ] **Step 5: Prove deterministic ordering with strict fixtures**

Assert `strict-seven.md` yields 7 accepted records with option counts `4,4,4,4,4,3,3`; `strict-two.txt` covers accepted syntax variants. Repeat parsing and compare deep values.

- [ ] **Step 6: Run targeted and full tests**

Run parser and scope-guard tests GREEN, then the full suite. Inspect the parser module for filesystem, UUID, subprocess, network, or workspace imports; any such import blocks Task 4.

### Task 4: Close ambiguous syntax, fences, and unsupported types

**Files:** modify `qbcore/single_choice_parser.py`, parser tests and `malformed.md`, `unsupported-type.md`, `fenced.md` fixtures.

- [ ] **Step 1: Write RED malformed-block matrix**

Cover empty stem/option, one option, 27 options, label gap/repeat/lowercase, option outside a block, question-like line without marker, unknown text inside a block, and a new header closing an invalid block. Assert code and locator without source正文 in summaries.

- [ ] **Step 2: Add unsupported-marker recognition**

Detect `[multiple_choice]`, `[true_false]`, and other bracket markers on question-like headers as `QB-TYPE-UNSUPPORTED`. Mixed-type files must return findings and prevent file-level publication later.

- [ ] **Step 3: Add Markdown fence handling**

Ignore all potential questions inside matching backtick or tilde fences, record unclosed fences as `QB-STRUCTURE-AMBIGUOUS`, and do not implement nested Markdown parsing or syntax highlighting rules.

- [ ] **Step 4: Define outside-block and answer-like behavior**

Ignore ordinary prose/headings and answer-like text outside blocks; reject non-option nonblank text inside a block. Assert no field named answer, correct, resolution, or decision appears in parser output.

- [ ] **Step 5: Enforce file-level no-partial-publication signal**

The pure parser may return accepted records alongside findings for diagnostics, but expose `publishable = accepted_count > 0 and findings is empty`. Test mixed valid/invalid input reports accepted diagnostics while remaining non-publishable.

- [ ] **Step 6: Run targeted and full tests**

Run malformed, unsupported, fence, scope, and full suites. Verify summaries contain rule descriptions and locators only.

### Task 5: Freeze normalization and fingerprint vectors

**Files:** create `qbcore/text_normalization.py`, `tests/test_m2_text_normalization.py`; add static expected vectors to the test file.

- [ ] **Step 1: Write independent RED normalization vectors**

Hard-code expected normalized strings and SHA-256 values for NFC composition, Unicode whitespace collapse, leading/trailing whitespace, case sensitivity, punctuation, empty-after-normalization rejection, repeated option text, and option reordering.

- [ ] **Step 2: Implement `normalize_text`**

Use only `unicodedata.normalize("NFC", value)` and `" ".join(value.split())`. It must not lowercase, transliterate, rewrite punctuation, or mutate the display string.

- [ ] **Step 3: Implement canonical JSON bytes**

Centralize UTF-8 JSON encoding with `ensure_ascii=False`, `sort_keys=True`, and compact separators. Reject unsupported object shapes rather than silently stringifying them.

- [ ] **Step 4: Implement the three fingerprint functions**

Add stem, option-set multiset, and content-revision functions exactly as the spec. Preserve duplicates in option-set input; sort only the option-set representation and preserve order for content revision.

- [ ] **Step 5: Prove invariants and non-invariants**

Assert option reorder keeps option-set fingerprint but changes content-revision fingerprint; duplicate removal changes option-set fingerprint; NFC-equivalent and whitespace-equivalent text hashes match; case changes do not.

- [ ] **Step 6: Run targeted and full tests**

Run normalization, parser, scope guard, and full regression. Read back the implementation to ensure no locale, platform newline, or random behavior enters hashes.

### Task 6: Materialize first-pass Candidate and Option identities

**Files:** create `qbcore/candidate_materializer.py`, `tests/test_m2_candidate_materializer.py`.

- [ ] **Step 1: Write RED exact-document test**

Using two parsed questions and a fixed UUID iterator, assert exact Candidate/Option ID allocation order, revision 1, status `candidate`, question type, locators, labels, positions, empty previous labels, source refs, and fingerprints.

- [ ] **Step 2: Implement materialization as a pure function**

Accept parsed records, source ID, and UUID factory; return one M0 candidate document. Allocate one Candidate UUID followed immediately by its Option UUIDs in source order. Do not read files or write workspace state.

- [ ] **Step 3: Enforce UUID and ownership invariants**

Reject non-UUID source IDs, exhausted/duplicate/ineligible UUID factory output, duplicate Candidate locators, duplicate Option locators within a Candidate, and mismatched ownership before returning.

- [ ] **Step 4: Validate through the frozen M0 validator**

Call `validate_document("candidate", document)` and turn any validation issue into a typed materialization error. Do not change `validation.py` or relax the schema.

- [ ] **Step 5: Cover zero records and UUID side effects**

Zero records must fail before consuming UUIDs because M0 forbids an empty candidate document. Parse findings must also prevent the service from invoking the materializer.

- [ ] **Step 6: Run targeted and full tests**

Run materializer, normalization, parser, scope, and complete tests. Recompute M0 authority hashes and compare to Task 1.

### Task 7: Add duplicate grouping without identity merging

**Files:** modify `qbcore/candidate_materializer.py`, its tests, and the strict-seven expected assertions.

- [ ] **Step 1: Write RED duplicate-group tests**

Assert equal content-revision fingerprints within one batch receive `content-sha256:<full-hash>`, unique candidates receive null, and duplicate Candidates/Options retain distinct injected UUIDs.

- [ ] **Step 2: Implement a two-pass grouping algorithm**

First compute content fingerprints and counts, then materialize in original order. Do not sort Candidates, collapse records, select a canonical record, or use the fingerprint as an ID.

- [ ] **Step 3: Cover duplicate option text**

Assert two identical option texts remain two Option objects with distinct IDs, positions and source locators but equal normalized-text fingerprints. Do not emit migration ambiguity on initial creation.

- [ ] **Step 4: Bind golden chapter expectations**

Assert 7 Candidate records; questions 6 and 7 share a duplicate group and fingerprints but not IDs; each retains all 3 source options. Do not compare to the older M0 hand-authored `tests/expected/golden-course/candidates.json`, whose reduced option rows test other contracts.

- [ ] **Step 5: Add local and cross-document uniqueness checks**

Verify every Candidate ID and Option ID in the generated document is unique, every option owner exists, and source IDs/locators are coherent. Cross-source duplicate detection remains absent.

- [ ] **Step 6: Run targeted and full tests**

Run materialization/golden tests and the entire suite. Confirm no Decision/review migration code entered the module.

### Task 8: Resolve and verify one source through the M1 registry

**Files:** create `qbcore/parse_service.py`, `tests/test_m2_source_resolution.py`.

- [ ] **Step 1: Write RED source-resolution tests**

Bootstrap a real M1 workspace and test valid lookup plus missing/duplicate source ID, `presence=missing`, missing project/registry, dataset mismatch, invalid registry, unsupported extension, source file absent, and current hash mismatch.

- [ ] **Step 2: Reuse M1 root and document validation**

Call `validate_roots`, load workspace project/registry with existing validation, and require an existing initialized workspace. Do not run discovery or update SourceIdentity implicitly.

- [ ] **Step 3: Resolve registry relative paths safely**

Reject absolute paths, `..`, ADS-like path segments, and any canonical or reparse-point result outside `input_root`. Build the source path only from the registry entry, never from an extra CLI path.

- [ ] **Step 4: Verify bytes before decoding and UUID allocation**

Open the file read-only, stream SHA-256, compare it to registry, then decode with strict `utf-8-sig`. Prove all precondition failures occur before the Candidate UUID factory is touched.

- [ ] **Step 5: Handle supported encoding/newlines**

Test UTF-8, BOM, LF, CRLF and CR yield identical parsed structures and locators for equivalent logical lines; invalid bytes become `QB-SOURCE-READ-FAILED` diagnostics without正文 leakage.

- [ ] **Step 6: Run targeted and full tests**

Run source-resolution, path, discovery, registry and full tests. Snapshot the input tree before/after every failure vector and assert equality.

### Task 9: Publish M2 artifacts through the workspace boundary

**Files:** modify `qbcore/workspace.py`, `qbcore/parse_service.py`; create `tests/test_m2_workspace_publication.py`.

- [ ] **Step 1: Write RED allowed-target tests**

Require exact filenames for the three M2 run artifacts and exact candidate target `candidates/sources/<source_id>.json`. Reject path separators, bad UUID names, traversal, absolute targets, and unregistered artifact names.

- [ ] **Step 2: Add bounded Workspace methods**

Add M2-specific write methods that call `RootPolicy.assert_write_target`, M2 contract validation, M0 candidate validation, UTF-8 atomic staging, fsync and read-back. Do not broaden the generic M1 allowlist.

- [ ] **Step 3: Implement no-overwrite candidate publication**

Use an implementation that fails if the final target already exists. Add a real Windows filesystem probe and a concurrent-race test; do not treat a pre-check followed by ordinary `os.replace` as sufficient no-overwrite protection.

- [ ] **Step 4: Implement publication ordering**

Write validated issues/report and a `publication` parse-run, publish the candidate, verify its bytes/hash/schema, then atomically mark the run complete. A needs-review run writes only run artifacts and never creates a candidate target.

- [ ] **Step 5: Add fault injection at every boundary**

Inject failures during staging create/write/flush/read-back, run artifact publication, no-overwrite publish, candidate read-back and final run update. Assert existing candidate/registry files remain byte-identical and no partial JSON is authoritative.

- [ ] **Step 6: Run targeted and full tests**

Run workspace publication, M1 workspace/recovery and full suites. Record the actual Windows primitive and result in the task checkpoint; if the atomic property cannot be demonstrated, stop here.

### Task 10: Complete service recovery and CLI behavior

**Files:** modify `qbcore/parse_service.py`, `qbcore/cli.py`; create `tests/test_m2_parse_service.py`, `tests/test_m2_cli.py`.

- [ ] **Step 1: Write RED end-to-end service tests**

Cover success, no questions, parse findings, unsupported type, existing valid candidate, existing corrupted candidate, stale source, and a candidate published with an incomplete run. Assert exact statuses and artifacts.

- [ ] **Step 2: Implement first-materialization orchestration**

Resolve source, check target absence, parse, build issues/report, materialize only if publishable, and publish. Existing target must produce `QB-IDENTITY-AMBIGUOUS`/failed-closed behavior without overwrite or UUID allocation.

- [ ] **Step 3: Implement exact crash repair**

If an incomplete parse run names an existing candidate whose path, hash, source ID/revision/content hash and contracts all match, update only that run to complete. Any mismatch fails and does not generate IDs or modify the candidate.

- [ ] **Step 4: Add `parse-single-choice` CLI routing**

Require all three flags, validate lowercase UUID, keep business rules in the service, output stable JSON to stdout, sanitize stderr, and preserve existing `inventory`/`restore` behavior.

- [ ] **Step 5: Enforce exit codes and no-answer semantics**

Assert exit `0` for complete, `3` for needs_review, and `2` for precondition/runtime failure. Verify all published Candidates remain `candidate` and no Decision, resolved option, answer field or adjacent-file read occurs.

- [ ] **Step 6: Run CLI and full regression**

Run in-process and subprocess tests, then the entire suite. Run an explicit smoke command against a temporary synthetic input/workspace and read back every artifact before proceeding.

### Task 11: Update Skill truthfulness, portability, and safeguards

**Files:** modify `skills/curate-question-bank/SKILL.md`, `agents/openai.yaml`; create `tests/test_m2_safeguards.py`, `tests/test_m2_portability.py`.

- [ ] **Step 1: Write RED capability-documentation tests**

Require the Skill to describe explicit source selection, strict single-choice grammar, first-materialization-only behavior, no answer association, no identity migration, supported encodings/extensions, outputs and exit statuses.

- [ ] **Step 2: Update Skill and agent metadata narrowly**

Advertise only implemented M2 behavior. Do not imply arbitrary Markdown understanding, answer resolution, batch parsing, PDF/OCR, incremental refresh, remote support or validated question-bank export.

- [ ] **Step 3: Expand static and runtime safety tests**

Reject network/process/package-manager/database imports in M2 modules, source-text execution primitives, writes outside workspace, implicit home/temp defaults, and command output containing fixture stems/options.

- [ ] **Step 4: Add input immutability and hostile-path tests**

Cover symlink/junction source replacement where available, workspace-inside-input pruning, unicode/case path variants, path traversal in a tampered registry, and read-only input files. Mark platform skips with precise reasons.

- [ ] **Step 5: Verify copied-skill portability**

Copy only the Skill package to an ASCII temporary directory outside the repository, invoke inventory and parse using synthetic fixtures, and prove schema/reference/runtime resolution does not rely on repository-relative or host-private paths.

- [ ] **Step 6: Run targeted and full tests**

Run safeguard, portability, package, scope and full suites. Confirm no host temp artifact is automatically deleted; list current-task temp cleanup candidates for Task 12.

### Task 12: Final audit, hashes, handoff, and acceptance gate

**Files:** update `START-HERE.md`, `NEW-THREAD-PROMPT.md`, `docs/SIDE-CONVERSATION-HANDOFF.md`; do not modify runtime unless an audit failure starts a new RED/GREEN loop in the owning task.

- [ ] **Step 1: Audit spec-to-test coverage and forbidden scope**

Map every acceptance item in spec section 19 to at least one named test. Run `rg` checks for answer association, Decision creation, validated promotion, migration/rescan, remote/network, dependency installation, unsupported adapters, unfinished-marker tokens and accidental real-data paths.

- [ ] **Step 2: Run the single authoritative full command twice**

Run `$env:PYTHONDONTWRITEBYTECODE='1'; D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q` twice from the repository root. Both runs must have exit code 0 and identical collected/pass counts.

- [ ] **Step 3: Perform final read-back and mutation audit**

Parse all JSON/YAML/Python/docs as applicable, recompute M0 authority hashes, compare input fixture tree snapshots, verify all changed files are in this plan, and list any temporary artifacts without deleting pre-existing/user-owned files.

- [ ] **Step 4: Run final synthetic CLI acceptance**

From clean temporary roots: inventory, obtain the strict source ID, parse successfully, validate the candidate document and 7/`4,4,4,4,4,3,3` counts, then rerun parse and prove no overwrite/ID churn. Exercise one needs-review fixture and one stale-registry failure.

- [ ] **Step 5: Update canonical handoff files**

Record objective, accepted scope, frozen spec/plan hashes, complete test command/result, changed files, actual Windows atomic-publication result, unverified areas, and exactly one next atomic action. Do not claim no high-risk defect exists; state whether any known high-risk defect remains undisclosed.

- [ ] **Step 6: Stop at the M2 acceptance gate**

Report completed implementation/artifacts, verification, acceptance status, unresolved risks and next maintenance action. Do not begin answer association or M3. Do not initialize or commit Git.

---

## 2. Spec-to-task coverage

| Spec area | Primary tasks |
|---|---|
| Authority, immutable M0/M1 boundaries | 1, 12 |
| M2 artifact schemas and issue codes | 2 |
| Strict grammar and internal representation | 3, 4 |
| Encoding, normalization and fingerprints | 5, 8 |
| Candidate/Option first identity allocation | 6 |
| Duplicate grouping without merging | 7 |
| Explicit source ID and registry/hash gates | 8 |
| Workspace layout, atomic publication, no overwrite | 9 |
| Crash repair, orchestration and CLI | 10 |
| Privacy, hostile paths, no-answer boundary | 4, 8, 10, 11 |
| Skill truthfulness and copied-package portability | 11 |
| Full acceptance and cross-thread handoff | 12 |

## 3. Planned verification commands

Targeted pattern:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m2_single_choice_parser.py -q
```

Full regression:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Documentation placeholder audit:

```powershell
rg -n "T[O]DO|T[B]D|F[I]XME|P[L]ACEHOLDER" docs -g "MILESTONE-2-*.md"
```

Authority hashes:

```powershell
Get-FileHash -Algorithm SHA256 docs\MILESTONE-2-SINGLE-CHOICE-PARSER-SPEC.md
Get-FileHash -Algorithm SHA256 docs\MILESTONE-2-SINGLE-CHOICE-PARSER-PLAN.md
```

No test count is predicted here. Task 12 records the actually collected and passed total.

## 4. Blocked-task handoff template

When any task cannot complete, stop before the next task and record:

```text
Milestone: 2
Task / Step:
Objective of this atomic step:
Status: blocked | red_expected | implementation_failed | environment_failed | spec_conflict
Exact command:
Exit code:
Observed failure summary:
Expected behavior:
Files changed in this step:
Files and hashes before change:
Tests currently passing/failing:
Input/workspace mutation check:
Backup/permission state:
Reasoning intensity currently in use:
Reminder required before any intensity/model change: yes
Unverified areas:
Next atomic action only:
```

Do not paste source question正文, secrets, full recursive directory dumps, or unrelated logs into the handoff.

## 5. Next atomic action after explicit implementation authorization

`Task 1 / Step 1 — recompute the approved M2 specification hash and rerun the 90-test M1 baseline.`
