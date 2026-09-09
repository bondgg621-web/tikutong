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
    fields = re.findall(r"^  ([a-z_]+):", text, flags=re.MULTILINE)
    assert fields == ["display_name", "short_description", "default_prompt"]
    assert "inventory local sources" in text


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
    result = subprocess.run([sys.executable, str(copied / "scripts" / "curate_question_bank.py"), "inventory", "--input-root", str(input_root), "--workspace-root", str(workspace)], cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "complete"
    assert (workspace / "registry" / "sources.json").is_file()
