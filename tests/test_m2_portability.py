from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from conftest import REPOSITORY_ROOT, SKILL_ROOT


ENTRYPOINT_RELATIVE = Path("scripts") / "curate_question_bank.py"
APPROVED_UNSUPPORTED_LIMIT_LINES = {
    "Inventory performs deterministic file discovery and file-level SourceIdentity reconciliation. Inventory does not parse questions, infer document roles, generate candidates, or skip unchanged files as an incremental executor.",
    "This is first materialization only. A successful first parse writes the source candidate artifact under `candidates/sources/` plus `parse-report.json`, `parse-issues.json`, and `parse-run.json` under one workspace run. It never overwrites or incrementally refreshes an existing candidate artifact.",
    "This milestone does not associate answers, does not perform identity migration, and does not create decisions or validated exports. It does not support batch parsing, arbitrary Markdown interpretation, PDF/OCR, remote sources, or question-bank export. Source revisions that already have candidates require a later migration design rather than an automatic rescan.",
}
APPROVED_SIMPLE_DENIAL = re.compile(
    r"^(?:batch parsing|arbitrary markdown|pdf/ocr|remote sources?|"
    r"validated exports?|incremental refresh) (?:is|are) not supported\.$",
    flags=re.IGNORECASE,
)


def _portable_environment(cwd: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONPATH"] = str(cwd)
    return environment


def _run_copied_skill(
    copied_skill: Path,
    *arguments: str,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(copied_skill / ENTRYPOINT_RELATIVE), *arguments],
        cwd=cwd,
        env=_portable_environment(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


def test_skill_truthfully_documents_the_frozen_m2_capability() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    required_phrases = (
        "parse-single-choice",
        "--source-id",
        "strict `[single_choice]` grammar",
        "first materialization only",
        "does not associate answers",
        "does not perform identity migration",
        "`.md`",
        "`.markdown`",
        "`.txt`",
        "UTF-8",
        "UTF-8 BOM",
        "CRLF",
        "parse-report.json",
        "parse-issues.json",
        "parse-run.json",
        "candidate",
        "`0` for `complete`",
        "`3` for `needs_review`",
        "`2` for errors",
    )

    assert all(phrase in text for phrase in required_phrases)
    assert "one explicitly selected source" in text
    assert _unsupported_positive_claims(text) == []


def _unsupported_positive_claims(text: str) -> list[str]:
    unsupported = (
        "arbitrary markdown",
        "batch",
        "pdf/ocr",
        "remote",
        "validated export",
        "incremental",
        "many files",
        "multiple files",
        "at once",
        "from the web",
        "fetch sources",
        "download sources",
    )
    return [
        line
        for line in text.splitlines()
        if any(term in line.casefold() for term in unsupported)
        and line not in APPROVED_UNSUPPORTED_LIMIT_LINES
        and APPROVED_SIMPLE_DENIAL.fullmatch(line) is None
    ]


def test_skill_overclaim_guard_rejects_positive_unsupported_promises() -> None:
    assert _unsupported_positive_claims(
        "Supports batch parsing and arbitrary Markdown from remote sources."
    )
    assert _unsupported_positive_claims(
        "Does not require setup and supports batch parsing."
    )
    assert _unsupported_positive_claims(
        "Can parse many files at once and fetch sources from the web."
    )
    assert _unsupported_positive_claims("Batch parsing is not supported.") == []


def test_agent_metadata_advertises_only_inventory_and_one_source_parse() -> None:
    text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert re.fullmatch(
        r'interface:\n'
        r'  display_name: "Question Bank Curator"\n'
        r'  short_description: "Inventory sources and parse one strict single-choice file"\n'
        r'  default_prompt: "Use \$curate-question-bank to inventory local sources or parse one explicitly selected strict single-choice source into first-materialization candidates\."\n',
        text,
    )
    assert not any(
        overclaim in text.casefold()
        for overclaim in (
            "batch",
            "answer association",
            "identity migration",
            "pdf",
            "ocr",
            "remote",
            "validated export",
            "incremental refresh",
        )
    )


def test_copied_skill_runs_inventory_and_parse_outside_repository(
    tmp_path: Path,
) -> None:
    portable_root = tmp_path / "portable_case"
    copied_skill = portable_root / "copied_skill"
    input_root = portable_root / "input"
    workspace_root = portable_root / "workspace"
    portable_root.mkdir()
    blocked_root = os.path.normcase(os.path.realpath(REPOSITORY_ROOT))
    guard_marker = portable_root / "guard-loaded.txt"
    (portable_root / "sitecustomize.py").write_text(
        "import os\n"
        "import sys\n"
        f"BLOCKED_ROOT = {blocked_root!r}\n"
        f"MARKER = {str(guard_marker)!r}\n"
        "with open(MARKER, 'w', encoding='utf-8') as stream:\n"
        "    stream.write('loaded')\n"
        "def is_blocked(path):\n"
        "    try:\n"
        "        value = os.path.normcase(os.path.realpath(os.path.abspath(os.fsdecode(os.fspath(path)))))\n"
        "        return os.path.commonpath((value, BLOCKED_ROOT)) == BLOCKED_ROOT\n"
        "    except (TypeError, ValueError, OSError):\n"
        "        return False\n"
        "def audit(event, args):\n"
        "    paths = []\n"
        "    if event == 'open' and args:\n"
        "        paths = [args[0]]\n"
        "    elif event == 'import' and len(args) > 1:\n"
        "        paths = [args[1]]\n"
        "    elif event in {'os.listdir', 'os.scandir'} and args:\n"
        "        paths = [args[0]]\n"
        "    if any(is_blocked(path) for path in paths if path is not None):\n"
        "        raise PermissionError('original repository access blocked')\n"
        "sys.addaudithook(audit)\n",
        encoding="utf-8",
    )
    shutil.copytree(
        SKILL_ROOT,
        copied_skill,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    input_root.mkdir()
    source_text = (
        "1. [single_choice] Portable synthetic stem?\n"
        "- A. Portable synthetic option one\n"
        "- B. Portable synthetic option two\n"
    )
    (input_root / "portable.MARKDOWN").write_text(source_text, encoding="utf-8")

    assert str(portable_root).isascii()
    assert not copied_skill.resolve().is_relative_to(REPOSITORY_ROOT.resolve())
    blocked_file = REPOSITORY_ROOT / "skills" / "curate-question-bank" / "SKILL.md"
    blocked_module = (
        REPOSITORY_ROOT
        / "skills"
        / "curate-question-bank"
        / "scripts"
        / "qbcore"
        / "cli.py"
    )
    blocked_probes = (
        f"import os; os.open({str(blocked_file)!r}, os.O_RDONLY)",
        (
            "import importlib.util; "
            f"spec = importlib.util.spec_from_file_location('blocked_cli', {str(blocked_module)!r}); "
            "module = importlib.util.module_from_spec(spec); "
            "spec.loader.exec_module(module)"
        ),
    )
    for probe in blocked_probes:
        blocked = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=portable_root,
            env=_portable_environment(portable_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
        assert blocked.returncode != 0
        assert "original repository access blocked" in blocked.stderr
    inventory = _run_copied_skill(
        copied_skill,
        "inventory",
        "--input-root",
        str(input_root),
        "--workspace-root",
        str(workspace_root),
        cwd=portable_root,
    )
    assert inventory.returncode == 0, inventory.stderr
    assert guard_marker.read_text(encoding="utf-8") == "loaded"
    assert json.loads(inventory.stdout)["status"] == "complete"
    registry = json.loads(
        (workspace_root / "registry" / "sources.json").read_text(encoding="utf-8")
    )
    source_id = registry["sources"][0]["source_id"]

    parsed = _run_copied_skill(
        copied_skill,
        "parse-single-choice",
        "--input-root",
        str(input_root),
        "--workspace-root",
        str(workspace_root),
        "--source-id",
        source_id,
        cwd=portable_root,
    )
    assert parsed.returncode == 0, parsed.stderr
    assert json.loads(parsed.stdout)["status"] == "complete"
    assert parsed.stderr == ""

    candidate = json.loads(
        (
            workspace_root / "candidates" / "sources" / f"{source_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert len(candidate["candidates"]) == 1
    assert candidate["candidates"][0]["stem"] == "Portable synthetic stem?"
    workspace_documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in workspace_root.rglob("*.json")
    ]
    assert workspace_documents
    persisted = "\n".join(
        path.read_text(encoding="utf-8")
        for path in workspace_root.rglob("*.json")
    )
    assert str(REPOSITORY_ROOT) not in persisted
    assert str(input_root) not in persisted
    assert str(workspace_root) not in persisted
    assert (copied_skill / "schemas" / "candidate.schema.json").is_file()
    assert (
        copied_skill / "schemas" / "single-choice-parse-report.schema.json"
    ).is_file()
    assert (copied_skill / "references" / "identity-contract.md").is_file()
