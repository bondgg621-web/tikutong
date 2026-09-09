# Milestone 1 Skill Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portable, stdlib-only Skill runtime that preflights explicit roots, discovers files without modifying input, maintains a file-level SourceIdentity registry, and publishes recoverable workspace state without implementing question parsing, answer association, or incremental execution.

**Architecture:** The CLI accepts explicit `input_root` and `workspace_root`, validates their canonical relationship before any write, builds a capability snapshot, performs a deterministic full discovery pass, reconciles file-level SourceIdentity in memory, checkpoints the previous complete control state, then atomically publishes validated JSON artifacts inside the workspace. Persistent artifacts use new Milestone 1 contracts; the frozen Milestone 0 manifest and run-state contracts remain unchanged.

**Tech Stack:** Python 3.12+, standard library runtime (`argparse`, `dataclasses`, `hashlib`, `json`, `os`, `pathlib`, `shutil`, `uuid`), pytest and jsonschema as development-only dependencies, YAML metadata as static text.

---

## 0. Authority, frozen boundaries, and execution discipline

Repository root:

```text
D:\question-bank-curator
```

Authoritative design:

```text
docs/MILESTONE-1-WORKSPACE-ISOLATION-SPEC.md
SHA-256 C61A5A79F3443318B1E35B0C793404D3D3F57F027156B84E60FA1B10ACFF96A5
```

Baseline command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected before implementation: `30 passed`.

This repository is not a Git repository. Do not run `git init`, commit, branch, worktree, remote, push, reset, or clean. Each task ends with a file/read-back and test checkpoint instead of a commit. If Git is authorized in a separate request, add commits outside this plan without changing its functional steps.

Every task follows these rules:

1. Record whether each listed target file exists and its SHA-256 before editing.
2. Change only files listed for the task.
3. Run the named RED test and verify the failure reason matches the missing behavior.
4. Add only the minimum implementation specified by the task.
5. Run the named GREEN test and the full regression command.
6. If the task remains blocked, stop at that Task/Step and report the handoff fields from Task 12.
7. Never install a dependency, initialize Git, read real question banks, or use a network service.

Milestone 1 must not contain:

- question, answer, explanation, PDF, DOCX, OCR, spreadsheet, image, or ZIP parsers;
- content-role classification or cross-file association;
- Candidate, Option, ReviewItem, or Decision generation;
- unchanged-file skipping or any other incremental executor;
- Electron, SQLite, GUI, HTML quiz, MCP, Plugin, or remote calls;
- changes to the six Milestone 0 schemas or `qbcore/validation.py`.

## 1. Target file map

All paths below are relative to `D:\question-bank-curator`.

```text
skills/curate-question-bank/
├─ SKILL.md
├─ agents/
│  └─ openai.yaml
├─ schemas/
│  ├─ workspace-project.schema.json
│  ├─ capability-matrix.schema.json
│  ├─ discovery-inventory.schema.json
│  ├─ source-registry.schema.json
│  ├─ workspace-run.schema.json
│  ├─ workspace-issues.schema.json
│  └─ checkpoint-manifest.schema.json
└─ scripts/
   ├─ curate_question_bank.py
   └─ qbcore/
      ├─ __init__.py
      ├─ validation.py                 # unchanged
      ├─ workspace_contracts.py       # M1 serialization/runtime validation
      ├─ paths.py                     # canonical roots and write boundary
      ├─ capabilities.py              # deterministic preflight snapshot
      ├─ discovery.py                 # read-only full inventory
      ├─ registry.py                  # file-level SourceIdentity reconcile
      ├─ workspace.py                 # layout and atomic JSON publication
      ├─ recovery.py                  # checkpoint creation/validation/restore
      └─ cli.py                       # orchestration only

tests/
├─ fixtures/m1-discovery/input/
│  ├─ alpha.txt
│  ├─ beta.md
│  ├─ unsupported.pdf
│  └─ nested/gamma.TXT
├─ m1_helpers.py
├─ test_m1_scope_guard.py
├─ test_m1_skill_package.py
├─ test_m1_workspace_contracts.py
├─ test_m1_paths.py
├─ test_m1_capabilities.py
├─ test_m1_discovery.py
├─ test_m1_source_registry.py
├─ test_m1_workspace.py
├─ test_m1_recovery.py
├─ test_m1_cli.py
└─ test_m1_safeguards.py

docs/
├─ MILESTONE-1-WORKSPACE-ISOLATION-SPEC.md  # unchanged
├─ MILESTONE-1-SKILL-INFRASTRUCTURE-PLAN.md # this plan
└─ SIDE-CONVERSATION-HANDOFF.md             # update only at final gate

START-HERE.md                               # update only at final gate
NEW-THREAD-PROMPT.md                        # update only at final gate
```

The new schemas are Milestone 1 workspace contracts. They do not replace or extend `manifest.schema.json` or `run-state.schema.json`.

---

### Task 1: Freeze the phase boundary and deterministic test helpers

**Files:**

- Create: `tests/test_m1_scope_guard.py`
- Create: `tests/m1_helpers.py`
- Create: `tests/fixtures/m1-discovery/input/alpha.txt`
- Create: `tests/fixtures/m1-discovery/input/beta.md`
- Create: `tests/fixtures/m1-discovery/input/unsupported.pdf`
- Create: `tests/fixtures/m1-discovery/input/nested/gamma.TXT`

- [ ] **Step 1: Record the baseline and frozen specification hash**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
Get-FileHash -Algorithm SHA256 docs\MILESTONE-1-WORKSPACE-ISOLATION-SPEC.md
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: the design hash is `C61A5A79F3443318B1E35B0C793404D3D3F57F027156B84E60FA1B10ACFF96A5` and pytest reports `30 passed`.

- [ ] **Step 2: Add synthetic discovery fixtures**

Create the four files with these exact bytes:

```text
# alpha.txt (UTF-8, final LF)
Synthetic alpha source.

# beta.md (UTF-8, final LF)
# Synthetic beta

# unsupported.pdf (ASCII bytes, not a real PDF)
synthetic unsupported container

# nested/gamma.TXT (UTF-8, final LF)
Synthetic gamma source.
```

These are deliberately content-free engineering fixtures; they are not real questions, course materials, or research data.

- [ ] **Step 3: Add deterministic helper functions**

Create `tests/m1_helpers.py`:

```python
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID


FIXED_TIME = datetime(2026, 8, 13, 0, 0, tzinfo=timezone.utc)


class UUIDSequence:
    def __init__(self, start: int = 1) -> None:
        self._next = start

    def __call__(self) -> UUID:
        value = UUID(int=self._next, version=4)
        self._next += 1
        return value


def fixed_now() -> datetime:
    return FIXED_TIME


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def tree_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): file_hash(path)
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold())
        if path.is_file()
    }
```

- [ ] **Step 4: Write the initial scope guard**

Create `tests/test_m1_scope_guard.py`:

```python
from pathlib import Path

from conftest import SKILL_ROOT


FORBIDDEN_RUNTIME_NAMES = {
    "parser.py",
    "answer_association.py",
    "candidate_builder.py",
    "incremental_executor.py",
}
FROZEN_M0 = {
    "candidate.schema.json",
    "decision.schema.json",
    "manifest.schema.json",
    "question-bank-interchange.schema.json",
    "review-item.schema.json",
    "run-state.schema.json",
}


def test_m1_does_not_add_forbidden_runtime_modules() -> None:
    runtime = SKILL_ROOT / "scripts" / "qbcore"
    assert not ({path.name for path in runtime.glob("*.py")} & FORBIDDEN_RUNTIME_NAMES)


def test_m0_schema_set_remains_present_and_distinct_from_m1() -> None:
    schemas = {path.name for path in (SKILL_ROOT / "schemas").glob("*.json")}
    assert FROZEN_M0 <= schemas
    assert "workspace-run.schema.json" not in FROZEN_M0
```

- [ ] **Step 5: Run the guard and regression suite**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_scope_guard.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: `2 passed`, then `32 passed`.

**Stop condition:** If any fixture resembles real user/course/research content, replace it with the exact synthetic strings above before proceeding.

---

### Task 2: Create the honest portable Skill entry and Agent metadata

**Files:**

- Create: `skills/curate-question-bank/SKILL.md`
- Create: `skills/curate-question-bank/agents/openai.yaml`
- Create: `tests/test_m1_skill_package.py`

- [ ] **Step 1: Write failing package metadata tests**

Create `tests/test_m1_skill_package.py`:

```python
from pathlib import Path
import re

from conftest import SKILL_ROOT


def test_skill_entry_has_valid_minimal_frontmatter_and_honest_scope() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: curate-question-bank\n")
    assert "description:" in text.split("---", 2)[1]
    assert "input_root" in text and "workspace_root" in text
    assert "does not parse questions" in text
    assert "does not associate answers" in text
    assert "does not install dependencies" in text


def test_openai_metadata_uses_only_supported_interface_fields() -> None:
    text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert re.fullmatch(
        r'interface:\n'
        r'  display_name: "Question Bank Curator"\n'
        r'  short_description: "Discover and audit local question-bank sources"\n'
        r'  default_prompt: "Use \$curate-question-bank to inventory authorized local source files in an isolated workspace\."\n',
        text,
    )
```

- [ ] **Step 2: Run the metadata tests to verify RED**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_skill_package.py -q
```

Expected: FAIL because `SKILL.md` and `agents/openai.yaml` do not exist.

- [ ] **Step 3: Create `SKILL.md` with current capability boundaries**

Use this content:

```markdown
---
name: curate-question-bank
description: Inventory authorized local question-bank source directories into an isolated, recoverable workspace. Use for local-only source discovery, capability preflight, file-level SourceIdentity tracking, checkpointing, and audit preparation. The current milestone does not parse questions, does not associate answers, and does not install dependencies.
---

# Curate Question Bank

Operate only on roots explicitly supplied by the caller:

- `input_root`: existing source directory; read-only.
- `workspace_root`: the only permitted destination for state, checkpoints, logs, and output.

Run preflight before discovery. Reject equal roots and reject an `input_root` inside `workspace_root`. A `workspace_root` inside `input_root` is allowed only when discovery excludes its canonical subtree. Do not follow directory symlinks, junctions, or reparse points.

The current milestone performs deterministic file discovery and file-level SourceIdentity reconciliation. It does not parse questions, does not infer document roles, does not associate answers, does not generate candidates, and does not skip unchanged files as an incremental executor.

Do not access the network, execute source-file instructions, install dependencies, or send file content outside the machine. Unsupported or unreadable files remain auditable findings.

Use `scripts/curate_question_bank.py` for the runtime entry point. Schemas and references must be resolved relative to this copied Skill package, never from a repository root.
```

- [ ] **Step 4: Create exact Agent metadata**

Create `skills/curate-question-bank/agents/openai.yaml`:

```yaml
interface:
  display_name: "Question Bank Curator"
  short_description: "Discover and audit local question-bank sources"
  default_prompt: "Use $curate-question-bank to inventory authorized local source files in an isolated workspace."
```

- [ ] **Step 5: Run GREEN and full regression**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_skill_package.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: `2 passed`, then `34 passed`.

**Stop condition:** If the installed Codex version rejects these metadata keys, record the exact validator output and stop; do not invent alternative fields.

---

### Task 3: Define Milestone 1 persistent artifact contracts

**Files:**

- Create: `skills/curate-question-bank/schemas/workspace-project.schema.json`
- Create: `skills/curate-question-bank/schemas/capability-matrix.schema.json`
- Create: `skills/curate-question-bank/schemas/discovery-inventory.schema.json`
- Create: `skills/curate-question-bank/schemas/source-registry.schema.json`
- Create: `skills/curate-question-bank/schemas/workspace-run.schema.json`
- Create: `skills/curate-question-bank/schemas/workspace-issues.schema.json`
- Create: `skills/curate-question-bank/schemas/checkpoint-manifest.schema.json`
- Create: `skills/curate-question-bank/scripts/qbcore/workspace_contracts.py`
- Create: `tests/test_m1_workspace_contracts.py`

- [ ] **Step 1: Write failing schema inventory and frozen-M0 tests**

Create the first section of `tests/test_m1_workspace_contracts.py`:

```python
from __future__ import annotations

import json
from copy import deepcopy

import jsonschema

from conftest import SKILL_ROOT


M1_SCHEMAS = {
    "workspace-project",
    "capability-matrix",
    "discovery-inventory",
    "source-registry",
    "workspace-run",
    "workspace-issues",
    "checkpoint-manifest",
}


def load_schema(name: str) -> dict:
    return json.loads((SKILL_ROOT / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))


def test_every_m1_schema_is_valid_draft_2020_12() -> None:
    for name in M1_SCHEMAS:
        jsonschema.Draft202012Validator.check_schema(load_schema(name))


def test_m1_does_not_change_m0_run_state_semantics() -> None:
    schema = load_schema("run-state")
    assert schema["required"] == ["run_id", "manifest_source_id", "phase", "status"]
    assert schema["properties"]["phase"]["enum"] == [
        "preflight", "candidate", "review", "decision", "complete"
    ]
```

- [ ] **Step 2: Run the schema inventory test to verify RED**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_workspace_contracts.py -q
```

Expected: FAIL because the seven Milestone 1 schemas do not exist.

- [ ] **Step 3: Create the seven exact schemas**

Create `workspace-project.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "workspace-project.schema.json",
  "type": "object",
  "required": ["schema_version", "project_format_version", "dataset_id", "created_at"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": "1.0"},
    "project_format_version": {"const": "1.0"},
    "dataset_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"},
    "created_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$"}
  }
}
```

Create `capability-matrix.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "capability-matrix.schema.json",
  "type": "object",
  "required": ["schema_version", "generated_at", "skill_version", "python_version", "input_root_fingerprint", "workspace_root_fingerprint", "network", "capabilities"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": "1.0"},
    "generated_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$"},
    "skill_version": {"type": "string", "minLength": 1},
    "python_version": {"type": "string", "minLength": 1},
    "input_root_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "workspace_root_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "network": {
      "type": "object", "required": ["status", "attempted"], "additionalProperties": false,
      "properties": {"status": {"const": "not_authorized"}, "attempted": {"const": false}}
    },
    "capabilities": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "required": ["id", "status", "detail"], "additionalProperties": false,
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "status": {"enum": ["available", "unavailable", "unsupported", "not_authorized"]},
          "detail": {"type": "string", "minLength": 1}
        }
      }
    }
  }
}
```

Create `discovery-inventory.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "discovery-inventory.schema.json",
  "type": "object",
  "required": ["schema_version", "generated_at", "input_root_fingerprint", "workspace_root_fingerprint", "entries", "skipped_directories", "issues"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": "1.0"},
    "generated_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$"},
    "input_root_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "workspace_root_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "entries": {
      "type": "array",
      "items": {
        "type": "object", "required": ["relative_path", "size_bytes", "content_hash", "support_status"], "additionalProperties": false,
        "properties": {
          "relative_path": {"type": "string", "minLength": 1},
          "size_bytes": {"type": ["integer", "null"], "minimum": 0},
          "content_hash": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
          "support_status": {"enum": ["builtin_text", "unsupported", "read_failed"]}
        },
        "allOf": [{
          "if": {"properties": {"support_status": {"const": "read_failed"}}, "required": ["support_status"]},
          "then": {"properties": {"size_bytes": {"type": "null"}, "content_hash": {"type": "null"}}},
          "else": {"properties": {"size_bytes": {"type": "integer", "minimum": 0}, "content_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}}
        }]
      }
    },
    "skipped_directories": {
      "type": "array",
      "items": {
        "type": "object", "required": ["relative_path", "reason"], "additionalProperties": false,
        "properties": {"relative_path": {"type": "string", "minLength": 1}, "reason": {"const": "reparse_point"}}
      }
    },
    "issues": {
      "type": "array",
      "items": {
        "type": "object", "required": ["code", "relative_path", "summary"], "additionalProperties": false,
        "properties": {
          "code": {"enum": ["QB-SOURCE-UNSUPPORTED", "QB-SOURCE-READ-FAILED"]},
          "relative_path": {"type": "string", "minLength": 1},
          "summary": {"type": "string", "minLength": 1}
        }
      }
    }
  }
}
```

Create `source-registry.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "source-registry.schema.json",
  "type": "object",
  "required": ["schema_version", "dataset_id", "registry_revision", "updated_at", "sources"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": "1.0"},
    "dataset_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"},
    "registry_revision": {"type": "integer", "minimum": 0},
    "updated_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$"},
    "sources": {
      "type": "array",
      "items": {
        "type": "object", "required": ["source_id", "current_relative_path", "path_history", "current_content_hash", "revision", "presence"], "additionalProperties": false,
        "properties": {
          "source_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"},
          "current_relative_path": {"type": "string", "minLength": 1},
          "path_history": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
          "current_content_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
          "revision": {"type": "integer", "minimum": 1},
          "presence": {"enum": ["present", "missing"]}
        }
      }
    }
  }
}
```

Create `workspace-run.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "workspace-run.schema.json",
  "type": "object",
  "required": ["schema_version", "run_id", "phase", "status", "started_at", "updated_at", "input_root_fingerprint", "workspace_root_fingerprint", "artifacts"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": "1.0"},
    "run_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"},
    "phase": {"enum": ["preflight", "discovery", "registry", "checkpoint", "complete"]},
    "status": {"enum": ["running", "failed", "complete"]},
    "started_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$"},
    "updated_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$"},
    "input_root_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "workspace_root_fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "artifacts": {
      "type": "array",
      "items": {
        "type": "object", "required": ["kind", "relative_path", "content_hash"], "additionalProperties": false,
        "properties": {
          "kind": {"enum": ["preflight", "discovery", "issues", "registry"]},
          "relative_path": {"type": "string", "minLength": 1},
          "content_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        }
      }
    }
  }
}
```

Create `workspace-issues.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "workspace-issues.schema.json",
  "type": "object",
  "required": ["schema_version", "run_id", "issues"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": "1.0"},
    "run_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"},
    "issues": {
      "type": "array",
      "items": {
        "type": "object", "required": ["issue_id", "code", "status", "summary", "relative_paths", "source_ids"], "additionalProperties": false,
        "properties": {
          "issue_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"},
          "code": {"enum": ["QB-SOURCE-UNSUPPORTED", "QB-SOURCE-READ-FAILED", "QB-IDENTITY-AMBIGUOUS"]},
          "status": {"enum": ["open", "resolved"]},
          "summary": {"type": "string", "minLength": 1},
          "relative_paths": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
          "source_ids": {"type": "array", "items": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"}}
        }
      }
    }
  }
}
```

Create `checkpoint-manifest.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "checkpoint-manifest.schema.json",
  "type": "object",
  "required": ["schema_version", "checkpoint_id", "created_at", "reason", "files"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": "1.0"},
    "checkpoint_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"},
    "created_at": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$"},
    "reason": {"enum": ["registry_update", "explicit_recovery"]},
    "files": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "required": ["relative_path", "content_hash", "size_bytes"], "additionalProperties": false,
        "properties": {
          "relative_path": {"type": "string", "minLength": 1},
          "content_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
          "size_bytes": {"type": "integer", "minimum": 0}
        }
      }
    }
  }
}
```

These schemas emit only the three already-frozen issue codes used by Milestone 1. Do not change `validation.py`.

- [ ] **Step 4: Add stdlib runtime document validation**

Create `workspace_contracts.py` with this complete implementation:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DOCUMENT_KINDS = {
    "workspace-project",
    "capability-matrix",
    "discovery-inventory",
    "source-registry",
    "workspace-run",
    "workspace-issues",
    "checkpoint-manifest",
}


@dataclass(frozen=True)
class WorkspaceContractIssue:
    code: str
    path: str
    message: str


def workspace_schema_path(name: str) -> Path:
    if name not in DOCUMENT_KINDS:
        raise ValueError(f"unknown workspace document kind: {name}")
    return Path(__file__).resolve().parents[2] / "schemas" / f"{name}.schema.json"


def _issue(issues: list[WorkspaceContractIssue], path: str, message: str) -> None:
    issues.append(WorkspaceContractIssue("QB-WORKSPACE-CONTRACT", path, message))


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValueError(f"unsupported workspace schema type: {expected}")


def _validate_node(
    value: Any,
    schema: dict,
    path: str,
    issues: list[WorkspaceContractIssue],
) -> None:
    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(_matches_type(value, choice) for choice in choices):
            _issue(issues, path, f"must have type {' or '.join(choices)}")
            return
    if "const" in schema and value != schema["const"]:
        _issue(issues, path, f"must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        _issue(issues, path, "must be one of the frozen enum values")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            _issue(issues, path, "must not be empty")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            _issue(issues, path, "does not match the required pattern")
    if isinstance(value, int) and not isinstance(value, bool):
        if value < schema.get("minimum", value):
            _issue(issues, path, f"must be at least {schema['minimum']}")
    if isinstance(value, dict):
        required = set(schema.get("required", []))
        missing = sorted(required - set(value))
        for key in missing:
            _issue(issues, f"{path}.{key}", "is required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                _issue(issues, f"{path}.{key}", "is not allowed")
        for key, child in properties.items():
            if key in value:
                _validate_node(value[key], child, f"{path}.{key}", issues)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            _issue(issues, path, f"must contain at least {schema['minItems']} item(s)")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _validate_node(item, item_schema, f"{path}[{index}]", issues)


def validate_workspace_document(kind: str, value: Any) -> list[WorkspaceContractIssue]:
    if kind not in DOCUMENT_KINDS:
        raise ValueError(f"unknown workspace document kind: {kind}")
    schema = json.loads(workspace_schema_path(kind).read_text(encoding="utf-8"))
    issues: list[WorkspaceContractIssue] = []
    _validate_node(value, schema, kind, issues)
    if kind == "discovery-inventory" and isinstance(value, dict):
        for index, entry in enumerate(value.get("entries", [])):
            if not isinstance(entry, dict):
                continue
            failed = entry.get("support_status") == "read_failed"
            null_pair = entry.get("content_hash") is None and entry.get("size_bytes") is None
            if failed != null_pair:
                _issue(
                    issues,
                    f"{kind}.entries[{index}]",
                    "only read_failed entries may have null hash and size",
                )
    return issues
```

The implementation deliberately validates only the schema keywords used by the seven files. JSON Schema remains the development oracle; the stdlib validator remains the runtime gate.

- [ ] **Step 5: Add valid samples and overlap-invalid parameterization**

Append this complete test support and the tests:

```python
from qbcore.workspace_contracts import validate_workspace_document


U1 = "00000000-0000-4000-8000-000000000001"
U2 = "00000000-0000-4000-8000-000000000002"
H1 = "a" * 64
STAMP = "2026-08-13T00:00:00Z"


def valid_documents() -> dict[str, dict]:
    return {
        "workspace-project": {
            "schema_version": "1.0", "project_format_version": "1.0",
            "dataset_id": U1, "created_at": STAMP,
        },
        "capability-matrix": {
            "schema_version": "1.0", "generated_at": STAMP,
            "skill_version": "0.1.0", "python_version": "3.12.0",
            "input_root_fingerprint": H1, "workspace_root_fingerprint": H1,
            "network": {"status": "not_authorized", "attempted": False},
            "capabilities": [{"id": "sha256", "status": "available", "detail": "stdlib"}],
        },
        "discovery-inventory": {
            "schema_version": "1.0", "generated_at": STAMP,
            "input_root_fingerprint": H1, "workspace_root_fingerprint": H1,
            "entries": [{
                "relative_path": "a.txt", "size_bytes": 1,
                "content_hash": H1, "support_status": "builtin_text",
            }],
            "skipped_directories": [], "issues": [],
        },
        "source-registry": {
            "schema_version": "1.0", "dataset_id": U1,
            "registry_revision": 1, "updated_at": STAMP,
            "sources": [{
                "source_id": U2, "current_relative_path": "a.txt",
                "path_history": ["a.txt"], "current_content_hash": H1,
                "revision": 1, "presence": "present",
            }],
        },
        "workspace-run": {
            "schema_version": "1.0", "run_id": U2,
            "phase": "complete", "status": "complete",
            "started_at": STAMP, "updated_at": STAMP,
            "input_root_fingerprint": H1, "workspace_root_fingerprint": H1,
            "artifacts": [{
                "kind": "registry", "relative_path": "registry/sources.json",
                "content_hash": H1,
            }],
        },
        "workspace-issues": {
            "schema_version": "1.0", "run_id": U2, "issues": [],
        },
        "checkpoint-manifest": {
            "schema_version": "1.0", "checkpoint_id": U2,
            "created_at": STAMP, "reason": "registry_update",
            "files": [{
                "relative_path": "project.json", "content_hash": H1, "size_bytes": 1,
            }],
        },
    }


def test_valid_samples_pass_runtime_and_json_schema() -> None:
    for kind, value in valid_documents().items():
        assert validate_workspace_document(kind, value) == []
        assert list(jsonschema.Draft202012Validator(load_schema(kind)).iter_errors(value)) == []


def test_runtime_and_json_schema_reject_missing_required_and_unknown_field() -> None:
    for kind, original in valid_documents().items():
        missing = deepcopy(original)
        missing.pop("schema_version")
        assert validate_workspace_document(kind, missing)
        assert list(jsonschema.Draft202012Validator(load_schema(kind)).iter_errors(missing))
        unknown = deepcopy(original)
        unknown["unexpected"] = True
        assert validate_workspace_document(kind, unknown)
        assert list(jsonschema.Draft202012Validator(load_schema(kind)).iter_errors(unknown))


def test_discovery_null_hash_and_size_are_legal_only_for_read_failure() -> None:
    failed = valid_documents()["discovery-inventory"]
    failed["entries"][0].update(
        {"support_status": "read_failed", "content_hash": None, "size_bytes": None}
    )
    assert validate_workspace_document("discovery-inventory", failed) == []
    assert list(jsonschema.Draft202012Validator(load_schema("discovery-inventory")).iter_errors(failed)) == []
    invalid = deepcopy(failed)
    invalid["entries"][0]["support_status"] = "builtin_text"
    assert validate_workspace_document("discovery-inventory", invalid)
    assert list(jsonschema.Draft202012Validator(load_schema("discovery-inventory")).iter_errors(invalid))


def test_runtime_has_no_jsonschema_dependency() -> None:
    source = (SKILL_ROOT / "scripts" / "qbcore" / "workspace_contracts.py").read_text(encoding="utf-8")
    assert "import jsonschema" not in source
    assert "from jsonschema" not in source
```

- [ ] **Step 6: Run contract tests and regression**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_workspace_contracts.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: all Milestone 1 workspace contract tests pass and the previous 34 tests remain green. Record the actual total rather than predicting a fixed count after parameterization.

**Stop condition:** If a persistent artifact cannot be represented without changing a Milestone 0 schema, stop and report the conflicting field; do not modify the old schema.

---

### Task 4: Enforce canonical root relationships and the single write boundary

**Files:**

- Create: `skills/curate-question-bank/scripts/qbcore/paths.py`
- Create: `tests/test_m1_paths.py`

- [ ] **Step 1: Write failing root-policy tests**

Create `tests/test_m1_paths.py` with these cases:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from qbcore.paths import PathPolicyError, RootPolicy, is_reparse_directory, validate_roots


def test_roots_must_be_explicit() -> None:
    with pytest.raises(PathPolicyError, match="input_root is required"):
        validate_roots(None, "workspace")
    with pytest.raises(PathPolicyError, match="workspace_root is required"):
        validate_roots("input", None)


def test_equal_roots_are_rejected_before_workspace_creation(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    with pytest.raises(PathPolicyError, match="must be different"):
        validate_roots(input_root, input_root)
    assert list(input_root.iterdir()) == []


def test_input_inside_workspace_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    input_root = workspace / "input"
    input_root.mkdir(parents=True)
    with pytest.raises(PathPolicyError, match="input_root cannot be inside workspace_root"):
        validate_roots(input_root, workspace)


def test_workspace_inside_input_is_allowed(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, input_root / ".curator-workspace")
    assert policy.workspace_is_inside_input is True
    assert policy.workspace_root == (input_root / ".curator-workspace").resolve()
```

- [ ] **Step 2: Run RED**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_paths.py -q
```

Expected: collection FAIL with `ModuleNotFoundError: qbcore.paths`.

- [ ] **Step 3: Implement canonical root validation**

Create `paths.py` with these public definitions:

```python
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path


class PathPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class RootPolicy:
    input_root: Path
    workspace_root: Path
    workspace_is_inside_input: bool

    @property
    def input_fingerprint(self) -> str:
        return _fingerprint(self.input_root)

    @property
    def workspace_fingerprint(self) -> str:
        return _fingerprint(self.workspace_root)

    def contains_input(self, path: Path) -> bool:
        return _is_within(path.resolve(strict=False), self.input_root)

    def contains_workspace(self, path: Path) -> bool:
        return _is_within(path.resolve(strict=False), self.workspace_root)

    def assert_write_target(self, path: Path) -> Path:
        resolved = path.resolve(strict=False)
        if not _is_within(resolved, self.workspace_root):
            raise PathPolicyError("write target escapes workspace_root")
        _reject_reparse_ancestors(self.workspace_root, resolved.parent)
        return resolved


def _fingerprint(path: Path) -> str:
    normalized = os.path.normcase(str(path.resolve(strict=False)))
    return sha256(normalized.encode("utf-8")).hexdigest()


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def is_reparse_directory(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def _reject_reparse_ancestors(root: Path, parent: Path) -> None:
    current = parent
    checked: list[Path] = []
    while _is_within(current, root) and current != root:
        checked.append(current)
        current = current.parent
    for candidate in reversed(checked):
        if candidate.exists() and is_reparse_directory(candidate):
            raise PathPolicyError("write target crosses a reparse point")


def validate_roots(input_root: str | Path | None, workspace_root: str | Path | None) -> RootPolicy:
    if input_root is None or str(input_root).strip() == "":
        raise PathPolicyError("input_root is required")
    if workspace_root is None or str(workspace_root).strip() == "":
        raise PathPolicyError("workspace_root is required")
    try:
        input_path = Path(input_root).expanduser().resolve(strict=True)
        workspace_path = Path(workspace_root).expanduser().resolve(strict=False)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise PathPolicyError("root paths cannot be safely resolved") from exc
    if not input_path.is_dir():
        raise PathPolicyError("input_root must be an existing directory")
    if input_path == workspace_path:
        raise PathPolicyError("input_root and workspace_root must be different")
    if _is_within(input_path, workspace_path):
        raise PathPolicyError("input_root cannot be inside workspace_root")
    return RootPolicy(
        input_root=input_path,
        workspace_root=workspace_path,
        workspace_is_inside_input=_is_within(workspace_path, input_path),
    )
```

- [ ] **Step 4: Add write-target and link-escape tests**

Append:

```python
def test_write_target_outside_workspace_is_rejected(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    with pytest.raises(PathPolicyError, match="escapes workspace_root"):
        policy.assert_write_target(tmp_path / "outside.json")


def test_path_fingerprints_do_not_expose_absolute_paths(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    assert len(policy.input_fingerprint) == 64
    assert str(tmp_path) not in policy.input_fingerprint


def test_reparse_helper_treats_directory_symlink_as_reparse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        original = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda self: True if self == link else original(self),
        )
    assert is_reparse_directory(link) is True
```

Import `is_reparse_directory` from `qbcore.paths`. This test uses a real directory symlink when permitted and an explicit pure fallback when Windows denies link creation; it never requires administrator privileges.

- [ ] **Step 5: Run GREEN and regression**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_paths.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: all path tests and the full suite pass.

**Stop condition:** If Windows path canonicalization yields an unverified containment result, reject that path relation; do not fall back to string-prefix comparison.

---

### Task 5: Produce an honest, deterministic capability matrix

**Files:**

- Create: `skills/curate-question-bank/scripts/qbcore/capabilities.py`
- Create: `tests/test_m1_capabilities.py`

- [ ] **Step 1: Write failing capability tests**

Create `tests/test_m1_capabilities.py`:

```python
from pathlib import Path

from m1_helpers import fixed_now
from qbcore.capabilities import build_capability_matrix
from qbcore.paths import validate_roots


def test_capability_matrix_is_honest_and_network_is_never_attempted(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    matrix = build_capability_matrix(policy, now=fixed_now, skill_version="0.1.0")
    statuses = {item["id"]: item["status"] for item in matrix["capabilities"]}
    assert statuses == {
        "directory_discovery": "available",
        "sha256": "available",
        "text_txt_utf8_bom": "available",
        "text_markdown_basic": "available",
        "pdf": "unsupported",
        "docx": "unsupported",
        "xlsx": "unsupported",
        "pptx": "unsupported",
        "image_ocr": "unsupported",
        "zip": "unsupported",
    }
    assert matrix["network"] == {"status": "not_authorized", "attempted": False}
    assert str(tmp_path) not in str(matrix)


def test_capability_order_is_stable(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    first = build_capability_matrix(policy, now=fixed_now, skill_version="0.1.0")
    second = build_capability_matrix(policy, now=fixed_now, skill_version="0.1.0")
    assert first == second
```

- [ ] **Step 2: Run RED**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_capabilities.py -q
```

Expected: collection FAIL because `qbcore.capabilities` does not exist.

- [ ] **Step 3: Implement capability snapshot construction**

Create `capabilities.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import platform

from qbcore.paths import RootPolicy


CAPABILITIES = (
    ("directory_discovery", "available", "stdlib recursive discovery"),
    ("sha256", "available", "stdlib hashlib SHA-256"),
    ("text_txt_utf8_bom", "available", "built-in text milestone scope"),
    ("text_markdown_basic", "available", "built-in text milestone scope"),
    ("pdf", "unsupported", "no PDF adapter in Milestone 1"),
    ("docx", "unsupported", "no DOCX adapter in Milestone 1"),
    ("xlsx", "unsupported", "no XLSX adapter in Milestone 1"),
    ("pptx", "unsupported", "no PPTX adapter in Milestone 1"),
    ("image_ocr", "unsupported", "no OCR adapter in Milestone 1"),
    ("zip", "unsupported", "no ZIP adapter in Milestone 1"),
)


def _utc_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_capability_matrix(
    policy: RootPolicy,
    *,
    now: Callable[[], datetime],
    skill_version: str,
) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": _utc_z(now()),
        "skill_version": skill_version,
        "python_version": platform.python_version(),
        "input_root_fingerprint": policy.input_fingerprint,
        "workspace_root_fingerprint": policy.workspace_fingerprint,
        "network": {"status": "not_authorized", "attempted": False},
        "capabilities": [
            {"id": identifier, "status": status, "detail": detail}
            for identifier, status, detail in CAPABILITIES
        ],
    }
```

- [ ] **Step 4: Validate the document without runtime jsonschema**

Append:

```python
from qbcore.workspace_contracts import validate_workspace_document


def test_capability_matrix_passes_the_stdlib_runtime_contract(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    matrix = build_capability_matrix(policy, now=fixed_now, skill_version="0.1.0")
    assert validate_workspace_document("capability-matrix", matrix) == []
```

Do not add environment probing that imports optional parser libraries; Milestone 1 reports only built-in capabilities and explicit unsupported states.

- [ ] **Step 5: Run GREEN and regression**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_capabilities.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: capability tests and the full suite pass without network access or installation.

**Stop condition:** If a test needs a third-party runtime package, the design has been violated; remove that probe rather than installing the package.

---

### Task 6: Implement deterministic read-only discovery

**Files:**

- Create: `skills/curate-question-bank/scripts/qbcore/discovery.py`
- Create: `tests/test_m1_discovery.py`

- [ ] **Step 1: Write failing golden discovery and immutability tests**

Create `tests/test_m1_discovery.py`:

```python
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil
import socket

from conftest import REPOSITORY_ROOT
from m1_helpers import fixed_now, tree_snapshot
from qbcore.discovery import discover_files
from qbcore.paths import validate_roots


FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "m1-discovery" / "input"


def test_discovery_is_deterministic_and_does_not_modify_input(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    workspace = input_root / ".workspace"
    workspace.mkdir()
    (workspace / "must-not-scan.txt").write_text("workspace output\n", encoding="utf-8")
    before = tree_snapshot(input_root)
    policy = validate_roots(input_root, workspace)
    result = discover_files(policy, now=fixed_now)
    after = tree_snapshot(input_root)
    assert before == after
    assert [entry["relative_path"] for entry in result["entries"]] == [
        "alpha.txt", "beta.md", "nested/gamma.TXT", "unsupported.pdf"
    ]
    assert all(not item["relative_path"].startswith(".workspace/") for item in result["entries"])


def test_empty_input_returns_empty_inventory(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    result = discover_files(policy, now=fixed_now)
    assert result["entries"] == []
    assert result["issues"] == []
```

- [ ] **Step 2: Run RED**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_discovery.py -q
```

Expected: collection FAIL because `qbcore.discovery` does not exist.

- [ ] **Step 3: Implement full discovery without parsing**

Create `discovery.py` with this API and algorithm:

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
import os
from pathlib import Path

from qbcore.capabilities import _utc_z
from qbcore.paths import RootPolicy, is_reparse_directory


BUILTIN_TEXT_SUFFIXES = {".txt", ".md"}


class DiscoveryError(RuntimeError):
    pass


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def discover_files(policy: RootPolicy, *, now: Callable[[], datetime]) -> dict:
    entries: list[dict] = []
    skipped: list[dict] = []
    issues: list[dict] = []
    pending = [policy.input_root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                children = sorted(iterator, key=lambda item: (item.name.casefold(), item.name))
        except OSError as exc:
            if directory == policy.input_root:
                raise DiscoveryError("input_root cannot be enumerated") from exc
            relative_directory = directory.relative_to(policy.input_root).as_posix()
            issues.append({
                "code": "QB-SOURCE-READ-FAILED",
                "relative_path": relative_directory,
                "summary": "authorized source directory could not be read",
            })
            continue
        for child in children:
            path = Path(child.path)
            resolved = path.resolve(strict=False)
            if policy.contains_workspace(resolved):
                continue
            relative = path.relative_to(policy.input_root).as_posix()
            if child.is_dir(follow_symlinks=False):
                if is_reparse_directory(path):
                    skipped.append({"relative_path": relative, "reason": "reparse_point"})
                else:
                    pending.append(path)
                continue
            if child.is_symlink() or is_reparse_directory(path) or not child.is_file(follow_symlinks=False):
                skipped.append({"relative_path": relative, "reason": "reparse_point"})
                continue
            try:
                content_hash = _hash_file(path)
                size_bytes = path.stat().st_size
            except OSError:
                entries.append({
                    "relative_path": relative,
                    "size_bytes": None,
                    "content_hash": None,
                    "support_status": "read_failed",
                })
                issues.append({
                    "code": "QB-SOURCE-READ-FAILED",
                    "relative_path": relative,
                    "summary": "authorized source could not be read",
                })
                continue
            supported = path.suffix.casefold() in BUILTIN_TEXT_SUFFIXES
            entries.append({
                "relative_path": relative,
                "size_bytes": size_bytes,
                "content_hash": content_hash,
                "support_status": "builtin_text" if supported else "unsupported",
            })
            if not supported:
                issues.append({
                    "code": "QB-SOURCE-UNSUPPORTED",
                    "relative_path": relative,
                    "summary": "source format is not supported in Milestone 1",
                })
    entries.sort(key=lambda item: (item["relative_path"].casefold(), item["relative_path"]))
    skipped.sort(key=lambda item: (item["relative_path"].casefold(), item["relative_path"]))
    issues.sort(key=lambda item: (item["relative_path"].casefold(), item["code"]))
    return {
        "schema_version": "1.0",
        "generated_at": _utc_z(now()),
        "input_root_fingerprint": policy.input_fingerprint,
        "workspace_root_fingerprint": policy.workspace_fingerprint,
        "entries": entries,
        "skipped_directories": skipped,
        "issues": issues,
    }
```

This error path never records an absolute path or source content.

- [ ] **Step 4: Add unsupported, hash, and enumeration-order tests**

Append:

```python
entry_by_path = {entry["relative_path"]: entry for entry in result["entries"]}
assert entry_by_path["alpha.txt"]["support_status"] == "builtin_text"
assert entry_by_path["nested/gamma.TXT"]["support_status"] == "builtin_text"
assert entry_by_path["unsupported.pdf"]["support_status"] == "unsupported"
assert entry_by_path["alpha.txt"]["content_hash"] == sha256(
    b"Synthetic alpha source.\n"
).hexdigest()
assert {issue["code"] for issue in result["issues"]} == {"QB-SOURCE-UNSUPPORTED"}


def test_reversed_filesystem_enumeration_produces_the_same_inventory(
    tmp_path: Path, monkeypatch
) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    policy = validate_roots(input_root, tmp_path / "workspace")
    normal = discover_files(policy, now=fixed_now)
    original = __import__("os").scandir

    class ReversedScandir:
        def __init__(self, path: Path) -> None:
            with original(path) as iterator:
                self.items = list(iterator)[::-1]

        def __enter__(self):
            return iter(self.items)

        def __exit__(self, *_args) -> None:
            return None

    monkeypatch.setattr("qbcore.discovery.os.scandir", ReversedScandir)
    reversed_result = discover_files(policy, now=fixed_now)
    assert reversed_result == normal


def test_unreadable_file_is_recorded_without_a_fake_hash(
    tmp_path: Path, monkeypatch
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "blocked.txt").write_text("synthetic\n", encoding="utf-8")
    policy = validate_roots(input_root, tmp_path / "workspace")
    monkeypatch.setattr(
        "qbcore.discovery._hash_file",
        lambda path: (_ for _ in ()).throw(PermissionError("injected")),
    )
    result = discover_files(policy, now=fixed_now)
    assert result["entries"] == [{
        "relative_path": "blocked.txt", "size_bytes": None,
        "content_hash": None, "support_status": "read_failed",
    }]
    assert [issue["code"] for issue in result["issues"]] == ["QB-SOURCE-READ-FAILED"]
```

- [ ] **Step 5: Add workspace-link exclusion tests**

Append:

```python
def test_workspace_and_alias_to_workspace_are_not_discovered(
    tmp_path: Path, monkeypatch
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = input_root / ".workspace"
    workspace.mkdir()
    (workspace / "output.txt").write_text("must not scan\n", encoding="utf-8")
    alias = input_root / "workspace-alias"
    try:
        alias.symlink_to(workspace, target_is_directory=True)
    except OSError:
        alias.mkdir()
        (alias / "also-output.txt").write_text("must not scan\n", encoding="utf-8")
        original = __import__("qbcore.discovery", fromlist=["is_reparse_directory"]).is_reparse_directory
        monkeypatch.setattr(
            "qbcore.discovery.is_reparse_directory",
            lambda path: True if path == alias else original(path),
        )
    policy = validate_roots(input_root, workspace)
    result = discover_files(policy, now=fixed_now)
    assert result["entries"] == []
```

The real-link branch is excluded through canonical workspace identity. The pure fallback proves a reparse-like directory is pruned when Windows denies link creation.

- [ ] **Step 6: Validate discovery output and run regression**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_discovery.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: all discovery tests pass, `validate_workspace_document("discovery-inventory", result)` returns no issues, and the full suite is green.

**Stop condition:** If a platform cannot prove a directory entry is safely inside the authorized root, record it as skipped or fail closed; never follow it speculatively.

---

### Task 7: Reconcile file-level SourceIdentity without incremental skipping

**Files:**

- Create: `skills/curate-question-bank/scripts/qbcore/registry.py`
- Create: `tests/test_m1_source_registry.py`

- [ ] **Step 1: Write failing first-scan and unchanged-source tests**

Create `tests/test_m1_source_registry.py`:

```python
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from m1_helpers import UUIDSequence, fixed_now
from qbcore.registry import reconcile_registry


def inventory(*entries: tuple[str, str]) -> dict:
    return {
        "entries": [
            {
                "relative_path": path,
                "size_bytes": 1,
                "content_hash": content_hash,
                "support_status": "builtin_text",
            }
            for path, content_hash in entries
        ]
    }


def empty_registry() -> dict:
    return {
        "schema_version": "1.0",
        "dataset_id": "00000000-0000-4000-8000-000000000100",
        "registry_revision": 0,
        "updated_at": "2026-08-12T00:00:00Z",
        "sources": [],
    }


def test_first_scan_assigns_distinct_ids_at_revision_one() -> None:
    registry, issues = reconcile_registry(
        empty_registry(), inventory(("a.txt", "a" * 64), ("b.txt", "a" * 64)),
        uuid_factory=UUIDSequence(1), now=fixed_now,
    )
    assert issues == []
    assert [source["revision"] for source in registry["sources"]] == [1, 1]
    assert len({source["source_id"] for source in registry["sources"]}) == 2


def test_same_path_same_hash_keeps_identity_and_revision() -> None:
    first, _ = reconcile_registry(
        empty_registry(), inventory(("a.txt", "a" * 64)),
        uuid_factory=UUIDSequence(1), now=fixed_now,
    )
    second, issues = reconcile_registry(
        first, inventory(("a.txt", "a" * 64)),
        uuid_factory=UUIDSequence(50), now=fixed_now,
    )
    assert issues == []
    assert second["sources"][0]["source_id"] == first["sources"][0]["source_id"]
    assert second["sources"][0]["revision"] == 1
```

- [ ] **Step 2: Run RED**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_source_registry.py -q
```

Expected: collection FAIL because `qbcore.registry` does not exist.

- [ ] **Step 3: Implement deterministic one-to-one reconciliation**

Create `registry.py` with this complete implementation:

```python
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from qbcore.capabilities import _utc_z


def reconcile_registry(
    previous: dict,
    discovery: dict,
    *,
    uuid_factory: Callable[[], UUID],
    now: Callable[[], datetime],
) -> tuple[dict, list[dict]]:
    """Return new file identities without mutating either input."""
    old_sources = deepcopy(previous["sources"])
    new_entries = [
        deepcopy(entry)
        for entry in discovery["entries"]
        if entry["support_status"] != "read_failed"
    ]
    old_paths = [source["current_relative_path"] for source in old_sources]
    new_paths = [entry["relative_path"] for entry in new_entries]
    if len(set(old_paths)) != len(old_paths):
        raise ValueError("source registry contains duplicate current paths")
    if len(set(new_paths)) != len(new_paths):
        raise ValueError("discovery inventory contains duplicate paths")

    old_unmatched = set(range(len(old_sources)))
    new_unmatched = set(range(len(new_entries)))
    reconciled: dict[int, dict] = {}
    issues: list[dict] = []
    old_by_path = {source["current_relative_path"]: index for index, source in enumerate(old_sources)}

    for new_index, entry in enumerate(new_entries):
        old_index = old_by_path.get(entry["relative_path"])
        if old_index is None:
            continue
        source = deepcopy(old_sources[old_index])
        if source["current_content_hash"] != entry["content_hash"]:
            source["current_content_hash"] = entry["content_hash"]
            source["revision"] += 1
        source["presence"] = "present"
        reconciled[old_index] = source
        old_unmatched.remove(old_index)
        new_unmatched.remove(new_index)

    old_by_hash: dict[str, list[int]] = defaultdict(list)
    new_by_hash: dict[str, list[int]] = defaultdict(list)
    for old_index in sorted(old_unmatched):
        old_by_hash[old_sources[old_index]["current_content_hash"]].append(old_index)
    for new_index in sorted(new_unmatched):
        new_by_hash[new_entries[new_index]["content_hash"]].append(new_index)

    for content_hash in sorted(set(old_by_hash) & set(new_by_hash)):
        old_group = old_by_hash[content_hash]
        new_group = new_by_hash[content_hash]
        if len(old_group) == 1 and len(new_group) == 1:
            old_index, new_index = old_group[0], new_group[0]
            source = deepcopy(old_sources[old_index])
            new_path = new_entries[new_index]["relative_path"]
            source["current_relative_path"] = new_path
            if source["path_history"][-1] != new_path:
                source["path_history"].append(new_path)
            source["presence"] = "present"
            reconciled[old_index] = source
            old_unmatched.remove(old_index)
            new_unmatched.remove(new_index)
            continue
        issues.append({
            "code": "QB-IDENTITY-AMBIGUOUS",
            "summary": "content hash does not establish a unique one-to-one rename",
            "relative_paths": sorted(
                [old_sources[index]["current_relative_path"] for index in old_group]
                + [new_entries[index]["relative_path"] for index in new_group],
                key=lambda value: (value.casefold(), value),
            ),
            "source_ids": sorted(old_sources[index]["source_id"] for index in old_group),
        })

    result_sources = list(reconciled.values())
    for old_index in sorted(old_unmatched):
        source = deepcopy(old_sources[old_index])
        source["presence"] = "missing"
        result_sources.append(source)
    for new_index in sorted(new_unmatched):
        entry = new_entries[new_index]
        result_sources.append({
            "source_id": str(uuid_factory()),
            "current_relative_path": entry["relative_path"],
            "path_history": [entry["relative_path"]],
            "current_content_hash": entry["content_hash"],
            "revision": 1,
            "presence": "present",
        })

    result_sources.sort(
        key=lambda source: (source["current_relative_path"].casefold(), source["source_id"])
    )
    previous_sorted = sorted(
        deepcopy(previous["sources"]),
        key=lambda source: (source["current_relative_path"].casefold(), source["source_id"]),
    )
    changed = result_sources != previous_sorted
    return ({
        "schema_version": "1.0",
        "dataset_id": previous["dataset_id"],
        "registry_revision": previous["registry_revision"] + (1 if changed else 0),
        "updated_at": _utc_z(now()) if changed else previous["updated_at"],
        "sources": result_sources,
    }, issues)
```

This is a complete full-scan reconciliation. It does not skip discovery or hashing based on the old registry.

- [ ] **Step 4: Add changed, rename, ambiguity, duplicate, and dual-change tests**

Append:

```python
from qbcore.workspace_contracts import validate_workspace_document


def first_registry(*entries: tuple[str, str]) -> dict:
    value, issues = reconcile_registry(
        empty_registry(), inventory(*entries),
        uuid_factory=UUIDSequence(1), now=fixed_now,
    )
    assert issues == []
    return value


def test_same_path_changed_hash_increments_source_revision() -> None:
    old = first_registry(("a.txt", "a" * 64))
    source_id = old["sources"][0]["source_id"]
    new, issues = reconcile_registry(
        old, inventory(("a.txt", "b" * 64)),
        uuid_factory=UUIDSequence(50), now=fixed_now,
    )
    assert issues == []
    assert new["sources"][0]["source_id"] == source_id
    assert new["sources"][0]["revision"] == 2


def test_unique_content_hash_rename_preserves_identity_and_revision() -> None:
    old = first_registry(("old.txt", "a" * 64))
    new, issues = reconcile_registry(
        old, inventory(("new.txt", "a" * 64)),
        uuid_factory=UUIDSequence(50), now=fixed_now,
    )
    assert issues == []
    assert new["sources"][0]["source_id"] == old["sources"][0]["source_id"]
    assert new["sources"][0]["revision"] == 1
    assert new["sources"][0]["path_history"] == ["old.txt", "new.txt"]


def test_one_old_to_two_new_same_hash_is_ambiguous_and_does_not_migrate() -> None:
    old = first_registry(("old.txt", "a" * 64))
    old_id = old["sources"][0]["source_id"]
    new, issues = reconcile_registry(
        old, inventory(("one.txt", "a" * 64), ("two.txt", "a" * 64)),
        uuid_factory=UUIDSequence(50), now=fixed_now,
    )
    assert [issue["code"] for issue in issues] == ["QB-IDENTITY-AMBIGUOUS"]
    by_id = {source["source_id"]: source for source in new["sources"]}
    assert by_id[old_id]["presence"] == "missing"
    assert all(by_id[source_id]["revision"] == 1 for source_id in by_id if source_id != old_id)


def test_two_old_to_one_new_same_hash_is_ambiguous_and_does_not_migrate() -> None:
    old = first_registry(("a.txt", "a" * 64), ("b.txt", "a" * 64))
    old_ids = {source["source_id"] for source in old["sources"]}
    new, issues = reconcile_registry(
        old, inventory(("c.txt", "a" * 64)),
        uuid_factory=UUIDSequence(50), now=fixed_now,
    )
    assert [issue["code"] for issue in issues] == ["QB-IDENTITY-AMBIGUOUS"]
    assert all(
        source["presence"] == "missing"
        for source in new["sources"] if source["source_id"] in old_ids
    )
    assert next(source for source in new["sources"] if source["current_relative_path"] == "c.txt")["source_id"] not in old_ids


def test_path_and_content_change_create_new_identity_and_archive_old_as_missing() -> None:
    old = first_registry(("old.txt", "a" * 64))
    old_id = old["sources"][0]["source_id"]
    old_copy = deepcopy(old)
    discovery = inventory(("new.txt", "b" * 64))
    discovery_copy = deepcopy(discovery)
    new, issues = reconcile_registry(
        old, discovery, uuid_factory=UUIDSequence(50), now=fixed_now,
    )
    assert issues == []
    assert old == old_copy and discovery == discovery_copy
    assert next(source for source in new["sources"] if source["source_id"] == old_id)["presence"] == "missing"
    assert next(source for source in new["sources"] if source["current_relative_path"] == "new.txt")["source_id"] != old_id
    assert validate_workspace_document("source-registry", new) == []
```

The first-scan test already proves concurrent same-hash files receive distinct IDs. Add `assert validate_workspace_document("source-registry", registry) == []` to every result-producing test.

- [ ] **Step 5: Run GREEN and regression**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_source_registry.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: all SourceIdentity cases and the full suite pass.

**Stop condition:** If a test can pass only by treating hash or path as the persistent identity key, stop and fix the algorithm; do not weaken the Milestone 0 identity contract.

---

### Task 8: Publish workspace JSON atomically inside the write boundary

**Files:**

- Create: `skills/curate-question-bank/scripts/qbcore/workspace.py`
- Create: `tests/test_m1_workspace.py`

- [ ] **Step 1: Write failing layout and atomic-write tests**

Create `tests/test_m1_workspace.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from qbcore.paths import PathPolicyError, RootPolicy, validate_roots
from qbcore.workspace import Workspace, WorkspaceWriteError


def test_initialize_creates_only_the_frozen_workspace_layout(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    policy = validate_roots(input_root, tmp_path / "workspace")
    workspace = Workspace.initialize(policy)
    assert sorted(path.name for path in policy.workspace_root.iterdir()) == [
        "checkpoints", "logs", "outputs", "registry", "runs"
    ]
    assert workspace.root == policy.workspace_root


def test_write_json_rejects_targets_outside_workspace(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    with pytest.raises(PathPolicyError, match="escapes workspace_root"):
        workspace.write_json_atomic(tmp_path / "outside.json", {"value": 1})


def test_failed_replace_preserves_previous_complete_json(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    target = workspace.root / "registry" / "sources.json"
    workspace.write_json_atomic(target, {"version": 1})
    monkeypatch.setattr("qbcore.workspace.os.replace", lambda *_: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(WorkspaceWriteError, match="atomic JSON publication failed"):
        workspace.write_json_atomic(target, {"version": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"version": 1}
```

- [ ] **Step 2: Run RED**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_workspace.py -q
```

Expected: collection FAIL because `qbcore.workspace` does not exist.

- [ ] **Step 3: Implement layout and atomic JSON publication**

Create `workspace.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from uuid import uuid4

from qbcore.paths import RootPolicy
from qbcore.workspace_contracts import UUID_PATTERN, validate_workspace_document


class WorkspaceWriteError(RuntimeError):
    pass


@dataclass(frozen=True)
class Workspace:
    policy: RootPolicy

    @property
    def root(self) -> Path:
        return self.policy.workspace_root

    @classmethod
    def initialize(cls, policy: RootPolicy) -> "Workspace":
        policy.assert_write_target(policy.workspace_root)
        policy.workspace_root.mkdir(parents=True, exist_ok=True)
        workspace = cls(policy)
        for relative in ("registry", "runs", "checkpoints", "logs", "outputs"):
            target = policy.assert_write_target(policy.workspace_root / relative)
            target.mkdir(exist_ok=True)
        return workspace

    def write_json_atomic(self, target: Path, value: object) -> str:
        target = self.policy.assert_write_target(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.policy.assert_write_target(
            target.parent / f".{target.name}.{uuid4()}.tmp"
        )
        payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            json.loads(temporary.read_text(encoding="utf-8"))
            os.replace(temporary, target)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise WorkspaceWriteError("atomic JSON publication failed") from exc
        return target.relative_to(self.root).as_posix()
```

`Workspace.initialize()` must validate all targets before creating them. If the root itself is an existing reparse directory, fail before adding subdirectories.

- [ ] **Step 4: Add project and run artifact writers**

Add these methods inside `Workspace`:

```python
    @staticmethod
    def _require_valid(kind: str, document: dict) -> None:
        issues = validate_workspace_document(kind, document)
        if issues:
            first = issues[0]
            raise WorkspaceWriteError(
                f"invalid {kind} document at {first.path}: {first.message}"
            )

    def write_project(self, document: dict) -> str:
        self._require_valid("workspace-project", document)
        return self.write_json_atomic(self.root / "project.json", document)

    def write_registry(self, document: dict) -> str:
        self._require_valid("source-registry", document)
        return self.write_json_atomic(self.root / "registry" / "sources.json", document)

    def write_run_artifact(self, run_id: str, name: str, document: dict) -> str:
        kind_by_name = {
            "preflight.json": "capability-matrix",
            "discovery.json": "discovery-inventory",
            "workspace-run.json": "workspace-run",
            "issues.json": "workspace-issues",
        }
        if UUID_PATTERN.fullmatch(run_id) is None:
            raise WorkspaceWriteError("run_id must be a lowercase UUID")
        try:
            kind = kind_by_name[name]
        except KeyError as exc:
            raise WorkspaceWriteError("run artifact name is not allowed") from exc
        if Path(name).name != name:
            raise WorkspaceWriteError("run artifact name cannot contain a path")
        if kind in {"workspace-run", "workspace-issues"} and document.get("run_id") != run_id:
            raise WorkspaceWriteError("run artifact run_id does not match its directory")
        self._require_valid(kind, document)
        return self.write_json_atomic(self.root / "runs" / run_id / name, document)
```

These are the only public persistent artifact writers in Milestone 1. Checkpoint code validates its manifest explicitly before using `write_json_atomic()` inside checkpoint staging.

- [ ] **Step 5: Add JSON determinism and validation-before-write tests**

Append:

```python
def test_atomic_json_bytes_are_independent_of_mapping_insertion_order(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    target = workspace.root / "runs" / "freeform-test.json"
    workspace.write_json_atomic(target, {"z": 1, "a": 2})
    first = target.read_bytes()
    workspace.write_json_atomic(target, {"a": 2, "z": 1})
    assert target.read_bytes() == first


def test_invalid_project_is_rejected_before_target_creation(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    target = workspace.root / "project.json"
    with pytest.raises(WorkspaceWriteError, match="invalid workspace-project"):
        workspace.write_project({"schema_version": "1.0"})
    assert not target.exists()


def test_injected_replace_failure_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    target = workspace.root / "registry" / "freeform.json"
    monkeypatch.setattr(
        "qbcore.workspace.os.replace",
        lambda *_: (_ for _ in ()).throw(OSError("injected")),
    )
    with pytest.raises(WorkspaceWriteError):
        workspace.write_json_atomic(target, {"value": 1})
    assert not target.exists()
    assert list(target.parent.glob("*.tmp")) == []
    assert all(
        path.resolve().is_relative_to(workspace.root.resolve())
        for path in workspace.root.rglob("*")
    )
```

- [ ] **Step 6: Run GREEN and regression**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_workspace.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: workspace tests and the full suite pass.

**Stop condition:** If atomic replacement semantics cannot be verified on the active filesystem, report that filesystem and stop before claiming crash-safe publication.

---

### Task 9: Create, validate, and explicitly restore checkpoints

**Files:**

- Create: `skills/curate-question-bank/scripts/qbcore/recovery.py`
- Create: `tests/test_m1_recovery.py`

- [ ] **Step 1: Write failing checkpoint tests**

Create `tests/test_m1_recovery.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from m1_helpers import UUIDSequence, fixed_now
from qbcore.paths import validate_roots
from qbcore.recovery import (
    CheckpointError,
    create_checkpoint,
    restore_latest_checkpoint,
    validate_checkpoint,
)
from qbcore.workspace import Workspace


def test_checkpoint_contains_only_complete_control_state(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "source.txt").write_text("do not copy\n", encoding="utf-8")
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    project = {
        "schema_version": "1.0", "project_format_version": "1.0",
        "dataset_id": "00000000-0000-4000-8000-000000000100",
        "created_at": "2026-08-13T00:00:00Z",
    }
    registry = {
        "schema_version": "1.0", "dataset_id": project["dataset_id"],
        "registry_revision": 0, "updated_at": "2026-08-13T00:00:00Z",
        "sources": [],
    }
    workspace.write_project(project)
    workspace.write_registry(registry)
    checkpoint = create_checkpoint(
        workspace, reason="registry_update", uuid_factory=UUIDSequence(1), now=fixed_now
    )
    files = {item["relative_path"] for item in checkpoint["files"]}
    assert files == {"project.json", "registry/sources.json"}
    assert not any(path.name == "source.txt" for path in workspace.root.rglob("*"))
```

- [ ] **Step 2: Run RED**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_recovery.py -q
```

Expected: collection FAIL because `qbcore.recovery` does not exist.

- [ ] **Step 3: Implement checkpoint creation and validation**

Create `recovery.py` with this complete implementation:

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from uuid import UUID

from qbcore.capabilities import _utc_z
from qbcore.workspace import Workspace
from qbcore.workspace_contracts import validate_workspace_document


class CheckpointError(RuntimeError):
    pass


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise CheckpointError("checkpoint contains an unsafe relative path")
    return path


def _read_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError("checkpoint JSON cannot be read") from exc
    if not isinstance(value, dict):
        raise CheckpointError("checkpoint JSON root must be an object")
    return value


def _latest_complete_run(workspace: Workspace) -> Path | None:
    candidates: list[tuple[str, str, Path]] = []
    for run_dir in workspace.root.joinpath("runs").iterdir():
        state_path = run_dir / "workspace-run.json"
        if not run_dir.is_dir() or not state_path.is_file():
            continue
        try:
            state = _read_object(state_path)
        except CheckpointError:
            continue
        if validate_workspace_document("workspace-run", state):
            continue
        if state["status"] == "complete":
            candidates.append((state["updated_at"], state["run_id"], run_dir))
    return max(candidates, default=("", "", None))[2]


def _control_files(workspace: Workspace) -> list[Path]:
    required = [workspace.root / "project.json", workspace.root / "registry" / "sources.json"]
    if not all(path.is_file() for path in required):
        raise CheckpointError("project and registry must exist before checkpointing")
    selected = list(required)
    latest_run = _latest_complete_run(workspace)
    if latest_run is not None:
        for name in ("preflight.json", "discovery.json", "issues.json", "workspace-run.json"):
            path = latest_run / name
            if path.is_file():
                selected.append(path)
    return selected


def _validate_checkpoint_dir(workspace: Workspace, checkpoint_dir: Path) -> dict:
    checkpoint_dir = workspace.policy.assert_write_target(checkpoint_dir)
    manifest_path = checkpoint_dir / "checkpoint-manifest.json"
    manifest = _read_object(manifest_path)
    issues = validate_workspace_document("checkpoint-manifest", manifest)
    if issues:
        raise CheckpointError("checkpoint manifest is invalid")
    expected = {item["relative_path"]: item for item in manifest["files"]}
    if len(expected) != len(manifest["files"]):
        raise CheckpointError("checkpoint manifest contains duplicate paths")
    actual = {
        path.relative_to(checkpoint_dir).as_posix()
        for path in checkpoint_dir.rglob("*")
        if path.is_file() and path.name != "checkpoint-manifest.json"
    }
    if actual != set(expected):
        raise CheckpointError("checkpoint file set does not match its manifest")
    for relative, item in expected.items():
        path = checkpoint_dir / _safe_relative(relative)
        if path.stat().st_size != item["size_bytes"] or _hash(path) != item["content_hash"]:
            raise CheckpointError("checkpoint file hash or size does not match")
    return manifest


def create_checkpoint(
    workspace: Workspace,
    *,
    reason: str,
    uuid_factory: Callable[[], UUID],
    now: Callable[[], datetime],
) -> dict:
    checkpoint_id = str(uuid_factory())
    staging = workspace.policy.assert_write_target(
        workspace.root / "checkpoints" / f"{checkpoint_id}.staging"
    )
    final = workspace.policy.assert_write_target(
        workspace.root / "checkpoints" / checkpoint_id
    )
    if staging.exists() or final.exists():
        raise CheckpointError("checkpoint identifier already exists")
    staging.mkdir(parents=False)
    files: list[dict] = []
    for source in _control_files(workspace):
        relative = source.relative_to(workspace.root)
        destination = workspace.policy.assert_write_target(staging / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        files.append({
            "relative_path": relative.as_posix(),
            "content_hash": _hash(destination),
            "size_bytes": destination.stat().st_size,
        })
    files.sort(key=lambda item: item["relative_path"])
    manifest = {
        "schema_version": "1.0",
        "checkpoint_id": checkpoint_id,
        "created_at": _utc_z(now()),
        "reason": reason,
        "files": files,
    }
    issues = validate_workspace_document("checkpoint-manifest", manifest)
    if issues:
        raise CheckpointError("generated checkpoint manifest is invalid")
    workspace.write_json_atomic(staging / "checkpoint-manifest.json", manifest)
    _validate_checkpoint_dir(workspace, staging)
    try:
        os.replace(staging, final)
    except OSError as exc:
        raise CheckpointError("checkpoint publication failed") from exc
    return _validate_checkpoint_dir(workspace, final)


def validate_checkpoint(workspace: Workspace, checkpoint_dir: Path) -> dict:
    resolved = checkpoint_dir.resolve(strict=True)
    if resolved.parent != (workspace.root / "checkpoints").resolve(strict=True):
        raise CheckpointError("checkpoint directory is outside the checkpoint root")
    if resolved.name.endswith(".staging"):
        raise CheckpointError("incomplete checkpoint staging is not restorable")
    return _validate_checkpoint_dir(workspace, resolved)
```

- [ ] **Step 4: Implement explicit latest-complete restore**

Append to `recovery.py`:

```python
def restore_latest_checkpoint(
    workspace: Workspace,
    *,
    run_id: str,
    now: Callable[[], datetime],
) -> list[str]:
    valid: list[tuple[str, str, Path, dict]] = []
    for candidate in (workspace.root / "checkpoints").iterdir():
        if not candidate.is_dir() or candidate.name.endswith(".staging"):
            continue
        try:
            manifest = validate_checkpoint(workspace, candidate)
        except CheckpointError:
            continue
        valid.append((manifest["created_at"], manifest["checkpoint_id"], candidate, manifest))
    if not valid:
        raise CheckpointError("no complete checkpoint is available")
    _, _, checkpoint_dir, manifest = max(valid)
    by_path = {item["relative_path"]: item for item in manifest["files"]}
    required = {"project.json", "registry/sources.json"}
    if not required <= set(by_path):
        raise CheckpointError("checkpoint lacks authoritative project or registry state")

    staging = workspace.policy.assert_write_target(
        workspace.root / "checkpoints" / f".restore-{run_id}.staging"
    )
    if staging.exists():
        raise CheckpointError("restore staging already exists")
    staging.mkdir()
    try:
        for relative in sorted(required):
            source = checkpoint_dir / _safe_relative(relative)
            destination = workspace.policy.assert_write_target(staging / _safe_relative(relative))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            expected = by_path[relative]
            if destination.stat().st_size != expected["size_bytes"] or _hash(destination) != expected["content_hash"]:
                raise CheckpointError("restore staging verification failed")
        project = _read_object(staging / "project.json")
        registry = _read_object(staging / "registry" / "sources.json")
        workspace.write_project(project)
        workspace.write_registry(registry)
        stamp = _utc_z(now())
        run = {
            "schema_version": "1.0", "run_id": run_id,
            "phase": "complete", "status": "complete",
            "started_at": stamp, "updated_at": stamp,
            "input_root_fingerprint": workspace.policy.input_fingerprint,
            "workspace_root_fingerprint": workspace.policy.workspace_fingerprint,
            "artifacts": [{
                "kind": "registry", "relative_path": "registry/sources.json",
                "content_hash": _hash(workspace.root / "registry" / "sources.json"),
            }],
        }
        workspace.write_run_artifact(run_id, "workspace-run.json", run)
    except (OSError, ValueError) as exc:
        raise CheckpointError("checkpoint restore failed") from exc
    try:
        shutil.rmtree(staging)
    except OSError:
        pass
    return sorted(required)
```

Do not overwrite historical run artifacts from the checkpoint. Restoration recovers authoritative project and registry state and creates a new audit run. A failed restore leaves its own `.staging` directory as recoverable diagnostic evidence; it never deletes existing authoritative files.

- [ ] **Step 5: Add corruption and failure-injection tests**

Append these helpers and tests:

```python
from m1_helpers import tree_snapshot


def prepared_workspace(tmp_path: Path) -> tuple[Path, Workspace, dict, dict]:
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "source.txt").write_text("synthetic input\n", encoding="utf-8")
    workspace = Workspace.initialize(validate_roots(input_root, tmp_path / "workspace"))
    project = {
        "schema_version": "1.0", "project_format_version": "1.0",
        "dataset_id": "00000000-0000-4000-8000-000000000100",
        "created_at": "2026-08-13T00:00:00Z",
    }
    registry = {
        "schema_version": "1.0", "dataset_id": project["dataset_id"],
        "registry_revision": 0, "updated_at": "2026-08-13T00:00:00Z",
        "sources": [],
    }
    workspace.write_project(project)
    workspace.write_registry(registry)
    return input_root, workspace, project, registry


def only_complete_checkpoint(workspace: Workspace) -> Path:
    return next(
        path for path in (workspace.root / "checkpoints").iterdir()
        if path.is_dir() and not path.name.endswith(".staging")
    )


def make_checkpoint(workspace: Workspace) -> Path:
    create_checkpoint(
        workspace, reason="registry_update",
        uuid_factory=UUIDSequence(1), now=fixed_now,
    )
    return only_complete_checkpoint(workspace)


def test_checkpoint_missing_listed_file_is_rejected(tmp_path: Path) -> None:
    _, workspace, _, _ = prepared_workspace(tmp_path)
    checkpoint = make_checkpoint(workspace)
    (checkpoint / "project.json").unlink()
    with pytest.raises(CheckpointError, match="file set"):
        validate_checkpoint(workspace, checkpoint)


def test_checkpoint_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    _, workspace, _, _ = prepared_workspace(tmp_path)
    checkpoint = make_checkpoint(workspace)
    (checkpoint / "project.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(CheckpointError, match="hash or size"):
        validate_checkpoint(workspace, checkpoint)


def test_checkpoint_extra_unlisted_file_is_rejected(tmp_path: Path) -> None:
    _, workspace, _, _ = prepared_workspace(tmp_path)
    checkpoint = make_checkpoint(workspace)
    (checkpoint / "extra.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(CheckpointError, match="file set"):
        validate_checkpoint(workspace, checkpoint)


def test_restore_ignores_incomplete_staging_and_uses_complete_checkpoint(tmp_path: Path) -> None:
    _, workspace, _, registry = prepared_workspace(tmp_path)
    make_checkpoint(workspace)
    incomplete = workspace.root / "checkpoints" / "incomplete.staging"
    incomplete.mkdir()
    changed = dict(registry, registry_revision=1, updated_at="2026-08-13T01:00:00Z")
    workspace.write_registry(changed)
    restored = restore_latest_checkpoint(
        workspace,
        run_id="00000000-0000-4000-8000-000000000200",
        now=fixed_now,
    )
    assert restored == ["project.json", "registry/sources.json"]
    assert json.loads((workspace.root / "registry" / "sources.json").read_text(encoding="utf-8")) == registry


def test_all_invalid_checkpoints_fail_without_changing_current_registry(tmp_path: Path) -> None:
    _, workspace, _, registry = prepared_workspace(tmp_path)
    checkpoint = make_checkpoint(workspace)
    (checkpoint / "project.json").write_text("corrupt", encoding="utf-8")
    before = (workspace.root / "registry" / "sources.json").read_bytes()
    with pytest.raises(CheckpointError, match="no complete checkpoint"):
        restore_latest_checkpoint(
            workspace,
            run_id="00000000-0000-4000-8000-000000000200",
            now=fixed_now,
        )
    assert (workspace.root / "registry" / "sources.json").read_bytes() == before


def test_valid_restore_preserves_input_bytes(tmp_path: Path) -> None:
    input_root, workspace, _, registry = prepared_workspace(tmp_path)
    before = tree_snapshot(input_root)
    make_checkpoint(workspace)
    workspace.write_registry(dict(registry, registry_revision=1, updated_at="2026-08-13T01:00:00Z"))
    restore_latest_checkpoint(
        workspace,
        run_id="00000000-0000-4000-8000-000000000200",
        now=fixed_now,
    )
    assert tree_snapshot(input_root) == before
    assert json.loads((workspace.root / "registry" / "sources.json").read_text(encoding="utf-8")) == registry


def test_checkpoint_copy_failure_never_replaces_registry(tmp_path: Path, monkeypatch) -> None:
    _, workspace, _, _ = prepared_workspace(tmp_path)
    before = (workspace.root / "registry" / "sources.json").read_bytes()
    monkeypatch.setattr(
        "qbcore.recovery.shutil.copyfile",
        lambda *_: (_ for _ in ()).throw(OSError("injected")),
    )
    with pytest.raises(OSError, match="injected"):
        create_checkpoint(
            workspace, reason="registry_update",
            uuid_factory=UUIDSequence(1), now=fixed_now,
        )
    assert (workspace.root / "registry" / "sources.json").read_bytes() == before
```

- [ ] **Step 6: Run GREEN and regression**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_recovery.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: recovery tests and the full suite pass.

**Stop condition:** If a checkpoint cannot prove a complete file/hash set, never mark it complete and never use it for restore.

---

### Task 10: Orchestrate inventory and explicit recovery through a portable CLI

**Files:**

- Create: `skills/curate-question-bank/scripts/qbcore/cli.py`
- Create: `skills/curate-question-bank/scripts/curate_question_bank.py`
- Create: `tests/test_m1_cli.py`

- [ ] **Step 1: Write failing end-to-end inventory tests**

Create `tests/test_m1_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import shutil

from conftest import REPOSITORY_ROOT
from m1_helpers import UUIDSequence, fixed_now, tree_snapshot
from qbcore.cli import run_inventory


FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "m1-discovery" / "input"


def test_run_inventory_publishes_complete_workspace_without_touching_input(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    workspace_root = input_root / ".workspace"
    before = tree_snapshot(input_root)
    result = run_inventory(
        input_root=input_root,
        workspace_root=workspace_root,
        now=fixed_now,
        uuid_factory=UUIDSequence(1),
    )
    after_without_workspace = {
        path: digest for path, digest in tree_snapshot(input_root).items()
        if not path.startswith(".workspace/")
    }
    assert before == after_without_workspace
    assert result.status == "complete"
    assert (workspace_root / "project.json").is_file()
    assert (workspace_root / "registry" / "sources.json").is_file()
    run_dir = workspace_root / "runs" / result.run_id
    assert {path.name for path in run_dir.iterdir()} == {
        "discovery.json", "issues.json", "preflight.json", "workspace-run.json"
    }
    run = json.loads((run_dir / "workspace-run.json").read_text(encoding="utf-8"))
    assert run["phase"] == "complete"
    assert run["status"] == "complete"
```

- [ ] **Step 2: Run RED**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_cli.py -q
```

Expected: collection FAIL because `qbcore.cli` does not exist.

- [ ] **Step 3: Implement workspace initialization helpers**

In `cli.py`, define:

```python
from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid4

from qbcore.capabilities import _utc_z, build_capability_matrix
from qbcore.discovery import discover_files
from qbcore.paths import PathPolicyError, RootPolicy, validate_roots
from qbcore.recovery import CheckpointError, create_checkpoint, restore_latest_checkpoint
from qbcore.registry import reconcile_registry
from qbcore.workspace import Workspace, WorkspaceWriteError
from qbcore.workspace_contracts import validate_workspace_document


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    workspace_root: Path


def system_now() -> datetime:
    return datetime.now(timezone.utc)


def system_uuid() -> UUID:
    return uuid4()


def _new_project(*, dataset_id: str, now: Callable[[], datetime]) -> dict:
    return {
        "schema_version": "1.0",
        "project_format_version": "1.0",
        "dataset_id": dataset_id,
        "created_at": _utc_z(now()),
    }


def _empty_registry(*, dataset_id: str, now: Callable[[], datetime]) -> dict:
    return {
        "schema_version": "1.0",
        "dataset_id": dataset_id,
        "registry_revision": 0,
        "updated_at": _utc_z(now()),
        "sources": [],
    }


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise WorkspaceWriteError("workspace JSON root must be an object")
    return value


def _require_document(kind: str, value: dict) -> None:
    issues = validate_workspace_document(kind, value)
    if issues:
        first = issues[0]
        raise WorkspaceWriteError(f"invalid {kind} at {first.path}: {first.message}")


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _build_workspace_issues(
    *,
    run_id: str,
    discovery_issues: list[dict],
    identity_issues: list[dict],
    uuid_factory: Callable[[], UUID],
) -> dict:
    rows: list[dict] = []
    for issue in discovery_issues:
        rows.append({
            "issue_id": str(uuid_factory()),
            "code": issue["code"],
            "status": "open",
            "summary": issue["summary"],
            "relative_paths": [issue["relative_path"]],
            "source_ids": [],
        })
    for issue in identity_issues:
        rows.append({
            "issue_id": str(uuid_factory()),
            "code": issue["code"],
            "status": "open",
            "summary": issue["summary"],
            "relative_paths": issue["relative_paths"],
            "source_ids": issue["source_ids"],
        })
    rows.sort(key=lambda item: (item["code"], item["relative_paths"], item["issue_id"]))
    return {"schema_version": "1.0", "run_id": run_id, "issues": rows}


def _complete_run_document(
    *,
    run_id: str,
    started_at: str,
    policy: RootPolicy,
    now: Callable[[], datetime],
    workspace: Workspace,
) -> dict:
    paths = (
        ("preflight", workspace.root / "runs" / run_id / "preflight.json"),
        ("discovery", workspace.root / "runs" / run_id / "discovery.json"),
        ("issues", workspace.root / "runs" / run_id / "issues.json"),
        ("registry", workspace.root / "registry" / "sources.json"),
    )
    artifacts = [{
        "kind": kind,
        "relative_path": path.relative_to(workspace.root).as_posix(),
        "content_hash": _hash_file(path),
    } for kind, path in paths]
    return {
        "schema_version": "1.0", "run_id": run_id,
        "phase": "complete", "status": "complete",
        "started_at": started_at, "updated_at": _utc_z(now()),
        "input_root_fingerprint": policy.input_fingerprint,
        "workspace_root_fingerprint": policy.workspace_fingerprint,
        "artifacts": artifacts,
    }


def _append_event_log(
    workspace: Workspace,
    run_id: str,
    event: str,
    summary: str,
    *,
    now: Callable[[], datetime],
) -> None:
    target = workspace.policy.assert_write_target(workspace.root / "logs" / "events.jsonl")
    record = {
        "timestamp": _utc_z(now()), "run_id": run_id,
        "event": event, "summary": summary,
    }
    payload = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    with target.open("ab") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
```

Existing `project.json` and registry documents are passed through `_require_document()` immediately after reading. A dataset ID mismatch is fatal. A missing project creates a new dataset ID; a missing registry for an existing project creates an empty registry with the existing dataset ID.

- [ ] **Step 4: Implement `run_inventory` in the frozen sequence**

Use this exact signature and ordering:

```python
def run_inventory(
    *,
    input_root: str | Path,
    workspace_root: str | Path,
    now: Callable[[], datetime] = system_now,
    uuid_factory: Callable[[], UUID] = system_uuid,
) -> RunResult:
    policy = validate_roots(input_root, workspace_root)
    workspace = Workspace.initialize(policy)
    run_id = str(uuid_factory())
    started_at = _utc_z(now())
    phase = "preflight"
    project_path = workspace.root / "project.json"
    registry_path = workspace.root / "registry" / "sources.json"
    try:
        if project_path.exists():
            project = _load_json(project_path)
            _require_document("workspace-project", project)
        else:
            project = _new_project(dataset_id=str(uuid_factory()), now=now)
            workspace.write_project(project)

        previous_registry = (
            _load_json(registry_path)
            if registry_path.exists()
            else _empty_registry(dataset_id=project["dataset_id"], now=now)
        )
        _require_document("source-registry", previous_registry)
        if previous_registry["dataset_id"] != project["dataset_id"]:
            raise WorkspaceWriteError("project and registry dataset IDs differ")

        preflight = build_capability_matrix(policy, now=now, skill_version="0.1.0")
        _require_document("capability-matrix", preflight)
        phase = "discovery"
        discovery = discover_files(policy, now=now)
        _require_document("discovery-inventory", discovery)
        phase = "registry"
        next_registry, identity_issues = reconcile_registry(
            previous_registry, discovery, uuid_factory=uuid_factory, now=now
        )
        _require_document("source-registry", next_registry)
        issue_rows = _build_workspace_issues(
            run_id=run_id,
            discovery_issues=discovery["issues"],
            identity_issues=identity_issues,
            uuid_factory=uuid_factory,
        )
        _require_document("workspace-issues", issue_rows)

        if registry_path.exists() and next_registry != previous_registry:
            phase = "checkpoint"
            create_checkpoint(
                workspace,
                reason="registry_update",
                uuid_factory=uuid_factory,
                now=now,
            )

        workspace.write_run_artifact(run_id, "preflight.json", preflight)
        workspace.write_run_artifact(run_id, "discovery.json", discovery)
        workspace.write_run_artifact(run_id, "issues.json", issue_rows)
        if next_registry != previous_registry or not registry_path.exists():
            workspace.write_registry(next_registry)
        _append_event_log(
            workspace, run_id, "publication_ready", "validated inventory artifacts published", now=now
        )
        complete_run = _complete_run_document(
            run_id=run_id, started_at=started_at,
            policy=policy, now=now, workspace=workspace,
        )
        _require_document("workspace-run", complete_run)
        workspace.write_run_artifact(run_id, "workspace-run.json", complete_run)
        return RunResult(run_id=run_id, status="complete", workspace_root=workspace.root)
    except Exception:
        failed = {
            "schema_version": "1.0", "run_id": run_id,
            "phase": phase, "status": "failed",
            "started_at": started_at, "updated_at": _utc_z(now()),
            "input_root_fingerprint": policy.input_fingerprint,
            "workspace_root_fingerprint": policy.workspace_fingerprint,
            "artifacts": [],
        }
        try:
            workspace.write_run_artifact(run_id, "workspace-run.json", failed)
        except Exception:
            pass
        raise
```

Because `workspace-run.json` cannot hash itself, its artifact list contains preflight, discovery, issues, and the authoritative registry. The broad exception is used only to emit best-effort structured failure state and immediately re-raise; it never converts a failure to success.

- [ ] **Step 5: Add the command parser and portable script entry**

Add:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="curate-question-bank")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory = subparsers.add_parser("inventory")
    inventory.add_argument("--input-root", required=True)
    inventory.add_argument("--workspace-root", required=True)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--input-root", required=True)
    restore.add_argument("--workspace-root", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inventory":
            result = run_inventory(
                input_root=args.input_root,
                workspace_root=args.workspace_root,
            )
        else:
            policy = validate_roots(args.input_root, args.workspace_root)
            workspace = Workspace.initialize(policy)
            run_id = str(system_uuid())
            restore_latest_checkpoint(workspace, run_id=run_id, now=system_now)
            result = RunResult(run_id, "complete", workspace.root)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"run_id": result.run_id, "status": result.status}, sort_keys=True))
    return 0
```

Create `skills/curate-question-bank/scripts/curate_question_bank.py`:

```python
from __future__ import annotations

from qbcore.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Add CLI failure and second-run tests**

Append these tests and import `pytest` plus `main`:

```python
import pytest

from qbcore.cli import main


def test_cli_requires_explicit_workspace_root(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    with pytest.raises(SystemExit) as raised:
        main(["inventory", "--input-root", str(input_root)])
    assert raised.value.code == 2
    assert list(input_root.iterdir()) == []


def test_cli_rejects_equal_roots_without_adding_input_files(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    assert main([
        "inventory", "--input-root", str(input_root),
        "--workspace-root", str(input_root),
    ]) == 2
    assert list(input_root.iterdir()) == []


def test_cli_rejects_input_inside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    input_root = workspace / "input"
    input_root.mkdir(parents=True)
    assert main([
        "inventory", "--input-root", str(input_root),
        "--workspace-root", str(workspace),
    ]) == 2


def test_second_unchanged_run_preserves_ids_but_still_hashes_every_file(
    tmp_path: Path, monkeypatch
) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    workspace = tmp_path / "workspace"
    run_inventory(
        input_root=input_root, workspace_root=workspace,
        now=fixed_now, uuid_factory=UUIDSequence(1),
    )
    before = json.loads((workspace / "registry" / "sources.json").read_text(encoding="utf-8"))
    import qbcore.discovery as discovery_module
    original = discovery_module._hash_file
    calls: list[str] = []

    def counting_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
        calls.append(path.name)
        return original(path, chunk_size)

    monkeypatch.setattr(discovery_module, "_hash_file", counting_hash)
    run_inventory(
        input_root=input_root, workspace_root=workspace,
        now=fixed_now, uuid_factory=UUIDSequence(100),
    )
    after = json.loads((workspace / "registry" / "sources.json").read_text(encoding="utf-8"))
    assert after == before
    assert len(calls) == 4


def test_changed_second_run_checkpoints_previous_registry(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    source = input_root / "source.txt"
    source.write_text("version one\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_inventory(
        input_root=input_root, workspace_root=workspace,
        now=fixed_now, uuid_factory=UUIDSequence(1),
    )
    source.write_text("version two\n", encoding="utf-8")
    run_inventory(
        input_root=input_root, workspace_root=workspace,
        now=fixed_now, uuid_factory=UUIDSequence(100),
    )
    registry = json.loads((workspace / "registry" / "sources.json").read_text(encoding="utf-8"))
    assert registry["registry_revision"] == 2
    assert len([path for path in (workspace / "checkpoints").iterdir() if not path.name.endswith(".staging")]) == 1


def test_ambiguous_rename_is_published_as_an_open_issue(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    old = input_root / "old.txt"
    old.write_text("same bytes\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_inventory(
        input_root=input_root, workspace_root=workspace,
        now=fixed_now, uuid_factory=UUIDSequence(1),
    )
    old.unlink()
    (input_root / "one.txt").write_text("same bytes\n", encoding="utf-8")
    (input_root / "two.txt").write_text("same bytes\n", encoding="utf-8")
    result = run_inventory(
        input_root=input_root, workspace_root=workspace,
        now=fixed_now, uuid_factory=UUIDSequence(100),
    )
    issues = json.loads(
        (workspace / "runs" / result.run_id / "issues.json").read_text(encoding="utf-8")
    )
    identity = [issue for issue in issues["issues"] if issue["code"] == "QB-IDENTITY-AMBIGUOUS"]
    assert len(identity) == 1 and identity[0]["status"] == "open"


def test_restore_without_checkpoint_fails_and_preserves_registry(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "source.txt").write_text("synthetic\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_inventory(
        input_root=input_root, workspace_root=workspace,
        now=fixed_now, uuid_factory=UUIDSequence(1),
    )
    registry = workspace / "registry" / "sources.json"
    before = registry.read_bytes()
    assert main([
        "restore", "--input-root", str(input_root),
        "--workspace-root", str(workspace),
    ]) == 2
    assert registry.read_bytes() == before
```

The unchanged-run test is the explicit proof that no incremental executor was smuggled into Milestone 1.

- [ ] **Step 7: Run GREEN and regression**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_cli.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: CLI tests and the full suite pass.

**Stop condition:** If end-to-end publication can expose a partially updated registry as authoritative, stop and return to Task 8/9; do not hide it with retry logic.

---

### Task 11: Prove privacy, portability, source preservation, and scope protection

**Files:**

- Create: `tests/test_m1_safeguards.py`
- Modify: `tests/test_m1_skill_package.py`
- Modify: `tests/test_m1_scope_guard.py`

- [ ] **Step 1: Write a failing repository-external portability test**

Append to `tests/test_m1_skill_package.py`:

```python
def test_copied_skill_runs_inventory_without_repository_root(tmp_path: Path) -> None:
    import json
    import os
    import shutil
    import subprocess
    import sys

    copied = tmp_path / "copied-skill"
    shutil.copytree(SKILL_ROOT, copied)
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "source.txt").write_text("portable synthetic source\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            str(copied / "scripts" / "curate_question_bank.py"),
            "inventory",
            "--input-root", str(input_root),
            "--workspace-root", str(workspace),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "complete"
    assert (workspace / "registry" / "sources.json").is_file()
```

- [ ] **Step 2: Write source-preservation and no-network tests**

Create `tests/test_m1_safeguards.py`:

```python
from __future__ import annotations

from pathlib import Path
import shutil

from conftest import REPOSITORY_ROOT, SKILL_ROOT
from m1_helpers import UUIDSequence, fixed_now, tree_snapshot
from qbcore.cli import run_inventory


FIXTURE = REPOSITORY_ROOT / "tests" / "fixtures" / "m1-discovery" / "input"


def test_full_run_preserves_every_source_byte(tmp_path: Path, monkeypatch) -> None:
    input_root = tmp_path / "input"
    shutil.copytree(FIXTURE, input_root)
    before = tree_snapshot(input_root)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network attempted")))
    run_inventory(
        input_root=input_root,
        workspace_root=tmp_path / "workspace",
        now=fixed_now,
        uuid_factory=UUIDSequence(1),
    )
    assert tree_snapshot(input_root) == before


def test_runtime_has_no_network_or_process_execution_imports() -> None:
    runtime = SKILL_ROOT / "scripts"
    text = "\n".join(path.read_text(encoding="utf-8") for path in runtime.rglob("*.py"))
    forbidden = ("import requests", "import urllib", "import httpx", "import socket", "import subprocess")
    assert not any(token in text for token in forbidden)


def test_persistent_artifacts_do_not_copy_source_text_or_absolute_paths(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    secret_marker = "SYNTHETIC-CONTENT-MUST-NOT-ENTER-STATE"
    (input_root / "source.txt").write_text(secret_marker, encoding="utf-8")
    workspace = tmp_path / "workspace"
    run_inventory(
        input_root=input_root,
        workspace_root=workspace,
        now=fixed_now,
        uuid_factory=UUIDSequence(1),
    )
    persisted = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in workspace.rglob("*") if path.is_file()
    )
    assert secret_marker not in persisted
    assert str(input_root) not in persisted
```

The runtime is allowed to use `os`, but not subprocess or network modules.

- [ ] **Step 3: Strengthen the scope guard with AST checks**

Append to `test_m1_scope_guard.py`:

```python
import ast


FORBIDDEN_CALL_NAMES = {
    "parse_question",
    "associate_answer",
    "build_candidate",
    "skip_unchanged",
}


def test_m1_runtime_does_not_define_forbidden_pipeline_functions() -> None:
    runtime = SKILL_ROOT / "scripts" / "qbcore"
    found: set[str] = set()
    for path in runtime.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found.update(
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
    assert not (found & FORBIDDEN_CALL_NAMES)


def test_m0_validator_remains_contract_only() -> None:
    text = (SKILL_ROOT / "scripts" / "qbcore" / "validation.py").read_text(encoding="utf-8")
    assert "scan directories" in text
    assert "parse source files" in text
    assert "associate cross-file content" in text
```

- [ ] **Step 4: Run RED before final safeguard adjustments**

Run:

```powershell
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_skill_package.py tests\test_m1_safeguards.py tests\test_m1_scope_guard.py -q
```

Expected on first run: any portability, absolute-path leakage, or runtime import violation fails with the exact offending assertion. Do not weaken a safeguard to make it pass.

- [ ] **Step 5: Make only the smallest safeguard-driven corrections**

Permitted corrections are limited to:

- replace repository-root lookups with Skill-relative paths;
- replace persisted absolute paths with root fingerprints and relative paths;
- remove a forbidden network/process import;
- remove an accidentally added parser/association/incremental function;
- make deterministic JSON and ordering stable.

Do not add compatibility aliases for forbidden behavior.

- [ ] **Step 6: Run GREEN and regression**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_skill_package.py tests\test_m1_safeguards.py tests\test_m1_scope_guard.py -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: all safeguard tests and the complete suite pass.

**Stop condition:** Any requirement for a repository root, network access, external runtime dependency, or real user data blocks Milestone 1 acceptance.

---

### Task 12: Close the Milestone 1 gate and write the durable handoff

**Files:**

- Modify: `START-HERE.md`
- Modify: `NEW-THREAD-PROMPT.md`
- Modify: `docs/SIDE-CONVERSATION-HANDOFF.md`
- Test: all `tests/test_m1_*.py` and existing Milestone 0 tests

- [ ] **Step 1: Verify the authoritative design has not changed**

Run:

```powershell
Get-FileHash -Algorithm SHA256 docs\MILESTONE-1-WORKSPACE-ISOLATION-SPEC.md
```

Expected: `C61A5A79F3443318B1E35B0C793404D3D3F57F027156B84E60FA1B10ACFF96A5`. If it differs, stop and review the diff before accepting the milestone.

- [ ] **Step 2: Run forbidden-scope and placeholder scans**

Run:

```powershell
rg -n -i "TBD|TODO|implement later|以后处理|待定|类似于|add appropriate|as needed" skills tests
rg -n -i "parse_question|associate_answer|build_candidate|incremental_executor|skip_unchanged|electron|sqlite|ocr|mcp server" skills\curate-question-bank\scripts tests\test_m1_*.py
```

Expected: no unresolved placeholder in Milestone 1 files and no forbidden implementation. Documentation statements such as “does not parse questions” are allowed outside the runtime scan.

- [ ] **Step 3: Run targeted Milestone 1 tests**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests\test_m1_*.py -q
```

Expected: all Milestone 1 tests pass. Record the actual count and duration.

- [ ] **Step 4: Run full regression twice**

Run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: both runs pass with identical test counts. The original 30 Milestone 0 tests remain included.

- [ ] **Step 5: Run a manual synthetic smoke test**

Use a newly created temporary directory outside the repository. Do not use real course or research material:

```powershell
$m1Smoke = Join-Path ([System.IO.Path]::GetTempPath()) ("qb-m1-smoke-" + [guid]::NewGuid())
$m1Input = Join-Path $m1Smoke 'input'
$m1Workspace = Join-Path $m1Input '.workspace'
New-Item -ItemType Directory -Path $m1Input | Out-Null
Set-Content -LiteralPath (Join-Path $m1Input 'synthetic.txt') -Value 'synthetic local source' -Encoding utf8
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe skills\curate-question-bank\scripts\curate_question_bank.py inventory --input-root $m1Input --workspace-root $m1Workspace
Get-ChildItem -LiteralPath $m1Workspace -Recurse -File | Select-Object FullName,Length
```

Expected: exit 0, one complete run, a registry source for `synthetic.txt`, and no inventory entry under `.workspace/`. After recording evidence, remove only `$m1Smoke`, whose resolved path must still begin with the system temporary directory and contain the generated `qb-m1-smoke-` prefix.

- [ ] **Step 6: Update durable entry and handoff documents**

Update all three documents to say:

```text
Milestone 1 status: accepted only if the recorded targeted, double-regression,
portability, source-preservation, and synthetic smoke checks all pass.

Next implementation boundary: do not begin parser, answer association, or
incremental execution until a separate Milestone 2 design and plan are approved.

Resume fields:
- project_root
- authoritative_spec
- authoritative_plan
- last_completed_task_step
- last_full_test_command_and_result
- current_failure_command_exit_code_summary
- files_changed_by_current_task
- next_atomic_action
- unverified_risks
```

`START-HERE.md` points first to the current accepted milestone and its test command. `NEW-THREAD-PROMPT.md` contains a copy-ready prompt that starts at the recorded next atomic action rather than replaying product history. `SIDE-CONVERSATION-HANDOFF.md` replaces stale “Milestone 0 not run” claims with observed results.

- [ ] **Step 7: Read back the handoff and run the final suite**

Run:

```powershell
rg -n "Milestone 1|authoritative_spec|authoritative_plan|last_completed_task_step|parser|答案关联|增量" START-HERE.md NEW-THREAD-PROMPT.md docs\SIDE-CONVERSATION-HANDOFF.md
$env:PYTHONDONTWRITEBYTECODE='1'
D:\R\miniconda\python.exe -m pytest -p no:cacheprovider tests -q
```

Expected: the three documents agree on the milestone state and next boundary, and the full suite passes.

**Acceptance:** Milestone 1 is accepted only after all 18 design acceptance conditions map to passing tests or explicit read-back evidence. Report actual test counts, commands, changed files, smoke-test evidence, undisclosed-known-high-risk-defect status, and unverified platform areas. Do not claim that no high-risk defect exists; state whether any known high-risk defect remains undisclosed.

**Stop condition:** Any failing safeguard, non-portable lookup, source mutation, partial registry publication, invalid recovery, or forbidden parser/association/incremental implementation keeps the milestone at FAIL.

---

## 2. Spec-to-task coverage

| Frozen design requirement | Implementation task |
|---|---|
| Skill skeleton and Agent metadata | Task 2 |
| Independent M1 persistent contracts | Task 3 |
| Explicit roots and canonical isolation | Task 4 |
| Preflight/capability matrix | Task 5 |
| Read-only deterministic discovery | Task 6 |
| File-level SourceIdentity registry | Task 7 |
| Single write boundary and atomic JSON | Task 8 |
| Checkpoint validation and recovery | Task 9 |
| Fixed run order, issues, logs, CLI | Task 10 |
| Privacy, no network, portability, no content leakage | Task 11 |
| Scope guard and Milestone 0 regression | Tasks 1, 11, 12 |
| Cross-thread blockage recovery | Task 12 and Section 3 |

## 3. Blocked-task handoff template

## Execution reporting rule

For every normal Task update, use exactly this four-line status card in plain Chinese:

```text
现在：<only the current Task / Step and its purpose>
完成：<only work completed since the previous update; write “无” if none>
验证：<exact command and concise result; write “未运行” only before verification>
下一步：<one next atomic action only>
```

Do not repeat the full Milestone plan, explain internal implementation details, list unrelated risks, or introduce new terminology in a normal update. Explain a technical term only when it blocks the current Task, using one short plain-language sentence. On a failure or stop condition, append the existing blocked-task handoff template after the four-line card.

When implementation stops, write this exact short report in the active thread or successor prompt. Do not create another process file unless the task spans threads and the existing handoff document cannot be updated safely.

```text
project_root: D:\question-bank-curator
authoritative_spec: D:\question-bank-curator\docs\MILESTONE-1-WORKSPACE-ISOLATION-SPEC.md
authoritative_plan: D:\question-bank-curator\docs\MILESTONE-1-SKILL-INFRASTRUCTURE-PLAN.md
last_completed_task_step: Task N / Step M
last_full_test_command_and_result: <exact command, exit code, count>
current_failure_command_exit_code_summary: <exact command, exit code, bounded error>
files_changed_by_current_task: <exact relative paths>
next_atomic_action: <one action only>
unverified_risks: <platform paths, junction support, filesystem atomicity, or none observed>
```

Classification:

- Expected RED: continue only when the failure matches the plan.
- Implementation defect: debug within the current task; do not start the next task.
- Environment or permission block: do not install or elevate; report and wait.
- Specification conflict: stop implementation and return to the design gate.
- External-service failure: impossible in this milestone; any network dependency is a scope violation.

## 4. Next atomic action

After plan approval, begin with:

```text
Task 1 / Step 1 — record the frozen specification hash and confirm the 30-test baseline.
```

Do not create runtime modules before that baseline is recorded.
